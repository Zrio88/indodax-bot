"""Parameter sweep to find optimal config for walk-forward backtest."""
import sys
sys.path.insert(0, "/home/get/projects/indodax-bot")

from dotenv import load_dotenv
load_dotenv()

import json
import itertools
import numpy as np
import pandas as pd

from lib.config import BotConfig
from lib.storage import TradeStore
from lib.indicators import Indicators
from lib.sentiment import FearGreedSentiment
from lib.phantom import PhantomDetector
from lib.risk import RiskManager

store = TradeStore()
PAIRS = ["BTC/IDR", "ETH/IDR", "SOL/IDR"]
BALANCE = 500_000
phantom = PhantomDetector()

# Grid search configs
RR_VALUES = [1.5, 2.0, 2.5, 3.0]
SL_FLOOR_VALUES = [0.01, 0.02, 0.03]
TRAIL_VALUES = [0.02, 0.05, 0.10]
ATR_MULT_VALUES = [2.0, 2.5, 3.0]
THRESHOLD_VALUES = [0.18, 0.22, 0.26]


def run_backtest_cfg(cfg, df_dict: dict) -> dict:
    """Run single backtest with given config over all pairs."""
    total = {"wins": 0, "losses": 0, "pnl": 0.0, "dd": 0.0}
    
    for pair in PAIRS:
        if pair not in df_dict:
            continue
        df = df_dict[pair].copy()
        risk = RiskManager(store)
        balance = BALANCE
        trades = []
        equity = [balance]

        for i in range(100, len(df)):
            row = df.iloc[i]
            window = df.iloc[:i + 1]
            close = row["close"]

            score = Indicators.signal_score(row, phantom_penalty=phantom.analyze(window)["phantom_score"])
            sig = score["total"]

            atr = row.get("atr_14")
            atr_val = atr if pd.notna(atr) and atr > 0 else None

            open_t = [t for t in trades if t["status"] == "open" and t["pair"] == pair]

            if not open_t:
                if sig >= cfg.signal_threshold:
                    # Manual sizing since risk manager uses global config
                    current_b = BALANCE + sum(
                        t2["size_idr"] * ((t2.get("exit_price", t2["entry_price"]) / t2["entry_price"]) - 1)
                        for t2 in trades if t2["status"] == "closed")
                    
                    if atr_val:
                        stop_dist = max((atr_val * cfg.stop_loss_atr_mult) / close, cfg.stop_loss_min_pct)
                        size = (current_b * cfg.risk_per_trade_pct) / stop_dist
                    else:
                        size = current_b * cfg.risk_per_trade_pct / cfg.stop_loss_min_pct
                    
                    size = max(cfg.min_notional_idr, min(size, cfg.max_order_idr))

                    if atr_val:
                        sl = close - (atr_val * cfg.stop_loss_atr_mult)
                        max_sl = close * (1 - cfg.hard_stop_loss_pct)
                        min_sl = close * (1 - cfg.stop_loss_min_pct)
                        sl = min(max(sl, max_sl), min_sl)
                        tp = close + (close - sl) * cfg.take_profit_rr
                    else:
                        sl = close * (1 - cfg.hard_stop_loss_pct)
                        tp = close + (close - sl) * cfg.take_profit_rr

                    trade = {
                        "pair": pair, "entry_price": close,
                        "size_idr": size, "stop_loss": sl, "take_profit": tp,
                        "status": "open", "exit_pnl": 0, "exit_reason": None,
                    }
                    balance -= size
                    trades.append(trade)
            else:
                t = open_t[0]
                hi, lo = row["high"], row["low"]
                entry = t["entry_price"]

                if lo <= t["stop_loss"]:
                    exit_p = t["stop_loss"]
                    pnl = exit_p / entry - 1
                    t.update(status="closed", exit_price=exit_p, pnl_pct=pnl, exit_reason="stop_loss")
                    balance += t["size_idr"] * (1 + pnl)
                elif hi >= t["take_profit"]:
                    exit_p = t["take_profit"]
                    pnl = exit_p / entry - 1
                    t.update(status="closed", exit_price=exit_p, pnl_pct=pnl, exit_reason="take_profit")
                    balance += t["size_idr"] * (1 + pnl)
                elif pd.notna(atr) and atr > 0:
                    atr_stop_dist = atr * cfg.atr_trailing_mult
                    pnl_pct = close / entry - 1
                    if pnl_pct >= cfg.trailing_stop_min_pnl and (close - atr_stop_dist) < entry:
                        t.update(status="closed", exit_price=close, pnl_pct=pnl_pct, exit_reason="trailing_stop")
                        balance += t["size_idr"] * (1 + pnl_pct)

            equity.append(balance)

        closed = [t for t in trades if t["status"] == "closed"]
        wins = sum(1 for t in closed if t["pnl_pct"] > 0)
        losses = len(closed) - wins
        pnl = balance - BALANCE
        avg_win = np.mean([t["pnl_pct"] for t in closed if t["pnl_pct"] > 0]) if wins else 0
        avg_loss = np.mean([t["pnl_pct"] for t in closed if t["pnl_pct"] <= 0]) if losses else 0
        pf = (avg_win * wins / abs(avg_loss * losses)) if losses and avg_loss else float("inf")
        
        peak = equity[0]
        max_dd = 0
        for v in equity:
            if v > peak: peak = v
            dd = (peak - v) / peak if peak > 0 else 0
            if dd > max_dd: max_dd = dd

        total["wins"] += wins
        total["losses"] += losses
        total["pnl"] += pnl
        total["dd"] = max(total["dd"], max_dd)

    total_closed = total["wins"] + total["losses"]
    wr = total["wins"] / total_closed if total_closed else 0
    return {
        "pf": round(total.get("pf", 0) / len(PAIRS), 3) if "pf" in locals() else 0,
        "wr": wr,
        "pnl": total["pnl"],
        "dd": total["dd"],
    }


def main():
    print("=" * 90)
    print("  CONFIG PARAMETER SWEEP — Walk-Forward Optimization")
    print(f"  {len(RR_VALUES)}×RR × {len(SL_FLOOR_VALUES)}×SLfloor × {len(TRAIL_VALUES)}×trail × {len(ATR_MULT_VALUES)}×ATRmult × {len(THRESHOLD_VALUES)}×thresh")
    print(f"  = {len(RR_VALUES) * len(SL_FLOOR_VALUES) * len(TRAIL_VALUES) * len(ATR_MULT_VALUES) * len(THRESHOLD_VALUES)} combinations")
    print("=" * 90)

    # Load data once
    df_dict = {}
    for pair in PAIRS:
        df = store.load_candles(pair, limit=5000)
        if df is not None and len(df) > 500:
            df = Indicators.compute(df)
            df_dict[pair] = df.tail(2000).reset_index(drop=True)
            print(f"  Loaded {pair}: {len(df_dict[pair])} bars")

    results = []
    best_pf = 0
    best_cfg = None

    for rr, sl_floor, trail, atr_mult, thresh in itertools.product(
        RR_VALUES, SL_FLOOR_VALUES, TRAIL_VALUES, ATR_MULT_VALUES, THRESHOLD_VALUES):
        
        cfg = BotConfig(
            take_profit_rr=rr,
            stop_loss_min_pct=sl_floor,
            trailing_stop_min_pnl=trail,
            stop_loss_atr_mult=atr_mult,
            signal_threshold=thresh,
        )
        
        r = run_backtest_cfg(cfg, df_dict)
        
        results.append({
            "rr": rr, "sl_floor": sl_floor, "trail": trail,
            "atr_mult": atr_mult, "thresh": thresh,
            "pf": r["pf"], "wr": round(r["wr"], 3),
            "pnl": r["pnl"], "dd": round(r["dd"], 3),
        })

        if r["pf"] > best_pf:
            best_pf = r["pf"]
            best_cfg = (rr, sl_floor, trail, atr_mult, thresh)

    # Sort by PF descending
    results.sort(key=lambda x: x["pf"], reverse=True)

    print("\n" + "=" * 90)
    print("  TOP 20 CONFIGS BY PROFIT FACTOR")
    print("=" * 90)
    print(f"  {'RR':>4s} {'SLflr':>6s} {'Trail':>6s} {'ATRx':>5s} {'Thrsh':>6s}  "
          f"{'PF':>6s} {'WR':>5s} {'P&L':>10s} {'DD':>5s}")
    print("  " + "-" * 65)
    for r in results[:20]:
        pf_str = f"{r['pf']:.2f}" if r['pf'] != float('inf') else "INF"
        print(f"  {r['rr']:>4.1f} {r['sl_floor']:>6.0%} {r['trail']:>6.0%} "
              f"{r['atr_mult']:>5.1f} {r['thresh']:>6.2f}  "
              f"{pf_str:>6s} {r['wr']:>5.1%} {r['pnl']:>10,.0f} {r['dd']:>5.1%}")

    print("\n" + "=" * 90)
    print(f"  BEST CONFIG: RR={best_cfg[0]} SLfloor={best_cfg[1]:.0%} "
          f"Trail={best_cfg[2]:.0%} ATRx={best_cfg[3]} Thresh={best_cfg[4]:.2f}")
    print("=" * 90)

    # Save all results
    with open("tune_results.json", "w") as f:
        json.dump({"results": results, "best": best_cfg}, f, indent=2)
    print("  → Full results saved to tune_results.json")


if __name__ == "__main__":
    main()
