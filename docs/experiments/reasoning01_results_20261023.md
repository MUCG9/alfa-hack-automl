# REASONING-01: explicit off found; xhigh verified and enabled for dev research

Canonical gateway had explicitly disabled thinking, rather than leaving provider
defaults. Historical reason: reasoning consumed entire output limits and yielded
empty JSON. [Original evidence](../v2_validation.md).

Official [Qwen Chat API](https://www.alibabacloud.com/help/en/model-studio/qwen-api-via-openai-chat-completions)
lists xhigh as maximum/default for qwen3.8-27b; ultra is not a supported Qwen level.
[Transport guidance](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)
explains that reasoning and final output share max_tokens. Organizer model
metadata confirms the configured ID but does not expose supported effort levels.

Real organizer endpoint, same fixed experimental-gate audit task:

|Requested profile|Combined token cap|Reported reasoning tokens|Seconds|Final JSON/facts|
|---|---:|---:|---:|---|
|Explicit off|2048|0|1.491|PASS|
|xhigh + enabled + exclude|32768|1014|14.716|PASS|

One HTTP attempt each, stop finish, no truncation, no compatibility fallback.
This verifies accepted configuration and actual thinking, not a quality/latency
A/B because caps differ, nor an ML gain. Effective server effort is not echoed.
Internal reasoning text was neither printed nor saved. [Receipts](reasoning01_results_20261023.json).

Active dev planners now configure xhigh,32768combined output tokens,300s call,
360s wall. Gateway adds explicit opt-in AUTOML_REASONING_EFFORT and per-call
metadata; HTTP400 cannot silently drop a requested effort. Ordinary unconfigured
runtime retains its measured off behavior. The already uploaded qualified ZIP
is immutable; no replacement upload is authorized by this check.

Four actual-local-HTTP/configuration checks,14shared-deadline/call-budget checks,
and2SDK/CLI checks (including a local mock fit/export) PASS. This is a focused
20-check gate; the previous352-source gate belongs to its historical source.
New LLM policy is independent of model training; no new public-dataset fitting or
full release qualification is part of REASONING01. Subsequent real xhigh plans
and fitting results are recorded separately in ROUND05/06. The equal-cap paired
agent audit is [REASONING02](reasoning02_results_20261023.md).
