# ROUND-02: residual-grounded Qwen features rejected

Qwen proposed3 typed features: cooling/heating degree-day ratio, July maximum
minus January minimum temperature, and clipped area-times-wind interaction.
These hypotheses form one exploratory bundle; no individual causal/gain claim.

Cut0 complete mixture RMSE38.90056134949635 loses to current
PIPE0238.82952590212054. Strict all-cut gate therefore stops cuts1/2; no full mean.
Eight successful standalone-inner TPE objectives, five after startup;9workers,
87.714s, observed maximum worker+parent665.3MiB. Actual source/input/harness/
plan fingerprints unchanged. Every inner objective/selection, ordered source
labels, historical reference and outer mixture independently verified. No code
fix/refit was needed, no release/official score changed.

[Aggregate evidence](round02_results_20261023.json). Candidate source25f9020;
rollback tag qwen-round02-features-start-20261023. Installed Karpathy-based skill
now records separate comparison/component control identities and ROUND-01's
limited negative result; five files synchronized and quick validation PASS.

Next round investigates exact-context execution reuse in the agent harness,
motivated by duplicate proposals observed in HAR-01. It measures cost and output
parity separately from ML quality, preserving PIPE02 as qualified control.
