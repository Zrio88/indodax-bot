import os
import sys
import time
import uuid
import random
from datetime import datetime, timezone

import ccxt
import pandas as pd

from .config import CONFIG
from .logger import get_logger

log = get_logger()


PAIR_PRECISION = {
    "BTC/IDR": 6, "ETH/IDR": 5, "SOL/IDR": 4,
    "XRP/IDR": 2, "DOGE/IDR": 1,
}


def retry(max_attempts: int = 3, base_delay: float = 1.0):
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except (ccxt.NetworkError, ccxt.ExchangeNotAvailable,
                        ccxt.RequestTimeout) as e:
                    last_err = e
                    if attempt < max_attempts:
                        delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                        log.warn("retry", func=func.__name__, attempt=attempt,
                                 max=max_attempts, delay_ms=round(delay * 1000),
                                 error=str(e))
                        time.sleep(delay)
                    else:
                        log.error("retry_exhausted", func=func.__name__,
                                  attempts=max_attempts, error=str(e))
                except ccxt.BadSymbol as e:
                    log.error("bad_symbol", pair=kwargs.get("pair", args[1] if len(args) > 1 else "?"), error=str(e))
                    raise
                except ccxt.InsufficientFunds as e:
                    log.warn("insufficient_funds", error=str(e))
                    raise
                except Exception as e:
                    log.error("unexpected_error", func=func.__name__, error=str(e))
                    raise
            raise last_err
        return wrapper
    return decorator


class BaseExchange:
    def __init__(self, ex: ccxt.Exchange):
        self.ex = ex
        self._session_id = str(uuid.uuid4())[:8]

    def _adjust_precision(self, pair: str, amount: float,
                          round_down: bool = True) -> float:
        prec = PAIR_PRECISION.get(pair, 6)
        factor = 10 ** prec
        if round_down:
            return int(amount * factor) / factor
        return round(amount, prec)

    def _client_order_id(self) -> str:
        return f"bot_{self._session_id}_{uuid.uuid4().hex[:12]}"

    @retry(max_attempts=3)
    def fetch_ohlcv(self, pair: str, timeframe: str = "1h",
                    limit: int = 100) -> pd.DataFrame:
        raw = self.ex.fetch_ohlcv(pair, timeframe, limit=limit)
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high",
                                         "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df

    @retry(max_attempts=3)
    def fetch_ohlcv_multi(self, pair: str,
                          timeframes: list[str] | None = None,
                          limit: int = 100) -> dict[str, pd.DataFrame]:
        if timeframes is None:
            timeframes = CONFIG.timeframes
        result = {}
        for tf in timeframes:
            try:
                df = self.fetch_ohlcv(pair, tf, limit)
                if not df.empty:
                    result[tf] = df
            except Exception as e:
                log.warn("fetch_mtf_failed", pair=pair, timeframe=tf, error=str(e))
        return result

    @retry(max_attempts=3)
    def fetch_balance(self) -> dict:
        return self.ex.fetch_balance()

    @retry(max_attempts=3)
    def fetch_ticker(self, pair: str) -> dict:
        return self.ex.fetch_ticker(pair)

    def idr_balance(self) -> float:
        bal = self.fetch_balance()
        ret = bal.get("info", {}).get("return", {})
        return float(ret.get("balance", {}).get("idr", 0))

    @retry(max_attempts=3)
    def open_orders(self, pair: str | None = None) -> list:
        return self.ex.fetch_open_orders(pair)

    @retry(max_attempts=3)
    def market_buy(self, pair: str, idr_amount: float) -> dict:
        ticker = self.fetch_ticker(pair)
        last_price = ticker["last"]
        amount = idr_amount / last_price
        amount = self._adjust_precision(pair, amount, round_down=True)
        resp = self.ex.create_limit_buy_order(
            pair, amount, last_price * (1 + CONFIG.max_slippage_pct),
            params={"type": "buy", "clientOrderId": self._client_order_id()})
        return resp

    @retry(max_attempts=3)
    def market_sell(self, pair: str, amount: float) -> dict:
        ticker = self.fetch_ticker(pair)
        last_price = ticker["last"]
        amount = self._adjust_precision(pair, amount, round_down=True)
        resp = self.ex.create_limit_sell_order(
            pair, amount, last_price * (1 - CONFIG.max_slippage_pct),
            params={"type": "sell", "clientOrderId": self._client_order_id()})
        return resp

    @retry(max_attempts=3)
    def limit_buy(self, pair: str, amount: float, price: float) -> dict:
        amount = self._adjust_precision(pair, amount, round_down=True)
        price = max(price, 1)
        resp = self.ex.create_limit_buy_order(
            pair, amount, price,
            params={"clientOrderId": self._client_order_id()})
        return resp

    @retry(max_attempts=3)
    def limit_sell(self, pair: str, amount: float, price: float) -> dict:
        amount = self._adjust_precision(pair, amount, round_down=True)
        price = max(price, 1)
        resp = self.ex.create_limit_sell_order(
            pair, amount, price,
            params={"clientOrderId": self._client_order_id()})
        return resp

    @retry(max_attempts=3)
    def get_current_price(self, pair: str) -> float:
        return self.fetch_ticker(pair)["last"]

    def reconcile_positions(self, store) -> list[dict]:
        local_opens = store.open_trades()
        discrepancies = []
        for trade in local_opens:
            pair = trade["pair"]
            try:
                ex_balance = self.fetch_balance()
                ret = ex_balance.get("info", {}).get("return", {})
                bal = ret.get("balance", {})
                base_currency = pair.split("/")[0].lower()
                held = float(bal.get(base_currency, 0))
                expected_amount = trade["amount"]
                if held < expected_amount * 0.5 and held > 0:
                    log.warn("reconcile_partial_fill", pair=pair,
                             trade_id=trade["id"],
                             expected=expected_amount, actual=held)
                    discrepancies.append({
                        "trade": trade, "type": "partial_fill",
                        "expected": expected_amount, "actual": held,
                    })
                elif held == 0:
                    log.warn("reconcile_missing_position", pair=pair,
                             trade_id=trade["id"],
                             reason="No coins held on exchange for open trade")
                    discrepancies.append({
                        "trade": trade, "type": "missing_position",
                    })
            except Exception as e:
                log.error("reconcile_error", pair=pair, trade_id=trade["id"],
                          error=str(e))
        return discrepancies

    def health_check(self) -> bool:
        try:
            t = self.fetch_ticker("BTC/IDR")
            return t is not None and t.get("last", 0) > 0
        except Exception:
            return False


class IndodaxExchange(BaseExchange):
    def __init__(self):
        key = os.environ.get("INDODAX_API_KEY", "")
        secret = os.environ.get("INDODAX_API_SECRET", "")
        if not key or not secret:
            print("✖ INDODAX_API_KEY / INDODAX_API_SECRET not set")
            sys.exit(1)
        ex = ccxt.indodax({
            "apiKey": key, "secret": secret, "enableRateLimit": True,
        })
        super().__init__(ex)


class BybitExchange(BaseExchange):
    def __init__(self):
        key = os.environ.get("BYBIT_API_KEY", "")
        secret = os.environ.get("BYBIT_API_SECRET", "")
        if not key or not secret:
            print("⚠ BYBIT_API_KEY / BYBIT_API_SECRET not set — Bybit unavailable")
            self._available = False
            return
        ex = ccxt.bybit({
            "apiKey": key, "secret": secret, "enableRateLimit": True,
        })
        super().__init__(ex)
        self._available = True

    def is_available(self) -> bool:
        return getattr(self, "_available", False)

    def idr_balance(self) -> float:
        return 0.0


class BinanceExchange(BaseExchange):
    def __init__(self):
        key = os.environ.get("BINANCE_API_KEY", "")
        secret = os.environ.get("BINANCE_API_SECRET", "")
        if not key or not secret:
            print("⚠ BINANCE_API_KEY / BINANCE_API_SECRET not set — Binance unavailable")
            self._available = False
            return
        ex = ccxt.binance({
            "apiKey": key, "secret": secret, "enableRateLimit": True,
        })
        super().__init__(ex)
        self._available = True

    def is_available(self) -> bool:
        return getattr(self, "_available", False)

    def idr_balance(self) -> float:
        return 0.0


class Exchange:
    _instances: dict[str, BaseExchange] = {}

    def __new__(cls):
        if "primary" not in cls._instances:
            cls._instances["primary"] = IndodaxExchange()
        return cls._instances["primary"]

    def __getattr__(self, name):
        return getattr(self._instances["primary"], name)
