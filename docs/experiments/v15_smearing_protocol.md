# Bounded fitting-holdout log-target retransformation study

Declared BEFORE implementation/any smearing measurements. Supplied LLM proposes
forcing log1p for skewed targets; existing portfolio already compares log/nonlog.
New hypothesis instead addresses retransformation bias under original-scale RMSE.
Inspired by [Duan1983](https://doi.org/10.1080/01621459.1983.10478017) and
[forecasting transformation bias](https://arxiv.org/abs/2208.12264). The former
estimates expected responses via an empirical residual distribution; this bounded
boosting/holdout adaptation is OUR experiment, not a guarantee from that theorem.
Heteroscedasticity/time drift/model mismatch may make a global factor harmful.

## Frozen one-factor method

Control: history4's exact semantic/log/asof-min3 LightGBM recipe (same as second
v10_history_support_candidates recipe). Candidate differs ONLY by explicit
target_smearing=true. No new portfolio/default/trial/weight/features change yet.

At matching selected iterations, get current INNER-training model predictions
on its inner held-out rows. Estimate s=mean(exp(log1p(y)-prediction_log)).
Require>=20calibration rows, finite numeric nonnegative targets and predictions;
bound factor [.8,1.25]. Nonfinite exponential moments preserve factor1 with a
diagnostic, never infer a zero cost/success. Final inverse is expm1(pred_log+log(s)).
If factor1, use the exact old np.expm1 path. No normal-error assumption or test
labels. Full refit learns its factor from a fresh training-only inner split using
the selected fixed iterations, then trains on all fitting rows as before.

For history_asof, apply ONLY when the actual calibration model's fitting-history
block is enabled (>=history_min_periods and supported contexts). Otherwise factor1
and exact control parity are required. This avoids calibrating an unavailable
history procedure and then correcting a different outer model. At public forward
cuts5/4/3, only cut5 is expected eligible (inner fitting periods1..3); older cuts
should remain exact control when history gate disables inner history. Eligibility
is structural/train-only, not chosen from RMSE. Nonhistory log-regression can use
the generic method, but this study does not qualify those tasks.

Support native trees, regression RMSE/MSE, log_target=true and noop data policy;
reject text/ranking/classification, malformed flags, unsupported metrics or mixed
data policies. Default off. All preprocessing/stopping/calibration remain fitting-
partition-local. No runtime dependency added (NumPy already allowed).

## Predeclared gates

1. Meaningful math/bounds/invalid moments/type/eligibility, matching iterations,
   outer-label poisoning, full refit, and insufficient-history exact-parity tests.
   Full unchanged-source unique suite/new named ZIP/exact-unpacked checks.
2. Same three forward cuts0/1/2,2threads,1.7GiB guard,1200s/worker, sequential after
   current AutoGluon study. Control must reproduce prior history4 fixed-recipe
   predictions. Require eligible cut5 STRICTLY lower RMSE; older cuts no worse,
   and BOTH validation and test CSV byte parity wherever factor is structurally
   disabled. All workers/refits/export pass; no resizing bounds after results.
3. Only if positive, append ONE qualified smear candidate immediately after asof
   in the existing time/numeric/static regression portfolio, preserving old recipes
   and relative order/default12trials. Then exact full-agent regression compare
   against frozen V11/history4. Require search RMSE STRICTLY improve and
   confirmation RMSE NOT worsen, with strictly better mean and all refit/integrity/
   export checks; classification policy and full CSV parity required.
   A component gain alone is not a full-procedure gain. If mixed, retain evidence
   and off-by-default method, not a posthoc rescue.

V11 remains the qualified release. No official upload/newdependencies/paidresources/
extraagents. Public validation reused, no private or official-points prediction.

Full-procedure gate clarified BEFORE ANY public smearing fits: the train-only
support rule deliberately disables correction on the confirmation cut, so demanding
a strict improvement there would reject an exactly invariant safe path by design.
Noninferiority is NOT permission for a better mean with any worse cut. Component
CSV parity where disabled remains mandatory. No quality outcome has been observed
for this method at this clarification; six pure math/contract checks passed only.
