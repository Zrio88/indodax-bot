import json
import pickle
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from .config import CONFIG
from .logger import get_logger

log = get_logger()

FEATURES = [
    "rsi_14", "ema_9", "ema_20", "ema_50", "sma_20", "sma_50",
    "macd", "macd_signal", "macd_hist", "bb_lower", "bb_upper",
    "atr_14", "adx", "stoch_k", "stoch_d", "volume_ratio",
    "obv",
]


class MLPredictor:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.model: RandomForestClassifier | None = None
        self._last_train_ts = 0
        self._min_samples = CONFIG.ml_min_samples
        model_dir = Path("models")
        model_dir.mkdir(exist_ok=True)
        self._model_path = model_dir / "ml_model.pkl"
        self._load_model()

    def _load_model(self):
        if self._model_path.exists():
            try:
                with open(self._model_path, "rb") as f:
                    self.model = pickle.load(f)
                log.info("ml_model_loaded", path=str(self._model_path))
            except Exception as e:
                log.warn("ml_model_load_failed", error=str(e))
                self.model = None

    def _save_model(self):
        if self.model is not None:
            try:
                with open(self._model_path, "wb") as f:
                    pickle.dump(self.model, f)
                log.info("ml_model_saved", path=str(self._model_path))
            except Exception as e:
                log.warn("ml_model_save_failed", error=str(e))

    def _extract_features(self, row: pd.Series) -> np.ndarray:
        vals = []
        for f in FEATURES:
            v = row.get(f)
            if pd.isna(v) or v is None:
                v = 0.0
            vals.append(float(v))
        return np.array(vals, dtype=np.float32)

    def predict(self, row: pd.Series) -> float:
        if self.model is None:
            return 0.5
        try:
            features = self._extract_features(row).reshape(1, -1)
            prob = self.model.predict_proba(features)
            class_idx = list(self.model.classes_).index(1) if 1 in self.model.classes_ else 1
            if prob.shape[1] > class_idx:
                return float(prob[0][class_idx])
            return float(prob[0][-1])
        except Exception as e:
            log.warn("ml_predict_failed", error=str(e))
            return 0.5

    def train(self, df: pd.DataFrame):
        if df is None or len(df) < self._min_samples:
            log.warn("ml_train_skipped", rows=len(df) if df is not None else 0,
                     min_samples=self._min_samples)
            return False

        df = df.copy()
        for f in FEATURES:
            if f not in df.columns:
                df[f] = 0.0
        df = df.fillna(0.0)

        shift = 1
        df["target"] = (df["close"].shift(-shift) > df["close"]).astype(int)
        df = df.iloc[:-shift]

        X = df[FEATURES].values.astype(np.float32)
        y = df["target"].values

        n_classes = len(np.unique(y))
        if n_classes < 2:
            log.warn("ml_train_single_class", n=len(y))
            return False

        self.model = RandomForestClassifier(
            n_estimators=100, max_depth=6, min_samples_leaf=10,
            random_state=42, n_jobs=-1, class_weight="balanced",
        )
        self.model.fit(X, y)

        acc = float(self.model.score(X, y))
        log.info("ml_trained", samples=len(X), accuracy=round(acc, 3))
        self._last_train_ts = time.time()
        self._save_model()
        return True

    def need_retrain(self) -> bool:
        if self.model is None:
            return True
        elapsed = time.time() - self._last_train_ts
        return elapsed >= CONFIG.ml_retrain_interval_h * 3600
