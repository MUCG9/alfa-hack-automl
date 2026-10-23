# AGENT-01 — bounded application assistants, offline admission

Separate from SEL/HPO/EMB/LAMA modeling: no new ChatGPT/Codex agents or chats.
Implement three sequential roles INSIDE the application: analyst selects a
diagnosis supported by supplied aggregate evidence, researcher nominates at most
two prevalidated experiment IDs, critic accepts a subset or rejects both.

Default OFF, no change to runner/planner or uploaded archive. No automatic fit,
promotion, split/metric changes, feature code, package install or network outside
the existing credential-owning LLM gateway. Shared RunBudget is REQUIRED; helper
calls consume its existing coordinator-wide count/deadline, never a fresh budget.
At most three logical calls, output caps512/1024/512 tokens, timeout<=30s each.
Transport retries remain the gateway's existing behavior; ledger distinguishes
logical calls, known HTTP attempts and incomplete token usage. This is NOT a
hard monetary cap or a promise of complete retry-token accounting.

Input: bounded typed aggregate metrics, feature names and a finite catalog of
same-engine single-parameter alternatives to an incumbent. No rows, target
values, predictions, keys, task prose or free-form descriptions. No model-written
code/expression execution. Exact schemas, finite numbers, known evidence/IDs,
single-factor bounds and immutable recipe hashes checked locally. Model verdict
is only a proposal; numerical external evaluation remains authoritative.

Offline contract gate: default-zero-calls, absent/shared/exhausted/deadline budget,
malformed JSON, invalid IDs/evidence, injected code, multiple-factor alternatives,
critic subset, accounting/privacy, independent response objects and uploaded ZIP
immutability. Mock success is NOT live Qwen availability or score improvement.
Do not extract historical credentials. If safe current process configuration is
absent, record live equal-budget comparison blocked and leave assistants OFF.
Live promotion would require a predeclared equal total budget comparison against
the existing single planner, fitting-only search, external group/forward checks,
then both-task full lifecycle. No promotion on assistant opinions alone.
