# V5 independent-target candidate

Archive: `../solution-v5-multitarget1.zip`.
SHA-256: `f87bddfddac37fb2e74b907ac5529cb7f4e16096e9f5cbc147a9cc1705cbdbd1`.
45 flat files; original requirements, no data/weights/credentials/new dependencies.
Source checkpoint: `997f3d0`; Python builder 3.12.14.

## Passed

- 111 unique repository checks, unchanged compiled source, 124.045 seconds.
- 23 exact-unpacked compatibility/fault/smoke checks, repeats of part of that suite.
- Nine new standalone small CLI scenarios across contract and multi-target tests,
  including sample reordering, missing ID, CSV/TSV, new objectives, clients/dates,
  and independent regression/classification targets. No claim of large-data
  multi-target quality or a live Qwen multi-target session.

Full default public gates for this exact snapshot still need to run. Contract1
passed both public tasks with byte-exact v4 predictions, but that older snapshot
does not include the new solver dispatch and group/date logic.

This candidate is NOT uploaded. The captain authorized/uploaded v4 only.
Keep all previous archives immutable; never overwrite a release to reuse its name.
