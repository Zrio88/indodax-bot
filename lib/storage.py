import json
import sqlite3
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .logger import get_logger

log = get_logger()


class TradeStore:
    def __init__(self, db_path: str = "trades.db"):
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.row_factory = sqlite3.Row
        self._init_tables()
        self._migrate()

    def _init_tables(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pair TEXT, side TEXT, entry_price REAL, amount REAL,
                stop_loss REAL, take_profit REAL, size_idr REAL,
                entry_time TEXT, exit_time TEXT, exit_price REAL,
                pnl_idr REAL, pnl_pct REAL, exit_reason TEXT,
                signal_score REAL, status TEXT,
                client_order_id TEXT
            )""")
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS daily_pnl (
                day TEXT PRIMARY KEY, pnl_idr REAL, trades INTEGER
            )""")
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS candles (
                pair TEXT, timestamp INTEGER, open REAL, high REAL,
                low REAL, close REAL, volume REAL,
                PRIMARY KEY(pair, timestamp)
            )""")
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY, value TEXT
            )""")
        self.db.commit()

    def _migrate(self):
        """Add columns that may not exist in older schemas."""
        for col in ["signal_data TEXT", "client_order_id TEXT"]:
            col_name = col.split()[0]
            try:
                self.db.execute(f"ALTER TABLE trades ADD COLUMN {col}")
                self.db.commit()
                log.info("schema_migrate", column=col_name)
            except sqlite3.OperationalError:
                pass

    def add_trade(self, t: dict) -> int:
        c = self.db.execute(
            "INSERT INTO trades (pair,side,entry_price,amount,stop_loss,"
            "take_profit,size_idr,entry_time,status,signal_score,signal_data,"
            "client_order_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (t["pair"], t["side"], t["entry_price"], t["amount"],
             t["stop_loss"], t["take_profit"], t["size_idr"],
             t["entry_time"], "open", t["signal_score"],
             json.dumps(t.get("signal_data", {})),
             t.get("client_order_id")))
        self.db.commit()
        return c.lastrowid

    def close_trade(self, trade_id: int, exit_price: float,
                    pnl_idr: float, pnl_pct: float, reason: str):
        self.db.execute(
            "UPDATE trades SET exit_time=?,exit_price=?,pnl_idr=?,"
            "pnl_pct=?,exit_reason=?,status=? WHERE id=?",
            (datetime.now(timezone.utc).isoformat(), exit_price,
             pnl_idr, pnl_pct, reason, "closed", trade_id))
        self.db.commit()

    def open_trades(self) -> list[dict]:
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM trades WHERE status='open'").fetchall()]

    def recent_trades(self, n: int = 20) -> list[dict]:
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM trades WHERE status='closed' ORDER BY id DESC LIMIT ?",
            (n,)).fetchall()]

    def today_pnl(self) -> float:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = self.db.execute(
            "SELECT pnl_idr FROM daily_pnl WHERE day=?", (day,)).fetchone()
        return row[0] if row else 0.0

    def update_daily_pnl(self, pnl: float):
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.db.execute(
            "INSERT INTO daily_pnl (day,pnl_idr,trades) VALUES (?,?,1) "
            "ON CONFLICT(day) DO UPDATE SET pnl_idr=pnl_idr+?,trades=trades+1",
            (day, pnl, pnl))
        self.db.commit()

    def rolling_metrics(self, pair: str, n: int = 20) -> dict:
        rows = self.db.execute(
            "SELECT pnl_pct FROM trades WHERE pair=? AND status='closed' "
            "ORDER BY id DESC LIMIT ?", (pair, n)).fetchall()
        pnl = [r[0] for r in rows]
        if len(pnl) < 5:
            return {"win_rate": 0.5, "avg_win": 0.03, "avg_loss": 0.02,
                    "trades": len(pnl)}
        wins = [p for p in pnl if p > 0]
        losses = [p for p in pnl if p <= 0]
        return {
            "win_rate": len(wins) / len(pnl),
            "avg_win": float(np.mean(wins)) if wins else 0.03,
            "avg_loss": float(abs(np.mean(losses))) if losses else 0.02,
            "trades": len(pnl),
        }

    def loss_streak(self) -> int:
        rows = self.db.execute(
            "SELECT pnl_pct FROM trades WHERE status='closed' "
            "ORDER BY id DESC LIMIT 10").fetchall()
        streak = 0
        for r in rows:
            if r[0] <= 0:
                streak += 1
            else:
                break
        return streak

    def total_pnl(self) -> float:
        row = self.db.execute(
            "SELECT COALESCE(SUM(pnl_idr),0) FROM trades").fetchone()
        return row[0] if row else 0.0

    def save_candles(self, pair: str, df: pd.DataFrame):
        if df is None or df.empty:
            return
        vals = []
        for _, r in df.iterrows():
            ts = int(r["timestamp"].timestamp()) if hasattr(r["timestamp"], "timestamp") else int(r["timestamp"])
            vals.append((pair, ts, r["open"], r["high"],
                         r["low"], r["close"], r["volume"]))
        self.db.executemany(
            "INSERT OR REPLACE INTO candles "
            "(pair,timestamp,open,high,low,close,volume) "
            "VALUES (?,?,?,?,?,?,?)", vals)
        self.db.commit()

    def load_candles(self, pair: str, limit: int = 500) -> pd.DataFrame | None:
        rows = self.db.execute(
            "SELECT * FROM candles WHERE pair=? "
            "ORDER BY timestamp ASC LIMIT ?", (pair, limit)).fetchall()
        if not rows:
            return None
        df = pd.DataFrame(
            [dict(r) for r in rows],
            columns=["pair", "timestamp", "open", "high", "low", "close", "volume"])
        df.drop(columns=["pair"], inplace=True)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
        return df

    def set_meta(self, key: str, value: str):
        self.db.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?,?)",
            (key, value))
        self.db.commit()

    def get_meta(self, key: str) -> str | None:
        row = self.db.execute(
            "SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def daily_pnl_history(self, days: int = 30) -> list[dict]:
        rows = self.db.execute(
            "SELECT * FROM daily_pnl ORDER BY day DESC LIMIT ?",
            (days,)).fetchall()
        return [dict(r) for r in rows]
