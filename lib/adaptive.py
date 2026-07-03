import pandas as pd

from .config import CONFIG

SIGNAL_KEYS = ["trend", "mean_reversion", "momentum", "volume", "stochastic"]


class AdaptiveEngine:
    def __init__(self):
        self.signal_stats: dict[str, dict] = {
            k: {"wins": 0, "losses": 0, "total": 0}
            for k in SIGNAL_KEYS
        }
        self.weights = CONFIG.signal_weights.copy()
        self.regime = "unknown"
        self.regime_history: list[str] = []
        self.current_adx = 0.0

    def detect_regime(self, df: pd.DataFrame) -> str:
        if df is None or df.empty or len(df) < 5:
            return self.regime
        latest = df.iloc[-1]
        adx = latest.get("adx", 0) or 0
        self.current_adx = float(adx)
        atr = latest.get("atr_14", 0) or 0
        atr_pct = atr / max(latest.get("close", 1), 1)

        if pd.isna(adx) or adx == 0:
            return self.regime

        if adx > CONFIG.regime_adx_strong and atr_pct > 0.03:
            reg = "volatile"
        elif adx > CONFIG.regime_adx_strong:
            reg = "strong_trend"
        elif adx > CONFIG.regime_adx_trend:
            reg = "trending"
        elif adx > 15:
            reg = "ranging"
        else:
            reg = "choppy"

        self.regime = reg
        self.regime_history.append(reg)
        if len(self.regime_history) > 20:
            self.regime_history.pop(0)
        return reg

    def regime_threshold_mult(self) -> float:
        m = {
            "strong_trend": 0.75, "trending": 0.85, "ranging": 1.0,
            "choppy": 1.25, "volatile": 1.15, "unknown": 1.0,
        }
        return m.get(self.regime, 1.0)

    def regime_sizing_mult(self) -> float:
        m = {
            "strong_trend": 1.0, "trending": 0.9, "ranging": 0.7,
            "choppy": 0.4, "volatile": 0.5, "unknown": 0.8,
        }
        return m.get(self.regime, 0.8)

    def feed_trade(self, components: dict, pnl_pct: float):
        for key, val in components.items():
            if key not in self.signal_stats:
                continue
            if val is not None and val > 0:
                self.signal_stats[key]["total"] += 1
                if pnl_pct > 0:
                    self.signal_stats[key]["wins"] += 1
                else:
                    self.signal_stats[key]["losses"] += 1

    def update_weights(self):
        total_adj = 0.0
        for key in self.weights:
            s = self.signal_stats[key]
            if s["total"] >= CONFIG.adaptive_lookback:
                wr = s["wins"] / max(s["total"], 1)
                if wr < 0.40:
                    self.weights[key] *= (1.0 - CONFIG.adaptive_adjust_rate)
                elif wr > 0.60:
                    self.weights[key] *= (1.0 + CONFIG.adaptive_adjust_rate * 0.5)
                self.weights[key] = max(0.05, min(0.50, self.weights[key]))
            total_adj += self.weights[key]

        if total_adj > 0:
            for k in self.weights:
                self.weights[k] /= total_adj

    def regime_label(self) -> str:
        adx_str = f"ADX{self.current_adx:.0f}" if self.current_adx else ""
        return f"{self.regime}" + (f" {adx_str}" if adx_str else "")
