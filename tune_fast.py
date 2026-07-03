"""Fast targeted config comparison — 8 candidate configs (optimized)."""
import sys; sys.path.insert(0, "/home/get/projects/indodax-bot")
from dotenv import load_dotenv; load_dotenv()
import json, numpy as np, pandas as pd, time
from lib.config import BotConfig
from lib.storage import TradeStore
from lib.indicators import Indicators
from lib.phantom import PhantomDetector

store = TradeStore()
PAIRS = ["BTC/IDR", "ETH/IDR", "SOL/IDR"]
BALANCE = 500_000
phantom = PhantomDetector()

CANDIDATES = [
    ("current",   3.0, 0.03, 0.03, 2.5, 0.22),
    ("tight",     2.0, 0.01, 0.05, 2.0, 0.22),
    ("mild",      2.0, 0.01, 0.10, 2.5, 0.22),
    ("conserv",   1.5, 0.01, 0.10, 2.0, 0.26),
    ("aggr",      2.5, 0.01, 0.05, 3.0, 0.18),
    ("trail_off", 2.0, 0.02, 0.15, 2.5, 0.22),
    ("tight_atr", 2.0, 0.01, 0.03, 1.5, 0.22),
    ("balanced",  2.0, 0.01, 0.10, 2.5, 0.24),
]

# Preload & precompute signal scores for all pairs (expensive part)
t0 = time.time()
pair_data = {}
for pair in PAIRS:
    df = store.load_candles(pair, limit=5000)
    if df is None or len(df) < 500: continue
    df = Indicators.compute(df).tail(2000).reset_index(drop=True)
    # Precompute signal scores
    scores = []
    phantom_penalties = []
    for i in range(len(df)):
        window = df.iloc[:i+1]
        pp = phantom.analyze(window)["phantom_score"]
        phantom_penalties.append(pp)
        scores.append(Indicators.signal_score(df.iloc[i], phantom_penalty=pp))
    pair_data[pair] = {"df": df, "scores": scores, "phantom": phantom_penalties}
print(f"Data prepped: {time.time()-t0:.1f}s", flush=True)

def backtest(cfg, pair):
    d = pair_data[pair]
    df = d["df"]
    scores = d["scores"]
    balance = BALANCE
    trades = []
    equity = [balance]
    sl_floor = cfg.stop_loss_min_pct
    hard_sl = cfg.hard_stop_loss_pct
    rr = cfg.take_profit_rr
    trail_pnl = cfg.trailing_stop_min_pnl
    atr_mult = cfg.stop_loss_atr_mult
    trail_mult = cfg.atr_trailing_mult
    thresh = cfg.signal_threshold
    risk_pct = cfg.risk_per_trade_pct
    min_not = cfg.min_notional_idr
    max_ord = cfg.max_order_idr

    for i in range(100, len(df)):
        row = df.iloc[i]
        sig = scores[i]["total"]
        close = row["close"]
        atr_v = row.get("atr_14")
        atr_val = atr_v if pd.notna(atr_v) and atr_v > 0 else None
        open_t = [t for t in trades if t["status"] == "open"]
        if not open_t:
            if sig >= thresh:
                if atr_val:
                    stop_d = max((atr_val * atr_mult) / close, sl_floor)
                    sz = (balance * risk_pct) / stop_d
                else:
                    sz = balance * risk_pct / sl_floor
                sz = max(min_not, min(sz, max_ord))
                if atr_val:
                    sl = close - atr_val * atr_mult
                    sl = min(max(sl, close * (1 - hard_sl)), close * (1 - sl_floor))
                    tp = close + (close - sl) * rr
                else:
                    sl = close * (1 - hard_sl)
                    tp = close + (close - sl) * rr
                trades.append({"entry_price": close, "size_idr": sz, "stop_loss": sl, "take_profit": tp, "status": "open", "pnl_pct": 0})
                balance -= sz
        else:
            t = open_t[0]
            hi, lo = row["high"], row["low"]
            e = t["entry_price"]
            if lo <= t["stop_loss"]:
                p = t["stop_loss"] / e - 1
                t["pnl_pct"] = p; t["status"] = "closed"
                balance += t["size_idr"] * (1 + p)
            elif hi >= t["take_profit"]:
                p = t["take_profit"] / e - 1
                t["pnl_pct"] = p; t["status"] = "closed"
                balance += t["size_idr"] * (1 + p)
            elif atr_val and atr_val > 0:
                pnl_pct = close / e - 1
                if pnl_pct >= trail_pnl and (close - atr_val * trail_mult) < e:
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
        ddd = (peak - v) / peak if peak > 0 else 0
        if ddd > dd: dd = ddd
    return wins, losses, pnl, pf, dd

# Run all configs
results = []
for name, rr, slf, trail, atrm, thresh in CANDIDATES:
    t0 = time.time()
    cfg = BotConfig(take_profit_rr=rr, stop_loss_min_pct=slf, trailing_stop_min_pnl=trail, stop_loss_atr_mult=atrm, signal_threshold=thresh)
    tw=tl=tpnl=0; dds=[]
    pfs=[]
    for pair in PAIRS:
        w,l,pnl,pf,dd = backtest(cfg, pair)
        tw+=w; tl+=l; tpnl+=pnl; dds.append(dd); pfs.append(pf)
    pf = np.mean([p for p in pfs if p!=float("inf")]) if any(p!=float("inf") for p in pfs) else 0
    t = tw+tl
    results.append((name, rr, slf, trail, atrm, thresh, pf, tw/t if t else 0, tw, tl, tpnl, np.mean(dds), time.time()-t0))

# Print results sorted by PF
results.sort(key=lambda x: x[6], reverse=True)
print(f"\n{'Config':>12s}  {'RR':>4s} {'Floor':>6s} {'Trail':>6s} {'ATRx':>5s} {'Thrsh':>6s}  {'PF':>6s} {'WR':>5s} {'W/L':>7s} {'P&L':>10s} {'DD':>5s}  {'Time':>5s}")
print("="*95)
for r in results:
    pf_s = f"{r[6]:.2f}" if r[6]!=float('inf') else "INF"
    print(f"{r[0]:>12s}  {r[1]:>4.1f} {r[2]:>6.0%} {r[3]:>6.0%} {r[4]:>5.1f} {r[5]:>6.2f}  {pf_s:>6s} {r[7]:>5.1%} {r[8]:>2.0f}W/{r[9]:<2.0f}L {r[10]:>10,.0f} {r[11]:>5.1%}  {r[12]:>5.1f}s")
