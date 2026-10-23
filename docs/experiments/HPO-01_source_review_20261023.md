# HPO-01 — reviewed historical work, not a new experiment

Read-only review while LONG-01 remains active. No HPO module imported, no Optuna
installed, no new ML fits or live API calls. Later stages must not repeat a
negative combined pipeline under a new name.

Controlling historical snapshot is colleague commit
01962f68cc1b0a1787e6beca40e64dd742875754:

- [HPO implementation](https://github.com/MUCG9/alfa-hack-automl/blob/01962f68cc1b0a1787e6beca40e64dd742875754/src/automl/search/hpo.py)
- [Declared HPO protocol](https://github.com/MUCG9/alfa-hack-automl/blob/01962f68cc1b0a1787e6beca40e64dd742875754/docs/experiments/hpo01_protocol_20261022.md)
- [tm1 lessons and evidence pointers](https://github.com/MUCG9/alfa-hack-automl/blob/01962f68cc1b0a1787e6beca40e64dd742875754/docs/experiments/autoresearch_lessons_tm1_20261023.md)

## What to preserve

The implementation builds a study split inside supplied outer fitting positions,
checks group disjointness, delegates actual fits to the owned worker, uses
ask/tell, records failed/duplicate trials, and leaves feature/calibration/weight/
seed/target policies unchanged. A queued anchor is checked against a predeclared
bounded search space. Search-space/control checks are useful code to reuse only
after integration review against our current adapters. Optional dependency
unavailable is explicit, not an installation from solution.py.

## What the old result does NOT establish

The tm1 report says classification planned8 HPO trials but attempted3, completed2,
timed out1, and reached ZERO guided TPE trials. Regression had5 guided successes.
The combined procedure changed several factors and lost to V11/V16 on both cuts
of both tasks. This does not isolate TPE as the cause and is not an equal-budget
TPE-vs-random experiment. These are historical reported results, not a fresh
independent artifact audit on this laptop.

That same report attributes about59% of classification solver time to feature
selection work. Do not reintroduce that selector/FE change while testing HPO.
Avoid claiming that planned trials or a TPE sampler name prove adaptive search.

## Before an actual HPO admission pilot

1. Use the strong chosen SINGLE baseline, not claim it equals the full V11
   ensemble. Do not include new feature selection or new representation.
2. Pin Optuna4.2.1 in a separate allowed development environment AFTER LONG-01;
   preserve original requirements and active environment. Check CPU package
   aliases explicitly (xgboost-cpu), not only distribution-name metadata.
3. Measure one anchor's full nested cost before admitting a study. Freeze startup
   trials and allow enough remaining time for guided trials plus confirmation
   and full refit. Reserve is coordinator-owned; the optimizer's deadline must
   already exclude it. Count nested fits, failures and unattempted trials.
4. Ensure the anchor truly matches the effective adapter; no clipping a control
   into the search space. An invalid/failed anchor means no measured HPO advantage,
   not permission to report a new candidate as a proven gain.
5. Compare unchanged anchor, random and TPE at identical caps/splits/deadlines;
   outer labels are not objective values. Guard nonfinite/boolean pseudo-metrics,
   timeout cleanup, duplicate proposals, no-success and deadline-before-start.
6. Require real guided attempts before describing a run as adaptive evidence.
   Source/fixture tests alone cannot establish improved model quality.

Official pinned API references checked during this review:
[TPESampler4.2.1](https://optuna.readthedocs.io/en/v4.2.1/reference/samplers/generated/optuna.samplers.TPESampler.html)
defines startup sampling before TPE; [Study4.2.1](https://optuna.readthedocs.io/en/v4.2.1/reference/generated/optuna.study.Study.html)
requires finishing asked trials with tell. Do not infer newer-version semantics.

This note does not change the finite stage order or enable HPO by default.
