# UAR-v1 contract

This is the target contract for the new integration, not an attestation that every
existing runtime path already satisfies it. Historical frozen research remains
unchanged. Only the root integration writer changes shared interfaces and defaults.

`TaskSpec` must bind task kind, evidence for target and ID columns, train/test/sample
roles, row order, lexical identifiers, label order and output schema. Ambiguous
schema is an explicit unresolved state. Dataset names and filenames do not choose
model families. Numeric-looking identifiers and class labels retain their lexical
form until an intentional, reversible conversion is established.

`MetricSpec` binds objective name, direction, prediction kind, source and evidence.
Missing, unsupported or conflicting objectives remain unresolved; optimization
must not guess RMSE or Macro F1. A format-only fallback is possible when output
schema is independently known. The legacy parser still has inferred defaults;
the strict resolver is opt-in until its integration passes checks.

The root `solution.py` positional task interface must be checked against the
organizer baseline. The target invocation is `python3 solution.py task.md` without
external private JSON or research flags. A valid early result should precede
profiling, LLM calls and model fitting. Publication uses a unique sibling temporary
file, flush/fsync where supported, close and atomic replace. Any failed candidate
preserves the last valid result. RMSE fallback uses a mean, MAE a median; class
fallback respects the requested labels or probability schema and fixed class order.

Adapters distinguish libraries allowed by the organizer, installed versions,
implemented code, source verification and measured readiness. Select a small
appropriate portfolio while retaining the strong anchor. Estimated costs are
heuristics until actual bounded runs supply measurements.

Scout/Researcher/Judge are runtime roles passing typed, bounded JSON proposals to
deterministic tools. Native developer agents are a separate engineering resource
and are excluded from the submitted archive. Arbitrary generated Python is disabled
unless a real isolation boundary is independently established; AST and subprocess
execution alone do not establish a sandbox.

All-inclusive wall and monotonic deadlines begin at invocation. Refit, final CSV,
verification and cleanup have explicit reserves. Unknown ownership, inaccessible
process traversal, exceeded budgets and missing artifacts cannot become success.
Existing frozen experiments keep their originally assigned clocks and inventories.
