# ERR-01 integration — parallel engineering, 23 October

Captain explicitly approved implementation alongside the isolated LONG-01 run.
Branch: `work/error-selection-20261023`, based on `7b071ab`. No new ML fits,
full fixture suites, package installation, submission or active-run mutations.
No handoff preparation or artificial15%-remaining stop, per latest instructions.

## Provenance and scope

Fetched colleague branch `origin/work/night-research-20261023`, checkpoint
`01962f6`. Its diagnostics originate in `b2a5ad4`, BASE-01 closure `68775f2`.
Compared diagnostic files to68775f2: later changes only UTF-8/LF exact-byte
reporting and portability tests. Those fixes are included. Other colleague
ML/search/HPO/planner changes are NOT imported. Historical aggregate reports
retain their original scope and claims, not proof of our new local verification.

Imported: pure contracts, lazy error-analysis API, verified artifact loader,
regression/classification/comparison/slice/cluster-bootstrap diagnostics,
request preparation and BASE audit/finalization, guarded CLIs and focused tests.
Outputs are JSON/Markdown; this is project tooling, not a new dashboard.
Reproducible CLI scripts and requests are the audit trail; no new notebook or
source preview is needed to duplicate the existing implementation tests. Raw
rows/predictions stay ignored. The Data quality skill governs integrity checks,
not a new analytical UI or a model-selection decision.

## Gates

`tools/verify_error_integration.py` checks ALL55 existing compiled files against
the frozen LONG-01 archive and runs only fit-free unit/architecture/diversity
tests, sequentially, one thread, 768MiB/90s per script. This is NOT the full
release gate. New modules are lazily reached; existing ML policy is unchanged.
Gate PASS:101 focused checks (20 contracts,39 backend including flat,16
preparation,7 architecture,19 existing diversity), source unchanged. ALL55
legacy compiled files including original requirements remain byte-identical.
Added11 diagnostic modules. Receipt: ERR-01_integration_gate_20261023.json.
This does not claim a complete release gate or any ML-quality improvement.

After passing: verify the transfer bundle, prepare a bounded local BASE audit
without running bootstrap passports during LONG-01, and review historical
diagnostic evidence. Then predeclare SEL-01 with fixed first2 slots and unchanged
portfolio/order/calibration/blend-grid; replay is diagnostic, not an outer score.
No confirmation prediction is invented for an unconfirmed recipe. Actual new
fits/CV/full lifecycles wait until LONG-01 is complete and have separate gates.
