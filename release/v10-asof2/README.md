# Experimental history support gate, measurements pending

Source05b2fdb; archive ../solution-v10-asof2.zip,
SHA167663dee6fa3cfe62819859ba976976e2a9e6e333b89185dcece2dbe3639ca9,
72,258bytes,51flat files,Python3.12.3. Original requirements unchanged.

Adds history_min_periods (2..10; explicit3 in follow-up recipe). Each inner/outer/
full fit counts only its own observation periods; insufficient support omits the
whole history block and records the decision. Original context/log control stays.
No default/portfolio change.19new history checks pass (13helper +6worker), including
held-out labels, same/future period exclusion and insufficient-support exact parity.
Complete210-source and23-unpacked gates are pending, as are paired metrics.

Read docs/experiments/v10_history_support.md and v10_progress.md. Do not reuse this
candidate's name for later source changes or claim upload readiness/private gain.

Before any metric run, static-context and observation-period guards were hardened.
The follow-up uses a NEW asof3 archive. This snapshot remains an unmeasured
historical checkpoint; do not treat its pending gate as a running job.
