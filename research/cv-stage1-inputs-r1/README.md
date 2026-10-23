Stage1 grouped outer-CV inputs, prepared and frozen without training or scoring.

The unchanged approved r2 protocol is the authority for factors, clocks, gates
and arm order. This bundle supplies its previously missing actual assignments:
existing make_folds(spec, train, pristine_raw_feature_hashes, 3, 83), exactly
three StratifiedGroupKFold folds. No fold was omitted, reseeded or retried.

Original rows are held out exactly once: 28,958 / 29,220 / 29,492. Fitting rows
are 58,712 / 58,450 / 58,178. Every fold has zero overlapping pristine feature
groups across its boundary and all ten classes in both partitions. The least
supported fitting class is Worms in each fold, with 45 / 41 / 44 independent
raw-feature groups. Every other class exceeds the frozen 100-group support
threshold. These are label counts/support, not prediction metrics.

Files intended for the future solver are ONLY the following five files within
each tasks/f0, tasks/f1 or tasks/f2 directory:

- task.md
- train.csv: original fitting rows, including only their own targets
- test.csv: original held-out features and IDs, with the target column removed
- sample_submission.csv: held-out IDs in original order, one constant class
  placeholder selected from fitting classes; sample values are not truth
- data_dictionary.csv: byte-identical original feature/ID/target schema

The templates preserve the original task instructions except local CSV paths,
actual fold row counts and the sentence describing the new held-out test set.
The feature order, schema categorical roles and class order remain unchanged.
CSV preparation retains source cell lexical values, avoiding a floating-point
read/write conversion. Re-reading each complete materialized task with the
existing discover(..., allow_llm=False) proved identical pristine raw-feature
hashes, fitting labels and ID/row order. A and B must receive byte-identical
copies of the SAME frozen template, whose five hashes are in manifest.json.

Verifier-only material MUST NOT be copied into a solver task or supplied in its
argv, task text, spec, feedback or environment:

- verifier-only/outer-folds.npz: original positions for all six partitions,
  exactly-once coverage and pristine raw feature hashes
- verifier-only/f0-truth.csv through f2-truth.csv: original position, ID, truth
- manifest.json and this preparation receipt: fold support and truth paths

This is an explicit data/argv separation; it is not an OS permission sandbox.
The future reviewed coordinator must deploy only the five-file allowlist into
the actual solver workspace, keep the original full-label task and verifier
files out of that workspace, and seal predictions/source/recipe before an
independent verifier loads outer truth. The coordinator must hash every A/B
deployed copy against this manifest before launch. No solver is launched here.

Arm order remains f0 A/B, f1 B/A, f2 A/B. Every outer fitting task gets the
ENTIRE ordinary offline search/selection/confirmation/calibration/refit process,
not CV of a fixed recipe. The existing internal validation defaults are not
altered. Same 9900 seconds, 12 slots, zero HPO/API and resource caps apply to A/B.
All-positive qualification requires all three complete folds and every r2 gate;
fold-mean and pooled metrics are distinct and cannot be claimed from partial
coverage. Any future formal failure-only early-rejection amendment must bind
these exact arrays/task hashes without changing folds, factors or arm order.

Preparation used one thread, a 90-second/1.5-GiB owned-process guard, and network
tripwires. Actual external wall time was 12.58 seconds, peak owned RSS 267.89 MiB,
tracking denial count zero and cleanup confirmed. No learner was imported or
fit, no API request or score computation occurred, and no canonical source,
active campaign helper/input, original CSV or approved protocol was edited.

Training remains blocked on reviewed ordinary-default last-slot integration,
source/release/path/parity gates, publication, terminal active-campaign cleanup,
released ResearchLock, a reviewed sequential supervisor/label separation and a
new root-assigned immutable prospective Stage1 clock. There is no deadline or
quality promotion in this bundle. Frozen data follows an adaptively developed
public-data hypothesis and is not private/official independent evaluation.
