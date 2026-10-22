# Predeclared classification feature-view experiment, not a weight rescue

Declared after the first ExtraTrees blend fold lost its fixed gate; remaining
ExtraTrees fold must finish before this starts. No TE classification metrics have
been observed. Existing helper supports multiclass encodings, but the completed
classification studies did not test them. No new runtime source/library/default.

## Fixed factor and primary endpoint

Control is exact strong calibrated LGBM seed42 from the completed two control
folds of v10-extratrees-paired, immutable history4 source SHAa42fcb1557ec0cf2455abb3add9d6968a8388aedcfcf8d554b26ed73a45788f8.
Candidate branch uses SAME learner/capacity/seed/weights/calibration/source rows,
plus existing target_encode_frames categorical class statistics and pair contexts.
Select the first THREE declared categorical feature columns in spec feature order,
no target/frequency/validation-based selection; enumerate their pairs, at most3.
Names in candidate JSON come from schema, never public-name runtime literals.
Smoothing20, no counts/recency/history/augmentation/generic feature-code changes.
Helper adds categorical singles too, so the treatment is this whole extra feature
block. Feature subsampling remains.9; adding columns changes the realized masks.

Each fitting row receives3fold GroupKFold cross-fitted statistics excluding its
entire feature-hash group. Validation/test encode using current fitting labels
only; every inner stopping/calibration fit rebuilds the encodings on its rows.
Original categorical features remain. Test multiclass own-group/outer-label
isolation, unseen-context priors/class channel order and actual worker invariance
before fitting. No target encoder fitted once before the inner split.

Primary endpoint: fixed50/50 probability average of the frozen strong control
and this TE branch, computed from aligned predictions using analyze_diversity.py.
Weights are never searched. TE branch standalone metrics are diagnostic, not an
alternate promotion path selected after outcomes. This tests feature diversity,
not a different ExtraTrees mixture weight. Respect same class order and normalization.

## Sequential screen and provenance

Two legacy feature-group holdouts42/43,2threads,1200s/worker,1.7GiB guard. Train
ONLY the new leaf; original standalone controls already completed with the exact
same source/input/split/harness hashes. Copy artifacts to a new derived analysis
directory with every file SHA preserved; retain both parent manifest SHA and the
new derived manifest lineage. No original result/partial file is overwritten.
Scores are comparable fixed recipes, not a runtime speed comparison. No pooling
of overlapping holdouts. Keep for CV only if fixed blend improves BOTH folds.
Otherwise preserve negative/mixed result with diagnostics and no default change.

If positive, run SAME fixed control and leaf complete3fold grouped CV seed73,
every row exactly once; compute the same fixed blend, no parameter/weight tuning.
Require all fold deltas, fold mean and pooled positive. For classes with >=100
independent fitting feature groups in every fold, pooled per-class F1 may not drop
more than.01. Excluding the class with minimum fitting-group support must leave
positive pooled macro gain (ties in stored class order). Then separately evaluate
full-agent selection/refit/export/runtime before any portfolio promotion.

## Limits and interpretation

Raw model artifacts/predictions stay local ignored. New schema/metrics do not
change organizer requirements. No live API/official submit. All public folds
have been inspected repeatedly; no unbiased/private or official-points estimate.
Encoding prior/fold noise can hurt despite being leakage-safe. A negative result
is not repaired by reducing smoothing or learning blend weights on outer labels;
those would be new separately declared hypotheses.
