# Predeclared V10 independent-family classification screen

Declared after history4 full-agent/release gates completed and captain resumed
work. No ExtraTrees fits have been observed yet. Use exact history4 archive SHA
a42fcb1557ec0cf2455abb3add9d6968a8388aedcfcf8d554b26ed73a45788f8.
No new runtime code/dependency/default policy is introduced by this study.

## Hypothesis and fixed recipes

Under70 changed errors but also broke many correct predictions; its mixed CV and
conditional bootstrap did not justify promotion. Test a structurally different
existing ExtraTrees branch, preserving fitting distribution instead of sampling.
Random thresholds/feature subsets and frequency-encoded categoricals differ from
LGBM. This tests that whole existing branch, not the threshold algorithm alone.

Recipes frozen in v10_extratrees_candidates.json:
A exact prior strong calibrated LGBM seed42/noop. B the SAME LGBM plus XT, equal
probability weights. XT300trees,depth24,min_leaf2,max_features.7,seed42,mild source
class weighting power.5,inner-only decision calibration. Existing XT encoding/
medians are fit-only. No augmentation, explicit feature code, target encoding,
class-weight sweep or blend-weight tuning. XT child-alone metrics are diagnostic.
Both branches refit transformations and class factors on their current fitting
partitions; child0 must reproduce the standalone control predictions exactly.

## Sequential paired screen

Legacy feature-group holdouts42/43, same pinned inputs/harness,2threads,1200s per
worker,1.7GiB process-tree guard. Four parent jobs, six component outer fits plus
inner fits/calibration. Controller runs sequentially; no concurrent full suite.
All successful exit0; align source/input/split/row/class hashes and inspect child
control parity. Keep for CV only if B's MacroF1 improves on BOTH screen folds.
Report per-class precision/recall/F1/confusion, corrected/broken predictions,
conditional correction rates and log loss. Disagreement alone is not a keep gate.
A weak XT single may still be useful; a weak final blend is not rescued by trying
new weights on these same folds. Mixed/negative: preserve exact result, no default
promotion, then declare a separate future hypothesis before any new fitting.

## Confirmation only if both screen folds improve

Run complete3fold StratifiedGroupKFold with seed73, same fixed recipes/weights,
respect duplicate/declared entity groups, exactly-once OOF, no retuning. Report
fold mean and pooled OOF separately. Keep only if all THREE fold deltas positive
and mean/pooled improve. Define class support as number of distinct fitting
feature hashes per class. A class is sufficiently supported if minimum support
across folds >=100; none may lose pooled per-class F1 by more than.01. The pooled
macro gain after excluding the class with smallest minimum fitting-group support
must also remain positive (ties resolve in stored class order). These diagnostic
constraints are predeclared, not weights optimized on validation labels.
Then require a separate full-agent selection/refit/export/runtime comparison
before adding this branch to the portfolio. No private-score guarantee.

## Failure interpretation and provenance

Timeout/memory/dependency failures are execution failures, not measured quality
losses; keep logs/receipts and isolate a resource fix before repeating. A changed
forest size/depth/categorical encoding is a new hypothesis, not a silent retry.
This machine has8GiB/full swap; limits here differ from platform8CPU/32GiB/3h.
Original requirements and historical ZIPs remain immutable; raw datasets,
probability arrays and row prediction CSVs remain ignored local artifacts.
No real API calls or official upload. Reused public folds are not unbiased/private.
