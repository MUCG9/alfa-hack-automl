# V10 work checkpoint,22October2026

Branch work/cpu-research-20261022. Predeclared protocol e838209.
History implementation a9cedc0; error-complementarity tools9591c71.

- Opt-in history_asof implemented,17new checks pass;18existing quality and7architecture
  checks pass. No default portfolio promotion. Candidate release/solution-v10-asof1.zip
  SHA8f4ae2d350729a7e318ac0d21e903801424eaa6246963d9dd025161e809a89c8.
- tools/analyze_diversity.py supports same-row/split/class validation, per-class
  joint errors, conditional corrections, residual correlation, fixed0.5 blends
  and component expansion.19synthetic tests pass in the pinned core environment.
- Active classification paired run: test-runs/v10-balanced-paired, frozen V9
  workers,2threads,local1.5GiB guard. Three-seed full control42/43:
  MacroF1 .645027031/.648629834. Under70 candidate42=.655688478;
  candidate43 still pending at this checkpoint. Not a complete comparison yet.
- Remaining sequence: finish paired class; regression3forward cuts from exact
  new archive; if class direction supports keep, full3fold CV; then complete
  source/unpacked gates sequentially. No overlapping memory-heavy checks.
- First unpacked verification timed out locally after300s in resilience while
  host available RAM≈313MiB/swap free0. This is not a passed gate. Incident saved
  in v10_verification_timeout.json; audit found no leftover owned processes.
  Strengthen verifier ownership/failure receipts and rerun sequentially.
- No official submit, live API call or original requirements change in this stage.

This is an intermediate status; read newer evidence before repeating jobs.

## Newer checkpoint: paired screens complete, CV active

Classification4/4workers finished: under70 mean.652199459 vs matched3-model
.646828432, but only+.000655771 vs strong single component and loses seed43 to it.
Full3fold CV is ACTIVE in test-runs/v10-balanced-cv3, frozen V9 workers. Read its
results.json before touching processes or starting another heavy fit.

History1 all6workers finished: RMSE40.960973/33.984412/50.924670 control vs
39.051678/32.518745/51.096680 candidate. Failed all-three-cuts keep gate.
Follow-up history_min_periods=3 declared in v10_history_support.md and implemented
in05b2fdb;6worker tests pass, including insufficient-history exact control parity.
New archive release/solution-v10-asof2.zip,
SHA167663dee6fa3cfe62819859ba976976e2a9e6e333b89185dcece2dbe3639ca9.
Its support-gated metric screen is NOT STARTED; run after active class CV.
Full210source checks and exact unpacked gate are also still pending; run sequentially.
No method promoted/default portfolio change, no official upload.

## Latest immutable source / automatic follow-up queue

Source0933a66 hardens context validation and keeps the original observation period
unchanged by feature code.21history checks pass. Support experiment will now use
release/solution-v10-asof3.zip,
SHA32120f240f0703f0f80de4a020a9be9c3c737070774b217dcb28954bef3acf2a.
As-of2 remains an unmeasured historical archive. No original result overwritten.

Live sequential queue test-runs/run-v10-followups.py waits for all6class CV worker
results, then runs asof3 support3cuts, full212repo checks and exact23unpacked checks.
State test-runs/v10-followups-queue.json; logs test-runs/v10-*.queue.log. Those jobs
are queued, not yet successful. Do not launch duplicate heavy fits or edit src
while the source audit runs. No real API calls/official upload in this queue.
