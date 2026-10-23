Root launch/observation helpers and historical publication receipts.

Stage1 snapshot records the actual fixed64800s clock and process admission;
it is an active snapshot, not a completed CV or model result. The controller
b85d and a70f manifest remain unchanged. observe_cv_r4.py is read-only and
never starts, resumes or signals work. No helper permits a concurrent fit,
clock reset, weakened quality gate, Stage2 or platform submission.
