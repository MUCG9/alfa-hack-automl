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
