"""
Momentum override - single source of truth.

THE IDEA (Version 12): a model trained to be right on average across all days
will always trade away rare-event performance, because that is what the loss
function asks for. Momentum runs are rare. You cannot train this out. So do not
retrain - override.

THE RULE AS DOCUMENTED: when the model signals SELL while RSI is above a
trigger AND the position is profitable, suspend the sell and hold with a
trailing stop measured from the RUNNING PEAK (not from entry). Exit when price
falls TRAIL% below that peak.

Trailing from the peak is the load-bearing part. Without it this degenerates
into "hold and hope", which TSLA's $445 top would have destroyed.

===========================================================================
VERSION 13 FINDING: THE VERSION 12 IMPLEMENTATION DID NOT MATCH THAT RULE
===========================================================================
Two bugs, both found by synthetic-price testing, both of which made the
override far more aggressive than described:

BUG 1 - the "position is profitable" test was a no-op in the common case.
`entry` was initialised to 0.0 and only updated on a 0 -> 1 signal transition.
When the test period BEGINS already in a position (Signal[0] == 1, which is
common) no such transition ever occurs, so `entry` stays 0.0 and
`close[i] > entry` is trivially true. The override engaged on losing positions.

BUG 2 - the trailing stop ratcheted downward instead of exiting. On the bar the
trailing stop released, control fell straight through to the re-entry check,
which (thanks to Bug 1) passed - so it re-engaged on the same bar at the lower
price, reset the peak, and repeated. Structurally identical to the engine's
stop-loss re-buy bug found in Version 13.

Demonstrated on a position falling 100 -> 10 with RSI pinned at 80: the
documented rule holds 0 days; the Version 12 implementation held 8 of 9,
re-engaging on every single bar.

**Every Version 12 override result was therefore measuring a different rule
than the one it described.** Both variants are kept below so the walk-forward
harness can report whether the Version 12 result depended on the bugs.
"""


def apply_trailing_stop_only(df, trail):
    """CONTROL ARM: ignore the model's exit signals entirely.

    Enter when the model says 1 and we are flat. Then hold until price falls
    TRAIL% below the running peak, regardless of what the model says. Re-enter
    on the next bar the model says 1.

    This is the limit case the Version 14 sensitivity gradient points at. If it
    matches or beats the RSI-gated override, then the RSI condition is doing no
    work and the real finding is "the model's exit signal is worse than a dumb
    trailing stop" - a much broader claim than "the momentum override works",
    and one that would reframe the TSLA/IBM misread open since Version 9.

    Returns the number of bars held.
    """
    sig = df["Signal"].values.copy()
    close = df["Close"].squeeze().values
    out = [0] * len(sig)
    in_pos, peak = False, 0.0
    held = 0

    for i in range(len(sig)):
        if in_pos:
            peak = max(peak, close[i])
            if close[i] < peak * (1 - trail):
                in_pos = False           # trailing stop -> flat this bar
            else:
                out[i] = 1
                held += 1
                continue
        # Flat: enter on a model buy. Not on the bar the stop just fired -
        # same rule as the engine, so the position is out for at least one bar.
        elif sig[i] == 1:
            in_pos, peak = True, close[i]
            out[i] = 1
            held += 1

    df["Signal"] = out
    return held


def apply_override(df, rsi_trigger, trail, legacy=False):
    """Rewrite df['Signal'] in place. Returns the count of days held by override.

    legacy=False (default) implements the rule as documented.
    legacy=True  reproduces the Version 12 behaviour bug-for-bug, so old results
                 remain reproducible and the two can be compared directly.

    KNOWN APPROXIMATION (present in both variants, deliberately not changed):
    `entry` tracks the model's own entry price, not the backtest's actual entry.
    The backtest's stop loss can close a position while Signal stays 1, after
    which `entry` is stale. The profitability test is approximate in that case.
    """
    sig = df["Signal"].values.copy()
    rsi = df["RSI"].values
    close = df["Close"].squeeze().values

    # BUG 1 FIX: if the series opens already in a position, that opening price
    # IS the entry. Without this the profitability test never binds.
    if legacy:
        entry = 0.0
    else:
        entry = float(close[0]) if len(sig) and sig[0] == 1 else 0.0

    in_form, peak = False, 0.0
    active = 0

    for i in range(1, len(sig)):
        released_this_bar = False

        if in_form:
            peak = max(peak, close[i])
            if close[i] < peak * (1 - trail):
                in_form = False              # trailing stop hit -> release
                released_this_bar = True
            else:
                sig[i] = 1                   # hold through the momentum run
                active += 1
                continue

        # BUG 2 FIX: do not re-arm the override on the bar its trailing stop
        # just fired. Otherwise the stop ratchets down forever and never exits.
        may_engage = legacy or not released_this_bar

        if (may_engage
                and sig[i] == 0 and sig[i - 1] == 1
                and rsi[i] > rsi_trigger
                and close[i] > entry):
            in_form, peak = True, close[i]
            sig[i] = 1
            active += 1

        if sig[i] == 1 and sig[i - 1] == 0:
            entry = close[i]

    df["Signal"] = sig
    return active
