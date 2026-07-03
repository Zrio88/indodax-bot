from pydantic import BaseModel, Field, field_validator
from typing import Optional


class PerPairConfig(BaseModel):
    stop_loss_atr_mult: float | None = None
    take_profit_rr: float | None = None
    rsi_long_threshold: float | None = None
    rsi_short_threshold: float | None = None


class BotConfig(BaseModel):
    pairs: list[str] = ["BTC/IDR", "SOL/IDR"]
    per_pair: dict[str, PerPairConfig] = Field(default={
        "SOL/IDR": PerPairConfig(stop_loss_atr_mult=1.0),
        "BTC/IDR": PerPairConfig(),
    })
    max_open_positions: int = Field(default=3, ge=1, le=10)
    max_order_idr: float = Field(default=100_000, ge=10_000, le=10_000_000)
    risk_per_trade_pct: float = Field(default=0.01, ge=0.001, le=0.10)
    daily_loss_limit_idr: float = Field(default=100_000, ge=0)
    initial_balance_idr: float = Field(default=500_000, ge=0)
    hard_stop_loss_pct: float = Field(default=0.10, ge=0.01, le=0.50)
    stop_loss_atr_mult: float = Field(default=1.5, ge=1.0, le=5.0)
    stop_loss_min_pct: float = Field(default=0.01, ge=0.005, le=0.15)
    take_profit_rr: float = Field(default=1.5, ge=1.0, le=10.0)
    atr_trailing_mult: float = Field(default=2.5, ge=0.5, le=10.0)
    trailing_stop_min_pnl: float = Field(default=0.15, ge=0.005, le=0.50)
    breakeven_trigger_pct: float = Field(default=0.02, ge=0.005, le=0.10)
    time_stop_hours: int = Field(default=24, ge=1, le=168)
    global_cooldown_min: int = Field(default=30, ge=0, le=1440)
    loss_streak_pause: int = Field(default=3, ge=0, le=20)
    loss_streak_pause_hours: int = Field(default=2, ge=0, le=72)
    drawdown_circuit_pct: float = Field(default=0.10, ge=0.01, le=0.50)
    kelly_fraction: float = Field(default=0.5, ge=0.01, le=1.0)
    signal_threshold: float = Field(default=0.18, ge=0.0, le=1.0)
    timeframe: str = "1h"
    timeframes: list[str] = Field(default=["15m", "1h", "4h"])
    mtf_weights: dict[str, float] = Field(default={"15m": 0.2, "1h": 0.5, "4h": 0.3})
    ohlcv_limit: int = Field(default=100, ge=20, le=500)
    min_notional_idr: float = Field(default=10_000, ge=1_000)
    max_slippage_pct: float = Field(default=0.02, ge=0.001, le=0.10)
    volume_ma_period: int = Field(default=20, ge=5, le=100)
    cycle_interval_s: int = Field(default=300, ge=5, le=86_400)
    paper_mode: bool = True
    paper_balance_idr: float = Field(default=500_000, ge=0)
    adx_period: int = Field(default=14, ge=5, le=50)
    regime_adx_trend: int = Field(default=25, ge=10, le=50)
    regime_adx_strong: int = Field(default=40, ge=20, le=60)
    phantom_penalty_max: float = Field(default=0.5, ge=0.0, le=1.0)
    phantom_vol_spike_threshold: float = Field(default=3.0, ge=1.0)
    phantom_pump_rise: float = Field(default=0.03, ge=0.01)
    phantom_pump_fall: float = Field(default=-0.02, le=0.0)
    adaptive_adjust_rate: float = Field(default=0.05, ge=0.0, le=0.50)
    adaptive_lookback: int = Field(default=15, ge=1, le=100)
    signal_weights: dict[str, float] = Field(default={
        "trend": 0.20, "mean_reversion": 0.35,
        "momentum": 0.25, "volume": 0.15,
        "stochastic": 0.05,
    })
    short_signal_threshold: float = Field(default=0.18, ge=0.0, le=1.0)
    rsi_long_threshold: float = Field(default=25, ge=10, le=50)
    rsi_short_threshold: float = Field(default=75, ge=50, le=90)
    ml_enabled: bool = Field(default=True)
    ml_retrain_interval_h: int = Field(default=24, ge=1, le=168)
    ml_min_samples: int = Field(default=50, ge=20, le=1000)
    ml_weight: float = Field(default=0.15, ge=0.0, le=0.50)

    telegram_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    kill_file: str = ".kill"
    heartbeat_interval_m: int = Field(default=60, ge=0, le=1440)

    use_market_orders: bool = Field(default=False)
    exchange_name: str = Field(default="indodax")
    additional_exchanges: list[str] = Field(default=[])

    termux_wake_lock: bool = Field(default=True)
    termux_notify: bool = Field(default=False)

    @field_validator("pairs")
    @classmethod
    def check_pairs(cls, v):
        for p in v:
            if "/" not in p:
                raise ValueError(f"Invalid pair format: {p}")
        return v

    @field_validator("signal_weights")
    @classmethod
    def weights_sum_one(cls, v):
        total = sum(v.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Signal weights must sum to ~1.0, got {total}")
        return v


CONFIG = BotConfig()
