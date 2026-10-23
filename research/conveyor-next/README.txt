Local conveyor helper

This CLI only changes local task state. It never launches an experiment, a model,
Qwen, Codex, a service or a remote worker. The existing guarded runners and
canonical research lock remain responsible for actual execution and resource caps.

Use one authoritative directory on one local filesystem. Initialize it explicitly
with: python conveyor.py --root QUEUE init

A draft packet contains task.json. It names one hypothesis/factor, immutable
source/control/input/split/evaluator hashes, source Git SHA, real resource caps,
acceptance and repair rules, dependencies and explicit execution readiness.
promote validates these fields before moving drafts/ID to pending/ID.
claim --worker PLUS-1 moves at most one packet to running/PLUS-1/ID. Any running
task blocks another claim on this host. Claim does not assign an ML deadline.

A failed transition or stale transition lock is inspected explicitly. The helper
never steals a lock, recovers/requeues an apparently missing process, retries a
fit or changes a campaign clock. Resume the existing guarded campaign according
to its actual receipts and fresh PID/create_time ownership checks.

The owning worker finishes receipt.json, metrics.json, closure.json and summary.txt
inside its running packet. publish validates task binding and a clean external
closure, seals all terminal files, then moves the complete packet into results.
review verifies the seal and task hash before moving it to reviewed. Dependency
review_decision=accepted requires accepted review; completed means any reviewed
result, including a negative result used to plan a different experiment.

The helper preserves supplied metrics as opaque data. It does not independently
certify finite/null semantics, scores, closure truth or quality improvement; the
existing evaluator and root-observed execution evidence must provide that proof.
Do not call a schema-valid packet a verified ML result.

No live tasks or background services are enrolled by installing this source.
