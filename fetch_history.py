"""Fetch historical OHLCV data from Indodax for backtesting."""
import sys
sys.path.insert(0, "/home/get/projects/indodax-bot")

from lib.config import CONFIG
from lib.exchange import Exchange as IndodaxExchange
from lib.storage import TradeStore
from lib.logger import get_logger
from dotenv import load_dotenv
load_dotenv()

log = get_logger()
exchange = IndodaxExchange()
storage = TradeStore()

pairs = ["BTC/IDR", "ETH/IDR", "SOL/IDR"]

for pair in pairs:
    log.info("fetching_history", pair=pair)
    df = exchange.fetch_ohlcv(pair, timeframe="1h", limit=500)
    if df is not None and not df.empty:
        storage.save_candles(pair, df)
        log.info("saved", pair=pair, bars=len(df),
                 time_range=f"{df['timestamp'].min()} → {df['timestamp'].max()}")

log.info("done")
