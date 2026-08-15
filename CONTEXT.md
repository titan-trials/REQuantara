# Quantara — Project Context Document
---

## What Quantara Is
A Python-based quantitative trading strategy simulator built from scratch.
Started with one stock, one indicator, one rule. Now runs autonomous
multi-strategy, multi-stock analysis with ML signal generation, live paper
trading via GitHub Actions, real order execution via Alpaca paper trading,
a full performance analytics layer, and a narrated event feed explaining
what actually happened to the money and why.

---

## Current State (as of Aug 14, 2026)
- Versions 1-17 complete.
- 🔴 **HEADLINE FINDING: the strategies do not beat buy and hold.** Tested across
  33 sector-diverse tickers with honest out-of-sample selection, no strategy beat
  holding on more than 7 of 33. Five of six have a negative mean Sharpe. See
  Version 17 — this is the project's conclusion, not a bug to be fixed.
- 🔴 **Buy & hold beats every ML strategy on every ticker.** Auto-selection now
  picks Buy & Hold for NVDA, TSLA, AAPL and IBM. Only JPM keeps an active
  strategy (SMA Crossover). See Version 16.
- **Live strategies (Aug 14 2026, V15 engine): NVDA -> EMA Crossover, TSLA -> Logistic Regression, AAPL -> EMA Crossover, JPM -> SMA Crossover, IBM -> Logistic Regression.**
- **⚠️ ALL BACKTEST NUMBERS PREDATING VERSION 13 ARE VOID.** Three separate Version 13
  changes moved every backtest figure: position size 0.50 → 1.0 in the backtest,
  fractional shares replacing whole-share flooring, and a stop loss that actually
  removes exposure. Any Sharpe / return / drawdown / composite score recorded in this
  document before Aug 14 2026 is **not comparable** to anything produced after it.
  Sections below that are affected are marked ⚠️ STALE.
- **Live strategy assignment changed by the Version 13 re-run** (pending next scheduled
  run): NVDA Random Forest → **EMA Crossover**, TSLA Logistic Regression → **SMA
  Crossover**. AAPL (LR), JPM (SMA Crossover), IBM (Bollinger Bands) unchanged. These
  are score changes driven by the sizing fix, not new research findings.
- **Account: ~$12,010 equity, +20.10% since Apr 29 inception.**
- **Benchmark: equal-weight buy & hold of the same 5 tickers returned +4.48% over the
  same period. Quantara is ahead by +15.62 points** (~+6 pts after adjusting for the
  leverage that ran until Aug 14). First real evidence of edge beyond market tracking.
- Live strategies (changed Jun 29, 2026): NVDA → Random Forest, TSLA → Logistic
  Regression, AAPL → Logistic Regression, JPM → SMA Crossover, IBM → Bollinger Bands.
- Stop loss confirmed working across three live triggers (NVDA Jun 24, TSLA Jul 21,
  AAPL Aug 3). Correct on gradual declines, overshoots on overnight gaps — structural,
  not fixable at the threshold level.
- **ML features: 18.** Original 14 + Mom_accel + ADX_14 + RSI_x_trend + Ret_vol_norm.
  Streak, Streak_Squared, BBpos_x_trend all tested and removed.
- Dashboard: 6 tabs + live Alpaca portfolio row refreshing every 60s.

### ✅ RESOLVED — the POSITION_SIZE warning (Aug 14, 2026)
The old warning here asked whether `POSITION_SIZE` was 0.20, 0.50, or 0.02. The answer
turned out to be that **the question was malformed**: one constant was serving two
incompatible purposes. Resolved in Version 13 by splitting it into
`BACKTEST_POSITION_SIZE` and `LIVE_POSITION_SIZE`. See Version 13 below.

---

## Version 11 — Live Readiness Audit (COMPLETE)

### Finding 1 — ~1.91x leverage discovered and fixed
`POSITION_SIZE = 0.50` means 50% of *total portfolio value* per position. Four
positions open = ~200% exposure, funded by Alpaca margin:

Account equity: $12,010.34
Total position market value: $22,907.63
Implied margin debt: $10,897.29
Effective leverage: 1.91x

The negative "Cash" figure on the Alpaca dashboard — earlier dismissed as a display
quirk and relabelled "Buying Power" — was margin debt. Roughly half the +20.10% return
was leverage amplification; delevered equivalent ~+10.5%.

Sizing rationale: the "2% rule" is **risk per trade, not position size**.
`position size = risk% ÷ stop distance%`. With a 5% nominal stop (≈9% in gap
scenarios), 2% risk implies a 20-22% position. Five tickers × 20% = 100%, no margin.

### Finding 2 — Rejected orders logged as successful (fixed)
TSLA's Jul 22 re-entry (14.4659 sh) was **rejected by Alpaca** — insufficient buying
power under 50% sizing. `execute_signal()` only checked `submit_order()`'s return, not
the order's subsequent status, so the CSV logged `SIGNAL` and `build_trade_segments()`
opened a phantom position at $378.93. Dashboard showed TSLA -13.57%; Alpaca showed
+9.2% from a real $311.49 entry opened Jul 27.

Fixes: `submit_and_verify()` in `alpaca_executor.py` polls order status ~10s after
submission. `reconcile_open_segments()` in `evaluation/performance.py` takes entry
price and P&L from live Alpaca positions for any OPEN segment, dropping segments
Alpaca isn't holding.

**Related:** the CSV logs the yfinance *close* at signal time; Alpaca fills at the
*next open*. TSLA's stop signal was $369.57, actual fill $376.06. All dashboard P&L
figures are approximations.

### Finding 3 — Stop loss correctly characterised
An earlier claim that the stop "always fires 3-4 points late" was **wrong** — it
measured against CSV closes instead of Alpaca's real `avg_entry_price`. Corrected:

TSLA (real entry $392.31): Jul 20 -2.92% → Jul 21 -5.80% TRIGGER ✓ correct
AAPL (real entry $340.08): Jul 31 -1.96% → Aug 03 -9.17% TRIGGER ✗ weekend gap

Works on gradual declines, cannot work on gaps — you trigger on a close and fill at the
next open, so the gap always lands in that window.

**4% threshold evaluated and rejected.** Simulated on real Apr–Aug prices: 4% beat 5%
by 0.92 pts across five tickers (noise). Replaying AAPL's gap, both thresholds trigger
on the same day — identical outcome. Of 155 occasions a holding sat in the -4% to -5%
band, 49% recovered next close, 51% fell further. **Position sizing is the only
effective gap defense** — AAPL's -9.17% gap cost -4.6% of equity at 50% sizing, -1.8%
at 20%.

### Evaluated and deliberately NOT adopted
- **Resting stop orders** (`StopOrderRequest`/brackets). Would give true intraday stops
  independent of the scheduler, but Alpaca doesn't support them on **fractional
  shares**. Whole-share sizing sets an account floor — at 20% and JPM near $365 you'd
  need ~$1,825 to buy one share of the priciest name. Planned live account is
  $100–$1,000, so fractional is non-negotiable. Also adds lifecycle management (cancel
  before manual sells, filter resting stops from `get_pending_orders`, partial fills,
  static stops that don't trail). Revisit if the account grows substantially.
- **VPS migration** (Kamatera box + DuckDNS provisioned). Enables intraday polling but
  does **not** solve gaps. Recommended split if pursued: keep the daily signal run on
  GitHub Actions; move the dashboard to the VPS first (lets the repo go private, zero
  trading risk); Quantara NN next; intraday monitoring last. Main risk: a VPS cron dies
  silently where Actions shows a red X. Uptime monitoring is a prerequisite.
- **Note:** GitHub Actions auto-disables scheduled workflows after 60 days of repo
  inactivity.

### System alerts now dated
`detect_problems()` returns `When` and `Detail` per flag, dated per check type:
switches are discrete dated events with history, drawdown breaches are dated by peak
plus days-since, accuracy shows its measurement range. Surfaced that IBM's drawdown
alert had fired continuously for 70+ days off a peak never actually held through.

---

## Version 12 — Momentum Round 2: Three Failures and One Success

Prompted by the Lis / Ślepaczuk / Sakowski paper, *"Overreaction as an indicator for
momentum in algorithmic trading: A Case of AAPL stocks"* (arXiv 2602.18912, Feb 2026).
Paper caveats worth remembering: Table 2 contradicts the body text on 10-min and 15-min
Sharpe values; trade counts are mislabelled between text and Figure 3; several headline
Sharpes rest on 0-2 trades; buy-and-hold is implausibly negative (-0.13) over the
sample. Not peer-reviewed. Its genuinely useful ideas were the volatility-scaled
threshold and the relabelled target.

### Attempt 1 — Interaction features (Path A)
Added `RSI_x_trend = (RSI - 50) × ADX_norm` and `BBpos_x_trend = (BB_position - 0.5) ×
ADX_norm`, plus `Ret_vol_norm = daily_return / Volatility_20` (Path C).

**The mechanism validated.** LR showed a unanimous sign flip on all five tickers —
`RSI` negative, `RSI_x_trend` positive. The model explicitly learned *"high RSI is
bearish normally, bullish once trend strength confirms it."* On TSLA and AAPL,
`RSI_x_trend` was the largest positive coefficient in the entire model.

**Performance didn't follow.** Clean 16-vs-19-feature comparison at POSITION_SIZE 0.50:

Ticker LR delta RF delta
NVDA -0.005 +0.428
TSLA -0.198 +0.079
AAPL -0.067 +0.106
JPM -0.093 +0.257
IBM -0.057 -0.297

LR worse on all five; RF better on four of five. Two of three live ML models are LR.
`BBpos_x_trend` had the **opposite** sign from `RSI_x_trend` everywhere while
`BB_position` was positive — collinear features fighting, the likely cause of LR's
uniform degradation. **`BBpos_x_trend` removed. `RSI_x_trend` and `Ret_vol_norm` kept.**

**Methodology note:** an earlier claim in this session that "Sharpe is scale-invariant"
to POSITION_SIZE was **wrong**. Same 19 features, same signals, only position size
differing: JPM RF moved +0.379, TSLA RF +0.115. Something in `run_backtest` — likely
the stop-loss path — doesn't scale linearly. Always compare at identical POSITION_SIZE.

### Attempt 2 — Volatility-scaled 3-class target (Path D)
Replaced binary next-day direction with the paper's target:
`+1 if r(t+1) > θσ(t) + 2TC`, `-1 if below negative of that`, `0 otherwise`.
Tested standalone in `test_or_target.py`, θ ∈ {1.0, 1.5, 2.0} × confidence ∈ {0.4, 0.5,
0.6}.

**RF results were void** — a calibration problem, not a failure. RF averages across 100
trees, so for a rare class `P(+1)` rarely exceeds 0.4. Nearly every cell produced zero
trades and `nan`. Would need thresholds ~0.15-0.25 or an argmax rule.

**LR results were a clean negative.** Averaged across all nine configs:

Ticker base avg new avg delta configs better
NVDA 0.928 0.276 -0.652 0/9
TSLA 1.111 0.530 -0.581 0/9
AAPL 1.091 0.387 -0.704 0/9
JPM 0.118 0.519 +0.401 8/9
IBM 0.496 0.415 -0.081 5/9

TSLA worse in all nine. JPM improved consistently — but by flipping in and out every
~2 days (55 round trips), and `run_backtest` models **no transaction costs**. TSLA at
the same settings held ~25 days per position and still lost ground. Rejected.

Consistent with the paper's own finding that the effect peaks at 10-min bars and fades
by 15 — no reason to expect it at daily frequency.

### Attempt 3 — The momentum override (SUCCESS)
**The reframing, and it came from Nolan:** the model is trained to be right *on average
across all days*. Momentum runs are rare. A model optimising average accuracy will
always trade away rare-event performance — that's what the loss function asks for. You
cannot train out of it. The bot "would have to break its own rules." So: don't retrain,
**override**.

Rule: when the model signals SELL while RSI is above a trigger AND the position is
profitable, suspend the sell and hold with a **trailing stop measured from the running
peak** (not from entry). Exit when price falls TRAIL% below the peak. Trailing from the
peak is what makes it work — without it this is just "hold and hope," which would have
been destroyed by TSLA's $445 top.

Tested 3 RSI triggers (65/70/75) × 3 trail widths (3/5/8%):

RANDOM FOREST configs better avg delta drawdown base -> worst
NVDA (LIVE on RF) 0/9 -0.215 -26.2% -> -31.3%
TSLA 9/9 +0.341 -31.1% -> -33.4%
AAPL 9/9 +0.330 -13.4% -> -15.6%
IBM 8/9 +0.080 -11.9% -> -12.9%
JPM 7/9 +0.048 -17.4% -> -19.4%

LOGISTIC REGRESSION configs better avg delta
TSLA (LIVE on LR) 3/9 +0.026
AAPL (LIVE on LR) 7/9 +0.044
JPM 8/9 +0.066
IBM 4/9 -0.023
NVDA 0/9 -0.095


**TSLA RF improved in 9 of 9 configurations, avg +0.341, with drawdown essentially
flat.** IBM RF 8/9. First intervention in four attempts to move both target tickers.
The consistency across every parameter combination is what distinguishes this from
prior single-cell false positives.

**Three caveats:**
1. **NVDA got worse on all 9, both models**, and drawdown widened. The override hurts
   where the model is already excellent (NVDA RF baseline 1.76). Should be applied
   per-ticker, not globally.
2. **The effect is RF-specific.** LR barely responds.
3. **Live-assignment mismatch.** The big wins are TSLA-on-RF and IBM-on-RF, but neither
   runs RF live. NVDA does — and it's the one the override hurts. Shipped as-is today,
   this would make NVDA worse and do little else.

**Not validated.** Single 50/50 split, run at POSITION_SIZE 0.50 on the 19-feature set
(before `BBpos_x_trend` was dropped). Needs walk-forward across the 2024/2023/2022/2021
window lengths, re-baselined on 18 features, before anything ships. Version 10's lesson
applies with full force: a convincing single-window result is exactly when to be most
suspicious.

**Standing research finding regardless of whether it ships:** *model override beats
model retraining for rare-event capture.* Four attempts to fix TSLA/IBM by giving the
model better information all failed — including one where the model demonstrably
learned the exact conditional we wanted. Changing what the model is allowed to do
worked where changing what it knows did not.

---

## Version 13 — Correctness Audit (COMPLETE)

Four structural bugs in the core accounting and selection layers, found by code review
rather than by a losing trade. None of them were visible in any result the system
produced — which is the point. Three of them silently corrupted every backtest number
this project has ever recorded.

### Fix 1 — `POSITION_SIZE` split into two constants

**The bug:** one constant served two incompatible definitions.

| | What reads it | What it means there |
|---|---|---|
| Backtest | `backtest/engine.py` | fraction of **one ticker's own private `INITIAL_CAPITAL`**, single-ticker sim, nothing competes for it |
| Live | `strategy/alpaca_executor.py` | fraction of **total account equity**, all 5 tickers drawing on the same pool |

At 0.50 the backtest was doing something harmless (half in, half idle). The *same*
0.50 live meant 5 × 50% = 250% gross exposure, funded by Alpaca margin — the 1.91x
leverage found in Version 11. **The two numbers were never the same quantity, and
sharing one variable meant neither could be set correctly without breaking the other.**

Now:
- `BACKTEST_POSITION_SIZE = 1.0` — when the strategy says be in the trade, be fully in.
  Anything lower parks that ticker's dedicated capital in cash modelling no real
  constraint, which drags returns down and muddies strategy comparison.
- `LIVE_POSITION_SIZE = 0.20` — 5 × 20% = 100% invested, no margin.

The old name `POSITION_SIZE` was **deleted** rather than aliased, so any code still
reaching for it fails immediately instead of silently picking the wrong number.

**Important consequence:** the ~2.5x jump in backtest returns (NVDA 191% → 496%) is
*not* improved strategy performance. It is the same strategies with twice the capital
per trade. Do not read it as an edge.

### Fix 2 — Fractional shares in `run_backtest`

`shares_to_buy = int(risk_amount / price)` floored to whole shares, making the
*effective* position size a function of the share price:

```
capital $10,000, position_size 0.20
  $20 stock  -> 100 shares  -> effective 0.200
  $200 stock ->  10 shares  -> effective 0.200
  $365 stock ->   5 shares  -> effective 0.182   <-- 9% short of target

capital $10,000, position_size 0.02
  $365 stock ->   0 shares  -> effective 0.000   <-- never trades at all
```

**This explains the Version 12 "Sharpe is not scale-invariant" anomaly.** JPM moved
+0.379 between position sizes and JPM is the priciest ticker in the book — highest
flooring error. It was never a stop-loss path issue as guessed at the time; it was
integer truncation. Live execution uses fractional shares via Alpaca, so this also
removed a genuine backtest/live mismatch. Now regression-tested: returns are invariant
to price level and scale exactly linearly with position size.

### Fix 3 — The backtest stop loss never removed exposure

Found by a synthetic-price unit test, not by reading the code. The engine sold on a
stop trigger and then **immediately re-bought on the same bar at the same close**,
because the strategy signal was still 1:

```
prices [100, 96, 94, 80], signal pinned at 1, stop 5%
  day 3: $94 < $95 -> STOP -> sell 100sh @ $94 -> instantly re-buy 100sh @ $94
  day 4: $80 < $89.30 -> STOP -> sell @ $80 -> instantly re-buy @ $80
```

The position stayed **fully invested the entire way down**. The stop's only effect was
to ratchet `entry_price` lower, which made the *next* stop trigger later. Every
backtested drawdown figure this project has ever produced was computed under a stop
loss that did essentially nothing.

Live behaviour was always different — `check_stop_loss()` force-sells and returns, so
the position is flat until at least the next scheduled run. The backtest now matches:
no re-entry on the bar the stop fired.

### Fix 4 — `auto_selector.py` silent-failure churn

**The suspected cause of AAPL's 15 one-day strategy flips (May–Jun 2026).** The
selector wrapped every candidate evaluation in a bare `except: continue` /
`except: pass`, and called `load_data()` separately inside every strategy branch —
**6 yfinance downloads per ticker, 30 per run, every day.**

A single transient download failure silently deleted a candidate from the field and
handed the win to whatever was left. The evidence fits: the scores are otherwise fully
deterministic (fixed 2015–2024 window, `random_state=42`), so identical inputs should
have produced identical winners daily. Instead AAPL flipped to RF for **exactly one
day** and straight back, seven separate times. IBM did the same.

Now:
- **2 downloads per ticker instead of 6.** Frames are loaded once and `.copy()`-ed per
  strategy (the build/signal functions mutate in place — sharing one frame would leak
  indicator and Signal columns between candidates).
- **No bare excepts.** Every failure logs ticker, strategy, exception type and traceback.
- **All-or-nothing selection.** If any candidate fails, the entire run is abandoned and
  the last known-good assignment is returned unchanged, from
  `results/strategy_assignments.json`. A data hiccup can no longer move money.
- **No fallback available → hard failure.** Refuses to trade rather than guess.
- **Near-tie warning.** Prints a NOTE when the winner beats second place by <0.05,
  because those selections are coin flips and coin flips are what cause churn.
  *(Notably: no near-ties fired on the Aug 14 re-run — all five winners had clear
  margins. Encouraging for the churn diagnosis.)*

`results/strategy_assignments.json` is written on every successful run and lives under
`results/`, which the GitHub Actions workflow already commits (`git add results/`) — so
the known-good state persists across Actions runs automatically.

### Test coverage added (first in the project)

`run_backtest` is the single function every result depends on and had **zero tests**.
That is how the flooring bug survived long enough to be misdiagnosed. Both suites are
network-free and use synthetic prices with hand-computed expected values, because real
market data has no known-correct answer to assert against.

- `test_engine_synthetic.py` — 18 assertions: buy & hold, stop-loss timing, signal
  exits, dust guard, plus explicit regression tests for price-level invariance,
  linear position-size scaling, and stop-loss exposure removal.
- `test_auto_selector_fallback.py` — 7 assertions: assignment persistence round-trip,
  fallback on simulated yfinance failure, hard-failure when no fallback exists, and
  confirmation that `evaluate_rule_based` raises rather than swallows.

**Both must pass before any result from this system is trusted again.**

### Prediction that was wrong, recorded deliberately
Going in, the expectation was that fixing the stop loss would make backtest drawdowns
*smaller*. They got **larger** (NVDA -36.77% → -50.25%). The stop fix does reduce
drawdown in isolation, but it was swamped by the sizing change: at
`BACKTEST_POSITION_SIZE = 1.0` each ticker is fully invested whenever it holds, so
per-ticker drawdowns are roughly double what they were at 0.50. Both effects are real;
sizing dominated. **Note these are per-ticker fully-invested drawdowns and are NOT
account drawdowns** — the live account holds 20% per ticker across five names.

---

## Version 14 — Measurement Layer + Override Correction (IN PROGRESS)

### The account measurement layer (`evaluation/account_log.py`) — BUILT, not yet run live

Every account figure this project has ever quoted — the +20.10%, the drawdowns, the
benchmark comparison — was **reconstructed** by replaying signal rows against yfinance
closes. That reconstruction is why 1.91x leverage went unnoticed for three months, why
a rejected order became a phantom position, and why `reconcile_open_segments()` had to
exist at all. yfinance closes are not what Alpaca filled at, and a signal log is not a
record of what happened to the money.

Three new CSVs, written from the Alpaca API on every run, after orders are submitted:

| File | Grain | Purpose |
|---|---|---|
| `results/equity_log.csv` | one row per run | equity, cash, buying power, **gross exposure, leverage, implied margin debt** |
| `results/positions_log.csv` | one row per open position per run | real `avg_entry_price`, market value, unrealized P&L, % of equity |
| `results/fills.csv` | one row per actual execution | order id, filled qty, **filled avg price**, notional — deduped by order id |

Design notes:
- **Leverage is computed and warned on every run** (`> 1.05x` prints a loud warning).
  This is the check that would have caught Version 11's leverage bug on day one.
- **Only genuine executions are written to fills.csv** — an order with zero filled
  quantity or no fill price is skipped. That is the Version 11 phantom-position bug
  encoded as a rule.
- **Fills look back 7 days and dedupe by order id**, so a missed run backfills instead
  of leaving a permanent hole. Three missed runs are already known (May 1, Jun 18,
  Aug 6 2026).
- **Nothing here can break trading.** Every entry point swallows its own exceptions and
  returns a status string; the call site in `paper_trader.py` is separately wrapped. It
  runs *after* all orders are submitted, so even a total failure is harmless.

Tested by `test_account_log.py` (22 assertions) against a fake Alpaca client, including
a reconstruction of the real Version 11 leverage scenario (equity $12,010.34, exposure
$22,907.63 → correctly detected as 1.91x with $10,897.29 margin debt).

**Once this has a few weeks of data it replaces reconstruction for: true live equity
curve, true live max drawdown, true live Sharpe, real slippage measurement (CSV signal
price vs actual fill price), and an automatic buy & hold benchmark.**

---

## Version 17 — The Verdict (COMPLETE) 🔴 THE STRATEGIES DO NOT WORK

**This is the most important section in this document. It is the conclusion the
whole project was built to be able to reach honestly.**

### The finding, stated plainly

**Quantara's trading strategies underperform simply buying and holding the same
stocks — badly, consistently, and across every test designed to give them a
fair chance.** This is not a tuning problem, a bug, or a bad sample. Six
strategies were tested on 33 stocks with proper out-of-sample discipline and
none of them worked.

### How the conclusion was reached (the chain of tests)

Each test was designed to eliminate one excuse for the previous result.

**Test 1 — the original five tickers (Version 16).** Buy & hold beat every ML
strategy on all five, on Sharpe as well as raw return. **Excuse:** the tickers
(NVDA, TSLA, AAPL, JPM, IBM) were chosen in 2026 knowing how 2015-2024 went,
and four were large-cap tech during a historic bull run. "You cannot beat
holding NVDA during the NVDA decade" is true of nearly everyone.

**Test 2 — five hindsight-free tickers.** THRM, LWAY, ECVT, PSA (plus NFLX as a
positive control). Active strategies "beat" holding on 3 of 4. **This looked
like vindication and was not.** Two flaws:
- The comparison took the BEST OF SEVEN strategies against ONE benchmark. With
  eight equally worthless candidates, the max of seven beats the single one
  **7/8 = 87.5%** of the time by construction. A "3 of 4" result is *below*
  what no skill predicts.
- The winner was chosen using the same period it was then scored on — pure
  look-ahead. Real deployment picks on history and finds out later.

**Test 3 — 33 tickers, honest selection.** Deliberately sector-diverse
(utilities, staples, REITs, telecom, energy, materials, healthcare,
industrials) and deliberately including known decliners (INTC, WBA, PARA, KHC,
MMM, T, VZ, BXP, LEG, F). Strategy picked on the FIRST half of each stock's
history, then scored on the SECOND half — exactly what `auto_selector` does
live.

```
1. HONEST      picked on train, scored on test    2/33 =  6%   baseline 50%
2. CHEATING    best chosen using test itself     16/33 = 48%   baseline 88%
3. PERSISTENCE train winner also won on test      6/33 = 18%   baseline 14%
4. DRAWDOWN    picked had shallower drawdown     14/33 = 42%
5. RETURN      mean picked +9.6%  vs  B&H +62.3%
```

(Note: 8 of the 33 had Buy & Hold picked on train, which then ties itself on
test and scores as a loss. Excluding those, the honest result is 2 of 25 = 8%.
It does not change anything.)

**Test 4 — the decisive one. No selection at all.** Apply each single strategy
uniformly to all 33 tickers and ask whether it beats holding. This removes the
selection problem entirely: if a strategy has real edge it should show up
broadly, not on cherry-picked names.

```
Strategy                beats B&H   mean Sharpe   mean return   mean DD
Logistic Regression       7/33          0.037         31.6%      -42.2%
Random Forest             7/33         -0.129          6.3%      -45.5%
EMA Crossover             6/33         -0.052         12.1%      -40.7%
SMA + RSI                 5/33         -0.148          5.0%      -39.3%
Bollinger Bands           3/33         -0.574         -4.3%      -19.6%
SMA Crossover             2/33         -0.104          7.6%      -42.3%
------------------------------------------------------------------------
BUY & HOLD                  --          0.214         62.3%      -49.2%
```

**Not one strategy beats holding on more than 7 of 33 tickers (21%).** Under a
50% no-skill baseline, all six are far below chance. **Five of six have a
NEGATIVE mean Sharpe.** Buy & hold's mean Sharpe is higher than every single
one of them.

### What each number means

**6% honest win rate against a 50% baseline** is not "no edge" — it is
*actively harmful*. Picking a strategy on history and deploying it did worse
than flipping a coin, by 44 points.

**48% cheating win rate against an 88% baseline** is the hardest number to
explain away. Even when allowed to see the answers and choose the best of seven
in hindsight, the strategies still lose to holding more than half the time. That
is not a selection failure — the strategies themselves are the problem.

**18% persistence against a 14% chance baseline** answers the central design
question of this entire project. Auto-selection rests on the premise that
different stocks have different character, so different strategies suit them. If
that premise held, a strategy chosen on old data would keep working on new data.
**It does not.** The winner on the first half of a stock's history is essentially
random with respect to the winner on the second half. Per-stock strategy fitting
was fitting to noise.

### A prediction that was recorded in advance and failed

Before the run, the stated expectation was: *"drawdown will favour the
strategies even if the return numbers do not, because sitting in cash
structurally reduces drawdown."*

**It did not.** 42% better, mean -47.1% vs -49.2%. Essentially nothing. The
reasoning missed that these strategies were frequently in cash during
*recoveries* and invested during *declines* — eating the drawdowns without the
rebounds.

The one genuine exception: **Bollinger Bands averaged -19.6% drawdown vs buy &
hold's -49.2%** — less than half. It also lost money (-4.3% mean return). So it
is a real risk-reduction property attached to a strategy with no return, which
is not useful on its own but is the only risk finding in the set that survived.

### Why this happens (the mechanism)

Daily-bar trend-following and mean-reversion rules on liquid US large-caps are
the most studied, most arbitraged setup in all of finance. Any edge was
competed away decades ago.

Meanwhile the strategies impose guaranteed costs:
- **Time out of the market forfeits the equity risk premium.** The market's
  upward drift is what generates return. Every day in cash gives some up.
- Transaction costs on every round trip.
- Execution lag — signal at the close, fill at the next open.

Unless the signal is genuinely better than random, being out of the market is
pure cost. Persistence at 14% says the signal is not better than random. The
`+9.6% vs +62.3%` return gap is that arithmetic: the strategies captured roughly
15% of the return that was available for the taking.

### ⚠️ WHAT THIS FINDING DOES *NOT* PROVE

Intellectual honesty cuts both ways, and a negative result has limits too:

- It does **not** prove no strategy can beat the market. It tests **six specific
  strategies** on daily bars.
- It does **not** test intraday frequencies, where microstructure differs and
  retail participation is thinner.
- It does **not** test **non-price signals** — fundamentals, sentiment, news,
  cross-sectional ranking, or anything outside OHLC.
- The basket is **better than the original five but still not unbiased**. It was
  written from memory, which means survivorship contamination. A true test needs
  point-in-time index membership including delisted names. (Notably, **K and WBA
  failed to download because they have genuinely been delisted** — Kellanova
  acquired, Walgreens taken private — so the basket did contain real casualties.)
- It covers **one regime**: roughly 2015-2026, a period dominated by a long bull
  market and one sharp COVID crash. Trend-following historically performs better
  in prolonged bear markets, which this window barely contains.
- The 50/50 train/test split is one methodology. Rolling-window or expanding
  walk-forward could give different results.

### Guardrails added as a result

`compute_composite_score` weights drawdown at only 0.3 while raw return is
**unbounded**. TSLA's buy & hold scored **3.7365** on a **-73.6% drawdown** and
won outright — the return term alone contributed 3.04. Recovering from -73.6%
requires **+279%**, and almost nobody holds through it. Sharpe does not capture
this either; it measures volatility, not survivability.

- **`MAX_ACCEPTABLE_DRAWDOWN = 0.40`** — a candidate whose backtested max
  drawdown is worse than this is ineligible for live selection regardless of
  score. If nothing clears the bar, the selector takes the **lowest-drawdown**
  candidate and prints `Consider not trading this ticker` rather than silently
  taking the top score.
- **`ALLOW_BUY_AND_HOLD_LIVE = False`** — Buy & Hold is scored every run as the
  benchmark, but is not tradeable. Live it has no stop loss by definition, and
  the assignment file had already selected it for NVDA, TSLA, AAPL and IBM,
  meaning the next scheduled run would have opened four unprotected positions
  on names with -66% and -74% backtested drawdowns.
- The selector now prints the vs-Buy-&-Hold gap for every ticker on every run.

### Follow-up — pairwise indicator combinations (also failed)

The natural response to Version 17 is "the indicators are fine, they just need
combining." Tested: 16 conditions → **120 pairwise combinations × 33 tickers =
3,960 backtests**, with tickers split into 17 discovery / 16 confirmation. The
confirmation half was not touched until the top 5 candidates were locked in.

```
DISCOVERY  best combo: sma_cross + rsi_not_hot       7/17
CONFIRMATION on held-back tickers:
  sma_cross + rsi_not_hot        7/17 -> 2/16    Sharpe -0.356 vs B&H
  ema_cross + rsi_not_hot        6/17 -> 2/16    Sharpe -0.296
  rsi_not_hot + bb_lower_half    6/17 -> 3/16    Sharpe -0.220
  mom5_positive + rsi_bullish    5/17 -> 1/16    Sharpe -0.434
  rsi_not_hot + adx_quiet        5/17 -> 1/16    Sharpe -0.490
```

**Nothing survived confirmation.** Every top-12 combination had a NEGATIVE mean
Sharpe even on discovery. Combining indicators does not fix a problem that was
never about the indicators.

**⚠️ METHODOLOGICAL CORRECTION — the null used was too generous.** The script
simulated a `Binomial(n, 0.5)` null, i.e. "a worthless combo beats buy & hold
half the time." That is wrong. A timing rule that sits in cash part of the time
does not face a coin flip, it faces the **equity risk premium**: random timing
*systematically* loses to holding in a rising market, so the true no-skill win
rate is well below 50%.

This means the reported "best scored 7/17 vs 13.6/17 by luck" **overstates how
anomalous the result is** — the combos may be at chance rather than below it. A
better null would simulate random signals with matched market exposure. The
confirmation collapse (1-3 of 16, all negative Sharpe) is decisive either way,
so this does not change the conclusion — but the 50% baseline should not be
quoted as-is in the final report.

### Follow-up — cross-sectional momentum (promising for one decade, then dead)

The third and final hypothesis. Unlike everything before it, this was NOT market
timing: rank the universe each month, hold the top slice, **always fully
invested**. That matters, because the failure mechanism of Versions 16-17 was
sitting in cash and forfeiting the equity risk premium. A ranking strategy never
does that.

**On 2016-2026 it looked genuinely good.** 33 tickers: 11.16% CAGR vs a 4.90%
equal-weight benchmark, beat all 1,000 random selections, +12.28% top-minus-
bottom spread. Expanded to 144 tickers: 80% of the parameter grid beat the
benchmark, survived 30bps costs, cleared size-matched random controls. Year by
year it won 7 of 11.

**Then it was tested from 2000 instead of 2015** — 26 years, 301 rebalances,
including the dot-com collapse, 2008, and 2009 (the worst momentum crash on
record). Nothing else changed.

```
                        CAGR      MaxDD    edge
momentum (6mo, top20%) 13.32%    -47.7%
equal-weight all       12.89%    -44.9%   +0.43%

BY PERIOD              momentum  benchmark   edge    years won
2000-2009               10.80%     11.17%   -0.36%     4/9
2010-2019               12.62%     14.49%   -1.87%     4/10
2020-2026               17.71%     12.71%   +5.01%     5/7

momentum beat the benchmark in 13 of 26 years — exactly a coin flip
parameter plateau collapsed from 80% to 35% of cells
did NOT clear the 95th percentile of size-matched random (13.32% vs 13.42%)
```

**The entire edge lives in 2020-2026.** Both earlier decades are negative. The
2016-2026 result was the decade, not the effect.

**On the crash years.** 2002 -5.7%, 2009 -12.2%, 2020 -2.5% — all survivable,
which initially reads as reassuring. It is not, for a technical reason: the
documented -50% momentum crashes are for **long-short** momentum. This
implementation is **long-only**, which underperforms during crashes rather than
collapsing. Passing that check was never a high bar.

**One honest observation, deliberately NOT acted on.** In the 26-year grid the
top 10% column beat the benchmark in 5 of 5 lookbacks, while every wider slice
mostly failed. That is the concentration pattern hypothesised earlier, appearing
in a fresh sample. It was **not** pursued, for a reason that matters more than
the observation: by this point the same price data had been searched through
six strategies, 120 indicator pairs, four ranking signals, and two parameter
grids. Finding one more configuration that works, after that much searching, is
what a false positive looks like. The correct response to "one cell survived
after hundreds of tests" is to stop, not to run test 601.

**Conclusion: all three hypotheses are now falsified.** Per-stock market timing,
indicator combinations, and cross-sectional ranking. The last one held up for a
decade and failed the moment it met a longer sample containing its known failure
mode - which is precisely why testing over a window that excludes that mode
proves nothing.

### The standing conclusion

**Quantara is a working, well-instrumented research system whose headline
finding is that its own strategies do not beat buy and hold.** That is a real
result, arrived at properly, and it is worth more than a backtest showing 500%
that nobody stress-tested.

Everything from Version 13 onward existed to make this conclusion trustworthy:
four correctness bugs in the accounting, three fail-open bugs in live order
handling, ~1.9x accidental leverage, a benchmark that was not a benchmark, a
selection bias measured rather than assumed, and 167 tests to keep it that way.
Without that work, the honest answer here would have been unknowable.

---

## Version 16 — The Benchmark (COMPLETE) 🔴 THE DECISIVE RESULT

Phase 2+3 of the post-audit plan. For the first time the system was measured
against the obvious alternative: **just buy the stock and do nothing.**

### What was fixed first

- **Sharpe now subtracts a risk-free rate**, from `^IRX` (13-week T-bill) via
  the price cache, with a 4% constant fallback. It never did. Sharpe is x0.5 in
  `compute_composite_score`, so this was influencing *selection*, not just
  reporting. The penalty scales as `rf / volatility`, so **low-volatility
  strategies lose more Sharpe than high-volatility ones** (measured: 0.649 vs
  0.086 on synthetic series).
- **`Win_Rate` renamed `Up_Day_Rate`.** It counted the fraction of DAYS the
  portfolio rose, cash days counting as losses — which is why it read ~30% next
  to a genuine trade-level 56.3%.
- **`Market_Return` and a new `Vs_Market` are surfaced everywhere.**
  `Market_Return` had been computed on every backtest since day one and read by
  nothing.
- **Buy & Hold added as a scoreable candidate**, stopless in backtest
  (`stop_loss=0`) and live (`apply_stop_loss=False`).
- **`stop_loss = 0` meant "stop at 0%", not "no stop"** — `price < entry * (1-0)`
  fires on ANY downtick. Caught by a test. Left unfixed it would have made the
  Buy & Hold candidate sell on the first red day and re-buy the next, which
  would have looked catastrophic and produced exactly the wrong conclusion from
  a one-character bug.

### 🔴 RESULT — buy & hold wins 4 of 5 tickers

```
Ticker  Best Strategy    Score   Sharpe  Return    MaxDD
NVDA    Buy & Hold      3.0321   1.297   1141.31%  -66.34%
TSLA    Buy & Hold      3.7365   1.242   1518.20%  -73.63%
AAPL    Buy & Hold      1.3154   1.046    293.32%  -31.43%
JPM     SMA Crossover   0.7919   0.753     91.65%  -22.64%
IBM     Buy & Hold      0.4931   0.414     51.51%  -38.98%
```

**Every ML strategy lost to buy & hold on every ticker. Ten out of ten.**

```
Vs Buy & Hold (percentage points)     LR         RF
NVDA                                 -764.20   -821.51
TSLA                                -1070.04  -1442.71
AAPL                                 -162.38   -222.50
JPM                                   -52.51    -82.03
IBM                                   -29.30    -52.93
```

**This is not an artifact of the unbounded return term in the composite score.**
That concern was raised in advance and checked: B&H also wins on **Sharpe
alone** — NVDA 1.297 vs LR 1.129, TSLA 1.242 vs 0.963, AAPL 1.046 vs 0.839,
IBM 0.414 vs 0.252.

**JPM is the sole survivor.** SMA Crossover 91.65% vs B&H 79.12%. JPM is the
one name in the book that did not ride a secular tech uptrend — consistent with
the standing hypothesis that this system earns its keep on non-trending names,
which now rests on exactly one ticker.

### ⚠️ THE COUNTER-ARGUMENT, WHICH IS REAL

Buy & hold's drawdowns are **-66% on NVDA and -74% on TSLA**. Recovering from
-74% requires a **+285%** gain just to break even; from -66%, **+194%**.

Sharpe does not measure this. Sharpe is return per unit of *volatility*; it says
nothing about whether the path was survivable. A strategy with a superior Sharpe
and a 74% drawdown is not obviously the better choice for a real person, who
would in practice sell near the bottom.

So the honest statement is narrower than "buy & hold wins":
**buy & hold produced more return per unit of volatility on these five
hindsight-selected names over their strongest decade, at drawdowns most people
could not sit through.** Every one of those qualifiers matters.

### Walk-forward re-run — the override is dead

With all four control arms finally executing (Round 3's Arm A never ran; the
B&H arm was scored with a stop and was not buy & hold):

```
Ticker Model   winner   interpretation
AAPL   LR      gated    "gate adds ~nothing" (beats arm B by 0.006)
AAPL   RF      B&H
IBM    LR      armA     RSI gate is decorative
IBM    RF      armB     exit signal has NO value
JPM    LR      B&H
JPM    RF      armB
NVDA   LR      armB
NVDA   RF      armB
TSLA   LR      armA
TSLA   RF      B&H
```

**The RSI-gated override wins outright in ZERO of ten cases.** Its one nominal
win is flagged as adding nothing.

The parameter surface confirms it. The no-gate control row (RSI 0) averages
**0.309**; the best gated cell is **0.317**. A margin of 0.008 is noise. The
gate does nothing between RSI 0 and 55, then starts actively hurting at 60+.

**Standing conclusion:** whatever the "momentum override" was capturing, it was
the trailing stop, not the momentum condition it is named after. The Version 12
research finding — *"model override beats model retraining for rare-event
capture"* — does not survive a proper control.

### 🐛 Two reporting bugs in the harness itself (fixed)

- **"Interior maximum found" was wrong.** The surface check treated
  `RSI_Trigger = 0` — the *control arm* — as a grid point. With the control
  excluded, the best gated cell beats no-gate by 0.008 and the report now says
  so explicitly instead of announcing a mechanism.
- **ADOPT verdicts were measured against the ML baseline**, which itself loses
  to B&H by 800+ points. A large positive delta only meant the override dragged
  a losing strategy part of the way back toward doing nothing. The verdict now
  reports a `vs B&H` column and returns **"LOSES TO BUY & HOLD - not an edge"**
  whenever B&H beats the override over the same window.

### ⬜ WHERE THIS LEAVES THE PROJECT

The question is no longer "does the override work" or "which model is best". It
is:

> **Does this system beat holding, on stocks that did not go up 10x?**

JPM says maybe. One ticker is not evidence. Running the whole pipeline on ~5
tickers chosen *without hindsight* — something outside tech, something that went
sideways for a decade, something that declined — is the experiment that settles
it, and everything since Version 13 has been clearing the instruments so that
its answer can be trusted.

---

## Version 15 — Execution Realism, Price Cache, Live Model Fix (COMPLETE)

Phase 1 of the post-audit plan. Three fixes to how the system models reality,
plus a cache. **Every backtest figure changed again — the third invalidation.**

### Fix 1 — The live model was trained on stale data (Phase 1.1)

`generate_current_signal()` fetched 300 calendar days, which after
`build_features().dropna()` left ~155 rows, then trained on the FIRST HALF:

```
live model:     ~77 rows, ending roughly 4 months before the prediction
backtest model: ~1,100 rows
```

**They were not the same model, so no backtest result described live
behaviour.** Now trains on all history from `START` up to yesterday and
predicts today — the same order of magnitude as the backtest.

Also fixed alongside it:
- **Scaler leakage.** `fit_transform(X)` ran over the whole frame *including*
  today's row, leaking today's feature values into the scaling parameters. Now
  fitted on training rows only.
- **`end=today` risked dropping today's bar.** yfinance treats `end` as
  exclusive; now passes tomorrow.
- **The last row's label is fabricated.** `build_target()` does
  `(close.shift(-1) > close).astype(int)`. On the final row `shift(-1)` is NaN,
  `NaN > close` is False, and `astype(int)` makes that **0** — not NaN. So it
  survives `dropna()` looking like a real label. Harmless under the old 50/50
  split (the last row was never in the training half); **fatal once training on
  everything**, since it would teach "today goes down" on every single run.
  Excluded via `.iloc[:-1]`, with a regression test.
- **Signal failure returned `0`, which means SELL.** Any exception — bad data,
  a crashed model — produced a SELL/HOLD signal that would liquidate a real
  position. Now returns `None` and the ticker is skipped entirely: no order,
  and no log row either (a row with `Signal 0` is indistinguishable from a real
  decision downstream). **Third fail-open bug in the live path**, after
  `get_pending_orders` and `get_position`. Same shape every time: an error
  handler returning a value that means "nothing here" instead of "I don't know."

### Fix 2 — Execution lag (Phase 1.2)

The engine decided AND executed at the same close. Live cannot do that:

```
21:00 UTC   job reads today's close, submits a DAY market order
04:00 ET    Alpaca releases it into the pre-market session
09:33 ET    it fills, minutes after the next regular open
```

Confirmed by real fills on 2026-08-14 (submitted 08:00 UTC, filled 13:33 UTC).
Now every decision — **including stop losses** — is made at a bar's close and
executed at the next bar's **open**. Required adding `Open` to the loader and
cache.

**This is what made gap risk visible.** Regression test, sell decided at a
close of 100 with an overnight gap to an open of 80:

```
same-bar (old): $10,000.00   <- loses nothing
lagged   (new): $ 8,000.00
```

The old engine was *structurally incapable* of pricing an AAPL-style weekend
gap: the stop triggered and exited at the identical price. 20% of equity the
backtest never charged.

### Fix 3 — Transaction costs (Phase 1.3)

`TRANSACTION_COST_BPS = 5.0` per side (Alpaca is commission-free, so this
stands in for spread and impact). Sizing divides by `(1 + cost_rate)` so the
fee comes out of the intended notional rather than overdrawing at
`position_size = 1.0`.

**Costs are not cosmetic — they change which strategy gets SELECTED.** On a
flat price series over 12 bars:

```
no costs:   holding and churning are IDENTICAL
with costs: hold $9,990.01  vs  churn $9,890.61
```

A strategy flipping in and out every other day previously looked exactly as
good as one that held.

### Fix 4 — Local price cache

15 yfinance downloads per run (~3,900/year) for bars fixed years ago. Every one
a chance to fail, and a failed download inside a bare `except` is what produced
AAPL's one-day strategy flips.

Now cached per ticker in `data/cache/` (gitignored; preserved on Actions by
`actions/cache`, since committing it would add a ~850KB blob daily). Wired into
`load_data()` so all callers benefit unchanged.

**The hard part is that yfinance history is not immutable** — Yahoo
retroactively re-adjusts every prior bar on a split or dividend. The cache
re-fetches the last 7 days on refresh and *compares* them to what is stored; on
disagreement it rebuilds the whole file. Self-healing, no manual invalidation.

Two bugs caught by testing rather than review:
- **Range coverage alone was not enough.** A request already spanned by the
  cache never re-checked, so a backtest-only run would serve pre-split prices
  indefinitely. Now re-verifies once per ticker per day.
- **A start date on a non-trading day defeated the cache entirely.** `START` is
  2015-01-01 — New Year's Day. The first real bar is 2015-01-02, so
  `2015-01-01 < 2015-01-02` was always true and every call decided it needed
  earlier history. **The cache was a complete no-op for the auto_select path.**
  Fixed by tracking the earliest *requested* start separately from the first
  bar returned.

### ✅ REGENERATED RESULTS — Aug 14 2026, Version 15 engine

```
Ticker  Best Strategy         Score   Sharpe  Return   MaxDD
NVDA    EMA Crossover         1.7828  1.172   524.11%  -50.48%
TSLA    Logistic Regression   1.4636  0.999   426.74%  -63.12%
AAPL    EMA Crossover         1.0741  1.018   163.14%  -20.38%
JPM     SMA Crossover         0.8384  0.846    91.65%  -22.64%
IBM     Logistic Regression   0.4084  0.335    24.02%  -35.72%
```

**Three assignments changed** vs the V13 table: TSLA SMA → **LR**, AAPL LR →
**EMA**, IBM Bollinger → **LR**.

**Finding 1 — lag is not a uniform tax.** NVDA's return went *up* (495.83% →
524.11%) despite paying costs. Filling at the next open rather than the same
close is a different price series, not a haircut; it can help or hurt depending
on the strategy and the trend.

**Finding 2 — Bollinger Bands on IBM collapsed, and the reason is instructive.**
It scored 0.8276 with a remarkable -6.49% drawdown under V13; it is not
selected at all now. **Mean-reversion strategies were the largest beneficiaries
of the same-bar execution bug.** Bollinger buys at the lower band — with
same-bar fills you buy at the exact extreme close you just observed. In reality
you buy at the next open, after the bounce has begun. Its apparent quality was
substantially an artifact of execution that cannot happen. Worth checking
whether the same applies to any other mean-reversion result in this document.

**Finding 3 — IBM now has no working strategy.** Its best available scores
**0.4084**, which is "failing" on this project's own scale (below 0.5). Under
V13 its winner scored 0.8276. This matters because IBM was one of only two
places the momentum override beat buy & hold, and the whole "edge appears on
non-trending names" hypothesis leans on it.

**Finding 4 — ML/rule-based comparison shifted in both directions**, not
uniformly:

```
Ticker  LR (V13 -> V15)   RF (V13 -> V15)
NVDA    0.911 -> 1.175    1.028 -> 1.139
TSLA    0.822 -> 0.999    0.515 -> 0.446
AAPL    1.168 -> 0.911    0.930 -> 0.716
JPM    -0.397 -> 0.339    0.209 -> 0.268
IBM     0.534 -> 0.335    0.433 -> 0.123
```

JPM's LR swung from -0.397 to +0.339. IBM's RF fell to 0.123. These moves are
too large to be "costs shaved a bit off" — they reflect a genuinely different
execution price series. **Do not treat any V13 comparison as still standing.**

### ⚠️ STILL OUTSTANDING after Version 15

- Buy & hold is **still not a candidate** in `auto_selector.py`. The Round 3
  finding (B&H beats every LR/RF baseline on Sharpe) has not been acted on, and
  none of these regenerated numbers are compared against simply holding.
- The **momentum override results are void again** — they were produced on the
  V13 engine with no lag and no costs. The override holds positions longer,
  which costs *less* in transaction terms, so it may look better now for a
  reason that has nothing to do with momentum.
- **No rebalancing logic.** JPM sits at 44% of equity against a 20% target.

---

### ✅ FIRST LIVE NQ RUN — Aug 14 2026 (the measurement layer works)

Three findings, all previously impossible to observe.

**1 — The position-sizing fix, confirmed in a real order.** The scheduled 21:00 UTC run
executed the *old remote* code (`POSITION_SIZE = 0.50` — the local fix had never been
pushed). A manual run after the push executed the new code. Same ticker, same day,
~$12,100 equity:

```
old code: NVDA buy 26.8561 sh x $225.30 = $6,051 = 50.0% of equity
new code: NVDA buy 10.7665 sh x $225.16 = $2,424 = 20.0% of equity
```

**2 — Slippage measured for the first time.** `fills.csv` vs the signal price:

| | Signalled (Aug 13) | Filled (Aug 14) | Difference |
|---|---|---|---|
| NVDA sell | $224.09 | $227.1603 | **+1.37%** in our favour |
| AAPL sell | $302.25 | $306.4322 | **+1.38%** in our favour |

Order lifecycle confirmed too: submitted 08:00 UTC (Alpaca releasing a queued
after-hours order at the 04:00 ET pre-market open), filled 13:33 UTC = **09:33 ET,
three minutes after the regular open**. That is the "signal at close, fill at next open"
window where gaps land — now documented from real data instead of inferred.

**3 — Leverage 0.93x, but position sizes still wrong.** No margin debt, but only because
two positions are held instead of five:

```
JPM   $5,328.20 = 44.0% of equity   (target 20%)
TSLA  $5,914.94 = 48.8% of equity   (target 20%)
cash    $877.75
```

Both are legacy 0.50-era positions. **There is no rebalancing logic** — oversized
positions only correct when they cycle out. TSLA's pending sell and NVDA's 20% re-entry
resolve two; JPM stays at 44% until it sells.

### ✅ Trading date vs wall-clock date (fixed)

Logs were stamped with `datetime.now()` — the date the *script ran*, not the date of the
*market data it acted on*. A manual run at 19:14 PT on Friday Aug 14 was 02:14 UTC on
**Saturday Aug 15**, so Friday's closing prices were recorded on a Saturday. Every
consumer in `performance.py` treats `Timestamp` as "which trading day is this row about"
(sorting, weekly bucketing, drawdown dating), so this corrupted all of them.

Fixed by `get_trading_date()` in `paper_trader.py`, which reads `df.index[-1]` from the
market data and is threaded through `log_signals()` and `log_account_state()`. Date comes
from the data; clock time still records when the job ran.

**`fills.csv` is deliberately excluded** — those timestamps are real Alpaca event times
for real executions and must never be rewritten. Existing 2026-08-15 rows in
`paper_trading_log.csv`, `equity_log.csv` and `positions_log.csv` were corrected by hand.

### ✅ Schedule moved off unsettled prices (fixed)

Two runs on the same trading day, 5 hours apart, disagreed on every closing price:

```
            17:21 ET   22:14 ET     diff
NVDA         225.30     225.16     -0.14
TSLA         339.96     342.27     +2.31
AAPL         305.26     305.93     +0.67
JPM          363.11     362.84     -0.27
IBM          237.14     234.32     -2.82
```

**The old `0 21 * * 1-5` fired at 5:00 PM ET — during post-market**, which runs to
8:00 PM ET; yfinance's daily close is not settled until after it. AAPL's Logistic
Regression signal **flipped from BUY to SELL on a $0.67 difference**, which separately
says the model was sitting on its decision boundary that day.

Now `0 1 * * 2-6` — 01:00 UTC, Tue–Sat:

| | ET | PT |
|---|---|---|
| Summer (EDT) | 9:00 PM | 6:00 PM |
| Winter (EST) | 8:00 PM | 5:00 PM |

Tue–Sat because 01:00 UTC falls on the calendar day *after* the session it belongs to.
Reasoning:
- **Running later costs nothing.** DAY market orders submitted after hours queue for the
  next open whether sent at 4 PM or 10 PM ET. The fill is identical; only data improves.
- **Cron has no DST awareness**, so the schedule must be right in both seasons. Firing at
  the close in summer (20:00 UTC) would land at 3:00 PM ET in winter — an hour *before*
  the close, market still open.
- **GitHub Actions runs scheduled jobs 1–3 hours late**, which only pushes this deeper
  into the settled window. Relying on that delay to escape an *unsettled* window would
  not be safe, since a fast run would get bad data.

### ✅ Two fail-OPEN bugs in `alpaca_executor.py` (fixed)

Both could place a duplicate order or skip a stop loss.

**Bug A — the duplicate-order guard never matched anything.**
```python
str(o.status) in ["accepted", "pending_new", "new"]
```
alpaca-py renders enums as `OrderStatus.ACCEPTED`, so this compared
`"OrderStatus.ACCEPTED"` against `"accepted"` and matched nothing.
`get_pending_orders()` returned `[]` regardless of what was queued.
`submit_and_verify()` in the *same file* had always normalised correctly with
`.split(".")[-1].lower()` — the two functions disagreed.

Now uses that normalisation, and the check is **inverted**: terminal statuses are listed
(`filled`, `canceled`, `expired`, `rejected`, `replaced`, `done_for_day`) and everything
else counts as live. An unrecognised or newly-added Alpaca status therefore errs toward
*skipping* a buy — one missed entry — rather than duplicating a position.

**Bug B — bare excepts made failure look like "nothing there."** `get_position()`
returned `None` and `get_pending_orders()` returned `[]` on *any* exception, so a network
blip was indistinguishable from "you hold nothing" and "nothing is queued." That both
skips the stop loss on a position you really hold *and* lets a duplicate BUY through.

Now `get_position()` returns `None` only for a genuine 404 "position does not exist" and
raises otherwise; `get_pending_orders()` raises on failure and the BUY branch **fails
closed** — if it cannot confirm nothing is queued, it does not buy.

**Also restructured:** pending orders used to be fetched at the top of `execute_signal()`,
*before* the stop-loss check, so an orders-endpoint failure aborted the function and
silently skipped a stop loss. They are now fetched only inside the BUY branch. **A
failure can no longer block a stop loss.**

### ⚠️ The Version 12 override did not implement the rule it described

Found by synthetic-price testing while building the walk-forward harness. Two bugs,
both of which made the override far more aggressive than documented:

**Bug 1 — the "position is profitable" test was a no-op in the common case.** `entry`
was initialised to `0.0` and only updated on a 0 → 1 signal transition. When the test
period **begins already in a position** (`Signal[0] == 1`, which is common) no such
transition ever occurs, so `entry` stays `0.0` and `close[i] > entry` is trivially
true. **The override engaged on losing positions.**

**Bug 2 — the trailing stop ratcheted downward instead of exiting.** On the bar the
trailing stop released, control fell straight through to the re-entry check, which
(thanks to Bug 1) passed — so it re-engaged on the same bar at the lower price, reset
the peak, and repeated. **Structurally identical to the engine's stop-loss re-buy bug
found in Version 13** — release, then immediately re-arm on the same bar.

Demonstrated on a position falling 100 → 10 with RSI pinned at 80:

```
documented rule : holds 0 of 9 bars   (position is not profitable - never engages)
V12 implementation: holds 8 of 9 bars (re-engages on EVERY bar, ratcheting down)
```

**Every Version 12 override result was measuring a different rule than the one it
described.** The reported "TSLA RF improved in 9 of 9 configurations" was produced by a
rule that holds losers longer — which is a leverage-on-losses effect, not an edge, and
would be actively dangerous live.

The rule now lives in `strategy/momentum_override.py` (single source of truth, imported
by both scripts so they cannot drift), with a `legacy=True` flag that reproduces the
Version 12 behaviour bug-for-bug. `override_walk_forward.py` scores **both** variants
side by side, so the report states directly whether the V12 result depended on the bugs.
Pinned by `test_momentum_override.py` (13 assertions).

### `override_walk_forward.py` — the actual validation harness

Supersedes `mom_override.py` (kept for provenance, now importing the shared rule).

- 4 windows (2015-01-01 → 2024/2023/2022/2021) × 5 tickers × 2 models × 9 configs
- **Trains once per (ticker, model, window)** and applies all 9 override configs to the
  same predictions. The override is a post-hoc signal rewrite and does not change the
  model, so `mom_override.py`'s 450 refits were pure waste. 40 fits instead.
- Verdict thresholds are deliberately demanding: **ADOPT** requires ≥80% of cells
  improved AND all 4 windows positive AND avg delta > 0.05. Version 12's "9 of 9" was
  on a single window, which is precisely what Version 10 established is not evidence.
- Reports parameter sensitivity across the full grid — "strength in one or two cells is
  the signature of a false positive."
- Writes `results/override_walk_forward.csv` for inspection.

### ✅ WALK-FORWARD RESULT (run Aug 14 2026, 360 cells) — THE OVERRIDE SURVIVES

```
Ticker Model   cells  windows    avg d  worst d   ddelta  verdict
AAPL   LR      32/36      4/4    0.137    0.101    +1.70  ADOPT
AAPL   RF      36/36      4/4    0.348    0.231    -2.48  ADOPT
TSLA   LR      36/36      4/4    0.176    0.079    -2.91  ADOPT
TSLA   RF      31/36      4/4    0.270    0.147    -1.34  ADOPT
JPM    RF      27/36      3/4    0.050   -0.058    -0.71  PROMISING
JPM    LR      24/36      2/4    0.048   -0.017    +1.27  NOISE
IBM    LR      21/36      3/4    0.014   -0.151    +0.07  NOISE
IBM    RF      18/36      1/4   -0.017   -0.089    +0.03  REJECT
NVDA   LR      17/36      1/4   -0.004   -0.060    -4.50  REJECT
NVDA   RF      17/36      1/4   -0.005   -0.090    -1.52  REJECT
```

**Finding 1 — the override is real, on AAPL and TSLA.** Four ticker/model pairs improved
in all four windows. AAPL/RF improved in **36 of 36 cells**. This is the first
intervention in five attempts to survive walk-forward validation.

**Finding 2 — it works on the wrong tickers, again.** Versions 9, 10 and 12 all targeted
**TSLA and IBM**. TSLA passes, but **IBM is a clean REJECT** (18/36 cells, 1/4 windows,
negative average) — the V12 claim of "IBM RF 8/9" does not survive walk-forward. And the
strongest result in the entire table is **AAPL**, which was never a target ticker. Third
time this project has found an effect on a ticker it wasn't looking at (cf. Version 10,
where Streak improved NVDA/AAPL while failing TSLA/IBM).

**Finding 3 — NVDA rejects on both models, confirming Version 12.** Negative in 3 of 4
windows, and it carries the worst drawdown cost in the table (-4.50 pts on LR). The
override should never be applied globally.

**Finding 4 — the V12 bugs were real but nearly immaterial on real data.**

```
Ticker Model  corrected d   legacy d   held  legacy held
AAPL   LR           0.137      0.145    157          160
AAPL   RF           0.348      0.357    315          317
TSLA   LR           0.176      0.187     82           88
TSLA   RF           0.270      0.364    131          157
NVDA   LR          -0.004     -0.039    128          134
NVDA   RF          -0.005     -0.046    204          211
IBM/JPM         (identical to 3 decimal places)
```

The two bugs barely bind on real price series, because when RSI is high the position is
usually *already* profitable — so the broken profitability test rarely changed a
decision. **The V12 result was NOT an artefact.** Two real differences: TSLA/RF loses
about a third of its edge under the corrected rule (0.364 → 0.270, holding 157 → 131
days), so some of that headline *was* bug-driven; and NVDA is *less bad* corrected than
legacy, meaning the bugs were actively hurting there. The fix is still correct — a rule
that engages on losing positions is unsafe regardless of whether it happened to pay on
this sample — but the earlier expectation that this would invalidate V12 was wrong.

**Finding 5 — ⚠️ THE OPTIMUM IS AT THE EDGE OF THE GRID.** The parameter sensitivity
table is monotonic, not peaked:

```
AAPL/RF:  RSI 65 -> 0.380 0.546 0.717   RSI 70 -> 0.192 0.314 0.499   RSI 75 -> 0.122 0.163 0.203
TSLA/RF:  trail 3% -> 0.152             trail 5% -> 0.316             trail 8% -> 0.513
```

**Lower RSI trigger is always better. Wider trail is always better.** Every best cell
sits on the boundary of what was tested, which means the true optimum lies *outside* the
grid and has not been found. Extrapolating the gradient, the limit case is "RSI trigger
low enough to always fire, trail wide enough to never stop out" — which is simply
**never sell on a model exit signal, and use a wide trailing stop instead.**

If that is what the data is saying, the finding is not "momentum override works" but the
much broader and more troubling **"the ML exit signal is worse than a dumb trailing
stop."** That would be consistent with the TSLA/IBM momentum misread documented since
Version 9 (models exit near local tops), and it is a fundamentally different conclusion
with different implications.

**This must be resolved before anything ships.** Re-run with RSI triggers {50, 55, 60}
and trails {8%, 12%, 15%, 20%}, plus two control arms: (a) trailing stop only, ignoring
RSI entirely, and (b) no model exits at all, trailing stop only. If control (a) matches
or beats the override, the RSI condition is doing no work and the simpler rule wins.

### ⚠️ ROUND 2 (wider grid) — PARTIALLY INVALID, RE-RUN REQUIRED

Round 2 ran RSI {0, 50, 55, 60, 65} × trail {8, 12, 15, 20%}. **Control Arm A did not
execute.** `score()` guarded with `if rsi_trigger:` — and `0` is falsy in Python — so
every Arm A cell silently returned the baseline and reported a delta of exactly `0.000`.
Fixed to `if rsi_trigger is not None`. **Every "RSI gate genuinely helps" verdict from
that run is void**, since it compared against a control that never ran.

Still valid from Round 2: the gated results, Arm B (trail-only), and the legacy
comparison. Gated beat trail-only on AAPL and TSLA; trail-only beat gated on JPM and
NVDA/LR.

**The parameter surface is still monotonic in the trail dimension** (best cell RSI 50 /
trail 20%, both at the boundary), though the RSI dimension has roughly plateaued — 50
and 55 are within noise of each other, while 60 and 65 are clearly worse.

### 🔴 ROUND 3 (Aug 14 2026) — CONFIRMED: BUY & HOLD BEATS EVERY STRATEGY

All four arms, corrected. This is the most important result the project has produced.

```
Ticker Model   gated d    armA d    armB d     B&H d  winner
AAPL   LR        0.354     0.322     0.243     0.408     B&H
AAPL   RF        0.545     0.326     0.375     0.405   gated  <-- beats B&H
IBM    LR        0.006     0.098    -0.001     0.062    armA
IBM    RF        0.058     0.004    -0.057     0.017   gated  <-- beats B&H
JPM    LR        0.224     0.382     0.414     0.591     B&H
JPM    RF        0.038     0.037     0.008     0.059     B&H
NVDA   LR        0.082     0.207     0.202     0.248     B&H
NVDA   RF        0.163     0.224     0.121     0.260     B&H
TSLA   LR        0.368     0.380     0.042     0.388     B&H
TSLA   RF        0.770     0.698     0.553     0.868     B&H
```

**Every single `B&H d` value is positive.** That means buy & hold has a higher Sharpe
than the ML model baseline for **all 10 ticker/model pairs, across all 4 windows**.
Buy & hold wins outright in 8 of 10.

**This reframes the entire override investigation.** The override was never capturing a
momentum effect. It was partially closing the gap to buy & hold by trading less. The
monotonic gradient — hold longer, stop out less, always better — was the strategies
converging toward the thing that was beating them *in this sample and on this metric*.

⚠️ **Scope this claim carefully.** It applies to LR and RF, judged on Sharpe, on five
hindsight-selected US large-caps during 2015-2024. It is NOT a general finding that the
system loses to buy & hold — see the Version 11 reconciliation below, where the same
system beat buy & hold by +15.62 pts (≈+6 delevered) in a flat market.

**Two genuine survivors:**
- **AAPL/RF** — gated 0.545 vs B&H 0.405. Beats buy & hold by a clear margin, and did
  so in all 4 windows (75/80 and 76/80 cells).
- **IBM/RF** — gated 0.058 vs B&H 0.017. Tiny, but positive.

**The pattern in those two is the interesting part.** IBM is the least trending name in
the book and the one where buy & hold is weakest (`B&H d` 0.062 / 0.017 vs TSLA's
0.868). The strategies add value precisely where the underlying did *not* simply go up.
That is what an actual edge would look like — and it is nearly invisible in a sample
dominated by names that went up 10x.

**The RSI axis finally bracketed.** Pooled surface at trail 20%: RSI 50 → 0.295,
**55 → 0.306**, 60 → 0.280, 65 → 0.244. An interior maximum at 55, so the RSI condition
is not purely decorative. The trail axis is still on the boundary at 20%, consistent
with "wider trail → closer to buy & hold → better."

**Caveats that make this finding STRONGER, not weaker:**
- **No transaction costs are modelled.** Buy & hold trades once; the ML strategies trade
  constantly. Adding costs widens B&H's lead.
- **Round 1's tighter grid hid this.** With trail capped at 8% the strategies never got
  close enough to buy & hold for the comparison to be obvious.

### ⚠️ THIS DOES NOT CONTRADICT VERSION 11's +15.62 pts — DIFFERENT MEASUREMENTS

Version 11 found Quantara +20.10% vs equal-weight buy & hold +4.48% over Apr 29 –
Aug 13 2026. Round 3 finds buy & hold beating every ML baseline on 2015-2024 windows.
Both are true. They are not the same comparison, in six separate ways:

| | Version 11 live | Round 3 backtest |
|---|---|---|
| **Period** | Apr–Aug 2026 (76 trading days) | test halves of 2015-2024 |
| **Metric** | total return, percentage points | **Sharpe ratio** |
| **Structure** | 5-ticker portfolio, shared capital | single ticker, own private capital |
| **Benchmark** | equal-weight B&H across 5 names | per-ticker B&H |
| **Strategies** | EMA, SMA, Bollinger, LR, RF | **LR and RF only** |
| **Leverage** | ~1.91x (delevered ≈ +10.5%, ≈ +6 pts) | none |

**The decisive difference is the market regime.** Per-ticker buy & hold over the live
window: NVDA **+5.12%**, TSLA **-12.90%**, AAPL +11.65%, JPM +17.25%, IBM **+1.26%**.
That is a flat-to-choppy market. Over the backtest windows the same names rose
enormously — NVDA roughly 10x.

**Buy & hold is unbeatable in a straight-line uptrend and easy to beat in a chop.** The
two results are measuring the same system in opposite regimes, and both are consistent
with the IBM finding: **these strategies earn their keep when the underlying is NOT
simply going up.** Version 11's edge came from trading around TSLA's decline and sitting
out IBM's mid-July collapse — exactly the conditions where holding fails.

Note also that **three of the five live strategies (EMA Crossover, SMA Crossover,
Bollinger Bands) were never in the Round 3 comparison at all** — it tested LR and RF
only. The Round 3 claim is therefore narrower than "the system loses to buy & hold." It
is: *LR and RF, judged on Sharpe, on five hindsight-picked names during their biggest
bull run, lose to buy & hold.*

**Measurement gap to close:** the `buy_and_hold` control arm records Sharpe and drawdown
but **not total return**, so it cannot currently be compared against Version 11's
return-based finding on equal terms. Add `Total_Return` / `Market_Return` to the control
rows before drawing further conclusions.

**The caveat that limits it:**
- **Sharpe is not the whole story.** Buy & hold on NVDA meant sitting through very deep
  drawdowns. The `ddelta` column shows the override already costs up to -9.50 points of
  drawdown on NVDA/RF; buy & hold is worse still. Whether that path is tolerable is a
  separate question Sharpe does not answer.
- **This is a hindsight-selected sample.** Five US large-caps chosen in 2026 with full
  knowledge of 2015-2024. "Buy & hold wins" is close to tautological here. It says much
  less about strategy quality than it appears to, which is exactly why the IBM result
  matters more than the TSLA one.

### ⬜ WHAT THIS CHANGES — highest priority in the project

1. **Buy & hold must become the default benchmark everywhere.** `get_metrics` has always
   returned `Market_Return` and it was never printed, never scored, never surfaced on the
   dashboard. `compute_composite_score` does not reference it at all. **A strategy that
   cannot beat holding the same ticker should not be selected for that ticker.**
2. **Add buy & hold as a candidate in `auto_selector.py`** so it competes directly. On
   this evidence it would win most tickers — which is the correct answer, not a failure.
3. **Re-run on tickers that did NOT go up 10x.** The IBM signal suggests the system may
   have real value on non-trending names. That is the hypothesis worth testing, and it
   requires a sample not chosen with hindsight.
4. Only then revisit the override. AAPL/RF remains the one configuration that beat buy &
   hold outright across all four windows.

### ⚠️ ORIGINAL HYPOTHESIS (now confirmed by Round 3)

The override improves monotonically as it holds longer, and its limit case is "never
sell." Over 2015-2024 on NVDA, AAPL and TSLA, **"never sell" is buy & hold on three
stocks that rose enormously.** NVDA's auto-selector return of 495.83% should be measured
against NVDA's own buy & hold over the same window, which is far higher.

If that is what is happening, the gradient is not evidence of a momentum effect. It is
evidence that **every strategy here underperforms simply holding the asset**, and any
modification that reduces trading looks like an improvement. This would also explain why
the effect strengthens on exactly the highest-momentum names and is absent on IBM.

A `buy_and_hold` control arm has been added to `override_walk_forward.py` and is now
reported alongside the others. **Run it before drawing any conclusion about the
override.** `get_metrics` has always returned `Market_Return`; it was simply never
printed.

If buy & hold wins across the board, the honest next question is not "how do we tune the
override" but **"does this system beat holding the stocks at all, and on what sample?"**
— which loops directly back to the survivorship-bias concern in Known Issues.

### Live-assignment check — for the first time, a match

Live as of the V13 re-selection: NVDA → EMA Crossover, TSLA → SMA Crossover,
**AAPL → Logistic Regression**, JPM → SMA Crossover, IBM → Bollinger Bands.

**AAPL/LR is both an ADOPT candidate and the live assignment.** It is also the only
ADOPT candidate whose drawdown *improved* (+1.70 pts) rather than worsened. Version 12
shipped nothing precisely because every win was on a model that wasn't live; that
blocker is now gone for exactly one ticker.

TSLA's wins (LR and RF) are currently unreachable — TSLA is live on SMA Crossover, a
rule-based strategy the override has not been tested against.

**Recommended sequence — do NOT ship yet:**
1. Resolve Finding 5 first. If the RSI condition is doing no work, the thing to ship is
   a trailing stop, not this.
2. Only then consider AAPL/LR, as a single-ticker change with the drawdown improvement
   as supporting evidence.
3. Add the override as a scoreable variant in `auto_selector.py` so RF+override can
   compete fairly rather than being applied by hand.

---

## Next Session — Priority Order
1. **Walk-forward the override** on TSLA and IBM RF across four window lengths,
   re-baselined on the 18-feature set **and the Version 13 engine**. The Version 12
   override results were produced on the old engine (whole-share flooring, non-working
   stop, position size 0.50) and must be considered void, not merely unvalidated.
2. **Daily equity + fills log** (original item 5). Append account equity, cash, buying
   power and per-position `avg_entry_price`/qty from the Alpaca API on every run, plus a
   separate `fills.csv` of actual executions. Currently every headline figure — the
   +20.10%, the drawdowns, the benchmark — is *reconstructed* from yfinance closes
   rather than measured. This is why `reconcile_open_segments()` had to exist, and it
   would have caught the 1.91x leverage on day one.
3. **Execution lag + transaction costs** in `run_backtest` (original item 6). The
   backtest fills at the signal's own close; live fills at the next open. Worst on the
   gap scenario the project cares most about — the backtest stop triggers and exits on
   the *same* close, so it structurally cannot see AAPL-style gap risk.
4. **Portfolio-level backtest** (original item 7). Every backtest is one ticker with its
   own private $10k. The thing actually running live is a 5-position correlated
   portfolio sharing one pool of capital. There is currently **no simulation of the
   system that is actually deployed** — no capital contention (which is what rejected
   the TSLA order), no true portfolio drawdown, no correlation awareness across five
   heavily-correlated US large-caps.
5. **Live LR training-window bug** (see Known Issues — the live model is trained on data
   ending ~150 days ago and has never seen the most recent five months).
6. **Strategy lock-in** with monthly re-evaluation. Note Fix 4 may have already removed
   the churn mechanism — re-assess whether lock-in is still needed before building it.

## How To Run
```powershell
# Activate environment
.\venv\Scripts\Activate.ps1

# Run modes by changing MODE in main.py
# Options: "compare", "optimize", "ml", "rf", "auto", "paper", "diagnostic"
python main.py

# Run automated paper trader directly (also executes Alpaca orders — careful, this trades)
python run_paper_trader.py

# Set env vars for local Alpaca testing
$env:ALPACA_KEY="your_key"
$env:ALPACA_SECRET="your_secret"

# Test performance analytics functions standalone (safe, no trading)
python test_performance.py

# --- V13 correctness tests. Network-free, no trading, no market data. ---
# RUN THESE BEFORE TRUSTING ANY BACKTEST RESULT. Both must report 0 failed.
python test_engine_synthetic.py          # 18 assertions on run_backtest
python test_auto_selector_fallback.py    # 7 assertions on selection failure handling
python test_account_log.py               # 22 assertions on the Alpaca measurement layer
python test_momentum_override.py         # 13 assertions on the override rule
python test_trading_date.py              # 14 assertions on trading-date logging
python test_alpaca_executor.py           # 20 assertions on the live order guards
python test_live_signal.py               # 17 assertions on live model training
python test_cache.py                     # 24 assertions on the price cache
python test_execution_model.py           # 13 assertions on lag + transaction costs
                                         # -- 148 assertions total, all network-free --

# One-command status check over results/ (no network, no Alpaca)
python check_health.py

# Inspect the price cache
python -m data.cache

# Walk-forward validation of the momentum override (needs network, ~few minutes)
python override_walk_forward.py
```

---

## Project Architecture
```
REQuantara/
├── .github/
│   └── workflows/
│       └── paper_trader.yml      # GitHub Actions - '0 1 * * 2-6' = 01:00 UTC Tue-Sat
│                                 # = 9PM ET summer / 8PM ET winter (V14; was 21:00 UTC,
│                                 # which fired mid post-market on unsettled prices)
│                                 # commit step: commit local changes BEFORE
│                                 # pull --rebase, then push (avoids unstaged-
│                                 # changes rebase failures)
├── data/
│   └── loader.py                 # yfinance fetch; keeps Close, High, Low
│                                 # (High/Low added for ADX_14 support)
├── indicators/
│   ├── moving_average.py         # compute_sma(df, window)
│   ├── ema.py                    # compute_ema(df, window)
│   ├── rsi.py                    # compute_rsi(df, window=14)
│   └── bollinger.py              # compute_bollinger_bands(df, window=20, num_std=2)
├── signals/
│   ├── sma_crossover.py          # generate_signals, generate_crossover_signals,
│   │                             # generate_ema_crossover_signals, generate_combined_signals
│   └── bollinger_signal.py       # generate_bollinger_signals
├── backtest/
│   └── engine.py                 # run_backtest(df, initial_capital, stop_loss, position_size)
├── evaluation/
│   ├── metrics.py                # calculate_metrics (prints), get_metrics (returns dict)
│   ├── exporter.py               # export_results, export_optimization - saves to Excel
│   └── performance.py            # build_trade_segments, ticker_summary, win_loss_stats,
│                                 # drawdown_tracker, signal_quality_score,
│                                 # signal_quality_weekly, detect_problems,
│                                 # build_event_feed, KNOWN_EXIT_REASON_OVERRIDES
├── plots/
│   └── visualizer.py             # plot_results(df) - 3 panel chart
│                                 # plot_diagnostic(ticker) - LR diagnostic chart
├── strategy/
│   ├── runner.py                 # run_all_strategies(tickers) - multi stock/strategy grid
│   ├── optimizer.py              # optimize_ema_crossover, optimize_all_tickers
│   ├── ml_signal.py              # FEATURE_COLS constant (16 features, single source
│   │                             # of truth) + run_ml_strategy (LR), run_rf_strategy
│   │                             # (RF), build_features, build_target
│   ├── auto_selector.py          # auto_select - picks best strategy per ticker
│   │                             # compute_composite_score, evaluate_rule_based, evaluate_ml
│   │                             # NOTE: scores 2015-2024 backtest only, no live data
│   │                             # awareness; EMA Crossover here is always default
│   │                             # 20/50, never the optimizer's tuned parameters
│   ├── paper_trader.py           # run_paper_trader - live signals + Alpaca execution
│   │                             # get_recent_data, generate_current_signal (imports
│   │                             # FEATURE_COLS from ml_signal.py), log_signals
│   │                             # CRITICAL: logs the ACTUAL executed Signal/Action,
│   │                             # overridden to SELL when exit_reason == STOP_LOSS —
│   │                             # never just the model's raw opinion
│   └── alpaca_executor.py        # get_client, execute_signal (ALWAYS returns a
│                                 # (result, reason) tuple — reason is one of
│                                 # "STOP_LOSS", "SIGNAL", None), get_pending_orders,
│                                 # check_stop_loss
├── results/
│   ├── paper_trading_log.csv     # auto updated by GitHub Actions daily; rows written
│   │                             # after the Stop Loss CSV Accuracy Fix include a 7th
│   │                             # field, Exit_Reason
│   ├── strategy_assignments.json # V13: last known-good strategy per ticker. Written on
│   │                             # every successful auto_select; read as fallback when a
│   │                             # selection run is abandoned. Committed by Actions via
│   │                             # `git add results/`, so it persists between runs.
│   ├── equity_log.csv            # V14: account snapshot per run — equity, cash,
│   │                             # gross exposure, LEVERAGE, implied margin debt
│   ├── positions_log.csv         # V14: one row per open position per run, with
│   │                             # Alpaca's real avg_entry_price
│   └── fills.csv                 # V14: actual executions only, deduped by order id.
│                                 # Ground truth for slippage vs the CSV signal price
├── config.py                     # all settings + Alpaca credentials via os.getenv
├── main.py                       # entry point with MODE switch
├── dashboard.py                  # Streamlit dashboard - Bloomberg institutional style
│                                 # 6 tabs: Paper Trader, Strategy Results, Auto
│                                 # Selection, ML Analysis, Performance, Recent
│                                 # Trading Events
├── override_walk_forward.py      # V14: walk-forward validation of the momentum
│                                 # override across 4 windows, corrected vs V12-legacy
├── mom_override.py               # V12 single-window override grid (SUPERSEDED by
│                                 # override_walk_forward.py; kept for provenance)
├── walk_forward_test.py          # one-off script: momentum-feature robustness check
│                                 # across 4 historical window lengths (see Version 10)
├── run_paper_trader.py           # standalone script for GitHub Actions
├── test_performance.py           # standalone test harness for evaluation/performance.py
├── test_engine_synthetic.py      # V13: 18 network-free assertions on run_backtest.
│                                 # Hand-computed expected values on synthetic prices.
│                                 # MUST PASS before trusting any backtest result.
├── test_account_log.py           # V14: 22 assertions on the Alpaca measurement layer
│                                 # (fake client, incl. the real V11 leverage scenario)
├── test_momentum_override.py     # V14: 13 assertions pinning the override rule to its
│                                 # documented behaviour, incl. both V12 bug regressions
├── test_trading_date.py          # V14: 14 assertions - trading date comes from
│                                 # market data, not the wall clock
├── test_alpaca_executor.py       # V14: 20 assertions - order-status normalization
│                                 # and fail-closed duplicate-order guard
├── test_auto_selector_fallback.py# V13: 7 network-free assertions on auto_select's
│                                 # failure handling and known-good fallback
└── CONTEXT.md                    # this file
```

---

## Dashboard
- Live: https://requantara-e4epzjkmfgtgb9almgh3le.streamlit.app
- Built with Streamlit Community Cloud, auto-updates when GitHub Actions commits new
  paper trading data
- Style: Bloomberg meets modern fintech — dark navy, Inter font, JetBrains Mono for data
- 6 tabs: Paper Trader, Strategy Results, Auto Selection, ML Analysis, Performance,
  Recent Trading Events
- Portfolio summary row (value, P&L, return %, best/worst performer) sits above the tabs
- Note: repo currently public for Streamlit — may go private later; redeploy/reboot
  from share.streamlit.io if it ever goes dark after a visibility change

---

## Config Settings
```python
TICKERS = ["NVDA", "TSLA", "AAPL", "JPM", "IBM"]
START = "2015-01-01"
END = "2024-01-01"
FAST_WINDOW = 20
SLOW_WINDOW = 50
EMA_FAST = 20
EMA_SLOW = 50
STOP_LOSS = 0.05

# TWO SEPARATE CONSTANTS - DO NOT MERGE THEM AGAIN. See Version 13, Fix 1.
BACKTEST_POSITION_SIZE = 1.0   # fraction of ONE ticker's own capital (single-ticker sim)
LIVE_POSITION_SIZE = 0.20      # fraction of TOTAL account equity (shared across 5 tickers)

INITIAL_CAPITAL = 10000

# Alpaca (loaded from environment variables)
ALPACA_KEY = os.getenv("ALPACA_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET")
ALPACA_BASE_URL = "https://paper-api.alpaca.markets"
```

---

## Alpaca Integration
- Paper trading account: $10,000
- SDK: alpaca-py
- Execution: MarketOrderRequest, TimeInForce.DAY
- Position sizing: 20% of portfolio per ticker (5 tickers × 20% = 100% invested, no
  margin). Was 50%, which produced ~1.91x leverage and caused buying-power rejections.
- Order verification: `submit_and_verify()` polls order status after submission,
  because Alpaca can accept an order into the system and reject it seconds later.
  A rejected order returns `(None, None)` so nothing is logged as executed.
- Position check: skips BUY if position OR pending order exists (duplicate-order fix)
- **Stop loss enforcement**: `check_stop_loss()` in `alpaca_executor.py` compares
  Alpaca's live `avg_entry_price` against current price before evaluating the model's
  signal. If drawdown from entry ≤ -5%, force-sells regardless of signal. CONFIRMED
  WORKING live on NVDA, Jun 24, 2026.
- `execute_signal()` always returns a `(result, reason)` tuple, never a bare value —
  `reason` is `"STOP_LOSS"`, `"SIGNAL"`, or `None`. This is what lets the CSV and the
  Recent Trading Events feed know *why* a trade happened, not just that it happened.
- Secrets stored in GitHub Actions secrets (ALPACA_KEY, ALPACA_SECRET)
- Local testing: set via `$env:` in PowerShell

---

## Strategies Built
| Strategy | File | Key Parameters |
|----------|------|----------------|
| SMA Crossover | sma_crossover.py | fast=20, slow=50 |
| EMA Crossover | sma_crossover.py | fast=20, slow=50 |
| SMA + RSI Combined | sma_crossover.py | fast=20, slow=50, rsi_high=70 |
| Bollinger Bands | bollinger_signal.py | window=20, num_std=2 |
| Logistic Regression | ml_signal.py | 18 features, walk forward split |
| Random Forest | ml_signal.py | 100 trees, 18 features, walk forward split |

**Current live strategy per ticker (as of the Aug 14 2026 V13 re-selection):**
NVDA → EMA Crossover, TSLA → SMA Crossover, AAPL → Logistic Regression,
JPM → SMA Crossover, IBM → Bollinger Bands.

Previous assignment (Jun 29 – Aug 14 2026): NVDA → Random Forest, TSLA → Logistic
Regression, AAPL → Logistic Regression, JPM → SMA Crossover, IBM → Bollinger Bands.
NVDA and TSLA changed as a direct consequence of the Version 13 sizing/engine fixes
re-scoring every candidate — not because of any new research finding.

(Auto-selected from 2015-2024 backtest composite scores — see "Auto-Selector vs Live
Performance" note below for why this doesn't always match recent live results.)

---

## ML Features (18 total)
**Original 14:** EMA_gap, RSI, BB_position, Momentum_5, Momentum_10, Momentum_20,
Momentum_30, RSI_slope, Volatility_10, Volatility_20, SMA_gap, Price_vs_SMA20,
Price_vs_SMA50, BB_width

**Added in Version 10:** Mom_accel, ADX_14 (10-day momentum acceleration and 14-period
Average Directional Index — kept after testing, see Version 10 section)

**Added in Version 12:** Ret_vol_norm (daily return / Volatility_20, clipped ±10) and
RSI_x_trend ((RSI - 50) × ADX_norm — "high RSI is bearish normally, bullish once trend
strength confirms it"). BBpos_x_trend was tested and removed for collinearity with
RSI_x_trend, which degraded LR on all five tickers.

**Tested and rejected in Version 10:** Streak, Streak_Squared (consecutive-day-count
features — removed after failing on both models, see Version 10 section)

Single source of truth: `FEATURE_COLS` constant defined once at the top of
`strategy/ml_signal.py`. `run_ml_strategy`, `run_rf_strategy`, and
`paper_trader.py`'s `generate_current_signal` all import and use this same constant —
no per-function local copies, so the feature set can't silently drift between
backtest/research code and live signal generation.

---

## Backtest Results Reference (2015-2024)

### ✅ CURRENT — Auto Selection, regenerated Aug 14 2026 on the Version 13 engine
Fractional shares, working stop loss, `BACKTEST_POSITION_SIZE = 1.0`.
**This is the only table on this page that reflects current code.**
```
Ticker  Best Strategy         Score   Sharpe  Return   MaxDD
NVDA    EMA Crossover         1.7169  1.152   495.83%  -50.25%
TSLA    SMA Crossover         1.4049  0.964   402.38%  -60.63%
AAPL    Logistic Regression   1.2086  1.168   201.84%  -26.35%
JPM     SMA Crossover         0.8833  0.900   101.14%  -22.98%
IBM     Bollinger Bands       0.8276  0.964    32.56%   -6.49%
```
No near-tie warnings fired — every winner had a >0.05 margin over second place.

ML head-to-head from the same run (test period 2019-07-03 → 2023-12-29):
```
Ticker  LR Sharpe   RF Sharpe   Better Model   (winner overall)
NVDA    0.911       1.028       RF             EMA Crossover beat both
TSLA    0.822       0.515       LR             SMA Crossover beat both
AAPL    1.168       0.930       LR             LR won outright
JPM    -0.397       0.209       RF             SMA Crossover beat both
IBM     0.534       0.433       LR             Bollinger Bands beat both
```
Note JPM's LR is now outright negative (-44.93% return, Sharpe -0.397). Rule-based
strategies won 4 of 5 tickers on the corrected engine — a meaningful reversal from the
pre-Version-13 picture and worth investigating rather than accepting at face value.

⚠️ **Caveat on all of the above:** these are per-ticker, fully-invested, single-ticker
results with no transaction costs and same-close fills. They are a strategy-comparison
bench, not a forecast of account performance.

---

### ⚠️ STALE — everything below this line predates Version 13
Retained for historical reasoning only. Produced with whole-share flooring, a stop loss
that re-bought on the same bar, and `POSITION_SIZE = 0.50`. **Do not compare any new
result against these numbers.** The qualitative findings (which features mattered, which
tickers overfit, the TSLA/IBM momentum misread) are probably still directionally valid;
the figures are not.

### Multi-Strategy Results (test period, default parameters)
```
Ticker  Strategy              Return   Sharpe   MaxDD
NVDA    EMA Crossover         138.72%  0.973    -36.77%
NVDA    Bollinger Bands        21.47%  0.820     -9.94%
NVDA    SMA Crossover          88.41%  0.807    -39.69%
AAPL    EMA Crossover          44.30%  0.766    -13.20%
JPM     SMA Crossover          34.08%  0.755    -13.00%
NVDA    SMA+RSI Combined       59.09%  0.725    -37.44%
AAPL    SMA+RSI Combined       26.70%  0.706    -14.26%
AAPL    SMA Crossover          34.28%  0.703    -15.66%
TSLA    EMA Crossover         107.15%  0.702    -43.15%
JPM     SMA+RSI Combined       23.58%  0.629     -9.46%
TSLA    SMA Crossover          68.52%  0.606    -31.35%
TSLA    SMA+RSI Combined       30.50%  0.437    -27.70%
JPM     Bollinger Bands         9.49%  0.357     -8.44%
JPM     EMA Crossover          10.61%  0.305    -15.21%
TSLA    Bollinger Bands         7.86%  0.300     -8.45%
AAPL    Bollinger Bands         5.25%  0.288     -4.14%
```

### ML Results Summary (original 14-feature set)
```
Ticker  LR Sharpe   RF Sharpe   Better Model
TSLA    1.252       0.675       LR
AAPL    0.760       0.928       RF
NVDA    0.707       0.850       RF
IBM     0.680       0.887       RF
JPM     0.043       0.405       RF
```
Key finding: RF dominates stable data-rich stocks, LR dominates volatile ones. NN
deferred — insufficient daily data (~625 training days) to outperform simpler models.
NN viable in Quantara NN project (minute data, 50k-120k samples per ticker).

### Optimization Results (EMA Crossover, tuned fast/slow windows)
```
Ticker  Fast  Slow  Train Sharpe  Test Sharpe  Overfit Gap
NVDA    36    193   1.853         1.267         0.586
TSLA    7     21    2.218         0.445         1.773
AAPL    5     24    1.883         0.373         1.510
JPM     33    113   1.279         0.289         0.990
```
Key finding: TSLA and AAPL severely overfit — unreliable parameters. Only NVDA shows
robust optimization. **Important:** these tuned parameters are NOT what the live
auto-selector uses — `auto_selector.py`'s `evaluate_rule_based()` always runs default
20/50 EMA Crossover, never these optimized windows. The optimizer is a separate,
standalone analysis path.

### Auto Selection Results (composite score, 2015-2024 backtest)
```
Ticker  Best Strategy         Score   Sharpe  Return   MaxDD
TSLA    Logistic Regression   1.1713  1.018   236.07%  -36.60%
NVDA    EMA Crossover         1.1044  1.062   191.86%  -36.77%
IBM     Random Forest         1.0240  1.243   65.71%    -9.65%
AAPL    EMA Crossover         0.8541  0.917   67.43%   -13.09%
JPM     SMA Crossover         0.7898  0.874   45.92%   -13.03%
```

**Composite Score Formula:**
`Score = (Sharpe × 0.5) + ((1 - abs(MaxDrawdown/100)) × 0.3) + (TotalReturn/100 × 0.2)`
- Above 1.0 = genuinely good
- 0.5 to 1.0 = acceptable
- Below 0.5 = failing

---

## ⚠️ Auto-Selector vs Live Performance — Why They Can Disagree
The auto-selector scores the 2015-2024 backtest only — it has zero awareness of the
live paper trading log. It is not measuring the same thing as live performance, and the
two are not in conflict even when they appear to disagree:
- NVDA and JPM's strong backtest scores come from riding multi-year trends with very
  few trades — the exact same low-frequency, slow-to-exit behavior that shows up live
  as NVDA going 0-for-48-days and JPM holding a single trade for 34 days.
- The live window (weeks, not years) is far too short to say whether current
  drawdowns are normal noise inside a longer trend (consistent with backtest behavior)
  or an actual trend break the backtest never saw. Don't read live underperformance as
  the backtest being "wrong" — they're different sample periods, and the live one is
  still tiny by comparison.

---

## Version 9 — Performance Analytics (COMPLETE)
Full research report generated: `Quantara_Version9_Report.docx` (Apr 29 – Jun 16, 2026
reporting period). Built the entire analytics layer this version is named for:

**Trade segmentation** (`evaluation/performance.py`, `build_trade_segments()`): walks
the CSV chronologically per ticker, closes a "segment" on strategy change or BUY→SELL
flip, tracks entry/exit price/date, duration, P&L, P&L%, and OPEN/CLOSED status.
Tracked at ticker+strategy granularity, then rolled up to ticker-level summaries
(`ticker_summary()`) so both views exist without duplicating logic. Unrealized P&L on
open positions marked with `*` rather than shown as a separate competing number.

**Key finding — trade frequency divide:** Rule-based crossover strategies (NVDA, JPM)
barely trade once a position is open — slow 20/50-period signals are designed to
filter noise and are correspondingly slow to register anything short of a full trend
reversal (NVDA: 0 closed trades in 48 days; JPM: 1 trade in 34 days). ML strategies
(TSLA, IBM) trade far more often since they're trained to predict next-period
direction. Not a bug — different strategies solving different problems, not directly
comparable on trade count.

**Key finding — ML momentum misread (TSLA & IBM):** Both LR (TSLA) and RF (IBM) exit
near local tops and re-enter after the best part of the move has already passed:
- **TSLA:** ran $376→$445 (May 14 peak, +18.4%). Model exited May 2 at $390.82 (missed
  most of the run), re-entered May 14 at $445.27 right before the reversal, closed
  that re-entry at -$125.81 (-6.3%) on May 21.
- **IBM:** ran $233→$329.23 (Jun 3 peak, +41%). Model exited May 22 at $252.97 (missed
  most of the run), didn't re-enter until Jun 9 at $280.82 — well after the peak, on
  the way down. IBM's drawdown from that live peak reached -18.4%, the worst in the
  portfolio.
- Likely cause: RSI/BB_position features read sustained momentum as "overextension"
  rather than confirmed trend. This became the explicit subject of the Version 10
  investigation below.

**Win/Loss stats** (`win_loss_stats()`, 16 closed trades through Jun 16): Win Rate
56.3%, Avg Win +$74.48, Avg Loss -$57.73. Biggest win: +$178.90 (IBM, May 2–22).
Biggest loss: -$125.81 (TSLA, May 14–21).

**Drawdown tracker** (`drawdown_tracker()`): tracks each ticker's running peak price
*since live tracking began*, not the backtest peak. This is what first surfaced that
every ticker was sitting past the 5% stop loss threshold from its own live peak with
no automatic exit — the gap that led directly to the Stop Loss CSV Accuracy Fix below.

**Signal quality score** (`signal_quality_score()`): next-day directional accuracy on
BUY signals. Most diagnostic for TSLA/IBM (LR/RF are explicitly trained on next-period
direction — their sub-40% scores are a real, meaningful underperformance finding and
the quantitative confirmation of the momentum misread above). Less applicable to
NVDA/JPM/AAPL since crossover strategies aren't designed to win on a daily basis, only
to ride confirmed multi-week trends.

**Weekly signal quality** (`signal_quality_weekly()`): built and tested, held back
from the dashboard. Sample sizes too small (2-5 signals/ticker/week) to be stable —
swings between 0% and 100% week to week on pure noise for most tickers. AAPL showed a
loose upward trend (~50% late April → 100% by mid-June) but flagged as preliminary
only given sample size. Revisit with more data or a rolling window instead of discrete
week buckets.

**Problem detection** (`detect_problems()`): scans switch flags, drawdown vs stop loss
threshold, and signal accuracy (only flags accuracy if ≥10 signals checked, to avoid
noise on small samples). Dashboard groups flags by ticker with severity icons (🔴
CRITICAL / 🟡 WARNING / 🟢 OK) rather than one flat list.

---

## Version 10 — Momentum Feature Investigation (COMPLETE, no live changes)

**Hypothesis going in:** TSLA (LR) and IBM (RF) showed the recurring momentum-misread
pattern documented in Version 9 — exiting near local tops, re-entering after
pullbacks. Both tickers' ADX_14 distributions (computed during this investigation)
showed they spend >50% of their time in a "trending" regime (median ADX ~32-33), yet
their feature sets were dominated by mean-reversion-flavored indicators (RSI,
BB_position, BB_width, Price_vs_SMA20/50 — 6 of the original 14 features). Hypothesis:
adding explicit momentum-persistence features would let LR/RF correctly weight
sustained trends instead of reading them as overextension.

**Features built and tested**, added to `build_features()`:
- `Streak` — signed consecutive up/down day count
- `Streak_Squared` — magnitude-only version, tested to check for a non-linear
  relationship (e.g. "short streak = momentum, long streak = exhaustion")
- `Mom_accel` — 10-day momentum minus 10-day momentum from 5 days ago
- `ADX_14` — standard 14-period Average Directional Index, direction-agnostic trend
  strength (required adding High/Low columns to `data/loader.py`'s `load_data()`,
  which previously kept only Close)

**Result 1 — `Streak` rejected.** RF ranked `Streak` dead last (lowest importance) on
every single ticker, no exceptions. LR's coefficient was negative on every ticker
(implying long streaks predict reversal, not continuation — opposite of the
hypothesis). TSLA and IBM, the actual target tickers, both got WORSE on both models:
```
              LR Sharpe                  RF Sharpe
TSLA:  1.252 -> 1.093 (-0.159)     0.675 -> 0.509 (-0.166)
IBM:   0.685 -> 0.504 (-0.181)     1.162 -> 0.944 (-0.218)
```
Meanwhile NVDA and AAPL — not target tickers — improved on both models. First sign the
new features might matter more for NVDA/AAPL than for the tickers they were built for.

**Result 2 — `Streak_Squared` also rejected.** Added specifically to test whether the
relationship was non-linear (RF should detect that natively if it existed). RF ranked
`Streak_Squared` dead last on every ticker — even lower than plain `Streak`. LR showed
only small (<0.1) Sharpe changes either direction. Conclusion: not a linearity
problem — the feature isn't predictive in raw or squared form, on either model, for
any ticker. Decided not to pursue manual bucketing into "strong/weak" categories,
since RF already had full access to find any threshold effect on its own and
consistently didn't.

**Result 3 — NVDA/AAPL "improvement" was a false lead, caught by walk-forward check.**
A single 50/50-split composite score comparison initially suggested NVDA-RF
(16-feature) would beat NVDA's live EMA Crossover by a wide margin. This comparison
was invalid — the EMA baseline number came from a different, unverified historical
test window than the new RF run. Recomputed fairly (same exact window, default 20/50
EMA via `auto_selector.py`'s actual logic) across 4 robustness windows (all starting
2015-01-01, ending 2024/2023/2022/2021 — note: these are 4 different total-history
lengths each internally split 50/50, NOT 4 independent disjoint train/test periods):
- **NVDA:** EMA beat RF-with-momentum in ALL 4 windows, often by ~2x margin. RF win
  rate: 0%.
- **AAPL:** LR-with-momentum beat EMA in 2/4 windows (most recent two), lost the other
  2 (lost badly on the 2022 window). LR win rate: 50% — a coin flip, not a finding.

Conclusion: the single-window NVDA result was a baseline-comparison error, not a real
edge. AAPL's split result doesn't clear the bar for a robust improvement either.

**Final decision:** `Streak` and `Streak_Squared` removed entirely from
`build_features()` and `FEATURE_COLS`. `Mom_accel` and `ADX_14` were KEPT — neither
actively hurt anything in any test, `ADX_14` was NVDA's #1 RF feature importance in
every run, and `Mom_accel` was consistently mid-pack to positive across all five
tickers. **No live strategy assignment changed** as a result of this investigation:
TSLA still LR, IBM still RF, NVDA and AAPL still EMA Crossover, JPM still SMA
Crossover. Purely a backtest research investigation.

**Bigger-picture finding worth remembering:** IBM's ADX profile (median ~33, mean
~35.4) is nearly identical to TSLA's (median ~31.6, mean ~35.1) — IBM is NOT the
"boring mean-reverting" stock its reputation suggests; it trends just as much as TSLA
on average. The original momentum-misread problem is real and confirmed, but explicit
momentum-persistence features (in the three forms tested here) were not the fix. The
actual cause may lie elsewhere — possibly in how RSI/BB features are scaled/weighted
relative to momentum features rather than momentum features being absent, or in the
train/test split methodology itself. **This remains unresolved — see Version 11.**

**Process note:** this thread is a good case study in why the walk-forward check
matters most exactly when a single-window result looks convincing, not despite it.
The NVDA "win" looked clean and would have been easy to ship without the second check.
Apply the same standard before trusting any single backtest-window result going
forward — the same instinct that already caught TSLA/AAPL's EMA Crossover overfitting
in the original optimizer work.

---

## Version 10 — Stop Loss CSV Accuracy Fix (COMPLETE)
**The problem:** when the live stop loss force-sells a position, the CSV log was still
writing the MODEL's opinion (Signal/Action), not what Alpaca actually executed. NVDA's
June 24, 2026 stop loss trigger logged as `Signal: 1, Action: BUY` even though Alpaca
force-sold the position that same day. This made `build_trade_segments()` show NVDA as
one continuous 58-day OPEN position straddling the real exit, and made it genuinely
hard to figure out what had happened without manually cross-referencing the CSV
against Alpaca's activity feed — the original complaint that started this thread.

**Fix, across 3 files:**
- **`alpaca_executor.py`** — `execute_signal()` now ALWAYS returns a `(result, reason)`
  tuple instead of a single value. `reason` is `"STOP_LOSS"`, `"SIGNAL"`, or `None`,
  consistent across every return path (stop loss, BUY, SELL, both skip cases). Also
  fixed a pre-existing bug in `get_position()` where the except path returned
  `None, None` (a tuple) instead of `None` — meant `position is None` checks could
  silently misbehave.
- **`paper_trader.py`** — call site updated to
  `order_result, exit_reason = execute_signal(...)`. If `exit_reason == "STOP_LOSS"`,
  the logged `Signal`/`Action` are OVERRIDDEN to `0`/`"SELL/HOLD"` before writing to
  the CSV, regardless of what the model originally recommended. The CSV is now a
  record of what actually happened to the money, not the model's opinion — the
  model's opinion is research data, independently recoverable by re-running
  `generate_current_signal`, not something the live log needs to preserve at the cost
  of misrepresenting the actual trade.
- **`evaluation/performance.py`** — new `Exit_Reason` column (7th CSV field, present
  only on rows written after this fix). `build_trade_segments()` reads it via `.get()`
  for backward compatibility with pre-fix rows, defaulting to `"SIGNAL"` if missing.

**Known one-off historical exception:** NVDA's Jun 24, 2026 row predates this fix, so
it was manually corrected (Signal 1→0, Action BUY→SELL/HOLD) but deliberately left at
6 fields — no `Exit_Reason` backfilled, to avoid a CSV column-count parse crash.
`build_event_feed()` has a small hardcoded `KNOWN_EXIT_REASON_OVERRIDES` dict mapping
this one specific (ticker, timestamp) pair to `"STOP_LOSS"` manually. Not a pattern to
extend — a one-time documented correction for data that predates tracking. Every stop
loss trigger from this point forward logs correctly with no manual intervention.

---

## Version 10 — "Recent Trading Events" Dashboard Tab (COMPLETE)
New 6th dashboard tab, built on the Stop Loss CSV fix above. Answers "what happened to
my portfolio and why" without cross-referencing Alpaca manually — the actual fix to
the "7 steps to find out NVDA sold" problem.

**`build_event_feed()`** (`evaluation/performance.py`) generates one narrated entry
per: closed trade exit (tagged STOP_LOSS vs SIGNAL, with dollar gain/loss), new entry
(BUY), and strategy switch (detected by walking the raw log per ticker, flagging any
day Strategy differs from the prior day). Returns a list sorted most-recent-first by
default. No share counts in messages — the CSV doesn't log real Alpaca quantities,
only an implied $2k-per-ticker assumption used elsewhere on the dashboard, and
dollar-only language was judged more honest than presenting a fictional quantity.

**Example (verified working on NVDA's real stop loss event):**
> 🔴 NVDA sold @ $200.04 — stop loss (5%) triggered (down 6.2% from your $213.17
> entry). You realized a loss of $123 on this position.

**Dashboard tab features:**
- Date range filter (7/14/30/90 days, or All time)
- Ticker filter dropdown
- Sort toggle: "Most Recent" (default, chronological) or "Severity" (Critical →
  Negative → Warning → Positive → Neutral; Python's stable sort preserves recency
  within each severity group)
- Color/icon coding: CRITICAL = red 🔴 (stop loss), NEGATIVE = red 🔸 (signal loss),
  POSITIVE = green 🟢 (signal gain), WARNING = amber 🟡 (strategy switch), NEUTRAL =
  grey ⚪ (buy — intentionally muted/low-opacity, since most days are routine entries
  that shouldn't visually compete with things that need attention)

---

## Version 11 — Live Readiness Audit (COMPLETE)
Triggered by reviewing 3.5 months of accumulated data before considering real capital.
Four findings, two of them significant.

### Finding 1 — The account was running ~1.91x leverage (fixed)
`POSITION_SIZE = 0.50` means 50% of *total portfolio value* per position. With four
positions open simultaneously that's ~200% exposure, funded by Alpaca margin:

Account equity: $12,010.34
Total position market value: $22,907.63
Implied margin debt: $10,897.29
Effective leverage: 1.91x

The negative "Cash" figure on the Alpaca dashboard — earlier dismissed as a display
quirk and relabelled "Buying Power" — was margin debt the whole time. Roughly half the
headline +20.10% return is leverage amplification; the delevered equivalent is ~+10.5%.

Fixed by setting `POSITION_SIZE = 0.20`. Sizing rationale: the common "2% rule" is
**risk per trade, not position size**. Position size = risk% ÷ stop distance%. With a
5% nominal stop (≈9% in gap scenarios), 2% risk per trade implies a 20-22% position.
Five tickers × 20% = exactly 100% invested, zero margin.

### Finding 2 — Genuine outperformance vs buy & hold

Equal-weight buy & hold, same 5 tickers, Apr 29 – Aug 13: +4.48%
Quantara actual: +20.10%
Outperformance: +15.62 pts
Delevered equivalent: ~+10.5% (≈ +6 pts)

Per-ticker B&H: NVDA +5.12%, TSLA **-12.90%**, AAPL +11.65%, JPM +17.25%, IBM +1.26%.
The edge came from trading around TSLA's decline and sitting out IBM's mid-July
collapse ($306 → $217). This is the first evidence that the system is doing something
beyond tracking the market — a meaningful update from the July read, which found no
such evidence.

### Finding 3 — Rejected orders were logged as successful (fixed)
TSLA's Jul 22 re-entry (14.4659 sh) was **rejected by Alpaca**, almost certainly for
insufficient buying power given the 50% sizing. But `execute_signal()` only checked the
return value of `submit_order()`, not the order's subsequent status — so the CSV logged
it as `SIGNAL` and `build_trade_segments()` opened a phantom position at $378.93. The
dashboard showed TSLA at **-13.57%** while Alpaca showed **+9.2%** from a real $311.49
entry opened Jul 27.

Two fixes:
- `submit_and_verify()` in `alpaca_executor.py` — polls order status for ~10s after
  submission, catching accept-then-reject. Rejected orders log nothing.
- `reconcile_open_segments()` in `evaluation/performance.py` — for any segment still
  marked OPEN, entry price and P&L are taken from Alpaca's live position rather than
  the CSV. Segments Alpaca isn't actually holding get dropped. Self-correcting from
  here on.

**Related slippage finding:** the CSV logs the yfinance *close* at signal time, but
Alpaca fills at the *next open*. TSLA's stop signal was $369.57; the actual fill was
$376.06. All dashboard P&L figures are approximations that drift from Alpaca's real
numbers — one reason `reconcile_open_segments()` matters.

### Finding 4 — Stop loss behaviour, correctly characterised
An earlier claim in this project that the stop "always fires 3-4 points late" was
**wrong** — it measured against CSV close prices instead of Alpaca's real
`avg_entry_price`. Corrected:

TSLA (real entry $392.31): Jul 17 -0.32% → Jul 20 -2.92% → Jul 21 -5.80% TRIGGER ✓
AAPL (real entry $340.08): Jul 30 -0.56% → Jul 31 -1.96% → Aug 03 -9.17% TRIGGER ✗

TSLA behaved correctly. AAPL gapped over a weekend from -1.96% straight to -9.17%,
skipping the threshold entirely. **The stop works on gradual declines and cannot work
on gaps** — you trigger on a close and fill at the next open, so the gap always lands
in that window regardless of where the threshold sits.

**Lowering the threshold to 4% was evaluated and rejected.** Simulated against real
Apr–Aug prices:

| Threshold | Stops fired | Summed return |
|---|---|---|
| 3% | 9 | 26.50% |
| 4% | 7 | 26.39% |
| 5% | 4 | 25.47% |
| 6% | 3 | 24.56% |

4% beats 5% by 0.92 pts across five tickers and three months — noise, not edge. And
critically, replaying AAPL's gap: **both 4% and 5% first trigger on the same day**,
identical outcome. Separately, of 155 occasions a holding sat in the -4% to -5% band,
49% recovered the next close and 51% fell further — a coin flip with no exploitable
information. Threshold stays at 5%.

**The only effective gap defense is position sizing.** AAPL's -9.17% gap cost -4.6% of
equity at 50% sizing; at 20% the same gap costs -1.8%. Already addressed by Finding 1.

### Evaluated and deliberately NOT adopted
- **Resting stop orders at Alpaca** (`StopOrderRequest` / bracket orders). Would give
  true intraday stops independent of the scheduler, but Alpaca does not support stops
  or brackets on **fractional shares**. Whole-share sizing sets an account-size floor —
  at 20% sizing and JPM near $365, you'd need ~$1,825 just to buy one share of the
  priciest name. Since the planned live account is $100–$1,000, fractional shares are
  non-negotiable. Also adds stop lifecycle management (cancel before manual sells,
  filter resting stops out of `get_pending_orders`, handle partial fills, static stops
  that don't trail). Revisit only if the account grows substantially.
- **VPS migration** (Kamatera box + DuckDNS already provisioned). Would enable
  intraday stop polling, but that does **not** solve gaps — AAPL's move happened while
  markets were closed. Recommended split when pursued: keep the daily signal run on
  GitHub Actions (free, fails loudly, git commit flow already solved); move the
  dashboard to the VPS first (immediate benefit — lets the repo go private, zero
  trading risk), then Quantara NN when built, then intraday monitoring only if
  intraday exits are genuinely wanted. Main risk: VPS cron dies silently where GitHub
  Actions shows a red X. Uptime monitoring is a prerequisite.
- **Note:** GitHub Actions auto-disables scheduled workflows after 60 days of repo
  inactivity. Not yet an issue, but a real hazard for an unattended system.

### System alerts now carry dates
`detect_problems()` returns `When` and `Detail` per flag. The three check types are
dated according to their actual semantics: strategy switches are discrete dated events
with a recent-switch history, drawdown breaches are dated by when the peak was set plus
days-since, and signal accuracy shows the date range it's measured over. Surfaced that
IBM's drawdown alert had been firing continuously for 70+ days off a peak never
actually held through — very different meaning from an alert that started yesterday.

## Alpaca Live Order History
First real paper trades placed May 24, 2026: NVDA, AAPL, JPM (a duplicate NVDA order
from manual testing was cancelled). TSLA and IBM have each sold off and re-entered
multiple times through normal signal flow since. NVDA completed its first full
stop-loss-triggered exit on Jun 24, 2026 (sold at $200.04, -7.7% from entry $216.72,
-$123 realized), then re-entered and has traded normally since under the now-corrected
logging.


---

## Key Technical Decisions
- Data source: yfinance (free, clean, sufficient for daily backtesting)
- Returns tracked as actual dollar portfolio value, not percentage multipliers
- ⚠️ **CORRECTION (V13):** the long-standing claim that `Position = Signal.shift(1)`
  "prevents lookahead bias" is **false**. Every signal generator sets a `Position`
  column, but `run_backtest` reads `row["Signal"]` and has never touched `Position` —
  it is dead code. The backtest executes at the same bar's close the signal was
  computed on. This is not lookahead (features at close t, trade at close t), but it IS
  optimistic relative to live, which fills at the next open. Genuine fix is item 3 in
  Next Session.
- Stop loss: exit if price drops 5% below entry — enforced in BOTH backtest AND live
  execution (live enforcement added and confirmed working Jun 2026; backtest stop was
  found in V13 to have been re-buying on the same bar and is now fixed)
- Position sizing: **two separate constants** — `BACKTEST_POSITION_SIZE = 1.0` (of one
  ticker's own capital) and `LIVE_POSITION_SIZE = 0.20` (of total account equity).
  These are different quantities and must never be merged. See Version 13, Fix 1.
- Backtest uses **fractional shares**, matching Alpaca live execution. Whole-share
  flooring made effective position size price-dependent (V13, Fix 2).
- Strategy selection is **all-or-nothing**: any candidate failure abandons the run and
  keeps the last known-good assignment rather than selecting from a partial field.
- Sharpe annualized with sqrt(252)
- Walk forward split: first 50% train, second 50% test
- Alpaca execution: MarketOrderRequest, TimeInForce.DAY
- Duplicate order prevention: checks both open positions AND pending orders
- Trade segment definition: closes on strategy change OR BUY→SELL flip within the same
  strategy — tracked at ticker+strategy granularity, rolled up to ticker-level
  summaries so both views exist without duplicating logic
- GitHub Actions commit order: commit local changes BEFORE `pull --rebase`, then push
  — avoids "cannot pull with rebase: unstaged changes" failures
- The live CSV log reflects what Alpaca actually executed, never just the model's raw
  signal — model opinion is recoverable separately by re-running the model, but the
  permanent record should never misrepresent the real trade
- `FEATURE_COLS` is defined exactly once, in `ml_signal.py`, and imported everywhere
  else it's needed — no per-function local copies of the feature list

---

## Key Research Findings
- EMA Crossover dominates momentum stocks (NVDA, AAPL) — in backtest
- LR dominates highly volatile stocks (TSLA) — in backtest
- RF dominates stable data-rich stocks (IBM, AAPL) — in backtest
- Rule-based beats ML when training data is limited
- RSI filter too restrictive on momentum stocks
- Bollinger Bands better suited for mean-reverting assets
- More training data (2015 vs 2020) significantly improves ML results
- TSLA optimization severely overfits — unreliable parameters
- Composite score captures return AND safety simultaneously
- TSLA and IBM both show a confirmed momentum misread: LR/RF exit near local tops,
  re-enter after pullbacks. Quantified in Version 9, investigated (unresolved) in
  Version 10.
- Live trade frequency reveals a structural divide: rule-based strategies barely trade
  once positioned; ML strategies trade often — different tradeoffs, not a bug
- Backtest auto-selector scores and live performance measure different time windows
  and are not contradictory even when they appear to disagree
- IBM's ADX trend-strength profile is nearly identical to TSLA's — IBM is not the
  "boring" stock its reputation suggests
- Adding momentum-persistence features (Streak, Streak_Squared) did not fix the
  TSLA/IBM momentum misread — tested properly via walk-forward validation, rejected.
  The fix for this problem requires a different approach (see Version 11)
- **Model override beats model retraining for rare-event capture — now walk-forward
  validated (V14).** Five attempts to fix the misread by giving the model better
  information all failed, including one where the model demonstrably learned the exact
  conditional wanted. Changing what the model is *allowed to do* worked where changing
  what it *knows* did not. Survives 4-window validation on AAPL and TSLA
- **The project keeps finding effects on tickers it wasn't targeting.** Versions 9/10/12
  all aimed at TSLA and IBM. Streak improved NVDA/AAPL and failed the targets; the
  override's strongest result is AAPL (36/36 cells) while IBM outright rejects. Worth
  treating "which ticker is this actually for?" as an open question rather than an
  assumption inherited from Version 9
- **Effects whose best parameters sit at the edge of the tested grid are not yet
  understood.** The override improves monotonically as the RSI trigger falls and the
  trail widens, meaning the optimum was never bracketed. Always check whether a winning
  configuration is an interior maximum before believing the mechanism you assigned to it

---

## Known Issues / Technical Debt

### Opened in Version 14 (NOT yet fixed)
- **No rebalancing logic.** Position sizing applies only at entry, so a position opened
  under the old 0.50 regime stays oversized until it cycles out. JPM is currently 44% of
  equity against a 20% target. Live confirmed Aug 14 2026.
- **`get_recent_data()` fetches a fixed 300 calendar days** regardless of what the
  strategy needs. Combined with the live training-window bug below, this determines what
  the live model sees.
- **The buy & hold control arm in `override_walk_forward.py` records Sharpe and drawdown
  but not total return**, so it cannot be compared to Version 11's return-based live
  finding on equal terms.
- **AAPL's LR signal flipped BUY -> SELL on a $0.67 price difference** (Aug 14, two runs
  5 hours apart). The model was on its decision boundary. A hard 0/1 `predict()` hides
  this; `predict_proba()` would expose it. Worth considering a confidence threshold.

### Opened in Version 13 (found during the correctness audit, NOT yet fixed)
- **Live LR/RF models are trained on a stale window.** In `paper_trader.py`,
  `generate_current_signal()` fetches a 300-day lookback, fits the `StandardScaler` on
  the **entire** window including today's row (minor leakage), then trains on only
  `[:midpoint]` — roughly days 300 to 150 ago — and predicts today. **The live model has
  never seen the most recent ~5 months of data**, and is a materially different model
  from the one `auto_selector` scores. High priority.
- **`Win_Rate` is not a win rate.** `get_metrics` computes `(daily_returns > 0).mean()`
  — the fraction of *days* the portfolio rose, with flat cash days counting as losses.
  This is why the Aug 14 run shows 25-30% "win rates" that look alarming and aren't
  comparable to `win_loss_stats()`'s trade-level 56.3%. Rename or replace.
- **Sharpe has no risk-free rate.** `(mean/std) * sqrt(252)` with no `rf` subtraction.
  In a 4-5% cash environment that is ~0.3-0.5 of free Sharpe on every strategy, and it
  systematically flatters strategies that hold cash least.
- **No transaction costs or slippage anywhere in `run_backtest`.** Noted for one JPM
  test in V12 but it is global, and it silently favours every high-turnover strategy in
  the auto-selector — i.e. it biases strategy *selection*, not just reported returns.
- **Rule-based strategies won 4 of 5 tickers** on the corrected engine, a reversal from
  the pre-V13 picture. Unexplained. Could be genuine (ML was previously flattered by
  flooring/stop artefacts) or could indicate a new problem. Investigate before trusting.
- **Ticker selection is survivorship-biased.** NVDA/TSLA/AAPL/JPM/IBM were chosen in
  2026 with full knowledge of 2015-2024. Any long-biased strategy looks good on that
  sample. A robustness run on 5 tickers chosen without hindsight — including something
  outside tech and something that went sideways for a decade — would be informative.

### Pre-existing
- IBM and AAPL have each switched strategy at least once live (IBM: RF ↔ Bollinger;
  AAPL: EMA ↔ RF) — auto-selector re-evaluates every run, no strategy lock-in period.
  **V13 note:** the silent-except bug (Fix 4) is the leading explanation for the
  *one-day* flips specifically. Re-assess whether lock-in is still needed after
  observing behaviour on the fixed selector.
- **GitHub Actions run gaps with no alerting.** Three weekdays missing from the log
  (May 1, Jun 18, Aug 6 2026); at least two appear to be trading days. Failures are
  visible as a red X in Actions but nothing surfaces them. Combined with the 60-day
  scheduled-workflow auto-disable, a heartbeat/uptime check is cheap insurance.
- Timestamp format inconsistent in early CSV rows (cosmetic only, self-resolved once
  GitHub Actions took over)
- Optimizer only built for EMA Crossover — needs extending to other strategies
- `squeeze()` needed throughout due to pandas version strictness
- NVDA EMA Crossover and JPM SMA Crossover are both slow to exit declining positions —
  structural property of long-window crossover signals, not a bug
- No strategy lock — auto-selector can pick differently each run
- **TSLA/IBM momentum misread — UNRESOLVED.** Quantified in Version 9, investigated in
  Version 10 (momentum-persistence features tested and rejected). Needs a different
  angle: candidates include a regime classifier upstream of LR/RF, reweighting the
  RSI/BB-heavy feature set, or revisiting the train/test split methodology itself.
- Weekly signal quality too noisy at current sample sizes — held back from dashboard,
  revisit with more data or a rolling window
- NVDA's Jun 24, 2026 stop loss exit is a known, documented, manually-corrected
  one-off exception in the historical CSV/event feed data (see Version 10 — Stop Loss
  CSV Accuracy Fix). Not a pattern, won't recur.

---

## Version Roadmap
### Version 1 ✅ — Single stock, SMA, basic backtest
### Version 2 ✅ — EMA, RSI, Bollinger, risk management
### Version 3 ✅ — Multi-strategy, multi-stock, Sharpe ranking
### Version 4 ✅ — Parameter optimization, walk forward testing
### Version 5 ✅ — ML signal generation (LR + RF)
### Version 6 ✅ — Autonomous strategy selection, composite scoring
### Version 7 ✅ — Paper trading, GitHub Actions scheduler
### Version 8 ✅ — Streamlit dashboard, Alpaca paper trading integration
### Version 9 ✅ — Performance Analytics
  - Trade segmentation (ticker + strategy level, rolled up to ticker level)
  - Win/loss stats, drawdown tracker, signal quality score
  - Problem detection grouped by ticker with severity icons
  - Live stop loss enforcement added (later found to have a logging gap — fixed in V10)
  - Full research report compiled (`Quantara_Version9_Report.docx`)
### Version 10 ✅ — Momentum Investigation, Stop Loss Accuracy Fix, Recent Trading Events
  - Momentum feature investigation (Streak, Streak_Squared, Mom_accel, ADX_14) —
    CLOSED, no live strategy changes. Streak/Streak_Squared rejected after testing;
    Mom_accel and ADX_14 kept (harmless to mildly positive, did not fix TSLA/IBM)
  - `FEATURE_COLS` centralized as a single constant, eliminating feature-list drift
    between backtest and live code
  - Stop Loss CSV Accuracy Fix — CSV now logs what Alpaca actually executed on stop
    loss days, not just the model's opinion
  - Recent Trading Events dashboard tab — narrated event feed with severity sort/filter
### Version 11 ✅ — Live Readiness Audit
  - Discovered and fixed ~1.91x leverage (POSITION_SIZE 0.50 → 0.20)
  - Established buy & hold benchmark: +20.10% vs +4.48%, first real evidence of edge
  - Fixed rejected-order logging + added live Alpaca position reconciliation
  - Corrected stop loss characterisation; evaluated and rejected a 4% threshold
  - Evaluated and deferred resting stop orders and VPS migration, with reasoning
  - Dated system alerts
### Version 12 (planned) — Not yet started
  - **TSLA/IBM momentum-misread fix — still UNRESOLVED.** Momentum-persistence
    features didn't work (Version 10). Next angle: regime classifier upstream of
    LR/RF, RSI/BB feature reweighting, or revisiting train/test split methodology.
  - Treating momentum and volatility as *opportunity* rather than overextension
  - Strategy lock-in period to reduce AAPL/IBM switching instability
  - Revisit weekly signal quality with more data or a rolling window
  - Quantara NN merger: unified dashboard, SQLite when going live
### Version 12 ✅ — Momentum Round 2 (3 failures, 1 success — override results now VOID,
    produced on the pre-V13 engine)
### Version 13 ✅ — Correctness Audit
  - `POSITION_SIZE` split into `BACKTEST_POSITION_SIZE` (1.0) and `LIVE_POSITION_SIZE`
    (0.20) — one constant had been serving two incompatible definitions
  - Fractional shares in `run_backtest`, replacing whole-share flooring — explains and
    closes the Version 12 "Sharpe is not scale-invariant" anomaly
  - Backtest stop loss no longer re-buys on the same bar; it now actually removes
    exposure, as live always did
  - `auto_selector` silent-failure churn fixed: 2 downloads per ticker instead of 6, no
    bare excepts, all-or-nothing selection with last-known-good fallback persisted to
    `results/strategy_assignments.json`, near-tie warnings
  - First automated tests in the project: `test_engine_synthetic.py` (18 assertions),
    `test_auto_selector_fallback.py` (7 assertions), both network-free
  - All pre-V13 backtest figures invalidated and marked STALE
### Version 15 ✅ — Execution Realism, Price Cache, Live Model Fix
  - Live model now trains on all history to yesterday, not the first half of a
    300-day window (~77 rows ending 4 months earlier)
  - Scaler leakage fixed; fabricated last-row label excluded from training
  - Signal-generation failure returns None instead of 0 (0 meant SELL)
  - Execution lag: decisions at a close execute at the NEXT open, stop losses
    included. Gap risk is finally visible
  - Transaction costs (5 bps/side), which change strategy SELECTION not just
    reported returns
  - Local price cache with split/dividend self-healing; two cache bugs caught
    by tests, one of which made it a complete no-op
  - 145 assertions across 9 network-free suites
### Version 16 ✅ — The Benchmark
  - Sharpe now subtracts a real risk-free rate (^IRX, cached, constant fallback)
  - Win_Rate renamed Up_Day_Rate; Market_Return and Vs_Market surfaced
  - Buy & Hold added as a scoreable, genuinely stopless candidate
  - Found `stop_loss=0` meant "stop at 0%", not "no stop" - would have wrecked
    the benchmark silently
  - RESULT: B&H wins 4 of 5 tickers, on Sharpe as well as return. All 10
    ticker/model combinations lose to it. JPM is the sole survivor
  - Momentum override dead: RSI gate wins 0 of 10 against its own controls
  - Two reporting bugs in the walk-forward harness fixed
  - 167 assertions across 10 network-free suites
### Version 17 ✅ — The Verdict
  - 33 sector-diverse tickers, deliberately including known decliners
  - Fixed a look-ahead bug: strategy now picked on TRAIN, scored on TEST
  - HONEST win rate 2/33 = 6% against a 50% no-skill baseline
  - PERSISTENCE 18% against 14% chance -> per-stock strategy fitting is fitting
    to noise; the premise auto-selection rests on does not hold
  - No single strategy beats B&H on more than 7 of 33 tickers; 5 of 6 have a
    negative mean Sharpe
  - A drawdown prediction recorded in advance FAILED and is documented as such
  - Guardrails: MAX_ACCEPTABLE_DRAWDOWN, Buy & Hold benchmark-only
### Version 18 ✅ — Three hypotheses, all falsified
  - Pairwise indicator combos: 120 pairs x 33 tickers, nothing survived
    confirmation on held-back tickers
  - Fundamentals: ruled out by probe — yfinance provides ~1.8 years median,
    roughly 4 usable rebalance points. Dead without paid data
  - Cross-sectional momentum: strong on 2016-2026 (80% parameter plateau, beat
    all random controls), then FAILED on 2000-2026. 13/26 winning years, edge
    +0.43%, negative in both pre-2020 decades
  - The entire momentum edge sits in 2020-2026
  - Stopped searching deliberately. After ~600 configurations tested against the
    same price data, finding one more that works is what a false positive looks
    like
### Version 19 (open) — Where next
  - Adding MORE strategies makes the selection problem WORSE, not better: with
    7 candidates the hindsight baseline is 88%, with 30 it is ~97%. The bottleneck
    is not candidate count, it is that selection cannot distinguish signal from
    noise (persistence = chance)
  - The correct test for ANY new strategy: apply it uniformly across 30+ tickers
    and ask whether it beats B&H on average. No picking. `experiment_basket.py`
    already does this
  - Non-price signals are the only untested hypothesis available at zero cost:
    fundamentals, cross-sectional ranking, sentiment/news
  - Intraday is ruled out on cost grounds (paid data + always-on infrastructure)
  - Make buy & hold the default benchmark in `get_metrics` output, the composite score,
    and the dashboard. It has always been computed and never shown
  - Add buy & hold as a scoreable candidate in `auto_selector.py`
  - Re-run the whole pipeline on tickers not selected with hindsight, especially
    non-trending names — the IBM result is the only place a real edge showed up
  - Transaction costs (this now matters more, not less — it widens B&H's lead)
### Version 14 🔄 — Measurement Layer + Override Correction (IN PROGRESS)
  - ✅ `evaluation/account_log.py` — equity/positions/fills logged from the Alpaca API,
    with automatic leverage detection and warning. Built and unit-tested against a fake
    client (22 assertions); **not yet run against the real account**
  - ✅ Found that the Version 12 override implementation did not match its documented
    rule — engaged on losing positions, and its trailing stop ratcheted down instead of
    exiting. All V12 override results are therefore void
  - ✅ Override rule extracted to `strategy/momentum_override.py` with a `legacy` flag
    reproducing the V12 bugs for direct comparison; 13 assertions
  - ✅ `override_walk_forward.py` — 4-window validation harness, trains 40 models
    instead of 450, scores corrected vs legacy side by side
  - ✅ **Ran `override_walk_forward.py`** — override SURVIVES walk-forward on AAPL (both
    models) and TSLA (both models); IBM REJECTS; NVDA REJECTS. V12 bugs found to be real
    but nearly immaterial on real data. ⚠️ Optimum sits at the edge of the parameter
    grid — unresolved, see Finding 5. Nothing shipped
  - ✅ **Resolved Finding 5** — Round 3 with control arms: buy & hold beats every LR/RF
    baseline on Sharpe in all four windows. AAPL/RF and IBM/RF are the only configs that
    beat it. The override was closing the gap to buy & hold by trading less
  - ✅ **First live NQ run** — 20% sizing confirmed in a real order (26.8561 sh -> 10.7665
    sh), slippage measured for the first time (+1.37% NVDA, +1.38% AAPL), leverage 0.93x
    with JPM still sitting at 44% of equity
  - ✅ Trading date now read from market data instead of `datetime.now()` — Friday's
    prices no longer land on a Saturday
  - ✅ Schedule moved from `0 21 * * 1-5` (5 PM ET, mid post-market, unsettled prices)
    to `0 1 * * 2-6` (9 PM ET summer / 8 PM ET winter — settled in both seasons)
  - ✅ Two fail-OPEN bugs fixed in `alpaca_executor.py`: the duplicate-order guard never
    matched any status, and bare excepts made an API failure look identical to "flat"
  - ⬜ **No rebalancing logic** — JPM is stuck at 44% of equity until it cycles out
  - ⬜ Execution lag + transaction costs in `run_backtest`
  - ⬜ Portfolio-level backtest — no simulation of the deployed system currently exists
  - ⬜ Live LR training-window fix
---

## Related Project
**Quantara NN** — separate intraday trading system
- Minute data, MLP neural network, Nemotron LLM reasoning
- Alpaca live order execution
- Multi-agent pipeline
- Position sizing bug: stacks positions despite 2% limit. Fix: check pending orders +
  open positions before buying (same pattern as this project's duplicate order fix)

---

## GitHub
- Repo: https://github.com/titan-trials/REQuantara
- Actions: https://github.com/titan-trials/REQuantara/actions
- Local: `C:\Users\logic\OneDrive\Desktop\REQuantara`

## Libraries
- yfinance — market data
- pandas — data manipulation
- matplotlib — visualization
- scikit-learn — ML models
- openpyxl — Excel export
- streamlit — dashboard
- plotly — interactive charts
- alpaca-py — paper trading execution