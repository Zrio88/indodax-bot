"""Test RSI strategy across different market regimes."""
import sys; sys.path.insert(0, "/home/get/projects/indodax-bot")
from dotenv import load_dotenv; load_dotenv()
import numpy as np, pandas as pd
from lib.storage import TradeStore
from lib.indicators import Indicators

store = TradeStore()
PAIRS = ["BTC/IDR", "ETH/IDR", "SOL/IDR"]
BALANCE = 500_000

for pair in PAIRS:
    df = store.load_candles(pair, limit=5000)
    if df is None or len(df) < 500: continue
    df = Indicators.compute(df).tail(2000).reset_index(drop=True)
    
    print(f"\n{'='*70}")
    perc = pair.split("/")[0]
    
    # Split into 4 windows of 500 bars (~21 days each)
    for win_idx in range(4):
        start = win_idx * 500
        end = (win_idx + 2) * 500  # 1000 bars per window  
        if end > len(df): break
        sub = df.iloc[start:end].reset_index(drop=True)
        
        bhr = sub["close"].iloc[-1] / sub["close"].iloc[0] - 1
        vol = sub["close"].pct_change().std() * 100
        
        # Test RSI<25 long (enter 30% of balance, SL=2%, TP=4%)
        balance = BALANCE
        trades = []
        equity = [balance]
        sl_pct = 0.02
        
        for i in range(100, len(sub)):
            row = sub.iloc[i]; close = row["close"]
            rsi = row.get("rsi_14", 50)
            open_t = [t for t in trades if t["status"] == "open"]
            if not open_t and rsi < 25:
                sz = balance * 0.15  # 15% per trade
                sz = min(max(sz, 10000), 500000)
                tp = close * 1.04  # 4% TP
                sl = close * 0.98   # 2% SL
                trades.append({"entry": close, "sz": sz, "sl": sl, "tp": tp, "status": "open"})
                balance -= sz
            elif open_t:
                t = open_t[0]; hi, lo = row["high"], row["low"]
                if lo <= t["sl"]:
                    p = t["sl"]/t["entry"] - 1; t["pnl"] = p; t["status"]="closed"; balance += t["sz"]*(1+p)
                elif hi >= t["tp"]:
                    p = t["tp"]/t["entry"] - 1; t["pnl"] = p; t["status"]="closed"; balance += t["sz"]*(1+p)
            equity.append(balance)
        
        closed = [t for t in trades if t["status"]=="closed"]
        wins = sum(1 for t in closed if t["pnl"] > 0)
        losses = len(closed) - wins
        pnl = balance - BALANCE
        aw = np.mean([t["pnl"] for t in closed if t["pnl"]>0]) if wins else 0
        al = np.mean([t["pnl"] for t in closed if t["pnl"]<=0]) if losses else 0
        pf = (aw*wins/abs(al*losses)) if losses and al else float("inf")
        peak = equity[0]; dd = 0
        for v in equity:
            if v>peak: peak=v
            d = (peak-v)/(peak or 1); 
            if d>dd: dd=d
        
        print(f"  {perc} win{win_idx+1} (bar {start}-{end}): "
              f"BHR={bhr*100:+.1f}% vol={vol:.2f}% | "
              f"trades={wins}W/{losses}L PF={pf:.2f} P&L={pnl:+,.0f} DD={dd*100:.1f}%")
