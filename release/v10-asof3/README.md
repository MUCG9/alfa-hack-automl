# Experimental support-gated history with static contract guards

Source0933a66; archive ../solution-v10-asof3.zip,
SHA32120f240f0703f0f80de4a020a9be9c3c737070774b217dcb28954bef3acf2a,
72,437bytes,51flat files,Python3.12.3. Original requirements unchanged.

Same min-period support algorithm as asof2, with static context validation even
below the gate and immutable observation-period semantics under feature code.
21history checks pass (13helper +8worker). No default/portfolio promotion.

Follow-up metrics and complete212repo/23unpacked gates are queued sequentially
AFTER the frozen-V9 balanced-subset CV in test-runs/v10-balanced-cv3. Queue state:
test-runs/v10-followups-queue.json. Do not call pending gates passed or start a
second heavy run. Read docs/experiments/v10_progress.md for the latest status.
No official upload or private score for this candidate.
