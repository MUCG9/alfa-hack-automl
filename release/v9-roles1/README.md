# V9 structural-role release (submitted once, result pending)

Branch `work/agent-budget-20261022`; source `41cae86`; Python3.12.14.
Archive `../solution-v9-roles1.zip`,69,565bytes,50flat root files.
SHA-256 `297647239badde608d349d053a89f9d7f98e8fffceb4a09633f675f99ebd7291`.
Original requirements unchanged; no added runtime dependencies/pretrained models.

Passed: **169 unique repo checks**, unchanged source,167.251s;23repeated exact-
unpacked checks also pass. They are not192unique tests. Evidence in this directory.
Includes V8's shared run/API budget and V9's bounded structural role feedback with
validated-frame reuse. See `docs/experiments/v9_role_feedback.md` for limitations.

No intended change to ML training, weighting, augmentation, model selection or
outer splits. New calibration/seed studies remain development experiments and
are NOT promoted into this snapshot. Current default is identity/noop, calibrated
LightGBM +optional inner-calibrated XGBoost portfolio with existing model selection.

Both exact-archive public lifecycles completed: exit0, refit/integrity pass.
Regression mean RMSE36.775244984792195; classification mean Macro F1 .6532812402233098.
Final CSVs byte-identical V7/V6. Evidence: public-full.json and task summaries.
No demonstrated ML metric gain; these are reused public folds, not official score.
Gateway tests use mocks/local HTTP, not live Qwen.

Captain separately approved ONE upload; accepted22October about08:03UTC /11:03MSK,
status «Решение находится на проверке», fresh counter2→1. Server result not waited
for; V9 official score unknown. Receipt: submission-20261022.json. V4 raw2184.173
belongs only to V4. Any further upload requires new captain authorization.
