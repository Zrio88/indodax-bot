# 🎮 INDODAX BOT - MENU & EXECUTION GUIDE

> **Easy execution with interactive menus for all platforms**

---

## 📋 QUICK START

### For Regular Linux/Mac/Windows (WSL)
```bash
# Make executable
chmod +x run_menu.sh

# Run the menu
./run_menu.sh
```

### For Termux (Android)
```bash
# Make executable
chmod +x termux_run.sh

# Run the Termux menu
./termux_run.sh
```

---

## 🎯 MENU OPTIONS COMPARISON

### run_menu.sh (Regular Systems)
| Option | Description | Safe for Live? |
|--------|-------------|--------------|
| **1** | Start PAPER Trading | ✅ Yes |
| **2** | Start LIVE Trading | ⚠️ Confirmation required |
| **3** | LIVE - 1 Cycle Test | ⚠️ Confirmation required |
| **4** | Run Backtest | ✅ Yes |
| **5** | Run Walk-Forward | ✅ Yes |
| **6** | Custom Cycles | ⚠️ Depends on mode |
| **7** | Reset Database | ✅ Yes |
| **8** | Run Test Suite | ✅ Yes |
| **9** | Show Configuration | ✅ Yes |
| **0** | Show Bot Status | ✅ Yes |
| **A** | Show Audit Report | ✅ Yes |
| **C** | Show Live Checklist | ✅ Yes |
| **Q** | Quit | ✅ Yes |

### termux_run.sh (Termux on Android)
| Option | Description | Termux Optimized |
|--------|-------------|-----------------|
| **1** | Start PAPER Trading | ✅ Wake lock, notifications |
| **2** | Start LIVE Trading | ✅ Wake lock, notifications |
| **3** | LIVE - 1 Cycle Test | ✅ Wake lock, notifications |
| **4** | Start in Background (tmux) | ✅ Best for 24/7 |
| **5** | Stop Bot (Graceful) | ✅ Creates .kill file |
| **6** | Force Stop Bot | ✅ Kills process |
| **7** | Check Bot Status | ✅ Shows all info |
| **8** | Run Test Suite | ✅ Full verification |
| **9** | Reset Database | ✅ Clean start |
| **T** | Termux Setup Guide | ✅ Installation help |
| **I** | Install Dependencies | ✅ Auto-install |
| **Q** | Quit | ✅ Yes |

---

## 🚀 RECOMMENDED WORKFLOWS

### For Beginners
```bash
# 1. Verify everything works
./run_menu.sh
# Select: 8 (Run Test Suite)

# 2. Try paper trading
./run_menu.sh
# Select: 1 (PAPER Trading)
# Let it run for a few cycles, then Ctrl+C

# 3. Check results
./run_menu.sh
# Select: 0 (Bot Status)

# 4. When ready for live
./run_menu.sh
# Select: 3 (LIVE - 1 Cycle Test)
# Then select: 2 (LIVE Trading)
```

### For Termux Users
```bash
# 1. Install dependencies
./termux_run.sh
# Select: I (Install Dependencies)

# 2. Test connection
./termux_run.sh
# Select: 3 (LIVE - 1 Cycle Test)

# 3. Start background trading
./termux_run.sh
# Select: 4 (Start in Background)
# Use session name: indodax-live

# 4. Check status
./termux_run.sh
# Select: 7 (Check Bot Status)

# 5. Stop when needed
./termux_run.sh
# Select: 5 (Graceful Stop)
```

---

## 🎨 FEATURES BY PLATFORM

### Regular Shell Menu (run_menu.sh)
- ✅ Color-coded output
- ✅ API key validation
- ✅ Configuration display
- ✅ Bot status monitoring
- ✅ Database management
- ✅ Test suite integration
- ✅ Documentation access

### Termux Menu (termux_run.sh)
- ✅ All regular features PLUS:
- ✅ Termux notifications (pop-up alerts)
- ✅ Wake lock (prevents phone sleep)
- ✅ Background execution (tmux)
- ✅ Auto-detection of Termux environment
- ✅ Termux-specific setup guide
- ✅ Dependency installation

---

## 📊 COMMAND REFERENCE

### Without Menu (Direct Commands)

```bash
# Paper Trading (Safe)
python3 bot.py
python3 bot.py --cycles 288  # Run 288 cycles (~24h)

# Live Trading
python3 bot.py --live
python3 bot.py --live --cycles 1  # Test 1 cycle
python3 bot.py --live --cycles 288  # Run 24h

# Backtest
python3 run_backtest.py

# Walk-Forward Analysis
python3 walk_forward.py

# Test Fixes
python3 test_fixes.py
```

### With Tmux (Background Execution)

```bash
# Start in background
tmux new-session -d -s indodax-bot 'python3 -u bot.py --live'

# Attach to see output
tmux attach -t indodax-bot

# Detach (keep running)
Ctrl+B, then D

# Check running sessions
tmux list-sessions

# Stop session
tmux kill-session -t indodax-bot

# Graceful stop (creates .kill file)
touch .kill
```

---

## 🎯 BEST PRACTICES

### Before Going Live
1. **Always test with paper trading first**
2. **Run the test suite**: `./run_menu.sh` → Option 8
3. **Start with 1 cycle test**: `./termux_run.sh` → Option 3
4. **Use background mode for 24/7**: `./termux_run.sh` → Option 4

### Monitoring
- Use **Option 7** (Bot Status) to check:
  - Running PIDs
  - Active tmux sessions
  - Database statistics (trades, P&L)

### Emergency Stop
1. **Graceful (recommended)**: `./termux_run.sh` → Option 5
2. **Force stop**: `./termux_run.sh` → Option 6
3. **Manual**: Create `.kill` file: `touch .kill`

---

## 📱 TERMUX SPECIFIC TIPS

### Prevent Phone from Sleeping
The Termux menu automatically uses **wake lock** when running in foreground:
- Keeps CPU awake while bot is running
- Prevents trades from being missed
- Works with `termux-run.sh` options 1, 2, 3

### Notifications
Termux notifications will appear for:
- Bot started/stopped
- 1 cycle test complete
- Background mode started
- Emergency stops

### Background Mode
For 24/7 trading on Termux:
1. Use **Option 4** to start in tmux background
2. Your phone can sleep - tmux keeps running
3. Check status with **Option 7**
4. Use `tmux attach` to see logs

### Battery Optimization
- Go to Android Settings → Apps → Termux → Battery
- Set to **Unrestricted** or **Don't optimize**
- This prevents Android from killing the bot

---

## ⚡ QUICK COMMANDS CHEAT SHEET

| Action | Regular Linux | Termux |
|--------|--------------|--------|
| Start Paper | `./run_menu.sh` → 1 | `./termux_run.sh` → 1 |
| Start Live | `./run_menu.sh` → 2 | `./termux_run.sh` → 2 |
| Test 1 Cycle | `./run_menu.sh` → 3 | `./termux_run.sh` → 3 |
| Background | Manual tmux | `./termux_run.sh` → 4 |
| Stop Graceful | Ctrl+C | `./termux_run.sh` → 5 |
| Force Stop | `pkill -f bot.py` | `./termux_run.sh` → 6 |
| Check Status | `./run_menu.sh` → 0 | `./termux_run.sh` → 7 |
| Test Suite | `./run_menu.sh` → 8 | `./termux_run.sh` → 8 |
| Reset DB | `./run_menu.sh` → 7 | `./termux_run.sh` → 9 |

---

## 🔧 TROUBLESHOOTING

### "Permission Denied" Error
```bash
chmod +x run_menu.sh termux_run.sh
```

### "command not found: tmux"
```bash
# On Ubuntu/Debian
sudo apt install tmux

# On CentOS/RHEL
sudo yum install tmux

# On Termux
pkg install tmux
```

### "No module named ccxt"
```bash
pip install ccxt pandas numpy pandas-ta scikit-learn httpx python-dotenv
```

### Termux Notifications Not Working
```bash
# Install Termux:API
pkg install termux-api
# Enable in Termux settings
```

### Wake Lock Not Working
```bash
# On Termux
pkg install termux-api
# Make sure you have the latest version
```

---

## 📝 AUTOMATION SCRIPTS

### Start Bot on Boot (Termux)

Create `~/.termux/boot/start_bot.sh`:
```bash
#!/bin/bash
cd /home/get/projects/indodax-bot
tmux new-session -d -s indodax-bot 'python3 -u bot.py --live'
```

Make it executable:
```bash
chmod +x ~/.termux/boot/start_bot.sh
```

Note: This requires Termux:Boot plugin from F-Droid.

### Auto-Restart Script

Create `auto_restart.sh`:
```bash
#!/bin/bash
cd /home/get/projects/indodax-bot

while true; do
    if ! pgrep -f "python3.*bot.py" > /dev/null; then
        echo "[$(date)] Bot not running, restarting..."
        python3 -u bot.py --live
    fi
    sleep 60
done
```

Run in background:
```bash
tmux new-session -d -s bot-watchdog './auto_restart.sh'
```

---

## 🎉 SUMMARY

| Feature | run_menu.sh | termux_run.sh |
|---------|------------|--------------|
| Paper Trading | ✅ | ✅ |
| Live Trading | ✅ | ✅ |
| Test Suite | ✅ | ✅ |
| Backtest | ✅ | ❌ |
| Walk-Forward | ✅ | ❌ |
| Custom Cycles | ✅ | ✅ |
| Database Reset | ✅ | ✅ |
| Bot Status | ✅ | ✅ |
| Configuration | ✅ | ✅ |
| Audit Report | ✅ | ❌ |
| Live Checklist | ✅ | ❌ |
| **Termux Notifications** | ❌ | ✅ |
| **Wake Lock** | ❌ | ✅ |
| **Background Mode** | ❌ | ✅ |
| **Termux Setup** | ❌ | ✅ |
| **Dependency Install** | ❌ | ✅ |

---

**Choose the right menu for your platform!**

- **Desktop/Laptop**: Use `run_menu.sh` (more options)
- **Android/Termux**: Use `termux_run.sh` (Termux-optimized)

Both menus provide easy access to all bot functionality with safety checks and confirmation prompts.
