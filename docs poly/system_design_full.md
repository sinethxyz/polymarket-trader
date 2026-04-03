# Polymarket Trading System: Architecture & Strategy Design

## 1. STRATEGY THESIS

### Target Inefficiencies

Polymarket is structurally inefficient for identifiable, exploitable reasons:

1. **Retail-dominated flow**: Most participants are crypto-native gamblers, not calibrated forecasters. They overweight narratives, recency, and salience.
2. **Fragmented liquidity**: Thin books on most markets mean prices reflect the last marginal participant, not informed consensus.
3. **No institutional short-selling pressure**: Unlike equity markets, there's no dedicated short-side capital enforcing efficiency. Overpriced YES contracts persist.
4. **Multi-outcome mispricing**: Markets with N>2 outcomes routinely have implied probabilities summing to ≠1.0 (after fees), creating structural arb.
5. **Calendar/event-time disconnect**: Markets price in continuous time but resolve on discrete event triggers. The gap between "time to resolution" and "information arrival rate" creates edge.
6. **Cross-market inconsistency**: Correlated markets (e.g., "Will X win nomination?" vs "Will X win general?") frequently violate logical constraints.
7. **Sentiment contagion**: Polymarket prices move on social media virality with predictable mean-reversion patterns.
8. **Late-stage convergence failure**: Markets approaching resolution with near-certain outcomes often trade at 94-97¢ instead of 99¢, creating low-risk carry.

### Alpha Hypotheses (Ranked)

| # | Hypothesis | Robustness | Impl. Complexity | Decay Speed |
|---|-----------|------------|-------------------|-------------|
| 1 | **Multi-outcome arbitrage**: Implied probs sum > 1.0 across linked markets; capture spread by selling overpriced legs | HIGH | LOW | SLOW — structural |
| 2 | **Cross-market logical constraint violations**: P(A∩B) > P(A) violations across correlated markets | HIGH | MEDIUM | SLOW — structural |
| 3 | **Late-stage convergence carry**: Buy YES at 94-97¢ on near-certain outcomes within 48h of resolution | HIGH | LOW | SLOW — behavioral |
| 4 | **Sentiment mean-reversion**: Large price moves driven by Twitter/Reddit volume revert within 4-24 hours when not accompanied by fundamental information | MEDIUM-HIGH | MEDIUM | MEDIUM — adapts as market matures |
| 5 | **Time-decay theta harvesting**: Sell uncertainty premium on long-dated markets where implied vol exceeds realized vol | MEDIUM | HIGH | MEDIUM |
| 6 | **Informed flow detection**: Track wallet clusters that historically precede correct resolution; piggyback within latency window | MEDIUM | HIGH | FAST — adversarial |
| 7 | **Anchoring exploitation**: New markets anchor to round numbers (50¢, 25¢, 75¢); true priors from base-rate models diverge | MEDIUM | MEDIUM | MEDIUM |
| 8 | **Event-schedule front-running**: Predictable information releases (polls, earnings, votes) create pre-event drift patterns | MEDIUM-LOW | MEDIUM | FAST |
| 9 | **Liquidity provider edge**: Provide two-sided quotes in illiquid markets, earning spread while maintaining directional neutrality | MEDIUM | HIGH | SLOW — structural |
| 10 | **Resolution ambiguity trading**: Markets with unclear resolution criteria trade at discounts; resolving the ambiguity before the crowd creates edge | LOW-MEDIUM | HIGH | VARIES |

**Priority stack for V1**: Hypotheses 1, 2, 3, 4 — all have structural or behavioral roots, moderate implementation cost, and slow decay.

---

## 2. MARKET TAXONOMY

### Category Breakdown

| Category | Example Markets | Liquidity Profile | Info Asymmetry | Best Strategy Family |
|----------|----------------|-------------------|----------------|---------------------|
| **US Politics** | Presidential election, Senate races | DEEP on majors, thin on state-level | LOW (polls are public) | Cross-market arb, sentiment mean-reversion, poll-model divergence |
| **Crypto/DeFi** | ETH ETF approval, BTC price brackets | MEDIUM-DEEP | MEDIUM (insider-adjacent) | Time-decay, informed flow detection, event front-running |
| **Macro/Econ** | Fed rate decisions, CPI brackets | MEDIUM | LOW (data is public) | Base-rate models, event-schedule front-running, late-stage carry |
| **Sports** | Game outcomes, player props | THIN-MEDIUM | HIGH (injury info, weather) | Avoid unless you have proprietary sports models |
| **Culture/Entertainment** | Oscar winners, streaming numbers | VERY THIN | MEDIUM | Late-stage carry only; too thin for systematic trading |
| **Long-dated Events** | "Will X happen by 2027?" | THIN | LOW | Theta harvesting, but illiquidity kills execution |
| **Geopolitical** | Conflict outcomes, treaties | THIN-MEDIUM | HIGH (OSINT edge) | Specialist signal only; avoid systematic approaches |

### Where Spread and Liquidity Matter Most

**High-liquidity markets (US politics, major crypto)**: Spread is tight (1-3¢). Edge must come from superior probability estimation or cross-market relationships. Execution quality matters less; signal quality matters more.

**Low-liquidity markets (culture, long-dated, niche)**: Spread is wide (5-15¢). Edge is often just being willing to provide liquidity. But: you become the market, which means adverse selection risk is extreme. Only enter with strong directional conviction AND willingness to hold to resolution.

**Critical insight**: The optimal strategy is NOT the same across categories. A system that treats "Will Biden win?" the same as "Will Taylor Swift release an album by June?" will lose money on one or both.

---

## 3. SIGNAL STACK

### Layer 1: Market-Derived Signals

#### 1a. Multi-Outcome Implied Probability Sum

**Intuition**: When a set of mutually exclusive outcomes has implied probabilities summing to significantly more (or less) than 1.0, at least one leg is mispriced.

**Formula**:
```
overround = Σ(mid_price_i) - 1.0    for i in all outcomes
mispricing_score_j = (mid_price_j / Σ(mid_price_i)) - mid_price_j
```

Where `mispricing_score_j > 0` means outcome j is overpriced relative to fair share.

**Input data**: Real-time mid prices for all outcomes in a market group.

**Failure modes**: (a) Prices may reflect informed views, not mispricing — the "overpriced" leg might be correctly priced while others are underpriced. (b) Bid-ask spread eats the arb. (c) Correlated resolution: all legs resolve simultaneously, so you can't exit one at a time.

**Tradability**: Only actionable when `overround > total_spread_cost + fee`. On Polymarket, typical fee is 0 on CLOB but there's a 2% fee on winnings for some market types. Require overround > 5¢ to be interesting after costs.

#### 1b. Cross-Market Logical Constraint Signal

**Intuition**: If market A is "Will X win the primary?" at 60¢ and market B is "Will X win the general?" at 40¢, then the implied P(win general | win primary) = 0.40/0.60 = 67%. If a separate market implies this conditional differently, there's an arb.

**Formula**:
```
implied_conditional = P(B) / P(A)     when B ⊂ A
violation = |implied_conditional - independent_estimate_of_P(B|A)|
```

**Input data**: Prices from logically related markets, a mapping of logical relationships (subset, superset, mutual exclusion, conditional).

**Failure modes**: (a) Logical relationships may be subtly wrong (different resolution criteria). (b) Resolution timing differs. (c) Liquidity on one leg may be much thinner.

**Tradability**: HIGH when both markets have >$50K open interest. Build the relationship graph manually for top-20 market clusters.

#### 1c. Price-Level Clustering / Round-Number Anchoring

**Intuition**: New markets disproportionately anchor at 25¢, 33¢, 50¢, 67¢, 75¢. If a calibrated model assigns 38% probability and the market sits at 33¢, there may be 5¢ of anchoring edge.

**Formula**:
```
anchor_score = min(|price - round_level|) for round_level in [0.10, 0.20, ..., 0.90]
signal = model_prob - market_price  (when anchor_score < 0.03)
```

**Input data**: Current price, time-since-market-creation, model probability estimate.

**Failure modes**: False positives — sometimes 33¢ IS the right price. Requires calibrated model to distinguish.

**Tradability**: MEDIUM. Only useful when you have an independent probability estimate. Signal decays as markets mature.

---

### Layer 2: Order Book / Price-Action Signals

#### 2a. Book Imbalance

**Intuition**: Persistent bid-heavy books precede upward price moves; persistent ask-heavy books precede downward moves. On Polymarket's CLOB, this is directly observable.

**Formula**:
```
imbalance = (bid_depth_3_levels - ask_depth_3_levels) / (bid_depth_3_levels + ask_depth_3_levels)
smoothed_imbalance = EMA(imbalance, halflife=30min)
signal = smoothed_imbalance when |smoothed_imbalance| > 0.3
```

**Input data**: Level-2 order book snapshots, polled or streamed via Polymarket API / WebSocket.

**Failure modes**: (a) Spoofing — large resting orders pulled before fill. (b) Thin books amplify noise. (c) Stale quotes from inactive LPs.

**Tradability**: LOW-MEDIUM. Useful as confirmation signal, not primary. Never trade book imbalance alone on thin markets.

#### 2b. Trade Flow Toxicity (VPIN Analog)

**Intuition**: Periods of high "toxic" flow (informed traders aggressively taking liquidity) precede large directional moves. Adapted from equity microstructure.

**Formula**:
```
# Bucket trades into volume-time bars of size V
# Classify each trade as buy or sell (tick rule or order-side if available)
buy_volume_i = Σ(trade_size) for buys in bucket i
sell_volume_i = Σ(trade_size) for sells in bucket i
VPIN = Σ(|buy_volume_i - sell_volume_i|) / (n * V)   over last n buckets
```

**Input data**: Trade-level data with timestamps and sizes. Ideally, order-side labels from the CLOB.

**Failure modes**: (a) Low trade count makes VPIN noisy. (b) Volume-time bucketing is sensitive to bucket size V. (c) On Polymarket, many trades are small retail → low signal-to-noise.

**Tradability**: LOW on most markets. Only viable on top-10 most liquid markets by volume.

---

### Layer 3: Time-to-Resolution Signals

#### 3a. Resolution Imminence Premium

**Intuition**: As resolution approaches, uncertainty should collapse. If it doesn't, there's either unresolved information OR stale pricing. Markets trading at 85¢ with 2 hours to a near-certain resolution should be at 97¢+.

**Formula**:
```
expected_price_at_T = model_prob * (1 - time_discount_factor)
time_discount_factor = exp(-lambda * hours_to_resolution)
resolution_premium = market_price - expected_price_at_T
signal = resolution_premium when hours_to_resolution < 48 and |model_prob - 0.5| > 0.35
```

**Input data**: Market price, estimated resolution time, model probability, historical convergence curves for similar market types.

**Failure modes**: (a) Resolution time is uncertain (e.g., "by end of month" could resolve any day). (b) "Near-certain" may not be — tail events happen. (c) Opportunity cost of capital locked until resolution.

**Tradability**: HIGH. This is the bread-and-butter of Hypothesis #3 (late-stage carry). Best on markets with hard resolution timestamps.

#### 3b. Information Calendar Front-Running

**Intuition**: Scheduled information releases (debate dates, CPI releases, earnings, vote counts) create predictable volatility windows. Prices drift in the hours before and snap after.

**Formula**:
```
event_proximity = hours_until_next_info_release
pre_event_drift = price_change over [-24h, -1h] before past events of same type
signal = direction_of_historical_drift when event_proximity < 24h
confidence = sqrt(n_historical_events) * abs(mean_drift) / std_drift
```

**Input data**: Event calendar (manual + scraped), historical price data around past events of the same type.

**Failure modes**: (a) Small sample sizes for event types. (b) Each event is somewhat unique. (c) Front-running drift may already be priced in on major events.

**Tradability**: MEDIUM. Useful for timing entries, not as standalone alpha.

---

### Layer 4: External Information Signals

#### 4a. Polling Aggregate Divergence

**Intuition**: When Polymarket price diverges from polling aggregates (538-style models, RCP averages, etc.) by more than historical norms, one of them is wrong. Polls have known biases but are usually closer to truth than prediction market prices during calm periods.

**Formula**:
```
divergence = market_price - polling_aggregate_prob
z_divergence = divergence / historical_std(divergence, same_market_type, same_time_horizon)
signal = -divergence when |z_divergence| > 2.0 and time_to_resolution > 7 days
```

**Input data**: Polling aggregates (scrape 538, RCP, Economist, etc.), historical divergence distribution.

**Failure modes**: (a) Polls can be systematically wrong (2016, 2020). (b) Polymarket might be more informed than polls (insider info, faster update). (c) Divergence can persist and widen before correcting.

**Tradability**: MEDIUM-HIGH for political markets with deep liquidity. Requires careful calibration of which direction to fade.

#### 4b. Social Media Velocity

**Intuition**: Spikes in Twitter/Reddit mention volume for a market topic, unaccompanied by fundamental news, predict short-term overreaction followed by mean reversion.

**Formula**:
```
mention_velocity = (mentions_last_1h - EMA_mentions_24h) / max(EMA_mentions_24h, 1)
news_filter = 1 if major_news_detected else 0
signal = -sign(price_change_last_2h) when mention_velocity > 3.0 and news_filter == 0
```

**Input data**: Twitter/X API or scraper, Reddit API, news API for filtering genuine news from noise.

**Failure modes**: (a) News filter is imperfect — sometimes the spike IS the news. (b) Latency: by the time you detect the spike, the move may be done. (c) Sentiment analysis is noisy.

**Tradability**: MEDIUM. Best as a mean-reversion trigger on high-liquidity political markets.

---

### Layer 5: Crowd Behavior / Wallet Signals

#### 5a. Wallet Cluster Tracking

**Intuition**: On-chain, you can identify wallets that historically resolve on the correct side. If a cluster of "smart money" wallets takes a position, it's signal.

**Formula**:
```
wallet_score_w = Σ(correct_resolution_i * size_i) / Σ(size_i)   over wallet w's history
smart_money_flow = Σ(wallet_score_w * position_delta_w)   for all wallets with score > 0.6
signal = sign(smart_money_flow) when |smart_money_flow| > threshold
```

**Input data**: On-chain transaction data for Polymarket's contracts (Polygon), historical resolution data, wallet-level P&L reconstruction.

**Failure modes**: (a) Smart wallets may change strategy or degrade. (b) On-chain tracking is public — if you can see it, so can everyone. (c) Wallets can be Sybilled. (d) Latency from on-chain detection to execution.

**Tradability**: MEDIUM. Edge decays as more people track the same wallets. Best used as confirmation, not primary.

---

### Layer 6: Confidence / Uncertainty Estimation

#### 6a. Model Confidence Envelope

**Intuition**: Every signal should carry an uncertainty estimate. A signal that says "fair value is 62¢" is useless without "±8¢ at 90% confidence."

**Formula**:
```
ensemble_estimate = weighted_mean(signal_estimates)
ensemble_std = sqrt(weighted_variance(signal_estimates) + model_uncertainty_prior)
confidence_interval = [ensemble_estimate - 1.65*ensemble_std, ensemble_estimate + 1.65*ensemble_std]
tradable = (market_price < CI_lower) or (market_price > CI_upper)
```

**Input data**: All signal outputs with their individual uncertainty estimates.

**Failure modes**: (a) Underestimated model uncertainty (the ensemble is overconfident). (b) Correlation between signals inflates false confidence. (c) Fat tails not captured by Gaussian CI.

**Tradability**: META-SIGNAL. This determines whether to trade at all, not which direction.

---

## 4. EXECUTION ENGINE

### Polymarket-Specific Execution Considerations

Polymarket uses a CLOB (Central Limit Order Book) on Polygon via the CTF Exchange contract. Key constraints:

- Orders are placed via signed EIP-712 messages to the Polymarket API
- Fills are atomic on-chain
- No partial fills on some order types
- Minimum order sizes apply
- Gas costs are negligible (Polygon) but API rate limits exist
- Order book depth is publicly visible
- There is NO maker/taker fee split on the primary CLOB (but check current fee schedule)

### Entry Logic

```
ENTRY_DECISION(signal, market_state, risk_state):
    # Gate 1: Signal strength
    if abs(signal.edge) < MIN_EDGE_THRESHOLD:    # typically 3-5¢
        return NO_TRADE
    
    # Gate 2: Liquidity check
    available_depth = get_depth_at_price(market, signal.direction, max_slippage=0.02)
    if available_depth < MIN_DEPTH:               # typically $500
        return NO_TRADE
    
    # Gate 3: Risk budget
    if risk_manager.would_breach(market, signal.size):
        return NO_TRADE
    
    # Gate 4: Event proximity
    if market.hours_to_resolution < EVENT_LOCKOUT_HOURS:
        if signal.type != "late_stage_carry":
            return NO_TRADE
    
    # Gate 5: Stale quote check
    if market.last_trade_time > STALE_THRESHOLD:  # e.g., 2 hours
        reduce_size_by(0.5)
    
    # Determine order type
    if signal.urgency == HIGH:
        return AGGRESSIVE_LIMIT(price=best_ask + 0.01, size=position_size)
    else:
        return PASSIVE_LIMIT(price=signal.target_entry, size=position_size)
```

### Exit Logic

```
EXIT_DECISION(position, market_state, signal_state):
    # Priority 1: Hard stop
    if position.unrealized_pnl < -position.max_loss:
        return AGGRESSIVE_EXIT("stop_loss")
    
    # Priority 2: Signal invalidation
    if signal_state.current_edge * sign(position.direction) < 0:
        return PASSIVE_EXIT("signal_flip")
    
    # Priority 3: Target reached
    if position.unrealized_pnl > position.target_profit:
        return SCALE_OUT(fraction=0.5, type="take_profit")
    
    # Priority 4: Time decay
    if market.hours_to_resolution < FORCE_EXIT_HOURS and position.type != "carry":
        return AGGRESSIVE_EXIT("time_expiry")
    
    # Priority 5: Liquidity deterioration
    if market.bid_depth < CRITICAL_DEPTH and position.direction == LONG:
        return PASSIVE_EXIT("liquidity_drain")
    
    # Default: hold
    return HOLD
```

### Scaling In/Out

- **Never enter full size at once**. Split into 3 tranches: 40% / 30% / 30%.
- **First tranche**: at signal trigger.
- **Second tranche**: on confirmation (price doesn't immediately revert, or additional signal fires).
- **Third tranche**: on favorable price improvement (limit order 1-2¢ better than first fill).
- **Scale out**: mirror the entry — exit 50% at first target, 30% at second, hold 20% for full resolution carry.

### Resting Limits vs. Aggressive Fills

| Condition | Order Type | Rationale |
|-----------|-----------|-----------|
| Signal urgency HIGH, depth available | Aggressive limit (cross spread) | News-driven; passive orders will be jumped |
| Signal urgency LOW, wide spread | Passive limit at mid or better | Earn spread; signal has long half-life |
| Thin book, position exit | Iceberg / split across time | Avoid moving the market against yourself |
| Late-stage carry | Aggressive limit | Time is the enemy; pay the spread |

### Slippage Controls

```python
MAX_SLIPPAGE_CENTS = 2  # Refuse fills worse than signal_price + 2¢
MAX_POSITION_AS_PCT_OF_DEPTH = 0.25  # Never be >25% of visible depth
MAX_SINGLE_ORDER_SIZE_USD = 5000  # Hard cap per atomic order
```

### Stale Quote Avoidance

A resting order becomes a liability if the market moves and your quote is stale:

```python
STALE_ORDER_POLICY:
    - Cancel and replace any resting order where:
        (a) price has moved > 2¢ from order price, OR
        (b) order has been resting > 30 minutes without fill, OR
        (c) new signal invalidates the trade thesis
    - Heartbeat check every 60 seconds on all open orders
    - If API is unreachable for > 120 seconds, cancel ALL resting orders
```

### Event-Time Shutdown Rules

```
EVENT_LOCKOUT_PROTOCOL:
    - 1 hour before known resolution: cancel all resting orders except carry positions
    - During resolution window: NO new orders
    - Post-resolution: wait for on-chain confirmation before acknowledging settlement
    - If resolution is disputed: freeze all related positions, alert operator
```

### Kill Switches

```python
KILL_SWITCH_TRIGGERS = [
    "portfolio_drawdown > 10% in 24h",
    "single_market_loss > $2000",
    "API_errors > 5 in 60 seconds",
    "unexpected_fill_price (> 5¢ from expected)",
    "operator_manual_trigger",
    "blockchain_congestion (gas > 500 gwei)",  # shouldn't happen on Polygon but check
    "system_clock_drift > 5 seconds",
]

KILL_SWITCH_ACTION:
    1. Cancel ALL resting orders immediately
    2. Log state snapshot
    3. Alert operator via Telegram/SMS
    4. Disable new order submission
    5. Require manual re-enable with human approval
```

---

## 5. RISK FRAMEWORK

### Per-Trade Risk Caps

```
max_loss_per_trade = max(
    $200,
    min($1000, 2% * portfolio_value)
)
position_size = max_loss_per_trade / (entry_price - stop_price)
```

### Per-Market Caps

```
max_exposure_per_market = min($5000, 5% * portfolio_value)
max_positions_per_market = 1 (directional) or 2 (if hedged across outcomes)
```

### Per-Theme / Correlation Caps

```
THEME_GROUPS = {
    "us_politics_2026": [market_ids...],
    "crypto_etf": [market_ids...],
    "fed_rates": [market_ids...],
}
max_exposure_per_theme = min($15000, 15% * portfolio_value)
```

**Correlation tracking**: Compute rolling 7-day pairwise correlation of daily price changes across all held positions. If any cluster exceeds correlation > 0.7 with aggregate exposure > 10% of portfolio, force-reduce the smaller position.

### Drawdown Controls

| Drawdown Level | Action |
|---------------|--------|
| 5% from peak | Reduce new position sizes by 50% |
| 10% from peak | Cancel all resting orders, no new trades for 24h |
| 15% from peak | Liquidate all positions to cash, full system pause |
| 20% from peak | Require full strategy review before restart |

### Liquidity-Adjusted Sizing

```python
def liquidity_adjusted_size(raw_size, market):
    depth_5pct = market.depth_within_cents(5)  # $ available within 5¢ of mid
    max_from_liquidity = depth_5pct * 0.25     # never be >25% of near depth
    return min(raw_size, max_from_liquidity)
```

### Volatility-Adjusted Sizing (Kelly-Inspired)

```python
def kelly_fraction(edge, odds, uncertainty_multiplier=0.25):
    """
    Half-Kelly with additional uncertainty penalty.
    edge: estimated edge in probability (e.g., 0.05 for 5¢)
    odds: price paid (e.g., 0.60 means you pay 60¢ to win $1)
    """
    win_payout = (1 - odds) / odds  # e.g., (1-0.60)/0.60 = 0.667
    kelly = (edge * (win_payout + 1) - (1 - edge)) / win_payout
    return max(0, kelly * uncertainty_multiplier)  # quarter-Kelly
```

### Market Closure / Resolution Risk

- **Binary event risk**: Any position held through resolution has binary P&L. Size accordingly — resolution positions should use 50% of normal sizing.
- **Ambiguous resolution**: Flag any market where resolution criteria are subjective. Apply 30% size haircut.
- **Multi-market resolution**: If multiple positions resolve on the same event, treat the aggregate as a single bet for sizing purposes.

### Black Swan Protocols

```
SCENARIO                              ACTION
----------------------------------------------------------------------
Platform outage (Polymarket down)     All orders assumed cancelled. Positions held.
                                      No action possible. Alert operator.

Blockchain fork / reorg               Freeze all activity. Verify positions on canonical chain.

Regulatory action against Polymarket  Immediate full exit of all positions if possible.
                                      If platform frozen, wait for resolution.

Oracle manipulation                   Flag any resolution that contradicts multiple
                                      independent sources. Do not claim winnings
                                      until verified. Alert operator.

Flash crash (price drops >20¢ in      Check for fat-finger. If systematic, buy the
1 minute on no news)                  crash with small size. Hard stop 10¢ below entry.
```

### Paper Trading Gating Criteria

**No live capital deployed until ALL of the following are met:**

1. Paper trading for ≥30 days with realistic fill simulation
2. ≥50 simulated trades completed
3. Positive expected value after simulated slippage and fees
4. No kill-switch trigger events in last 14 days of paper trading
5. Manual review of top-10 winning AND losing trades by operator
6. Backtest results match paper trading results within 20% on key metrics
7. Explicit human sign-off documented in audit log

---

## 6. RESEARCH AND BACKTESTING

### Required Datasets

| Dataset | Source | Granularity | Purpose |
|---------|--------|-------------|---------|
| Historical market prices | Polymarket API / archive | 1-minute OHLCV | Backtest price signals |
| Order book snapshots | Polymarket WebSocket archive | 5-second snapshots | Backtest execution |
| Trade-level data | Polymarket API | Per-trade | Flow toxicity, wallet analysis |
| Resolution outcomes | Polymarket API | Per-market | Labels for supervised models |
| On-chain transactions | Polygon RPC / Dune | Per-block | Wallet tracking |
| Polling data | 538, RCP, Economist | Daily | Political signal |
| Social media volume | Twitter/X API, Reddit API | Hourly | Sentiment signal |
| News events | News API, GDELT | Per-article | News filter, event calendar |
| Economic calendar | FRED, BLS | Scheduled releases | Event timing signal |

### Feature Engineering

**Raw features → Derived features → Signal features → Trading features**

```
Raw:            price, volume, bid_depth, ask_depth, timestamp
Derived:        returns, spread, imbalance, VPIN, mention_velocity
Signal:         z_divergence, resolution_premium, cross_mkt_violation
Trading:        edge_estimate, confidence_interval, sizing_recommendation
```

**Critical**: All feature engineering must be strictly causal. No future data leakage. Every feature at time T must use only data available at T-1 or earlier.

### Labeling

```python
def label_trade(entry_time, entry_price, direction, market_resolution, exit_time):
    """
    Label 1: Resolution-based (was the trade correct at resolution?)
    Label 2: Mark-to-market at T+24h (did price move favorably?)
    Label 3: Best exit PnL (what was the max favorable excursion?)
    """
    resolution_pnl = (resolution_price - entry_price) * direction
    mtm_24h_pnl = (price_at_24h - entry_price) * direction
    max_favorable = max_price_excursion(entry_time, exit_time, direction) - entry_price
    return resolution_pnl, mtm_24h_pnl, max_favorable
```

**Use resolution-based labeling for carry/arb strategies. Use MTM-24h for mean-reversion. Never optimize on max-favorable excursion — that's hindsight bias.**

### Train / Validation / Test Split

```
DO NOT use random splits. Use temporal splits only.

Timeline:  [---- Train ----|---- Validation ----|---- Test ----]
           [  60% of data  |    20% of data     |  20% of data ]

Walk-forward: Retrain every 30 days. Validate on next 30 days. Test on final 30 days.

CRITICAL: Markets are heterogeneous. A model trained on political markets
          should NOT be validated on crypto markets. Split by category too.
```

### Walk-Forward Testing

```python
def walk_forward_backtest(data, train_window=90, val_window=30, step=30):
    results = []
    for t in range(train_window, len(data) - val_window, step):
        train = data[t - train_window : t]
        val = data[t : t + val_window]
        
        model = train_model(train)
        signals = model.predict(val)
        trades = simulate_execution(signals, val, slippage_model)
        metrics = compute_metrics(trades)
        results.append(metrics)
    
    return aggregate_walk_forward_results(results)
```

### Simulation of Realistic Fills

```python
class FillSimulator:
    def simulate_fill(self, order, book_snapshot, latency_ms=500):
        """
        Simulate realistic fill accounting for:
        1. Latency: book may have changed
        2. Queue position: passive orders fill after existing queue
        3. Partial fills: may not get full size
        4. Price impact: large orders walk the book
        """
        adjusted_book = self.age_book(book_snapshot, latency_ms)
        
        if order.type == AGGRESSIVE:
            fill_price = self.walk_book(adjusted_book, order.size, order.side)
            fill_size = min(order.size, adjusted_book.available_at(order.limit_price))
            slippage = abs(fill_price - order.limit_price)
        
        elif order.type == PASSIVE:
            # Probability of fill depends on queue position and price movement
            fill_prob = self.estimate_fill_probability(
                order.price, adjusted_book, holding_period=order.max_wait
            )
            fill_size = order.size if random() < fill_prob else 0
            fill_price = order.price
            slippage = 0
        
        return Fill(price=fill_price, size=fill_size, slippage=slippage)
```

### Slippage Assumptions

| Market Liquidity Tier | Assumed Slippage (aggressive) | Assumed Slippage (passive) |
|----------------------|-------------------------------|----------------------------|
| Tier 1 ($1M+ OI) | 0.5¢ | 0¢ (but 30% fill rate) |
| Tier 2 ($100K-$1M OI) | 1.5¢ | 0¢ (but 15% fill rate) |
| Tier 3 (<$100K OI) | 3-5¢ | 0¢ (but 5% fill rate) |

### Metrics That Matter

| Metric | Formula | Why It Matters |
|--------|---------|---------------|
| **Edge per trade (after costs)** | mean(pnl_per_trade - slippage - fees) | The only metric that determines profitability |
| **Sharpe ratio (daily)** | mean(daily_returns) / std(daily_returns) * sqrt(365) | Risk-adjusted return |
| **Win rate × avg_win / avg_loss** | Self-explanatory | Separates "right often" from "right big" |
| **Max drawdown** | max(peak - trough) | Survival metric |
| **Capacity** | max AUM before edge degrades >50% | Scalability |
| **Profit factor** | gross_profit / gross_loss | Must be >1.3 to be interesting |
| **Trade count** | N trades in test period | Statistical significance check |

### Misleading Metrics to Reject

| Metric | Why It's Misleading |
|--------|-------------------|
| **Accuracy / hit rate alone** | A 90% hit rate at 1¢ edge with 10% losing 20¢ is -11¢ EV |
| **Backtest P&L without slippage** | Fantasy returns. Useless. |
| **Sharpe on resolved-only trades** | Ignores the opportunity cost and risk of holding |
| **In-sample R² of signal** | Overfitting guaranteed. Only out-of-sample matters. |
| **Max profit on any single trade** | Survivorship bias. Cherry-picking. |
| **"Average edge" across all signals** | Mixing high-N low-edge with low-N high-edge signals obscures reality |

---

## 7. SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MONITORING & ALERTING                        │
│  Grafana dashboards, PagerDuty alerts, Telegram bot notifications   │
└─────────────┬───────────────────────────────────┬───────────────────┘
              │                                   │
┌─────────────▼───────────┐   ┌──────────────────▼───────────────────┐
│    ANALYTICS DASHBOARD   │   │          EXPERIMENT TRACKER          │
│  Trade journal, P&L,     │   │  MLflow / custom: signal versions,  │
│  signal attribution,     │   │  backtest runs, parameter sweeps    │
│  execution quality       │   │                                     │
└─────────────┬───────────┘   └──────────────────┬───────────────────┘
              │                                   │
┌─────────────▼───────────────────────────────────▼───────────────────┐
│                          AUDIT LOG                                   │
│  Every signal, decision, order, fill, cancellation — immutable log   │
└─────────────────────────────────────────────────────────────────────┘

              ┌─────────────────────────────────┐
              │        DATA INGESTION LAYER      │
              │                                  │
              │  Polymarket API Poller (REST)     │
              │  Polymarket WebSocket (L2 book)   │
              │  Polygon RPC (on-chain txns)      │
              │  External APIs (polls, news,      │
              │    social, econ calendar)          │
              └───────────────┬─────────────────┘
                              │
              ┌───────────────▼─────────────────┐
              │       MARKET STATE STORE          │
              │                                  │
              │  Redis: real-time prices, books   │
              │  Postgres: historical data,       │
              │    market metadata, resolutions   │
              │  Market taxonomy + relationship   │
              │    graph                          │
              └───────────────┬─────────────────┘
                              │
              ┌───────────────▼─────────────────┐
              │         SIGNAL ENGINE             │
              │                                  │
              │  Signal modules (pluggable):      │
              │    ├─ CrossMarketArb              │
              │    ├─ MultiOutcomeArb             │
              │    ├─ LateStageCarry              │
              │    ├─ SentimentReversion          │
              │    ├─ PollDivergence              │
              │    └─ BookImbalance               │
              │                                  │
              │  Ensemble combiner + confidence   │
              └───────────────┬─────────────────┘
                              │
              ┌───────────────▼─────────────────┐
              │        STRATEGY ENGINE            │
              │                                  │
              │  Signal → Trade decision          │
              │  Entry/exit logic                 │
              │  Order type selection             │
              │  Scaling logic                    │
              └───────────────┬─────────────────┘
                              │
              ┌───────────────▼─────────────────┐
              │     PORTFOLIO / RISK MANAGER      │
              │                                  │
              │  Position tracking                │
              │  Exposure calculations            │
              │  Correlation monitoring           │
              │  Drawdown tracking                │
              │  Kill switch logic                │
              │  Sizing (Kelly + liquidity adj)   │
              └───────────────┬─────────────────┘
                              │
              ┌───────────────▼─────────────────┐
              │       EXECUTION ROUTER            │
              │                                  │
              │  Order management                 │
              │  Polymarket CLOB interface         │
              │  Fill tracking                    │
              │  Stale order cancellation          │
              │  Slippage monitoring              │
              │  Paper trade / live trade switch   │
              └─────────────────────────────────┘
```

### Component Communication

```
Data Ingestion → Market State Store:     async message queue (Redis Streams)
Market State Store → Signal Engine:      event-driven (price update triggers signal recalc)
Signal Engine → Strategy Engine:         direct function call (same process)
Strategy Engine → Risk Manager:          synchronous check (must pass before order)
Risk Manager → Execution Router:         approved order objects
Execution Router → Polymarket API:       async HTTP with retry logic
All components → Audit Log:              async append to Postgres + file log
```

### Key Design Decisions

1. **Signal engine is stateless**: Takes market state snapshot, returns signal vector. No internal state. Testable in isolation.
2. **Risk manager is the gatekeeper**: Every order MUST pass through risk manager. No bypass. No exceptions.
3. **Execution router handles all API interaction**: No other component talks to Polymarket directly.
4. **Paper/live is a configuration flag**: Same code path, different execution router backend.
5. **Audit log is append-only**: Write to Postgres + flat file simultaneously. No deletions.

---

## 8. BEST INITIAL MVP

### What to Build First (V1)

**The Late-Stage Carry Bot**: This is Hypothesis #3 — the simplest, most robust, lowest-complexity edge.

**V1 scope**:
- Monitor all active Polymarket markets
- Identify markets within 48 hours of resolution where outcome is >90% implied by external sources
- If market price is <95¢ for the likely outcome, buy
- Hold to resolution
- Hard-coded sizing: $200 per trade max
- Paper trade only

**Why this first**: No model training needed. No complex signals. Edge is behavioral (people don't bother buying 95¢ contracts for 5¢ upside). Implementation is simple REST API polling + basic decision logic.

### What to Ignore Initially

- Order book signals (complex, noisy on thin markets)
- Wallet tracking (requires expensive on-chain indexing)
- Social media sentiment (requires NLP pipeline)
- Complex execution (just use market orders on V1 — the edge is large enough to absorb spread)
- Multi-outcome arb (requires relationship graph — V2)
- Machine learning models (premature optimization)

### Where False Complexity Usually Appears

1. **Over-engineering the signal stack before validating one signal**. Don't build an ensemble of 10 signals that each have 0 validated edge.
2. **Building a dashboard before building the trading logic**. Dashboards don't make money.
3. **Optimizing execution on markets where you have no signal**. Execution alpha is second-order.
4. **Building ML models before establishing base rates**. Simple heuristics beat undertrained models.
5. **Abstracting too early**. Write the specific code for Strategy #1 first. Refactor into generic interfaces after Strategy #2.

### Roadmap

| Week | Milestone | Deliverable |
|------|-----------|-------------|
| **1-2** | Data foundation + Late-Stage Carry V1 | Market data poller, market state DB, carry signal detector, paper trade logger |
| **3-4** | Execution + Multi-Outcome Arb V1 | Polymarket order API integration, basic risk manager, multi-outcome arb detector, paper trading both strategies |
| **5-6** | Cross-Market Arb + Signal Ensemble | Logical relationship graph for top-50 markets, cross-market signal, confidence estimator, combined paper trading |
| **7-8** | Backtesting + Live Readiness | Historical backtest harness, walk-forward validation, fill simulator, live deployment checklist, human review of paper results |

---

## 9. CODE PLAN

### Folder Structure

```
polymarket-trader/
├── config/
│   ├── settings.yaml              # All configuration
│   ├── market_taxonomy.yaml       # Market categories + relationships
│   └── secrets.env                # API keys (gitignored)
├── src/
│   ├── data/
│   │   ├── __init__.py
│   │   ├── polymarket_client.py   # REST + WebSocket client
│   │   ├── market_store.py        # Redis + Postgres interface
│   │   ├── external_data.py       # Polls, news, social APIs
│   │   └── schemas.py             # Pydantic models for all data types
│   ├── signals/
│   │   ├── __init__.py
│   │   ├── base.py                # Abstract signal interface
│   │   ├── late_stage_carry.py
│   │   ├── multi_outcome_arb.py
│   │   ├── cross_market_arb.py
│   │   ├── sentiment_reversion.py
│   │   ├── poll_divergence.py
│   │   ├── book_imbalance.py
│   │   └── ensemble.py            # Signal combiner + confidence
│   ├── strategy/
│   │   ├── __init__.py
│   │   ├── base.py                # Abstract strategy interface
│   │   ├── entry_exit.py          # Entry/exit decision logic
│   │   └── order_type.py          # Order type selection
│   ├── risk/
│   │   ├── __init__.py
│   │   ├── position_manager.py    # Track open positions
│   │   ├── risk_manager.py        # All risk checks
│   │   ├── sizing.py              # Kelly + liquidity sizing
│   │   └── kill_switch.py         # Emergency shutdown
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── order_manager.py       # Order lifecycle
│   │   ├── polymarket_executor.py # Live execution
│   │   ├── paper_executor.py      # Paper trade simulation
│   │   └── fill_tracker.py        # Track fills + slippage
│   ├── backtest/
│   │   ├── __init__.py
│   │   ├── engine.py              # Walk-forward backtest engine
│   │   ├── fill_simulator.py      # Realistic fill simulation
│   │   ├── metrics.py             # Performance metrics
│   │   └── report.py              # Generate backtest reports
│   ├── monitoring/
│   │   ├── __init__.py
│   │   ├── audit_log.py           # Immutable logging
│   │   ├── alerts.py              # Telegram/SMS alerts
│   │   └── dashboard.py           # Metrics export for Grafana
│   └── main.py                    # Entry point + async event loop
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── notebooks/
│   ├── signal_exploration.ipynb
│   └── backtest_analysis.ipynb
├── scripts/
│   ├── bootstrap_db.py
│   ├── backfill_history.py
│   └── run_backtest.py
├── docker-compose.yaml
├── Dockerfile
├── requirements.txt
└── README.md
```

### Key Schemas (Pydantic)

```python
from pydantic import BaseModel
from enum import Enum
from datetime import datetime
from typing import Optional

class MarketCategory(str, Enum):
    POLITICS = "politics"
    CRYPTO = "crypto"
    MACRO = "macro"
    SPORTS = "sports"
    CULTURE = "culture"
    LONG_DATED = "long_dated"

class MarketState(BaseModel):
    market_id: str
    question: str
    category: MarketCategory
    outcomes: list[str]
    prices: dict[str, float]        # outcome_name -> mid_price
    spreads: dict[str, float]       # outcome_name -> bid_ask_spread
    volumes_24h: dict[str, float]
    open_interest: float
    resolution_time: Optional[datetime]
    last_trade_time: datetime
    book_snapshot: Optional[dict]    # top 5 levels each side

class Signal(BaseModel):
    signal_id: str
    signal_type: str
    market_id: str
    direction: int                   # +1 = buy YES, -1 = buy NO
    outcome: str
    edge_estimate: float             # in cents
    confidence: float                # 0-1
    urgency: str                     # "high", "medium", "low"
    timestamp: datetime
    metadata: dict                   # signal-specific details

class OrderRequest(BaseModel):
    market_id: str
    outcome: str
    side: str                        # "buy" or "sell"
    price: float
    size_usd: float
    order_type: str                  # "limit", "aggressive_limit"
    time_in_force: str               # "GTC", "IOC", "GTD"
    signal_id: str                   # traceability
    max_slippage: float

class Position(BaseModel):
    position_id: str
    market_id: str
    outcome: str
    direction: int
    entry_price: float
    current_price: float
    size_usd: float
    unrealized_pnl: float
    entry_time: datetime
    signal_id: str
    stop_loss: float
    take_profit: float
```

### Abstract Interfaces

```python
# signals/base.py
from abc import ABC, abstractmethod

class BaseSignal(ABC):
    @abstractmethod
    def compute(self, market_state: MarketState, context: dict) -> Optional[Signal]:
        """
        Given current market state and any additional context,
        return a Signal if one exists, or None.
        Must be stateless and deterministic given inputs.
        """
        pass
    
    @abstractmethod
    def required_data(self) -> list[str]:
        """List of data keys this signal needs in context dict."""
        pass
    
    @abstractmethod
    def backtest_compatible(self) -> bool:
        """Whether this signal can be honestly backtested."""
        pass
```

```python
# risk/risk_manager.py
class RiskManager:
    def check_order(self, order: OrderRequest, portfolio: Portfolio) -> RiskDecision:
        """
        Returns APPROVE, REDUCE, or REJECT with reason.
        Checks: per-trade, per-market, per-theme, drawdown, liquidity.
        """
        checks = [
            self._check_per_trade_limit(order),
            self._check_per_market_limit(order, portfolio),
            self._check_theme_correlation(order, portfolio),
            self._check_drawdown(portfolio),
            self._check_liquidity(order),
        ]
        
        for check in checks:
            if check.status == "REJECT":
                return check
        
        worst_reduction = min(c.allowed_fraction for c in checks)
        if worst_reduction < 1.0:
            return RiskDecision("REDUCE", fraction=worst_reduction)
        
        return RiskDecision("APPROVE")
```

```python
# execution/order_manager.py
class OrderManager:
    def __init__(self, executor: BaseExecutor, risk_manager: RiskManager):
        self.executor = executor  # PolymarketExecutor or PaperExecutor
        self.risk_manager = risk_manager
        self.open_orders: dict[str, Order] = {}
    
    async def submit_order(self, request: OrderRequest) -> OrderResult:
        decision = self.risk_manager.check_order(request, self.portfolio)
        if decision.status == "REJECT":
            self.audit_log.log("ORDER_REJECTED", request, decision)
            return OrderResult(status="rejected", reason=decision.reason)
        
        if decision.status == "REDUCE":
            request.size_usd *= decision.fraction
        
        result = await self.executor.place_order(request)
        self.audit_log.log("ORDER_SUBMITTED", request, result)
        return result
    
    async def heartbeat(self):
        """Called every 60 seconds. Cancel stale orders."""
        for order_id, order in self.open_orders.items():
            if self._is_stale(order):
                await self.executor.cancel_order(order_id)
                self.audit_log.log("ORDER_CANCELLED_STALE", order)
```

### Suggested Libraries

```
# requirements.txt
aiohttp>=3.9           # async HTTP for Polymarket API
websockets>=12.0       # WebSocket for order book streaming
redis>=5.0             # real-time state store
asyncpg>=0.29          # async Postgres
sqlalchemy>=2.0        # ORM for historical data
pydantic>=2.5          # data validation
numpy>=1.26
pandas>=2.1
scipy>=1.12            # statistical functions
scikit-learn>=1.4      # basic ML (optional, V2+)
click>=8.1             # CLI
pyyaml>=6.0            # config
python-telegram-bot>=20 # alerts
prometheus-client>=0.20 # metrics export
structlog>=23.2        # structured logging
pytest>=8.0
pytest-asyncio>=0.23
httpx>=0.27            # testing HTTP mocks
```

### Async Data Flow

```python
# main.py
import asyncio

async def main():
    # Initialize components
    config = load_config("config/settings.yaml")
    store = MarketStore(config.redis_url, config.postgres_url)
    signal_engine = SignalEngine([
        LateStageCarry(),
        MultiOutcomeArb(),
        CrossMarketArb(),
    ])
    risk_manager = RiskManager(config.risk)
    executor = PaperExecutor() if config.paper_mode else PolymarketExecutor(config.api)
    order_manager = OrderManager(executor, risk_manager)
    
    # Launch concurrent tasks
    await asyncio.gather(
        poll_markets(store, interval=30),          # Fetch prices every 30s
        stream_orderbook(store),                    # WebSocket L2 data
        run_signal_loop(store, signal_engine, order_manager, interval=60),
        run_heartbeat(order_manager, interval=60),
        run_monitoring(store, order_manager),
    )

async def run_signal_loop(store, signal_engine, order_manager, interval):
    while True:
        markets = await store.get_active_markets()
        for market in markets:
            state = await store.get_market_state(market.market_id)
            signals = signal_engine.compute_all(state)
            for signal in signals:
                if signal and signal.edge_estimate > MIN_EDGE:
                    order = strategy.signal_to_order(signal, state)
                    await order_manager.submit_order(order)
        await asyncio.sleep(interval)
```

### Backtest Harness Design

```python
# backtest/engine.py
class BacktestEngine:
    def __init__(self, signal_modules, fill_simulator, risk_config):
        self.signals = signal_modules
        self.fill_sim = fill_simulator
        self.risk = RiskManager(risk_config)
    
    def run_walk_forward(self, data, train_days=90, test_days=30, step_days=30):
        results = []
        dates = sorted(data.keys())
        
        for i in range(train_days, len(dates) - test_days, step_days):
            train_end = dates[i]
            test_start = dates[i]
            test_end = dates[i + test_days]
            
            # Calibrate signals on train period
            for sig in self.signals:
                sig.calibrate(data, end_date=train_end)
            
            # Simulate on test period
            portfolio = SimulatedPortfolio()
            for day in dates[i:i+test_days]:
                for market_id, state in data[day].items():
                    for sig in self.signals:
                        signal = sig.compute(state, context={})
                        if signal and signal.edge_estimate > MIN_EDGE:
                            order = signal_to_order(signal, state)
                            risk_decision = self.risk.check_order(order, portfolio)
                            if risk_decision.status != "REJECT":
                                fill = self.fill_sim.simulate_fill(
                                    order, state.book_snapshot
                                )
                                if fill.size > 0:
                                    portfolio.add_position(fill)
                
                # Mark to market
                portfolio.mark_to_market(data[day])
            
            results.append(compute_metrics(portfolio))
        
        return WalkForwardReport(results)
```

---

## 10. OUTPUT FORMAT

### Final Recommended Strategy Stack

**Deploy in this order:**

1. **Late-Stage Carry** — Simplest, most robust, proven behavioral edge. Requires only price polling + external source checks.
2. **Multi-Outcome Arbitrage** — Structural, non-decaying. Requires enumerating outcome sets and computing implied probability sums.
3. **Cross-Market Logical Constraint** — Structural. Requires manual mapping of market relationships (start with top 20 market clusters).
4. **Sentiment Mean-Reversion** — Behavioral. Requires social media data pipeline. Deploy after V1 strategies are validated.

### Ranked Build Order

1. Polymarket API client (REST + auth)
2. Market state database (Postgres schema + Redis cache)
3. Late-Stage Carry signal module
4. Paper trade executor
5. Audit log
6. Risk manager (basic: per-trade + per-market caps)
7. Multi-Outcome Arb signal module
8. Kill switch
9. Backtest engine
10. Cross-Market Arb signal module
11. Alerting (Telegram)
12. Execution router (live mode)
13. Monitoring dashboard

### Top 5 Ways This Project Could Fail

| # | Failure Mode | Why It Happens | How to Prevent |
|---|-------------|----------------|----------------|
| 1 | **Overfitting signals to historical data** | Backtests look amazing; live trading loses money. Too many parameters, too little data. | Walk-forward only. Prefer simple heuristics over trained models. Require ≥50 out-of-sample trades before trusting a signal. |
| 2 | **Ignoring execution costs** | Edge looks like 5¢ in the model but slippage eats 4¢. Thin books + aggressive entries = no profit. | Simulate fills with realistic slippage from Day 1. Never assume you get the mid price. |
| 3 | **Correlated blowup** | All positions are secretly the same bet. "Diversified" portfolio of 10 political markets all resolve the same way. | Enforce theme-level exposure caps. Compute rolling correlation matrix. Stress-test: "What if the unlikely thing happens?" |
| 4 | **Platform risk** | Polymarket changes API, changes fees, gets regulated, goes down during a critical resolution window. | Never deploy more than 20% of total capital. Have withdrawal plan. Monitor regulatory news. |
| 5 | **Premature complexity** | Building ML pipelines, NLP sentiment engines, and on-chain indexers before validating that any single signal has real edge. | Follow the roadmap. V1 is Late-Stage Carry with $200 max per trade. Prove it works. Then add complexity. |

### Top 5 Ways to Make It Genuinely Profitable

| # | Path to Profit | Why It Works |
|---|---------------|-------------|
| 1 | **Nail execution on the carry trade and compound** | Late-stage carry has 3-7% return per trade with <48h holding period. At 5 trades/week, that's meaningful annualized return on deployed capital. Low drawdown. Consistent. |
| 2 | **Build the cross-market relationship graph better than anyone else** | Most participants look at one market. If you systematically map P(A), P(B), P(A∩B) across 100+ market pairs and enforce logical constraints, you'll find 1-2 arbs per week that nobody else catches. |
| 3 | **Be the market maker in medium-liquidity markets** | If you can reliably estimate fair value within ±3¢, you can quote 5¢ wide in $100K-$500K OI markets and earn the spread while staying directionally neutral. Requires good risk mgmt but scales. |
| 4 | **Use Polymarket as a hedge/complement to external positions** | If you have views from other sources (prediction model, fundamental research), Polymarket is a cheap, uncorrelated way to express them. The real alpha is your external model; Polymarket is just the venue. |
| 5 | **Specialize ruthlessly** | Don't trade all categories. Pick the one where you have genuine informational or analytical edge (e.g., US politics if you're a polisci quant, crypto if you're a DeFi native). Depth of expertise in one category beats breadth across all. |
