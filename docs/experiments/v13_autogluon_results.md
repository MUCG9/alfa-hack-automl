# Pinned AutoGluon procedure: discard this configuration, not the library

All4paired workers fit/refit/export successfully; source/input/split/class/row
artifacts verified and MacroF1 recomputed. Both native LightGBM and CatBoost
trained in each framework worker. Weighted ensemble selected only LightGBM as a
nonzero parent, so full refit correctly includes LightGBM_FULL, not CatBoost_FULL.
Prefitted feature generator used inner-train X only; synthetic poison/isolation
checks passed before public fits. No dependency installation or runtime registry.

|MacroF1|Strong project control|Fixed framework procedure|
|---|---:|---:|
|42|.650292960705|.608943086003|
|43|.652794415506|.645600107908|
|Mean|.651543688106|.627271596955|

BOTH cuts and supported-class noninferiority fail. No fullCV/runtime promotion.
Framework worker520.400/521.991s versus40.739/41.942s control,946.2MiB first peak.
These results cover this exact unweighted GBM/CAT/inner-selection/refit procedure,
not all AutoGluon settings or a causal isolation of one difference. Do not blindly
replace a tuned solution merely because another allowed AutoML package imports.
No model/time/bounds rescue after results. Portable manifest/gate adjacent;
raw prediction/model files remain ignored in test-runs. No official upload.
