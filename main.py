"""gta6-trophy-rarity-forecast-01 entry (Python 3.13, standard library only).

Forecast each GTA VI PS5 trophy's Exophase earn rate at the case target.

The idea. A printed earn rate is a ratio of two moving quantities:

    rate_i(t) = 100 * E_i(t) / P(t)

where P(t) is the players Exophase tracks and E_i(t) the number of them who
hold trophy i. Earners only grow (a trophy once earned stays earned), while
P jumps up whenever Exophase refreshes its counts, diluting every rate.
Modelling the rate directly confuses the two; modelling E and P apart does
not. Both are fitted in log space against x = ln(1 + hours since release),
the clock a launch lives on: early hours move fast, later hours slowly.

  * E_i: least squares of log E_i on x over the case's distinct reads
    (consecutive identical reads collapse to one point: a frozen page is
    one observation, not seven). The slope is shrunk toward its tier's mean
    slope (bronze story trophies are earned fast, platinum slowly) with
    weight n/(n+4) on the trophy's own fit, then blended 15% toward the
    global slope. Slopes clamp to [-0.5, 3]. The forecast E is forced to be
    at least the last observed E: earners never decrease.
  * P: least squares of log P on x, slope clamped to [0, 1.2] and damped
    x0.9 (player growth saturates), forced to be at least the last P.
  * median rate = 100 * E_target / P_target, clamped to [0.01, 99.99].
  * The E/P forecast is then averaged, in logit space, with a second
    forecast: a least-squares line of logit(rate) on x, the house curve
    baseline's shape. The E/P leg knows about dilution (a player jump
    drops rates) but its exponential E can run away to 100% on a steep
    trophy; the logit leg saturates gracefully as a rate approaches 100%.
    Averaging the two logits keeps the dilution signal while capping the
    runaway. A loose tier ceiling backstops it further (bronze 98%,
    silver 85%, gold 60%, platinum 8%): a median above the ceiling can
    only come from extrapolating a steep slope past saturation, and on
    the logit scale overforecasting to 99.99% costs far more than the
    ceiling ever could. The two legs' disagreement also widens the
    spread, so a trophy the models read differently gets honest
    quantiles.

A frozen history (every read identical, as on launch night) carries a
different warning: the page has not refreshed yet, so the next refresh is
still ahead of the checkpoint and the fitted trends say nothing. In that
regime only, the median takes a pending-refresh haircut. The kit's own
launch-night numbers fix the size of one refresh: players 638 -> 3868
(x6.06) while trophies earned 943 -> 4276, and the one trophy at 100%
cannot dilute, so the other trophies' earners grew only (4276-3868) /
(943-638) = x1.34 and their rates fell by 1.34 / 6.06 = x0.22. Expected
refreshes before the target are (staleness + horizon) / 5h, staleness
being how long the page has already sat frozen at the checkpoint (a page
frozen for hours is overdue: refreshes come hours apart), capped at 2.
Once the history shows any refresh, the fit is trusted and no haircut is
applied: over the final's 4.5-day horizon the fitted E/P trends already
price in ongoing dilution.

The spread is a logit sigma combining four honest sources of miss: a
random walk 0.5*sqrt(horizon days) (the house baseline's term), the
per-trophy fit residual, the observed jumpiness of log P between reads
(refresh shocks), and a floor for model miss (0.65 logit on a frozen
history, 0.35 otherwise). Quantiles are inv_logit(logit(median) +
z_tau * sigma), rounded to 4 decimals. The 100% trophy stays at 99.99
with a tiny spread: every tracked player holds it and new players earn
it on starting the game.

One more brake: both legs are read at a damped target clock,
x_last + 0.6 * (x_target - x_last), not at the target itself. A launch
cohort's growth decelerates in clock time as players finish content, so
a slope fitted over the first two days overstates the next four and a
half; taking 60% of the remaining log-time growth is the honest
middle between persistence and full extrapolation. On a frozen
history the slopes are zero, so the brake changes nothing there.

Deterministic: the same case file always gives the same bytes (no
randomness, no clock, no network; reads are processed oldest first and
every summary sorts before it is used). Runs offline under the 8 s cap.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0, 0.674, 1.645]

# Refresh spacing (hours) and per-refresh rate factor used only when the
# whole history is one frozen snapshot. Both come from the kit's own
# launch-night numbers: players 638 -> 3868 (x6.06), trophies earned
# 943 -> 4276; the 100% trophy cannot dilute, so the other trophies'
# earners grew (4276-3868)/(943-638) = x1.34 and their rates fell by
# 1.34/6.06 = x0.22 on the refresh.
FROZEN_REFRESH_HOURS = 5.0
FROZEN_REFRESH_FACTOR = 0.221
# Share of the remaining log-time growth the forecasts take: launch
# growth decelerates, so full extrapolation overstates the target.
GROWTH_DAMP = 0.6


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def parse_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def logit(pct):
    p = clamp(pct, 0.01, 99.99) / 100.0
    return math.log(p / (1.0 - p))


def inv_logit(lg):
    return 100.0 / (1.0 + math.exp(-clamp(lg, -20.0, 20.0)))


def round4(x):
    scaled = x * 10000
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 10000
    return int(value) if value == int(value) else value


def ols(xs, ys):
    """Least squares y ~ a + b*x. Returns (a, b, resid_sd, n)."""
    n = len(xs)
    if n == 0:
        return 0.0, 0.0, 0.0, 0
    if n == 1:
        return ys[0], 0.0, 0.0, 1
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return my, 0.0, 0.0, n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx
    a = my - b * mx
    if n > 2:
        var = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys)) / (n - 2)
        resid = math.sqrt(max(var, 0.0))
    else:
        resid = 0.0
    return a, b, resid, n


def median_of(vals):
    s = sorted(vals)
    n = len(s)
    if n == 0:
        return 0.0
    if n % 2 == 1:
        return s[n // 2]
    return 0.5 * (s[n // 2 - 1] + s[n // 2])


def forecast_case(case):
    trophies = case["trophies"]
    history = case["history"]
    horizon_days = case["horizon_minutes"] / 1440.0
    horizon_hours = case["horizon_minutes"] / 60.0

    release = case.get("game", {}).get("release_date", "2026-11-19")
    try:
        t0 = datetime.fromisoformat(release).replace(tzinfo=timezone.utc)
    except ValueError:
        t0 = parse_time(history[0]["at"]) if history else datetime(
            2026, 11, 19, tzinfo=timezone.utc
        )

    def x_of(when):
        hours = (parse_time(when) - t0).total_seconds() / 3600.0
        return math.log1p(max(hours, 0.0))

    # Collapse consecutive identical reads: a frozen page is one point.
    reads = []
    for h in history:
        key = (h["players_tracked"], tuple(h["rates"]))
        if reads and reads[-1][0] == key:
            continue
        reads.append((key, h))
    frozen = len(reads) <= 1

    xs = [x_of(h["at"]) for _, h in reads]
    x_target = x_of(case["target"])
    # Damped evaluation clock (see the module docstring).
    x_eval = xs[-1] + GROWTH_DAMP * (x_target - xs[-1]) if xs else x_target
    players = [float(h["players_tracked"]) for _, h in reads]
    p_last = players[-1] if players else 638.0

    # --- players tracked at the target -------------------------------------
    if len(reads) >= 2:
        ap, bp, _, _ = ols(xs, [math.log(max(p, 1.0)) for p in players])
        slope_p = clamp(0.9 * bp, 0.0, 1.2)
        p_target = math.exp(ap + slope_p * x_eval)
    else:
        slope_p = 0.0
        p_target = p_last
    p_target = clamp(p_target, p_last, p_last * 100.0)

    # Log-P jumpiness between distinct reads: refresh-shock scale.
    jumps = []
    for a, b in zip(players, players[1:]):
        if a > 0 and b > 0:
            jumps.append(math.log(b / a))
    jump_sd = 0.0
    if len(jumps) >= 2:
        mj = sum(jumps) / len(jumps)
        jump_sd = math.sqrt(sum((j - mj) ** 2 for j in jumps) / (len(jumps) - 1))
    jump_sd = clamp(jump_sd, 0.0, 0.5)

    # --- per-trophy earner fits --------------------------------------------
    n_tr = len(trophies)
    fits = []
    for i in range(n_tr):
        ex, ey = [], []
        lx, ly = [], []
        last_e = 0.0
        last_rate = None
        for k, (_, h) in enumerate(reads):
            r = h["rates"][i]
            if r is None:
                continue
            last_rate = r
            e = max(r, 0.01) / 100.0 * float(h["players_tracked"])
            last_e = e
            ex.append(xs[k])
            ey.append(math.log(max(e, 0.5)))
            lx.append(xs[k])
            ly.append(logit(r))
        if len(ex) >= 2:
            a, b, resid, n = ols(ex, ey)
            al, bl, _, _ = ols(lx, ly)
        elif len(ex) == 1:
            a, b, resid, n = ey[0], 0.0, 0.0, 1
            al, bl = ly[0], 0.0
        else:
            a, b, resid, n = math.log(0.5), 0.0, 0.0, 0
            al, bl = logit(0.0), 0.0
        fits.append(
            {
                "a": a,
                "b": clamp(b, -0.5, 3.0),
                "resid": resid,
                "n": n,
                "last_e": last_e,
                "last_rate": last_rate if last_rate is not None else 0.0,
                "a_logit": al,
                "b_logit": clamp(bl, -1.0, 3.0),
            }
        )

    # Tier-mean slopes and the global slope, for shrinkage.
    tiers = {}
    tiers_logit = {}
    for t, f in zip(trophies, fits):
        tiers.setdefault(t["tier"], []).append(f["b"])
        tiers_logit.setdefault(t["tier"], []).append(f["b_logit"])
    tier_mean = {k: (sum(v) / len(v) if v else 0.0) for k, v in tiers.items()}
    tier_mean_logit = {k: (sum(v) / len(v) if v else 0.0) for k, v in tiers_logit.items()}
    global_slope = median_of([f["b"] for f in fits])
    global_slope_logit = median_of([f["b_logit"] for f in fits])

    # Loose tier ceilings on the median rate: only a runaway extrapolation
    # reaches them, and overforecasting to ~100% is the expensive error.
    TIER_CAP = {"platinum": 8.0, "gold": 60.0, "silver": 85.0, "bronze": 98.0}

    rw = 0.5 * math.sqrt(horizon_days)
    floor = 0.65 if frozen else 0.35
    # How long the page has sat frozen at the checkpoint, in hours: a page
    # frozen for hours is overdue for its next refresh.
    staleness_h = 0.0
    if reads:
        staleness_h = max(
            0.0,
            (parse_time(case["at"]) - parse_time(reads[0][1]["at"])).total_seconds() / 3600.0,
        )
    rows = []
    for t, f in zip(trophies, fits):
        # Shrink the slope toward the tier mean, then a little toward global.
        w = f["n"] / (f["n"] + 4.0) if f["n"] else 0.0
        b = w * f["b"] + (1.0 - w) * tier_mean.get(t["tier"], global_slope)
        b = 0.85 * b + 0.15 * global_slope
        b = clamp(b, -0.5, 3.0)
        e_target = math.exp(f["a"] + b * x_eval)
        e_target = max(e_target, f["last_e"])
        e_target = min(e_target, p_target)

        med_ep = 100.0 * e_target / p_target
        # Cap the E/P leg at the tier ceiling BEFORE the logit blend: an
        # uncapped leg sits at logit ~9 and would drag the average to ~100%
        # on its own, however sane the logit leg is.
        med_ep = clamp(med_ep, 0.01, TIER_CAP.get(t["tier"], 98.0))
        # Second leg: logit(rate) linear in x, slope shrunk like the first.
        w_logit = f["n"] / (f["n"] + 4.0) if f["n"] else 0.0
        bl = w_logit * f["b_logit"] + (1.0 - w_logit) * tier_mean_logit.get(
            t["tier"], global_slope_logit
        )
        bl = 0.85 * bl + 0.15 * global_slope_logit
        bl = clamp(bl, -1.0, 3.0)
        med_logit_leg = inv_logit(f["a_logit"] + bl * x_eval)
        # Average the two legs in logit space; disagreement widens sigma.
        lg_blend = 0.5 * (logit(med_ep) + logit(med_logit_leg))
        disagree = abs(logit(med_ep) - logit(med_logit_leg))
        med = inv_logit(lg_blend)
        if frozen:
            # A refresh is still ahead of the checkpoint: haircut the median.
            # Expected refreshes before the target count the frozen stretch
            # already waited plus the horizon, over the refresh spacing.
            expected = clamp((staleness_h + horizon_hours) / FROZEN_REFRESH_HOURS, 0.0, 2.0)
            med *= FROZEN_REFRESH_FACTOR ** expected
        med = clamp(med, 0.01, TIER_CAP.get(t["tier"], 98.0))
        med = clamp(med, 0.01, 99.99)

        if f["last_rate"] >= 99.99:
            sigma = 0.10
            med = 99.99
        else:
            resid = clamp(f["resid"], 0.10, 0.8)
            sigma = math.sqrt(
                rw * rw
                + resid * resid
                + (jump_sd * math.sqrt(horizon_days)) ** 2
                + floor * floor
                + (0.25 * disagree) ** 2
            )
            sigma = clamp(sigma, 0.15, 2.0)

        lg = logit(med)
        qs = [round4(clamp(inv_logit(lg + z * sigma), 0.01, 99.99)) for z in Z]
        for k in range(1, 5):
            if qs[k] < qs[k - 1]:
                qs[k] = qs[k - 1]
        rows.append({"id": t["id"], "q": qs})
    return {"trophies": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
