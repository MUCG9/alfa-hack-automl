# V10 history4: validated local release candidate

Source8f6b73e. Archive ../solution-v10-history4.zip,
SHAa42fcb1557ec0cf2455abb3add9d6968a8388aedcfcf8d554b26ed73a45788f8,
72537bytes,51flat files,Python3.12.3. Original requirements unchanged.

Adds one minimum3 as-of history portfolio candidate immediately after existing
metadata-history/log recipe, only numeric observation-period regression with
schema-described static numeric properties; pointwise ranking excluded. Prior
recipes/order,class/text policies,12trials,9900s deadline,confirmation and blends
preserved. Existing fallback may inherit history from a winning incumbent.

## Complete local gates

- 216unique original repository checks passed (repo-tests.json). Later full219
  checks including multiclass TE isolation passed, source_unchanged=true, all51
  source hashes equal this manifest (additional-repo219-tests.json).
- 23repeated exact-unpacked checks passed, matches_current_source=true.
- 14frozen-V9 portfolio-parity cases and8search-choice checks passed.
- Both default full regression runs exit0,final refit=ok,integrity=true.
- Full-size classification bounded1trial/600s lifecycle exit0,refit/export/integrity
  pass. This is packaging coverage, not a new default classification quality run.

|Default full regression|V9 control|History4|
|---|---:|---:|
|Search RMSE|39.321110258|38.902803731|
|Confirmation RMSE|34.229379712|31.991659384|
|Fold mean RMSE|36.775244985|35.447231558|
|Pipeline seconds|336.888|389.131|

Predeclared both-cuts improvement gate PASSED,mean RMSE3.611% lower. Selected90/10
blend of minimum3 as-of LightGBM and unchanged CatBoost. New final CSV SHA
05ccd9eabcbf29f4b858e9cd89f6dfe568ce1bdddb32a397c71b98ef1c0c1673.
Control exactly reproduced historical V9 CSV. Evidence quality-comparison.json,
regression-{assessments,report}.json,v9-baseline-*.json,sequential-gate.json.

Technical local packaging/lifecycle gates complete. No official submission or
private score for V10; repeated public folds do not guarantee platform improvement.
Classification model quality is unchanged by intent and historical recipe parity;
a bounded1trial run is not evidence of a new full-default MacroF1 score.
Historical asof1/2/3 archives remain immutable. New experiments must not overwrite
this archive; source changes require a new named release and independent gates.
