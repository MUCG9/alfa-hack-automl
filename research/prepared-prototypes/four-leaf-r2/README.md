Isolated default-OFF backend, not a full-agent integration or ML qualification.

Tree: work/four-leaf-view-dev, base b505629876770d741627f371a0778dd30f3b9dc0.
Only feature_views.py and worker.py change; one mocked test module is added.
Canonical source, active trueMVP files, cache/HPO trees and inputs are unchanged.

Explicit activation is recipe.params.feature_views=categorical_te_capacity_pair.
The default portfolio/planner/runner is unchanged and does not add this mode.
The existing categorical_te_pair behavior and two-leaf iteration contract remain.
The new subtype requires base num_leaves63, no generic FE/selector, ordinary
calibrated softmax classification and the existing schema-based category rules.
It copies the exact two-view factory twice with capacities63 and98, preserving
all other model/weight/calibration/encoding settings. No dataset or label names
are used. Four leaf order: original63,encoded63,original98,encoded98.

Internal dispatch accepts exactly these four leaves with .25 each; ordinary
global ensembles still accept only2..3 non-ensemble components. The external
learner remains lightgbm, allowing a global ensemble to contain this bounded
feature-view subtree. Four refit iteration values are validated and retained
recursively, including median_iterations and a global parent. There is no alpha
or capacity tuning axis and no HPO, broad, selector or cache policy change.

Nine mocked checks passed with real-model-fit/API/network tripwires all zero,
one thread,2.72seconds,160.4MiB peak owned RSS and confirmed cleanup. They cover
exact factory equality with both original parents, default portfolio/two-view
parity, schema renaming, unsupported tasks/transforms, four-leaf/global iteration
trees and mismatch rejection, .25 probability averaging with permuted class
orders, calibration/iteration/full-fit propagation, old .5 two-view behavior,
global two-parent recursion and rejected arbitrary four-parent/weight changes.
All teachers/students are mocks; no actual ML cost or quality was measured.

Pure AST flat compilation passed for68 files, changing only automl_worker.py and
automl_execution_feature_views.py. This is not an imported-runtime, full source
registry or exact-unpacked gate. The original requirements SHA is unchanged.
Initial/final manifests preserve exact source and patch SHA; source did not
change after the tests. No test assertions or old evidence were removed.

Missing before training: independent patch review/publication, eventual reviewed
default-last-slot integration, full source/exact-release/regression parity gates,
actual frozen three-fold assignments and whole-selection CV. Follow prospective
work/fullagent-fixed-half-plan-r2. No fits are authorized by this document, no
deadline is assigned and no default promotion is claimed.

R2 append-only freeze: r1 pending manifest (tests_executed=0), verified proof,
source and mock receipts remain preserved without edits. R2 changes only
unsupported-method membership from set to tuple, preserving ValueError for JSON
list/object/null; negative cases live in the existing mocked validation test.
R2 nine mock tests passed, no skips/failures/errors/real fit/API/network attempts,
one thread, 2.50 seconds external wall time, 160.76 MiB peak RSS, cleanup true.
Source bytes match the r2 manifest before and after checks. Pure AST flat build
again passed 68 files; only the two expected compiled modules differ from base.

The fixed internal alpha=.5 means four leaf probability weights exactly .25 each.
It is separate from the existing outer global ensemble weight selection policy,
which is unchanged. No default-slot integration, source/full-release/import gate,
CV qualification, actual fit, performance claim or promotion has occurred.
R2 source and patch are now frozen pending independent review and root action.
