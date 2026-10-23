# HPO-01 isolated execution checkpoint

Protocol frozen in889af4a before fits; reviewed executor/tests fac15cd. No canonical
ML runtime changes.7fake-objective/partition checks PASS in actual Optuna4.2.1
separate env. They include9real-TPE-guided proposals against fake objective,not
new ML quality evidence. Main source suite remains403unique+7focusedSELguards;
the dedicated optional HPO checks are separate,not a fresh417-check fullgate.

Environment work/hpo-venv-optuna421 uses approved primary ML site-packages via
approved-base.pth. Optuna4.2.1,PyYAML6.0.2 and original model/numpy/pandas pins
verified; Optuna dependencies installed only in NEW env. Original requirements
and primary env untouched. PyYAML initially resolved6.0.3 as transitive,then
corrected to original6.0.2 BEFORE any pilot. Not an unapproved runtime dependency.

Resource pilot session46588 completed exit0:6.965s guarded total,4.176s worker,
2nested fitting steps,innerRMSE31.846185166957753. AdmissionPASS<=20s. Original
search outer-fitting rows only; train22054 /inner validation12946,cutYear4.
No outer evaluation in admission,not a quality gain. Source unchanged,1.7GiB/2CPU.
Evidence HPO-01_admission_pilot_20261023.json,HPO-01_environment_source_20261023.json.

Equal-budget STUDY now launched at test-runs/hpo-isolated-20261023/study/.
One controller executes four arms sequentially: search-random,search-tpe,
confirmation-random,confirmation-tpe;12trialcaps/startup3/equal420s caps including
120reserve. Source/recipe/feature/weight/seed policies unchanged; exact original
outercuts. Read progress.json and final result.json/process-receipt.json,not this
historical active statement,to determine live state. Do not start a duplicate.
Owned session is recorded in the current chat/tool result. No automatic retry
on a negative/incomplete outcome. Study success requires BOTH-cuts strict win vs
random andanchor,nonregressionvsLONG and meanimprove; see protocol,not one scalar.
Then only additional-forward research,not defaultpromotion or officialsubmit.

Other stages EMB/LAMA/app-levelAGENT not started. Their conditional admission
depends on measured evidence/resources/allowed versions; no actual extra agents.
