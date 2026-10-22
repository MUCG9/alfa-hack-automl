# Limited pointwise ranking baseline

This extension supports a numeric **score per document**, not an output permutation
or integer rank positions. It is a pointwise regression surrogate, NOT LambdaRank,
XGBRanker, a listwise model or a claim of optimal ranking quality.

## Contract

- Detect a ranking/NDCG description, numeric non-negative relevance, one explicit
  query/group role in the dictionary, and a single score-output column.
- Keep `kind=regression` for the pointwise learner and record
  `task_family=pointwise_ranking`, the actual NDCG objective and query metadata.
  Never misreport NDCG as RMSE classification or use a query ID as a feature.
- Hold out entire queries in outer, inner and CV evaluation. Legacy row-wise
  ranking validation is rejected. Joint query/time validation is not implemented.
- Evaluate mean query-wise NDCG, with the task's explicit `@k` or the full list.
  Average ties. Default linear relevance gain follows sklearn's definition;
  explicit `2**relevance - 1`/exponential-gain text selects exponential gain.
  Zero-ideal queries score zero (the pinned sklearn 1.5.2 convention); positive
  singleton queries score one. These choices are logged, not a universal promise
  that every organizer uses the same NDCG formula.
- NDCG itself drives LightGBM/XGBoost inner stopping through aligned query context.
  CatBoost still uses its regression stopping proxy; all outer selection uses the
  requested NDCG. Linear-text ranking and multi-target ranking are unsupported.
- Cached blends retain the same query/evaluation context. Predictions can be
  negative finite scores: their order, not a probability interpretation, matters.

## Verification

Thirteen ranking tests passed in 24.113 seconds, plus seven architecture checks.
They compare ties, interleaved/unequal query sizes, cutoff, linear/exponential gain
and callback/log inversion against sklearn; verify query-safe splits and caches;
run the compiled CLI with/without ID through confirmation/refit/export; and run
an XGBoost worker with query-aware inner stopping. This is synthetic lifecycle and
metric correctness evidence, not real ranking-data performance or a private score.
The complete 124-check suite passed with unchanged compiled source in 170.407
seconds. This establishes the synthetic/offline gate, not full-size ranking quality.

Reference: [sklearn NDCG](https://scikit-learn.org/1.5/modules/generated/sklearn.metrics.ndcg_score.html).
