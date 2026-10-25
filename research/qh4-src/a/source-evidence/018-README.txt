Q3A01 R2 source-only correction

R1 ca8f and peer4311 are preserved verbatim under source-evidence/r1 and the
original directory. Only LiteralCSV, its verify_task wiring, and one explicit
exact_csv_roles helper change runtime source. All R4/C5/LOSS primitives and
assertions remain byte-exact, as do the original fifteen test methods/file.

Roles are an exact resolved-path map: pristine CLASS train gets declared target
and ID literal converters; pristine test and sample get ID only. Regression
targets and all numeric predictors retain native parsing even when a predictor
is named y_true, y_pred or the output column. Saved prediction CSVs are identified
from the already sealed worker-result sibling paths inside actual parent callback
roots. Submission roles get declared CLASS output+ID; validation roles get CLASS
y_true/y_pred. Unknown paths/conflicting roles/extraneous converters STOP.
No suffix or column name by itself grants a role.

Two NEW prepared synthetic mock/native-fixture methods cover numeric-name
collisions and lexical001/NA, yielding seventeen prepared/zero executed methods.
No candidates/tests/data/arrays/models/API/PID observations/actual clock ran.
Main CLI, schema, pretruth barrier, source qualification, common10800/audit600
(child570), metrics/provenance/fresh-refit/class gates and NULL failure semantics
are unchanged. Future actual qualification/root/seals/clock remain NULL/NOT_READY.
The full original rationale remains in source-evidence/r1/README.txt.
