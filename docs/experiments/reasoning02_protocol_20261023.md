# REASONING02: small paired audit, equal output and time caps

REASONING01 established accepted xhigh and actual thinking, with different token
caps. It did not establish reasoning quality. This dev-only follow-up compares
explicit off and xhigh on three fixed experiment-audit contexts from measured
research history: marginal-HPO tie/futility, qualified PIPE02 regression gains,
and the class blend's negative grouped CV despite positive public holdouts.

Freeze the case fixture, prompt, gateway and evaluator before requests. Both
profiles receive byte-identical messages for each case, temperature.4,
32768combined output tokens and300s call cap. Case order fixed; profile order
alternates off/xhigh,xhigh/off,off/xhigh. Six logical calls maximum, one shared
1800s wall deadline. Canonical transport permits at most3HTTP tries per logical
call; actual tries and incomplete usage must be reported. No proposal repair,
resampling, selecting best response, hidden thinking logs or post-result prompt
edits. Unavailable/truncated/invalid responses count as failure, not exclusions.

Primary descriptive outcome is exact structured decision correctness, including
control/component identity, promotion/completeness, fact-ID namespace, allowed
next operators and no cache-to-quality or pending-score claims. Expected answers
come from existing independently verified gates/receipts, not a second LLM.
Record JSON/schema validity separately from scientific correctness; reasoning
tokens, total reported tokens, wall time and actual HTTP attempts separately.

Only3paired tasks/one sample each: no significance or general model-quality
claim, no causal account of downstream ML gains. No model fitting, default or
qualified-release change, official upload, external data or new dependency.
This is an agent decision audit, not a new ML validation partition. Keep the
active ML worker sequential and its frozen source/harness untouched.
