# ROUND-05: worst-period marginal HPO loses the first outer cut

Fresh organizer Qwen planning used explicit xhigh with32768combined tokens.
First plan112.082s/12253reasoning tokens was rejected for fact/context namespace
confusion and a repeated failed mean suggestion. One bounded repair94.911s/
10169reasoning tokens retained the correct controls/gates and passed audit.
Internal reasoning text is not saved; this is not a quality A/B against off.

The new fixed operator maximizes over inner-period mixture RMSEs, then TPE
minimizes that worst-fold objective. Two inner periods, fresh V16 controls,
unchanged recipes/space/weights/seed137/startup3,8trials per sampler.

Cut0 complete mixture TPE38.85602938037247 loses to current PIPE02
38.82952590212054; Random38.95098030683384. Stop by predeclared futility,
cuts1/2 absent and mean=None. Sixteen aggregate objectives/32native requests,
6cache hits/26new native trial fits +2inner controls +2outer fits =30workers.
All objectives/rows/labels/selection/lineage/outer gates independently verified;
actual source/input/harness/plan unchanged. The old cache was deliberately not
seeded after gateway source changed, preserving the conservative identity rule.

[Aggregate evidence](round05_results_20261023.json). No model/official promotion.
PIPE02 remains qualified; the submitted archive remains queued unchanged.
Next distinct direction: constrained joint decision calibration after the full
classification ensemble, distinguishing it from existing per-component tuning.
