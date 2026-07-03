#!/data/data/com.termux/files/usr/bin/bash
# Termux setup for Indodax Trading Bot

echo "=== Indodax Bot — Termux Setup ==="
echo ""

# 1. Update packages
echo "[1/5] Updating Termux packages..."
pkg update -y && pkg upgrade -y

# 2. Install Python and dependencies
echo "[2/5] Installing Python + build tools..."
pkg install -y python python-pip clang binutils libxml2 libxslt cmake

# 3. Install Python packages
echo "[3/5] Installing Python packages..."
pip install --upgrade pip
pip install ccxt pandas pandas-ta numpy scikit-learn flask httpx pydantic

# 4. Install Termux extras
echo "[4/5] Installing Termux extras..."
pkg install -y termux-api termux-services

# 5. Setup auto-start script
echo "[5/5] Setting up auto-start..."

cat > $PREFIX/bin/start-bot << 'SCRIPT'
#!/data/data/com.termux/files/usr/bin/bash
# Auto-start script for Indodax Bot
cd ~/projects/indodax-bot

# Acquire wake lock
termux-wake-lock indodax-bot

# Notification
termux-notification --title "Indodax Bot" --content "Starting..." --id indodax-bot

# Run
python3 bot.py

# Release wake lock on exit
termux-wake-unlock indodax-bot
termux-notification --title "Indodax Bot" --content "Stopped" --id indodax-bot
SCRIPT

chmod +x $PREFIX/bin/start-bot

# Create auto-restart watchdog
cat > ~/projects/indodax-bot/watchdog.sh << 'WATCHDOG'
#!/data/data/com.termux/files/usr/bin/bash
# Watchdog: auto-restart bot if it crashes
cd ~/projects/indodax-bot
while true; do
    python3 bot.py >> logs/watchdog.log 2>&1
    echo "[$(date)] Bot crashed/stopped, restarting in 10s..." >> logs/watchdog.log
    sleep 10
done
WATCHDOG
chmod +x ~/projects/indodax-bot/watchdog.sh

# Create .bashrc entry for auto-start on Termux boot
if ! grep -q "start-bot" ~/.bashrc 2>/dev/null; then
    cat >> ~/.bashrc << 'BASHRC'
# Auto-start Indodax Bot (comment out to disable)
# ~/projects/indodax-bot/watchdog.sh &
BASHRC
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Commands:"
echo "  start-bot        — Run the bot (with wake lock)"
echo "  ~/projects/indodax-bot/watchdog.sh &  — Run with auto-restart"
echo ""
echo "To enable auto-start on boot, uncomment the line in ~/.bashrc"
echo "Or use termux-services for proper service management."
