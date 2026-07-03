# Indodax Trading Bot — Arsitektur

```mermaid
flowchart TB
    subgraph Runner["🔄 Main Loop (Bot.run)"]
        direction LR
        CYCLE["Bot.cycle()"] --> SLEEP["Sleep 300s"]
        SLEEP --> CYCLE
    end

    subgraph Cycle["⚙️ Satu Siklus (Bot.cycle())"]
        direction TB
        EXIT["1️⃣ Exit Check"] --> ENTRY["2️⃣ Entry Scan"]
    end

    subgraph ExitCheck["1️⃣ Exit Check"]
        EXIT_CHECK["Loop 5 pair"] --> FETCH_OHLCV_EXIT["Exchange.fetch_ohlcv()"]
        FETCH_OHLCV_EXIT --> INDICATORS_EXIT["Indicators.compute()"]
        INDICATORS_EXIT --> EXIT_MGR["ExitManager.check()"]
        EXIT_MGR --> TP{"TP ≥ 2×5%?"}
        EXIT_MGR --> SL{"SL ≤ -5%?"}
        EXIT_MGR --> TRAIL{"Trailing Stop\nATR × 2?"}
        EXIT_MGR --> BREAK{"Breakeven\n≥ 1.5%?"}
        EXIT_MGR --> TIME{"Time Stop\n≥ 24 jam?"}
        TP --> CLOSE["Close → record_trade()"]
        SL --> CLOSE
        TRAIL --> CLOSE
        BREAK --> UPDATE_SL["Update SL ke entry"]
        TIME --> CLOSE
        CLOSE --> ADAPT["AdaptiveEngine.feed_trade()"]
    end

    subgraph EntryScan["2️⃣ Entry Scan"]
        ENTRY_SCAN["Loop 5 pair"] --> CAN_TRADE{"RiskManager\ncan_trade()?"}
        CAN_TRADE -->|"⛔ Blokir"| BLOCK["Cooldown / Daily Limit\n/ Drawdown / Loss Streak"]
        CAN_TRADE -->|"✅ Ok"| FETCH_OHLCV["Exchange.fetch_ohlcv()"]
        FETCH_OHLCV --> INDICATORS["Indicators.compute()"]
        INDICATORS --> REGIME["AdaptiveEngine\n.detect_regime()"]
        INDICATORS --> PHANTOM["PhantomDetector\n.analyze()"]
        INDICATORS --> SIGNAL["Indicators\n.signal_score()"]
        REGIME --> THRESHOLD["Dynamic Threshold\n= 0.50 × regime_mult"]
        PHANTOM --> PENALTY["Phantom Penalty\n× (max 50%)"]
        SIGNAL --> COMPARE{"Score ≥\nThreshold?"}
        COMPARE -->|"hold"| SKIP
        COMPARE -->|"enter"| SIZE["RiskManager\n.position_size()\nHalf-Kelly × DD × Regime"]
        SIZE --> PAPER{"Paper Mode?"}
        PAPER -->|"Ya"| DB_ENTRY["TradeStore.add_trade()\n→ trades.db"]
        PAPER -->|"Tidak"| LIVE_ORDER["Exchange.market_buy()\n→ limit order"]
    end

    subgraph Storage["💾 Storage Layer"]
        DB[(trades.db)]
        DB --> TRADES["trades\n(open/closed)"]
        DB --> DAILY["daily_pnl\n(loss limit)"]
    end

    subgraph Services["🧠 Service Components"]
        SENTIMENT["Sentiment\nalternative.me\nFear & Greed API"]
        EXCHANGE["Exchange\nCCXT Indodax\nOHLCV + Orders + Balance"]
    end

    subgraph IndicatorsDetail["📊 Indicator Engine (Indicators.compute())"]
        direction LR
        EMA["EMA 9/20/50"]
        SMA["SMA 20/50"]
        RSI["RSI 14"]
        BB["Bollinger Bands\nBB 20,2"]
        MACD["MACD"]
        ATR["ATR 14"]
        ADX["ADX 14\nDMP / DMN"]
        STOCH["Stochastic\n%K / %D"]
        VOL["Volume SMA\nVolume Ratio\nOBV"]
    end

    subgraph RiskLayer["🛡️ Risk Layer"]
        HALF_KELLY["Half-Kelly Sizing\n(based on win rate)"]
        DD_MULT["Drawdown Multiplier\n<5%→1× / >15%→0.25×"]
        REGIME_SIZE["Regime Sizing\nTrend→0.9 / Choppy→0.4"]
        MAX_POS["Max 3 Positions"]
        COOLDOWN["Global Cooldown 30m"]
        DAILY_LIMIT["Daily Loss Limit\nRp100.000"]
        LOSS_STREAK["Loss Streak Pause\n3 losses → 2h pause"]
        DRAWDOWN["Drawdown Circuit\n10% → stop all"]
    end

    subgraph Adaptive["🧬 Adaptive Engine"]
        REGIME_DETECT["Regime Detection\nADX-based"]
        ADAPT_W["Adaptive Weights\nPer-signal win rate update"]
        REGIME_TH["Regime Threshold Mult\nTrend→0.85 / Ranging→1.05"]
    end

    subgraph Phantom["👻 Phantom Detector"]
        WASH["Wash Trade\nVol spike + flat price"]
        PUMP_DUMP["Pump & Dump\nRise >3% then fall <-2%"]
        DOJI["Doji Manipulation\nBody/wick < 8%"]
        SPREAD["Spread Anomaly\n> 3× mean"]
        BULL["Consecutive Bullish\n10 candlesticks hijau"]
    end

    SENTIMENT --> SIGNAL
    EXCHANGE --> FETCH_OHLCV
    EXCHANGE --> FETCH_OHLCV_EXIT
    IndicatorsDetail --> INDICATORS
    IndicatorsDetail --> INDICATORS_EXIT
    STORAGE --> DB
    RiskLayer --> SIZE
    Adaptive --> REGIME
    Adaptive --> THRESHOLD
    Phantom --> PHANTOM
```

## Alur Program

```
┌─────────────────────────────────────────────────────┐
│                  Bot.run()                          │
│   Loop selamanya → Bot.cycle() → sleep 300s        │
└───────────────────┬─────────────────────────────────┘
                    │
    ┌───────────────┴───────────────┐
    │         Bot.cycle()           │
    │                               │
    │  1️⃣ Scan 5 pair untuk EXIT    │
    │    └ ExitManager.check()      │
    │      → TP / SL / Trailing     │
    │        / Breakeven / Time Stop│
    │      → Close trade → feed     │
    │        ke AdaptiveEngine      │
    │                               │
    │  2️⃣ RiskManager.can_trade()   │
    │      → Cooldown / Drawdown    │
    │        / Daily Limit / dll    │
    │                               │
    │  3️⃣ Scan 5 pair untuk ENTRY   │
    │      → fetch OHLCV            │
    │      → compute indicators     │
    │      → detect regime          │
    │      → phantom check          │
    │      → signal_score()         │
    │      → if score ≥ threshold:  │
    │        position_size() → entry│
    └───────────────────────────────┘
```

## Komponen Scoring

```
Score =  trend    × 25%
       + momentum  × 20%
       + mean_rev  × 20%
       + volume    × 15%
       + sentiment × 15%
       + stochastic ×  5%
       ─────────────────
       Total (max 1.0)

       Dikali phantom_penalty (max -50%)
       Lalu dibandingkan dengan dynamic_threshold
```

## Alur Exit

```
Setiap cycle → untuk setiap pair open:
  1. TP?  (pnl ≥ 2 × 5% = +10%)    → CLOSE
  2. SL?  (pnl ≤ -5%)               → CLOSE
  3. Trailing? (pnl > 0, price - 2×ATR < entry) → CLOSE
  4. Breakeven? (pnl ≥ 1.5%)         → UPDATE SL ke entry
  5. Time Stop? (≥ 24 jam)           → CLOSE
```

## Alur Entry

```
Setiap cycle → untuk setiap pair (max 3 positions):
  1. can_trade() check
  2. fetch OHLCV 1h (100 candles)
  3. compute() → EMA/SMA/RSI/BB/MACD/ATR/ADX/Stoch/Volume
  4. detect_regime() → ADX-based
  5. analyze_phantom() → 5 anomaly detektor
  6. signal_score() → weighted confluence
  7. Score ≥ dynamic_threshold?
     → position_size() via Half-Kelly × DD × Regime
     → Paper: simpan ke DB
     → Live: limit order via CCXT
```
