# Cooperative supervision fix — source only

T6 remains FAIL with its original source, threshold and clock preserved. This
folder contains a patch/copy of the external coordinator only. It is NOT a T7
assembly or launcher. Its retained historical output/manifest references must
not be executed; root must create a separate reviewed attempt/binding later.
The actual m3 ML runtime archive and its source/parameters/metrics are untouched.

sha() now accepts an optional cooperative checkpoint before/open/read chunks,
after every1MiB chunk and after close. guard()/core_seal() propagate it; guard
rechecks exact manifest+coordinator after the full inventory as well as before.
The checkpoint measures the existing real previous heartbeat and keeps threshold10,
then checks unchanged actual wall/monotonic/common and optional parent deadlines.
No thread, sample reset, excluded wall time or deadline extension is introduced.
The original all-file/all-byte digests, symlink checks, ownership cleanup and
qualification invalidation remain. Post-task metadata has explicit source guards
before/after; parent cap is checked throughout it rather than only on return.

The first exceeded heartbeat sample is retained in the receipt before raising.
After PowerRequest release the source guard cannot call an active heartbeat:
its per-chunk callback checks the unchanged elapsed10s terminal bound from the
last real active sample plus common/final clocks; it does not invent new samples.
Thus a truly blocked read/OS/JSON operation>10s still fails. The fix addresses
long *cooperative* work, not immunity to host suspension or arbitrary blocking.

Two UNEXECUTED test methods use fake time/stream plus a byte-identical local
PowerRequestGuard fixture. They model24s of6s chunks with unchanged deadlines,
and a real uninstrumented10.5s gap that fails before any reset. No Windows API,
fit/network/child process or real task data is needed. Tests/imports were not run.
Future root-controlled no-fit validation must use explicit bounded guards and
tripwires before any new heavy launch; no gates, clocks or gain are claimed here.
