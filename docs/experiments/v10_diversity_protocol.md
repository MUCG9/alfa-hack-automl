# Predeclared V10 diversity research

Authorized22October2026 after the feature/data diversity discussion. Base V9
`a95c931`, working branch `work/cpu-research-20261022`. Official best reported by
captain: V9 raw2187.849 (his21.87/100). No further official upload authorized.

## A. Classification: balanced-subset ensemble

Frozen V9 archive SHA
`297647239badde608d349d053a89f9d7f98e8fffceb4a09633f675f99ebd7291`.
Recipes: v10_balanced_candidates.json. SAME three calibrated LGBM models,
model seeds42/47/52, fixed equal probability weights, SAME preprocessing/weights,
iterations and early stopping procedure. Control uses all fitting rows. Candidate
changes ONLY DataPolicy: majority_fraction=.7, sampler seeds101/202/303. Existing
under policy reduces each class with support at least half the largest class,
retains other classes and prefers distinct feature hashes. Original fitting class
counts/weights precede sampling; each inner/outer/full fit applies its policy anew.

First screen: two legacy feature-group holdouts42/43,2threads, sequential,
1200s/ensemble watchdog, local1.5GiB tree guard. Two controls and two candidates,
12component outer fits plus their inner fits. No augmentation/new features/engine
change. Component predictions retained locally for paired diversity diagnostics.
Do not compare one single model with three under-models as a sampling ablation.

Keep only if ensemble Macro F1 improves on BOTH folds, all workers exit0 and
classes/rows align; inspect minority-class precision/recall and joint errors.
If mixed/negative: discard default promotion; preserve exact results. If positive:
predeclare3-fold grouped CV, report fold mean and pooled OOF separately, then test
the complete selection/refit procedure. Full data3-seed blend may itself be worse
than V9's selected model; component contribution is not a promise of final gain.

## B. Regression: strictly earlier context history

New helper is opt-in only, no portfolio/default changes before evidence. Recipes:
v10_history_candidates.json. Frozen metadata hierarchy/log LGBM control vs SAME
recipe with history_asof=true. Context groups still inferred from fitting X/schema.
For each fitting context and observed period compute mean target. For query t add
latest mean at period<t and trend between the latest TWO earlier period means,
divided by period distance. Same-period targets, outer labels and test labels are
never used. Missing history/trend yields NaN, no future-derived global fallback.
The new flag requires numeric observation periods and regression context encoding.

Predeclare three forward cuts: offsets0/1/2 (public periods5/4/3). Each candidate
repeats its fitting-only transformations inside inner stopping and final fit.
Same model/capacity/log/contexts/smoothing, only this feature block changes. No
public feature names or hand-written public entity keys in runtime source.

Keep gate: lower RMSE on BOTH original cuts AND the additional older cut, no
causality/held-out perturbation failures, exit0 and valid export. Otherwise inspect
whether context support or cold-start history explains the result; any alternative
must have a newly recorded hypothesis, never silently retune on the same results.
Successful component must still improve a full-agent comparison before promotion.

## C. Error complementarity tools

Add development analysis of common held-out predictions: both wrong, candidate
correct given control wrong, classwise corrections; regression residual correlation;
fixed0.5 blend evaluated without tuning. Optional component expansion. Keep rows,
classes,input/source/split hashes aligned. Correlation is diagnostic, not a selection
objective. No pooled OOF claim for overlapping holdouts; no oracle F1 guarantee.

## Reproducibility / stopping

Original requirements SHA unchanged; no new dependencies/pretrained models/API
calls required. Public inputs must match docs/handoff/public_inputs.json. Source
snapshot per run is immutable. Heavy ML runs sequentially on the low-memory PC;
unit tests stay small. Every completed logical stage gets a commit, evidence and
updated handoff. At the captain's10–15percent remaining usage window stop new long
work, checkpoint and hand off; do not fabricate a live usage counter.

Public folds have been repeatedly inspected; none of these scores is an unbiased
private/platform estimate. No official submit or main merge in this protocol.

## Implementation checkpoint

Opt-in history_asof helper and worker/recipe registration implemented. No default
portfolio change.17new checks (13pure-history +4worker/normalization/export) pass,
including strict past/same-period exclusion, held-out target invariance, unseen
contexts, nonuniform periods, overflow and full refit. Existing18quality +7architecture
checks also pass in the pinned Python3.12.3 CPU environment. First classification
full-data control fold completed; no sampling result or history quality decision yet.
