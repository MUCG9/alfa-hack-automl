# Validation-contract extension after contract1

This is a separate change after the frozen `solution-v5-contract1.zip`. Existing
numeric-period public backtests keep their exact partitions. The extension does
not claim a better local score merely by changing the validation task.

## Implemented

- An unambiguous dictionary role `group`, `group_id` or `validation_group` supplies
  an explicit semantic grouping hint. Auto evaluation now keeps each such group
  together in outer, inner and full-CV partitions. Exact-feature-hash grouping
  remains the legacy fallback, not a substitute for semantic entities.
- If a rare class has only one group, try bounded group-safe partitions retaining
  every training class. Never silently split that group row-wise. An impossible
  contract fails explicitly. This does not guarantee a valid AUC fold exists.
- A documented future observation column may be a parseable date or a
  high-cardinality numeric timestamp. These use forward 20%-of-distinct-period
  blocks rather than a noisy single final-date row. Previous blocks exclude
  their future rows. All timestamps normalize to UTC.
- Small numeric period sets keep the original last-period backtests. Construction
  year, age, birth and duration hints are excluded from observation detection.
- Historical context-encoding recipes are not automatically offered for date
  strings or high-cardinality timestamps: their implementation expects the old
  small numeric-period contract. A conservative baseline remains available.
- `--validation-strategy legacy` explicitly preserves old row/hash validation.

Twelve unit checks pass, alongside the prior 18 quality checks. All six standalone
compiled lifecycle fixtures pass, including the two added fixtures for declared
clients and dated regression (34.683 seconds for the six cases). The seven
architecture tests pass. A complete 99-check suite and exact candidate verification
remain required before promotion.

## Remaining limits

Group discovery currently requires an explicit dictionary role, not arbitrary
free-text client/session inference. Date discovery requires a documented input
column and an entirely future test range. Multiple candidate group/time columns
are not guessed. When both a group hint and a future-period hint occur, forward
validation takes priority and a warning explicitly states that joint unseen-group
and future-period evaluation is not implemented. Do not describe this as enforcing
both constraints. A later semantic task-contract stage should resolve the actual
intent and add a separately tested joint strategy where necessary.
