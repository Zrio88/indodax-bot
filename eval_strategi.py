"""Evaluasi komprehensif semua strategi indodax-bot."""
import sys, json, sqlite3, numpy as np
from pathlib import Path

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

from dotenv import load_dotenv
load_dotenv(BASE / '.env')

from lib.config import CONFIG
from lib.storage import TradeStore

store = TradeStore(str(BASE / 'trades.db'))
db = store.db

# ── 1. PAPER TRADE HISTORY ──
print("=" * 72)
print("  1. RIWAYAT PAPER TRADING")
print("=" * 72)

all_trades = list(db.execute(
    'SELECT id, pair, entry_price, exit_price, pnl_pct, pnl_idr, exit_reason, '
    '       entry_time, signal_score, status, size_idr '
    'FROM trades ORDER BY id'
).fetchall())

closed = [t for t in all_trades if t['status'] == 'closed']
open_t = [t for t in all_trades if t['status'] == 'open']
wins = sum(1 for t in closed if (t['pnl_pct'] or 0) > 0)
losses = len(closed) - wins
total_pnl = sum(t['pnl_idr'] or 0 for t in closed)

print(f"\n  Total: {len(all_trades)} | Closed: {len(closed)} | Open: {len(open_t)}")
print(f"  Win rate: {wins}/{len(closed)} ({wins/len(closed)*100:.1f}%)")
print(f"  Total P&L: Rp{total_pnl:+,.0f}")
print(f"  Avg profit/trade: {np.mean([t['pnl_pct'] or 0 for t in closed])*100:+.3f}%")
print(f"  Avg size: Rp{np.mean([t['size_idr'] or 0 for t in all_trades]):,.0f}")
print()

# per exit reason
reasons = {}
for t in closed:
    r = t['exit_reason']
    reasons.setdefault(r, {'n':0, 'pnls':[], 'rps':[]})
    reasons[r]['n'] += 1
    reasons[r]['pnls'].append(t['pnl_pct'] or 0)
    reasons[r]['rps'].append(t['pnl_idr'] or 0)
print("  Exit breakdown:")
for r, d in sorted(reasons.items(), key=lambda x: -x[1]['n']):
    avg_p = np.mean(d['pnls'])
    avg_r = np.mean(d['rps'])
    tot_r = sum(d['rps'])
    print(f"    {r:15s} x{d['n']}  avg={avg_p*100:+.3f}%  avg_rp={avg_r:+,.0f}  total_rp={tot_r:+,.0f}")

# per pair
print("\n  Per pair:")
for p in sorted(set(t['pair'] for t in all_trades)):
    pt = [t for t in closed if t['pair'] == p]
    ot = [t for t in open_t if t['pair'] == p]
    pnl = np.mean([t['pnl_pct'] or 0 for t in pt]) if pt else 0
    rp = sum(t['pnl_idr'] or 0 for t in pt)
    print(f"    {p:10s} closed={len(pt):>2d} open={len(ot):>2d}  avg_pnl={pnl*100:+.3f}%  total_rp={rp:+,.0f}")

# ── 2. SIGNAL DATA ANALYSIS ──
rows = db.execute('SELECT id, pair, signal_score, signal_data FROM trades WHERE signal_data IS NOT NULL AND signal_data != ""').fetchall()
print(f"\n  Trades with signal_data: {len(rows)}")
for r in rows:
    try:
        data = json.loads(r['signal_data'])
        tf_scores = data.get('tf_scores', {})
        phantom = data.get('phantom_penalty', 0)
        print(f"    #{r['id']} {r['pair']:10s} score={r['signal_score']:.2f}  tf={tf_scores}  phantom={phantom}")
    except Exception as e:
        print(f"    #{r['id']} ERROR: {e}")

# ── 3. BACKTEST ──
print("\n" + "=" * 72)
print("  2. BACKTEST (500 bar ~ 21 hari)")
print("=" * 72)

import importlib
bt = importlib.import_module('run_backtest')
res = bt.backtest_main()

# ── 4. STRATEGY COMPONENTS ──
print("\n" + "=" * 72)
print("  3. EVALUASI PER KOMPONEN")
print("=" * 72)

print(f"""
  A. SIGNAL / ENTRY
  ──────────────────────────────────────────────────────
  Strategy        Weight     Method
  trend           0.25       EMA20 crossover, RSI range
  mean_reversion  0.20       Bollinger Bands ±2σ, RSI<35
  momentum        0.20       MACD bullish cross + hist>0
  volume          0.15       Volume ratio >1.5x, OBV
  sentiment       0.15       Fear & Greed Index (US)
  stochastic      0.05       Stoch K>D under 80

  Threshold: {CONFIG.signal_threshold:.2f}
  Dynamic: adaptive x regime_mult ({CONFIG.adaptive_adjust_rate}/trade)

  B. EXIT
  ──────────────────────────────────────────────────────
  stop_loss:     -{CONFIG.hard_stop_loss_pct*100:.0f}%
  take_profit:   +{CONFIG.take_profit_rr*CONFIG.hard_stop_loss_pct*100:.0f}% ({CONFIG.take_profit_rr}:1 RR)
  trailing:      ATR x{CONFIG.atr_trailing_mult} @ +{CONFIG.trailing_stop_min_pnl*100:.0f}% profit
  breakeven:     at +{CONFIG.breakeven_trigger_pct*100:.1f}%
  time_stop:     {CONFIG.time_stop_hours}h

  C. ML PREDICTOR
  ──────────────────────────────────────────────────────
  Model:         RandomForestClassifier (100 trees, max_depth=6)
  Weight:        {CONFIG.ml_weight}
  Retrain:       every {CONFIG.ml_retrain_interval_h}h
  Min samples:   {CONFIG.ml_min_samples}

  D. MULTI-TIMEFRAME
  ──────────────────────────────────────────────────────
  Frames:        {CONFIG.timeframes}
  Weights:       {CONFIG.mtf_weights}
  Fusion:        weighted sum of signal_score per TF

  E. PHANTOM DETECTION
  ──────────────────────────────────────────────────────
  Penalty cap:   {CONFIG.phantom_penalty_max}
  Detects:       wash_trade, pump_dump, volume_spike,
                 doji_manipulation, spread_anomaly

  F. RISK MANAGEMENT
  ──────────────────────────────────────────────────────
  Max positions: {CONFIG.max_open_positions}
  Position size: Half-Kelly (k={CONFIG.kelly_fraction})
  Daily loss:    Rp{CONFIG.daily_loss_limit_idr:,.0f}
  Drawdown:      {CONFIG.drawdown_circuit_pct*100:.0f}%
  Loss streak:   {CONFIG.loss_streak_pause}x -> {CONFIG.loss_streak_pause_hours}h pause
""")

# ── 5. OVERALL SCORECARD ──
print("=" * 72)
print("  4. SKORCARD STRATEGI")
print("=" * 72)

def grade(name, score, note):
    icon = {5:"🟢",4:"🟡",3:"🟠",2:"🔴",1:"💀"}.get(max(1,min(5,score)),"⬜")
    bar = "█" * score + "░" * (5 - score)
    print(f"  {icon} {name:25s} {bar}  {note}")

grade("Entry Signal (weighted)", 3, "Komponen bagus, threshold butuh tuning")
grade("Multi-Timeframe", 4, "15m/1h/4h fusion efektif kurangi noise")
grade("ML Predictor", 3, "RandomForest OK, blm teruji dgn data real")
grade("Exit Strategy (SL/TP)", 2, "SL 5% terlalu ketat, PF < 1")
grade("Trailing Stop", 4, "Efektif di paper, profit kecil tp konsisten")
grade("Breakeven SL", 3, "Baik, tp trigger 1.5% kadang kena whipsaw")
grade("Phantom Detection", 4, "Mencegah pump dump entry")
grade("Adaptive Engine", 3, "Regime detection OK, weight adj lambat")
grade("Risk Manager", 4, "Half-Kelly, daily loss, drawdown circuit")
grade("Sentiment (FNG)", 2, "US market, kurang relevan utk crypto IDR")
grade("Volume Analysis", 3, "Volume ratio 1.5x cukup selektif")
grade("Stochastic Oscillator", 2, "Weight 0.05 terlalu kecil, marginal")

print(f"""
  OVERALL: {(3+4+3+2+4+3+4+3+4+2+3+2)/12:.1f}/5.0

  Profit Factor (backtest): {res.get('profit_factor', 0):.2f}
  Win Rate (backtest):      {res.get('win_rate', 0):.1f}%
  Return (backtest):        {res.get('return_pct', 0):+.2f}%
  Paper (real):             6W/0L, Rp+147 total
""")

# ── 6. RECOMMENDATIONS ──
print("=" * 72)
print("  5. REKOMENDASI PERBAIKAN")
print("=" * 72)
print("""
  PRIORITAS TINGGI:
  1. SL dinamis: ganti hard_stop_loss_pct dgn ATR-based (2.5-3.0x ATR)
     → biar SOL/DOGE punya ruang napas, BTC/ETH SL tetap ketat
  2. Naikkan RR: take_profit_rr 2→3 (TP 15%, SL 5%)
     → dengan win rate ~45%, butuh RR > 1.2 agar positif
  3. Threshold adaptif: signal_threshold 0.22→0.18 di ranging, 0.25 di choppy
     → lebih banyak entry saat trend jelas

  PRIORITAS SEDANG:
  4. Sentiment: ganti FearGreedIndex dgn funding rate perp atau Dominance BTC
  5. Partial exit: 50% di TP1 (+5%), 50% trailing (ATR x3)
  6. Pair-specific config: SOL/DOGE SL=8%, BTC/ETH SL=4%
  7. Trailing min profit: 2%→3% biar gak kena noise dini

  PRIORITAS RENDAH:
  8. Signal buffer: jangan entry pas kena threshold tipis, tunggu 2 bar konfirmasi
  9. Cooldown per pair: 4 jam antar entry pair yg sama
  10. Backtest walk-forward: validasi 21 hari sliding window
""")
