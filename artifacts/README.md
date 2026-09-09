# Review artifact status

These files are intentionally retained milestone/scenario evidence, not current application assets or a proof of institutional approval. [Documentation hierarchy](../docs/README.md) and [artifact guidance](../docs/RUNNING_AND_VALIDATION.md).

| Collection | Status |
|---|---|
| `policy-legibility/after/` | Canonical current accepted student presentation screenshots; README uses UCT/Northstar desktop overviews |
| `shared-workspace/` | Historical before-state relative to policy legibility; accepted workspace extraction snapshot |
| `northstar-legibility/` | Historical before/after and UCT comparison captures, canonical digests and observations |
| `northstar-student-interface/` | Historical portal implementation captures and closure |
| `northstar-v1-browser/` | Historical original Northstar reference integration captures and closure |
| `ppe-browser-qa/` | Historical PPE scenario captures, observations and review |

The separate `docs/redesign-*.png` files show the historical UCT redesign, not the current shared interface. Current means the accepted presentation snapshot, not a live deployment capture or a human comprehension study. Older test counts and screenshots retain their milestone context.

Hygiene Slice 1 removed 20 unreferenced copied source-directory PNGs from `northstar-student-interface/`. Same-subject/same-viewport, byte-identical files remain in `northstar-legibility/before/`; the [capture map](../docs/HYGIENE_SLICE1_DUPLICATE_CAPTURE_MAP.csv) records every old path, retained path and SHA-256. All closures, observations, digests and unique/current views remain. Identical images do not imply identical underlying evidence or failed tests. Other duplicate candidates remain deferred.

Send transient new captures to ignored `tmp/` or `temp/` directories. Do not blanket-ignore this directory: selected review images and closure evidence are intentionally versioned.
