# Predeclared paired study: fixed LightGBM seed averaging

Hypothesis: a second model seed reduces variance of the existing calibrated
LightGBM recipe. Change only the addition of seed47 and fixed50/50 probability
averaging against the same seed42 control. No outer-fitted ensemble weights,
new features, new class weighting, augmentation or altered splits.

Candidate recipes in `v9_lgbm_seed_blend_candidates.json`. Frozen workers V7 SHA
`a31d1fc7c9bee3403f992f70467e95a446c19dbffdb4cdfea9abf2d035f79b27`.
The ordinary ensemble worker supports this fixed composition; no runtime source
implementation/policy change is needed for measurement.

Run seeds42/43, legacy feature-group partitions,2threads,1200s/worker and1.5GiB
tree limit, sequentially after the completed OOF-calibration study. Require all
workers and positive direction on BOTH folds before considering full3fold CV.
Keep/discard must inspect per-class changes and source/split alignment. A positive
component result does not automatically promote another portfolio trial: full
agent selection/refit and runtime cost still need validation. No official score.
