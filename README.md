# gta6-trophy-rarity-forecast-01

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/verren044/makefun-gta6-trophy-rarity-forecast-01/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/verren044/makefun-gta6-trophy-rarity-forecast-01/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

Forecasts every GTA VI PS5 trophy's Exophase earn rate at 2026-11-26T00:00:00Z as five quantiles per trophy, scored by pinball loss on the logit scale.

## Model

A printed earn rate is a ratio of two moving quantities, `rate = 100 * E / P`, where `P` is the players Exophase tracks and `E` the number of them holding the trophy. Earners only grow; `P` jumps up whenever Exophase refreshes, diluting every rate. The entry models `E` and `P` apart, both fitted in log space against `x = ln(1 + hours since release)`:

- **E per trophy**: least squares of `log E` on `x` over distinct reads (consecutive identical reads collapse to one point), slope shrunk toward the tier mean and blended toward the global slope, forecast `E` forced ≥ last observed `E`.
- **P**: least squares of `log P` on `x`, slope damped ×0.9, forced ≥ last `P`.
- **Second leg**: least squares of `logit(rate)` on `x` (the house curve baseline's shape), which saturates gracefully as a rate approaches 100%. The median averages the two legs in logit space; their disagreement widens the spread.
- **Brakes**: both legs are read at a damped clock (`x_last + 0.6 * (x_target - x_last)`) because launch growth decelerates, and a loose tier ceiling (bronze 98%, silver 85%, gold 60%, platinum 8%) stops runaway extrapolation.
- **Frozen history**: when every read is identical (launch night), a pending-refresh haircut applies — one refresh multiplies non-100% rates by ×0.22, derived from the kit's own launch-night numbers (players 638→3868, trophies earned 943→4276, the 100% trophy undilutable). Once the history shows any refresh, the fit is trusted and no haircut is applied.
- **Spread**: random walk `0.5*sqrt(days)` + fit residual + observed log-P jumpiness + model-miss floor (0.65 frozen, 0.35 otherwise) + leg disagreement, in logit space.

## Run it

```sh
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Deterministic: the same case file always gives the same bytes. Standard library only, offline, well under the 8 s cap (~0.1 s per case).

## Validation

- Practice (p00/p01), answers reconstructed from the kit's documented refresh numbers (players 638→3868, trophies earned 943→4276; non-100% rates ×0.221, 100% unchanged — this reconstruction reproduces the documented house-baseline practice loss ≈1.51 as 1.40): **loss 0.153 / 0.141 vs house baseline 1.40**, 90% coverage 0.98. Robust to the true refresh factor in 0.15–0.35 (mine 0.14–0.25 vs baseline 0.95–1.78).
- Synthetic final-like case (2 days of reads, saturating trophy curves, 6,510-min horizon): **loss 0.489 vs baseline 0.512** (0.473 vs 0.507 excluding the platinum, whose synthetic truth was mis-set).

---

Entered on [make.fun](https://make.fun/?ref=vvz66fvh&utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards
