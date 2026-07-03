# ✅ LIVE TRADING CHECKLIST - INDODAX BOT

## 🎯 BEFORE GOING LIVE

### 1. Verify All Fixes
```bash
cd /home/get/projects/indodax-bot
python3 test_fixes.py
```
**Expected**: All tests pass with ✅

---

### 2. Reset Database (Recommended)
```bash
rm -f trades.db trades.db-shm trades.db-wal
```
*This ensures clean start without old paper trades*

---

### 3. Configure for Live Trading
Edit `lib/config.py` or create `.env` file:

```python
# Recommended conservative settings for LIVE
CONFIG = BotConfig(
    paper_mode=False,              # LIVE mode
    pairs=["BTC/IDR"],            # Start with 1 pair
    max_open_positions=2,         # Max 2 positions
    risk_per_trade_pct=0.01,      # 1% risk per trade
    max_order_idr=100_000,        # Rp 100K max per order
    initial_balance_idr=500_000,  # Your actual balance
    daily_loss_limit_idr=50_000, # 10% of balance
    drawdown_circuit_pct=0.05,    # 5% drawdown circuit
    signal_threshold=0.20,        # 20% minimum signal
    use_market_orders=False,      # Use limit orders (safer)
    cycle_interval_s=300,         # 5 minutes
    timeframe="1h",               # 1 hour candles
    stop_loss_atr_mult=1.5,       # 1.5x ATR for SL
    take_profit_rr=1.5,           # 1.5:1 reward ratio
    hard_stop_loss_pct=0.10,      # 10% hard stop
    stop_loss_min_pct=0.01,      # 1% minimum SL
)
```

---

### 4. Set Environment Variables
```bash
# Add to your shell profile or .env file
export INDODAX_API_KEY="your_api_key_here"
export INDODAX_API_SECRET="your_api_secret_here"

# Optional: Telegram notifications
export TELEGRAM_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
```

---

### 5. Test API Connection
```bash
python3 -c "
from lib.exchange import IndodaxExchange
from lib.config import CONFIG
ex = IndodaxExchange()
print('Testing connection...')
print('Health check:', ex.health_check())
print('Balance:', ex.idr_balance())
print('Ticker BTC/IDR:', ex.fetch_ticker('BTC/IDR')['last'])
"
```
**Expected**: No errors, positive balance returned

---

## 🚀 STARTING LIVE TRADING

### Option 1: Manual Run (Recommended for first time)
```bash
# Start bot in LIVE mode for 1 cycle (test)
python3 bot.py --live --cycles 1

# If successful, start continuous trading
python3 bot.py --live
```

### Option 2: Tmux Session (Recommended for production)
```bash
# Create tmux session
tmux new-session -d -s indodax-bot-live 'python3 -u bot.py --live'

# Attach to monitor
tmux attach -t indodax-bot-live

# Detach (keep running): Ctrl+B, then D
```

### Option 3: Screen Session
```bash
screen -S indodax-bot-live
python3 -u bot.py --live
# Detach: Ctrl+A, then D
```

---

## 📊 MONITORING LIVE TRADING

### 1. Check Logs
```bash
# View real-time logs
tail -f bot.log

# View structured logs (JSON)
tail -f logs/bot.jsonl | jq

# Check errors
tail -f logs/error.jsonl | jq
```

### 2. Check Database
```bash
# View recent trades
sqlite3 trades.db "SELECT id, pair, entry_price, exit_price, pnl_idr, pnl_pct, exit_reason, entry_time, exit_time FROM trades ORDER BY id DESC LIMIT 10;"

# Check total PnL
sqlite3 trades.db "SELECT SUM(pnl_idr) FROM trades;"

# Check open positions
sqlite3 trades.db "SELECT id, pair, entry_price, amount, stop_loss, take_profit FROM trades WHERE status='open';"
```

### 3. Dashboard (if enabled)
```bash
# Dashboard runs on port 8081 by default
# Open in browser: http://localhost:8081
```

---

## ⚡ EMERGENCY STOP

### Method 1: Kill Switch File (Recommended)
```bash
touch .kill
# Bot will stop on next cycle
```

### Method 2: Graceful Shutdown
```bash
# Find process ID
ps aux | grep bot.py

# Send SIGTERM
kill <PID>
```

### Method 3: Kill Tmux Session
```bash
tmux kill-session -t indodax-bot-live
```

### Method 4: Emergency Kill (Last Resort)
```bash
pkill -9 -f bot.py
```

---

## 📈 POST-TRADE ANALYSIS

### 1. Daily Report
Bot sends daily report via Telegram (if configured) with:
- Total PnL
- Win rate
- Average win/loss
- Open positions

### 2. Performance Metrics
```bash
python3 -c "
from lib.storage import TradeStore
store = TradeStore()
trades = store.recent_trades(100)
print(f'Total trades: {len(trades)}')
print(f'Total PnL: Rp {store.total_pnl():,.0f}')
wins = [t for t in trades if t.get('pnl_pct', 0) > 0]
losses = [t for t in trades if t.get('pnl_pct', 0) <= 0]
print(f'Win rate: {len(wins)/(len(wins)+len(losses)):.1%}')
if wins:
    print(f'Avg win: {sum(t[\"pnl_pct\"] for t in wins)/len(wins):.2%}')
if losses:
    print(f'Avg loss: {sum(t[\"pnl_pct\"] for t in losses)/len(losses):.2%}')
"
```

### 3. Walk-Forward Analysis
```bash
python3 walk_forward.py
```
*Runs backtest on recent data*

---

## 🔄 MAINTENANCE

### 1. Database Backup
```bash
# Daily backup
cp trades.db trades.db-$(date +%Y%m%d).bak
```

### 2. Log Rotation
```bash
# Compress old logs
find logs/ -name "*.jsonl" -size +10M -exec gzip {} \;
```

### 3. Model Retraining
ML models auto-retrain every `ml_retrain_interval_h` hours (default: 24)

---

## ⚠️ TROUBLESHOOTING

### Problem: Bot won't start
**Check**:
- API keys in environment
- Python dependencies installed
- No syntax errors

### Problem: No trades being placed
**Check**:
- Signal threshold too high
- Market conditions (trending/ranging)
- Risk limits (daily loss, drawdown)

### Problem: Exchange connection failed
**Check**:
- Internet connection
- Indodax API status
- API rate limits (ccxt has built-in rate limiting)

### Problem: Orders not filling
**Check**:
- Using market orders? Try limit orders
- Price too far from market
- Insufficient funds

---

## 📞 SUPPORT & MONITORING

### Checklist Before Leaving Bot Running
- [ ] Bot started successfully
- [ ] First cycle completed without errors
- [ ] Exchange connection stable
- [ ] API keys working
- [ ] Notifications working (Telegram)
- [ ] Logs being written
- [ ] Database updating
- [ ] Dashboard accessible (if enabled)
- [ ] Emergency stop method tested
- [ ] Backup strategy in place

---

## 🎉 SUCCESS CHECKLIST

- [ ] Bot running for 24+ hours without crashes
- [ ] At least 5 trades executed
- [ ] Win rate > 50%
- [ ] No negative PnL trends
- [ ] All monitoring systems working
- [ ] Emergency stop tested
- [ ] Backup strategy verified

**When all checked: Bot is production-ready!**

---

*Last updated: 2026-07-03*