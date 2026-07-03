"""Debug signal scores across historical data."""
import sys; sys.path.insert(0, "/home/get/projects/indodax-bot")
from dotenv import load_dotenv; load_dotenv()

import numpy as np
from lib.storage import TradeStore
from lib.indicators import Indicators
from lib.phantom import PhantomDetector
from lib.config import CONFIG

store = TradeStore()

for pair in ["BTC/IDR", "ETH/IDR", "SOL/IDR"]:
    df = store.load_candles(pair)
    if df is None or len(df) < 100:
        continue
    df = Indicators.compute(df)
    scores = []
    for i in range(100, len(df)):
        window = df.iloc[:i+1]
        row = df.iloc[i]
        penalty = PhantomDetector.analyze(window)["phantom_score"]
        sig = Indicators.signal_score(row, phantom_penalty=penalty)
        scores.append(sig["total"])

    arr = np.array(scores)
    above = sum(1 for s in scores if s >= CONFIG.signal_threshold)
    max_sig = max(scores)
    print(f"\n{pair}:")
    print(f"  Threshold: {CONFIG.signal_threshold}")
    print(f"  Samples:   {len(scores)}")
    print(f"  Above thresh: {above}")
    print(f"  Max sig:   {max_sig:.3f}")
    print(f"  Top 5:     {sorted(scores, reverse=True)[:5]}")
    print(f"  Mean:      {arr.mean():.3f}")
    print(f"  Median:    {np.median(arr):.3f}")
    print(f"  Std:       {arr.std():.3f}")
    print(f"  Min:       {arr.min():.3f}")
