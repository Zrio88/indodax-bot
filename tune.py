"""Grid search parameter tuning for Indodax bot strategy."""
import sys, itertools, copy, json
sys.path.insert(0, "/home/get/projects/indodax-bot")

from dotenv import load_dotenv
load_dotenv()
import numpy as np
import pandas as pd

from lib.config import CONFIG, BotConfig
from lib.logger import get_logger
from lib.storage import TradeStore
from lib.indicators import Indicators
from lib.phantom import PhantomDetector
from lib.risk import RiskManager

log = get_logger()
store = TradeStore()

PAIRS = ["BTC/IDR", "ETH/IDR", "SOL/IDR"]
BALANCE = 500_000

# Load data once
ohlcv = {}
for pair in PAIRS:
    df = store.load_candles(pair)
    if df is not None and len(df) > 100:
        ohlcv[pair] = Indicators.compute(df)

def backtest(params: dict) -> dict:
    stop_loss = params["stop_loss"]
    tp_rr = params["tp_rr"]
    threshold = params["threshold"]
    atr_mult = params["atr_mult"]
    trail_min = params["trail_min"]
    adx_filter = params["adx_filter"]

    trades = []
    balance = BALANCE
    balance_history = [balance]

    for pair, df in ohlcv.items():
        for i in range(100, len(df)):
            window = df.iloc[:i + 1]
            row = df.iloc[i]
            close = row["close"]

            # ADX filter
            adx = row.get("adx", 0) or 0
            if adx < adx_filter:
                continue

            # Signal
            score = Indicators.signal_score(row, phantom_penalty=PhantomDetector.analyze(window)["phantom_score"])
            sig = score["total"]

            atr_val = row.get("atr_14")
            if pd.isna(atr_val) or atr_val <= 0:
                atr_val = None
            already_open = any(t["status"] == "open" and t["pair"] == pair for t in trades)
            if sig >= threshold and not already_open:
                size = RiskManager(store).position_size(close, pair, atr=atr_val)
                if size >= CONFIG.min_notional_idr:
                    trade = {
                        "pair": pair, "entry_price": close, "entry_idx": i,
                        "size_idr": size, "stop_loss": close * (1 - stop_loss),
                        "take_profit": close * (1 + stop_loss * tp_rr),
                        "status": "open",
                    }
                    balance -= size
                    trades.append(trade)

            # Exit checks
            for t in trades:
                if t["status"] != "open" or t["pair"] != pair:
                    continue
                hi, lo, entry = row["high"], row["low"], t["entry_price"]

                if lo <= t["stop_loss"]:
                    exit_p = t["stop_loss"]
                    pnl = exit_p / entry - 1
                    t.update(status="closed", exit_price=exit_p, pnl_pct=pnl, exit_reason="stop_loss")
                    balance += t["size_idr"] * (1 + pnl)
                    balance_history.append(balance)
                elif hi >= t["take_profit"]:
                    exit_p = t["take_profit"]
                    pnl = exit_p / entry - 1
                    t.update(status="closed", exit_price=exit_p, pnl_pct=pnl, exit_reason="take_profit")
                    balance += t["size_idr"] * (1 + pnl)
                    balance_history.append(balance)
                elif pd.notna(row.get("atr_14")):
                    atr_stop = row["atr_14"] * atr_mult
                    pnl = close / entry - 1
                    if pnl >= trail_min and (close - atr_stop) < entry:
                        t.update(status="closed", exit_price=close, pnl_pct=pnl, exit_reason="trailing_stop")
                        balance += t["size_idr"] * (1 + pnl)
                        balance_history.append(balance)

    closed = [t for t in trades if t["status"] == "closed"]
    wins = sum(1 for t in closed if t["pnl_pct"] > 0)
    losses = len(closed) - wins
    total_pnl = balance - BALANCE
    avg_win = np.mean([t["pnl_pct"] for t in closed if t["pnl_pct"] > 0]) if wins else 0
    avg_loss = np.mean([t["pnl_pct"] for t in closed if t["pnl_pct"] <= 0]) if losses else 0
    pf = (avg_win * wins / abs(avg_loss * losses)) if losses and avg_loss else float("inf") if wins > 0 else 0
    ret = total_pnl / BALANCE
    dd = 0.0
    peak = BALANCE
    for b in balance_history:
        peak = max(peak, b)
        dd = min(dd, (b - peak) / peak)

    return {
        "params": params,
        "entries": len(trades),
        "closed": len(closed),
        "wins": wins, "losses": losses,
        "win_rate": wins / len(closed) * 100 if closed else 0,
        "avg_win_pct": avg_win * 100,
        "avg_loss_pct": avg_loss * 100,
        "profit_factor": pf,
        "total_pnl": total_pnl,
        "return_pct": ret * 100,
        "max_drawdown_pct": dd * 100,
        "balance": balance,
    }


# Grid
GRID = {
    "threshold": [0.15, 0.18, 0.20, 0.22, 0.25],
    "stop_loss": [0.05, 0.07],
    "tp_rr": [2.0, 3.0],
    "atr_mult": [3.0, 4.0],
    "trail_min": [0.01, 0.02, 0.03],
    "adx_filter": [0, 20, 25],
}

keys = list(GRID.keys())
total = 1
for v in GRID.values():
    total *= len(v)

print(f"Tuning {total} combinations over {len(PAIRS)} pairs...")
print()

results = []
count = 0
for values in itertools.product(*[GRID[k] for k in keys]):
    params = dict(zip(keys, values))
    r = backtest(params)
    results.append(r)
    count += 1
    pf_disp = f"{r['profit_factor']:.2f}" if r['profit_factor'] != float('inf') else "INF"
    sys.stdout.write(f"\r  [{count}/{total}] th={params['threshold']:.2f} sl={params['stop_loss']:.0%} "
                     f"tp={params['tp_rr']:.1f} atr={params['atr_mult']:.1f} "
                     f"tm={params['trail_min']:.0%} adx={params['adx_filter']} "
                     f"→ PF={pf_disp} r={r['return_pct']:+.2f}% wr={r['win_rate']:.0f}% "
                     f"n={r['closed']} dd={r['max_drawdown_pct']:.1f}%{' ' * 20}")
    sys.stdout.flush()

print("\n\n")

# Rank — profitable first (PF >= 1.1), sorted by PF desc then return desc
profitable = [r for r in results if r["profit_factor"] >= 1.1 and r["closed"] >= 5]
unprofitable = [r for r in results if r not in profitable]

profitable.sort(key=lambda r: (-r["profit_factor"], -r["return_pct"]))
unprofitable.sort(key=lambda r: (-r["profit_factor"], -r["return_pct"]))

print("=" * 130)
print(f"  TOP 20 PROFITABLE SETUPS (PF >= 1.1, closed >= 5)")
print("=" * 130)
print(f"  {'#':>3} {'thresh':>6} {'SL':>5} {'TP_RR':>5} {'ATRx':>4} {'Trail':>6} {'ADXf':>4} "
      f"{'Entries':>7} {'Closed':>7} {'WR':>5} {'AvgW':>6} {'AvgL':>6} {'PF':>5} "
      f"{'PnL':>10} {'Ret':>6} {'DD':>5}")
print("-" * 130)
for i, r in enumerate(profitable[:20]):
    p = r["params"]
    pf_disp = f"{r['profit_factor']:.2f}" if r['profit_factor'] != float('inf') else " INF"
    print(f"  {i+1:>3} {p['threshold']:>6.2f} {p['stop_loss']:>4.0%} {p['tp_rr']:>5.1f} "
          f"{p['atr_mult']:>4.1f} {p['trail_min']:>5.0%} {p['adx_filter']:>4d} "
          f"{r['entries']:>7d} {r['closed']:>7d} {r['win_rate']:>4.0f}% "
          f"{r['avg_win_pct']:>+5.2f}% {r['avg_loss_pct']:>+5.2f}% {pf_disp:>5s} "
          f"Rp{r['total_pnl']:>+8,.0f} {r['return_pct']:>+5.1f}% {r['max_drawdown_pct']:>4.1f}%")

print()
print("=" * 130)
print(f"  TOP 10 UNPROFITABLE SETUPS (for reference)")
print("=" * 130)
print(f"  {'#':>3} {'thresh':>6} {'SL':>5} {'TP_RR':>5} {'ATRx':>4} {'Trail':>6} {'ADXf':>4} "
      f"{'Entries':>7} {'Closed':>7} {'WR':>5} {'AvgW':>6} {'AvgL':>6} {'PF':>5} "
      f"{'PnL':>10} {'Ret':>6} {'DD':>5}")
print("-" * 130)
for i, r in enumerate(unprofitable[:10]):
    p = r["params"]
    pf_disp = f"{r['profit_factor']:.2f}" if r['profit_factor'] != float('inf') else " INF"
    print(f"  {i+1:>3} {p['threshold']:>6.2f} {p['stop_loss']:>4.0%} {p['tp_rr']:>5.1f} "
          f"{p['atr_mult']:>4.1f} {p['trail_min']:>5.0%} {p['adx_filter']:>4d} "
          f"{r['entries']:>7d} {r['closed']:>7d} {r['win_rate']:>4.0f}% "
          f"{r['avg_win_pct']:>+5.2f}% {r['avg_loss_pct']:>+5.2f}% {pf_disp:>5s} "
          f"Rp{r['total_pnl']:>+8,.0f} {r['return_pct']:>+5.1f}% {r['max_drawdown_pct']:>4.1f}%")

# Save all to JSON
with open("tune_results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
print(f"\nAll {total} results saved to tune_results.json")

# Summary stats
pf_ge_1 = sum(1 for r in results if r["profit_factor"] >= 1.0)
pf_ge_12 = sum(1 for r in results if r["profit_factor"] >= 1.2)
pf_ge_15 = sum(1 for r in results if r["profit_factor"] >= 1.5)
print(f"\nSummary: {total} combos → PF>=1.0: {pf_ge_1} ({pf_ge_1/total*100:.1f}%), "
      f"PF>=1.2: {pf_ge_12} ({pf_ge_12/total*100:.1f}%), "
      f"PF>=1.5: {pf_ge_15} ({pf_ge_15/total*100:.1f}%)")
