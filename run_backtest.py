"""Standalone backtest using real bot components."""
import sys
sys.path.insert(0, "/home/get/projects/indodax-bot")

from dotenv import load_dotenv
load_dotenv()

import numpy as np
import pandas as pd

from lib.config import CONFIG
from lib.logger import get_logger
from lib.storage import TradeStore
from lib.indicators import Indicators
from lib.sentiment import FearGreedSentiment
from lib.phantom import PhantomDetector
from lib.risk import RiskManager

log = get_logger()
store = TradeStore()

PAIRS = ["BTC/IDR", "ETH/IDR", "SOL/IDR"]
BALANCE = CONFIG.initial_balance_idr


def backtest_main() -> dict:
    ohlcv = {}
    for pair in PAIRS:
        df = store.load_candles(pair)
        if df is not None and len(df) > 100:
            ohlcv[pair] = Indicators.compute(df)
            log.info("loaded", pair=pair, bars=len(ohlcv[pair]))

    if not ohlcv:
        log.error("no_data")
        return {"error": "no data"}

    risk = RiskManager(store)

    trades = []
    balance = BALANCE

    for pair, df in ohlcv.items():
        log.info("scanning", pair=pair, bars=len(df))
        for i in range(100, len(df)):
            window = df.iloc[:i + 1]
            row = df.iloc[i]
            close = row["close"]

            score = Indicators.signal_score(
                row, phantom_penalty=PhantomDetector.analyze(window)["phantom_score"])
            sig = score["total"]

            if sig >= CONFIG.signal_threshold:
                atr = row.get("atr_14")
                atr_val = atr if pd.notna(atr) and atr > 0 else None
                size = risk.position_size(close, pair, atr=atr_val)
                already_open = any(t["status"] == "open" and t["pair"] == pair for t in trades)
                if not already_open and size >= CONFIG.min_notional_idr:
                    atr = row.get("atr_14")
                    atr_val = atr if pd.notna(atr) and atr > 0 else None
                    trade = {
                        "pair": pair, "side": "buy",
                        "entry_idx": i,
                        "entry_price": close,
                        "entry_time": str(row["timestamp"]),
                        "amount": size / close,
                        "size_idr": size,
                        "stop_loss": risk.stop_loss(close, size, atr_val),
                        "take_profit": risk.take_profit(close, size, atr_val),
                        "signal_score": sig,
                        "status": "open",
                        "pnl_pct": 0.0,
                        "exit_reason": None,
                    }
                    balance -= size
                    trades.append(trade)

        for t in trades:
                if t["status"] != "open" or t["pair"] != pair:
                    continue
                hi, lo = row["high"], row["low"]
                entry = t["entry_price"]

                if lo <= t["stop_loss"]:
                    exit_p = t["stop_loss"]
                    pnl_pct = exit_p / entry - 1
                    t.update(status="closed", exit_price=exit_p,
                             exit_time=str(row["timestamp"]),
                             pnl_pct=pnl_pct, exit_reason="stop_loss")
                    balance += t["size_idr"] * (1 + pnl_pct)
                elif hi >= t["take_profit"]:
                    exit_p = t["take_profit"]
                    pnl_pct = exit_p / entry - 1
                    t.update(status="closed", exit_price=exit_p,
                             exit_time=str(row["timestamp"]),
                             pnl_pct=pnl_pct, exit_reason="take_profit")
                    balance += t["size_idr"] * (1 + pnl_pct)
                elif pd.notna(row.get("atr_14")):
                    atr_stop = row["atr_14"] * CONFIG.atr_trailing_mult
                    pnl = close / entry - 1
                    if pnl >= CONFIG.trailing_stop_min_pnl and (close - atr_stop) < entry:
                        pnl_pct = close / entry - 1
                        t.update(status="closed", exit_price=close,
                                 exit_time=str(row["timestamp"]),
                                 pnl_pct=pnl_pct, exit_reason="trailing_stop")
                        balance += t["size_idr"] * (1 + pnl_pct)

    closed = [t for t in trades if t["status"] == "closed"]
    wins = sum(1 for t in closed if t["pnl_pct"] > 0)
    losses = len(closed) - wins
    total_pnl = balance - BALANCE

    avg_win = np.mean([t["pnl_pct"] for t in closed if t["pnl_pct"] > 0]) if wins else 0
    avg_loss = np.mean([t["pnl_pct"] for t in closed if t["pnl_pct"] <= 0]) if losses else 0
    pf = (avg_win * wins / abs(avg_loss * losses)) if losses and avg_loss else float("inf")

    result = {
        "entries": len(trades),
        "closed": len(closed),
        "open": len(trades) - len(closed),
        "wins": wins,
        "losses": losses,
        "win_rate": wins / len(closed) * 100 if closed else 0,
        "avg_win_pct": avg_win * 100,
        "avg_loss_pct": avg_loss * 100,
        "profit_factor": pf,
        "total_pnl": total_pnl,
        "final_balance": balance,
        "return_pct": (balance - BALANCE) / BALANCE * 100,
    }

    _print_result(result, closed, trades)
    return result


def _print_result(result: dict, closed: list, trades: list):
    print("=" * 60)
    print(f"  HASIL BACKTEST (500 IDR ~ 21 hari)")
    print("=" * 60)
    print(f"  Total entries:  {result['entries']}")
    print(f"  Closed:         {result['closed']}")
    print(f"  Open:           {result['open']}")
    print(f"  Win rate:       {result['wins']}/{result['closed']} "
          f"({result['win_rate']:.1f}%)" if result['closed'] else "  Win rate:      N/A")
    print(f"  Avg win:        {result['avg_win_pct']:.2f}%")
    print(f"  Avg loss:       {result['avg_loss_pct']:.2f}%")
    print(f"  Profit factor:  {result['profit_factor']:.2f}"
          if result['profit_factor'] != float('inf') else "  Profit factor:  INF")
    print(f"  Total P&L:      Rp{result['total_pnl']:,.0f}")
    print(f"  Balance akhir:  Rp{result['final_balance']:,.0f}")
    print(f"  Return:         {result['return_pct']:.2f}%")
    print("=" * 60)

    for t in closed:
        print(f"  {t['pair']} {t['exit_reason']:>12s}  {t['pnl_pct'] * 100:+.2f}%  Rp{t['size_idr']:,.0f}")
    for t in trades:
        if t["status"] == "open":
            print(f"  {t['pair']} {'OPEN':>12s}  entry=Rp{t['entry_price']:,.0f}  idx={t['entry_idx']}")


if __name__ == "__main__":
    backtest_main()
