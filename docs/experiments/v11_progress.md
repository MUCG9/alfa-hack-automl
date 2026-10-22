# V11 continuation, 22 October 2026

Captain renewed development after colleague checkpoint6aefbd9. Branch
`work/llm-upgrade-20261022`; main remains V2. No official upload authorized.
Actual initial usage12:01UTC primary0%,12:06UTC5%; cutoff85% used.
Read `v11_llm_review.md` for accepted/rejected supplied advice and references.

## Active baseline and implementation

Frozen history4 full-default classification launched at about12:03UTC in
`test-runs/llm-upgrade-20261022/history4-class-baseline`. Exact historical SHA
a42fcb1557ec0cf2455abb3add9d6968a8388aedcfcf8d554b26ed73a45788f8 explicitly
verified. Python3.12.14, offline2threads,1.7GiB tree guard,10100s watchdog.
Its source is an independent unpacked copy, not changed by current edits.
Completed about12:24UTC: exit0,1245.970s,refit/integrity pass. SearchF1
.6538467374261537,confirmation .6527157430204659,mean .6532812402233098.
Final CSV58f52dfbfecb1416a456ed715a43cf944876a7f69eed73d7bf1e10170631b326,
byte-identical historical V9/V7/V6. All10original input SHA verified after resolving
the declared nested CSV paths (a first root-path-only diagnostic used wrong paths,
not missing input data). Portable baseline reports copied to release/v11-featureviews1.

Sourcee11409e implements the colleague's already-positive categorical two-view
candidate under the existing protocol. The typed flag is `feature_views` with
value `categorical_te_pair`; it is NOT an arbitrary recursive ensemble engine.
Two internal equal weights, original categories plus fitting-cross-fitted TE,
schema-order first3declared category pairs, smoothing20. Old portfolio relative
order unchanged; one candidate displaces a fallback under unchanged12trial budget.
Each view retains its own fitted iterations; global ensemble/recursive median
reject malformed trees instead of silently truncating zip. Conflicting feature,
encoding/history/augmentation policies fail closed. No threshold/weight/default
regression changes in this stage. Nine non-fitting contract tests passed first.
After the heavy baseline finished, all230unique source checks passed unchanged-
source (165.749s), including real fixtures.23repeated exact-unpacked checks pass.
Frozen featureviews1 full class→regression run started sequentially around12:29UTC
in test-runs/llm-upgrade-20261022/featureviews1-full. Same resource/input controls.
Do not call the pending public gate passed. No new model default retained yet.

## Environment inventory

Available in the current existing venv: Python3.12.14,numpy1.26.4,scipy1.12,
pandas2.2.3,sklearn1.5.2,LGBM4.6,XGB-cpu2.1.4,CatBoost1.2.8,openai1.68.2.
AutoGluon.tabular1.3.1 distribution and actual TabularPredictor import verified;
no fit claim. Its custom groups are constructor input, not fit keyword, and
internally use LeaveOneGroupOut. Default inner feature generation/splitting must
be audited before integration; do not assume a framework import solves contracts.
Optuna/FLAML/LightAutoML/torch/imbalanced-learn/category-encoders/feature-engine
not installed here. All are allowed pins where present in requirements, but
availability is not a reason to replace split/metric/resource contracts.
No dependencies installed. Local RAM15.3GiB, available about2.3GiB initially,
swap partly full; heavy fits and full fixture checks strictly sequential.

Frequent logical commits pushed to the new branch. No extra agents, main merge,
paid resources, keys in commands or official submit. Live Qwen remains unverified.
