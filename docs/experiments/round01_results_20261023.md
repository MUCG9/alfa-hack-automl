# ROUND-01: marginal objective rejected by the strict gate

Qwen's repaired plan was executed froma2ebf0c. Candidate changes only the inner
objective to RMSE(.9*fresh inner V16 complete+.1trial); outer comparison remains
current PIPE02. Native worker metrics and model recipes were preserved.

|Forward cut|Current PIPE02 RMSE|Marginal TPE mixture|Marginal Random mixture|
|---|---:|---:|---:|
|0|38.82952590212054|38.76140658403198|38.95098030683384|
|1|31.965070385455594|31.965070385455594|31.95675128400607|
|2|Not run|Not run|Not run|

Cut0 improves, cut1 ties. Strict each-cut improvement fails: predeclared futility
stops cut2. No three-cut mean or equal-three-cut-work claim. Four studies/32
successful objectives, including10successful TPE objectives after startup.
PIPE02 remains the best fully qualified solution; no production/default change.

The original coordinator failed only at independent ledger comparison because
in-memory search bounds use tuples while JSON uses lists. Original receipts and
predictions are preserved. One permitted correction normalizes JSON equality;
five no-fit objective/boundary/serialization checks PASS. Independent posthoc
verification recomputed ALL32 native/mixture objectives, selected recipes,
actual labels/row order and outer scores, with NO refits. Corrected verifier has
a distinct hash and does not retroactively replace the failed execution receipt.
See [aggregate evidence](round01_results_20261023.json).

First Qwen proposal conflated comparison and component controls; repaired context
explicitly named both and restored all-cut/Random gates. Two real organizer API
calls, one scientific rejection and one accepted repair; no reliability A/B claim.
Next: [ROUND-02](round02_protocol_20261023.md), residual-grounded typed features
with the original standalone HPO objective, fixed weights and strong control.
