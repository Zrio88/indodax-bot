"""Walk-forward backtest: validate config across time windows.
Pure RSI mean-reversion strategy with optional volume filter."""
import sys
sys.path.insert(0, "/home/get/projects/indodax-bot")

from dotenv import load_dotenv
load_dotenv()

import json
import numpy as np
import pandas as pd

from lib.config import CONFIG
from lib.storage import TradeStore
from lib.indicators import Indicators
from lib.risk import RiskManager

store = TradeStore()
PAIRS = CONFIG.pairs
BALANCE = CONFIG.initial_balance_idr


def pair_config(pair: str):
    ppc = CONFIG.per_pair.get(pair)
    return {
        "sl_mult": ppc.stop_loss_atr_mult if ppc and ppc.stop_loss_atr_mult is not None else CONFIG.stop_loss_atr_mult,
        "rr": ppc.take_profit_rr if ppc and ppc.take_profit_rr is not None else CONFIG.take_profit_rr,
        "rsi_long": ppc.rsi_long_threshold if ppc and ppc.rsi_long_threshold is not None else CONFIG.rsi_long_threshold,
        "rsi_short": ppc.rsi_short_threshold if ppc and ppc.rsi_short_threshold is not None else CONFIG.rsi_short_threshold,
    }


def backtest_window(df: pd.DataFrame, pair: str) -> dict:
    risk = RiskManager(store)
    balance = BALANCE
    trades = []
    equity_curve = [balance]
    pc = pair_config(pair)

    for i in range(100, len(df)):
        row = df.iloc[i]
        close = row["close"]
        rsi = row.get("rsi_14", 50)
        atr = row.get("atr_14")
        atr_val = atr if pd.notna(atr) and atr > 0 else None

        open_t = [t for t in trades if t["status"] == "open" and t["pair"] == pair]

        if not open_t:
            direction = None
            if pd.notna(rsi) and rsi < pc["rsi_long"]:
                direction = "long"
            elif pd.notna(rsi) and rsi > pc["rsi_short"]:
                direction = "short"

            if direction:
                size = risk.position_size(close, pair, regime_mult=1.0, atr=atr_val)
                if size >= CONFIG.min_notional_idr:
                    if direction == "long":
                        sl = risk.stop_loss(close, size, atr_val, mult=pc["sl_mult"])
                        tp = risk.take_profit(close, size, atr_val, mult=pc["sl_mult"], rr=pc["rr"])
                    else:
                        sl = risk.stop_loss_short(close, size, atr_val, mult=pc["sl_mult"])
                        tp = risk.take_profit_short(close, size, atr_val, mult=pc["sl_mult"], rr=pc["rr"])
                    trade = {
                        "pair": pair, "entry_idx": i,
                        "entry_price": close,
                        "entry_time": str(row["timestamp"]),
                        "size_idr": size,
                        "stop_loss": sl,
                        "take_profit": tp,
                        "rsi": rsi,
                        "direction": direction,
                        "status": "open",
                    }
                    balance -= size
                    trades.append(trade)
        else:
            t = open_t[0]
            hi, lo = row["high"], row["low"]
            entry = t["entry_price"]
            direction = t.get("direction", "long")
            pnl_pct = (close - entry) / entry if direction == "long" else (entry - close) / entry

            if direction == "long":
                if lo <= t["stop_loss"]:
                    exit_p = t["stop_loss"]
                    pnl = exit_p / entry - 1
                    t.update(status="closed", exit_price=exit_p,
                             exit_time=str(row["timestamp"]),
                             pnl_pct=pnl, exit_reason="stop_loss")
                    balance += t["size_idr"] * (1 + pnl)
                elif hi >= t["take_profit"]:
                    exit_p = t["take_profit"]
                    pnl = exit_p / entry - 1
                    t.update(status="closed", exit_price=exit_p,
                             exit_time=str(row["timestamp"]),
                             pnl_pct=pnl, exit_reason="take_profit")
                    balance += t["size_idr"] * (1 + pnl)
                elif pd.notna(atr) and atr > 0 and pnl_pct >= CONFIG.trailing_stop_min_pnl:
                    locked = entry * (1 + CONFIG.trailing_stop_min_pnl * 0.3)
                    if close <= locked:
                        t.update(status="closed", exit_price=close,
                                 exit_time=str(row["timestamp"]),
                                 pnl_pct=pnl_pct, exit_reason="trailing_stop")
                        balance += t["size_idr"] * (1 + pnl_pct)
            else:  # short
                if hi >= t["stop_loss"]:
                    exit_p = t["stop_loss"]
                    pnl = (entry - exit_p) / entry
                    t.update(status="closed", exit_price=exit_p,
                             exit_time=str(row["timestamp"]),
                             pnl_pct=pnl, exit_reason="stop_loss")
                    balance += t["size_idr"] * (1 + pnl)
                elif lo <= t["take_profit"]:
                    exit_p = t["take_profit"]
                    pnl = (entry - exit_p) / entry
                    t.update(status="closed", exit_price=exit_p,
                             exit_time=str(row["timestamp"]),
                             pnl_pct=pnl, exit_reason="take_profit")
                    balance += t["size_idr"] * (1 + pnl)
                elif pd.notna(atr) and atr > 0 and pnl_pct >= CONFIG.trailing_stop_min_pnl:
                    locked = entry * (1 - CONFIG.trailing_stop_min_pnl * 0.3)
                    if close >= locked:
                        t.update(status="closed", exit_price=close,
                                 exit_time=str(row["timestamp"]),
                                 pnl_pct=pnl_pct, exit_reason="trailing_stop")
                        balance += t["size_idr"] * (1 + pnl_pct)

        equity_curve.append(balance)

    closed = [t for t in trades if t["status"] == "closed"]
    wins = sum(1 for t in closed if t["pnl_pct"] > 0)
    losses = len(closed) - wins
    total_pnl = balance - BALANCE

    avg_win = np.mean([t["pnl_pct"] for t in closed if t["pnl_pct"] > 0]) if wins else 0
    avg_loss = np.mean([t["pnl_pct"] for t in closed if t["pnl_pct"] <= 0]) if losses else 0
    pf = (avg_win * wins / abs(avg_loss * losses)) if losses and avg_loss else float("inf")
    max_dd = _max_drawdown(equity_curve)

    longs = sum(1 for t in closed if t.get("direction") == "long")
    shorts = sum(1 for t in closed if t.get("direction") == "short")

    return {
        "pair": pair,
        "bars": len(df),
        "entries": len(trades),
        "closed": len(closed),
        "longs": longs, "shorts": shorts,
        "wins": wins, "losses": losses,
        "win_rate_pct": wins / len(closed) * 100 if closed else 0,
        "avg_win_pct": avg_win * 100,
        "avg_loss_pct": avg_loss * 100,
        "profit_factor": round(pf, 3) if pf != float("inf") else float("inf"),
        "total_pnl_idr": total_pnl,
        "return_pct": total_pnl / BALANCE * 100,
        "max_drawdown_pct": max_dd * 100,
    }


def _max_drawdown(equity):
    peak = equity[0]
    max_dd = 0
    for v in equity:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _rsi_winrate(df: pd.DataFrame, pair: str):
    """Analyze RSI threshold win rates across the full dataset."""
    from collections import defaultdict
    results = defaultdict(lambda: {"wins": 0, "losses": 0, "forward_ret": []})

    for i in range(100, len(df) - 5):
        row = df.iloc[i]
        rsi = row.get("rsi_14", 50)
        if pd.isna(rsi):
            continue
        for thresh in [20, 22, 25, 27, 30]:
            if rsi < thresh:
                fwd = df.iloc[i + 1]["close"]
                ret = (fwd / row["close"] - 1)
                results[("long", thresh)]["forward_ret"].append(ret)
                if ret > 0:
                    results[("long", thresh)]["wins"] += 1
                else:
                    results[("long", thresh)]["losses"] += 1
            if rsi > (100 - thresh):
                fwd = df.iloc[i + 1]["close"]
                ret = (row["close"] / fwd - 1)
                results[("short", thresh)]["forward_ret"].append(ret)
                if ret > 0:
                    results[("short", thresh)]["wins"] += 1
                else:
                    results[("short", thresh)]["losses"] += 1

    print(f"\n  RSI win-rate analysis ({pair}):")
    for key in sorted(results.keys()):
        r = results[key]
        total = r["wins"] + r["losses"]
        if total > 0:
            wr = r["wins"] / total * 100
            avg_ret = np.mean(r["forward_ret"]) * 100
            print(f"    {key[0]:>5} RSI<{key[1]:>2}: {total:>4} cases  "
                  f"WR={wr:.1f}%  avg_1h_ret={avg_ret:+.3f}%")


def main():
    print("=" * 72)
    print("  WALK-FORWARD BACKTEST — RSI Mean Reversion")
    print(f"  Balance: Rp{BALANCE:,}  |  Min SL: {CONFIG.stop_loss_min_pct:.0%}")
    print(f"  Default: SL={CONFIG.stop_loss_atr_mult}x ATR  RR={CONFIG.take_profit_rr}:1"
          f"  RSI<{CONFIG.rsi_long_threshold}/>{CONFIG.rsi_short_threshold}")
    for p, pc in CONFIG.per_pair.items():
        overrides = []
        if pc.stop_loss_atr_mult is not None: overrides.append(f"SL={pc.stop_loss_atr_mult}x")
        if pc.take_profit_rr is not None: overrides.append(f"RR={pc.take_profit_rr}:1")
        if pc.rsi_long_threshold is not None: overrides.append(f"RSI_L<{pc.rsi_long_threshold}")
        if pc.rsi_short_threshold is not None: overrides.append(f"RSI_S>{pc.rsi_short_threshold}")
        if overrides:
            print(f"    {p}: {' '.join(overrides)}")
    print("=" * 72)

    all_results = []
    consolidated = {"wins": 0, "losses": 0, "entries": 0, "pnl": 0.0,
                    "longs": 0, "shorts": 0}
    max_dds = []

    for pair in PAIRS:
        df = store.load_candles(pair, limit=5000)
        if df is None or len(df) < 500:
            print(f"  ✖ {pair}: insufficient data")
            continue

        df = Indicators.compute(df)
        pc = pair_config(pair)
        print(f"\n  ── {pair} ({len(df)} bars)  [SL={pc['sl_mult']}x RR={pc['rr']}:1 RSIs<{pc['rsi_long']}/>{pc['rsi_short']}] ──")

        _rsi_winrate(df, pair)

        full = df.tail(2000).reset_index(drop=True)
        r = backtest_window(full, pair)
        all_results.append(r)
        consolidated["wins"] += r["wins"]
        consolidated["losses"] += r["losses"]
        consolidated["entries"] += r["entries"]
        consolidated["pnl"] += r["total_pnl_idr"]
        consolidated["longs"] += r["longs"]
        consolidated["shorts"] += r["shorts"]
        max_dds.append(r["max_drawdown_pct"])

        pf_str = f"{r['profit_factor']:.2f}" if r['profit_factor'] != float('inf') else "INF"
        print(f"    Full ({len(full)}b): {r['entries']} entries ({r['longs']}L/{r['shorts']}S)  "
              f"{r['wins']}W/{r['losses']}L  WR={r['win_rate_pct']:.1f}%  "
              f"PF={pf_str}  Ret={r['return_pct']:+.2f}%  DD={r['max_drawdown_pct']:.1f}%")

        w1 = full.iloc[500:1500].reset_index(drop=True)
        r1 = backtest_window(w1, pair)
        pf1 = f"{r1['profit_factor']:.2f}" if r1['profit_factor'] != float('inf') else "INF"
        print(f"    W1 (500-1499b): {r1['entries']}e {r1['wins']}W/{r1['losses']}L  "
              f"WR={r1['win_rate_pct']:.1f}%  PF={pf1}  "
              f"Ret={r1['return_pct']:+.2f}%  DD={r1['max_drawdown_pct']:.1f}%  "
              f"({r1['longs']}L/{r1['shorts']}S)")

        w2 = full.iloc[1000:2000].reset_index(drop=True)
        r2 = backtest_window(w2, pair)
        pf2 = f"{r2['profit_factor']:.2f}" if r2['profit_factor'] != float('inf') else "INF"
        print(f"    W2 (1000-1999b): {r2['entries']}e {r2['wins']}W/{r2['losses']}L  "
              f"WR={r2['win_rate_pct']:.1f}%  PF={pf2}  "
              f"Ret={r2['return_pct']:+.2f}%  DD={r2['max_drawdown_pct']:.1f}%  "
              f"({r2['longs']}L/{r2['shorts']}S)")

    total_closed = consolidated["wins"] + consolidated["losses"]
    wr = consolidated["wins"] / total_closed * 100 if total_closed else 0
    avg_pf = np.mean([r["profit_factor"] for r in all_results
                      if r["profit_factor"] != float("inf")])
    avg_dd = np.mean(max_dds) if max_dds else 0

    print("\n" + "=" * 72)
    print("  CONSOLIDATED RESULTS")
    print("=" * 72)
    print(f"  Total entries:    {consolidated['entries']}")
    print(f"  Long / Short:     {consolidated['longs']} / {consolidated['shorts']}")
    print(f"  Closed trades:    {total_closed}")
    print(f"  Win rate:         {wr:.1f}%")
    print(f"  Avg profit factor:{avg_pf:.2f}")
    print(f"  Total P&L:        Rp{consolidated['pnl']:,.0f}")
    print(f"  Avg max DD:       {avg_dd:.1f}%")
    print(f"  Return:           {consolidated['pnl'] / BALANCE * 100:.2f}%")

    grade = "PASS"
    if avg_pf < 1.2 or avg_dd > 15:
        grade = "FAIL"
    elif avg_pf < 1.5 or avg_dd > 10:
        grade = "BORDERLINE"
    print(f"  Verdict:          {grade}")
    print("=" * 72)

    with open("walk_forward_result.json", "w") as f:
        json.dump({
            "config": {
                "stop_loss_atr_mult": CONFIG.stop_loss_atr_mult,
                "take_profit_rr": CONFIG.take_profit_rr,
                "stop_loss_min_pct": CONFIG.stop_loss_min_pct,
                "hard_stop_loss_pct": CONFIG.hard_stop_loss_pct,
                "risk_per_trade_pct": CONFIG.risk_per_trade_pct,
                "rsi_long_threshold": CONFIG.rsi_long_threshold,
                "rsi_short_threshold": CONFIG.rsi_short_threshold,
            },
            "consolidated": consolidated,
            "avg_profit_factor": avg_pf,
            "avg_max_dd": avg_dd,
            "verdict": grade,
            "per_pair": all_results,
        }, f, indent=2, default=str)
    print("  → Results saved to walk_forward_result.json")


if __name__ == "__main__":
    main()
