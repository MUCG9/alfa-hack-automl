UQ3 READY binding metadata builder R2 — frozen SOURCE ONLY

Source SHA256: c323ef4b793960b94f0fff1db83525dfe85b9bb91aaf703093b4758160520581

Default command (root may later run after review; NOT run by author):
  work/venv/Scripts/python.exe -B -X utf8 work/uq3-ready-binding-r2-next-dev/build_binding.py
This only describes required refs. It does not read a gate, assign a clock, write READY,
import a candidate, or launch anything.

Future actual write syntax (placeholders are explanatory, not executable READY values):
  work/venv/Scripts/python.exe -B -X utf8 work/uq3-ready-binding-r2-next-dev/build_binding.py --write --self-sha256 c323ef4b793960b94f0fff1db83525dfe85b9bb91aaf703093b4758160520581 --private-manifest <WORK-relative.json=actualSHA> --driver <WORK-relative.py=actualSHA> --closer <WORK-relative.py=actualSHA> --campaign <WORK-relative.json=actualSHA> --root-closure <WORK-relative.json=actualSHA> --root-confirmation <WORK-relative.json=actualSHA> --archive <WORK-relative.zip=actualSHA> --candidate-manifest <WORK-relative.json=actualSHA> --authority-review <WORK-relative.json=actualSHA>
All input paths are relative to work, with POSIX separators. Output defaults to the
exclusive NEW uq3-ready-binding-r2-next-dev/binding.ready-root.json. It must not exist.
The source template is never rewritten. Failure emits only type/status, no private path.

The full gate is selected by actual refs, NOT a UAR08 directory/session/positive claim.
The failed UAR08 cannot satisfy the positive gate predicate. A future UAR09 or another
reviewed full gate must use the exact same schema/counts59/634/23/104/73, actual driver
and closer exit0/root confirmation, exact current source inventory and same73 ZIP
members. Raw HPO is the reviewed R3 e11ac8...; cadence runner is12091e....
Archive hashing/opening occurs only AFTER positive gate/root/confirmation validation.
The script hashes code/metadata only; no CSV, target, prediction or pristine label reads.
It verifies actual module-map/member hashes for HPO/runner/metric, plus raw qualified
source pins. Policy compiled hashes are derived from the actual qualified code archive.

Metadata READY is not launch approval, publication evidence, a test PASS, or a newclock.
The reviewed UQ3 launcher/controller still perform their own gate/artifact/current-source,
publication, provider, actual ownership/lock, clock, authority and all-four deployment checks.
CSV copies and the real authority checkpoint remain inside that future common10800 clock.
No actual future gate/archive/root confirmation/binding is manufactured by this packet.
The historical UQ2 root5c9/ec6 is admitted as a clean NEGATIVE only; original FAIL stays.
The sole historical fac3 relocation preserves canonical9f84. All other merged pin
collisions fail, including output collision. This addresses the prior UQ1 pin failure.

Inspection performed: source/AST/hash only. Builder/default/write execution0, tests0,
models0, API0, data reads0, process scans0, assigned clocks0. Future actual gate/source
checks and metadata-tool invocation belong solely to root after source peer review.

R2 closes only RB01: BOTH archive and candidate.manifest.json supplied hashes must
match BOTH campaign.technical_artifacts and positive proof.technical_artifact_refs.
These maps use absolute producer str(Path(cfg['output'])/filename) keys. WORK-relative
CLI refs resolve to those checked fixed output paths; no relative-key/case fallback.
The check precedes ZipFile/member acceptance. An independently valid replacement
ZIP+manifest is rejected if either producer map is missing, stale or mismatched.
All other predicates remain exactly R1. The only other AST delta is the new exclusive
output-directory default. R1 source/handoff/proof/README and the source-only finding
are preserved; R1 was never executed and no runtime failure is fabricated.
