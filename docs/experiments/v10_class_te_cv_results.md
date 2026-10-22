# Frozen categorical feature-view grouped CV — completed

Protocol v10_class_te_protocol.md; source exact history4 SHA
`a42fcb1557ec0cf2455abb3add9d6968a8388aedcfcf8d554b26ed73a45788f8`.
Three-fold StratifiedGroupKFold seed73,unchanged frozen leaf recipes,2threads,
1200s/worker,1.7GiB tree guard. Controller46586exit0,all6workers successful.
87670original rows exactly_once. No fitting after captain requested handoff.

## Predeclared primary endpoint: fixed50/50probability blend

|MacroF1|Strong control|TE leaf diagnostic|Fixed blend PRIMARY|
|---|---:|---:|---:|
|Fold0|.641237770212|.646137014192|.648007875526|
|Fold1|.633295603768|.638289441226|.638038833502|
|Fold2|.647188887692|.658442975176|.649725432942|
|Fold mean|.640574087224|.647623143531|.645257380657|
|Pooled OOF|.640209809443|.647349395776|.645099303706|

All fold deltas positive,+.006770105315/+.004743229734/+.002536545250.
Mean gain+.004683293433;pooled gain+.004889494263. Standalone TE is diagnostic,
not an alternative endpoint selected after observing stronger CV results.

Additional frozen gates PASS:all nine classes with minimum100independent fitting
full-feature-hash groups across folds have pooledF1drop≤.01;worst DoS−.002776829.
The rarest fitting-support class is Worms,minimum41groups. Mean pooled classF1gain
excluding that class remains+.004943201374. Exclusion means averaging the other
nine already computed classF1 values with all rows/predictions unchanged,not
removing Worms rows before recomputing class metrics. No weights/thresholds tuned.

## Evidence and reproduction

- v10_class_te_cv_results.json:complete original benchmark aggregate manifest,
  six worker status/metrics,source/input/harness/split fingerprints and leaf OOF.
- v10_class_te_cv_diversity.json:validated prediction alignment/hashes,per-fold
  fixed blends and exactly_once pooled blend diagnostics.
- v10_class_te_cv_gate.json:fitting-group support counts,per-classF1deltas,all gates.
- Local ignored test-runs/v10-class-te-cv3 retains raw artifacts;not in Git.

Existing analyzer command (output must be a NEW path):

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 test-runs/venv-core/bin/python tools/analyze_diversity.py   --results test-runs/v10-class-te-cv3/results.json   --control calibrated-lgbm-control --candidate categorical-pair-te   --output test-runs/v10-class-te-cv3/reanalysis-new.json
```

Fitting support is computed from SHA-verified original train.csv,feature columns
in frozen manifest order,using pandas.util.hash_pandas_object(index=False),then
counting unique hashes with each class among original split.npz training rows.
No validation-label choice of classes/thresholds;support>=100,drop<=.01 and rarest
exclusion were declared before CV. Ties use stored class order. Counts and split
SHA are portable in gate JSON. No new generic gate tool was implemented.

## Checkpoint decision

Fixed recipe CV gate PASSED. Runtime/class defaults remain history4,feature-view
integration and full-agent comparison NOT STARTED. Captain requested stop/handoff
for usage limits;no new long work. Next agent follows already predeclared
v10_class_te_agent_protocol.md:one candidate,tests/newarchive,full baseline/candidate
classification and regression parity. No official submission. Reused public data,
not unbiased/private quality or platform points estimate. TE helper isolations
are tested;CV pass alone does not establish full search/refit procedure quality.
