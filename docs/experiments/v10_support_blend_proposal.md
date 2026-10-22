# Next conditional ensemble hypothesis: fixed train-support shrinkage

This is a PROPOSAL, no scores from this method have been observed and no fits are
started here. Complete categorical-pair TE and its gate first. If that method
passes its screen, prioritize its predeclared CV; otherwise this low-fit-cost
experiment can reuse frozen LGBM/ExtraTrees predictions after a separate protocol
commit and implementation tests. No default or official submission change.

Observation motivating a NEW hypothesis: fixed50/50 LGBM+XT improved accuracy and
log loss both folds, but first-fold Worms F1 dropped.078431. Macro gains excluding
that class are positive both folds. This was discovered on reused public labels;
any follow-up remains exploratory and needs fresh predeclared grouped CV.

Proposed fixed algorithm, not an outer-label weight search:
for each class k count n_k distinct ORIGINAL fitting feature hashes carrying that
class, before any resampling. Let alpha_k=.5*n_k/(n_k+100). Combine class scores
(1-alpha_k)*p_LGBM(k)+alpha_k*p_XT(k), then normalize each row. Prior100 and maximum
XT contribution.5 are fixed BEFORE this method's scores. Missing fitting class
has alpha0. No sweeps/optimizers/per-class validation-derived exceptions. LGBM is
the declared reference; shrink the less established branch at low fitting support.
Hypothesis can fail: support is not the same as relative model quality, and some
rare classes may benefit from XT. Row normalization can also change log loss.

Screen uses original two frozen control/XT component probability artifacts, same
history4 source/input/harness/split hashes, validation labels for evaluation only.
Verify fitting-only support invariance, exact duplicate-group collapse, class
order and normalized finite probabilities. Report corrections/breaks/per-class F1.
Keep for CV only if MacroF1 improves BOTH42/43folds; no post-result prior tuning.

If positive: freeze same two leaf recipes, complete3fold grouped CV seed91,
exactly-once OOF. Alpha is recomputed on each fold's FITTING labels/groups.
Require all fold deltas, mean and pooled positive; gain excluding the class with
smallest minimum fitting-group support positive; no pooled F1 loss >.01 for classes
with >=100fitting groups in every fold. No OOF-based choice of prior/weights.
Then separately design and test full-agent selection/final-fit integration;
current scalar-weight ensemble/shortlist cannot be assumed to support classwise
weights. Preserve original fixed50/50 failure and no claims of independent/private
score. Existing calibrated leaf predictions are reused, not newly re-fitted models.
