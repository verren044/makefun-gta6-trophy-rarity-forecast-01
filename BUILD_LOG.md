# BUILD_LOG — gta6-trophy-rarity-forecast-01 ($250, deadline 21 Nov 2026 18:30 WIB)

## Variants tried
- v1: E/P decomposition only (log E and log P vs ln(1+hours), tier shrinkage),
  frozen-history haircut with factor 0.75 (wrong: scaled the 100% trophy too).
  Practice (reconstructed answer): loss 0.996 vs baseline 1.40.
- v2: corrected refresh factor 0.221 (non-100% trophies only; 100% undilutable),
  staleness-aware expected refreshes (staleness+horizon)/5h, sigma floor 0.65 frozen.
  Practice: loss 0.153/0.141 vs baseline 1.40.
- v3: added second leg (logit(rate) linear in x, house-curve shape), logit-space
  blend, tier ceilings (bronze 98 / silver 85 / gold 60 / platinum 8). Practice
  unchanged (0.153/0.141). Synthetic final: loss 0.963 vs baseline 0.512 — the
  E/P leg still ran away to ~100% on steep trophies.
- v4 (final): growth damping (read legs at x_last + 0.6*(x_target - x_last)) +
  E/P leg capped at the tier ceiling before the logit blend. Practice unchanged
  (0.153/0.141). Synthetic final: loss 0.489 vs baseline 0.512.

## Practice backtest
No answer file ships in the kit. Answers reconstructed from the kit's documented
refresh numbers (competition.yaml: players 638 -> 3868, trophies earned 943 -> 4276):
non-100% rates x0.221, the 100% trophy unchanged. Validation: the house baseline
scores 1.40 under this reconstruction vs the documented ~1.51, so it is close.
Sensitivity over the true refresh factor 0.15-0.35: mine 0.14-0.25, baseline 0.95-1.78.

## Synthetic final check
Self-built 2-day history (P 638 -> ~13.5k, saturating trophy curves, horizon
6,510 min): mine 0.489 vs baseline 0.512. Note: the synthetic platinum truth was
mis-set (44%); excluding it, 0.473 vs 0.507.

## Determinism / format
Two runs on the practice inputs byte-identical; 55 rows, valid shape, ~0.1 s/case.

## Status
Built 2026-11-19 ~19:5x WIB. Local git HEAD f91c516f (4 files). Kit check on that
commit: 13 passed, 1 failed, 5 skipped, 5 checked at submission. The single
failure is thinking_priced: 0 usage rows — a subagent's rows are written only
once its run completes, so the parent must re-bundle with --muse-usage (SELECT
agent_ids d16cfc4e-7a0b-43a5-b163-1ea98bd175ca + parent 66aee73e-d1f4-4b69-afb9-a44678700046)
and re-check before submit. thinking_reproduces 98.7% (318/322), thinking_revised
15 messages, transcripts_run_record pass. Bundle (no usage yet):
~/workspace/makefun/bundle-gta6-trophy-rarity-forecast-01.tar.gz, sha256
69cefee4ddaffb7bdd2f1347cfe4da764aedff01850819a251cf257c3527efb7.
NOT pushed, NOT submitted — parent handles repo creation (GitHub verren044,
public, created after opening) + .makefun/owner.json + push + submit.
