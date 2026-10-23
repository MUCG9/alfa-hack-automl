# Parallel engineering progress — 23 October2026

EMB-01 now:read EMB-01_progress_20261023.md,source f458c0c,7CPUfixture and7arch
checksPASS;ONE publicscreencontroller57404/test-runs/emb-20261023/public-screen/.
Fourcases sequential,max180s/2CPU/1.7GiB each;do NOTduplicate or modify active
canonicalcode. Original uploaded55files remain identical,defaultbackendOFF.

HPO-01 isolated DONE/DISCARD: all4arms12/12trials,18guidedTPESuccesses,256.021s,
sourceunchanged. TPE loses bothcuts vs random and searchvsanchor/LONG. See
HPO-01_isolated_progress_20261023.md/results/receipt. No new HPO fits/CV/promotion.
Next conditional EMB-01 CPU technicalpilot,not a new submitteddefault.

Current HPO-01 isolated study: read HPO-01_isolated_progress_20261023.md and actual
test-runs/hpo-isolated-20261023/study/{progress,result,process-receipt}.json.
Admission pilotPASSED (worker4.176s),Optuna4.2.1 separateenv ready,4equal-caparms
sequentially RUNNING from executorfac15cd. Do not repeat BASE/ERR/SEL (closed and
SELdiscarded) or start duplicatefits. Prior not-launched statuses are historical.

Latest: BASE-01 locally CLOSED,8new diagnostics/4original runs/0newfits; see
BASE-01_local_verified_20261023.json and ERR-01_local_diagnoses_20261023.md.
SEL-01 now DISCARDED: r2 exited0,fit70.379s/iterations333,all protected/source
hashes unchanged; samegridmean .6575816208657863 vs .6593178433614652control,
searchimproves but confirmationregresses. SelectorOFF;NO CV/fullagent/promotion.
Evidence SEL-01_confirmation_replay_20261023.json and fitreceipt. Do NOT repeat.
Next distinct HPO-01 isolated protocol HPO-01_isolated_protocol_20261023.md:
one LightGBM family,originalhistoryanchor,noFE,randomvsTPE,equal420s/cut/arm,
12trials/startup3,strictfitting-inner forward split. Separatepinnedenv preparing,
admission pilot not yet launched at this checkpoint.
SEL executor implemented with7 fit-free checks; first launch failed BEFORE
reading job (relative output path); corrected absolute-path retry justified,
same frozen recipe/split/seed/budget. See SEL-01_confirmation_execution_20261023.md
and actual fresh sel01-one-confirmation-r2 output. No candidate score yet at
this checkpoint; selector OFF. Prior prepared_not_run text below is historical.

Branch `work/error-selection-20261023`, parent7b071ab; ERR integrationa396368,
SEL predeclaration4aaebaa. This is the ordinary work journal, NOT a handoff.
Captain cancelled the15%-remaining stop and handoff preparation. Work continues
on the finite agreed plan, respecting real permissions/service limits.

## New checkpoint: LONG completed; one authorized official upload

LONG-01 completed both tasks; verified exports and controller exit0 saved in
6ce66a5, LONG-01_progress.md and release/long01-anytime1/completed-assessments.json.
Regression exported mean34.696921280971,classification unchanged. No more active
LONG fits, and no need to rerun this full public experiment.

Captain subsequently requested submission of best measured version. Separate
release profile enables exact tested offline long settings in task-only launcher;
ALL54 other files unchanged versus LONG-01. solution-long01-submit2.zip accepted
in queue, counter2->1. SHA364f49f62616fc9bddc0d1eeab1146eabfb27dd4ed10a595c88bab29b07d0a7a.
One earlier wrapper was rejected by unpacked tests, NEVER uploaded. Source gate
403unique after HTTP permission retry; final wrapper5tests rerun,23unpacked and
2bounded default-launcher lifecycles PASS. No changed ML policy/default research
selector. See release/long01-submit2/. No official score available yet; do not wait
or resubmit automatically. BASE8passports below remain prepared_not_run.
Next action: sequential passports+closure, then frozen SEL confirmation screen.
Historical active/provisional statements below are superseded by this checkpoint.

## Completed without new model fits

- Fetched colleague work/night-research-20261023@01962f6; imported ONLY diagnostics
  originating in68775f2 plus reviewed exact UTF8/LF portability fixes. No colleague
  ML/search/HPO/planner changes copied. Historical reports keep historical scope.
- Transfer bundle verified:852files/485objects. All10 actual public input SHA
  checks passed; historical V11/V16 archives and portable assessment/12trial/recipe/
  iteration parity verified. No completed training parity rerun.
- New local BASE adapter maps the actual declared organizer file locations using
  a fresh symlink view, not a copy or source rewrite. Eight original search/
  confirmation requests prepared. It NEVER runs passports automatically.
- Latest fit-free integration gate PASS:137 unique checks, source unchanged; ALL55
  original compiled files including original requirements byte-identical to
  LONG-01.12 dormant modules added (diagnostics plus selector). This is NOT the
  full release gate. Latest receipt ERR-SEL_integration_gate_r3_20261023.json;
  earlier126-check evidence remains preserved separately.
- Full source runner now registers398 expected unique checks. It has NOT run
  during LONG-01;398 must not be reported as passed based on137 focused checks.
- SEL-01 pure third-slot selector and fixed-grid replay implemented/tested, NOT
  wired into runtime. Predeclared criterion/protocol before actual cached screen.
  Frozen first2, fixed1/3 marginal criterion, no fitted weights or new recipes.

## SEL-01 diagnostic result, not a quality claim

Legacy replay reproduced V11 exactly on both cached cuts and mean.
New third choice is model-a68c0bffe7b2b47ed864; its fixed-thirds searchF1 is
.6639489668728188 versus control blend .6632403174648631. However the original
confirmation cache is absent, so recommendation is `needs_confirmation_fit`.
No candidate confirmation/mean/full-refit/private score exists. Do NOT report
the search-only difference as an improvement or enable the selector by default.
Source/frozen request/artifact fingerprints: SEL-01_cached_replay_20261023.json.
Missing predictions must NOT be substituted or inferred. No V14 rerun.

The missing candidate is the ORIGINAL uncalibrated XGBoost recipe (1800max
iterations,lr.035,depth6,mild class-weight power.5), primary iterations345.
ONE bounded confirmation recipe evaluation is prepared, NOT executed:
SEL-01_confirmation_plan_20261023.json and
SEL-01_confirmation_protocol_20261023.md. At most900s/2threads/1.7GiB whole tree;
nested fits counted separately. Plan uses original split bytes and artifact
hashes. tools/prepare_selector_confirmation.py cannot train; its readiness guard
requires both LONG-01 reports, successful assessments, trained exports and actual
CSV hashes.11 readiness/output-isolation tests passed within the137-check gate.
The saved blocked_by entry is a historical preparation snapshot: recompute
readiness before any future fit rather than treating it as a live lock/PID.

Also reviewed colleague HPO source/protocol/tm1 lessons without importing its
runtime or installing dependencies. See HPO-01_source_review_20261023.md. Its old
class campaign reached0 guided TPE trials; do not blindly repeat the combined
FE/selector/HPO procedure or call planned trials adaptive-search evidence.

## Current work and next allowed actions

LONG-01 regression remains active in its isolated original task-01; classification
finished without gain. Continue observing without edits inside that run, no new
ML fits/heavy suites/environment changes while it is active. Current branch edits
cannot affect copied frozen code. See LONG-01_progress.md and actual receipts,
not historical RUNNING/PID text. Local controller session25832.

BASE local state is `prepared_not_run`, NOT newly locally completed. Historical
colleague closure and eight passport aggregates were imported, but they are not
proof of fresh local report regeneration. After LONG-01 completes, use the8
request descriptors in test-runs/error-selection-20261023/base-prepared/audit/
baseline_inventory.json with tools/error_passport.py, one at a time; no training
is needed. Their output directories are fresh. Freeze source during each analyzer
because it verifies source stability. Then invoke error_analysis.api.finalize_baseline
on that inventory only if all required sections and actual final CSVs pass.
Reuse a verified existing profile if already completed; never overwrite evidence.

After that, define a bounded confirmation screen for the frozen missing SEL
recipe and original confirmation split, with both-cut keep/discard unchanged.
Only after a promising screen design fitting-internal selection plus external
group/forward evaluation of the whole procedure. Cached public labels are not
independent assessment. Keep original blend-grid and all first2/order policies.
HPO-01/EMB-01/LAMA-01/AGENT-01 remain later distinct conditional stages. Review
colleague's later reports before repeating research, not blindly merge them.

Environment inventory queried distribution metadata, not import availability.
In particular xgboost is supplied as xgboost-cpu in this CPU environment; a null
`packages.xgboost` does not prove the working XGBoost backend is absent. Optuna,
Torch and LightAutoML were not installed during the active benchmark. Do not
change this environment; later package pilots need a separate allowed-pin env.

No official upload, new release promotion, main merge, extra agents or paid
resources. Raw rows, prediction matrices, models and new run caches stay ignored.
