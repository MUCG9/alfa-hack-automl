# LONG-01 — V11 active model policy, three-hour anytime search

Captain23Oct2026 explicitly requested implementation/local runs, superseding the
documentation/transfer-only stop. Branch experiment/v11-long-budget-20261023.
No official submission, extra agents, packages, paid resources or API-key bypass.

Reference: immutable submitted V11 featureviews1 SHA
fbbd2511652814d7c05334ab0240f18b81e88a7b59dfc979efa617011dc84490.
Current runtime has the exact same enabled models and verified full-public CSVs
(V16 full-default-parity.json); its later postprocessors remain OFF.
Preserve original requirements and ALL old releases. No new feature/model/weight
policy; extended candidates use the EXISTING fallback/planner parameter policies.

## Why setting a timer alone does not work

Legacy search stops at default12 trials, hard cap14, not at its9900s deadline.
Its confirmation requires remaining>reserve+90; simply searching until1200s remain
would skip confirmation. A distinct opt-in anytime schedule is therefore needed.
This compares WHOLE procedures, not a causal isolation of wall time alone.
Legacy default path and current portfolio stay unchanged.

## Predeclared schedule

One coordinator-wide10800s per task, search cutoff1200s before that deadline;
30s final export margin. First run the unchanged12-trial baseline procedure with
at most half the wall budget, including confirmation/blending/fullrefit. Retain
its fully trained CSV as protected fallback, not just dummy/search predictions.
If no confirmed/full-refit baseline exists, report incomplete and do not pretend
to have completed an anytime quality comparison.

Then continue UNTRIED existing fallback/planner recipes from index12, bounded by
the same global search cutoff, max1000extra attempts and8consecutive failures.
No plateau stop and no artificial sleep to claim3hours. Keep signatures/negative
results. Validate a promising candidate on the SAME original seed43/forward
confirmation split while still before cutoff; no new split or validation-label
preprocessing. Compare best3 confirmed standalone recipes and the existing fixed
blend grid; do not create nested engine=ensemble recipes from old blends.

Promotion: strictly better two-cut mean AND neither cut worse than baseline
chosen solution. Keep baseline if not satisfied. This is reused-public adaptive
selection, not private/generalization proof. No retuning gates after outcomes.
During exploration never replace the fully trained fallback with a single-split
or failed/unconfirmed candidate. Persist best-found recipes/metrics separately.

At1200s remaining stop launching search/confirmation. Full-refit the best eligible
confirmed solution using its nested median iteration tree; publish atomically on
success. If refit fails/timeouts, the previous trained baseline remains valid.
Report best-observed versus actually exported quality separately, never attach
an unexported candidate metric to fallback CSV. No success/three-hour claim on an
interrupted run. Hard outer watchdog protects platform10800s; no forced waiting
if safety/failure/unique-attempt limits are reached.

## Evaluation, resources, evidence

Public classification and regression run sequentially, EACH budget10800s (up to
6h total);2threads,1.7GiB local tree guard, no GPU. Strict sequential tests/fits on
this low-free-RAM host. Offline: privateQwen environment absent, no live calls or
balance claim. Inputs/splits/metric/row/class/source SHA frozen. Runtime reports
all attempts, confirmed means, promotions, stop reason, timing and final fallback.

Before long fits: clock/worker mocks for deadline/reserve/checkpoint/failure and
selection, real small lifecycle, unchanged-source full suite, exact-unpacked gate,
immutable archive. Compare final BOTH task lifecycles to V11 search/confirmation
means and CSV validity, plus runtime/number of trials. Negative results retained.
At85%used five-hour usage, stop new stages and hand off actual controller state;
never reset credits. No official submit without a NEW explicit authorization.
