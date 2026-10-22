# V5 contract work: separate from the history3 submission candidate

The v4 history3 full classification benchmark runs from its immutable extracted
archive, not from these changed canonical sources. Do not replace v4 ZIPs with v5.

Hypothesis: an agent can lose an entire unknown task before model search if it
misunderstands its files, output schema or objective. Public metric improvements
alone do not address this. The organizer webinar explicitly did not guarantee an
unchanged schema or metric. These are robustness changes, not claims of private
score improvement.

## Objective semantics

- Added MAPE, MSE, RMSLE and balanced accuracy to discovery and outer evaluation,
  with matching inner LightGBM/XGBoost callback semantics and optimization direction.
- Explicit primary declarations override diagnostic metric mentions. An explicitly
  unsupported objective is rejected instead of silently relabeled RMSE/Macro F1.
- Existing metrics retain their formulas. This does not change default training
  objectives or prove that the new metrics are optimally modeled.
- MAPE uses sklearn 1.5.2's relative scale, epsilon behavior at zero targets, not
  an invented percentage multiplier. RMSLE clips negative predictions to zero in
  evaluation and publication, but rejects negative ground truth.
- Eight objective tests cover detection, direction and inner/outer agreement.
  Further lifecycle and exact-release gates are required before promotion.

References: [pinned MAPE semantics](https://scikit-learn.org/1.5/modules/generated/sklearn.metrics.mean_absolute_percentage_error.html),
[balanced accuracy](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.balanced_accuracy_score.html).

## Input roles and table I/O

- Preserve exact canonical filenames and explicitly quoted local paths first.
  Add bounded aliases for training/test/sample/schema tables; reject ambiguous
  roles instead of picking the first file. Arbitrary unnamed roles are not yet
  inferred by an early LLM contract stage.
- The dictionary is optional if target and ID are unambiguous from table schemas.
- CSV, semicolon-delimited CSV and TSV share the same input reader in discovery
  and execution. Other formats are explicitly unsupported, not silently parsed.
- Input paths must resolve inside the task directory, including symlinks.
  Generated run directories and hidden paths are excluded from the role catalog.
- Duplicate headers are rejected before pandas can rename them invisibly.
- Eight small input tests and the seven architecture tests pass. Full lifecycle
  and public parity remain separate required gates; these tests are not model
  quality evidence.

## Output contract

- A sample without an identifier is now a supported row-order output contract;
  no invented ID column is inserted. Documented training IDs remain excluded
  from features even when they are not part of the output.
- Sample IDs may be in a different order from test IDs. Store a checked bijection,
  publish in sample order and invert the mapping when reading regression caches.
  Classification probability caches remain in test order. This also prevents a
  cached ensemble from accidentally applying the same permutation twice.
- Missing/duplicate/unmatched IDs and invalid row mappings fail explicitly.
- Six output tests cover label/probability shape, missing ID, reorder, invalid
  mappings and cached regression blends. Composite IDs are not implemented.
- `TaskSpec.identifier` permits `None` for row-order output; old string-ID payloads
  remain valid. No other message format or DataPolicy version was changed.
