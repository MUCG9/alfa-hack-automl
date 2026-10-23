# LONG-01 submission profile —23October2026

Captain explicitly authorized one official upload of the best currently locally
measured version. Archive solution-long01-submit2.zip,83,696bytes,55flatfiles,
SHA256364f49f62616fc9bddc0d1eeab1146eabfb27dd4ed10a595c88bab29b07d0a7a.
Build: tools/build_submission.py --profile long01-submit. Original requirements
SHA9173b0388532fbd2a709e4f4b3029e3b9ccab685fce43a85261ffa1ba95efbe6.

ALL54 files other than solution.py are BYTE-IDENTICAL to completed LONG-01
archive SHA565e0b40d225022f91a3217fae34ac1895044f63d40f854d69ddd4f2e2767a49.
No ERR/SEL research modules, raw data, predictions, credentials or model weights.
Only the release launcher injects the exact offline long-run settings when no
explicit --time-budget is provided:10800seconds,1200refit/export reserve,
search-until-deadline,1000extended-attempt guard. Explicit-budget CLI retains
legacy behavior; normal python solution.py task.md enables this long profile.
This is deliberately the tested OFFLINE policy, NOT a new live-Qwen claim.
No dataset-specific winning recipe/seed or feature name is injected.

Local full quality evidence: ../long01-anytime1/completed-assessments.json.
Classification mean MacroF1 .6593178433614652 (unchanged); regression mean RMSE
34.696921280971 vs35.44723155783769,2.1167%lower. Both actual trained exports
verified with report/assessment CSV SHA, refit and integrity. Reused adaptive
public cuts, not independent/private evaluation or guaranteed official points.
Task runtime depends on platform data/hardware; the exact uploaded default
launcher was tested on two bounded fixtures, not another6h public replay.

Verification:

- Canonical compiled source unchanged across full suite:401checks passed in
  first attempt; HTTP test blocked by sandbox before network permission.
- The SAME2HTTP checks passed after permission, same source and test SHA.
-5launcher checks rerun on FINAL wrapper, including explicit-budget CLI guard;
  supersedes older wrapper-test SHA within the first full-suite receipt.
- Total403UNIQUE source checks (not an unqualified first-attempt suite PASS).
-23repeated exact-unpacked compatibility checks PASS on THIS archive.
-2additional bounded real exact-unpacked default-launcher lifecycles PASS,
  classification and regression; default10800/reserve1200/offline verified,
  explicit counts2baseline+1extended to avoid starting new public tuning.

Prior solution-long01-submit1.zip SHA0448d64e4d1d5c0f5a88a7ac579172ba661fd811b8ef321e1127dbf10d90862f
is REJECTED, NOT UPLOADED: its wrapper conflicted with explicit short budgets.
Its immutable failed unpacked receipt stays in ../long01-submit1/.
The corrected launcher leaves canonical ML sources unchanged.

Official acceptance/status goes in submission-20261023.json after verification
in the UI. Selecting a file/starting upload is not proof of queue acceptance.
