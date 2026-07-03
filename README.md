# Indodax Trading Bot 🤖

Bot trading kripto otomatis untuk Indodax dengan **multi-strategy confluence scoring**, **half-Kelly position sizing**, **15 lapis risk management**, **phantom/anomaly detection**, **adaptive engine**, dan **8 fitur production-critical** — semuanya dalam satu paket Python modular.

> **Status:** Paper trading已验证 (live-ready) | Balance awal: Rp500.000 | Pair: BTC/ETH/SOL/XRP/DOGE

---

## Daftar Isi

- [Arsitektur](#arsitektur)
- [Struktur Proyek](#struktur-proyek)
- [Modul `lib/`](#modul-lib)
- [Konfigurasi](#konfigurasi)
- [Scoring Engine](#scoring-engine)
- [Risk Management (15 Lapis)](#risk-management-15-lapis)
- [Exit Strategy](#exit-strategy)
- [Phantom Detector](#phantom-detector)
- [Adaptive Engine](#adaptive-engine)
- [Production Features](#production-features)
- [Cara Pakai](#cara-pakai)
- [Research & Referensi](#research--referensi)

---

## Arsitektur

```
┌──────────────────────────────────────────────────────────────────┐
│                        Bot.run()                                 │
│     ┌──────────┐    ┌──────────┐    ┌──────────┐                │
│     │ Cycle #1 │    │ Cycle #2 │    │ Cycle #3 │  ...           │
│     └────┬─────┘    └────┬─────┘    └────┬─────┘                │
│          │               │               │                       │
│          ▼               ▼               ▼                       │
│    ┌─────────────────────────────────────────────────┐          │
│    │               Bot.cycle()                        │          │
│    │                                                  │          │
│    │  ┌───────────── 1️⃣ EXIT CHECK ─────────────┐    │          │
│    │  │  ∀ pair: fetch OHLCV → Indicators →     │    │          │
│    │  │  ExitManager.check()                    │    │          │
│    │  │    → TP / SL / Trailing / Breakeven     │    │          │
│    │  │    → Close → feed ke AdaptiveEngine     │    │          │
│    │  └──────────────────────────────────────────┘    │          │
│    │                                                  │          │
│    │  ┌───────────── 2️⃣ RISK CHECK ─────────────┐    │          │
│    │  │  RiskManager.can_trade()                  │    │          │
│    │  │    → Cooldown / Drawdown / Daily Limit   │    │          │
│    │  │    → Loss Streak / Max Positions /       │    │          │
│    │  │      Balance Check                       │    │          │
│    │  └──────────────────────────────────────────┘    │          │
│    │                                                  │          │
│    │  ┌───────────── 3️⃣ ENTRY SCAN ─────────────┐    │          │
│    │  │  ∀ pair: fetch OHLCV → Indicators →      │    │          │
│    │  │  Regime Detection → Phantom Check →      │    │          │
│    │  │  signal_score() ≥ dynamic_threshold?     │    │          │
│    │  │    → position_size() → DB / Exchange     │    │          │
│    │  └──────────────────────────────────────────┘    │          │
│    └─────────────────────────────────────────────────┘          │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │        Background Tasks (per cycle)                     │    │
│  │  • Heartbeat check (setiap N menit)                     │    │
│  │  • Daily report (setiap pergantian hari UTC)            │    │
│  │  • Kill switch monitor (cek .kill file tiap detik)      │    │
│  │  • Signal handler (SIGINT/SIGTERM → graceful shutdown)  │    │
│  └─────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Struktur Proyek

```
indodax-bot/
├── bot.py              # Main entry point — loop + orchestration
├── lib/
│   ├── __init__.py
│   ├── config.py       # Pydantic Config — validasi + type safety
│   ├── logger.py       # StructuredLogger (JSONL) + Console (human)
│   ├── exchange.py     # CCXT exchange — retry + idempotency
│   ├── storage.py      # SQLite WAL — trades + daily_pnl + meta
│   ├── indicators.py   # pandas_ta — 13+ indikator + signal scoring
│   ├── sentiment.py    # Fear & Greed API — contrarian signal
│   ├── phantom.py      # 5 pola anomaly detection
│   ├── adaptive.py     # Regime detection + weight tuning
│   ├── risk.py         # Half-Kelly + 8 lapis risk
│   ├── exit.py         # 5 exit strategy
│   ├── notifier.py     # Telegram bot — entry/exit/alert/report
│   └── backtest.py     # Backtest engine — historical simulation
├── .env                # INDODAX_API_KEY + INDODAX_API_SECRET
├── .gitignore
├── trades.db           # SQLite — auto-created
├── logs/
│   ├── bot.jsonl       # Structured logs (INFO+)
│   └── error.jsonl     # Structured logs (WARN+)
├── .kill               # Emergency kill switch (touch to stop)
├── ARCHITECTURE.md     # Mermaid diagram
├── CLAUDE.md           # Agent context
├── paper_trade.sh      # Jalankan 1 siklus paper
├── start_paper.sh      # Tmux session (bot + monitor)
└── monitor.py          # Real-time portfolio dashboard
```

---

## Modul `lib/`

### `config.py` — Konfigurasi Tervalidasi

Semua parameter bot divalidasi dengan **Pydantic V2**:

```python
from lib.config import CONFIG

CONFIG.signal_threshold        # → 0.50
CONFIG.max_open_positions      # → 3
CONFIG.cycle_interval_s        # → 300
CONFIG.telegram_token          # → None (optional)
```

Validasi otomatis: pair format `XXX/YYY`, signal weights sum ≈ 1.0, bounds checking untuk semua numeric field.

### `logger.py` — Dual Logging

| Output | Format | Tujuan |
|---|---|---|
| `Console` | Human-readable, color-coded | Terminal |
| `StructuredLogger` | JSONL (NDJSON) | `logs/bot.jsonl` + `logs/error.jsonl` |

Contoh log JSONL:
```json
{"ts": "2026-07-02T21:39:34+00:00", "level": "INFO", "event": "heartbeat", "open_positions": 2, "total_pnl": 15000, "paper": true}
```

### `exchange.py` — CCXT Exchange Layer

| Fitur | Detail |
|---|---|
| **Retry** | Exponential backoff + jitter (3 attempts) untuk `NetworkError`, `ExchangeNotAvailable`, `RequestTimeout` |
| **Idempotency** | Setiap order punya `clientOrderId` unik (`bot_{session}_{uuid}`) |
| **Reconciliation** | `reconcile_positions()` → bandingkan open trades lokal vs exchange |
| **Health Check** | `health_check()` → test fetch ticker, return boolean |

**Decorator:**
```python
@retry(max_attempts=3, base_delay=1.0)
def fetch_ohlcv(self, pair, timeframe, limit):
    ...
```

### `storage.py` — SQLite WAL

| Feature | Benefit |
|---|---|
| **WAL mode** (`PRAGMA journal_mode=WAL`) | Concurrent reads + writes tanpa lock |
| **Busy timeout** (`PRAGMA busy_timeout=5000`) | Anti database-locked error |
| **Meta table** | Persistent state: last run, balance snapshot, dll |
| **Daily PnL** | `daily_pnl` table + `update_daily_pnl()` |
| **Rolling metrics** | Win rate, avg win/loss per pair (lookback N) |

### `notifier.py` — Telegram Singleton

Pattern: **Singleton** — hanya satu instance, diinisialisasi dari CONFIG.

| Method | Trigger |
|---|---|
| `startup()` | Bot mulai |
| `entry(pair, price, size, score)` | Entry baru |
| `exit(pair, price, reason, pnl_pct, pnl_idr)` | Exit trade |
| `alert(text)` | Error / warning |
| `daily_report(trades, balance, pnl, open)` | Pergantian hari UTC |
| `shutdown(reason)` | Bot berhenti |

Aman: jika `telegram_token` atau `telegram_chat_id` tidak di-set, semua method jadi no-op.

### `backtest.py` — Backtest Engine

Simulasi historis dengan scoring, entry, dan exit yang identik dengan live:

```bash
python -c "
from lib.backtest import BacktestEngine
# ... load OHLCV dataframes per pair ...
engine = BacktestEngine(indicators_compute, risk_mgr, exit_mgr, phantom, sentiment)
result = engine.run(ohlcv_data)
print(result)
"
```

Output:
```python
{
  "balance_final": 520000,
  "total_pnl": 20000,
  "return_pct": 0.04,
  "total_trades": 12,
  "wins": 7, "losses": 5,
  "win_rate": 0.583,
  "avg_win": 0.035, "avg_loss": 0.025,
  "profit_factor": 1.96,
  "open_positions": 0,
}
```

---

## Scoring Engine

6 sinyal dihitung dari indikator teknikal + sentimen, masing-masing dengan bobot:

```
TREND         25%  ─ EMA 20 (price > EMA = +0.15)
                  ─ RSI 14 (30-70 = +0.10)

MEAN REV      20%  ─ Bollinger Bands (touch lower = +0.15)
                  ─ RSI oversold (<35 = +0.05)

MOMENTUM      20%  ─ MACD (bullish crossover + hist >0 = +0.20)

VOLUME        15%  ─ Volume Ratio >1.5× = +0.10
                  ─ OBV valid = +0.05

SENTIMENT     15%  ─ Fear & Greed API (extreme fear = +1.0)
                  ─ contrarian: fear = buy, greed = sell

STOCHASTIC     5%  ─ %K > %D dan %K < 80 = +0.05
```

**Formula final:**
```
raw_score        = Σ(signal × weight) / Σ(weight)
phantom_penalty  = phantom_score × 0.5  (max 50% reduction)
adjusted_score   = raw_score × (1.0 - phantom_penalty)
threshold        = 0.50 × regime_mult
verdict          = "enter" if adjusted_score ≥ threshold else "hold"
```

---

## Risk Management (15 Lapis)

Bot ini punya **15 mekanisme risk** yang bekerja simultan:

| # | Risk Layer | Parameter | Trigger |
|---|---|---|---|
| 1 | **Half-Kelly Sizing** | `kelly_fraction: 0.5` | Position size = balance × Kelly × fraction |
| 2 | **Win Rate Adaptive** | `rolling_metrics(pair)` | Kelly ratio dari win rate rolling |
| 3 | **Drawdown Multiplier** | 5% / 10% / 15% threshold | Size dikali 1.0 / 0.75 / 0.50 / 0.25 |
| 4 | **Regime Sizing** | `regime_sizing_mult()` | Trending=0.9, Choppy=0.4, Volatile=0.5 |
| 5 | **Max Positions** | `max_open_positions: 3` | Tolak entry baru jika sudah 3 |
| 6 | **Max Order Size** | `max_order_idr: 50.000` | Tidak pernah entry > Rp50rb |
| 7 | **Min Notional** | `min_notional_idr: 10.000` | Tolak entry < Rp10rb |
| 8 | **Daily Loss Limit** | `daily_loss_limit_idr: 100.000` | Stop trading jika rugi > Rp100rb/hari |
| 9 | **Drawdown Circuit** | `drawdown_circuit_pct: 0.10` | Stop total jika drawdown > 10% |
| 10 | **Loss Streak Pause** | `loss_streak_pause: 3` | Jeda 2 jam setelah 3 rugi berturut-turut |
| 11 | **Global Cooldown** | `global_cooldown_min: 30` | Minimal 30 menit antar entry |
| 12 | **Hard Stop Loss** | `hard_stop_loss_pct: 0.05` | Cut loss otomatis di -5% |
| 13 | **Take Profit** | `take_profit_rr: 2.0` | Ambil untung di +10% (2× SL) |
| 14 | **ATR Trailing Stop** | `atr_trailing_mult: 2.0` | Trailing oleh ATR × 2 |
| 15 | **Phantom Penalty** | `phantom_penalty_max: 0.5` | Score dikurangi hingga 50% |

---

## Exit Strategy

5 mekanisme exit, diperiksa setiap cycle:

```
         P&L
          │
   +10% ──┤ TP ────────────────────→ CLOSE (take_profit)
          │
   +1.5% ─┤ Breakeven ──→ Update SL ke entry price
          │
     0% ──┤
          │
          │    ATR Trailing: jika price turun
          │    lebih dari 2× ATR dari entry → CLOSE
          │
   -5% ──┤ SL ─────────────────────→ CLOSE (stop_loss)
          │
          └─────────────────────────→ Time Stop ≥ 24 jam → CLOSE
```

---

## Phantom Detector

Mendeteksi 5 pola anomali yang mengindikasikan manipulasi pasar:

| Anomali | Deteksi | Severity |
|---|---|---|
| **Wash Trade** | Volume spike > 6×, price change < 1% | 0.8 |
| **Volume Spike No Move** | Volume spike > 3×, price change < 1.5% | 0.5 |
| **Pump & Dump** | Rise > 3% lalu fall < -2% dalam 10 candle | 0.7 |
| **Doji Manipulation** | Body/wick ratio < 8% | 0.3 |
| **Consecutive Bullish** | 9+ candle hijau berturut-turut | 0.3 |
| **Spread Anomaly** | Spread > 3× rata-rata | 0.4 |

Phantom `severity` dikonversi ke penalty multiplier:
```
adjusted_score = raw_score × (1.0 - severity × 0.5)
```

---

## Adaptive Engine

### Regime Detection (berbasis ADX)

| ADX | Regime | Threshold Mult | Sizing Mult | Perilaku |
|---|---|---|---|---|
| < 18 | `choppy` | 1.15× | 0.4× | Hampir tidak entry |
| 18-25 | `ranging` | 1.05× | 0.7× | Selektif |
| 25-35 | `trending` | 0.95× | 0.9× | Agresif |
| 35-50 | `strong_trend` | 0.85× | 1.0× | Paling agresif |
| > 50 + ATR > 3% | `volatile` | 1.10× | 0.5× | Hati-hati |

### Adaptive Weights

Per-signal win rate dilacak setelah setiap trade ditutup:

```
fitur    wins  losses  total  win_rate    efek
trend      7      3     10     0.70    → weight +2.5%
momentum   4      6     10     0.40    → weight -5%
```

Threshold untuk penyesuaian:
- WR < 40% → weight dikurangi 5%
- WR > 60% → weight ditambah 2.5%

Semua weights dinormalisasi agar tetap sum-to-1 setelah setiap update.

---

## Production Features

### 1. Retry with Exponential Backoff

Semua panggilan exchange dibungkus decorator `@retry`:

```
Attempt 1 → gagal → delay 1.0s + jitter
Attempt 2 → gagal → delay 2.0s + jitter
Attempt 3 → gagal → raise exception + log error
```

Hanya `NetworkError`, `ExchangeNotAvailable`, `RequestTimeout` yang di-retry. `BadSymbol`, `InsufficientFunds`, dan error lain langsung di-throw.

### 2. Idempotency

Setiap order punya `clientOrderId` unik:
```
bot_a1b2c3d4_e5f6a7b8c9d0e1f2
       ^session^  ^random UUID^
```

Jika order terkirim tapi timeout response → retry tidak akan membuat duplikat karena exchange lihat `clientOrderId` yang sama.

### 3. Graceful Shutdown (SIGINT/SIGTERM)

```
User Ctrl+C atau kill PID
        │
        ▼
  signal_handler() → set self._running = False
        │
        ▼
  Main loop berhenti dalam ≤1 detik
  (sleep loop granular 1s, bukan 300s)
        │
        ▼
  _shutdown() → cetak summary
              → notifikasi Telegram
              → log "shutdown"
              → warning jika ada open positions
```

### 4. Emergency Kill Switch

```bash
# Buat file .kill di direktori bot:
touch /home/get/projects/indodax-bot/.kill

# Bot akan berhenti dalam ≤1 detik dan kirim alert Telegram:
# "⚠️ Alert — Emergency kill switch triggered — bot stopping"
```

File `.kill` otomatis dihapus saat bot start.

### 5. Heartbeat

Setiap `heartbeat_interval_m` (default 60 menit):
- Log `heartbeat` ke JSONL (open positions, total PnL, mode)
- Cek `exchange.health_check()` → warning jika exchange unreachable
- Tidak mengganggu cycle normal

### 6. Daily Report

Otomatis terkirim saat pertama kali deteksi hari baru UTC:
- Balance, P&L, jumlah trade, win rate, avg win/loss
- Ke Telegram (jika dikonfigurasi) dan log JSONL

### 7. WAL Mode SQLite

```
PRAGMA journal_mode=WAL;       -- Concurrent read/write
PRAGMA busy_timeout=5000;      -- Anti locked error
```

### 8. Structured Logging

Dua file JSONL:
- `logs/bot.jsonl` — level INFO+
- `logs/error.jsonl` — level WARN+

Setiap event punya timestamp ISO 8601, level, dan context:
```json
{"ts": "2026-07-02T21:39:34+00:00", "level": "INFO", "event": "daily_report", "day": "2026-07-02", "balance": 515000, "pnl": 15000, "trades": 5}
```

### 9. Position Reconciliation

`Exchange.reconcile_positions(store)` → bandingkan open trades lokal dengan balance exchange:
- `missing_position`: exchange tidak punya coin tapi lokal menganggap open → warning
- `partial_fill`: jumlah coin di exchange < expected → warning

### 10. Backtest Engine

`BacktestEngine` menjalankan logika scoring + entry + exit yang persis sama dengan live mode di atas DataFrame historis. Output: balance final, total PnL, return %, win rate, profit factor.

---

## Konfigurasi

Semua parameter ada di `lib/config.py` (kelas `BotConfig` dengan Pydantic). Override via environment variable juga bisa:

```bash
export SIGNAL_THRESHOLD=0.60
python bot.py
```

### Parameter Utama

| Parameter | Default | Deskripsi |
|---|---|---|
| `signal_threshold` | 0.50 | Threshold entry (0-1) |
| `kelly_fraction` | 0.5 | Fraksi Kelly (0.01-1.0) |
| `max_open_positions` | 3 | Maksimal posisi bersamaan |
| `max_order_idr` | 50.000 | Maksimal IDR per entry |
| `hard_stop_loss_pct` | 0.05 | Stop loss 5% |
| `take_profit_rr` | 2.0 | Risk/reward ratio |
| `cycle_interval_s` | 300 | Interval antar cycle |
| `daily_loss_limit_idr` | 100.000 | Batas rugi harian |
| `drawdown_circuit_pct` | 0.10 | Drawdown circuit breaker |
| `paper_mode` | true | Paper/live toggle |

### Environment

| Variable | Required | Deskripsi |
|---|---|---|
| `INDODAX_API_KEY` | Ya | API key dari Indodax |
| `INDODAX_API_SECRET` | Ya | Secret key dari Indodax |

---

## Cara Pakai

### 1. Clone & Install

```bash
pip install ccxt pandas pandas-ta numpy pydantic httpx
```

### 2. Setup .env

```bash
# Di file .env
INDODAX_API_KEY=JIGGR0OL-xxxx
INDODAX_API_SECRET=ae474a33cxxxx
```

### 3. Paper Trading

**Satu siklus:**
```bash
./paper_trade.sh
# atau spesifik:
./paper_trade.sh --cycles 5
```

**Background via tmux:**
```bash
./start_paper.sh
tmux attach -t indodax-bot
# Ctrl+B 0 → bot logs
# Ctrl+B 1 → portfolio monitor
```

### 4. Live Trading

```bash
# Hanya jika balance IDR > 0!
python bot.py --live
```

### 5. Emergency Stop

```bash
touch .kill        # Stop dalam 1 detik
# atau
Ctrl+C             # Graceful shutdown
# atau
kill <PID>         # SIGTERM → graceful
```

### 6. Monitor

```bash
python monitor.py          # CLI dashboard (refresh 30s)
tail -f logs/bot.jsonl     # Live structured logs
tail -f logs/error.jsonl   # Error log
```

### 7. Backtest

```python
from lib.backtest import BacktestEngine
# load OHLCV dataframes...
engine = BacktestEngine(indicators, risk, exit, phantom, sentiment)
result = engine.run(ohlcv_dict)
print(result)
```

---

## Research & Referensi

Fitur production-critical di bot ini didasarkan pada riset dari sumber terpercaya:

| Sumber | Kontribusi |
|---|---|
| [cryptorobot.ai](https://cryptorobot.ai/blog/risk-management-crypto-trading-bots) | Risk management framework — 15 lapis risk, drawdown circuit, loss streak pause |
| [vantixs.com](https://vantixs.com/blog/rate-limits-retries-idempotency-crypto-trading-bots) | Exchange reliability — retry dengan exponential backoff, idempotency key, rate limit handling |
| [novaquantlab.com](https://novaquantlab.com/multi-exchange-trading-bot-python-production-bugs/) | Production bugs — crash recovery, structured logging, kill switch, reconciliation |
| [blockchain-council.org](https://www.blockchain-council.org/cryptocurrency/crypto-trading-bot-security/) | Security — API key isolation, graceful shutdown, server-side SL (via exchange limit orders) |
| [tradingwizard.io](https://tradingwizard.io/blog/crypto-trading-bot-risk-management-tips/) | Risk tips — daily loss limit, max drawdown, position sizing discipline |

**8 critical features yang diimplementasikan:**

1. ✅ Retry + exponential backoff untuk network errors
2. ✅ Order idempotency via clientOrderId
3. ✅ Graceful shutdown (SIGINT/SIGTERM)
4. ✅ Emergency kill switch (.kill file)
5. ✅ Crash recovery (WAL mode + checkpoint)
6. ✅ Position reconciliation (lokal vs exchange)
7. ✅ Structured logging (JSONL)
8. ✅ Telegram notifikasi real-time

**5 important features:**

9. ✅ Config validation (Pydantic — type + bounds)
10. ✅ Heartbeat monitoring
11. ✅ Daily P&L report
12. ✅ SQLite WAL mode (concurrent safety)
13. ✅ Backtest engine (identik dengan live)

---

## Testing History

| Tanggal | Test | Hasil |
|---|---|---|
| 2026-07-02 | Full lifecycle (threshold=0.20) | 15 cycles, entries BTC/ETH/SOL, trailing stop exits, cooldown blocked re-entry ✅ |
| 2026-07-02 | Moderate settings (threshold=0.20, SL=3%, cooldown=2m) | 20 cycles, 3 positions stayed open, hold behavior ✅ |
| 2026-07-02 | Background tmux runner | Bot + monitor running ✅ |
| 2026-07-02 | Refactor lib/ package | All imports OK, 1 cycle verified ✅ |

---

## Fitur Selanjutnya

- **Server-side SL/TP** via Indodax API (jika tersedia)
- **Multi-timeframe analysis** (konfirmasi 15m + 1h + 4h)
- **Market-making strategy** untuk sideway market
- **Web dashboard** (Streamlit atau Flask)
- **Portfolio rebalancing** otomatis
- **Machine learning** untuk prediksi arah price
