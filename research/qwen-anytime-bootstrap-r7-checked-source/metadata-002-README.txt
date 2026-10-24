Source only: exact QH config + strong_authority + predecessor projection.

Usage after actual RQ6 full closure and final QH READY private binding:
  <pinned-python> -B preflight.py <ABS-controller.py> <ABS-private.json> <controller-sha256> <private-sha256>

The utility always evaluates BOTH exact predicates and reports their matching hashes and complete saved known count. It creates only its own bounded30s metadata interval, never a campaign origin.

Policy: opaque SHA streams may read ONLY the exact frozen immutable allowlist (including CSV/NPZ), in <=1MiB chunks with clock checks. No stored SHA is substituted for actual bytes. Decoded reads are restricted to pinned .json/.py metadata, <=32MiB; datasets, NPZ/NPY, prediction files and other payloads cannot be decoded. No candidate/controller module import, model, network, process observation or execution entrypoint is permitted. The one import exception is the exact previously qualified C5 stdlib-top-level metadata helper; the projected predecessor calls only its ids function.

Eight entire controller function bodies and their transitive top-level global assignments are copied, with no formula, field, path-normalization or predicate rewrite. MetadataPath adds an IO boundary, not synthetic hash answers. The input controller must already have an independent source review; this is not an arbitrary Python sandbox.

No utility invocation, test, fixture, dataset read, array decode, API call, PID observation or actual experiment clock was performed during authoring. Root must publish/pin the final utility and observe actual exit0 on the final controller/private hashes before QH launch.
