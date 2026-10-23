Git experiment queue — source-only bootstrap

CLI: global --repo LOCAL_CLONE --remote origin --dispatch-branch research/remote-dispatch,
then list|poll [--worker-id ID], claim --job-id ID --worker-id ID [--dispatch-sha SHA40],
submit --job-id ID --worker-id ID --claim-sha SHA40 --report FILE --artifacts DIR,
or collect --job-id ID [--output NEW_DIR]. The copyable agent instructions are
REMOTE_AGENT_START.txt. Recommended published script path:
research/remote-experiments/queue/remote_queue.py.

Job schema uses schema=1 (not schema_version), exactly id/kind/readiness/objective/
caps/source_refs/dependencies/expected_outputs. Ready jobs must have pinned source
refs and declared outputs. Store ready immutable JSON at
research/remote-experiments/jobs/<id>.json. Keep drafts outside until ready; edits
or deletions/reuse of published IDs fail history checks. Source files referenced
by old jobs must remain at immutable versioned paths. Source refs allow only
.py/.patch/.json/.txt/.md. A pinned source-manifest.json can bind the separately
root-approved pure-code ZIP; the agent verifies it manually. ZIP upload denied.
SHA256 pins describe exact Git blob bytes, not a checkout transformed by CRLF
filters. Publish/hash those same bytes; the offline fixtures disable autocrlf.

Caps: wall_seconds1..10800, cpu_threads1..2, worker_memory_mib128..1536,
whole_memory_mib>=worker and<=2048, max_fits0..128, max_api_calls=0. Actual learner
fit calls include nested fits/refit (not logical jobs); preprocessing separate.
First source_only(max_fits0) performs the capability handshake. A later bounded
job is admitted only if it depends on a completed source_only result of the
SAME worker and pins primary-published approval JSON at
research/remote-experiments/reviews/<dependency-id>.json. Exact approval schema:
schema=1,job_id,result_sha,worker_id,approved_for_bounded_experiments=true,caps.
The resultSHA/worker/dependency must match, requested caps must not exceed either
that approval or global hardcaps. The approval is a trusted primary dispatch
review decision, not self-certified scalar ML correctness. No approval/dependency
means fail closed. Normal operation is one existing agent/claim/model at a time;
poll resumes the current unfinished claim. No extra agent or service is started.

Only fixed Git commands run, shell=False, no job/source/patch execution, services,
cron, model/project imports or keys. Existing cached Git auth remains; GIT_TERMINAL_PROMPT=0 and GCM_INTERACTIVE=Never
prevent interactive credential prompts, provider API env is stripped, hooks
disabled and raw Git errors suppressed. Missing auth is blocked; no GUI opens. Fetch only names the
configured research dispatch and declared claim/result branches. Local HEAD,
working tree, main and dispatch are not changed by claim/submit/collect.

Claim is a unique sibling commit parented to the exact dispatchSHA and pushed
normally to refs/heads/research/remote-claims/<id>. Two workers racing for that
new ref produce distinct sibling commits: one push wins, the other is rejected.
Same-owner resume returns the original immutable claim/clock; another owner,
expiry/reclaim/requeue/reset/force/deletion is never supplied. Result is a unique
child of the exact claim, normal-pushed once to
refs/heads/research/remote-results/<id>. It seals exact job/claim bytes, workerID,
metadata, source artifact hashes. Result appends/overwrites are rejected.

Claims use original claimed_at_unix and deadline=start+cap. Reports must preserve
both, finite/null scalar metrics, exact usage, first+secondary failures. Non-success
requires null metrics and first_error. Numeric future metrics require complete
reported resource values under caps. Source-only unknown measurements may be
null, but fits/API remain0. Completed outputs equal expected_outputs; failures
may provide subsets. Declared/actual filename case collisions are denied for
Windows/Linux portability. Content/path/size checks do not establish real remote
resource or model correctness.

Public artifacts: flat UTF8 .py/.patch/.json/.txt/.md only; <=128KiB/file,
<=16files/256KiB total. Reject symlinks, directories, traversal, common raw-data/
prediction/learned-weight names, disallowed extensions/binary, credentials and
absolute/private paths. Bounded text/JSON and secret-pattern checks are sanitation
filters in a trusted collaboration protocol, NOT a semantic guarantee against
disguised raw rows/predictions/weights/secrets. Every received source/metadata is
untrusted pending main-agent review. The tool never applies or imports it.

Collect validates parentage, declared refs, jobSHA/claimSHA/workerID, original
clock fields, caps, metrics/errors and every artifact hash, and labels results
remote_reported_requires_independent_verification,promotion=false. It does not
independently measure host clock/RSS, verify scalar ML metrics or auto-promote.
Network push completion can occur after a pre-push timestamp: submit returns its
actual local completion time, but an immutable Git packet cannot independently
prove publication timing. Root must retain this limitation and independently
verify/local-confirm before qualification. No remote agent is considered connected
until an actual validated claim is observed.

Prepared offline tests (AUTHOR DID NOT RUN):
python -B -X utf8 -m unittest discover -s work/remote-experiment-queue-next-dev -p test_remote_queue.py -v
13 methods use isolated temporary bare Git repos/clones, no network, real repo,
models or APIs. Cases: actual2worker race, roundtrip/hash proof, immutablejob/ref,
same-owner originalclock, wrongworker/claim/job/artifact, duplicate result,
null/timeout/deadline/caps including18actualfits, credentials/path/data/binary,
case collisions, malformed schema and Git symlinkmode. The13th creates a real
source result and primary review, then admits a matching bounded claim while
rejecting wrongworker, changedresult and excessive approvedcaps. Root runs serial under
its bounded technical supervisor before publication/use.
