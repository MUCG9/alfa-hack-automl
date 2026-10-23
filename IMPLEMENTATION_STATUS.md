# Universal AutoResearch: UAR-v1

The new specification is being integrated into the existing pipeline. The real Qwen campaign LA2 completed training from its immutable archive, then
failed its audit metadata check; a separate saved-artifact audit is being prepared. Development changes
below have not changed that campaign or the qualified V11/V16 release.

| Work item | Actual state | Qualification still required |
|---|---|---|
| Task/metric contract | Strict opt-in `MetricSpec` and objective resolver prepared | Independent review, 12 tests, module packaging and entrypoint wiring |
| Publication | C01 commit `e638f568`: metric-aware fallback, unique atomic temporary files, optional validated checkpoint | Independent review, 12 tests, earlier fallback ordering in entrypoint |
| Model portfolio | M01 commit `978bf40e`: typed pure family router | Independent review, 12 tests, explicit opt-in wiring, matched ML experiment |
| Process observation | E01 strict observation patch, constructor-cost repair pending | Independent review, meaningful mocked failure tests, caller opt-in and denial propagation |
| Idea registry | Exactly 150 source IDs, root-owned | Per-idea implementation and evidence; registry presence is not implementation |
| Parallel development | Four actual native agent slots, three isolated branches/worktrees | Cross-review and serial resource-leased execution |
| Linux coordination | Source packet 05 received and reviewed; no model fits yet | Exact private authority/job bindings, then separately bounded six-job class experiment |
| Platform release | Historical V11/V16 retained | New generic ZIP, both standard CLI tasks, refit/CSV and clean-platform gates |

The registry currently has 144 planned, four isolated implemented, one deferred
and one blocked entry. These statuses describe UAR-v1 qualification, rather than
denying that historical mechanisms exist. No new feature is enabled by the registry.

Unit tests for this development wave are prepared, **not executed** until a root-owned serial test lease is admitted after the saved-artifact audit. Source parsing and Git checks are recorded
separately. No new ML improvement is claimed for these code changes.

Automatic submissions are disabled by the latest user specification. Existing
authorization to publish checked research and dispatch changes remains in effect.
No main changes, force pushes, new services, paid resources or external teacher
models are part of this work.

See [contract](docs/contract.md), [validation protocol](docs/validation_protocol.md),
[measured results](docs/experiment_report.md) and [next steps](docs/next_steps.md).
