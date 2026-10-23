# HPO-01 isolated pilot/study — declared before fits

Previous stage SEL-01 DISCARDED: third-slot rule loses confirmation and mean;
runtime OFF. BASE/ERR complete. This is NOT a repeat of colleague's combined tm1
feature-selection/FE/HPO run. ONE changed factor is the parameter proposal rule,
random vs TPE, within ONE LightGBM regression family. No new FE, class weighting,
target transform, calibration, model-seed or ensemble changes. No real API calls.

## Source/data/control

Parent e18edb0 plus the reviewed development-only HPO executor to be committed
before training. Canonical55ML files still match frozen LONG-01 SHA565e0b40….
Original organizer requirements SHA9173b038… unchanged. Separate development env
work/hpo-venv-optuna421 adds only original Optuna4.2.1 and its required dependencies
while reusing approved ML base; active primary env not modified, no runtimepip.
Record actual Python/distribution versions and code/data/split/recipe fingerprints.

ERR shows dominant context-history LightGBM and high SSE from unseen contexts;
choose ORIGINAL recipe model-049136473c313a8ac902,not the ensemble disguised as
a single model.1600maxiterations,lr.035,127leaves,lambda8,colsample.9,seed42,
minchild25,all original history/TE/logtarget/missing-feature policies preserved.
Strong references are original full V11/V16 meanRMSE35.44723155783769 and newly
completed LONG mean34.696921280971 (search37.56014204464436,confirm31.833700517297636).
Single-anchor reference is not equivalent to these full agents/ensembles.

## Admission pilot

ONE original-anchor recipe evaluation on the study split strictly INSIDE original
search fitting rows. At most120s,2threads,1.7GiB whole-tree; retain source/rows/time
metadata and actual nested cost. No outer labels used for objective or startup.
Admission requires successful finite RMSE,strictly earlier fitting periods and
cost<=20s; otherwise this420s-per-arm design infeasible,not permission to change
the space/caps after viewing external quality. A new cap would require a fresh
predeclaration. Pilot itself establishes no quality gain.

## Equal-budget study if admitted

Original two forward outer cuts (search Year5,confirmation Year4) kept byte-exact.
For EACH outer cut independently,make forward inner split of OUTER FITTING ROWS:
latest period within fitting is objective validation,strictly earlier periods fit.
Do not reuse a Year4-optimized winner when evaluating externalYear4. No outside
winning trajectory transplanted; selected recipe re-chosen independently in each
outer fitting set. Original outer validation labels read only by final scorer.

Two samplers per outer cut,ordered random then TPE; four arms STRICTLY SEQUENTIAL.
Each arm total420s,search cutoff300s,120s reserved for original anchor and selected
recipe OUTER refits/evaluation. No wall-budget extension for a preferred sampler.
Up to12trials including queued effective anchor127/8/.9. TPE startup3finished
trials (anchor+2random if all valid),then up to9guided; random gets same seed137,
same anchor and12attempt cap. Count failures/duplicates/unattempted/guided actuals.
Ask/tell completes every trial. Failure/nonfinite/bool objective is not a score.
No valid anchor=>no admissible comparison. Actual parameters must equal adapter
effective parameters,no clipping. Trial cap60s also bounded by search deadline.

Frozen search space ONLY:

- num_leaves integer31..255 (anchor127,not rejected leaf10);
- reg_lambda log-uniform2..20 (anchor8);
- colsample_bytree uniform.75..1 (anchor.9).

Same existing nested stopping inside objective fitting,not objective-heldout early
stopping. Features/TE/history/stopping rebuilt only from each relevant fit. Same
420s total/120reserve/12trials and original inputs for random/TPE. If budget cannot
finish both original-anchor and selected outer evaluation,report incomplete,not
impute candidate quality. Public cuts have been reused historically; NOT independent
private performance even with new fitting-internal isolation.

## Predeclared keep/discard

Need real successful guidedTPE trials on BOTH cuts before calling it adaptive
evidence. TPE must strictly improve BOTH outercuts vs equal-cap random and original
single anchor,mean improve; AND no worse than strong current LONG on eithercut,
strictly better mean. Otherwise discard/inconclusive,keep current runtime unchanged.
This conservative screen does not promote from study alone. Positive only:
appropriate additional forward validation of WHOLE fitting-internal procedure,
then fullagentboth tasks/refit/export/integrity/unchangedsource/exactunpacked.
Any later full-data HPO costs confirmation and export within original3h deadline.
No official submission authorized. Negative outcomes saved,not searched around.

Pinned API sources reviewed:
[TPESampler4.2.1](https://optuna.readthedocs.io/en/v4.2.1/reference/samplers/generated/optuna.samplers.TPESampler.html),
[Studyask/tell4.2.1](https://optuna.readthedocs.io/en/v4.2.1/reference/generated/optuna.study.Study.html).
