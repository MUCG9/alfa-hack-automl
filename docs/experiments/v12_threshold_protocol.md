# Proposed bounded threshold-search experiment (not implemented or run yet)

Declared BEFORE any new optimizer implementation/outer result. This is a later
isolated stage, not part of V11 feature-view attribution. Run only after the V11
full-procedure gate has completed and the source/default decision is checkpointed.

The supplied unconstrained raw-weight Nelder–Mead is not accepted verbatim.
Positive weights are essential. A tiny simplex on flat argmax F1 can terminate
without changing predictions; existing coordinate calibration already improves
over raw argmax and already isolates outer validation labels.

## One changed factor

Control: strong calibrated LGBM with existing inner-holdout coordinate factors,
same seed42/rows/weights/preprocessing/stopping as prior fixed controls.
Candidate: SAME inner training/heldout probabilities and iteration matching,
warm-start current factors, bounded log-space Nelder–Mead refinement. Same
objective macro F1 minus.004mean(log(weights)^2), same [.4,2.5] factor bounds.
Explicit simplex step.15 in log space, max400function evaluations and400iterations.
Keep warm-start if optimizer is invalid/nonfinite or its INNER objective does not
strictly improve. This is optimizer search only, not probability calibration or
OOF3 repetition, no changed class weighting/feature views or data policy.

The optimizer API must validate probability/class/label alignment, positive finite
normalization, known labels and factor dimensions. No fitting on outer OOF scores
then reporting the same rows as an unbiased tuned score. No posthoc broadening
of bounds or budget after results. Cross-fitted probability generation, if used
in later work, must remain entirely inside the current outer fitting partition.

## Gates

1. Meaningful probability/class-order/bounds/fallback/outer-label isolation tests;
   source hash / recipes / input / split fingerprints / resource caps recorded.
2. Paired group-holdouts42/43,2threads,1.7GiB guard,1200s worker watchdog. Keep
   for grouped CV73 only if BOTH outer MacroF1 improve, all fits/refits succeed,
   and no supported class (>=100independent fitting feature groups on each cut)
   loses more than.01 pooled class F1. Overlapping holdouts are not pooled OOF.
3. If positive, full3fold grouped CV73 exactly_once, all folds/mean/pooled improve;
   supported-class noninferiority checked separately on true pooled OOF. Gain
   excluding the least-supported class must remain positive (unchanged rows).
4. Only then a new full-agent candidate/default and exact archive/full lifecycle,
   compared against the checkpoint immediately before this treatment. The model
   optimizer may overfit a small inner holdout; negative result means discard,
   not tune on outer labels. Never predict .75F1 or75–85 official points from it.

No new dependencies; scipy1.12 already allowed/installed. Official upload needs
separate authorization. API budget is unrelated to this local numeric optimizer.
