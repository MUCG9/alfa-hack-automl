# Experimental as-of history1, not promoted

Source a9cedc0; archive ../solution-v10-asof1.zip.
SHA8f4ae2d350729a7e318ac0d21e903801424eaa6246963d9dd025161e809a89c8,
71,846bytes,51flat root files, Python3.12.3. Original requirements unchanged.

Adds opt-in history_asof: fitting-only strictly earlier context mean/trend.
Default portfolio unchanged.17new targeted checks pass, existing18quality and
7architecture pass. Full new source gate and unpacked verification are separate.
First unpacked attempt timed out locally; do not call it passed.

All6fixed regression workers exited0. RMSE control→candidate:
40.960973→39.051678,33.984412→32.518745,50.924670→51.096680.
Initial all-three-cuts keep criterion failed, so not promoted. Evidence in
docs/experiments/v10_history_results.json and v10_history_support.md. Follow-up
support-gated source gets a NEW archive; this historical snapshot is immutable.
No official upload/private score.
