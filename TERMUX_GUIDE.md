# Termux Installation Guide - Indodax Bot

> **Complete step-by-step guide to install and run Indodax Bot on Termux (Android)**

---

## Requirements

- **Termux**: Must be installed from **F-Droid** (not Play Store)
- **Android**: Version 7.0 or higher
- **Storage**: At least 1GB free internal storage
- **RAM**: Minimum 2GB recommended

---

## Step 1: Install Termux from F-Droid

### Important: Use F-Droid version only!
The Play Store version of Termux **does not support** essential features like:
- `termux-api` (wake lock, notifications)
- `termux-wake-lock`
- `termux-notification`

### Installation:
1. Install **F-Droid** from [f-droid.org](https://f-droid.org)
2. Open F-Droid
3. Search for "Termux"
4. Install **Termux** (by Fredrik Fornwall)
5. Open Termux

---

## Step 2: Update System Packages

In Termux, run:
```bash
pkg update -y && pkg upgrade -y
```

This may take 5-10 minutes. Wait for completion.

---

## Step 3: Install Required System Packages

```bash
pkg install -y git curl wget openssh tmux nano
```

**Packages explained:**
- `git` - For repository cloning
- `curl`, `wget` - For downloading files
- `openssh` - For SSH connections
- `tmux` - For background execution
- `nano` - Text editor

---

## Step 4: Install Python

```bash
pkg install -y python
```

### Verify Installation:
```bash
python3 --version
```
Should display: **Python 3.11.x** or newer

---

## Step 5: Clone the Repository

### Option 1: Clone via Git (Recommended)
```bash
git clone https://github.com/Zrio88/indodax-bot.git
cd indodax-bot
```

### Option 2: Download ZIP (if git fails)
```bash
curl -L -o indodax-bot.zip https://github.com/Zrio88/indodax-bot/archive/refs/heads/master.zip
unzip indodax-bot.zip
mv indodax-bot-master indodax-bot
cd indodax-bot
```

---

## Step 6: Install Python Dependencies

```bash
pip install --upgrade pip
pip install ccxt pandas numpy pandas-ta scikit-learn httpx python-dotenv
```

**Installed packages:**
- `ccxt` - Exchange connection library (Indodax, Binance, Bybit)
- `pandas` - Data manipulation and analysis
- `numpy` - Numerical computations
- `pandas-ta` - Technical indicators (RSI, MACD, Bollinger Bands, etc.)
- `scikit-learn` - Machine learning (RandomForest classifier)
- `httpx` - HTTP client for notifications
- `python-dotenv` - Environment variable management

---

## Step 7: Install Termux API (Optional but Recommended)

For **wake lock** and **notification** features:

```bash
pkg install -y termux-api
```

Then install **Termux:API** plugin from F-Droid:
1. Open F-Droid
2. Search for "Termux:API"
3. Install the plugin
4. Restart Termux

---

## Step 8: Configure API Keys

Create `.env` file:
```bash
nano .env
```

Add your Indodax API keys:
```ini
INDODAX_API_KEY=your_api_key_from_indodax
INDODAX_API_SECRET=your_api_secret_from_indodax

# Optional: Telegram notifications
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### How to get Indodax API Keys:
1. Login to [Indodax](https://indodax.com)
2. Go to **Profile** → **API Key**
3. Create new API Key
4. Copy **API Key** and **Secret Key**

Save with: `Ctrl+O`, then `Enter`, then `Ctrl+X`

---

## Step 9: Verify Installation

### Test Python Dependencies:
```bash
python3 -c "import ccxt, pandas, numpy, pandas_ta; print('All dependencies available')"
```

### Test Indodax Connection:
```bash
python3 -c "
from lib.exchange import IndodaxExchange
import os
os.environ['INDODAX_API_KEY'] = 'YOUR_KEY'
os.environ['INDODAX_API_SECRET'] = 'YOUR_SECRET'
ex = IndodaxExchange()
print('Connection successful' if ex.health_check() else 'Connection failed')
"
```

---

## Step 10: Run the Bot

### Option 1: Use Termux Menu (Recommended)
```bash
chmod +x termux_run.sh
./termux_run.sh
```

**Menu Options:**
- `[1]` - Start PAPER Trading (Safe, no real money)
- `[2]` - Start LIVE Trading (Real money)
- `[3]` - LIVE - 1 Cycle Test
- `[4]` - Start in Background (Recommended for 24/7)
- `[5]` - Stop Bot (Graceful)
- `[6]` - Force Stop Bot
- `[7]` - Check Bot Status
- `[8]` - Run Test Suite
- `[9]` - Reset Database
- `[T]` - Termux Setup Guide
- `[I]` - Install Dependencies
- `[Q]` - Quit

### Option 2: Direct Commands
```bash
# Paper Trading
python3 bot.py

# LIVE Trading
python3 bot.py --live

# LIVE - 1 Cycle Test
python3 bot.py --live --cycles 1
```

---

## Termux-Specific Features

### Wake Lock
- Prevents phone from sleeping while bot is running
- Automatically activated when using `termux_run.sh` options 1, 2, 3

### Termux Notifications
- Pop-up notifications for:
  - Bot started/stopped
  - 1 cycle test complete
  - Background mode started
  - Emergency stops

### Background Execution (tmux)
- Bot continues running even when Termux is closed
- Use **Option 4** in the menu
- To attach: `tmux attach -t session_name`
- To detach: `Ctrl+B`, then `D`

---

## Monitoring the Bot

### Check Bot Status
```bash
./termux_run.sh
# Select: 7 (Check Bot Status)
```

### View Logs
```bash
tail -f bot.log
```

### Check Database
```bash
# Total trades
sqlite3 trades.db "SELECT COUNT(*) FROM trades;"

# Closed trades
sqlite3 trades.db "SELECT COUNT(*) FROM trades WHERE status='closed';"

# Open positions
sqlite3 trades.db "SELECT COUNT(*) FROM trades WHERE status='open';"

# Total P&L
sqlite3 trades.db "SELECT COALESCE(SUM(pnl_idr),0) FROM trades;"
```

---

## Performance Optimization Tips

### 1. Battery Optimization
- **Settings** → **Apps** → **Termux** → **Battery** → **Unrestricted**
- **Settings** → **Apps** → **Termux** → **Mobile Data** → **Unrestricted**
- Disable **Battery Optimization** for Termux

### 2. Storage
- Use **Internal Storage** (not SD Card)
- Ensure at least **1GB free space**

### 3. Network Connection
- Use **WiFi** for lowest latency
- Avoid slow mobile networks

### 4. Auto-Start (Optional)
To auto-start bot on boot:
1. Install **Termux:Boot** from F-Droid
2. Create boot script:
   ```bash
   mkdir -p ~/.termux/boot
   nano ~/.termux/boot/start_bot.sh
   ```
3. Add content:
   ```bash
   #!/bin/bash
   cd $HOME/indodax-bot
   tmux new-session -d -s indodax-bot 'python3 -u bot.py --live'
   ```
4. Make executable:
   ```bash
   chmod +x ~/.termux/boot/start_bot.sh
   ```

---

## Troubleshooting

### "command not found" Error
**Solution:**
```bash
pkg install <package-name>
```

### Python Module Not Found
**Solution:**
```bash
pip install <module-name>
```

### Termux API Not Working
**Solution:**
1. Ensure **Termux:API** is installed from F-Droid
2. Restart Termux
3. Test:
   ```bash
   termux-wake-lock
   termux-wake-unlock
   termux-notification --title "Test" --content "Hello"
   ```

### Permission Denied
**Solution:**
```bash
chmod +x run_menu.sh termux_run.sh
```

### Cannot Connect to Indodax
**Solution:**
1. Check API keys in `.env`
2. Test connection:
   ```bash
   python3 -c "from lib.exchange import IndodaxExchange; ex=IndodaxExchange(); print(ex.health_check())"
   ```

### Bot Crashes on Start
**Solution:**
1. Check error message
2. Install missing module:
   ```bash
   pip install <missing-module>
   ```
3. Fix API key errors in `.env`

---

## Pre-Start Checklist

| # | Task | Status |
|---|------|--------|
| 1 | Termux from F-Droid | ✅ |
| 2 | Update & Upgrade | ✅ |
| 3 | Install system packages | ✅ |
| 4 | Install Python | ✅ |
| 5 | Clone repository | ✅ |
| 6 | Install Python dependencies | ✅ |
| 7 | Install Termux:API | ⏳ |
| 8 | Configure .env | ⏳ |
| 9 | Test Indodax connection | ⏳ |
| 10 | Run test suite | ⏳ |

---

## Quick Start Commands

```bash
# 1. Update system
pkg update -y && pkg upgrade -y

# 2. Install packages
pkg install -y git curl wget openssh tmux nano python

# 3. Clone repository
git clone https://github.com/Zrio88/indodax-bot.git
cd indodax-bot

# 4. Install Python dependencies
pip install ccxt pandas numpy pandas-ta scikit-learn httpx python-dotenv

# 5. Install Termux:API
pkg install -y termux-api

# 6. Configure API keys
nano .env

# 7. Run menu
chmod +x termux_run.sh
./termux_run.sh
```

---

## License

This project is open-source under the **MIT License**. See [LICENSE](LICENSE) for details.

---

## Repository

- **GitHub**: [https://github.com/Zrio88/indodax-bot](https://github.com/Zrio88/indodax-bot)
- **Status**: Production Ready ✅
- **Maintainer**: Zrio88

---

**Happy Trading!** 🚀
