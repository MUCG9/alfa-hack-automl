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

This document predeclares the experiment; results have not been obtained yet.
