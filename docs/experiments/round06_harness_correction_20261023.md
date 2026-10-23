# ROUND06: preserve the no-fit failure and original deadline

Original attempt at04b03c9 stopped after3.383s before any new worker launch.
Shared native-artifact loader verified classification CSV metrics correctly but
then tried to cast named class predictions to float. This is a development
loader error, not a model failure or evidence against the hypothesis. Original
`round06/screen/` and identity120263/create_time1792739389.25 are preserved.

Correction branches only the returned prediction dtype on task kind. The
existing regression path still returns float; both paths retain the same native
job/split/recipe/row/truth/metric verification. Five focused joint-decision tests
PASS, including actual classification and regression CSV loading and independent
trial-tampering rejection. No new ML fit was part of these checks.

Retry uses a new output directory and the ORIGINAL common screen deadline:
1792739389.7839258+3000=1792742389.7839258 UTC epoch. The harness accepts this
deadline explicitly and reserves60s for verification; no new3000s budget.
No split, grid, control, objective, class gate, memory/thread cap or Qwen plan
changes. No candidate outer scores have been observed. This fixes the setup
failure before fitting; the protocol's maximum one correction after fitting
begins remains available, with original attempts/deadline preserved.
