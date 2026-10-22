# V8 shared-budget candidate (not submitted)

Branch `work/agent-budget-20261022`, source `f7bb907`, Python3.12.14.
Archive `../solution-v8-budget1.zip`,68,448bytes,49flat root files.
SHA-256 `2522f6ef47194d92410ceffff22835610c1820ea4c330a2d6ad8c7b0b0ebaa07`.
Original requirements are byte-identical; no new runtime dependencies or models.

**163 unique repository checks pass**, source unchanged,167.662s. The previous
161-check snapshot also passed before two further gateway edge-case fixes.
`repo-tests.json` describes only the final163-check source snapshot.
Exact-unpacked verification is recorded separately in `unpacked-tests.json`;
its23checks repeat part of163, never add them as unique tests.

Scope: one startup-to-export deadline and API ledger across semantic mapping,
planner and independent targets; bounded metadata65,536UTF-8bytes; API-client setup
and retry delays cannot renew the deadline; absent/retried token usage stays
incomplete. No intended change to training, validation splits, augmentation or
model selection. Library discovery remains network-free by default.

The SDK/HTTP/CLI fixture used a local fake server and dummy key, not live Qwen.
Private key input to the organizer-API smoke was policy-denied before entry;
no successful real API session or development spend is claimed.

Full public lifecycles for THIS archive still need verification. Frozen V7's
resumed classification is independent evidence, not a replacement V8 gate.
Only V4 was authorized/uploaded; it shows raw platform score2184.173. Do not
automatically send this candidate or overwrite historical releases.
