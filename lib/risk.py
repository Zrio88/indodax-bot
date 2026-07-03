import time

from .config import CONFIG


class RiskManager:
    def __init__(self, store, paper: bool = False):
        self.store = store
        self.last_trade_time: float | None = None
        self.consecutive_losses = 0
        self.peak_balance = CONFIG.initial_balance_idr
        self.paper = paper
        self.paper_balance = CONFIG.paper_balance_idr if paper else 0

    def refresh(self):
        self.consecutive_losses = self.store.loss_streak()

    def can_trade(self, ex=None) -> tuple[bool, str]:
        self.refresh()

        today_pnl = self.store.today_pnl()
        if today_pnl <= -CONFIG.daily_loss_limit_idr:
            return False, f"Daily loss limit ({today_pnl:,.0f} IDR)"

        total_pnl = self.store.total_pnl()
        base = CONFIG.paper_balance_idr if self.paper else CONFIG.initial_balance_idr
        current_balance = base + total_pnl
        if current_balance > self.peak_balance:
            self.peak_balance = current_balance
        dd = (self.peak_balance - current_balance) / self.peak_balance if self.peak_balance > 0 else 0
        if dd > CONFIG.drawdown_circuit_pct:
            return False, f"Drawdown {dd:.1%}"

        if self.consecutive_losses >= CONFIG.loss_streak_pause:
            return False, f"Loss streak {self.consecutive_losses}"

        if len(self.store.open_trades()) >= CONFIG.max_open_positions:
            return False, "Max positions reached"

        if self.last_trade_time:
            elapsed = (time.time() - self.last_trade_time) / 60
            if elapsed < CONFIG.global_cooldown_min:
                return False, f"Cooldown {elapsed:.0f}/{CONFIG.global_cooldown_min}m"

        if self.paper:
            if self.paper_balance < CONFIG.min_notional_idr:
                return False, f"Paper balance too low ({self.paper_balance:,.0f} IDR)"
        elif ex:
            idr = ex.idr_balance()
            if idr < CONFIG.min_notional_idr:
                return False, f"IDR balance too low ({idr:,.0f})"

        return True, "ok"

    def position_size(self, entry_price: float, pair: str,
                      regime_mult: float = 1.0, atr: float | None = None) -> float:
        if self.paper:
            base = CONFIG.paper_balance_idr
        else:
            base = CONFIG.initial_balance_idr
        total_pnl = self.store.total_pnl()
        current_balance = base + total_pnl

        # 1. ATR-based sizing: risk equal % of balance per trade
        if atr and atr > 0:
            stop_dist_pct = max(
                (atr * CONFIG.stop_loss_atr_mult) / entry_price,
                CONFIG.stop_loss_min_pct)
            size = (current_balance * CONFIG.risk_per_trade_pct) / stop_dist_pct
        else:
            size = (current_balance * CONFIG.risk_per_trade_pct
                    / CONFIG.stop_loss_min_pct)

        # 2. Drawdown reduction
        dd = max(0, -total_pnl / base) if base > 0 else 0
        if dd > 0.20:
            dd_mult = 0.0
        elif dd > 0.15:
            dd_mult = 0.25
        elif dd > 0.10:
            dd_mult = 0.50
        elif dd > 0.05:
            dd_mult = 0.75
        else:
            dd_mult = 1.0

        size *= dd_mult * regime_mult

        return max(CONFIG.min_notional_idr,
                   min(size, CONFIG.max_order_idr))

    def stop_loss(self, price: float, size: float = 0, atr: float | None = None, mult: float | None = None) -> float:
        mult = mult if mult is not None else CONFIG.stop_loss_atr_mult
        if atr and atr > 0:
            sl = price - (atr * mult)
            max_sl = price * (1 - CONFIG.hard_stop_loss_pct)
            min_sl = price * (1 - CONFIG.stop_loss_min_pct)
            return min(max(sl, max_sl), min_sl)
        return price * (1 - CONFIG.hard_stop_loss_pct)

    def take_profit(self, price: float, size: float = 0, atr: float | None = None, mult: float | None = None, rr: float | None = None) -> float:
        sl = self.stop_loss(price, size, atr, mult=mult)
        rr = rr if rr is not None else CONFIG.take_profit_rr
        return price + (price - sl) * rr

    def stop_loss_short(self, price: float, size: float = 0, atr: float | None = None, mult: float | None = None) -> float:
        mult = mult if mult is not None else CONFIG.stop_loss_atr_mult
        if atr and atr > 0:
            sl = price + (atr * mult)
            max_sl = price * (1 + CONFIG.hard_stop_loss_pct)
            min_sl = price * (1 + CONFIG.stop_loss_min_pct)
            return max(min(sl, max_sl), min_sl)
        return price * (1 + CONFIG.hard_stop_loss_pct)

    def take_profit_short(self, price: float, size: float = 0, atr: float | None = None, mult: float | None = None, rr: float | None = None) -> float:
        sl = self.stop_loss_short(price, size, atr, mult=mult)
        rr = rr if rr is not None else CONFIG.take_profit_rr
        return price - (sl - price) * rr

    def record_trade(self, pnl_pct: float, pnl_idr: float = 0):
        self.last_trade_time = time.time()
        self.paper_balance += pnl_idr
        if pnl_pct <= 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
