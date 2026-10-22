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

Classification has now COMPLETED, exit0/refit/integrity pass,2691.782s:
search .6632403174648631,confirmation .6553953692580672,mean .6593178433614652.
Both improve over full reproduced history4 control .6538467374261537 /
.6527157430204659,mean .6532812402233098. Final CSV SHA
af64a22a5e9f5ff26ed817dfaa707e77e5bd9500dc63e52748521b00670efa96.
Selected equal-thirds global blend contains TWO typed feature-view recipes plus
XGBoost, nested iteration tree preserved. Portable classification evidence in
release/v11-featureviews1. Regression parity also COMPLETED: exit0/refit/integrity,
mean RMSE35.44723155783769,CSV05ccd9eabcbf29f4b858e9cd89f6dfe568ce1bdddb32a397c71b98ef1c0c1673
byte-identical history4,harness225.692s. Both exact public lifecycles and the
predeclared full-procedure quality gate PASS. KEEP V11 as the qualified local
release; official upload still not authorized. V12 threshold optimizer remains
a separate dormant method pending its source/unpacked/screen gates.
This is reused public validation, no official-points projection.

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

## Completed follow-up research, 14:47UTC checkpoint

V11 is the qualified improving full-agent release, not a pending integration.
V12 threshold2 passed244unique source/23repeated unpacked checks, but bounded
log-weight numerical optimization worsened BOTH paired cuts; default old
coordinate callback remains unchanged. V13 pinned AutoGluon GBM/CAT successfully
fit/refit/exported all4workers with inner-only prefitted feature generation, but
both cuts worsened. V14 cached selection proposal reproduced actual controls,
then failed its predeclared V11 noninferiority gate;0newfits/no runtime change.
V15 moment retransformation and V16 original-scale LS factors both worsened the
latest supported forward cut; older cuts correctly skipped with exact CSV parity.
V17 leaf10 in both fixed views worsened BOTH cuts (.654793887→.646085495 mean).
All negative protocols/results/gates are preserved; no rescue CV or defaults.

Latest canonical runtime f72c6df, frozen solution-v16-mean1.zip,
SHA68e1eb0c933807720178ef4708df2c0dbf55fe9940b0dfb849d7704dbe3b2566.
258unique unchanged-source checks169.114s+23repeated exact-unpacked PASS.
All new postprocessors remain OFF. Final full-default regression→class parity
started around14:42UTC in final-default-parity, execution15685, same2threads/
1.7GiB/10100s controls. At this checkpoint pending, not a passed public gate.

One async permission question for exactV11 is pending; no human answer/upload.
Usage14:46:51UTC primary78%used/22%remaining,weekly91%used. No new research after
final parity, preparing current.md/next-agent.md and Git for85%used cutoff.
