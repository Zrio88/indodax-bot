"""Investigate why bot is unprofitable — signal quality analysis."""
import sys; sys.path.insert(0, "/home/get/projects/indodax-bot")
from dotenv import load_dotenv; load_dotenv()
import numpy as np, pandas as pd
from lib.storage import TradeStore
from lib.indicators import Indicators
from lib.phantom import PhantomDetector

store = TradeStore()
PAIRS = ["BTC/IDR", "ETH/IDR", "SOL/IDR"]
phantom = PhantomDetector()

for pair in PAIRS:
    df = store.load_candles(pair, limit=5000)
    if df is None or len(df) < 500: continue
    df = Indicators.compute(df).tail(2000).reset_index(drop=True)

    df["next_ret"] = df["close"].shift(-1) / df["close"] - 1
    df["next_5ret"] = df["close"].shift(-5) / df["close"] - 1
    df["next_24ret"] = df["close"].shift(-24) / df["close"] - 1

    scores = []
    for i in range(len(df)):
        pp = phantom.analyze(df.iloc[:i+1])["phantom_score"]
        scores.append(Indicators.signal_score(df.iloc[i], phantom_penalty=pp))

    df["sig"] = [s["total"] for s in scores]
    comps = [s["components"] for s in scores]
    df["trend_comp"] = [c.get("trend",0) for c in comps]
    df["mom_comp"] = [c.get("momentum",0) for c in comps]
    df["vol_comp"] = [c.get("volume",0) for c in comps]
    df["sent_comp"] = [c.get("sentiment",0) for c in comps]

    print(f"\n{'='*70}")
    print(f"  {pair}")
    print(f"{'='*70}")
    print(f"  Period: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
    print(f"  Bars: {len(df)}")
    print(f"  Close range: {df['close'].min():,.0f} - {df['close'].max():,.0f}")

    start_c = df["close"].iloc[0]; end_c = df["close"].iloc[-1]
    print(f"  Buy & hold return: {(end_c/start_c-1)*100:.1f}%")
    print(f"  Avg 1h return: {df['next_ret'].mean()*100:.3f}%")
    vol = df['next_ret'].std()*100
    print(f"  Volatility (1h): {vol:.2f}%")

    print(f"\n  -- SIGNAL STATS --")
    print(f"  Signal range: {df['sig'].min():.2f} to {df['sig'].max():.2f}")
    print(f"  Signal mean: {df['sig'].mean():.3f}, median: {df['sig'].median():.3f}")
    for thresh in [0.12, 0.15, 0.18, 0.20, 0.22]:
        hits = (df["sig"] >= thresh).sum()
        above = df[df["sig"] >= thresh]
        if len(above) > 0:
            pos = (above["next_5ret"] > 0.005).sum()
            neg = (above["next_5ret"] < -0.005).sum()
            wr = pos/(pos+neg)*100 if (pos+neg) > 0 else 0
            avg_ret = above["next_5ret"].mean()*100
            print(f"  thresh={thresh:.2f}: {hits:>4d} hits ({hits/len(df)*100:.1f}%), "
                  f"5h WR={wr:.0f}%, avg_ret={avg_ret:.2f}%")

    # Component breakdown
    print(f"\n  -- COMPONENTS at sig>=0.18 --")
    df_s = df[df["sig"] >= 0.18]
    if len(df_s) > 0:
        for col in ["trend_comp", "mom_comp", "vol_comp", "sent_comp"]:
            print(f"  {col}: mean={df_s[col].mean():.3f}")

    # Simple strategies
    print(f"\n  -- SIMPLE STRATEGIES --")
    # MA crossover
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma50"] = df["close"].rolling(50).mean()
    df["ma_pos"] = df["ma20"] > df["ma50"]
    correct = ((df["ma_pos"].shift(1)) == (df["next_5ret"] > 0)).sum()
    total = (df["ma_pos"].shift(1).notna()).sum()
    print(f"  MA20>MA50 direction accuracy (5h): {correct/total*100:.1f}%")

    # RSI oversold
    df["rsi"] = df["rsi_14"]
    rsi_low = df[df["rsi"] < 30]
    if len(rsi_low) > 0:
        pos = (rsi_low["next_5ret"] > 0.005).sum()
        neg = (rsi_low["next_5ret"] < -0.005).sum()
        wr = pos/(pos+neg)*100 if (pos+neg) > 0 else 0
        print(f"  RSI<30 oversold: {len(rsi_low)} signals, 5h WR={wr:.0f}%")

    # Trend strength
    df["adx25"] = df["adx"] > 25
    strong = df[df["adx25"]]
    if len(strong) > 0:
        pos = (strong["next_5ret"] > 0.005).sum()
        neg = (strong["next_5ret"] < -0.005).sum()
        wr = pos/(pos+neg)*100 if (pos+neg) > 0 else 0
        print(f"  ADX>25 trend: {len(strong)} bars, 5h WR={wr:.0f}%")
        # Directional accuracy when ADX high
        pos_d = strong[strong["dmp"] > strong["dmn"]]
        if len(pos_d) > 0:
            p = (pos_d["next_5ret"] > 0.005).sum()
            n = (pos_d["next_5ret"] < -0.005).sum()
            print(f"    +DI> -DI: {len(pos_d)} bars, 5h WR={p/(p+n)*100:.0f}%")

    # Check if market is at a crucial level
    print(f"\n  -- RANDOM BASELINE --")
    n_test = len(df) - 100
    rand = np.random.choice([-1,1], n_test)
    rand_acc = (rand * df["next_5ret"].iloc[100:].values > 0).mean()
    print(f"  Random 5h direction accuracy: {rand_acc*100:.1f}%")

    # Always-long baseline
    long_ret = df["next_5ret"].iloc[100:].mean() * 100
    print(f"  Always-long 5h avg return: {long_ret:.2f}%")

    # Anti-correlation check: does our signal predict the OPPOSITE?
    print(f"\n  -- SIGNAL PREDICTIVE POWER --")
    sig_corr = df["sig"].corr(df["next_5ret"])
    print(f"  Signal vs 5h return correlation: {sig_corr:.3f}")
    # If signal is high, what happens?
    for q in [0.75, 0.80, 0.85, 0.90]:
        qv = df["sig"].quantile(q)
        top = df[df["sig"] >= qv]
        avg_top = top["next_5ret"].mean()*100
        avg_rest = df[df["sig"] < qv]["next_5ret"].mean()*100
        print(f"  Top {1-q:.0%} sig (>{qv:.2f}): avg 5h ret={avg_top:.2f}% vs rest={avg_rest:.2f}%")
