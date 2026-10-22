# Binary probability output contract

Previous output projection always chose the second sorted model class. This is
incorrect when the task explicitly requests probability of the first class,
for example label 0 or the literal class `fraud` in [`fraud`, `normal`].

## Implemented

- Resolve explicit positive class/label declarations and literal probability-of
  class names, including quoted labels and numeric labels. Validate against the
  actual classes. Record the source of the choice; reject contradictory or unknown
  explicit declarations instead of silently inverting the answer.
- Preserve the historical last-class default when no literal class can be inferred.
  This is NOT free-text semantic understanding of every business event. Ambiguous
  synonyms, per-target positive-label descriptions and arbitrary label mappings
  still need a later validated task-interpretation stage.
- Use the requested class consistently in dummy priors, ordinary tree output,
  linear-text output, cached blends and refitted ensembles. Keep probability NPZ
  caches in canonical model-class order. Internal binary ROC AUC/log loss remains
  evaluated with its aligned two-column matrix, not mislabeled scalar output.
- Strip harmless surrounding whitespace from dictionary roles.

Nine targeted tests pass (11.434 seconds), including two standalone CLI tests,
reordered/no-ID output, literal positive 0, a first-sorted string label, text output
and cached blend projection. The seven architecture checks pass. Full repository
and exact-release gates are required before promoting the combined v6 candidate.

The known public multiclass Macro F1 task uses labels, not a scalar probability;
this output-contract change should not itself alter its model performance.
