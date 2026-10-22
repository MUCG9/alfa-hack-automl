# Bounded threshold optimizer: reject quality promotion

Exact threshold2 archive, same strong learner/inner rows/iteration matching,
original coordinate control versus positive bounded log-space Nelder–Mead400fev.
No feature/weighting/data-policy change. All4workers exit0, matching split/input
hashes; prediction/class/row/metric artifacts independently revalidated.

|Macro F1|Coordinate control|Refined factors|
|---|---:|---:|
|42|.6502929607048801|.6492554207203460|
|43|.6527944155063504|.6525964375154725|
|Mean|.6515436881056152|.6509259291179093|

BOTH cuts worsen. Supported-class drop remains within.01, but direction/mean
gates fail. No fullCV or default insertion. Existing conservative calibration
remains; this does not show all threshold tuning is bad (the control uses it).

On fitting-only inner holdouts, regularized objectives improved
.646439081→.646879068 and .649716963→.650875553; both reached400evaluations without
convergence. Better inner fit did NOT transfer to outer F1. Do not expand bounds/
budget after outcomes or copy the supplied optimizer as a guaranteed breakthrough.

Code remains an explicit dormant experimental capability; original coordinate
callback unchanged.244unique unchanged-source checks (169.873s) and23repeated
exact-unpacked threshold2 checks PASS. Earlier prequeued threshold1 verifier
correctly refused source mismatch after bound fix; not counted as passed. No
public fit used superseded threshold1. No new dependencies/liveQwen/officialupload.
Portable results/gate JSON adjacent; raw predictions/models ignored locally.
