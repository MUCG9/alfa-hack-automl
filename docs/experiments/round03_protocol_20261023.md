# ROUND-03: Qwen-guided exact-context execution cache

Different factor: harness efficiency. HAR-01 baseline/staged Qwen proposed the
same supported execution recipe and incurred duplicate work. ROUND-01/02 are
negative against PIPE02; do not re-run them or weaken gates. Current qualified
release remains PIPE02F1.6593178433614652/RMSE35.39729814378806.

Ask organizer Qwen once (180s,2048output,at most3HTTP attempts) to select ONE
already measured regression recipe ID for a duplicate-execution replay and
explain cache validity. Closed recipe registry, no new code/parameters. Explicit
comparison/component controls, direction and negative ledger in context. JSON
validation plus scientific audit; at most one documented repair, no free code.

Replay the chosen outer cut0 recipe twice without cache, then once cold plus a
hit with cache:3 actual top-level fits,4 logical requests. Same frozen source,
original inputs, actual saved fitting/validation row order, seed/threads/fit mode.
Fresh exclusive output and owned lock,2threads,1536MiB worker+parent,600s/worker,
2160s entire experiment with verification reserve. No concurrent fixture suites.
Never present replay as a new model-selection gain or an independent score.

Conservative cache key covers complete source map, input hashes, complete task
spec+task text hash, recipe (exclude only descriptive hypothesis), ordered split
rows, fit mode/iterations, threads, Python and core library versions. Root/output
directories are recorded as lineage, not confused with a new training run.
Validate current source/input/spec/split context before lookup; hit also requires
unchanged successful origin result and ALL artifact fingerprints. Failed jobs
are never cached. A hit writes a distinct reference receipt and returns origin
metadata; it must never pretend the requested new directory contains a refit.

Gate: native metrics and actual ordered prediction arrays must match across all
four logical requests; independent labels/split/recipe checks required. Assert
2 versus1 actual worker launches and no hit launch. Report cold/hit/verification
latencies and observed wall comparison; claim a speed benefit only if measured.
Changed labels/data, row order, recipe/policy/features/seed, source/dependency
version, threads or fit mode MUST miss; tampered artifact MUST refuse reuse.
Test these boundaries before fits, commit before runs. No canonical cache/default
promotion from this narrow replay. Feed observed outcome into a distinct next
Qwen plan under the captain's continuing authorization.
