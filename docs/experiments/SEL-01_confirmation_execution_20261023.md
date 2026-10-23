# SEL-01 — one missing confirmation execution

BASE-01 local closure completed:8passports,original4V11/V16 runs,0fits. See
BASE-01_local_verified_20261023.json and ERR-01_local_diagnoses_20261023.md/JSON.
All required alignment/models/comparisons/slices complete; regression uncertainty
unavailable because each scope supplies only one forward period, not a failure.

Frozen plan remains sel01-confirmation-plan-r2.json, SHA
cd7838f953fdfc490ea4d2a0f5674ebf3bde5381464c38cdc71cf809596413e1.
Candidate model-a68c0bffe7b2b47ed864,original XGBoost recipe/seed and original
confirmation NPZ unchanged. Runtime selector OFF; no official upload authorized.

First technical launch: test-runs/error-selection-20261023/sel01-one-confirmation,
owned session86018,exit2 after2.965s. Actual worker exit1 before reading job.json:
relative job path was resolved from the fresh isolated output cwd. Confirmed
FileNotFoundError in candidate/worker.log, no result.json and NO model training
started. The receipt's new_recipe_evaluations=1 counts a submitted evaluation
attempt, NOT one completed ML fit or measured quality. Preserve these artifacts;
never invent a score. Protocol/source/protected cache fingerprints stayed intact.

Corrective change ONLY in development executor: resolve output path before
constructing the worker job.7 fit-free checks PASS, including regression test for
absolute worker path when caller supplies relative output. Canonical compiled ML
sources unchanged. This justifies ONE technical retry in a new immutable output
sel01-one-confirmation-r2,not another seed/hyperparameter or added search trial.
Original900s/2threads/1.7GiB whole-tree limit,predeclared keep/discard unchanged.
No overlap with LONG (already completed),no change to uploaded release.

Status at this checkpoint: corrected retry ready to launch; no candidate score
or promotion yet. Record actual result after its exit,do not automatically repeat
an interrupted or negative quality result.

## Completed corrected retry — DISCARD

r2/session94221 exit0; recipe evaluation73.479s,worker70.379s,iterations333,
459MiB observed worker peak. Originalsplit/plan/protectedartifacts/canonical and
compiledsources unchanged. Raw candidate confirmationMacroF1 .6395695856289502.
Same fixed blend-grid replay:

|Policy|Search|Confirmation|Mean|
|---|---:|---:|---:|
|V11 control,3equalweights|.6632403174648631|.6553953692580672|.6593178433614652|
|Marginalthird,XGBweight.5|.6642260242015644|.6509372175300082|.6575816208657863|

Search+.000985707 but confirmation−.004458152; mean−.0017362225. This is MIXED/
NEGATIVE under the declared both-cuts gate. DISCARD the policy, runtime remains
OFF. No groupedCV/fullagent/refit/export/promotion or officialsubmit for SEL.
Do not repeat without a concrete NEW hypothesis; no new seed/weights workaround.
One successful recipe evaluation comprised nested stopping and fitting; do not
count it as one elementary model fit. Technical firstattempt started0fits.
Evidence: SEL-01_confirmation_replay_20261023.json and fit_receipt JSON, original
predictions remain ignored under test-runs/error-selection-20261023/.
Next distinct stage HPO-01,with BASE/ERR already CLOSED.
