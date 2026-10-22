# Balanced-subset result and predeclared CV confirmation

All4paired workers exited0, frozen V9 source/input/split hashes match.

|Legacy holdout seed|Three full-data models|Three under70 models|Delta|
|---|---:|---:|---:|
|42|.645027031|.655688478|+.010661447|
|43|.648629834|.648710441|+.000080607|
|Mean|.646828432|.652199459|+.005371027|

The exact same single calibrated LGBM seed42 component has mean.651543688
(.650292961/.652794416). Candidate gains only+.000655771 against that stronger
single control, and loses its second holdout. This is promising against the
matched3-model sampling control, not evidence to replace V9's final selected model.

## CV declared before running

Same frozen V9 worker archive, same v10_balanced_candidates.json and equal weights.
Run complete3fold StratifiedGroupKFold on exact feature hashes, seed42, every row
exactly once,2threads, sequential,1200s/ensemble and local1.5GiB process-tree guard.
No retuning model/sampler seeds/fractions/weights after reading paired outcomes.

Primary comparison remains under vs matched3-model full-data control. Also compare
with its exact single seed42 component using existing component predictions.
Report each fold, fold mean and pooled OOF separately, minority precision/recall,
joint errors and fixed0.5 component blends as diagnostics only. Default promotion
requires robust gains over the stronger single control in mean AND pooled OOF;
a mere improvement over a weak3-seed baseline is insufficient. Any new blend or
data-policy alternative needs its own predeclared experiment and external check.

Run after regression forward screen, never simultaneously with another heavy fit.
If the result is mixed/negative, do not promote. A positive fixed recipe would
still require complete agent selection/refit/runtime validation and a new release.

Evidence: v10_balanced_results.json and v10_balanced_diversity.json. Public folds
are reused; no official/private-score or uncertainty guarantee is claimed.
