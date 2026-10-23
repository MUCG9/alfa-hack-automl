# SEL-01 — missing confirmation and subsequent external design

Frozen candidate: model-a68c0bffe7b2b47ed864 from the ORIGINAL12-trial V11 trace.
This is not a new recipe/hyperparameter search or the rejected V14 proposal.
Preparation only while LONG-01 is active. ONE new confirmation fit after both
LONG-01 tasks finish and actual trained CSVs/integrity are verified. One recipe
evaluation may contain multiple nested view/stopping fits; report actual cost.
Never start
it from a stale RUNNING/PID assumption or silently restart an interrupted fit.

Use the original confirmation_split.npz, exact selected recipe and original
input bytes. No split reconstruction, altered first2 slots, calibration policy,
new class weights or feature changes. At most900seconds,2threads,1.7GiB owned
whole-tree watchdog, separate fresh output. A failed/timed-out fit is a technical
failure, not an imputed quality score. No automatic repeat on a new seed.
Parent/child/source/input/probability/row/class/metric hashes must remain auditable.
Do not put the new prediction into original baseline directories or rewrite
original evidence. A new versioned confirmation request adds its one prediction
reference and declares its ACTUAL new source manifest, not a historical V11 SHA.

Then reuse the same frozen search shortlist and original fixed blend-grid; no
third re-selection based on the new confirmation labels. Compare both cuts to
the exact reproduced V11 ensemble. Both must strictly improve for a promising
screen. Any negative/mixed result is retained, selector stays OFF, no full CV.
A positive screen remains adaptive reused-public evidence, NOT promotion.

## External design declared before any new fit

For a positive screen, evaluate the ENTIRE selection/search/confirmation/blend
procedure, not just this chosen third model. Classification:3 full-feature-hash
outer folds via StratifiedGroupKFold(shuffle=True,random_state=20261023), frozen
before execution. Require every fitting fold to contain all declared classes;
insufficient group support is infeasible, not a license to change the split.
Within each outer fitting subset generate
all fitting-internal search/confirmation evidence and stopping/calibration/TE.
Each arm has identical portfolio/order, no outside-derived winning recipe or
probability cache. Only third-slot rule differs. Outer held-out targets remain
outside the task given to workers and are read only by the final scorer.
Re-execute adaptive fallback inside fitting rows; do not transplant a trajectory
selected using the outer labels. First2 slots are frozen relative to each arm's
own identical inner trace; use the same blending grid and reserve on both arms.

Initially cap each arm at1800seconds per outer fold, with300seconds reserved
for inner confirmation and outer full refit;3folds x2arms <=10800seconds total
research wall budget on this host. Count nested view fits, not only recipe IDs.
If feasibility pilot cannot complete both lifecycles under this cap, report
infeasible rather than selectively extending only the candidate. Any budget
amendment must be declared before a fresh paired experiment, never after seeing
outer quality. The small pilot itself does not establish a quality improvement.

Require complete exactly-once outer predictions; report pooled F1 and fold means,
per-class support, paired group-bootstrap for fixed outer predictions, and gain
without the rarest class. Gate: pooled and mean improve, no outer-fold regression,
no supported-class regression, then complete both full public task lifecycles
and integrity/export/release tests. Bootstrap is descriptive and unadjusted for
adaptive/multiple comparisons, not private-score proof. No runtime promotion or
official upload is authorized by a positive component-only result.

Supported class means at least100 independent full-feature groups in EVERY
outer-fitting fold. Its pooled outer F1 must be noninferior; report all classes
regardless of this guard. The rarest class is defined by total fitting-group
support before the study; pooled macroF1 excluding it must also improve. These
guards are frozen, not selected after observing new scores.

Regression selection remains unchanged for this classification-only experiment;
future forward work needs a separate declared temporal protocol.
