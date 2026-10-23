# Native Windows process-identity cleanup incident — 23 October 2026

The public MVP coordinator failed during `wait_owned` cleanup after regression completed. This is a coordinator cleanup failure; it does not invalidate the completed task merely by changing its status to a failed model fit.

Preserved original evidence, relative to the chat workspace:

- `work/mvp-campaign.log`: traceback from `wait_owned` finally → `ProcessTree.terminate` → cached `member.terminate()` → Windows `OpenProcess` access denial for PID 22860.
- `work/frozen-mvp/test-runs/public-mvp-native/campaign.json`: initial coordinator state remained `running`; it is not a reliable completed-campaign receipt after this exception. Preserve it rather than silently rewriting the failed attempt.
- `work/frozen-mvp/test-runs/public-mvp-native/task-00/automl_runs/mvp-four-stage/report.json`: completed regression reports `final_fit_status=ok`, `integrity_ok=true`, elapsed 328.328 seconds. The report was read directly during this fix; no regression refit was performed.
- The coordinating agent separately inspected the reused PID and reported `svchost.exe`, creation time `1792710257.8444164`, parent PID 1388. This fix did not inspect, signal, terminate, kill, or attempt to elevate access to that unrelated process. The Windows access denial prevented the stale termination attempt from completing.

The old implementation retained psutil Process objects and assumed its signal methods guaranteed PID identity on every platform. On this Windows/psutil 6.1.1 path, that assumption was insufficient: a tracked descendant's old PID could designate another process at cleanup. Checking a cached object's cached creation time would not repair that failure.

The patch changes only `src/automl/infrastructure/processes.py` runtime behavior:

- Reopen each tracked PID with a fresh `psutil.Process(pid)` and compare its actual creation time to the stored `(pid, create_time)` before descendant discovery, termination, killing, and inclusion in `wait_procs`.
- Remove missing, reused, or unverifiable identities. A denial during an owned descendant's signal is recorded in `cleanup_errors` and excluded from escalation and further waits; no permission bypass is attempted.
- When the owned Popen root has exited, never reopen it for discovery or signal it by PID. Running root termination/killing uses the owned Popen interface, which retains the root handle on Windows. Root waiting also uses Popen.
- Revalidate descendants after the graceful wait before killing them, and again before the final wait. A returned cached `alive` Process object alone does not authorize a signal.

`tests/test_process_identity.py` contains nine fake-process checks: reuse before discovery, reuse after refresh, valid owned descendant termination, exited root reuse, reuse immediately after termination, reuse while waiting, verified live descendant killing, disappearance, and AccessDenied without kill retry. All nine passed in 0.009 seconds. These tests performed no actual process termination and no ML fits or API calls.

The patched source was copied byte-for-byte to `work/frozen-mvp/src/automl/infrastructure/processes.py`; matching SHA-256:

`ee60b1aa8592db65a515b9c03f43cc9112d8ab6e8f11b60b63496cb0255d740f`

This is an explicit supervisor correction to the frozen snapshot, not a feature/model/search-policy change. Preserve the prior failure and task artifacts. Classification may resume through a new coordinator receipt with the original shared deadline; do not duplicate regression or reset its research budget.

Fresh identity checks remove the demonstrated stale-object failure. They are not an operating-system sandbox or an atomic lifetime handle for arbitrary descendants: a process can still change between separate system calls. No claim of an absolute cross-platform race-free process API is made.
