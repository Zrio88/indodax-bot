#!/bin/bash
# =============================================================================
# INDODAX BOT - TERMUX SPECIFIC RUNNER
# Optimized for Termux on Android
# Features: Wake lock, notifications, better error handling
# Usage: ./termux_run.sh [paper|live|test]
# =============================================================================

BOT_DIR="/home/get/projects/indodax-bot"
cd "$BOT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Termux notifications
termux_notify() {
    local title="$1"
    local msg="$2"
    termux-notification --title "$title" --content "$msg" --id indodax-bot --sound 2>/dev/null
}

# Wake lock management
acquire_wake_lock() {
    termux-wake-lock 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "  [Termux] Wake lock acquired"
    fi
}

release_wake_lock() {
    termux-wake-unlock 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "  [Termux] Wake lock released"
    fi
}

# Check Termux
if [ ! -d "/data/data/com.termux/files" ]; then
    echo "This script is optimized for Termux. Running in regular shell mode."
    TERMUX_MODE=false
else
    TERMUX_MODE=true
fi

# Load .env if exists
if [ -f ".env" ]; then
    source .env 2>/dev/null
fi

# Header
clear
cat << "EOF"
╔══════════════════════════════════════════════════════════════════════╗
║              🤖 INDODAX BOT - TERMUX EDITION                        ║
║                  Phantom-Aware | Super-Adaptive                   ║
╚══════════════════════════════════════════════════════════════════════╝
EOF

# Show Termux status
if [ "$TERMUX_MODE" = true ]; then
    echo -e "  ${GREEN}✓ Running in Termux mode${NC}"
    echo "  Features: Wake lock, Notifications, Background support"
else
    echo -e "  ${YELLOW}ℹ Running in regular shell mode${NC}"
fi

echo ""

# Check API keys
if [ -z "$INDODAX_API_KEY" ] || [ -z "$INDODAX_API_SECRET" ]; then
    echo -e "  ${RED}❌ INDODAX API keys not found${NC}"
    echo "  Please configure in .env file or export manually"
    echo ""
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Show menu
cat << "EOF"
  TERMUX MENU

  ${CYAN}[1]${NC}  Start PAPER Trading (Safe)
  ${CYAN}[2]${NC}  Start LIVE Trading (Real money)
  ${CYAN}[3]${NC}  Start LIVE - 1 Cycle Test
  ${CYAN}[4]${NC}  Start in Background (tmux)
  ${CYAN}[5]${NC}  Stop Bot (Graceful)
  ${CYAN}[6]${NC}  Force Stop Bot
  ${CYAN}[7]${NC}  Check Bot Status
  ${CYAN}[8]${NC}  Run Test Suite
  ${CYAN}[9]${NC}  Reset Database

  ${CYAN}[T]${NC}  Termux Setup
  ${CYAN}[I]${NC}  Install Dependencies

  ${CYAN}[Q]${NC}  Quit

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EOF

read -p "  Select option: " choice

echo ""

case "$choice" in
    1)
        # Paper Trading
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "  Starting PAPER TRADING"
        echo "  No real money - Safe mode"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        
        if [ "$TERMUX_MODE" = true ]; then
            acquire_wake_lock
            termux_notify "Indodax Bot" "Starting PAPER trading..."
            python3 -u bot.py
            release_wake_lock
            termux_notify "Indodax Bot" "PAPER trading stopped"
        else
            python3 bot.py
        fi
        ;;
    2)
        # Live Trading
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "  ⚠️  WARNING: LIVE TRADING - REAL MONEY"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        
        if [ -z "$INDODAX_API_KEY" ] || [ -z "$INDODAX_API_SECRET" ]; then
            echo -e "${RED}❌ ERROR: API keys required for LIVE trading${NC}"
            echo ""
            echo "  Set in .env file:"
            echo "    INDODAX_API_KEY=your_key"
            echo "    INDODAX_API_SECRET=your_secret"
            exit 1
        fi
        
        echo "  Testing connection..."
        python3 -c "
from lib.exchange import IndodaxExchange
import os
ex = IndodaxExchange()
if ex.health_check():
    print('  ✓ Connected to Indodax')
else:
    print('  ❌ Connection failed')
" 2>&1
        
        echo ""
        read -p "  Start LIVE trading? (y/N): " confirm
        if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
            echo "  Cancelled"
            exit 0
        fi
        
        echo ""
        echo "  Starting LIVE TRADING..."
        echo "  Running in foreground - Press Ctrl+C to stop"
        echo ""
        
        if [ "$TERMUX_MODE" = true ]; then
            acquire_wake_lock
            termux_notify "Indodax Bot LIVE" "Live trading started - Monitor carefully!"
            python3 -u bot.py --live
            release_wake_lock
            termux_notify "Indodax Bot" "Live trading stopped"
        else
            python3 bot.py --live
        fi
        ;;
    3)
        # Live - 1 Cycle Test
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "  LIVE TRADING - 1 Cycle Test"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        
        if [ -z "$INDODAX_API_KEY" ] || [ -z "$INDODAX_API_SECRET" ]; then
            echo -e "${RED}❌ ERROR: API keys required${NC}"
            exit 1
        fi
        
        echo "  Running 1 cycle test..."
        echo ""
        
        if [ "$TERMUX_MODE" = true ]; then
            acquire_wake_lock
            termux_notify "Indodax Bot" "Running 1 cycle test..."
            python3 -u bot.py --live --cycles 1
            release_wake_lock
            termux_notify "Indodax Bot" "1 cycle test complete"
        else
            python3 bot.py --live --cycles 1
        fi
        ;;
    4)
        # Background with tmux
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "  Starting Bot in Background (tmux)"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        
        read -p "  Mode (paper/live): " mode
        
        if [ "$mode" = "live" ]; then
            if [ -z "$INDODAX_API_KEY" ] || [ -z "$INDODAX_API_SECRET" ]; then
                echo -e "${RED}❌ ERROR: API keys required for LIVE${NC}"
                exit 1
            fi
            
            read -p "  Session name (default: indodax-live): " session
            if [ -z "$session" ]; then
                session="indodax-live"
            fi
            
            # Kill existing session
            tmux kill-session -t "$session" 2>/dev/null
            
            echo "  Starting tmux session: $session"
            echo "  Command: python3 -u bot.py --live"
            echo ""
            
            tmux new-session -d -s "$session" "python3 -u bot.py --live"
            
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✓ Bot started in background${NC}"
                echo ""
                echo "  To attach: tmux attach -t $session"
                echo "  To detach: Ctrl+B, then D"
                echo "  To stop: tmux kill-session -t $session"
                echo ""
                
                if [ "$TERMUX_MODE" = true ]; then
                    termux_notify "Indodax Bot" "Started in background (tmux: $session)"
                fi
            else
                echo -e "${RED}❌ Failed to start tmux session${NC}"
            fi
        else
            read -p "  Session name (default: indodax-paper): " session
            if [ -z "$session" ]; then
                session="indodax-paper"
            fi
            
            tmux kill-session -t "$session" 2>/dev/null
            tmux new-session -d -s "$session" "python3 -u bot.py"
            
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✓ Bot started in background${NC}"
                echo ""
                echo "  To attach: tmux attach -t $session"
                echo "  To stop: tmux kill-session -t $session"
            else
                echo -e "${RED}❌ Failed to start tmux session${NC}"
            fi
        fi
        ;;
    5)
        # Stop bot gracefully
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "  Stopping Bot (Graceful)"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        
        # Create kill file
        touch .kill
        echo "  ✓ Kill switch activated (.kill file created)"
        echo "  Bot will stop on next cycle (within ~5 minutes)"
        echo ""
        
        # Check if running
        if pgrep -f "python3.*bot.py" > /dev/null; then
            echo "  Waiting for bot to stop..."
            for i in {1..12}; do
                sleep 5
                if ! pgrep -f "python3.*bot.py" > /dev/null; then
                    echo "  ✓ Bot stopped"
                    break
                fi
                echo "  ."
            done
            
            if pgrep -f "python3.*bot.py" > /dev/null; then
                echo "  ⚠ Bot still running, try force stop"
            fi
        else
            echo "  ℹ Bot is not running"
        fi
        
        # Clean up
        rm -f .kill
        
        if [ "$TERMUX_MODE" = true ]; then
            termux_notify "Indodax Bot" "Graceful stop requested"
        fi
        ;;
    6)
        # Force stop
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "  Force Stopping Bot"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        
        pkill -f "python3.*bot.py" 2>/dev/null
        rm -f .kill
        
        echo "  ✓ Bot force stopped"
        
        if [ "$TERMUX_MODE" = true ]; then
            termux_notify "Indodax Bot" "Force stopped by user"
        fi
        ;;
    7)
        # Status
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "  Bot Status"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        
        # Check running
        if pgrep -f "python3.*bot.py" > /dev/null; then
            echo -e "${GREEN}✓ Bot is RUNNING${NC}"
            pgrep -f "python3.*bot.py" | while read pid; do
                echo "  PID: $pid"
                ps -p $pid -o cmd= | sed 's/^/    /'
            done
            echo ""
            echo "  Commands:"
            echo "    ./termux_run.sh 5  - Graceful stop"
            echo "    ./termux_run.sh 6  - Force stop"
        else
            echo -e "${RED}✗ Bot is NOT RUNNING${NC}"
        fi
        
        echo ""
        # tmux sessions
        echo "  Active tmux sessions:"
        tmux list-sessions 2>/dev/null | while read line; do
            echo "    $line"
        done
        
        echo ""
        # Database
        if [ -f "trades.db" ]; then
            echo "  Database:"
            closed=$(sqlite3 trades.db "SELECT COUNT(*) FROM trades WHERE status='closed';" 2>/dev/null)
            open=$(sqlite3 trades.db "SELECT COUNT(*) FROM trades WHERE status='open';" 2>/dev/null)
            pnl=$(sqlite3 trades.db "SELECT COALESCE(SUM(pnl_idr),0) FROM trades;" 2>/dev/null)
            
            echo "    Closed trades: $closed"
            echo "    Open positions: $open"
            if [ "$pnl" -gt 0 ]; then
                echo -e "    Total P&L: ${GREEN}+Rp ${pnl:,.0f}${NC}"
            else
                echo -e "    Total P&L: ${RED}Rp ${pnl:,.0f}${NC}"
            fi
        else
            echo "  Database: Not found"
        fi
        
        echo ""
        ;;
    8)
        # Test suite
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "  Running Test Suite"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        python3 test_fixes.py
        ;;
    9)
        # Reset database
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "  ⚠️  WARNING: Delete all trade history?"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        read -p "  Confirm (y/N): " confirm
        if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
            rm -f trades.db trades.db-shm trades.db-wal
            echo -e "${GREEN}✓ Database reset${NC}"
        else
            echo "  Cancelled"
        fi
        ;;
    T|t)
        # Termux setup
        clear
        cat << "EOF"
╔══════════════════════════════════════════════════════════════════════╗
║                  TERMUX SETUP GUIDE                                 ║
╚══════════════════════════════════════════════════════════════════════╝
EOF
        
        echo ""
        echo "  1. Install Termux from F-Droid (recommended)"
        echo ""
        echo "  2. Update packages:"
        echo "     pkg update && pkg upgrade"
        echo ""
        echo "  3. Install dependencies:"
        echo "     pkg install python git curl wget openssh tmux"
        echo ""
        echo "  4. Install pip packages:"
        echo "     pip install ccxt pandas numpy pandas-ta scikit-learn httpx"
        echo ""
        echo "  5. Clone or copy bot to Termux:"
        echo "     git clone https://github.com/your-repo/indodax-bot.git"
        echo "     cd indodax-bot"
        echo ""
        echo "  6. Configure API keys:"
        echo "     nano .env"
        echo "     Add: INDODAX_API_KEY=your_key"
        echo "          INDODAX_API_SECRET=your_secret"
        echo ""
        echo "  7. Allow Termux to run in background:"
        echo "     Settings > Apps > Termux > Battery > Unrestricted"
        echo ""
        echo "  8. Enable wake lock (prevents sleep):"
        echo "     pkg install termux-api"
        echo "     pip install termux-api"
        echo ""
        echo "  9. Run bot:"
        echo "     ./termux_run.sh"
        echo ""
        
        read -p "  Press Enter to return..."
        ;;
    I|i)
        # Install dependencies
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "  Installing Dependencies"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        
        if [ "$TERMUX_MODE" = true ]; then
            echo "  Updating Termux packages..."
            pkg update -y && pkg upgrade -y
            
            echo ""
            echo "  Installing system packages..."
            pkg install -y python git curl wget openssh tmux
            
            echo ""
            echo "  Installing Python packages..."
            pip install --upgrade pip
            pip install ccxt pandas numpy pandas-ta scikit-learn httpx python-dotenv
            
            echo ""
            echo -e "${GREEN}✓ Dependencies installed${NC}"
        else
            echo "  Installing Python packages..."
            pip install --upgrade pip
            pip install ccxt pandas numpy pandas-ta scikit-learn httpx python-dotenv
            
            echo ""
            echo -e "${GREEN}✓ Python packages installed${NC}"
        fi
        ;;
    Q|q)
        clear
        echo "  Goodbye!"
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid option: $choice${NC}"
        echo ""
        exit 1
        ;;
esac

echo ""
