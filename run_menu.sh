#!/bin/bash
# =============================================================================
# INDODAX BOT - MAIN MENU
# Easy execution menu for all bot operations
# Usage: ./run_menu.sh
# =============================================================================

BOT_DIR="/home/get/projects/indodax-bot"
cd "$BOT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Check if running in Termux
IS_TERMUX=false
if [ -d "/data/data/com.termux/files" ]; then
    IS_TERMUX=true
fi

clear

# Header
cat << "EOF"
╔══════════════════════════════════════════════════════════════════════╗
║                   🤖 INDODAX TRADING BOT MENU                         ║
║                     Phantom-Aware | Super-Adaptive                 ║
╚══════════════════════════════════════════════════════════════════════╝
EOF

# Environment check
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Please configure your API keys.${NC}"
    echo ""
fi

# Check API keys
if [ -f ".env" ]; then
    source .env 2>/dev/null
    if [ -z "$INDODAX_API_KEY" ] || [ -z "$INDODAX_API_SECRET" ]; then
        echo -e "${RED}❌ INDODAX API keys not configured in .env${NC}"
    else
        echo -e "${GREEN}✓ INDODAX API keys configured${NC}"
    fi
else
    echo -e "${RED}❌ .env file missing${NC}"
fi

# Main menu
while true; do
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  MAIN MENU"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  📊 ${CYAN}[1]${NC}  Run PAPER Trading (Safe - No real money)"
    echo "  💰 ${CYAN}[2]${NC}  Run LIVE Trading (Real money)"
    echo "  ⚡ ${CYAN}[3]${NC}  Run LIVE Trading (1 cycle test)"
    echo "  🧪 ${CYAN}[4]${NC}  Run Backtest"
    echo "  📈 ${CYAN}[5]${NC}  Run Walk-Forward Analysis"
    echo "  ⏱️  ${CYAN}[6]${NC}  Run Custom Cycles"
    echo ""
    echo "  🧹 ${CYAN}[7]${NC}  Reset Database (Clean start)"
    echo "  🧠 ${CYAN}[8]${NC}  Run Test Suite (Verify all fixes)"
    echo "  🔧 ${CYAN}[9]${NC}  Configure Bot Settings"
    echo "  ℹ️  ${CYAN}[0]${NC}  Show Bot Status"
    echo ""
    echo "  📋 ${CYAN}[A]${NC}  Show Audit Report"
    echo "  ✅ ${CYAN}[C]${NC}  Show Live Trading Checklist"
    echo "  ❌ ${CYAN}[Q]${NC}  Quit"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    read -p "  Select option: " choice
    
    case "$choice" in
        1)
            # Paper Trading
            clear
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "  Starting PAPER TRADING mode"
            echo "  No real money will be used"
            echo "  Press Ctrl+C to stop"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            python3 bot.py
            ;;
        2)
            # Live Trading
            clear
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "  ⚠️  WARNING: LIVE TRADING - REAL MONEY WILL BE USED"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            
            # Check API keys
            if [ -z "$INDODAX_API_KEY" ] || [ -z "$INDODAX_API_SECRET" ]; then
                echo -e "${RED}❌ ERROR: INDODAX API keys not configured!${NC}"
                echo ""
                echo "  Please add to .env file:"
                echo "    INDODAX_API_KEY=your_key_here"
                echo "    INDODAX_API_SECRET=your_secret_here"
                echo ""
                read -p "  Press Enter to return to menu..."
                continue
            fi
            
            # Test connection
            echo "  Testing exchange connection..."
            python3 -c "
from lib.exchange import IndodaxExchange
import os
os.environ['INDODAX_API_KEY'] = '$INDODAX_API_KEY'
os.environ['INDODAX_API_SECRET'] = '$INDODAX_API_SECRET'
try:
    ex = IndodaxExchange()
    if ex.health_check():
        print('  ✓ Connection successful')
    else:
        print('  ❌ Connection failed')
except Exception as e:
    print(f'  ❌ Error: {e}')
" 2>&1
            
            echo ""
            read -p "  Are you sure you want to start LIVE trading? (y/N): " confirm
            if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
                continue
            fi
            
            echo ""
            echo "  Starting LIVE TRADING..."
            echo "  Press Ctrl+C to stop"
            echo ""
            
            if [ "$IS_TERMUX" = true ]; then
                termux-wake-lock
                python3 -u bot.py --live
                termux-wake-unlock
            else
                python3 bot.py --live
            fi
            ;;
        3)
            # Live Trading - 1 cycle test
            clear
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "  LIVE TRADING - 1 Cycle Test"
            echo "  This will execute ONE trading cycle and exit"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            
            if [ -z "$INDODAX_API_KEY" ] || [ -z "$INDODAX_API_SECRET" ]; then
                echo -e "${RED}❌ ERROR: INDODAX API keys not configured!${NC}"
                read -p "  Press Enter to return to menu..."
                continue
            fi
            
            echo "  Running 1 cycle test..."
            echo ""
            python3 bot.py --live --cycles 1
            read -p "  Press Enter to return to menu..."
            ;;
        4)
            # Backtest
            clear
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "  Running Backtest"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            python3 run_backtest.py
            read -p "  Press Enter to return to menu..."
            ;;
        5)
            # Walk-Forward
            clear
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "  Running Walk-Forward Analysis"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            python3 walk_forward.py
            read -p "  Press Enter to return to menu..."
            ;;
        6)
            # Custom cycles
            clear
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "  Run Custom Number of Cycles"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            read -p "  Mode (paper/live): " mode
            read -p "  Number of cycles: " cycles
            
            if [ "$mode" = "live" ]; then
                if [ -z "$INDODAX_API_KEY" ] || [ -z "$INDODAX_API_SECRET" ]; then
                    echo -e "${RED}❌ ERROR: INDODAX API keys not configured!${NC}"
                    read -p "  Press Enter to return to menu..."
                    continue
                fi
                echo "  Starting LIVE trading for $cycles cycles..."
                python3 bot.py --live --cycles "$cycles"
            else
                echo "  Starting PAPER trading for $cycles cycles..."
                python3 bot.py --cycles "$cycles"
            fi
            read -p "  Press Enter to return to menu..."
            ;;
        7)
            # Reset database
            clear
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "  ⚠️  WARNING: This will DELETE all trade history"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            read -p "  Are you sure? (y/N): " confirm
            if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
                rm -f trades.db trades.db-shm trades.db-wal
                echo -e "${GREEN}✓ Database reset successfully${NC}"
            else
                echo "  Cancelled"
            fi
            read -p "  Press Enter to return to menu..."
            ;;
        8)
            # Test suite
            clear
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "  Running Test Suite"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            python3 test_fixes.py
            read -p "  Press Enter to return to menu..."
            ;;
        9)
            # Configure settings
            clear
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "  Bot Configuration"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            echo "  Current Configuration (from lib/config.py):"
            python3 -c "
from lib.config import CONFIG
print(f'  Mode: {\"LIVE\" if not CONFIG.paper_mode else \"PAPER\"}')
print(f'  Pairs: {CONFIG.pairs}')
print(f'  Timeframe: {CONFIG.timeframe}')
print(f'  Cycle interval: {CONFIG.cycle_interval_s}s')
print(f'  Max positions: {CONFIG.max_open_positions}')
print(f'  Risk per trade: {CONFIG.risk_per_trade_pct:.2%}')
print(f'  Max order size: Rp {CONFIG.max_order_idr:,.0f}')
print(f'  Signal threshold: {CONFIG.signal_threshold}')
print(f'  Use market orders: {CONFIG.use_market_orders}')
"
            echo ""
            echo "  Edit lib/config.py to change settings"
            echo ""
            read -p "  Press Enter to return to menu..."
            ;;
        0)
            # Show status
            clear
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "  Bot Status Check"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            
            # Check if bot is running
            if pgrep -f "python3.*bot.py" > /dev/null; then
                echo -e "${GREEN}✓ Bot is RUNNING${NC}"
                pgrep -f "python3.*bot.py" | while read pid; do
                    echo "  PID: $pid"
                done
                echo ""
                echo "  Commands:"
                echo "    touch .kill      - Graceful stop (recommended)"
                echo "    pkill -f bot.py  - Force stop"
            else
                echo -e "${RED}✗ Bot is NOT RUNNING${NC}"
            fi
            
            echo ""
            # Database stats
            if [ -f "trades.db" ]; then
                echo "  Database Statistics:"
                sqlite3 trades.db "SELECT COUNT(*) FROM trades WHERE status='closed';" 2>/dev/null | while read count; do
                    echo "    Closed trades: $count"
                done
                sqlite3 trades.db "SELECT COUNT(*) FROM trades WHERE status='open';" 2>/dev/null | while read count; do
                    echo "    Open positions: $count"
                done
                sqlite3 trades.db "SELECT COALESCE(SUM(pnl_idr),0) FROM trades;" 2>/dev/null | while read pnl; do
                    if [ "$pnl" -gt 0 ]; then
                        echo -e "    Total P&L: ${GREEN}+Rp ${pnl:,.0f}${NC}"
                    else
                        echo -e "    Total P&L: ${RED}Rp ${pnl:,.0f}${NC}"
                    fi
                done
            else
                echo "  Database: Not found (trades.db)"
            fi
            
            echo ""
            read -p "  Press Enter to return to menu..."
            ;;
        A|a)
            # Show audit report
            clear
            less AUDIT_REPORT_2026_07_03.md
            ;;
        C|c)
            # Show checklist
            clear
            less LIVE_TRADING_CHECKLIST.md
            ;;
        Q|q)
            clear
            echo "  Goodbye!"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid option. Please try again.${NC}"
            ;;
    esac
done
