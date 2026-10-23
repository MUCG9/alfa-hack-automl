# ROUND-04: extra inner period does not change the measured selections

Qwen chose FORWARD_MEAN: average the fixed mixture RMSE over the latest two
usable fitting-only periods. Component V16 was freshly refit per inner prefix;
current PIPE02 remained the outer comparison. All tested cuts had2inner periods.

|Outer cut|PIPE02 RMSE|Candidate TPE|Candidate Random|
|---|---:|---:|---:|
|0|38.82952590212054|38.76140658403198|38.95098030683384|
|1|31.965070385455594|31.965070385455594|31.95675128400607|

Cut1 ties, so strict gate rejects and cut2 is absent, mean=None. Selected recipes
and all trial recipes on these cuts match ROUND01. Adding this inner-period
aggregate did not change the measured decisions; no general causal conclusion.

478.86s,32successful aggregate objectives/64native fold requests,20exact-context
cache hits,44actual native trial fits +4inner controls +4outer fits =52workers.
Independent verification covers ALL per-fold native/mixed scores, aggregates,
selected recipes, cache keys/artifact/origin lineage, counts and outer scores.
Source/input/harness/plan unchanged; no corrective refit needed. Absolute row
positions are bound by saved NPZ/cache hashes; embedded canonical inner split
info retains its local-subset hash scope, explicitly recorded in aggregate JSON.

Qwen's variance-causality clause was unsupported and rejected as a fact; only the
fixed operator/hypothesis was accepted. [Evidence](round04_results_20261023.json).
Qwen predeclared FORWARD_WORST as next_if_rejected. The next plan evaluates this
distinct operator and seeds only independently verified native cache artifacts.
PIPE02 remains the qualified model; no new official-score/model-gain claim.
