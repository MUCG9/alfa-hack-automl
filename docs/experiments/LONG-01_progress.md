# LONG-01 — execution checkpoint, 23 October 2026

Source checkpoint: `2e15fe4`, branch `experiment/v11-long-budget-20261023`.
Protocol: [LONG-01_protocol.md](LONG-01_protocol.md), declared before public fits.
Archive: `release/solution-long01-anytime1.zip`, 83,544 bytes, 55 flat files.
SHA256: `565e0b40d225022f91a3217fae34ac1895044f63d40f854d69ddd4f2e2767a49`.
Original requirements unchanged. Live Qwen credentials absent; runs offline.

Verification COMPLETE: 287 unique unchanged-source checks and23 repeated
exact-unpacked checks PASS. Receipts in release/long01-anytime1/.
Full public three-hour fits have NOT started at this checkpoint. No new quality
result or official submission. Local artifacts stay ignored; only compact
reports/receipts go into Git. Do not commit new prediction CSV/NPZ/model assets.

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
