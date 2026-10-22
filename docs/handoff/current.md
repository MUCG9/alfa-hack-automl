# Текущая передача — V11–V17, 22 октября 2026

Ветка **work/llm-upgrade-20261022**, основана на коллеги6aefbd9.
Main неизменён:5dd6b0f2910af7aa706d400bc28093a277ac2932 (V2).
Работа одним агентом; никаких новых зависимостей/платных ресурсов/reset credits.
Фактический HEAD и origin проверять в Git: handoff commits идут после65ce8db.

## Лучший квалифицированный результат

|Полный default pipeline|Повторённый history4 контроль|V11 featureviews1|
|---|---:|---:|
|Classification search MacroF1|0.6538467374261537|0.6632403174648631|
|Classification confirmation MacroF1|0.6527157430204659|0.6553953692580672|
|Classification mean MacroF1|0.6532812402233098|0.6593178433614652|
|Regression mean RMSE|35.44723155783769|35.44723155783769|

Оба class cuts лучше. Regression final CSV побайтово совпал с history4.
Это full search/confirmation/selection/refit/export, но НЕ full K-fold OOF и НЕ
оценка private/официальных баллов. Предыдущая CV коллеги — отдельный3fold gate:
pooled .640209809443→.645099303706, exactly_once, все predeclared gates PASS.

Квалифицированный архив: **release/solution-v11-featureviews1.zip**,
runtime e11409e,74443bytes,52flatfiles,
SHA fbbd2511652814d7c05334ab0240f18b81e88a7b59dfc979efa617011dc84490.
230unique unchanged-source +23repeated exact-unpacked checks PASS.
Full class2691.782s (harness2693.394), regression harness225.692s на2CPUthreads.
Полные отчёты/assessments/проверки: release/v11-featureviews1/.

CSV fingerprints:
- Class af64a22a5e9f5ff26ed817dfaa707e77e5bd9500dc63e52748521b00670efa96.
- Regression 05ccd9eabcbf29f4b858e9cd89f6dfe568ce1bdddb32a397c71b98ef1c0c1673.
- History4 class control 58f52dfbfecb1416a456ed715a43cf944876a7f69eed73d7bf1e10170631b326.

V11 adds ONE typed LightGBM feature_views=categorical_te_pair candidate, schema-
declared first3categoricals, existing group-cross-fitted statistics/pairs,
smoothing20, fixed internal50/50. Original categories remain. Per-view iteration
trees survive global blend/confirmation/recursive median/full refit.
Selected global equal-thirds blend: TWO typed-view recipes +calibrated XGBoost.
No public column names in runtime, no forced class weights/log target/augmentation.
Default12trials/9900s/old relative portfolio order retained; fallback inheritance
makes the whole procedure slower than control. Source src/automl is canonical.

## Latest code and finishing job

Canonical runtime **f72c6df**, frozen **release/solution-v16-mean1.zip**:
SHA 68e1eb0c933807720178ef4708df2c0dbf55fe9940b0dfb849d7704dbe3b2566,
79054bytes,54flatfiles, Python3.12.14.
**258unique unchanged-source checks169.114s +23repeated exact-unpacked PASS.**
V12–V16 add dormant typed postprocessors and guards, NOT new enabled model defaults.

Final full-default parity started around14:42UTC, execution session15685:
test-runs/llm-upgrade-20261022/final-default-parity.
Offline,2threads,1.7GiB tree guard,10100s watchdog/task, jobs1,
FULL default12trials (no max-experiments override), regression FIRST then class.
At this checkpoint it is RUNNING. Read task-00/assessment.json and task-01/
assessment.json / assessments.json for completion; do not duplicate this job.
Expected both final CSVs and scores match qualified V11 exactly.
No source/test edits during current integrity stages; docs/evidence only.
If interrupted, retain V11, honestly mark latest-source full gate incomplete.

Finishing checkpoint15:10UTC: regression has COMPLETED exit0/refit/integrity,
221.052s, same search38.902803731334785 /confirmation31.991659384340597,
mean35.44723155783769, exact expected final CSV. Portable assessment/report and
source manifest in release/v16-mean1/. Static final-source audit there verifies
archive↔canonical↔258-test-receipt equality, original requirements and ALL10inputs.
Classification11/12search experiments complete, ALL metrics and recipes exactly
match qualified V11 trace; experiment11 is the long final search learner.
This partial trace is NOT confirmation/refit/full-default PASS. The bounded
controller remains active at handoff; it may finish locally after this snapshot.
Do not assume it completed or is still running without checking actual files.
Execution15685 identifies this session, not a process ID to kill from another chat.
Local artifacts are ignored, so another computer cannot recover their later
results from Git unless a continuing agent first commits portable evidence.
No new experiments are to be started in this finishing checkpoint.

## Rejected studies — do not silently enable or rerun

|Study|Observed result|Decision|
|---|---|---|
|V12 bounded log-weight Nelder–Mead|paired mean F1 .651543688→.650925929, both cuts worse|OFF; no CV/default promotion|
|V13 pinned AutoGluon1.3.1 GBM+CAT|paired mean F1 .651543688→.627271597, both worse|Dev-only extension, no runtime integration|
|V14 thirteen-trial cached proposal|hypothetical mean .660102396 but search below V11|reject_without_fits,0new fits; not implemented|
|V15 log-residual moment correction|latest forward RMSE39.051678→40.160774; older cuts exact parity|OFF|
|V16 original-scale LS correction|latest forward RMSE39.051678→39.354053; older cuts exact parity|OFF|
|V17 min_child_samples10 in both views|F1 .655863466/.653724308→.645102660/.647068331|reject; keep25, no CV|

All protocols/candidate configs/results/gates are in docs/experiments/v12…v17_*.
Raw rows/predictions/models remain ignored in test-runs, never Git.
V12 optimizer has positive bounded [.4,2.5] factors, old coordinate warmstart,
regularized log-space objective and numeric acceptance safeguards; max400fev.
No arbitrary unbounded/negative supplied-Nelder–Mead snippet copied.
AutoGluon synthetic poison/isolation/full-refit checks PASS; feature generator
explicitly prefitted on inner train only because framework default concatenates
train+tuning data. The negative result is THIS procedure, not all AutoGluon.
V15/V16 use inner calibration only, matching iteration and history-support guards,
bound [.8,1.25], exact identity when ineligible. Neither transfers forward.
Do not claim these fitting optima guarantee outer RMSE.

## Authorization / API / quota

No official upload THIS continuation. ONE async question asks permission for
**exact V11 archive**; no answer received yet. Silence is not approval.
If captain answers yes: freshly inspect login/counter, upload exact V11 ONCE,
save receipt/counter/queue proof and do not wait server results. Do not substitute
V16 without approval. Historical1remaining afterV9 is NOT a current counter.
Last captain-reported official V9 raw2187.849,1940.2s,his21.87/100; latest request
says23/100 without per-task breakdown. No new authenticated official score.

No live Qwen calls or dependency installs in this continuation. Existing local
openai SDK/mocked gateway tests are not live verification. Private process env
checks found OPENAI_API_KEY/BASE_URL/MODEL and QWEN_API_KEY absent; do not reuse
exposed historical chat key or bypass denied private credential input.
600RUB is a shared organizer API budget, not a verified current balance.
LightAutoML/Optuna/FLAML/torch/imbalancedlearn not installed locally; no runtimepip.
AutoGluon was already installed and actually fitted, no install claim.

Actual quota readings:12:01UTC primary0%used,14:32UTC71%,14:40:58UTC76%used;
15:10:02UTC84%used/16%remaining, weekly92%used. Handoff is being finalized BEFORE
the85%used cutoff; no new long stage after final parity was started.
Current final parity is the only long stage; checkpoint even if latest gate fails.
No reset credits consumed or other agents spawned. Latest confirmed push before
finishing receipts:8375b67 on this branch; final handoff commits follow it.

FINAL quota observation15:14:20UTC:85%USED/15%REMAINING,weekly92%used. Threshold
reached; finish this handoff and STOP NEW WORK. Confirmed HEAD=origin6c27a65 before
this quota-note commit, clean tree, main unchanged. Class still11/12exact-trace,
no fullreport/assessment; bounded controller is the only remaining owned ML job.
Do not silently promote V16 or restart research after this quota-triggered stop.

## Reproduction and next stage

Current local Python: ../../work/ml-venv/bin/python from repo, Python3.12.14,
numpy1.26.4/scipy1.12/pandas2.2.3/sklearn1.5.2/LGBM4.6/XGB-cpu2.1.4/CB1.2.8.
Local host15.3GiB with low free RAM and used swap: fits sequential2threads, suite1.
Platform remains Python3.12/8CPU/32GB/noGPU/3h per dataset; measured2threads is not
proof about every hidden task. All10public task/CSV SHA matched public_inputs.json.

Original requirements SHA:
9173b0388532fbd2a709e4f4b3029e3b9ccab685fce43a85261ffa1ba95efbe6.

On another computer, clone this branch, obtain original organizer data and private
API env separately; do not expect ignored local rows/venv/predictions in Git.
Check actual default parity completion first, then read next-agent.md.
Historical current/STOP/prompts preserved in history-current-before-v11.md,
agent-instructions-before-v17.md and ../prompts/history/next-agent-before-v11.md.
