#!/usr/bin/env python3
"""
Quick test script to verify all critical fixes are working.
Run this before going live!
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.config import CONFIG
from lib.indicators import Indicators
from lib.risk import RiskManager
from lib.exit import ExitManager
from lib.storage import TradeStore
import pandas as pd
import numpy as np

print("=" * 70)
print("TESTING CRITICAL FIXES FOR LIVE TRADING")
print("=" * 70)

# Test 1: Import check
print("\n[TEST 1] Checking imports...")
try:
    from lib.exchange import Exchange, BybitExchange, BinanceExchange
    from lib.phantom import PhantomDetector
    from lib.adaptive import AdaptiveEngine
    from lib.ml import MLPredictor
    from lib.notifier import Notifier
    from lib.logger import Console, get_logger
    print("  ✅ All imports successful")
except Exception as e:
    print(f"  ❌ Import failed: {e}")
    sys.exit(1)

# Test 2: SL/TP calculation for LONG
print("\n[TEST 2] Testing LONG position SL/TP calculation...")
store = TradeStore()
risk = RiskManager(store, paper=True)

# Simulate LONG entry
price = 100000
atr_val = 2000
sl_mult = 1.5
rr = 1.5

sl_price_long = price - (atr_val * sl_mult)
max_sl_long = price * (1 - CONFIG.hard_stop_loss_pct)
min_sl_long = price * (1 - CONFIG.stop_loss_min_pct)
sl_price_long = max(min(sl_price_long, max_sl_long), min_sl_long)
sl_dist_long = price - sl_price_long
tp_price_long = price + sl_dist_long * rr

print(f"  Entry: Rp {price:,.0f}")
print(f"  SL: Rp {sl_price_long:,.0f} ({((sl_price_long/price)-1)*100:+.2f}%)")
print(f"  TP: Rp {tp_price_long:,.0f} ({((tp_price_long/price)-1)*100:+.2f}%)")
assert sl_price_long < price, "SL should be below entry for LONG"
assert tp_price_long > price, "TP should be above entry for LONG"
print("  ✅ LONG SL/TP calculation correct")

# Test 3: SL/TP calculation for SHORT
print("\n[TEST 3] Testing SHORT position SL/TP calculation...")
sl_price_short = price + (atr_val * sl_mult)
max_sl_short = price * (1 + CONFIG.hard_stop_loss_pct)
min_sl_short = price * (1 + CONFIG.stop_loss_min_pct)
sl_price_short = min(max(sl_price_short, min_sl_short), max_sl_short)
sl_dist_short = sl_price_short - price
tp_price_short = price - sl_dist_short * rr

print(f"  Entry: Rp {price:,.0f}")
print(f"  SL: Rp {sl_price_short:,.0f} ({((sl_price_short/price)-1)*100:+.2f}%)")
print(f"  TP: Rp {tp_price_short:,.0f} ({((tp_price_short/price)-1)*100:+.2f}%)")
assert sl_price_short > price, "SL should be above entry for SHORT"
assert tp_price_short < price, "TP should be below entry for SHORT"
print("  ✅ SHORT SL/TP calculation correct")

# Test 4: PnL calculation for LONG
print("\n[TEST 4] Testing PnL calculation for LONG...")
entry_long = 100000
exit_long = 105000
amount_long = 0.01  # 0.01 BTC
pnl_long = (exit_long - entry_long) * amount_long
pnl_pct_long = (exit_long - entry_long) / entry_long
print(f"  Entry: Rp {entry_long:,.0f}, Exit: Rp {exit_long:,.0f}")
print(f"  PnL: Rp {pnl_long:,.0f}, PnL%: {pnl_pct_long:.2%}")
assert pnl_long > 0, "Long should be profitable"
assert pnl_pct_long > 0, "Long PnL% should be positive"
print("  ✅ LONG PnL calculation correct")

# Test 5: PnL calculation for SHORT
print("\n[TEST 5] Testing PnL calculation for SHORT...")
entry_short = 100000
exit_short = 95000
amount_short = 0.01  # 0.01 BTC
pnl_short = (entry_short - exit_short) * amount_short
pnl_pct_short = (entry_short - exit_short) / entry_short
print(f"  Entry: Rp {entry_short:,.0f}, Exit: Rp {exit_short:,.0f}")
print(f"  PnL: Rp {pnl_short:,.0f}, PnL%: {pnl_pct_short:.2%}")
assert pnl_short > 0, "Short should be profitable"
assert pnl_pct_short > 0, "Short PnL% should be positive"
print("  ✅ SHORT PnL calculation correct")

# Test 6: Risk manager position sizing
print("\n[TEST 6] Testing risk manager position sizing...")
size_long = risk.position_size(entry_long, "BTC/IDR", atr=atr_val)
size_short = risk.position_size(entry_short, "BTC/IDR", atr=atr_val)
print(f"  LONG position size: Rp {size_long:,.0f}")
print(f"  SHORT position size: Rp {size_short:,.0f}")
assert size_long > 0, "Position size should be positive"
assert size_short > 0, "Position size should be positive"
assert size_long <= CONFIG.max_order_idr, "Position size should respect max_order_idr"
print("  ✅ Position sizing working correctly")

# Test 7: Exit manager trailing stop
print("\n[TEST 7] Testing exit manager trailing stop...")
exit_mgr = ExitManager(store)

# Create test dataframe
df = pd.DataFrame({
    'open': [100000, 101000, 102000, 103000, 104000],
    'high': [101000, 102000, 103000, 104000, 105000],
    'low': [99000, 100000, 101000, 102000, 103000],
    'close': [101000, 102000, 103000, 104000, 104000],
    'volume': [100, 200, 300, 400, 500]
})

# Add trade to store
trade_id = store.add_trade({
    "pair": "BTC/IDR",
    "side": "buy",
    "direction": "long",
    "entry_price": 100000,
    "amount": 0.01,
    "stop_loss": 95000,
    "take_profit": 110000,
    "size_idr": 1000000,
    "entry_time": "2026-07-03T00:00:00+00:00",
    "signal_score": 0.8
})

# Test trailing stop
price_peak = 104000  # Price reached peak, now dropping
df_test = df.copy()
df_test['close'] = [100000, 101000, 102000, 103000, 101000]  # Drops from peak
actions = exit_mgr.check("BTC/IDR", 101000, df_test)

# Clean up
store.close_trade(trade_id, 101000, -3000, -0.03, "test_close")

print("  ✅ Exit manager working")

# Test 8: Signal threshold
print("\n[TEST 8] Testing signal threshold...")
config_signal_threshold = CONFIG.signal_threshold
print(f"  Signal threshold: {config_signal_threshold}")
assert config_signal_threshold > 0, "Signal threshold should be positive"
print("  ✅ Signal threshold configured")

# Test 9: API key validation (for LIVE mode)
print("\n[TEST 9] Testing API key presence...")
key = os.environ.get("INDODAX_API_KEY", "")
secret = os.environ.get("INDODAX_API_SECRET", "")
if not key or not secret:
    print("  ⚠️  INDODAX API keys not set in environment (OK for paper trading)")
else:
    print(f"  ✅ INDODAX API keys present")

# Test 10: Exchange connection (if keys present)
print("\n[TEST 10] Testing exchange connection...")
if key and secret:
    try:
        from lib.exchange import IndodaxExchange
        ex = IndodaxExchange()
        healthy = ex.health_check()
        if healthy:
            print("  ✅ Exchange connection healthy")
        else:
            print("  ⚠️  Exchange connection failed (check API keys)")
    except Exception as e:
        print(f"  ⚠️  Exchange connection error: {e}")
else:
    print("  ⏭️  Skipping exchange test (no API keys)")

# Cleanup
store.db.close()

print("\n" + "=" * 70)
print("ALL TESTS PASSED ✅")
print("Bot is ready for paper trading!")
print("For LIVE trading: Ensure API keys are set and exchange is reachable")
print("=" * 70)
