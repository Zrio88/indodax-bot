import io
import os
from datetime import datetime, timezone

import httpx

from .config import CONFIG
from .logger import get_logger

log = get_logger()


class Notifier:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.token = CONFIG.telegram_token
        self.chat_id = CONFIG.telegram_chat_id
        self._enabled = bool(self.token and self.chat_id)

    def send(self, text: str):
        if not self._enabled:
            return
        try:
            resp = httpx.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text[:4096],
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=10,
            )
            resp.raise_for_status()
        except Exception as e:
            log.warn("notifier_failed", error=str(e))

    def entry(self, pair: str, price: float, size: float, score: float):
        msg = (
            f"🟢 <b>ENTRY</b> {pair}\n"
            f"Price: Rp{price:,.0f}\n"
            f"Size: Rp{size:,.0f}\n"
            f"Score: {score:.2f}"
        )
        self.send(msg)

    def exit(self, pair: str, price: float, reason: str,
             pnl_pct: float, pnl_idr: float):
        sign = "+" if pnl_pct >= 0 else ""
        emoji = "🟢" if pnl_pct >= 0 else "🔴"
        msg = (
            f"{emoji} <b>EXIT</b> {pair}\n"
            f"Price: Rp{price:,.0f}\n"
            f"Reason: {reason}\n"
            f"P&L: {sign}{pnl_pct:.2%} ({sign}{pnl_idr:,.0f} IDR)"
        )
        self.send(msg)

    def alert(self, text: str):
        self.send(f"⚠️ <b>Alert</b>\n{text}")

    def daily_report(self, trades: list, balance: float, total_pnl: float,
                     open_count: int):
        import numpy as np
        wins = sum(1 for t in trades if t.get("pnl_pct", 0) > 0)
        losses = sum(1 for t in trades if t.get("pnl_pct", 0) <= 0)
        total = wins + losses
        wr = wins / total if total else 0
        avg_win = (np.mean([t["pnl_pct"] for t in trades
                           if t.get("pnl_pct", 0) > 0])
                   if wins else 0)
        avg_loss = (np.mean([t["pnl_pct"] for t in trades
                            if t.get("pnl_pct", 0) <= 0])
                    if losses else 0)
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        msg = (
            f"📊 <b>Daily Report — {day}</b>\n"
            f"Balance: Rp{balance:,.0f}\n"
            f"P&L: {total_pnl:+,.0f} IDR\n"
        )
        if total:
            msg += (
                f"Trades: {total} ({wins}W/{losses}L)\n"
                f"Win rate: {wr:.1%}\n"
                f"Avg win: {avg_win:.2%} | Avg loss: {avg_loss:.2%}"
            )
        if open_count:
            msg += f"\nOpen positions: {open_count}"
        self.send(msg)

    def startup(self):
        if not self._enabled:
            return
        mode = "PAPER" if CONFIG.paper_mode else "LIVE"
        self.send(
            f"🤖 <b>Bot Started</b>\n"
            f"Mode: {mode}\n"
            f"Pairs: {', '.join(CONFIG.pairs)}\n"
            f"Cycle: {CONFIG.cycle_interval_s}s\n"
            f"Balance: Rp{CONFIG.paper_balance_idr:,.0f}"
        )

    def shutdown(self, reason: str = ""):
        self.send(f"🛑 <b>Bot Stopped</b>\n{reason}" if reason
                  else "🛑 <b>Bot Stopped</b>")
