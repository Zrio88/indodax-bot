"""Test mean-reversion strategies — RSI oversold bounces."""
import sys; sys.path.insert(0, "/home/get/projects/indodax-bot")
from dotenv import load_dotenv; load_dotenv()
import numpy as np, pandas as pd
from lib.storage import TradeStore
from lib.indicators import Indicators
from lib.phantom import PhantomDetector

store = TradeStore()
PAIRS = ["BTC/IDR", "ETH/IDR", "SOL/IDR"]
BALANCE = 500_000
phantom = PhantomDetector()

STRATEGIES = [
    ("rsi30_bb", 1.5, 0.02, 0.02),  # RSI<30 + close <= BB_lower, RR 1.5:1, trail 2%
    ("rsi30",    2.0, 0.02, 0.02),  # RSI<30 only, RR 2:1, trail 2%
    ("rsi35_bb", 1.5, 0.02, 0.02),  # RSI<35 + BB touch
    ("rsi25",    2.0, 0.02, 0.02),  # RSI<25 only, RR 2:1
    ("rsi30_adx",1.5, 0.02, 0.02),  # RSI<30 + ADX<25 (ranging only)
]

def backtest_mr(strat_name, rr, sl_pct, trail_pct, df):
    balance = BALANCE
    trades = []
    equity = [balance]
    
    for i in range(100, len(df)):
        row = df.iloc[i]
        close = row["close"]
        atr_v = row.get("atr_14")
        open_t = [t for t in trades if t["status"] == "open"]
        
        if not open_t:
            # Entry conditions
            rsi = row.get("rsi_14", 50)
            bb_low = row.get("bb_lower", 0)
            adx = row.get("adx", 0)
            
            enter = False
            if "rsi30" in strat_name and rsi < 30:
                enter = True
            elif "rsi35" in strat_name and rsi < 35:
                enter = True
            elif "rsi25" in strat_name and rsi < 25:
                enter = True
            
            # BB filter
            if "bb" in strat_name and enter:
                if pd.notna(bb_low) and close > bb_low:
                    enter = False  # Must touch or be below BB lower
                    
            # ADX filter (only in ranging market)
            if "adx" in strat_name and enter:
                if pd.notna(adx) and adx > 25:
                    enter = False
            
            if enter:
                sz = balance * 0.3  # Use 30% of balance
                sz = min(max(sz, 10000), sz)
                sl = close * (1 - sl_pct)
                tp = close * (1 + sl_pct * rr)  # TP = SL * RR
                
                # Also use ATR for SL if available
                if pd.notna(atr_v) and atr_v > 0:
                    atr_sl = close - atr_v * 1.5  # 1.5x ATR tight stop
                    sl = max(atr_sl, sl)  # Don't go below min SL
                    
                trades.append({"entry_price": close, "size_idr": sz, "stop_loss": sl, "take_profit": tp, "status": "open"})
                balance -= sz
        else:
            t = open_t[0]
            hi, lo = row["high"], row["low"]
            e = t["entry_price"]
            if lo <= t["stop_loss"]:
                p = t["stop_loss"] / e - 1; t["pnl_pct"] = p; t["status"] = "closed"
                balance += t["size_idr"] * (1 + p)
            elif hi >= t["take_profit"]:
                p = t["take_profit"] / e - 1; t["pnl_pct"] = p; t["status"] = "closed"
                balance += t["size_idr"] * (1 + p)
            else:
                # Trailing at trail_pct profit (only activates after profit threshold)
                pnl_pct = close / e - 1
                if pnl_pct >= trail_pct and pnl_pct < 0:
                    # If we're at a loss and trailing wants to exit... skip
                    pass
                elif pnl_pct >= trail_pct and (close - atr_v * 2.5) < e:
                    t["pnl_pct"] = pnl_pct; t["status"] = "closed"
                    balance += t["size_idr"] * (1 + pnl_pct)
                    
        equity.append(balance)

    closed = [t for t in trades if t["status"] == "closed"]
    wins = sum(1 for t in closed if t["pnl_pct"] > 0)
    losses = len(closed) - wins
    pnl = balance - BALANCE
    aw = np.mean([t["pnl_pct"] for t in closed if t["pnl_pct"] > 0]) if wins else 0
    al = np.mean([t["pnl_pct"] for t in closed if t["pnl_pct"] <= 0]) if losses else 0
    pf = (aw * wins / abs(al * losses)) if losses and al else float("inf")
    peak = equity[0]; dd = 0
    for v in equity:
        if v > peak: peak = v
        d = (peak - v) / peak if peak > 0 else 0
        if d > dd: dd = d
    return wins, losses, round(pnl), round(pf, 2), round(dd*100, 1), len(closed)

# Load data
df_dict = {}
for pair in PAIRS:
    df = store.load_candles(pair, limit=5000)
    if df is not None and len(df) > 500:
        df_dict[pair] = Indicators.compute(df).tail(2000).reset_index(drop=True)

print(f"{'Strategy':>12s}  {'RR':>4s} {'SL%':>5s} {'Trail':>5s}  ", end="")
for pair in PAIRS:
    p = pair.split("/")[0]
    print(f"{p+'_W/L':>12s} {p+'_PF':>6s} {p+'_P&L':>10s} {p+'_DD':>5s}  ", end="")
print()

for name, rr, sl_pct, trail_pct in STRATEGIES:
    line = f"{name:>12s}  {rr:>4.1f} {sl_pct:>5.0%} {trail_pct:>5.0%}  "
    all_w = all_l = 0
    for pair in PAIRS:
        w, l, pnl, pf, dd, total_trades = backtest_mr(name, rr, sl_pct, trail_pct, df_dict[pair])
        all_w += w; all_l += l
        line += f"{w:>2.0f}W/{l:<2.0f}L {pf:>6.2f} {pnl:>10,.0f} {dd:>5.1f}%  "
    print(line)
