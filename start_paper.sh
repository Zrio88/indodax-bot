#!/usr/bin/env bash
# Start paper trading bot in tmux with dashboard
cd "$(dirname "$0")"
SESSION="indodax-bot"

tmux new-session -d -s "$SESSION" -n bot bash -c '
  cd "$(dirname "$0")"
  export $(cat .env 2>/dev/null | xargs)

  # Acquire Termux wake lock if available
  command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock indodax-bot

  python3 bot.py "$@"

  # Release wake lock on exit
  command -v termux-wake-unlock >/dev/null 2>&1 && termux-wake-unlock indodax-bot
'

tmux new-window -t "$SESSION" -n monitor -d 'python3 monitor.py'

# Start dashboard if flask is available
python3 -c "import flask" 2>/dev/null && \
  tmux new-window -t "$SESSION" -n dashboard -d 'python3 -c "
import sys; sys.path.insert(0,\".\")
from dotenv import load_dotenv; load_dotenv()
from lib.dashboard import start_dashboard
from lib.storage import TradeStore
start_dashboard(TradeStore(), port=8081)
import time; time.sleep(99999)
"'

echo "Started session '$SESSION'"
echo "  Attach: tmux attach -t $SESSION"
echo "  Bot log:  Ctrl+B 0"
echo "  Monitor:  Ctrl+B 1"
echo "  Dashboard: Ctrl+B 2 (http://localhost:8081)"
echo ""
echo "  Kill:    touch .kill"
echo "  Detach:  Ctrl+B d"
