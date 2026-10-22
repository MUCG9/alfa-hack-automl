# Residual-moment retransformation: discard

All6workers successful, frozen source/input/forward partitions unchanged. Control
reproduces previous asof-min3 scores on all3cuts. Only factor correction changed.

|Forecast period|Control RMSE|Bounded smearing RMSE|
|---|---:|---:|
|5|39.05167816956453|40.16077429802434|
|4|31.846185166957753|31.846185166957753|
|3|50.92466951315985|50.92466951315985|

Eligible latest cut WORSENS. Fitting-only estimated factor1.0484459043820131,
12946calibration rows,3fitting periods/2contexts,matching173iterations. Older cuts
correctly skip when calibration history is unavailable; BOTH validation/test CSVs
are byte-identical control on each. Validation SHA for periods4/3 respectively
bd003cae6a86b73077f1609b3b37ffa02bb2e100980196d12ec85a6ac2531721 /
60336096ceb8be0682d296391d493d06464ebb3a57b4b28d7b18445a3396ec73;
test SHA d9ea588fa3ba3d124f07a649c7db03f25e0b8c235efac927c2858b85f87d324a /
a4da03ce7b9aae72f961404681318ebfd96d031fe5e0606f102921c713699d4f.

Gate FAIL, no portfolio/default/full-agent promotion. Correction is a legitimate
hypothesis, not a universal remedy for skew: residual distribution/model/history
can shift. No adjustment of bounds/eligibility after results. V11 remains qualified.
Portable aggregate adjacent; raw rows/models/predictions not in Git. No upload.
