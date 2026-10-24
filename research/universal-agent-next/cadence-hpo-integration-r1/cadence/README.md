# Prospective strict-task checkpoint cadence — SOURCE ONLY

Only copied runner.py and new focused test source. No canonical/frozen changes, imports/tests/fits/API/PID scans/data reads or actual clocks.

Deadline/rollback/finite checks use the ORIGINAL caller budget.clock on every callback. Real resource inspections are first-call, forced phase boundaries or due0.25s. No newclock, deadline, allowance, sleep, thread or background heartbeat. Only fully successful completed inspection advances last_sample. Actual raw denial/resource violation, slow inspection>10s, stale gap>10s (before and after inspection), nonfinite/rollback/deadline are sticky fatal. Skipped callbacks never refresh observation time.

Required forcing sites in strict flow: initial boundary; IO03 completion; before/afterIO02; before/afterfallback allocations/publication; initial protected fingerprint phase; before/afterfull loader; afterfull validation/discovery; handoff to existing solver. IO03/IO02 callback/bytelimit code unchanged. No memory-doublecount fix, caps/model/task/metric/retention/API policy change. DefaultOFF flow and original direct checkpoint helper unchanged; AST proof restores wholebase by removingonlynewclass and restoring strictflow.

12 meaningful synthetic methods prepared,0run. Tests use fakeclock/inspector only; no actualprocess enumeration or learner. This directory is a delta overlay, not standalone complete package; future root can materialize it into a full source tree only after UQ2 terminal/freshclosure and source review/new lease. No current runtime cause/savings/quality claim. Cadence is an explicit prospective observation-policy change; it is not equivalent to per-row sampling.
