#!/usr/bin/env python3

import os
import signal
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from lib.config import CONFIG
from lib.logger import Console, get_logger
from lib.storage import TradeStore
from lib.exchange import Exchange, BybitExchange, BinanceExchange
from lib.indicators import Indicators
from lib.phantom import PhantomDetector
from lib.adaptive import AdaptiveEngine
from lib.risk import RiskManager
from lib.exit import ExitManager
from lib.notifier import Notifier
from lib.ml import MLPredictor

log = get_logger()

SIGNAL_KEYS = ["trend", "mean_reversion", "momentum", "volume", "sentiment", "stochastic"]


def _termux_wake_lock(acquire: bool = True):
    try:
        cmd = "termux-wake-lock" if acquire else "termux-wake-unlock"
        os.system(f"{cmd} indodax-bot 2>/dev/null")
    except Exception:
        pass


def _termux_notify(title: str, msg: str):
    if not CONFIG.termux_notify:
        return
    try:
        safe_msg = msg.replace('"', "'")
        os.system(f'termux-notification --title "{title}" --content "{safe_msg}" --id indodax-bot 2>/dev/null')
    except Exception:
        pass


class Bot:
    def __init__(self, paper: bool = True):
        self.paper = paper
        self.ex = Exchange()
        
        # Validate API keys for LIVE mode
        if not paper:
            self._validate_api_keys()

        self.extra_exchanges = []
        for ex_name in CONFIG.additional_exchanges:
            ex_cls = {"bybit": BybitExchange, "binance": BinanceExchange}.get(ex_name.lower())
            if ex_cls:
                inst = ex_cls()
                if getattr(inst, "is_available", lambda: False)():
                    self.extra_exchanges.append(inst)

        self.store = TradeStore()
        self.risk = RiskManager(self.store, paper=paper)
        self.exit_mgr = ExitManager(self.store)
        self.phantom = PhantomDetector()
        self.adaptive = AdaptiveEngine()
        self.notifier = Notifier()
        self.ml = MLPredictor()
        self._dashboard = None
        self._start_dashboard()
        self._prev_weights: dict | None = None
        self._running = True
        self._last_heartbeat_ts = 0
        self._last_daily_report_ts = ""
        self._setup_signals()
        self._setup_kill_switch()
        self._mtf_data: dict[str, dict[str, pd.DataFrame]] = {}
        self._consecutive_exchange_errors = 0
        self._max_consecutive_errors = 5

    def _validate_api_keys(self):
        import os
        if CONFIG.exchange_name == "indodax":
            key = os.environ.get("INDODAX_API_KEY", "")
            secret = os.environ.get("INDODAX_API_SECRET", "")
            if not key or not secret:
                Console.error("LIVE mode requires INDODAX_API_KEY and INDODAX_API_SECRET")
                self.notifier.alert("CRITICAL: API keys missing for LIVE trading")
                raise ValueError("API keys required for LIVE trading")
            # Test connection
            try:
                self.ex.health_check()
                print("  ✓ Exchange connection verified")
            except Exception as e:
                Console.error(f"Exchange connection failed: {e}")
                raise

    def _start_dashboard(self):
        try:
            from lib.dashboard import start_dashboard as _sd
            self._dashboard = _sd(self.store)
        except Exception as e:
            pass

    def _setup_signals(self):
        def handler(signum, frame):
            sig_name = signal.Signals(signum).name
            log.info("signal_received", signal=sig_name)
            print(f"\n  Signal {sig_name} — shutting down...")
            self._running = False
        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

    def _setup_kill_switch(self):
        kill_path = os.path.join(os.path.dirname(__file__) or ".", CONFIG.kill_file)
        if os.path.exists(kill_path):
            try:
                os.remove(kill_path)
                log.info("kill_switch_cleaned", path=kill_path)
            except OSError:
                pass

    def _check_kill_switch(self):
        kill_path = os.path.join(os.path.dirname(__file__) or ".", CONFIG.kill_file)
        if os.path.exists(kill_path):
            log.warn("kill_switch_triggered", path=kill_path)
            Console.blocked(f"Kill switch {CONFIG.kill_file} detected")
            self.notifier.alert("Emergency kill switch triggered — bot stopping")
            self._running = False
            return True
        return False

    def _heartbeat(self):
        if CONFIG.heartbeat_interval_m <= 0:
            return
        now = time.time()
        if now - self._last_heartbeat_ts >= CONFIG.heartbeat_interval_m * 60:
            self._last_heartbeat_ts = now
            open_count = len(self.store.open_trades())
            total_pnl = self.store.total_pnl()
            log.info("heartbeat", open_positions=open_count,
                     total_pnl=round(total_pnl, 0), paper=self.paper)
            exchange_ok = self.ex.health_check()
            if not exchange_ok:
                log.warn("heartbeat_exchange_down")
                Console.error("Exchange unreachable on heartbeat")

    def _daily_report(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today == self._last_daily_report_ts:
            return
        self._last_daily_report_ts = today
        trades = self.store.recent_trades(100)
        total_pnl = self.store.total_pnl()
        base = CONFIG.paper_balance_idr if self.paper else CONFIG.initial_balance_idr
        balance = base + total_pnl
        open_count = len(self.store.open_trades())
        self.notifier.daily_report(trades, balance, total_pnl, open_count)
        log.info("daily_report", day=today, balance=round(balance),
                 pnl=round(total_pnl), trades=len(trades))

    def _fetch_all_timeframes(self, pair: str) -> dict[str, pd.DataFrame]:
        cached = self._mtf_data.get(pair, {})
        fresh = self.ex.fetch_ohlcv_multi(pair)
        for tf, df in fresh.items():
            if not df.empty:
                cached[tf] = Indicators.compute(df)
        self._mtf_data[pair] = cached
        return cached

    def _run_backtest(self):
        import importlib
        bt = importlib.import_module("run_backtest")
        print("=== RUNNING BACKTEST ON STARTUP ===")
        result = bt.backtest_main()
        print(f"  Backtest complete: PF={result.get('profit_factor', 0):.2f} "
              f"Return={result.get('return_pct', 0):+.2f}%")
        return result

    def _check_exchange_health(self) -> bool:
        try:
            return self.ex.health_check()
        except Exception as e:
            self._consecutive_exchange_errors += 1
            log.error("exchange_health_check_failed", error=str(e), consecutive=self._consecutive_exchange_errors)
            if self._consecutive_exchange_errors >= self._max_consecutive_errors:
                Console.error(f"Exchange error streak: {self._consecutive_exchange_errors} - circuit breaker triggered")
                self.notifier.alert(f"Circuit breaker: {self._consecutive_exchange_errors} consecutive exchange errors")
                return False
            return False

    def cycle(self):
        # Check circuit breaker
        if self._consecutive_exchange_errors >= self._max_consecutive_errors:
            Console.blocked(f"Circuit breaker active: {self._consecutive_exchange_errors} exchange errors")
            self._summary()
            return
        
        # Check exchange health
        if not self._check_exchange_health():
            if not self.paper:
                Console.blocked("Exchange unreachable - pausing cycle")
                time.sleep(30)
                return
        
        self._consecutive_exchange_errors = 0
        
        Console.banner(paper=self.paper)
        Console.header()

        open_trades = self.store.open_trades()
        print(f"  Open positions: {len(open_trades)}")

        for pair in CONFIG.pairs:
            try:
                tf_dfs = self._fetch_all_timeframes(pair)
                if not tf_dfs:
                    continue
                primary_tf = CONFIG.timeframe
                df = tf_dfs.get(primary_tf)
                if df is None or df.empty:
                    continue
                price = df["close"].iloc[-1]

                actions = self.exit_mgr.check(pair, price, df)
                for act in actions:
                    trade = act["trade"]
                    if act["action"] == "close":
                        direction = trade.get("direction", "long")
                        if direction == "long":
                            pnl = (act["price"] - trade["entry_price"]) * trade["amount"]
                            pnl_pct = (act["price"] - trade["entry_price"]) / trade["entry_price"]
                        else:
                            pnl = (trade["entry_price"] - act["price"]) * trade["amount"]
                            pnl_pct = (trade["entry_price"] - act["price"]) / trade["entry_price"]

                        if not self.paper:
                            try:
                                self.ex.market_sell(pair, trade["amount"])
                            except Exception as e:
                                Console.error(f"sell failed: {e}")
                                continue

                        self.store.close_trade(trade["id"], act["price"],
                                               pnl, pnl_pct, act["reason"])
                        self.store.update_daily_pnl(pnl)
                        self.risk.record_trade(pnl_pct, pnl)
                        if trade.get("signal_score"):
                            components = Indicators._extract_signal_components(trade)
                            if components:
                                self.adaptive.feed_trade(components, pnl_pct)
                        Console.exit(pair, act["price"], act["reason"], pnl_pct, pnl)
                        self.notifier.exit(pair, act["price"], act["reason"],
                                           pnl_pct, pnl)
                        _termux_notify("Trade Closed",
                                       f"{pair} {act['reason']} {pnl_pct:+.2%}")
                    elif act["action"] == "breakeven":
                        self.store.db.execute(
                            "UPDATE trades SET stop_loss=? WHERE id=?",
                            (act["price"], trade["id"]))
                        self.store.db.commit()
                        print(f"  ▲ BREAKEVEN SL {pair} @ Rp{act['price']:,.0f}")
            except Exception as e:
                Console.error(f"exit check {pair}: {e}")
                log.error("exit_check_failed", pair=pair, error=str(e))

        can, reason = self.risk.can_trade(self.ex)
        if not can:
            Console.blocked(reason)
            self._summary()
            return

        for pair in CONFIG.pairs:
            try:
                open_trades = self.store.open_trades()
                if any(t["pair"] == pair for t in open_trades):
                    continue
                if len(open_trades) >= CONFIG.max_open_positions:
                    continue

                tf_dfs = self._fetch_all_timeframes(pair)
                if not tf_dfs:
                    continue

                primary_tf = CONFIG.timeframe
                df = tf_dfs.get(primary_tf)
                if df is None or df.empty:
                    continue

                latest = df.iloc[-1]
                price = latest["close"]

                self.adaptive.detect_regime(df)
                phantom = self.phantom.analyze(df)

                ml_prob = None
                if CONFIG.ml_enabled:
                    ml_prob = self.ml.predict(latest)
                    if self.ml.need_retrain():
                        print(f"  ML: retraining...")
                        combined_df = None
                        for tf in CONFIG.timeframes:
                            tdf = tf_dfs.get(tf)
                            if tdf is not None:
                                combined_df = tdf if combined_df is None else pd.concat([combined_df, tdf])
                        if combined_df is not None:
                            self.ml.train(combined_df)

                rsi = latest.get("rsi_14", 50)

                ppc = CONFIG.per_pair.get(pair)
                sl_mult = ppc.stop_loss_atr_mult if ppc and ppc.stop_loss_atr_mult is not None else CONFIG.stop_loss_atr_mult
                rr = ppc.take_profit_rr if ppc and ppc.take_profit_rr is not None else CONFIG.take_profit_rr
                rsi_long = ppc.rsi_long_threshold if ppc and ppc.rsi_long_threshold is not None else CONFIG.rsi_long_threshold
                rsi_short = ppc.rsi_short_threshold if ppc and ppc.rsi_short_threshold is not None else CONFIG.rsi_short_threshold

                is_oversold = pd.notna(rsi) and rsi < rsi_long
                is_overbought = pd.notna(rsi) and rsi > rsi_short

                direction = None
                if is_oversold:
                    direction = "long"
                elif is_overbought:
                    direction = "short"

                # Only enter if signal meets minimum threshold
                if direction and rsi / 100 >= CONFIG.signal_threshold:
                    Console.pair_status(pair, price, {}, f"enter_{direction}")
                    print(f"    RSI={rsi:.0f}  SL={sl_mult}x ATR  RR={rr}:1")

                    atr = latest.get("atr_14", 0)
                    atr_val = atr if pd.notna(atr) and atr > 0 else None
                    size_idr = self.risk.position_size(
                        price, pair, regime_mult=self.adaptive.regime_sizing_mult(),
                        atr=atr_val)
                    amount = size_idr / price

                    if direction == "long":
                        if atr_val is not None:
                            sl_price = price - (atr_val * sl_mult)
                            max_sl = price * (1 - CONFIG.hard_stop_loss_pct)
                            min_sl = price * (1 - CONFIG.stop_loss_min_pct)
                            sl_price = max(min(sl_price, max_sl), min_sl)
                        else:
                            sl_price = price * (1 - CONFIG.hard_stop_loss_pct)
                        sl_dist = price - sl_price
                        tp_price = price + sl_dist * rr
                    else:  # short
                        if atr_val is not None:
                            sl_price = price + (atr_val * sl_mult)
                            max_sl = price * (1 + CONFIG.hard_stop_loss_pct)
                            min_sl = price * (1 + CONFIG.stop_loss_min_pct)
                            sl_price = min(max(sl_price, min_sl), max_sl)
                        else:
                            sl_price = price * (1 + CONFIG.hard_stop_loss_pct)
                        sl_dist = sl_price - price
                        tp_price = price - sl_dist * rr

                    Console.entry(pair, price, size_idr, rsi / 100)
                    print(f"      SL={sl_price:,.0f} ({((sl_price/price)-1)*100:+.2f}%) "
                          f"TP={tp_price:,.0f} ({((tp_price/price)-1)*100:+.2f}%) "
                          f"DIR={direction}")
                    trade = {
                        "pair": pair, "side": "sell" if direction == "short" else "buy",
                        "direction": direction,
                        "entry_price": price, "amount": amount,
                        "stop_loss": sl_price,
                        "take_profit": tp_price,
                        "size_idr": size_idr,
                        "entry_time": datetime.now(timezone.utc).isoformat(),
                        "signal_score": rsi / 100,
                        "signal_data": {"phantom_penalty": phantom.get("phantom_score", 0)},
                    }

                    if self.paper:
                        tid = self.store.add_trade(trade)
                        self.risk.paper_balance -= size_idr
                        print(f"      ✓ Paper entry (id={tid})")
                        self.notifier.entry(pair, price, size_idr, rsi / 100)
                    else:
                        try:
                            if CONFIG.use_market_orders:
                                if direction == "long":
                                    resp = self.ex.market_buy(pair, size_idr)
                                else:
                                    resp = self.ex.market_sell(pair, amount)
                            else:
                                if direction == "long":
                                    resp = self.ex.limit_buy(pair, amount, price)
                                else:
                                    resp = self.ex.limit_sell(pair, amount, price)
                            trade["client_order_id"] = resp.get("info", {}).get("clientOrderId", "")
                            tid = self.store.add_trade(trade)
                            print(f"      ✓ Order placed (id={tid})")
                            self.notifier.entry(pair, price, size_idr, rsi / 100)
                        except Exception as e:
                            Console.error(f"{direction} failed: {e}")
                            log.error("entry_failed", pair=pair, direction=direction, error=str(e))
                else:
                    Console.pair_status(pair, price, {}, "hold")
            except Exception as e:
                Console.error(f"entry scan {pair}: {e}")
                log.error("entry_scan_failed", pair=pair, error=str(e))

        if self.adaptive.weights != self._prev_weights:
            print(f"  weights: {dict(sorted(self.adaptive.weights.items()))}")
            log.info("weights_updated", weights=self.adaptive.weights)
            self._prev_weights = self.adaptive.weights.copy()

        self._summary()

    def _summary(self):
        trades = self.store.recent_trades(20)
        total_pnl = self.store.total_pnl()
        base = CONFIG.paper_balance_idr if self.paper else CONFIG.initial_balance_idr
        balance = base + total_pnl
        open_count = len(self.store.open_trades())
        Console.summary(trades, balance, total_pnl, open_count,
                        regime=self.adaptive.regime_label())

    def _reconcile_positions(self):
        if self.paper:
            return
        try:
            discrepancies = self.ex.reconcile_positions(self.store)
            if discrepancies:
                for d in discrepancies:
                    if d["type"] == "missing_position":
                        Console.error(f"Found orphaned trade: {d['trade']['id']} - {d['trade']['pair']}")
                        self.store.close_trade(
                            d["trade"]["id"], d["trade"]["entry_price"],
                            0, 0, "reconciliation_orphan"
                        )
                        log.warn("reconciliation_closed_orphan", trade_id=d["trade"]["id"])
                    elif d["type"] == "partial_fill":
                        Console.warn(f"Partial fill detected: {d['trade']['id']} - updating amount")
                        new_amount = d["actual"]
                        self.store.db.execute(
                            "UPDATE trades SET amount=? WHERE id=?",
                            (new_amount, d["trade"]["id"]))
                        self.store.db.commit()
                        log.info("reconciliation_updated_amount", 
                                 trade_id=d["trade"]["id"], old=d["expected"], new=new_amount)
        except Exception as e:
            Console.error(f"Position reconciliation failed: {e}")
            log.error("reconciliation_failed", error=str(e))

    def run(self, cycles: int | None = None):
        mode = "PAPER TRADING" if self.paper else "LIVE TRADING"
        print(f"╔{'═'*70}╗")
        print(f"║  {mode:^66} ║")
        print(f"╚{'═'*70}╝")

        if CONFIG.termux_wake_lock:
            _termux_wake_lock(acquire=True)
            print("  [Termux] Wake lock acquired")

        # Reconcile positions on startup for LIVE mode
        if not self.paper:
            print("  🔄 Reconciling positions with exchange...")
            self._reconcile_positions()
            print("  ✓ Position reconciliation complete")

        self.notifier.startup()
        _termux_notify("Bot Started", f"Mode: {mode}, Pairs: {len(CONFIG.pairs)}")

        count = 0
        while self._running and (cycles is None or count < cycles):
            if self._check_kill_switch():
                break
            try:
                self.cycle()
                count += 1
                if cycles and count >= cycles:
                    print(f"\n=== Completed {cycles} cycles ===")
                    break
                self._heartbeat()
                self._daily_report()
                interval = CONFIG.cycle_interval_s
                print(f"\n  Sleeping {interval}s...")
                print("─" * 72)
                for _ in range(interval):
                    if not self._running or self._check_kill_switch():
                        break
                    time.sleep(1)
            except Exception as e:
                Console.error(f"cycle: {e}")
                log.error("cycle_failed", error=str(e), cycle=count)
                time.sleep(60)

        self._shutdown(cycles=count)

        if CONFIG.termux_wake_lock:
            _termux_wake_lock(acquire=False)
            print("  [Termux] Wake lock released")

    def _shutdown(self, reason: str = "user_stop", cycles: int = 0):
        print("\n" + "=" * 72)
        print("  SHUTDOWN")
        print("=" * 72)

        open_count = len(self.store.open_trades())
        total_pnl = self.store.total_pnl()
        base = CONFIG.paper_balance_idr if self.paper else CONFIG.initial_balance_idr
        balance = base + total_pnl
        trades = self.store.recent_trades(50)
        Console.summary(trades, balance, total_pnl, open_count,
                        regime=self.adaptive.regime_label())

        if open_count > 0:
            print(f"\n  ⚠ {open_count} position(s) still open — will resume on next run")
            log.warn("open_positions_on_shutdown", count=open_count)

        self.notifier.shutdown(
            f"Cycles: {cycles} | Open: {open_count} | P&L: {total_pnl:+,.0f}")
        log.info("shutdown", cycles=cycles, open_positions=open_count,
                 total_pnl=round(total_pnl))
        print(f"\n  Goodbye.\n")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    is_live = "--live" in sys.argv
    do_backtest = "--backtest" in sys.argv
    bot = Bot(paper=not is_live)
    cycles = None
    for i, arg in enumerate(sys.argv):
        if arg == "--cycles" and i + 1 < len(sys.argv):
            cycles = int(sys.argv[i + 1])
    if do_backtest:
        bot._run_backtest()
    bot.run(cycles=cycles)
