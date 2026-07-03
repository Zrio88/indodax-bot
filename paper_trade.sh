#!/usr/bin/env bash
# Indodax Paper Trading — real data, simulated orders
cd "$(dirname "$0")"
export $(cat .env 2>/dev/null | xargs)
python3 bot.py --cycles "$@"
