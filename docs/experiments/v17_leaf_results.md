# Smaller leaves in both categorical feature views: discard

Exact frozen V16 defaults; one changed parameter min_child_samples25→10 in BOTH
views, otherwise fixed learner/seed42/weights/calibration/encodings50/50. All4
workers exit0; original inputs/split/class/row/probability artifacts verified and
MacroF1 independently recomputed by tools/check_paired_gate.py.

|Grouped cut|Leaf25 control|Leaf10 candidate|
|---|---:|---:|
|42|0.6558634659956402|0.6451026598944554|
|43|0.653724307666515|0.6470683310935825|
|Mean|0.6547938868310776|0.646085495494019|

BOTH cuts worsen; supported-class drop gate also fails. Reject without CV or
default changes. Keep leaf25; do not rescue by posthoc5/15/weights. Smaller leaves
did not solve rare-class regions under these group splits. Portable manifest and
gate adjacent, raw rows/probabilities/models remain ignored locally.

The protocol's expected seed43 value had a transcription error in the last
digits (.653724307927 instead of .653724307666515). This does not change recipes,
partitions, thresholds or the keep rule; actual control is recorded in artifacts.
No official upload and no new runtime/archive required for this negative study.
