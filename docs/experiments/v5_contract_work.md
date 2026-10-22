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
