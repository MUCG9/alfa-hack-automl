# Iteration3 HPO admission B: source review packet

Prepared only; no canonical edit, Git commit, model fit, API call or promotion.
Apply base: `3060dc243b2d903ec879fb38953798ea05e65774`.

`changes.patch` includes only optional HPO admission, runner/benchmark opt-in,
independent saved-artifact qualification, focused tests and the declared protocols.
Existing canonical portability changes are excluded. All real patch targets and
frozen harness metadata names are repository-relative; Git uses `/dev/null` for
new files. No machine username, private path or credential is embedded.

The default remains `legacy`. Measured admission is explicit. Sampler/seed,
search space, anchor, objective and model/feature policy remain unchanged.
Qualification separates full initial900-second allocation from externally
clipped studies and rejects failed/nonfinite outer outcomes or inconsistent
artifacts/splits. It does not replay the monotonic stop trace or recompute outer
metrics. A valid negative screen remains evidence; promotion is always false.

Verification:42 unique focused no-fit checks PASS (13 admission,7 original HPO,
14 anchor/constructor,8 synthetic qualifier). The final8 qualifier checks ran
AFTER the final relative-harness metadata revision recorded in manifest.json.
Full472-check/48-script source gate, unpacked-release gate and real ML screen
remain PENDING for this source. Pristine public gate inputs and a concrete
common execution deadline are still required before those later gates.

The patch passed `git apply --check` and actual application on a separate pristine
archive of the exact base commit, without any Git commits. All applied source
bytes match the isolated prototype. Flat compilation matches the prototype and
differs from the base in only `automl_runner.py` and `automl_search_hpo.py` (2 of68
files). Requirements are byte-identical. Existing modified files retain the
base CRLF convention; new files use LF.

Review/apply from the repository root with the packet path appropriate to the
review checkout:

```text
git -c core.autocrlf=false -c core.whitespace=cr-at-eol apply --check changes.patch
git -c core.autocrlf=false -c core.whitespace=cr-at-eol apply changes.patch
```

Do not apply to an active frozen runtime. Publication or later integration follows
root review and the separately declared full validation gates.
