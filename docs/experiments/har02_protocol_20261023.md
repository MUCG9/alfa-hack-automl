# HAR-02: structured feature hypotheses after the initial MVP

Predeclared before generation/scoring. The initial MVP's regression completed:
meanRMSE36.02469255996805 versus qualified V11/V16 35.44723155783769; both cuts
worse. Optuna inner32.063943365696076→32.06013962740466 did not transfer:
outer40.13054654395413→41.12065014664088. Keep the negative result unchanged.

One genuine Qwen feature proposal failed before training because it imported
NumPy/pandas despite the explicit prompt. It also invented calendar2020 for
an anonymized period and generated20 features at once. Failure is not a measured
ML degradation of those features. This motivates a different proposal interface,
without relaxing the existing worker restrictions or changing the evaluator.

## One new harness hypothesis

Qwen returns at most12 small declarative features: an allowed operation, existing
numeric source columns and a short mechanism. A trusted compiler emits the
row-wise transform; there are no model-generated imports, arbitrary Python,
calendar constants, target/ID access, learned statistics or external data.
Operations: signed_log, difference, product, ratio, log_ratio, missing,
angle_delta. Handle zero denominators, infinities and original row/column order.
This is a bounded alternative generator, not a security-sandbox claim or an
assertion that the generated features will improve the metric.

## Fixed test

One organizer Qwen call, output<=4096tokens, timeout120s; all metadata/no raw rows.
Use the qualified SINGLE asof/history LightGBM recipe as unchanged control,
with CatBoost selector OFF in both arms. Only feature_code differs. Use original
fitting data and forward offsets0/1/2,2threads,1536MiB,600s per worker. Freeze
source/inputs/recipes/splits. Fit all learned preprocessing on fitting rows only.
Compare original-scale RMSE. Advance only if ALL three outer cuts improve;
otherwise discard, without posthoc feature pruning or changed bounds.

Report generation/compilation validity, API usage and ML quality separately.
A single valid generation is not a statistical reliability estimate. It is not
the same experiment as the predeclared HAR-01 baseline/staged prompt comparison.
Current full classification MVP must finish before any new ML benchmark starts.
Do not run nested fits in parallel or promote this generator into runtime by
default without its declared gates and full integration checks.
