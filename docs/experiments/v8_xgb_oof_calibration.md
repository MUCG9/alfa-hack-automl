# Predeclared one-factor study: training OOF decision calibration

Hypothesis: the one-inner-holdout Macro F1 decision factors have high variance for
rare classes. Existing3fold training OOF calibration may stabilize them without
changing capacity, training weights, augmentation or the outer evaluator.

Control/candidate are in `v8_xgb_oof_calibration_candidates.json`. Both calibrate
the same XGBoost recipe; ONLY `calibration_folds` changes from1 to3. Source workers
are frozen V7 (`a31d1fc7c9bee3403f992f70467e95a446c19dbffdb4cdfea9abf2d035f79b27`),
not changing V8 infrastructure or the old study's execution snapshot.

## Before running

- Finish the resumed V7 full classification first; never overlap heavy ML jobs.
- Compare both recipes on the same legacy feature-group folds42/43 with2threads,
  a1200s/worker watchdog and1.5GiB process-tree guard. Preserve source/input/split
  hashes. Both controls are re-run on the same archive; old CV results are context.
- Require all workers/refits and both folds to support the direction before
  considering promotion. Inspect per-class regressions and rare-class counts.
- If consistently promising, compare full3fold group CV. Report fold mean and
  pooled OOF separately, with exactly-once row coverage and class/split alignment.
- Discard from defaults on inconsistent/negative results. A single lucky fold or
  a reused-OOF tuned score is not sufficient. Record failures, not only winners.
- Full candidate-agent search/selection/refit still needs testing even if this
  component improves; V6 demonstrated that component gains may transfer weakly.

Training OOF here is only for fitting decision factors inside outer fitting data.
Iterations are selected within that outer fitting data, not an independent nested
hyperparameter assessment of the OOF predictions themselves. The OUTER evaluation
is the check of this procedure. No claim of perfectly unbiased training OOF or
private-score uncertainty. No new runtime implementation is required for the study.

## Result: discard from defaults

All four workers passed; same frozen V7 execution bytes and paired split hashes.

| Fold seed | Inner control | Training OOF3 | Delta |
|---|---:|---:|---:|
|42|0.652319467|0.651515878|-0.000803590|
|43|0.645949771|0.646542924|+0.000593153|
|Mean|0.649134619|0.649029401|-0.000105218|

OOF3 took about159/161s versus82/80s for control. Direction is inconsistent and
mean is slightly worse, so the predeclared keep criterion fails. No full CV or
default/portfolio promotion is justified by this study. Negative evidence is
preserved in `v8_xgb_oof_calibration_results.json`. Local/reused data, not official.
