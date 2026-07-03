import json
import numpy as np
import pandas as pd
import pandas_ta as ta

from .config import CONFIG


class Indicators:
    @staticmethod
    def compute(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        for l in [9, 20, 50]:
            df[f"ema_{l}"] = ta.ema(df["close"], length=l)

        for l in [20, 50]:
            df[f"sma_{l}"] = ta.sma(df["close"], length=l)

        df["rsi_14"] = ta.rsi(df["close"], length=14)

        bb = ta.bbands(df["close"], length=20, std=2)
        if bb is not None and bb.shape[1] >= 3:
            df["bb_lower"] = bb.iloc[:, 0]
            df["bb_mid"] = bb.iloc[:, 1]
            df["bb_upper"] = bb.iloc[:, 2]

        macd = ta.macd(df["close"])
        if macd is not None and macd.shape[1] >= 3:
            df["macd"] = macd.iloc[:, 0]
            df["macd_signal"] = macd.iloc[:, 1]
            df["macd_hist"] = macd.iloc[:, 2]

        df["atr_14"] = ta.atr(df["high"], df["low"], df["close"], length=14)

        adx_df = ta.adx(df["high"], df["low"], df["close"], length=CONFIG.adx_period)
        if adx_df is not None:
            df["adx"] = adx_df.iloc[:, 0]
            df["dmp"] = adx_df.iloc[:, 1]
            df["dmn"] = adx_df.iloc[:, 2]

        stoch = ta.stoch(df["high"], df["low"], df["close"])
        if stoch is not None and stoch.shape[1] >= 2:
            df["stoch_k"] = stoch.iloc[:, 0]
            df["stoch_d"] = stoch.iloc[:, 1]

        df["volume_sma"] = ta.sma(df["volume"], length=CONFIG.volume_ma_period)
        df["volume_ratio"] = df["volume"] / df["volume_sma"].replace(0, np.nan)

        df["obv"] = ta.obv(df["close"], df["volume"])

        return df

    @staticmethod
    def signal_score(row: pd.Series, weights: dict | None = None,
                     phantom_penalty: float = 0.0,
                     ml_prob: float | None = None) -> dict:
        scores = {}
        details = {}

        trend = 0.0
        close = row.get("close")
        if pd.notna(close) and pd.notna(row.get("ema_20")):
            trend += 0.15 if close > row["ema_20"] else 0.0
            details["trend_price"] = "above_ema" if close > row["ema_20"] else "below_ema"
            details["trend_ema_gap"] = f"{((close/row['ema_20']-1)*100):+.2f}%"
        if pd.notna(row.get("rsi_14")):
            trend += 0.10 if 30 < row["rsi_14"] < 70 else 0.0
            details["trend_rsi"] = f"{row['rsi_14']:.1f}"
        scores["trend"] = trend

        meanrev = 0.0
        if pd.notna(close) and pd.notna(row.get("bb_lower")):
            if close <= row["bb_lower"]:
                meanrev += 0.15
                details["mrev_bb"] = "touch_lower"
            elif close >= row.get("bb_upper", close):
                details["mrev_bb"] = "touch_upper"
            else:
                bb_pct = (close - row["bb_lower"]) / max(row.get("bb_upper", close) - row["bb_lower"], 1)
                details["mrev_bb_pct"] = f"{bb_pct:.0%}"
        if pd.notna(row.get("rsi_14")):
            if row["rsi_14"] < 35:
                meanrev += 0.05
                details["mrev_rsi"] = "oversold"
        scores["mean_reversion"] = meanrev

        momentum = 0.0
        if pd.notna(row.get("macd")) and pd.notna(row.get("macd_signal")):
            if row["macd"] > row["macd_signal"] and row.get("macd_hist", 0) > 0:
                momentum += 0.20
                details["mom_macd"] = "bullish"
            elif row["macd"] < row["macd_signal"]:
                details["mom_macd"] = "bearish"
            else:
                details["mom_macd"] = "neutral"
        scores["momentum"] = momentum

        volume = 0.0
        if pd.notna(row.get("volume_ratio")):
            if row["volume_ratio"] > 1.5:
                volume += 0.10
                details["vol_ratio"] = f"{row['volume_ratio']:.1f}x"
            if pd.notna(row.get("obv")):
                volume += 0.05
                details["vol_obv"] = "ok"
        scores["volume"] = volume

        stoch = 0.0
        if pd.notna(row.get("stoch_k")) and pd.notna(row.get("stoch_d")):
            if row["stoch_k"] > row["stoch_d"] and row["stoch_k"] < 80:
                stoch += 0.05
                details["stoch"] = "bullish"
            else:
                details["stoch"] = "neutral"
        scores["stochastic"] = stoch

        w = weights or CONFIG.signal_weights
        total = (trend * w.get("trend", 0.20)
                 + meanrev * w.get("mean_reversion", 0.35)
                 + momentum * w.get("momentum", 0.25)
                 + volume * w.get("volume", 0.15)
                 + stoch * w.get("stochastic", 0.05))

        if ml_prob is not None and CONFIG.ml_enabled:
            total = total * (1 - CONFIG.ml_weight) + ml_prob * CONFIG.ml_weight
            details["ml_prob"] = f"{ml_prob:.2f}"

        penalty = phantom_penalty * CONFIG.phantom_penalty_max
        total_adj = total * (1.0 - penalty)
        max_raw = sum(w.values())
        return {
            "total": round(total_adj / max_raw, 2) if max_raw > 0 else 0,
            "raw": round(total / max_raw, 2) if max_raw > 0 else 0,
            "components": scores,
            "details": details,
            "phantom_penalty": round(penalty, 3),
        }

    @staticmethod
    def mtf_score(tf_dfs: dict[str, pd.DataFrame],
                  weights: dict[str, float] | None = None,
                  phantom_penalty: float = 0.0,
                  ml_prob: float | None = None) -> dict:
        if weights is None:
            weights = CONFIG.mtf_weights

        tf_scores = {}
        for tf, df in tf_dfs.items():
            if df is None or df.empty:
                continue
            latest = df.iloc[-1]
            tf_scores[tf] = Indicators.signal_score(
                latest, phantom_penalty=phantom_penalty, ml_prob=ml_prob)

        total_weight = sum(weights.get(tf, 0) for tf in tf_scores)
        if total_weight == 0:
            return {"total": 0.5, "components": {}, "details": {"mtf_note": "no_data"}}

        combined_total = 0.0
        combined_components = {}
        combined_details = {}
        for tf, sc in tf_scores.items():
            w = weights.get(tf, 0) / total_weight
            combined_total += sc["total"] * w
            for k, v in sc["components"].items():
                combined_components[f"{tf}_{k}"] = combined_components.get(f"{tf}_{k}", 0) + v * w
            combined_details[f"{tf}_score"] = f"{sc['total']:.2f}"

        return {
            "total": round(combined_total, 2),
            "raw": combined_total,
            "components": combined_components,
            "details": combined_details,
            "tf_scores": tf_scores,
        }

    @staticmethod
    def _extract_signal_components(trade: dict) -> dict[str, float]:
        raw = trade.get("signal_data", "{}")
        if isinstance(raw, str) and raw:
            try:
                data = json.loads(raw)
                return data.get("components", {})
            except (json.JSONDecodeError, TypeError):
                pass
        return {}
