UAR00 is prepared source, not an executed test result. There are four sequential
suites: contracts12, models12, evaluation12, metrics12. No suite is imported or
executed by source preparation. No fit, API call, quality metric or promotion is
part of this queue.

The private-manifest.json contains machine paths and must stay local. Do not
publish/copy it with the public source packet. Public source pins contain relative
module names/hashes only. All source inventories, suite files, interpreter and
proven supervision dependencies are pinned before actual launch. In particular,
the guard uses original canonical process helper fac3; E01's changed process
module is a separate under-test source in its isolated worktree.

Before launch, root must finish the separate LA2 postfailure audit, observe its
actual terminal exec, close it, and freshly confirm its preparers absent. Bind
that actual root-proof path to extra_closures.postfailure_audit in the private
manifest. The current null path deliberately blocks execution. Recompute the
private manifest SHA after this one binding. Keep all existing source/test pins
unchanged. The separate LA2 proof is required too: primary FAIL stays FAIL.

Only then root reviews/publishes source and gives the single serial test lease.
There is no background heartbeat, service, auto-retry or expiry/reclaim. The first
actual --launch assigns exactly one fresh600s wall/monotonic clock. It includes
preflight60, four parent100/child75 envelopes, final audit110, and root closure30.
Unused time does not raise a child cap. Guard callbacks keep the same clocks and
record real heartbeat gaps; they never reset a deadline.

Children use the proven supervisor with solver_seconds=None: a minimal environment
without API keys, one BLAS/OpenMP/compute thread, 1536MiB suite subtree and 2048MiB
whole owned tree. These are sampled cooperative guards, not an OS sandbox or a
claim that all instantaneous peaks are observed. Only exact owned identities and
their observed descendants are used. Unknown/denied observation or cleanup stops
the queue. No broad PID/name scan or unrelated signal is introduced.

Root launch template (variables are filled from actual receipts; no clock is
assigned by this document):

```powershell
& $Python -B -X utf8 $Runner --launch --private-manifest $PrivateManifest --private-manifest-sha256 $PrivateManifestSha --self-sha256 $RunnerSha --la2-closure-sha256 3ae50a32e3931f214e59343eee99654c37b77bf66b1b8ec233d416586d6cfd8b --la2-actual-exit-code 1 --la2-actual-tool-evidence $La2ActualToolEvidence --extra-closure ("postfailure_audit=" + $AuditRootSha)
```

Add --la2-actual-exec-session with the real session only when the LA2 proof records
one; omission truthfully means null. Actual tool/exit/session must equal that
SHA-bound proof. Each suite directly runs its pinned test file with -v, requires
one exact Ran12 summary, final OK, no skip, exit0, cleanup and original caps.
The queue preserves the first and secondary errors and all raw logs/receipts.

After observing actual UAR00 exec terminal, root promptly closes inside the same
original600s and the closer's own30s:

```powershell
& $Python -B -X utf8 $Closer --private-manifest $PrivateManifest --private-manifest-sha256 $PrivateManifestSha --driver-sha256 $RunnerSha --self-sha256 $CloserSha --actual-exit-code $ActualExitCode --actual-tool-evidence $ActualToolEvidence
```

Add the real --actual-exec-session if non-null. Parent success is only pending
root confirmation until this separate proof. Root must also observe the closer's
actual exit and freshly confirm its captured preparers absent. The terminal
closure never turns a failed suite or the historical LA2 failure into PASS.
