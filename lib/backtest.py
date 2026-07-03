import json
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .config import CONFIG
from .logger import get_logger
from .indicators import Indicators

log = get_logger()


class BacktestEngine:
    def __init__(self, indicators_fn, risk_mgr, exit_mgr,
                 phantom_detector, sentiment_scorer):
        self.indicators_fn = indicators_fn
        self.risk_mgr = risk_mgr
        self.exit_mgr = exit_mgr
        self.phantom = phantom_detector
        self.sentiment = sentiment_scorer
        self.balance = CONFIG.initial_balance_idr

    def run(self, ohlcv_data: dict[str, pd.DataFrame]) -> dict:
        trades = []
        for pair, df in ohlcv_data.items():
            log.info("backtest_pair", pair=pair, bars=len(df))
            for i in range(100, len(df)):
                window = df.iloc[:i + 1]
                row = df.iloc[i]

                raw = self.indicators_fn(window)
                if raw is None:
                    continue

                computed_df = Indicators.compute(window)
                score, components, computed_df = self._compute_score(raw, computed_df, pair)
                self.exit_mgr.check_phantom(score)

                open_positions = [t for t in trades
                                  if t["status"] == "open" and t["pair"] == pair]
                position = open_positions[0] if open_positions else None

                if position is None:
                    if score["total"] >= CONFIG.signal_threshold:
                        atr_val = row.get("atr_14")
                        if pd.isna(atr_val) or atr_val <= 0:
                            atr_val = None
                        size = self.risk_mgr.position_size(
                            row["close"], pair, atr=atr_val)
                        if size >= CONFIG.min_notional_idr:
                            trade = {
                                "pair": pair, "side": "buy",
                                "entry_price": row["close"],
                                "entry_time": str(row["timestamp"]),
                                "amount": size / row["close"],
                                "size_idr": size,
                                "stop_loss": self.risk_mgr.stop_loss(
                                    row["close"], size),
                                "take_profit": self.risk_mgr.take_profit(
                                    row["close"], size),
                                "signal_score": score["total"],
                                "status": "open",
                            }
                            self.balance -= size
                            trade["id"] = len(trades)
                            trades.append(trade)

                elif position:
                    exit_signal, reason = self.exit_mgr.check_exits(
                        position, row["high"], row["low"], row["close"],
                        i, len(df), raw)
                    if exit_signal:
                        pnl_idr = (position["size_idr"]
                                   * (row["close"] / position["entry_price"] - 1))
                        pnl_pct = (row["close"] / position["entry_price"] - 1)
                        position["exit_time"] = str(row["timestamp"])
                        position["exit_price"] = row["close"]
                        position["pnl_idr"] = pnl_idr
                        position["pnl_pct"] = pnl_pct
                        position["exit_reason"] = reason
                        position["status"] = "closed"
                        self.balance += position["size_idr"] + pnl_idr

        closed = [t for t in trades if t["status"] == "closed"]
        opens = [t for t in trades if t["status"] == "open"]
        wins = sum(1 for t in closed if t.get("pnl_pct", 0) > 0)
        losses = sum(1 for t in closed if t.get("pnl_pct", 0) <= 0)
        total = wins + losses
        wr = wins / total if total else 0
        avg_win = np.mean([t["pnl_pct"] for t in closed
                          if t.get("pnl_pct", 0) > 0]) if wins else 0
        avg_loss = np.mean([t["pnl_pct"] for t in closed
                           if t.get("pnl_pct", 0) <= 0]) if losses else 0
        total_pnl = sum(t.get("pnl_idr", 0) for t in closed)

        return {
            "balance_final": self.balance,
            "total_pnl": total_pnl,
            "return_pct": total_pnl / CONFIG.initial_balance_idr,
            "total_trades": total,
            "wins": wins, "losses": losses,
            "win_rate": wr,
            "avg_win": avg_win, "avg_loss": avg_loss,
            "profit_factor": (avg_win * wins / abs(avg_loss * losses)
                              if losses else float("inf")),
            "open_positions": len(opens),
        }

    def _compute_score(self, indicators, window, pair):
        adx = indicators.get("adx", 25)
        regime = self._detect_regime(adx)
        threshold_mult = {"choppy": 1.2, "ranging": 1.05, "trending": 0.95,
                          "strong_trend": 0.85, "volatile": 0.90}.get(regime, 1.0)

        weights = CONFIG.signal_weights.copy()
        components = {}
        trend = indicators.get("trend", 1)
        components["trend"] = {"value": trend, "weight": weights["trend"],
                               "contribution": trend * weights["trend"]}

        mean_rev = indicators.get("mean_reversion", 0)
        components["mean_reversion"] = {"value": mean_rev,
                                        "weight": weights["mean_reversion"],
                                        "contribution": mean_rev * weights["mean_reversion"]}

        momentum = indicators.get("momentum", 0)
        components["momentum"] = {"value": momentum,
                                  "weight": weights["momentum"],
                                  "contribution": momentum * weights["momentum"]}

        vol = indicators.get("volume", 0)
        components["volume"] = {"value": vol, "weight": weights["volume"],
                                "contribution": vol * weights["volume"]}

        sto = indicators.get("stochastic", 0)
        components["stochastic"] = {"value": sto,
                                    "weight": weights["stochastic"],
                                    "contribution": sto * weights["stochastic"]}

        sentiment = self.sentiment()
        components["sentiment"] = {"value": sentiment,
                                   "weight": weights["sentiment"],
                                   "contribution": sentiment * weights["sentiment"]}

        total = sum(c["contribution"] for c in components.values())

        phantom_penalty = self.phantom.penalty(window)
        total *= (1 - phantom_penalty)

        return {"total": total, "components": components, "regime": regime,
                "threshold_mult": threshold_mult}, components, window

    def _detect_regime(self, adx):
        if adx < 18:
            return "choppy"
        elif adx < 25:
            return "ranging"
        elif adx < 35:
            return "trending"
        elif adx < 50:
            return "strong_trend"
        return "volatile"
