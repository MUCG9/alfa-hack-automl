# LAMA-01 — pinned, isolated CPU admission and screen

LightAutoML0.4.2 installed ONLY in work/lama-venv042 under all original version
constraints (extras stripped for pip constraints; requirements.txt untouched).
No NLP extras, pretrained assets, GPU execution, TabICL or TabM experiments.
The resolver brings an unused NCCL wheel via ordinary xgboost2.1.4; this does NOT
enable GPU training. Torch reused from the separate2.5.1+cpu environment.

Pinned source inspected: TabularAutoML has no public refit method. Implement a
fresh preset lifecycle rather than claim fold-trained prediction is full refit.
ONE fixed LGBM learner, no tuned algorithms, feature selection(mode0), stacked
levels, target encoding, intersections, advanced role inference or learned blend.
Explicit numeric/category roles; category encoding_type=int. Original features,
raw regression target, no new masks/weights/SMOTE/HPO/EMB combinations.

Inner training/validation supplied as separate frames, using ONLY original
outer-fitting rows and existing grouped/forward inner split. Stop by primary
MacroF1 or RMSE; preserve supplied class order via integer label mapping. Freeze
the selected inner iteration count; create a NEW preset/reader/features/model
on ALL outer-fitting rows with stopping disabled and that count. Use pinned
DummyIterator train==train ONLY during fixed-length refit; its in-sample output
is NEVER a validation score, never used for selection. cv=False avoids reader
random folds/TE (pinned implementation uses type(cv)is int; None breaks its
multiclass smallest-class comparison). Explicitly assert reader folds are None.

Resource pilot first: tiny deterministic classification/regression, test class
order/OOV/fitting isolation/fresh full refit/export and outer-target perturbation.
CPU1,whole-process1.7GiB/120s. Imported dependencies alone are not admission.
Only after this passes: four sequential original public cuts under max180s,
2CPU/1.7GiB including import; backend165s, max400iterations/lr.05/leaves63/lambda8,
inner stopping30,seed42. Same limits allcuts; compare verified strong V11class
and LONGreg controls. Fixed .1/.25 mixtures, SAME weight must improve BOTHcuts of
at least one task. No weight selection/parameter search on outer labels.

Public screen is reused-public diagnostic, NOT independent quality or official
points. Negative/incomplete -> dormant OFF, no furtherCV/promotion. Positive ->
proper whole-procedure grouped/forward evaluation and both-task lifecycle before
any new immutable release; no additional official submission authorized.
Sources: installed exact0.4.2 reader/utils.py,reader/base.py,validation/base.py,
ml_algo/boost_lgbm.py,automl/presets/tabular_presets.py; official API overview
https://lightautoml.readthedocs.io/en/latest/pages/modules/generated/lightautoml.automl.presets.tabular_presets.TabularAutoML.html
