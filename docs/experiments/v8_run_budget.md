# V8: shared run deadline, gateway ledger, bounded semantic metadata

Separate runtime-correctness stage after frozen V7; no training/selection policy
change is intended. It is not evidence of improved ML metrics.

## Implemented and targeted checks

- Start one coordinator deadline BEFORE file discovery/loading. Semantic calls,
  single-target search and all independent targets share it. Local worker and
  child-target deadlines can only shorten that deadline, not renew it.
- New `--max-llm-calls` controls total gateway invocations across file roles and
  planner/targets (0..16). Default is bounded planner limit+2 file-role calls.
  Existing `--max-planner-calls` is still planner-specific. HTTP retries remain
  inside each gateway deadline, and are reported separately from logical calls.
- `automl_runs/run-budget-*/report.json` is one cumulative shared ledger. Child
  snapshots reference the SAME ledger and must not be summed. It records only
  whitelisted status/count/usage metadata, not prompts, errors, credentials or rows.
  Reported token totals are not a currency/balance estimate; unknown retry usage
  remains explicitly incomplete. An unreported reserved call cannot look complete.
- The final ledger records completed/failed/interrupted. Per-model reports have
  snapshots taken at publication; the referenced final ledger is authoritative.
- File-role metadata is bounded to65,536 UTF-8 bytes, including feedback on each
  retry. Oversized names/headers fail before sending the request, without silent
  path truncation. Count/row bounds and no-raw-row behavior remain in place.
- Library/offline defaults and canonical-name no-call behavior are unchanged.

12 budget tests pass (mock transport/clock),10 semantic tests pass (including2new
metadata bounds),7architecture and7resilience checks pass. Full161-unique suite is
running with source hashes before/after. Exact ZIP/full public gates still needed.

## HTTP fixture versus live provider

`tools/live_smoke.py` can exercise an authorized private process environment or
hidden terminal input; it never accepts a key in argv. It restricts destination to
the organizer endpoint or loopback. Loopback accepts ONLY a fixed dummy credential.
It uses opaque file names, reversed sample IDs,7model experiments, one planner
call and actual refit/export on180artificial rows.

Two tests passed using a LOCAL FAKE HTTP server and the real installed OpenAI
client: mapping→planner→model→CSV, correct key routing, final shared ledger with
two calls and reported token counts. They explicitly label `local_mock_http` and
`semantic_live_ok=false`/`planner_live_ok=false`. This is SDK/HTTP plumbing evidence,
NOT a successful live Qwen request and NOT public/private ML quality evidence.

A new hidden-input attempt in this resumed turn was policy-denied before the key
entered the process. The waiting terminal has no key; no live request/spend is
inferred. Do not bypass the denial. A separately authorized private environment
is still needed for organizer-API validation. No keys were added to source/Git.
