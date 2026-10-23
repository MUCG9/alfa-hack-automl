# LAMA-01 current execution checkpoint

Protocol0c5e383 predeclared before fixtures/publicfits. Pinned dependency resolver
and import succeed in isolated work/lama-venv042; core environment unchanged.
requirements.txt unchanged. Constraints cover ALL original listed package pins,
not only LAMA. No runtime installation. Unused transitive NCCL wheel is NOT GPU
execution. NLP extras/pretrained backends remain unused.

Typed dormant LAMA API added, not in registry/runner. One fixed LGBM preset, all
selection/tuning/target encoding/intersections disabled. Reader cv=False pin-
specific fold disabling behavior inspected; fresh full refit at inner-selected
iterations with early stopping0. Refit's in-sample predictions ignored, not OOF.

6optional real/synthetic tests PASS, source unchanged,5.234s guard wall. Class
probability order, OOV/missing input, unsorted-ID export, full refit, external
target perturbation invariance and resource/partition checks included. Fixture-r1
accidentally imported an existing unittest TestCase, ran13 checks successfully but
FAILED expected-count gate; import fixed, fresh r2 ran exactly6. Do not count
repeated checks as13 new LAMA tests. No public quality claim from fixtures.

Active: ONE controller30382,source1d550b9,output
test-runs/lama-20261023/public-screen/. One independent four-case public screen via tools/screen_embeddings.py
--backend lama; same strong controls/original partitions as EMB, not combined
with EMB/HPO. At most180s/2CPU/1.7GiB percase. No canonical edits while source-
guarded controller is active. Check actual outputs before repeating any action.
Default OFF; no new official upload authorized.

## Completed: DISCARD, no runtime promotion

Controller30382 ended0. All4cases exit0,fullfreshrefit/exportPASS,sourceunchanged.
No samefixedmixture improves BOTHcuts of either task. Evidence
LAMA-01_results_20261023.json. The classification confirmation10%gain is mixed
with searchregression; regression10%searchgain is mixed with confirmregression.

|Task/cut|Strongcontrol|StandaloneLAMA|10%LAMA|25%LAMA|Inneriterations|
|---|---:|---:|---:|---:|---:|
|Class/searchF1|.6632403175|.5950444951|.6536113858|.6513234638|126|
|Class/confirmF1|.6553953693|.6228133174|.6555466923|.6520630524|159|
|Reg/searchRMSE|37.5601420446|49.9134597666|37.5124001722|38.0568250655|196|
|Reg/confirmRMSE|31.8337005173|46.0327525083|31.9569157775|32.7998071980|33|

Wholecasewall49.206/62.402/8.853/6.037seconds,not an equal3hfinalsearchcomparison.
This is a bounded admission screen against stronger saved controls,not proof that
every possible LAMA configuration fails. Do not tune posthoc or promote mixed
results. Dormant adapter retained;defaultOFF,noCV/fullagent/newsubmit. Next and
last finite stage: app-levelAGENT-01 offline contract gate/live admission.
