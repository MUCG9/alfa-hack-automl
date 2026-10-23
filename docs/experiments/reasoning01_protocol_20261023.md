# REASONING-01: verify the requested maximum Qwen effort

Captain asks to check whether Qwen reasoning is default and should be ultra.
Actual canonical gateway explicitly sends reasoning.enabled=false, motivated by
earlier reasoning-only truncation. This is NOT provider default. Organizer
models endpoint exposes qwen/qwen3.8-27b but no per-model effort metadata.

Official Alibaba Chat Completions documentation, checked23Oct2026, specifies
qwen3.8-27b levels low/medium/xhigh; maximum/default is xhigh, high/max map to
xhigh, ultra is not listed. OpenRouter documents reasoning.effort=xhigh and
reasoning.exclude=true; reasoning and final output share max_tokens.
Sources: https://www.alibabacloud.com/help/en/model-studio/qwen-api-via-openai-chat-completions
and https://openrouter.ai/docs/guides/best-practices/reasoning-tokens .

Probe the ACTUAL authorized organizer endpoint/model. Same fixed JSON gate-audit
task from ROUND01/04; first current explicit-off profile, then xhigh with reasoning
enabled and excluded from response. Off<=2048output/60s; xhigh<=32768combined
output/300s. At most one HTTP attempt per call; no automatic retry/downgrade.
Only if nested xhigh is explicitly rejected400, one additional standard top-level
reasoning_effort=xhigh probe may run with its own receipt,300s; total<=660s.
These different caps verify configuration, NOT a controlled quality/latency A/B.

Save requested parameters, status, final JSON, finish reason, token usage and
reasoning-token count only. NEVER persist/print internal reasoning_content,
reasoning_details or full raw model response. Check JSON presence, facts and
truncation. Acceptance of an effort parameter alone does not prove effective
server level; nonzero reported reasoning tokens proves thinking occurred.
Do not claim an ML gain. Qualified uploaded ZIP remains immutable. Before new
ML fits, decide from measured compatibility/latency whether to enable explicit
xhigh for subsequent Qwen research and reserve sufficient output/time budget.
Any source/config change is a separate local commit and does not replace the
already accepted official submit. Existing pending ROUND05 stays deferred while
this new user steering is investigated; preserve all its drafted evidence.
