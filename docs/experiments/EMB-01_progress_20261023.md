# EMB-01 CPU execution checkpoint

Protocol/backend/pilot committed f458c0c BEFORE public fits. HPO isolated finished
discarded; see HPO-01_isolated_progress_20261023.md. One new dormant execution API
and standard-library contracts added; default registry/worker/planner untouched.
Uploaded55-file long01-submit2 still byte-identical to build profile AFTER these
additions. Main/primaryenv/originalrequirements untouched.

Separate work/emb-venv-torch251:official CPU torch2.5.1+cpu (base version2.5.1),
174.6MB CPUwheel,noCUDA/pretrained/externaldata. Model's actual __version__ checked
at execution.7bounded real/synthetic contract testsPASS in2.047s,sourceunchanged,
plus7architecture checksPASS. Includes full reinitialization/refit,prediction,
CSVexport with unsortedIDs,unknowncategory,fit-local numericstats and perturbing
outertargets without affecting predictions. Initial fixture used wrong positional
TaskSpec args (schema rejected BEFORE fit); corrected to named args. Export round
trip tested within float32precision (relative difference<4e-8),not bitidentity.
Original failed pilot receipts remain ignored,no public quality claims from them.

Public screen ACTIVE,ownedcontroller session57404,output
test-runs/emb-20261023/public-screen/. Four cases strictly sequential:
classification-search,classification-confirmation,regression-search,
regression-confirmation.2CPU/1.7GiB whole-tree/max180s EACHincluding import,inner
stopping and fresh outer refit;ML backend deadline165s/20epochs. No new fits
parallel to this controller,no modifications to canonical sources while active.
Read progress.json,percasecase.json/process.log and finalresult.json,not ACTIVE
as proof of life. Don't duplicate a case if it is still owned/running.

Strong classification control originalV11/LONG ensemble;strong regression LONG
winner at promotion484,matchedrecipe/rows/truth/metrics,not weak singleanchor.
Fixed mixtures .1/.25,not learnedweights;require SAME mixture improve BOTHcuts
for at leastone task,complete lifecycle. Positiveonlyadditionalgroup/forward and
fullagentgates,NOTdefaultpromotion or officialupload. Negative/incomplete retained.
Next conditional LAMA-01,then app-levelAGENT-01;do not invent endlessnewstages.

## Public screen completed — DISCARD

Controller57404 exit0,all4cases exit0,sourceunchanged,fullouterrefit/exportPASS.
Strong controls exactly reproduced,not substituted. No same fixed mixture
improves BOTHcuts of either task. Evidence EMB-01_results_20261023.json.

|Task/cut|Strongcontrol|StandaloneEMB|10%EMB|25%EMB|
|---|---:|---:|---:|---:|
|Class/searchF1↑|.6632403175|.5048597059|.6525933754|.6415745790|
|Class/confirmF1↑|.6553953693|.4880923256|.6550788564|.6437944963|
|Reg/searchRMSE↓|37.5601420446|59.4362707493|37.5194486244|38.6369243621|
|Reg/confirmRMSE↓|31.8337005173|55.7536555846|32.1855560220|33.8763620801|

Class casewall35.711/29.672s,bestepochs16/10;reg6.036/5.232s,bestepochs2/2.
The smallregsearch gain at10% is mixedwithconfirmregression,not promotion.
Do not increaseepochs/changeclassweights/newseed posthoc to erase this outcome.
Dormant typed backend retained,defaultregistryOFF,no furtherCV/fullagent/submit.
Next LAMA-01 compatibility/strictisolation/refit admission,not another EMBfit.
