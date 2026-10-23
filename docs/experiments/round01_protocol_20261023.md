# ROUND-01: grounded Qwen planning and marginal HPO

New captain request reopens continuing research. Start from qualified PIPE-02:
complete-agent F1 .6593178433614652 and RMSE35.39729814378806. The pending
submission ZIP a2ca924416be9b1fc9c528b431f22123b42324b44e50402601e828c4f15056f2
remains immutable. This round changes dev tools only, not production defaults.

First ask organizer Qwen for one falsifiable operation from MARGINAL_HPO,
RESIDUAL_DSL or GROUNDED_LEDGER. Tool-generated context fixes control, metric
direction, signed gain, negative evidence, capabilities and budgets. One logical
call, at most3 HTTP attempts,180s total,2048 output tokens. Raw responses stay
ignored. Validate schema/IDs and manually audit scientific premises before any
execution; valid JSON is not evidence of truth. One further logical proposal is
allowed only after a recorded failure, with its own receipt; no endless retry.

Preferred falsifiable mechanism: rank augmentation trials by the fixed mixture
RMSE rather than standalone RMSE. Complete V16 control has weight.9, trial
augmentation.1, unchanged. Fit a NEW complete control solely on each INNER
training partition, predicting its inner validation. Outer-trained predictions
cannot enter this objective. Keep identical recipes, search space, seeds,
frozen outer partitions and evaluation. Native trial metric remains separate
and unchanged in worker result.json; ledger objective is explicitly mixture RMSE.

Control for advancement is CURRENT PIPE-02 on3 forward cuts:
38.82952590212054,31.965070385455594,50.89527201436724. Reuse only independently
verified actual saved predictions with matching input/worker-source/split hashes;
do not reconstruct historical partitions or call single learners complete agents.

For marginal HPO, Random8 and TPE8 each include unchanged anchor, seed137,
startup3, fixed existing LGBM search space. Two threads,1536MiB total owned
worker tree,600s/worker,1800s/study,5400s overall screen including verification.
Use exclusive global training lock; fits and suites sequential. Eight successful
objectives per study required for a complete equal-cap comparison. Preserve
failures/duplicates with absent values. A positive screen requires all3 forward
TPE mixture RMSEs strictly improve CURRENT PIPE-02 and mean beat new-objective
Random8. Predeclared futility: stop after the first failed mandatory TPE cut;
status rejected/incomplete, no fictitious three-cut mean or equal-work claim.

Independently recompute every native and mixture objective from actual source
labels and ordered predictions; verify inner partitions are subsets of outer
fitting rows, disjointness/chronology and selected-best trial. Save source/input/
task/split/harness fingerprints, actual counts, elapsed time and guards. Protect
canonical evaluator/data/splits; hypothesis wrappers cannot edit worker metrics.
Commit tools/protocol before fits. Maximum one local harness correction then
preserve failed attempt and start a distinct round instead of silent restarting.

If Qwen selects another registered operation, first write its concrete matched
measurement protocol before execution. A positive screen requires subsequent
complete adaptive-procedure qualification, refit/CSV/integrity and release gates.
No automatic promotion from a component result. A rejected screen triggers a
new considered plan/Qwen feedback under the captain's continuing authorization.
No hidden/private/official performance inferred from reused public partitions.
