# V11: review of the supplied LLM plan, 22 October 2026

Continuation branch `work/llm-upgrade-20261022`, base colleague checkpoint
`6aefbd9` from `work/cpu-research-20261022`. Main and historical releases stay
immutable. Captain renewed implementation authority, not official upload authority.
Initial actual app reading12:01UTC: primary0% used, weekly79%. At85% used stop
starting long work and prepare handoff. No extra agents or paid resources.

## Useful principles, not promises

Keep fail-safe publication, fitting-only class decision calibration, task-aware
feature hypotheses, explicit inverse target transforms, diverse probabilistic
ensembles and bounded JSON AutoResearch. They already substantially exist.
There is no evidence supporting a guaranteed .75 F1 or75–85 official points.
The latest official feedback remains captain-reported V9raw2187.849; the new
message rounds the overall score to23/100, not a new per-task metric breakdown.

|Supplied suggestion|Audit / decision|
|---|---|
|Replace modular code with six root files|Reject rewrite. Canonical `src/automl` has tested service boundaries; flat compiler produces platform modules. New postprocessing belongs behind existing evaluation API.|
|First baseline3fold within3minutes|Current dummy CSV is published before model fitting, then working model checkpoints atomically replace it. Three fits cannot guarantee3minutes on unknown inputs. Preserve fail-safe, measure actual latency.|
|Only overwrite after5fold OOF improvement|Not implemented as claimed. Runtime uses search+confirmation; dev benchmark supports grouped CV. IID KFold leaks duplicate groups and future periods. Train calibration inside outer fitting rows; evaluate complete selected procedure outside it.|
|Rare classes currently F1=0|False for current control: Worms/Shellcode already have nonzero F1; calibrated class factors already used. Inspect per-class precision/recall/support, not a stale generic diagnosis.|
|Unconstrained Nelder–Mead class multipliers|Do not copy blindly: negative/unbounded weights, scale nonidentifiability and piecewise-constant F1 plateaus. Existing bounded positive, regularized coordinate search is a legitimate threshold rule. Any replacement is a separate paired experiment with outer-label isolation.|
|Always balanced class weights|Already mild inverse-frequency power.5 plus inner decision calibration; full inverse frequency is an existing alternative. Do not multiply library balanced weights by current sample weights and accidentally double-balance.|
|Network formulas and fixed2024 building age|Public-name hardcoding violates universal-agent aim. Most ratios/log priors were already investigated. Age must use an observed reference period, never a fixed invented year. New formulas require metadata eligibility, numerical guards and a separate measured factor.|
|Always log1p if skew>1|Reject forced switch. Log target changes the loss and inverse predictions need not minimize original-scale RMSE. Existing log/nonlog candidates and original-scale callback already compare this. Require nonnegative fitting targets; never use outer targets to choose transform.|
|Automatically choose LightAutoML if import succeeds|Pinned0.4.2 is allowed, but not installed in current local venv; import success is not integration validation. Default internal splits/metrics/resources may violate our contracts. Optuna/FLAML/LAMA/AutoGluon are future isolated backends, no runtime pip or dependency changes.|
|df.eval for untrusted expressions|Not a sandbox. Preserve bounded AST-filtered row-wise transforms in credential-free workers; AST filtering itself is not full security isolation. Reject I/O/imports/targets/IDs/other-row statistics.|
|Always fixed LGBM/CatBoost50/50|A fixed mixture is a hypothesis, not automatically better. Existing cache-based blend selection and refit already work. Colleague has a predeclared positive fixed two-feature-view study; complete that protocol first.|
|Write sample_submission.csv|Wrong output for organizer CLI: preserve sample input and write validated `submission.csv` beside task.md.|
|Qwen3.8 model / internet off|Supplied model name is not verified. Preserve organizer environment model/URL and bounded gateway; do not infer that all egress or the organizer API is unavailable from generic text. No new live API verification claimed.|

## Immediate predeclared implementation sequence

1. Repeat frozen history4 full-default classification baseline in current pinned
   Python3.12.14 environment, offline2threads,1.7GiB guard,10100s watchdog.
   This is a trusted historical archive run; expected SHA is explicit because
   colleague built on Python3.12.3 (ast.unparse can differ in bytes).
2. Implement ONLY the already-positive categorical feature-view candidate under
   `v10_class_te_agent_protocol.md`. Typed LightGBM flag, fixed internal.5/.5,
   schema-order categorical pairs, fitting-only existing TE. Per-view iterations
   must survive confirmation/recursive median/global blend/full refit.
3. Meaningful small tests, new archive, full unchanged-source suite and unpacked
   gate; then full candidate class and regression parity sequentially. Keep only
   if BOTH full search/confirmation F1 improve. Record failures, no posthoc rescue.
4. Only after that checkpoint, isolate a bounded postprocessor experiment or
   another nonredundant suggestion. Never combine a threshold change and feature
   ensemble into one attribution claim. No official submit without new approval.

## Primary references checked

- [LightGBM4.6 class weights](https://lightgbm.readthedocs.io/en/v4.6.0/pythonapi/lightgbm.LGBMClassifier.html): weights distort probabilities and multiply sample weights.
- [SciPy1.12 Nelder–Mead](https://docs.scipy.org/doc/scipy-1.12.0/reference/optimize.minimize-neldermead.html): evaluation/iteration limits and bounds are explicit; supplied snippet sets no bounds.
- [sklearn1.5 target transformation](https://scikit-learn.org/1.5/modules/generated/sklearn.compose.TransformedTargetRegressor.html): inverse transform is part of prediction, not a universal quality guarantee.
- [sklearn CV](https://scikit-learn.org/stable/modules/cross_validation.html): split choice and held-out prediction evaluation have distinct scopes.
- [pandas2.2 eval](https://pandas.pydata.org/pandas-docs/version/2.2/reference/api/pandas.eval.html): expression evaluation API, not a security boundary.

Original requirements SHA remains
`9173b0388532fbd2a709e4f4b3029e3b9ccab685fce43a85261ffa1ba95efbe6`.
Raw rows, predictions, weights, environments and API keys are never committed.
