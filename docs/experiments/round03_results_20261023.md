# ROUND-03: exact-context reuse passes the narrow efficiency replay

Qwen selected the already measured PIPE02 augmentation recipe. Three actual
owned worker identities produced four logical responses on unchanged saved cut0.
All ordered prediction arrays match EXACTLY, including the historical origin;
native RMSE38.59512241438067 is a component metric, not complete PIPE02's score.

|Request|Seconds|Actual worker launches|
|---|---:|---:|
|Uncached1|13.934|1|
|Uncached2|13.921|1|
|Cached cold|13.880|1|
|Cached hit|0.866|0|

Observed pair speedup1.889x. Hit time includes identity/artifact validation and
is not zero. This narrow replay supports dev-harness reuse, not a general runtime
speed guarantee or ML gain. Canonical runtime/defaults and release are unchanged.
Within-study duplicate filtering already exists; cross-study/context-identical
replays are the new target. Changed contexts must miss; altered artifacts refuse
reuse. Five no-fit boundary/serialization/observation checks PASS.

Two setup attempts failed BEFORE any worker launch: missing XGBoost distribution
metadata despite importable2.1.4, then an observer proxy omitted STDOUT. Both
receipts preserved. Fixes fingerprint the module fallback and preserve subprocess
attributes, with regression checks. Successful attempt4cee160 retains the
ORIGINAL2160s deadline; no invisible budget reset. Source/input/harness/plan
unchanged during successful replay, independent artifact audit PASS.

[Aggregate evidence](round03_results_20261023.json). Next hypothesis: multiple
inner forward periods for marginal HPO, using the measured conservative cache
only to avoid identical native fits, not to modify any model/objective output.
