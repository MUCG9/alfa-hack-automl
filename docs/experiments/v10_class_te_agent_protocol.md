# Conditional full-agent categorical feature-view evaluation

Declared while frozen-history4 grouped CV seed73 runs, BEFORE any new integration
or full-agent classification measurement. Run ONLY if all predeclared CV gates
in v10_class_te_protocol.md pass. Otherwise preserve that result; no promotion.

## Scope of one new candidate

Add ONE fixed50/50 two-view LightGBM candidate immediately after the old calibrated
LGBM candidate, only MacroF1 classification, nontext/nonranking, with at least two
schema-declared categorical feature columns. Same strong learner/class weighting/
calibration as frozen screen; second view adds the first three schema-order
categorical columns' pairs plus existing categorical TE, smoothing20. No public
column-name constants, frequency/label-driven context selection or new dependency.
Prior recipes and their relative order remain. Default12trials/9900s deadline,
confirmation slots,shortlist and global cached-blend procedure stay unchanged.
One extra entry displaces a fallback; the new entry trains two views, so trial
counts do not equal equal model-fit counts. Account for all work under shared time.

The candidate must retain per-view fit iterations through confirmation, recursive
median and final full refit. Expose its feature-view structure in records, without
silently dropping a component or treating a two-view recipe as a scalar learner.
If represented as an explicit typed learner flag, reject unsupported engine/kind/
metric, ambiguous pre-existing encoding/augmentation/code combinations and invalid
iteration shapes. Original no-flag paths stay equivalent. A later global ensemble
may contain the two-view candidate; nested iteration/refit/export must be tested.
Fallback may inherit the method and vary ordinary learner params/seed, as existing
search does for incumbents. Global blend can reweight it with other candidates;
the fixed two INTERNAL view weights stay.5/.5. This full-procedure effect is part
of the test, not another fixed-recipe feature ablation.

## Required validation before retention

1. Tests for schema/rename invariance, fitting-only/outer-label isolation, static
   eligibility and previous recipe order, per-view iterations and actual nested
   global-blend full refit. Small meaningful fixtures; no validation-statistic fit.
2. New named source archive, complete unique source gate with unchanged hashes,
   exact-unpacked23tests. Historical history4 and earlier artifacts stay immutable.
3. Repeat exact history4 FULL DEFAULT classification on current pinned environment,
   same public input hashes,offline,2threads,1.7GiB guard,10100s watchdog. Expected
   former V9 mean MacroF1 .653281240,CSV58f52dfbfecb1416a456ed715a43cf944876a7f69eed73d7bf1e10170631b326.
   Verify actual search/confirmation metrics/refit/integrity before comparing.
4. New candidate same settings/default12trial budget. Retain only if BOTH search
   and confirmation MacroF1 improve, all fits/export/integrity succeed. Do not use
   a better mean with one worse cut as a successful gate. Record chosen recipes,
   actual component fits/runtime/RSS and final CSV SHA. No rescue budget expansion.
5. Regression policy is unchanged by intent: exact history4 portfolio parity,
   full default regression lifecycle and CSV parity expected
   05ccd9eabcbf29f4b858e9cd89f6dfe568ce1bdddb32a397c71b98ef1c0c1673,
   RMSE38.902803731/31.991659384. Any change requires investigation, not rounding away.

Existing full-loop baseline first, then one new procedure, all heavy jobs strictly
sequential. If any gate fails, keep evidence and separate new hypotheses. No live
API,unapproved dependencies,official upload,main merge or private-score guarantee.
