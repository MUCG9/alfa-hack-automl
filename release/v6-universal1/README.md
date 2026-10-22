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

Full public regression and classification for this exact archive are running
sequentially, offline, two threads, 1.7 GiB local tree guard, 10,100-second outer
watchdog per task. Do not mark this gate passed until both reports/refits exist.

Only v4 was authorized/uploaded. Do not automatically consume another submit slot.
