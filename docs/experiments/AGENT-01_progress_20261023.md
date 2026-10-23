# AGENT-01 application assistant checkpoint

Protocol91b61f3 predeclared before implementation. Public boundary:
automl.search.api.request_advice(AssistantRequest,...,enabled=False).
No new Codex/ChatGPT agents, chats or messages. Default runner/planner untouched.

Three fixed sequential roles through the existing credential-owning gateway:
analyst selects a schema-checked diagnosis/evidence refs; researcher picks at most
two exact catalog IDs; critic accepts a subset or rejects. No executable output,
model-written features, tools, rows, arbitrary task prose or alternate evaluator.
Input catalog has at most8 same-engine single-parameter alternatives to the
incumbent, validated locally against fixed bounds and recipe signatures. Normal
external numerical evaluation still decides whether proposals are useful.

Requires an EXISTING RunBudget, never allocates/resets a local helper budget.
All roles share global remaining wall time/logical-call count and existing usage
ledger. Output caps512/1024/512 tokens and timeout30s each. Existing gateway may
retry; usage accounting explicitly marks unknown retry usage incomplete, not
hardcurrency/token-total assurance. No separate helper API keys or client.

First16offline contract tests PASS in.025s. Covers disabled/unconfigured/shared/
exhausted/deadline limits; zero transport when denied; three-role accounting;
invalid schemas/IDs/evidence/code, critic subset, single-factor catalog, input
immutability and clean ledger. Full final source gate still pending,not claimed
from these focused tests. Optional LAMA/Torch/HPO checks remain separate scopes.

LIVE BLOCKER: checked only presence of OPENAI_API_KEY/OPENAI_BASE_URL/OPENAI_MODEL
in current process: all false. No historical secret recovery or new API calls.
No equal-budget live comparison vs single planner or private quality result.
Helpers stay OFF; enabling them is not a demonstrated score improvement.

Finite modeling stages BASE/ERR/SEL/HPO/EMB/LAMA are closed; latest strong checked
release remains LONG-01, already uploaded by separate human authorization. No
new research loop or submission is implied. Next: final sequential regression
gate, ZIP immutability check, logical commit/push, then completion with this live
comparison explicitly blocked. No handoff package or15%stop policy.

## Final local gate completed

All426unique source checks PASS,exit0,sourceunchanged,214.390s; includes16helpers,
existing14sharedbudget+2real-localHTTPtransport tests. Optional pinned LAMA6,
Torch7,Optuna7 are separate earlier scopes,not added to426. Exact55current long
profile files match the accepted ZIP; no upload or quality promotion. See
FINITE_PLAN_final_gate_20261023.json and FINITE_PLAN_results_20261023.md.
Local implementation/offline checks complete; live equal-budget comparison still
blocked by absent safe current configuration. Helpers remainOFF. Noownedjobs.
