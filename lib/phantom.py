import numpy as np
import pandas as pd

from .config import CONFIG


class PhantomDetector:
    @staticmethod
    def penalty(df: pd.DataFrame) -> float:
        result = PhantomDetector.analyze(df)
        return result["phantom_score"]

    @staticmethod
    def analyze(df: pd.DataFrame) -> dict:
        if df is None or df.empty or len(df) < 6:
            return {"phantom_score": 0.0, "anomalies": [], "clean": True}
        lookback = df.tail(10).copy()
        latest = lookback.iloc[-1]
        anomalies = []
        severity = 0.0

        vol_ratio = latest.get("volume_ratio", 1.0)
        if pd.notna(vol_ratio):
            mid_idx = len(lookback) // 2
            first_half = lookback.iloc[:mid_idx]
            second_half = lookback.iloc[mid_idx:]
            price_change_mid = abs(
                first_half["close"].mean() / max(second_half["close"].mean(), 1) - 1
            ) if mid_idx >= 1 else 0
            if vol_ratio > CONFIG.phantom_vol_spike_threshold * 2 and price_change_mid < 0.01:
                anomalies.append("wash_trade")
                severity = max(severity, 0.8)
            elif vol_ratio > CONFIG.phantom_vol_spike_threshold and price_change_mid < 0.015:
                anomalies.append("volume_spike_no_move")
                severity = max(severity, 0.5)

        if len(lookback) >= 6:
            mid = len(lookback) // 2
            if mid >= 2:
                first = lookback.iloc[:mid]
                second = lookback.iloc[mid:]
                rise = first["close"].iloc[-1] / max(first["close"].iloc[0], 1) - 1
                fall = second["close"].iloc[-1] / max(second["close"].iloc[0], 1) - 1
                if rise > CONFIG.phantom_pump_rise and fall < CONFIG.phantom_pump_fall:
                    anomalies.append("pump_dump")
                    severity = max(severity, 0.7)

        candle = latest
        body = abs(candle.get("close", 0) - candle.get("open", 0))
        wick = candle.get("high", 0) - candle.get("low", 0)
        if wick > 0 and body / wick < 0.08:
            anomalies.append("doji_manipulation")
            severity = max(severity, 0.3)

        if len(lookback) >= 5:
            closes = lookback["close"].values
            ups = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i - 1])
            if ups >= len(closes) - 1:
                anomalies.append("consecutive_bullish")
                severity = max(severity, 0.3)

        spread = candle.get("high", 0) - candle.get("low", 0)
        mean_spread = (lookback["high"] - lookback["low"]).mean()
        if mean_spread > 0 and spread / mean_spread > 3.0:
            anomalies.append("spread_anomaly")
            severity = max(severity, 0.4)

        return {
            "phantom_score": round(severity, 2),
            "anomalies": anomalies,
            "clean": severity < 0.3,
        }
