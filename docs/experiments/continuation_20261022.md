# Autonomous continuation, 22 October 2026

Working branch: `work/autonomous-score-20261022`, based on
`work/pipeline-review-instructions` at `d950cb930a7a092e356f57f6de74104c17595a90`.
The captain explicitly requested continuation, frequent commits and one submission
if the candidate is ready. This current authorization supersedes historical
handoff statements saying that no submission is authorized. It does not authorize
merging main, force pushes, paid GPU provisioning or additional agents.

The captain reports v3 received **16/100**. This is user-reported official feedback;
the scoring formula and hidden-task breakdown remain unknown. Public validation
metrics must not be presented as predicted official points.

## Execution order

1. Reconcile the exact archive and local compiler, verify repository/unpacked tests.
2. Verify public input hashes, then complete a sequential full default offline
   classification run. Compare with the completed frozen-v3 baseline, not its old
   interrupted run. Preserve existing full regression results and provenance.
3. Reassess readiness, inspect the live platform and, if ready, submit one exact
   checked archive. Record queue acceptance separately from an official result.
4. Continue measured quality improvements, one change at a time. Never overwrite
   frozen archives or tune on official test labels.
5. At **15% remaining in the five-hour usage window** (85% used), stop starting
   long work, checkpoint results and prepare the next-agent handoff. Do not use
   account reset credits or purchase additional resources.

## Initial findings

- Historical history3 archive SHA-256:
  `8639e810d92633ca5127bc4c0aef15c75f4a0f48ebcdec2aa6c427b4840bd40f`.
- Its `automl_runner.py` differs from the local compiler in one f-string's quote
  style only. Every other compiled file matches byte-for-byte, and the changed
  module has an identical parsed AST under local Python 3.12.14. The previous
  agent built with Python 3.12.3. This is not evidence of a changed ML algorithm.
- The strict current-source verifier correctly rejected that byte mismatch. Keep
  the historical archive immutable and build a separately named local candidate;
  do not weaken the verification gate to claim a byte-identical build.
- Public raw data, credentials, predictions and local logs stay outside tracked
  files. Local heavy runs are sequential with two threads and a whole-tree
  memory watchdog because this machine has little available RAM.

## Fourth submission

The captain subsequently requested immediate upload because server checking takes
a long time. Uploaded `release/solution-v4-history3-py31214.zip`, SHA-256
`734ec4da69c7513f1896a9b528c35ae5489206df2af360c7650246d4bc0155f1` (51,695 bytes).
The exact archive passed the 23 unpacked compatibility/fault/lifecycle checks.
At upload, the full offline classification had completed 12 search experiments;
confirmation and full refit were still running. Unfinished v5 changes are NOT in it.

The platform shows the named archive and «Решение находится на проверке».
However, the history currently associates the new filename with the old v3 record,
old 21 October 23:37 time and old 1723.691 score; the displayed attempt count stays
3. This inconsistent UI does not establish a new score or exact attempt debit.
Do not resubmit automatically. See `release/v4-history3/submission-20261022.json`.
Server results are not being waited for, as requested.

## Completed full history3 classification

The exact uploaded archive completed the offline default classification lifecycle
after upload: 12 search experiments, confirmation, selected three-component blend,
full refit and export, integrity true, 1,422.972 seconds inside the agent
(1,423.986 seconds including the local harness).

- Search blend Macro F1: **0.657720274**.
- Confirmation blend Macro F1: **0.647764944**.
- Mean: **0.652742609**, versus completed frozen-v3 **0.653714716**.
- The decrease of about 0.00097 means classification is NOT an established
  improvement over v3. Regression's previously measured improvement is separate.
- Selected equal weights: calibrated LightGBM and two XGBoost variants. Final
  prediction SHA-256: `2753a7af287633fda9be4172c103a85641cfccffbef14d4a7e2f2b2fa072b707`.

Evidence: `docs/experiments/v4_history3_class_full_20261022.json` and
`release/v4-history3/classification-full-20261022.json`. All these reused public
fold scores are local development evidence, not an official/private estimate.
