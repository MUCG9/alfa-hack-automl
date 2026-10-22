# V6 combined candidate (not submitted)

Archive: `../solution-v6-universal1.zip`, 63,842 bytes, 47 flat root files.
SHA-256 `b3b46b6a6bee7b7540fda0db22bf663a7afa090baff6e1b9ee72a3a221e3afb5`.
Source checkpoint `050659a`; builder Python 3.12.14.

Passed: **137 unique repo checks**, unchanged compiled source, 158.696 seconds;
23 exact-unpacked checks (repeats, not 23 additional unique tests). Original
requirements and historical release archives remain unchanged. No raw data,
weights, credentials, runtime package installation or added dependencies.

Includes v5 file/output/metric contracts, declared group/date validation,
independent targets, limited pointwise NDCG score-output ranking, correct requested
binary-class projection, and ONE optional calibrated XGBoost candidate for Macro
F1. The uncalibrated control remains available. Stage notes explain limitations.

Calibration passed paired seeds 42/43 and complete 3-fold group CV; pooled OOF
Macro F1 improved 0.611757099 → 0.617987602. This is component evidence on reused
public data, not the final combined-agent score or an official/private estimate.

Full public regression and classification for this exact archive **completed**
sequentially, offline, two threads, 1.7 GiB local tree guard, 10,100-second outer
watchdog per task. Both return zero, final refit succeeds and integrity is true.
See `public-full.json` and `classification-summary.json`.

- Regression: search RMSE 39.321110258; confirmation 34.229379712; mean
  **36.775244985**. Final CSV is byte-identical to v4 history3.
- Classification: selected blend Macro F1 0.653846737 / 0.652715743; mean
  **0.653281240**, compared with v4 0.652742609 and v3 0.653714716. The gain over
  v4 is small, and this is still below v3 classification alone. Search's best
  individual 0.658219218 is NOT the final selected blend's score.
- The selected blend is 90% calibrated LightGBM, 10% calibrated XGBoost. These
  weights were selected on reused search/confirmation data, not an untouched test.
- Classification final CSV SHA-256
  `58f52dfbfecb1416a456ed715a43cf944876a7f69eed73d7bf1e10170631b326`;
  agent elapsed 1,332.668 seconds. No official/private score is inferred.

Only v4 was authorized/uploaded. Do not automatically consume another submit slot.
