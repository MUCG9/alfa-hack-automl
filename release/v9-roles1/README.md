# V9 structural-role candidate (not submitted)

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

Full exact-archive public lifecycles are still required. V7 completed both with
CSV parity V6, but this does NOT automatically establish the V9 public gate.
Gateway tests use mocks/local HTTP, not live Qwen. Official V4 raw score2184.173
belongs only to the uploaded V4; no official V9 score or next-upload permission.
