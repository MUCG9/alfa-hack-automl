# HPO-01 / FE-01: renewed implementation request, 22 October 2026

The captain's new request authorizes an MVP, local training within a three-hour
budget, and iterations on the Qwen agent. This supersedes the previous stop on
fits; it does not authorize submissions, extra agents or paid compute. Work on
`work/qwen-optuna-mvp-20261022`, based on `f3c8aba`. Preserve V11/V16 and all
historical evidence. Original requirements remain byte-identical.

## Independent changes

1. FE-01: optional CatBoost importance selection after bounded feature generation.
   Fit a small selector separately on EACH actual fitting partition, including
   inner stopping/calibration and full refit; never reuse an outer selector for
   inner predictions. Stable original column order. No default feature removal.
2. HPO-01: optional Optuna 4.2.1 ask/tell sampler, sequential owned workers.
   Study objective is a fixed holdout constructed solely inside outer fitting
   rows. The existing worker separately nests preprocessing/stopping/calibration.
   Outer validation labels never enter study values. Keep transformations,
   weights, target policy and seeds fixed; tune model capacity/regularization.
3. HAR-01: compare the existing planner with explicit stage feedback only after
   a bounded live smoke. Missing private credentials are a live blocker, not
   evidence that mock or offline results used Qwen. Never copy a chat key.

## Predeclared experiment and gates

First run the explicitly requested four-stage MVP as an exploratory complete
procedure: EDA/role discovery, bounded features plus CatBoost top32 selection,
the existing multi-family portfolio, inner Optuna8, staged Qwen feedback,
confirmation, full refit/export. At most14 search experiments, two planner
calls per task and a common10800s campaign deadline; two public tasks sequential.
This combines several factors to establish the requested MVP and cannot
attribute a gain to one component. Its control is the preserved V11/V16 complete
procedure. Keep the best qualified baseline even if this exploratory MVP loses.
The independent component gates below govern any subsequent promotion.

HPO screen uses the strongest qualified SINGLE recipe (not a weak uncalibrated
model) from current portfolio: categorical two-view LightGBM for classification,
schema/history LightGBM for temporal regression. These component controls are
distinct from the stronger complete V11 ensemble. Refit the selected procedure
on each outer fitting partition before evaluating its outer holdout once.

Compare unchanged recipe, RandomSampler and TPESampler. Both samplers: eight
maximum trials including the unchanged anchor; TPE startup=3, seed137. Same
inner split, search space, per-worker and total-study deadline. No pruning from
incomparable intermediate metrics. Failures/duplicates stay in the ledger.
Report completed trials and actual seconds: equal caps do not imply equal work.

Classification outer group/hash cuts42/43; regression forward offsets0/1/2.
Use two threads, at most 1536MiB per owned worker, 600s per worker, 1800s per
study and 10800s for the entire development screen. Fits/fixtures sequential.
No partition reconstruction from old predictions; these are NEW development
splits from the original fitting data and their fingerprints must be recorded.

Advance TPE only if all available outer cuts improve over the unchanged recipe
and its mean beats equal-cap random search. Class per-class F1 loss<=.01 for
classes with >=100 independent fitting feature groups; report gain excluding
the rarest class. Negative screen stops expansion and default promotion.
Positive classification screen requires three-fold grouped CV of the ENTIRE
inner selection procedure, exactly-once coverage, separate pooled/fold scores.
Forward regression is not exactly-once OOF. Then compare the complete candidate
agent with V11 on both tasks including refit/export/integrity, unchanged-source
suite and exact-unpacked gate before any release promotion.

FE selection is a separate paired ablation, without HPO or generated features
changing simultaneously. Use the same outer cuts and qualified component
controls, top_k=32, selector100 iterations/depth5. Advance only if both class
cuts improve with the same supported-class gate; regression must improve all
forward cuts. A skip when <=32 columns is not evidence of selection benefit.

No official score claim from these reused public data. The PDF specifies RMSE
and Macro F1; official normalized points need hidden-test baseline metrics and
cannot be inferred from local validation. Publish measurements and limitations.

After the initial MVP and live smoke, HAR-01 compares baseline/staged prompts
using identical measured feedback, at most two candidates per prompt and two
API calls per task. Score proposals on the same declared outer cuts, with the
unchanged component control. Same positive paired/support gates as above;
contract acceptance, distinct proposals, runtime and token usage are separate
from ML quality. No prompt changes after observing a mode's results.

## Access at start

Original participant baseline and requirements read; requirements SHA256
`9173b0388532fbd2a709e4f4b3029e3b9ccab685fce43a85261ffa1ba95efbe6`.
Optuna4.2.1 installed only in local development venv. Qwen environment is empty;
a private env-file path was requested. Linked Google document unavailable via
browser; existing project endpoint/model are configuration, not new live proof.

Optuna API reference checked:
https://optuna.readthedocs.io/en/v4.2.1/reference/generated/optuna.study.Study.html
