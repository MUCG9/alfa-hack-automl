# Optional pinned AutoGluon procedure: declared before implementation or fits

This is a later independent study, NOT a default runtime backend. Captain asks to
use permitted packages where useful. Installed AutoGluon.tabular1.3.1 imports;
LightAutoML is absent. No package installation or requirements change proposed.
Complete V11 decision and V12 threshold screen before any public AutoGluon fits.
Implementation and API inspection may proceed while frozen earlier archives run.

## One alternative training procedure, fixed before results

Control: same strong calibrated LGBM from v12_threshold_candidates.json, seed42.
Treatment: AutoGluon1.3.1 nonbagged, nonstacked CPU GBM+CAT and its ordinary
weighted ensemble. This is a whole-framework alternative (including learner
weighting/features/selection), NOT a claim that one isolated algorithm caused gain.

Within EACH outer fitting partition, create the existing grouped/time-compatible
inner split73. Only inner train fits AutoGluon feature generation/models; inner
held-out rows are its explicit tuning_data. No automatic IID split, no outer
validation/test labels. Set label_count_threshold1, metric f1_macro, whitelist
GBM1200trees/.04/63leaves/minleaf25/lambda5/feature_fraction.9 and CAT600/depth6/
.07/l2=5,seed42. No added class weights (this differs from mild-weight control).
Disable temperature/decision-threshold auto-calibration. Learn the EXISTING
coordinate class factors on inner held-out selected-model probabilities, then
AutoGluon refit_full(best) on its inner-train+tuning rows. Apply factors to refit
outer-validation/test probabilities. This is an inner-holdout procedure, NOT OOF.
Feature generator remains fitted only on inner train, not on outer validation X.

No bagging in this first study: default pre-bag feature generation and group
contracts need a separate nested audit. AutoGluon's groups argument belongs to
the constructor and implements LeaveOneGroupOut, not a generic fit-time groups
vector. Do not silently substitute IID folds or drop rare classes.

fit time_limit450s, total worker watchdog1200s,1.7GiB tree guard,2CPUs/0GPU,
sequential fit_strategy, no dynamic stacking/HPO/pretrained/model downloads.
Frozen dev extension is copied into the benchmark source snapshot and hashed;
it dispatches ordinary controls to the original compiled worker. It is NOT put
into contest ZIP or production registry until separate qualification.

## Gates

1. Small synthetic full lifecycle, class/channel/ID checks, outer-label poisoning
   invariance, expected dependency version and own-process watchdog. Stop/fix
   actual API errors before public measurement, not by changing quality knobs.
2. Paired legacy feature-group holdouts42/43 with the same inputs. Require BOTH
   outer MacroF1 improve and all fit/refit/export statuses pass; supported-class
   F1 drop<=.01 on each cut (>=100independent fitting groups). Otherwise discard.
   Record complete procedure runtime/memory, inner split hashes, models/refit map,
   calibration provenance, source/input/recipe hashes. No outer weight tuning.
3. Only if positive, same full3fold grouped CV73, exactly_once, all folds/mean/
   pooled improve; supported-class drop<=.01 pooled and gain excluding rarest class
   stays positive. Then a separately designed runtime adapter/new ZIP/full-agent
   comparison under remaining deadline; cannot claim score from import or one cut.

No official upload/paid resources/additional agents. References:
[1.3.1 fit](https://auto.gluon.ai/1.3.1/api/autogluon.tabular.TabularPredictor.fit.html),
[constructor/groups](https://auto.gluon.ai/1.3.1/api/autogluon.tabular.TabularPredictor.html),
[OOF API](https://auto.gluon.ai/1.3.1/api/autogluon.tabular.TabularPredictor.predict_proba_oof.html).
Local pinned source signature/kwargs inspection supplements these primary docs.

Before any fit, code inspection found DefaultLearner concatenates train+tuning
X (and passes concatenated y) to fit_transform_features by default. The study now
explicitly prefits AutoMLPipelineFeatureGenerator on inner-train X ONLY, then
passes that already-fitted object to predictor.fit. Pinned learner.is_fit branch
uses transform-only; no learned preprocessing sees inner held-out rows. Text/
vision generators are disabled. This is contract hardening before outcomes, not
a posthoc quality knob. Trained-model artifact count is not native fit count.

Synthetic check now PASSED: two actual fit/refit/export lifecycles, poisoned outer
labels leave predictions/factors unchanged, probability/class/ID contracts pass,
source and frozen extension unchanged. Evidence v13_autogluon_synthetic.json;
these optional checks are not added to the244core unique-check count. V11 gate
passed and V12 numeric refinement was rejected; public paired framework screen
now starts sequentially. Still no production backend, score or promotion claim.
