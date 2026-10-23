# REASONING02: xhigh3/3, off1/3 on fixed paired decisions

Six actual organizer Qwen responses, identical caller messages within each pair,
same32768combined token and300s call caps, fixed alternating order. No repairs,
missing responses, truncations or transport retries; one HTTP each. Context,
protocol, prompt and gateway remained frozen. Independent recomputation PASS.

|Profile|Valid JSON|Valid schema|Correct structured decision|Reported thinking tokens|Total call seconds|
|---|---:|---:|---:|---:|---:|
|Explicit off|3/3|2/3|1/3|0|5.875|
|xhigh|3/3|3/3|3/3|9509|179.003|

Both reject the marginal-HPO tie correctly. Off wrongly marks the completed
PIPE02 qualification mean unavailable despite both required cuts being present;
its class-CV audit returns an empty object. Xhigh answers all declared structured
decisions correctly, including the class blend's failed fold despite a positive
public replay. Final one-sentence reasons inspected: no unsupported causal or
official-score assertion. See [independent receipts](reasoning02_results_20261023.json).

This supports keeping explicit xhigh for active research planning. Three fixed
tasks/one sample each do not establish general model superiority, significance
or an ML metric gain. Latencies are observed, not a stable speed estimate. Caller
messages were identical; server-reported prompt tokens differ between profiles
(1649off/1757xhigh), so no claim of equal provider-internal tokenization. Effective
server effort is not echoed. Thinking text was neither printed nor saved.

Canonical request includes enabled:true,effort:xhigh,exclude:true; active
research budgets remain32768combined/300s call/360s wall. Uploaded qualified
submission ZIP remains unchanged. A subsequent real xhigh-selected class rule
still failed its ML gate (ROUND06): better audit answers do not assure better
predictions.
