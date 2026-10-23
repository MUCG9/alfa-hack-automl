# EMB-01 CPU admission — predeclared

HPO-01 complete/discarded (32a601c);no parameter-search promotion. New factor:
small supervised tabular MLP with learned categorical embeddings,NOT pretrained,
not data augmentation and not a replacement of existing defaults. Optional typed
execution API,not exposed to ordinary planner/default registry until full gates.
Only original Torch2.5.1,CPU wheel from official PyTorch index in separate env;
primary env/requirements/submitted ZIP unchanged. No CUDA/external data/assets.

Representation: numeric fitting-only median/IQR scaling,clip[-10,10],missing
indicators;categorical fitting-only most-frequent1024 vocabulary,0unknown/missing,
learned embedding dim min(16,max(2,round(2*cardinality**.25))). No target encoding
or cross-row transforms learned from validation/test. Head128→64→output,
ReLU/LayerNorm/dropout.1,AdamW lr.001/decay.0001,batch512,seed42,max20epochs,
patience4 on fitting-INNER primary metric;regression fitting-targetmean/std,
MSE on standardized raw target,NO log-target guess;classification unweighted CE,
fixed declared classorder. No threshold tuning/classweights/resampling changes.

First bounded synthetic CPU resource/contractpilot,classification+regression,
known missing and unseen categories,inner stop plus independent outer refit,
test predict and exact export validation.1thread forfixtures,120s/1.2GiB guard
for complete pilot. Require finite aligned predictions/probabilities,fit-only
vocabulary/scaler/target stats,deterministic classorder,complete fullfit and source
integrity. Import alone not an admission result. Any technical exception gets a
fresh versioned retry only for a specific diagnosed repair,never fake metrics.

If pilot admits,bounded screen both public tasks and BOTH original validation
splits,strictly sequential. Each max180s/2CPU/1.7GiB including inner model
selection and freshly initialized outer refit. Preserve original group/time
isolation;inner partitions derived ONLY from outerfitting.20epochcap fixed.
Compare independent candidate to strong V11/LONG exported policy,then FIXED
mixtures .1EMB+.9control and .25EMB+.75control on same saved predictions,
not learnedweights/thresholds. Identical class/row alignment. For regression use
strong current LONG saved paired predictions,not only a weaker standalone tree.
Classification uses unchanged V11/LONG baseline ensemble.

Require SAME declared mixture to improve BOTH cuts for at leastone task,
complete lifecycle and reported time/memory;otherwise discard this bounded
candidate,do not widen epochs/loss/depth after seeing validation. A promising
screen remains reused-public,needs independent-structure group/forward procedure
validation and fullagentboth/refit/export/source/unpacked gates before promotion.
No new official submission authorized. Do not claim standalone weak candidate
useful merely from residual decorrelation. LAMA/AGENT later distinct stages.

Official installation reference:
[PyTorch2.5.1 CPU](https://pytorch.org/get-started/previous-versions/#v251).
Pinned embedding API pages inaccessible through web reader;verify installed
Torch2.5.1 signatures and CPU behavior locally before using backend.
