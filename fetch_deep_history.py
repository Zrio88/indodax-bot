"""Fetch deeper historical OHLCV via pagination (since param)."""
import sys
sys.path.insert(0, "/home/get/projects/indodax-bot")

from dotenv import load_dotenv
load_dotenv()

import time
import ccxt
import pandas as pd
from lib.config import CONFIG
from lib.storage import TradeStore
from lib.logger import get_logger

log = get_logger()
store = TradeStore()

pairs = ["BTC/IDR", "ETH/IDR", "SOL/IDR"]
TARGET_BARS = 2000  # ~83 days of 1h data

ex = ccxt.indodax({"enableRateLimit": True})

for pair in pairs:
    log.info("fetching_deep", pair=pair, target=TARGET_BARS)
    all_bars = []

    # Start from ~90 days ago
    since = ex.parse8601("2026-04-01T00:00:00Z")
    limit = 500

    while len(all_bars) < TARGET_BARS:
        try:
            raw = ex.fetch_ohlcv(pair, "1h", since=since, limit=limit)
            if not raw:
                break
            all_bars.extend(raw)
            since = raw[-1][0] + 1  # next batch after last timestamp
            log.info("  fetched", bars=len(raw), total=len(all_bars),
                     last_ts=pd.to_datetime(raw[-1][0], unit="ms").strftime("%Y-%m-%d %H:%M"))
            time.sleep(1.5)  # rate limit
        except Exception as e:
            log.error("fetch_error", pair=pair, error=str(e))
            break

    if not all_bars:
        continue

    df = pd.DataFrame(all_bars, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp")
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

    store.save_candles(pair, df)
    log.info("saved", pair=pair, bars=len(df),
             start=df["timestamp"].min().strftime("%Y-%m-%d"),
             end=df["timestamp"].max().strftime("%Y-%m-%d"))

log.info("deep_fetch_done")
