# Next research stage: proposal, NOT STARTED at V10 checkpoint

The captain reported8% usage-window remaining and asked to finish/checkpoint.
Do not start this screen during handoff. Resume only after the next agent checks
current release gates and active jobs. No official upload is authorized here.

## Classification: structurally different errors with existing ExtraTrees

Use approved sklearn1.5.2/current ExtraTrees adapter; no new dependency, pretrained
weights or domain-specific feature names. Existing LGBM seed averaging and under70
were mixed/negative. Under70 pooled disagreement5.36% corrected1635 single-model
errors but broke2223 correct predictions; diversity alone is not a keep criterion.

Before any fit, freeze a new protocol and candidate JSON. Proposed matched screen:
exact strong calibrated LGBM seed42/noop control; candidate fixed50/50 probability
blend of that SAME LGBM and one ExtraTrees branch. XT proposed300trees/depth24/
min_leaf2/max_features.7/seed42/class_weight_power.5/calibrate=True. No seed/fraction/
weight sweep after metrics. Standalone XT and conditional correction/break counts
are diagnostics. Frequency encoding and median imputation are already part of XT's
existing adapter path, both fit-only; this tests the whole branch, not thresholds
in isolation. Inner calibration must also use only its own fitting partition.

Paired feature-group holdouts42/43,2threads,1.7GiB local guard,1200s/worker,
sequential. Keep for confirmation only if the fixed blend beats the strong single
on BOTH folds. Otherwise preserve the negative result without rescue tuning.
If positive, predeclare complete3fold grouped CV seed73, every row exactly once,
respect duplicate/declared groups. Require positive direction on all folds plus
fold mean and pooled Macro F1; inspect per-class P/R, confusion, log loss and
whether gain survives excluding the rarest class. Any per-class safety threshold
must be fixed before fitting, based on fitting-group support, not public labels.
Then separately validate the full agent selection/refit/export/runtime before
portfolio promotion. A new family can still share existing mistakes or lose
category information through frequency collisions. No private-score guarantee.

## Alternatives after evidence

- Selection audit: family representatives vs existing shortlist, same outer folds
  and confirmation slots. Cached replay is diagnostic, not independent evaluation.
- Bounded train-only HPO using approved Optuna4.2.1 vs matched deterministic search;
  account for short12trial defaults and reserve confirmation/refit time. This is
  a separate procedure comparison, not a silent budget increase for history.
- Context-specific history support: global3period gate does not guarantee every
  context has two earlier observations. New support variants require a fresh
  hypothesis and frozen comparison; do not retune the completed V10 screen.

Read v10_agent_history_protocol.md and v10_progress.md first. All public folds
have been repeatedly inspected; local scores are not official/private estimates.
