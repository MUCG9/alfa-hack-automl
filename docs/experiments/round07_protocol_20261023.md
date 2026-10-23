# ROUND07: fitting-only probability stacker, fixed small residual mixture

Previous whole-ensemble coordinate factors failed cut0 despite an inner gain.
No new multiplier grid on those rows. A different hypothesis is that relative
reliability of the three GLOBAL components is class-dependent and can be learned
from their separate probabilities. No causal explanation of previous failures
is assumed. Existing component models/calibration, features, data and partitions
remain fixed. This is an exploratory complete prediction procedure, not a new
claim about the private test or official score.

Ask real Qwen xhigh once,32768combined/300s call/360s wall, to choose a fixed
implemented meta-learner: LOGIT_STACK_C01(C=.1) or LOGIT_STACK_C1(C=1). No fitting
to select C and no free code/other policy. Both concatenate log(max(p,1e-6)) for
each of the three complete-control global components, in fixed component/class
order, without new raw features. LogisticRegression lbfgs,1200iterations,
tol1e-4,random_state137,fit_intercept=True. Fitting-only sample weights are
inverse square-root meta-fitting class counts, normalized to mean1. All classes
must occur; otherwise no candidate score. No extra calibration or threshold fit.

Meta-fitting rows are solely inner validation after the unchanged COMPLETE
five-leaf control was fitted on disjoint inner training (nested_partition137
inside the saved outer fitting rows). Predict both meta-training and outer
validation using their respective base-model components. Align all component
class/row orders and verify the native CSV argmax. Final probabilities are FIXED
.9*complete_outer_control+.1*meta_outer. These coefficients are declared before
any stacker output; no post-result weight search. The earlier negative class
.9C+.1standalone-TPE blend used a different component and still remains negative.

Reuse ROUND06 cut0's fresh INNER native complete-control artifacts only after
full source/input/actual split/recipe/probability/5-leaf-fitting-lineage checks.
This reuses raw native predictions, not its learned additional factors or
candidate probabilities. No new base-model fit on cut0. Outer complete controls
are unchanged verified PIPE02 originals. Cut1, only if needed, gets one fresh
complete INNER control. Record origin references and physical fits honestly.

Outer gates unchanged: each cut strictly beats complete-control F1
[.6632403174648631,.6553953692580672], supported-class loss<=.01 at>=100
independent outer-training feature groups, gain excluding rarest>0. First failed
cut stops; missing-cut mean=None. No new C/weight after outcomes. If both pass,
predeclare grouped3-fold evaluation of ENTIRE inner-stacking procedure with
exactly-once coverage before considering complete refit/export/release checks.

Sequential owned training lock,2threads,1536MiB coordinator+worker,900s per
complete-control worker,120s per meta-learner subprocess,1800s common screen
including60s verification reserve. Maximum1new complete-inner control worker,
2meta-fitting workers. Original immutable partitions, sources, inputs, plan,
protocol/harness frozen. At most one fitting-phase harness correction, preserve
all attempts and original deadline. Meta-process has no secrets/API access.
Independent artifact-only verifier recomputes softmax from saved coefficient
arrays, class weights/order/actual fitting rows, final mixture/CSV, per-class
metrics and gates; does not rerun fitting. No production/default change and no
further official upload.
