"""Debug signal components to understand capped scores."""
import sys; sys.path.insert(0, "/home/get/projects/indodax-bot")
from dotenv import load_dotenv; load_dotenv()
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

    # Best signal bar
    best_i, best_sig = 100, 0
    for i in range(100, len(df)):
        window = df.iloc[:i+1]
        row = df.iloc[i]
        penalty = PhantomDetector.analyze(window)["phantom_score"]
        sig = Indicators.signal_score(row, phantom_penalty=penalty)
        if sig["total"] > best_sig:
            best_sig = sig["total"]
            best_i = i

    row = df.iloc[best_i]
    sig = Indicators.signal_score(row)
    w = CONFIG.signal_weights

    print(f"\n{pair} — best signal @ bar {best_i}:")
    print(f"  Total: {sig['total']:.3f} (raw: {sig['raw']:.3f})")
    print(f"  Phantom penalty: {sig.get('phantom_penalty', 0):.3f}")
    for k, v in sig["components"].items():
        contrib = v * w.get(k, 0)
        print(f"  {k:>15s}: {v:.3f} × w={w.get(k,0):.2f} = {contrib:.3f}")
    print(f"  Details: {sig['details']}")

    # Show current market state
    print(f"  Close: Rp{row['close']:,.0f}")
    if pd.notna(row.get("rsi_14")):
        print(f"  RSI(14): {row['rsi_14']:.1f}")
    if pd.notna(row.get("adx")):
        print(f"  ADX: {row['adx']:.1f}")
    if pd.notna(row.get("macd_hist")):
        print(f"  MACD hist: {row['macd_hist']:.0f}")
    if pd.notna(row.get("volume_ratio")):
        print(f"  Vol ratio: {row['volume_ratio']:.2f}")
    if pd.notna(row.get("stoch_k")):
        print(f"  Stoch K: {row['stoch_k']:.1f}  D: {row['stoch_d']:.1f}")
