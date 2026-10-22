# Independent multi-target extension

Separate change after the validation-contract checkpoint. This is not a joint
multi-output estimator, classifier chain, ranking method or stacking layer.

## Contract and isolation

- Detect 2..16 declared targets or unambiguous train-only target columns. The
  output must contain their exact names, plus at most the known identifier.
- Reuse read-only loaded input frames for metadata and partition planning. Build
  one ordinary single-target TaskSpec per target; project the sample through the
  shared table boundary, without copying or changing the raw source CSVs.
- All declared targets, not just the current one, are excluded from features and
  forbidden in generated feature code, including a target-shaped column in test.
- The original single-target search/confirmation/refit workflow now lives in
  `solve_single`; the CLI dispatches multi-target tasks to a separate coordinator.
  Child outputs live in separate run directories and are combined only through
  the publishing API. Source/data integrity is checked both per target and globally.
- Models are sequential. Divide one shared wall-clock deadline and one planner
  call budget, rather than multiplying the platform's 3-hour budget by targets.
- Publish valid per-target baselines for every output before any long search.
  A failing target preserves its valid checkpoint or reverts to its baseline;
  other targets continue. Exhausted time explicitly reports skipped baselines,
  never fabricated successful training.
- Preserve sample row order, including reordered IDs and outputs without IDs.
  Do not infer an aggregate metric from differently scaled per-target scores.

## Verification scope

The complete **111-check repository suite passes** with unchanged compiled source
(124.045 seconds). Its twelve multi-target checks include three standalone CLI cases:
two regression targets with reordered IDs, no-ID regression outputs, and two
classification targets with different class counts. A twelfth check was added
for excluding another declared target even when a placeholder is present in test.

Large real multi-target datasets, mixed-objective task descriptions, per-target
multiclass probability matrices, arbitrary output renaming, joint target modeling,
ranking and a live multi-target Qwen session are NOT validated capabilities.
Binary probability columns use the existing per-target probability contract.
Current public tasks still require a full exact-archive parity gate after the
single-target orchestration extraction before promoting this checkpoint.
