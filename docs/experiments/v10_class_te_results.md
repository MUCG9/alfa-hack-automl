# Categorical-pair feature-view screen: fixed blend passes, CV pending

Unchanged history4 runtime/input/harness/splits; new leaf target statistics use
only each current fitting partition, including inner stopping/calibration. Schema
selects categorical names; no public-name constants are added to runtime source.
3new isolation tests and full219source checks pass; all51source hashes match the
history4 release manifest. Raw predictions remain ignored local artifacts.

|Holdout|Strong control|TE branch diagnostic|Primary fixed50/50 blend|Blend delta|
|---|---:|---:|---:|---:|
|42|0.650292961|0.650249495|0.655863466|+0.005570505|
|43|0.652794416|0.648823665|0.653724308|+0.000929892|
|Mean|0.651543688|0.649536580|0.654793887|+0.003250199|

Primary endpoint was fixed blend before fitting; standalone TE is diagnostic.
Both-fold screen gate PASSED. No weight/smoothing/model tuning after results.
Proceed to the already declared complete3fold grouped CV seed73, SAME two leaf
recipes and fixed0.5 blend; exactly-once OOF, fold mean and pooled separate.
Predeclared all-fold/class-support/rarest-excluded constraints remain unchanged;
no portfolio/default promotion before CV and full-agent confirmation.

Control artifacts were copied from successful original runs with every SHA
preserved; derived manifest retains both parent manifest hashes. No new control
fits for the screen, so this is a quality comparison, not a runtime comparison.
Evidence v10_class_te_results.json and v10_class_te_diversity.json. These public
folds have been repeatedly inspected; no private/official-points guarantee.
