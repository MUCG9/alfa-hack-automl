# ExtraTrees feature-family screen: mixed result, no promotion

Protocol v10_extratrees_protocol.md, frozen history4 runtime, no default changes.
Original run stopped without a completed candidate result; scoped process audit
found no live owned worker. Cause remains unknown. Preserve the interruption
receipt, do not label it a measured quality loss. Exact candidate-only retry
completed both jobs exit0. Sources/harness/inputs/splits match completed controls;
control child0 validation AND test CSV bytes match standalone controls both folds.
Derived analysis copies retain every file SHA and both manifest hashes.

|Holdout seed|Calibrated LGBM control|Fixed50/50 LGBM+XT|Delta|
|---|---:|---:|---:|
|42|0.650292961|0.644409878|-0.005883083|
|43|0.652794416|0.658312670|+0.005518255|
|Mean|0.651543688|0.651361274|-0.000182414|

Both-fold keep gate FAILED; no CV, class portfolio or runtime source change.
XT child-alone scores and conditional errors are diagnostic; no rescue weight
search. Peak candidate RSS1548.6/1518.2MiB stayed within the1.7GiB local guard.

The fixed blend improves accuracy and log loss on BOTH folds, while MacroF1 is
mixed. First fold corrects247control errors but breaks174correct predictions;
Worms F1 loses.078431 and Analysis.016071, offsetting gains in other classes.
This is direct evidence that error complementarity needs the actual target metric,
not only disagreement or an aggregate error count. Second fold MacroF1 gain does
not satisfy the predeclared two-fold criterion. Conditional pooled OOF is not
claimed for these overlapping holdouts.

Evidence: v10_extratrees_results.json, v10_extratrees_diversity.json and
v10_extratrees_interruption.json. Generic analyzer additional fixed blend fields
are diagnostic only; the original50/50 endpoint and discard decision remain fixed.
Reused public data, no private score or official upload.
