import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path


class StructuredLogger:
    def __init__(self, name: str = "indodax-bot", log_dir: str = "logs"):
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.DEBUG)

        json_handler = logging.FileHandler(self.log_dir / "bot.jsonl")
        json_handler.setLevel(logging.INFO)
        json_handler.setFormatter(_JSONFormatter())
        self._logger.addHandler(json_handler)

        err_handler = logging.FileHandler(self.log_dir / "error.jsonl")
        err_handler.setLevel(logging.WARNING)
        err_handler.setFormatter(_JSONFormatter())
        self._logger.addHandler(err_handler)

        self._logger.propagate = False

    def _log(self, level: str, event: str, **extra):
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "event": event,
            **extra,
        }
        json_line = json.dumps(record, default=str)
        self._logger.log(
            {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}.get(level, 20),
            json_line,
        )

    def info(self, event: str, **kw):
        self._log("INFO", event, **kw)

    def warn(self, event: str, **kw):
        self._log("WARN", event, **kw)

    def error(self, event: str, **kw):
        self._log("ERROR", event, **kw)

    def debug(self, event: str, **kw):
        self._log("DEBUG", event, **kw)


class _JSONFormatter(logging.Formatter):
    def format(self, record):
        return record.getMessage()


class Console:
    """Pretty console output (human-readable — replaces old Logger class)."""

    @staticmethod
    def banner(paper: bool = True):
        mode = "PAPER" if paper else "LIVE"
        print("=" * 72)
        print(f"  INDODAX TRADING BOT — {mode} | Phantom-Aware | Super-Adaptive")
        print("=" * 72)

    @staticmethod
    def header():
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
        print("-" * 72)

    @staticmethod
    def pair_status(pair: str, price: float, score: dict, verdict: str):
        signal = "★" if verdict == "enter" else ("✓" if verdict == "hold" else "─")
        score_val = score.get('total', 0) if isinstance(score, dict) else 0
        print(f"  {signal} {pair:10s} Rp{price:>10,.0f} | score: {score_val:.2f} | {verdict}")

    @staticmethod
    def entry(pair: str, price: float, size: float, score: float):
        print(f"\n  → ENTRY {pair} @ Rp{price:,.0f} | Rp{size:,.0f} | score: {score:.2f}")

    @staticmethod
    def exit(pair: str, price: float, reason: str, pnl_pct: float, pnl_idr: float):
        sign = "+" if pnl_pct >= 0 else ""
        print(f"  ← EXIT  {pair} @ Rp{price:,.0f} | {reason} | {sign}{pnl_pct:.2%} ({sign}{pnl_idr:,.0f})")

    @staticmethod
    def summary(trades: list, balance: float, total_pnl: float, open_count: int, regime: str = ""):
        import numpy as np
        wins = sum(1 for t in trades if t.get("pnl_pct", 0) > 0)
        losses = sum(1 for t in trades if t.get("pnl_pct", 0) <= 0)
        total = wins + losses
        wr = wins / total if total else 0
        avg_win = np.mean([t["pnl_pct"] for t in trades if t.get("pnl_pct", 0) > 0]) if wins else 0
        avg_loss = np.mean([t["pnl_pct"] for t in trades if t.get("pnl_pct", 0) <= 0]) if losses else 0
        print(f"\n  ── Portfolio ──")
        print(f"  Balance: Rp{balance:,.0f} | P&L: {total_pnl:+,.0f} IDR")
        if total > 0:
            print(f"  Win rate: {wr:.1%} ({wins}W/{losses}L) | Avg win: {avg_win:.2%} | Avg loss: {avg_loss:.2%}")
        if open_count:
            print(f"  Open positions: {open_count}")
        if regime:
            print(f"  Market: {regime}")

    @staticmethod
    def blocked(reason: str):
        print(f"  ⛔ BLOCKED: {reason}\n")

    @staticmethod
    def error(msg: str):
        print(f"  ✖ ERROR: {msg}")


_log: StructuredLogger | None = None


def get_logger() -> StructuredLogger:
    global _log
    if _log is None:
        _log = StructuredLogger()
    return _log
