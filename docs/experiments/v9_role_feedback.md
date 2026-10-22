# V9: bounded structural feedback for semantic input roles

Separate task-understanding change on frozen V8 runtime infrastructure. It does
not change the model portfolio, training weights, augmentation or outer splits.

Previously a structurally valid path mapping was accepted before loading tables,
even if the model swapped fitting/test/sample roles. The task then failed after
the semantic stage had already claimed success.

## New behavior

- Only semantically selected roles get the new structural callback. Deterministic
  canonical/alias selection retains the existing discovery/validation path.
- Load selected tables, check sample/test row counts, identifiable targets,
  predictor overlap, dictionary shape and identifier constraints. Keep validated
  frames for discovery and multi-target dispatch instead of reading them again.
- A typed `RoleContractError` supplies fixed schema-only feedback, never row values
  or private IDs. One correction is allowed inside the existing TWO-attempt total,
  64KiB context cap, global deadline and gateway-call cap. No unbounded retry loop.
- Other table-read/parser/runtime exceptions are terminal; their TYPE is audited
  without sending their potentially private message to the model. Unsupported
  metric/target/data-quality errors later in TaskSpec remain terminal, not a reason
  to choose a different task or objective. The model cannot override path/security.
- Validating roles does not establish that a complete natural-language contract
  is understood. Arbitrary target/metric aliases, non-CSV formats, joint group/time
  constraints and native rankers remain unsupported.

Six new targeted checks cover cached frames, swapped roles, private-ID feedback,
bounded repeated failure, unsupported objective and terminal parser error. Initial
test runs caught two overly specific assertions (row-count validation precedes
target validation; the existing unsupported-metric message wording). Production
behavior was correct; assertions were corrected and the whole targeted suite rerun.

These are mock/local fixture checks, NOT live Qwen or real-data quality evidence.
Full169-check source audit, exact ZIP and full public gates are required separately.
The ongoing calibration study executes immutable V7 workers, isolated from this
canonical-source change; its already loaded harness/provenance are not rewritten.
