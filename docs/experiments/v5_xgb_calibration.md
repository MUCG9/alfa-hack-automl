# Predeclared experiment: XGBoost decision calibration

The prior v4 fixed-recipe classification studies mainly calibrated LightGBM.
The completed history3 search spent eight fallback trials on XGBoost capacity
variants, none beating its first XGBoost recipe, and final two-fold ensemble mean
was slightly below frozen v3. Do not promote another capacity/default change from
this observation alone.

Hypothesis: XGBoost's existing, training-only decision-factor calibration can
improve the precision/recall balance of rare classes without changing fitting
weights, capacity or the evaluator. This is decision calibration for Macro F1,
not a claim of calibrated probabilities for log loss.

- Control and one-factor candidate: `v5_xgb_calibration_candidates.json`.
- Frozen execution archive: `release/solution-v5-contract1.zip` (existing adapter
  calibration support, before later orchestration changes).
- First compare the same feature-hash-group folds, seeds 42 and 43. Two threads,
  sequential workers, 900-second per-worker watchdog, 1.5 GiB worker RSS guard.
- Require successful workers and inspect every class, not only mean Macro F1.
  Do not add calibration to the portfolio unless direction is supported on both
  folds; if promising, confirm on full 3-fold group CV before promotion.
- Fold/CV data are already researched public rows, not a blind private estimate.
  A negative/inconsistent result is recorded and discarded, not hidden.

## Paired result

All four workers passed. Control/candidate Macro F1:

| Seed | Control | Inner decision calibration | Difference |
|---|---:|---:|---:|
| 42 | 0.650904187 | 0.652319467 | +0.001415280 |
| 43 | 0.639569586 | 0.645949771 | +0.006380185 |
| Mean | 0.645236886 | 0.649134619 | +0.003897733 |

The exact source archive SHA is
`1defe433da3fe65813b5c1cc3682991e508780dd89defefdb08b7589e17ccb5a`.
The next predeclared gate, full 3-fold group CV for both recipes, has been started
sequentially. Calibration is NOT in the default portfolio at this checkpoint;
do not describe paired reuse of public folds as independent private evidence.
