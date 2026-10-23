# LONG-01 — execution checkpoint, 23 October 2026

Source checkpoint: `2e15fe4`, branch `experiment/v11-long-budget-20261023`.
Protocol: [LONG-01_protocol.md](LONG-01_protocol.md), declared before public fits.
Archive: `release/solution-long01-anytime1.zip`, 83,544 bytes, 55 flat files.
SHA256: `565e0b40d225022f91a3217fae34ac1895044f63d40f854d69ddd4f2e2767a49`.
Original requirements unchanged. Live Qwen credentials absent; runs offline.

Verification COMPLETE: 287 unique unchanged-source checks and23 repeated
exact-unpacked checks PASS. Receipts in release/long01-anytime1/.
Full public run STARTED at 2026-10-23 10:30:23 UTC (13:30:23 Moscow).
Owned terminal controller session: 25832. Classification first, regression queued
in the same sequential benchmark. First classification worker completed OK and
the next started. Overall state is RUNNING, not PASS; no new final quality result
or official submission. Local artifacts stay ignored; only compact
reports/receipts go into Git. Do not commit new prediction CSV/NPZ/model assets.

Working output: `test-runs/long-01-20261023/public-full/`. Per task inspect
`automl_runs/run-v2/anytime_state.json`, `best_found.json`, and final `report.json`.
During the baseline phase its experiments are under `run-v2-baseline/`.
Final benchmark receipts are `task-00/assessment.json` (classification),
`task-01/assessment.json` (regression), then overall `assessments.json`.
Do not start a duplicate run if the controller is still alive. If reconnecting,
check reports/process status first; this file's RUNNING is a dated checkpoint,
not proof that the process is still alive or that both tasks succeeded.
Classification cutoff approximately16:10 Moscow; hard deadline16:30.
Regression starts after classification finishes; both tasks finish no later
than approximately19:30 if uninterrupted and not cut short by safety guards.
Keep the computer awake; local execution does not move to the cloud.

Planned full run, strictly sequential (classification then regression):

```sh
TMPDIR="$PWD/test-runs/long-01-20261023/source-gate/tmp" \
MPLCONFIGDIR="$PWD/test-runs/long-01-20261023/source-gate/mpl" \
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 \
../../work/ml-venv/bin/python -u scripts/benchmark_release.py \
  --archive release/solution-long01-anytime1.zip \
  --task ../../work/evaluation/multiclass/task.md \
  --task ../../work/evaluation/regression/task.md \
  --output test-runs/long-01-20261023/public-full \
  --offline --threads 2 --memory-gb 1.7 --watchdog-seconds 10800 \
  --time-budget 10800 --search-until-deadline \
  --finalization-reserve 1200 --max-extended-experiments 1000
```

Both tasks EACH get 10,800 seconds; search stops with 1,200 seconds remaining.
No artificial waiting after useful work finishes or safety guards trigger.
Fully trained baseline CSV is preserved during exploration. Final refit failure
keeps that baseline; `best_observed_mean` must NOT be confused with
`exported_mean`. Local benchmark uses 2 threads/1.7GiB guard, not platform8CPU/32GB.

Comparison reference (same reused public two-cut validation):

|Task|V11 search|V11 confirmation|V11 mean|
|---|---:|---:|---:|
|Classification MacroF1 ↑|0.663240317465|0.655395369258|0.659317843361|
|Regression RMSE ↓|38.902803731335|31.991659384341|35.447231557838|

No conversion from these local metrics to official points is known. More tuning
on reused public cuts is not independent evidence of private improvement.

## Completed — verified 23 October,18:51 Moscow

Both tasks completed with exit0; controller25832 ended exit0. Both actual
submission.csv hashes match report.json and assessment.json; integrity and
exported_full_fit_ok are true. This supersedes the historical RUNNING above.

|Task|Exported search|Exported confirmation|Exported mean|Harness seconds|
|---|---:|---:|---:|---:|
|Classification MacroF1|.6632403174648631|.6553953692580672|.6593178433614652|9598.310|
|Regression RMSE|37.56014204464436|31.833700517297636|34.696921280971|9607.868|

Classification:38 trials (12 baseline+26 extended), no gain; preserved fully
trained V11 baseline is a valid fallback, not a failed fit. Regression:12 baseline
plus690 extended attempts; exported_mean equals best_observed_mean, final refit
status ok, component iterations185/181. Mean RMSE improves by .75031027686669
(2.1167%); search improves1.342661686690425 and confirmation .157958867042961.
Both stop reasons search_deadline. The20-minute reserve was NOT required in full:
regression finished after approximately2h40, not an artificial wait until3h.

Classification CSV SHA256:
af64a22a5e9f5ff26ed817dfaa707e77e5bd9500dc63e52748521b00670efa96.
Regression CSV SHA256:
3b6912dbea6ef7daf3b39a300c9adfc4b89f0321f2a1a4c1a3293e0fea49df38.
Aggregate harness receipts: release/long01-anytime1/completed-assessments.json.
Raw predictions/model artifacts stay ignored in the original local directory.

The winning regression blend consists of two existing LightGBM alternatives,
equal weights,127/255 leaves and seeds526/311; it uses the same allowed
history/target-encoding/log-target policy, not a new external dependency.
This is adaptive reused-public evidence after many comparisons, not independent
CV or official score. No archive/default-policy promotion or upload is implied.
Next: locally regenerate the8 prepared BASE passports sequentially without fits,
verify closure, then evaluate the frozen single missing SEL confirmation.
