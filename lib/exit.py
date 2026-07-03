from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .config import CONFIG


class ExitManager:
    def __init__(self, store):
        self.store = store

    def check(self, pair: str, price: float, df: pd.DataFrame) -> list[dict]:
        actions = []
        for trade in self.store.open_trades():
            if trade["pair"] != pair:
                continue
            entry = trade["entry_price"]
            if not entry:
                continue
            direction = trade.get("direction", "long")
            pnl_pct = ((price - entry) / entry
                        if direction == "long"
                        else (entry - price) / entry)
            latest = df.iloc[-1] if df is not None and not df.empty else None

            stored_tp = trade.get("take_profit")
            stored_sl = trade.get("stop_loss")

            # Long exit checks
            if direction == "long":
                if stored_tp and stored_tp > entry and price >= stored_tp:
                    actions.append({"trade": trade, "action": "close",
                                    "reason": "take_profit", "price": stored_tp})
                    continue
                if stored_sl and stored_sl < entry and price <= stored_sl:
                    actions.append({"trade": trade, "action": "close",
                                    "reason": "stop_loss", "price": stored_sl})
                    continue
                if pnl_pct <= -CONFIG.hard_stop_loss_pct:
                    actions.append({"trade": trade, "action": "close",
                                    "reason": "hard_stop_loss", "price": price})
                    continue
            else:  # Short exit checks
                if stored_tp and stored_tp < entry and price <= stored_tp:
                    actions.append({"trade": trade, "action": "close",
                                    "reason": "take_profit", "price": stored_tp})
                    continue
                if stored_sl and stored_sl > entry and price >= stored_sl:
                    actions.append({"trade": trade, "action": "close",
                                    "reason": "stop_loss", "price": stored_sl})
                    continue
                if pnl_pct <= -CONFIG.hard_stop_loss_pct:
                    actions.append({"trade": trade, "action": "close",
                                    "reason": "hard_stop_loss", "price": price})
                    continue

            # Trailing stop: lock profit after threshold
            if pnl_pct >= CONFIG.trailing_stop_min_pnl:
                # Trail at X% below peak for longs, X% above peak for shorts
                trail_pct = CONFIG.trailing_stop_min_pnl * 0.3
                if direction == "long":
                    peak_price = entry * (1 + pnl_pct)
                    trail_level = peak_price * (1 - trail_pct)
                    if price <= trail_level:
                        actions.append({"trade": trade, "action": "close",
                                        "reason": "trailing_stop", "price": price})
                        continue
                elif direction == "short":
                    peak_price = entry * (1 - pnl_pct)
                    trail_level = peak_price * (1 + trail_pct)
                    if price >= trail_level:
                        actions.append({"trade": trade, "action": "close",
                                        "reason": "trailing_stop", "price": price})
                        continue

            # Breakeven SL
            if pnl_pct >= CONFIG.breakeven_trigger_pct:
                current_sl = trade.get("stop_loss", 0)
                if direction == "long" and current_sl < entry:
                    actions.append({"trade": trade, "action": "breakeven",
                                    "reason": "breakeven", "price": entry})
                elif direction == "short" and current_sl > entry:
                    actions.append({"trade": trade, "action": "breakeven",
                                    "reason": "breakeven", "price": entry})

            # Time stop
            entry_time = datetime.fromisoformat(trade["entry_time"])
            elapsed_h = (datetime.now(timezone.utc) - entry_time).total_seconds() / 3600
            if elapsed_h >= CONFIG.time_stop_hours:
                actions.append({"trade": trade, "action": "close",
                                "reason": "time_stop", "price": price})

        return actions
