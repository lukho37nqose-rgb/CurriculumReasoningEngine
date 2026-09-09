# Repository Hygiene Slice 1

Documentation baseline: `2fa9f69730d2daa7b66398a66e008550aa51da41`, committed separately as `docs: align repository with current CRE architecture` and pushed to `origin/main`. All 39 intended Markdown files were included, matched the completed documentation slice, and the tree was clean before hygiene work. Remote: `https://github.com/lukho37nqose-rgb/CurriculumReasoningEngine.git`.

## Scope and decision standard

Only low-risk stale browser scripts, repeated generated captures and unused frontend helpers are removed. Old is not the same as dead. The accepted archaeology audit remains historical evidence; this register records the changed candidate status rather than rewriting that audit.

The ten selected helpers have no executable reference beyond their declarations in the tracked tree. HTML inclusion, event handlers, projection-only loading, string dispatch, window/global lookup, tests, docs, workflow/build references and compatibility comments were inspected. Their top-level global exposure is incidental to a classic script, not a documented stable interface. Precise Chromium coverage found zero calls for every candidate in three app.js loads spanning Northstar and UCT manual/empty desktop journeys; active renderReport calls were observed. Coverage supports the dependency evidence, not a claim to observe external developer-console users.

## Pre-removal inventory and decisions

| Candidate | Type | References / replacement | Risk | Decision |
|---|---|---|---|---|
| statusWidget, requirementExplanation, majorExplanation, courseExplanation, reportStatusExplanation | Old frontend presentation | Definition-only; shared workspace/language owns active presentation; zero observed calls | LOW | SAFE_TO_REMOVE / DEAD |
| isRecognitionNotice, noticeGroup, detailMessage | Old notices/error formatting | Definition-only; current shared rendering/error mapping used; zero observed calls | LOW | SAFE_TO_REMOVE / DEAD |
| completionPercent, nextSummary | Old report summaries | Definition-only; shared overview/exploration and bounded export replace old composition; zero observed calls | LOW | SAFE_TO_REMOVE / DEAD |
| tools/qa_northstar_browser.py | Browser rehearsal | No runtime/test/workflow imports/calls; moved useful checks to shared browser suite | LOW after migration | SAFE_TO_REMOVE |
| tools/qa_ppe_browser.py | Browser rehearsal | No runtime/test/workflow imports/calls; moved scenario/keyboard/upload checks to test_browser_rehearsal_scenarios.py | LOW after migration | SAFE_TO_REMOVE |
| Twenty northstar-student-interface/*-sources.png copies | Duplicate historical capture output | No explicit path/basename references; same scenario and viewport retained byte-for-byte in northstar-legibility/before | LOW | SAFE_TO_REMOVE |
| .pytest_cache/, .ruff_cache/ | Observed local caches | Local-only, already self-ignored; explicit root patterns make purpose durable | LOW | GENERATED_IGNORE_ONLY |
| Local logs / Python bytecode | Local/transient output | Existing *.log and __pycache__ rules sufficient; no tracked files found | LOW | GENERATED_IGNORE_ONLY; retain local files |
| Current policy images | Current review evidence | README/closure references; intentional versioning | HIGH deletion risk | GENERATED_VERSIONED_INTENTIONALLY |
| Other old screenshots, closure reports, observations and digests | Historical review evidence | Preserve milestone and scenario context | MEDIUM/HIGH | KEEP_HISTORICAL |

No existing test was deleted. No backend production code, parser, API, adapter, rule, institutional fixture, manifest, workflow or migration implementation changed. No CSS was removed: compressed/shared selectors were not proven exclusively owned by the removed helpers.

## Stale scripts: original role, references and replacement

Both scripts entered the committed tree in the earlier Northstar/PPE checkpoint (`ca0ec9e`); shared workspace extraction (`73f0714`) invalidated their layout assumptions. They are direct local CLIs, not application imports or CI entry points. A bounded root/tools/static scan found no additional equally safe standalone deletion: builders and catalogue_guard remain active; no scripts/ directory or extra shell-script family exists.

| Script | Original/last meaningful role | Concrete stale assumptions | Preserved checks and current command |
|---|---|---|---|
| qa_northstar_browser.py | LoginÃ¢â€ â€™recordÃ¢â€ â€™reportÃ¢â€ â€™logout, desktop/mobile captures for old portal | Dashboard title; #ns-sources container; old evidence wording | Current shared browser suite retains ordinary/unresolved/conflict/entry/award journeys, adds NS-012 history, expanded why/token/registry/help/inspector checks. `python -m pytest -q tests/test_shared_workspace_browser.py` |
| qa_ppe_browser.py | Synthetic PPE positive/missing/negative/conflict/recognition capture rehearsal | .report-hero, requirements tab, #reportSectionContent and old source-directory text | Six scenario inputs, seven rule cards matched to canonical outcomes, keyboard source disclosure, invalid uploadÃ¢â€ â€™empty recovery and evidence/source boundaries at desktop/mobile. `python -m pytest -q tests/test_browser_rehearsal_scenarios.py` |

Current commands were repaired in running guidance, Northstar README and the repository map. Original commands in historical Northstar/PPE review documents remain explicitly marked retired, with a link to current tests; historical narrative was not erased. The current tests use ephemeral local servers, not hard-coded persistent ports. Existing backend projection tests continue to protect semantic expectations; the migrated browser assertions check actual UI fidelity to those projections.

## Artifact families and exact-copy removal

| Directory/family | Purpose / decision |
|---|---|
| artifacts/policy-legibility/after/ | CURRENT REVIEW EVIDENCE; all eight images retained |
| artifacts/shared-workspace/ | HISTORICAL REVIEW EVIDENCE; all eight extraction/before-state images retained |
| artifacts/northstar-legibility/ | HISTORICAL REVIEW EVIDENCE; all before/after/UCT images, digests and observations retained |
| artifacts/northstar-student-interface/ | HISTORICAL REVIEW EVIDENCE mixed with DUPLICATE copies; only twenty same-name source captures removed |
| artifacts/northstar-v1-browser/ | HISTORICAL REVIEW EVIDENCE; retained original integration milestone |
| artifacts/ppe-browser-qa/ | HISTORICAL REVIEW EVIDENCE; every image/observation/report retained |
| docs/redesign-*.png | HISTORICAL REVIEW EVIDENCE; retained |
| tmp/, temp/, cache and logs | LOCAL/TRANSIENT or REGENERABLE TEST OUTPUT; ignored, not evidence |

The [capture map](HYGIENE_SLICE1_DUPLICATE_CAPTURE_MAP.csv) records every removed path, retained same-subject/same-viewport path, SHA-256 and byte size. Each pair matched before deletion. The removed PNGs total 1,570,320 working-file bytes. This is not a Git-history/pack-size savings claim; Git already deduplicates identical blobs. The earlier version and generator are recoverable from Git, and an exact preserved copy removes any need to recreate a historical browser environment just to recover the evidence. No referenced image was removed and no historical state was lost.

Other exact-copy groups were deliberately deferred. No observations JSON or canonical digest was removed merely because identical; equality can be meaningful evidence of unchanged reasoning. No currently tracked transient log/cache was found. Narrow /.pytest_cache/ and /.ruff_cache/ ignore patterns were added; no broad artifact/JSON/image ignore was added. Normal tests do not set CRE_WORKSPACE_SCREENSHOTS. Review capture remains opt-in; temporary visual comparison output was saved outside the repository.

## Compatibility and remaining candidate register for Slice 2

| Item/path | Current classification | Why retained / required next audit | Risk |
|---|---|---|---|
| app.js reportTabs, overviewSection, nextCoursesSection, evidenceSection, renderReportSection; northstar.js nsShow | KEEP_COMPATIBILITY / COMPATIBILITY_ONLY | Explicit retained global/delegating interfaces; decide supported consumers before removal | HIGH |
| app.js requirementCard, requirementsSection, renderStudentReasoningView | KEEP_COMPATIBILITY / COMPATIBILITY_ONLY | Executable PPE tests extract them; migrate contract/tests before deletion | HIGH |
| Hidden Copy/Print controls and handlers | KEEP_COMPATIBILITY | Active bindings; paired HTML/event lifecycle review required | HIGH |
| app.js on Northstar in projection-only mode | KEEP_ACTIVE | Shared helpers and conclusion wrapper; no whole-file removal | HIGH |
| sourceLocator, blockingRequirements, blockersSummary, uniqueLines, confidenceLine, statusDisclosure and adjacent legacy constants/helpers | UNCERTAIN | Some are now isolated/transitively unused; audit full global/call-chain contract instead of expanding removal opportunistically | MEDIUM |
| StudentPortal dashboard/summary wrappers | KEEP_COMPATIBILITY | Tested exported surface alongside active section rendering | MEDIUM/HIGH |
| Old report CSS and Northstar/shared CSS overlap | UNCERTAIN | Cascade and shared selectors; selector-level browser/print coverage required | MEDIUM |
| northstar/presentation.json navigation and unused labels | KEEP_COMPATIBILITY | Still returned by a public API; external key-consumer review required | MEDIUM |
| Remaining exact screenshot copies | KEEP_HISTORICAL | Need path/reference/chronology decisions beyond source-directory copies | MEDIUM |
| Historical build/checksum/config documents | KEEP_HISTORICAL | Audit/merge references and original delivery meaning; no deletion authorized here | MEDIUM |
| All faculty builders, humanities_provenance.py, catalogue_guard.py | KEEP_ACTIVE | Tests/provenance consumers; /mnt/data inputs require separate reproducibility audit | MEDIUM/HIGH |
| engine/extractor.py, isolated Python helpers | UNCERTAIN | CLI/support/provenance consumers not established; outside frontend scope | HIGH |
| Parser shims, Report fields, model defaults and unversioned API aliases | KEEP_COMPATIBILITY | Real import/response consumers; dedicated contract migration required | HIGH |
| Northstar rules, records, adapter, sources, cases and independent tests/fixtures/northstar | KEEP_ACTIVE | Portability/integration and evidence-boundary proof, not disposable synthetic output | HIGH |
| UCT governed data and duplicate source-extraction files | GENERATED_VERSIONED_INTENTIONALLY | Separately manifest-governed paths; source/provenance migration required | HIGH |
| Both GitHub workflows / launchers | KEEP_ACTIVE | Distinct checks and possible external status/deployment consumers; no deletion | MEDIUM/HIGH |

Recommended next bounded slice: **CI dependency and validation-scope declaration**. Explicitly declare Node and document/review Ruff/Bandit target coverage while preserving job names, triggers and the UCT gate. Do not combine this with workflow deletion or full-suite deduplication until required-check consumers are established. It addresses a concrete undeclared dependency and known coverage boundaries without beginning parser/Report migration.

## Validation record

- Frontend syntax: `node --check static/app.js` passed.
- Focused product/interface/policy/PPE checks: **289 passed**.
- Full ordinary pytest suite: **1272 passed in 212.94s (0:03:32)**. Screenshot environment variable unset.
- Both runs compared all tracked and nonignored untracked file hashes before/after: **no unexpected repository changes** (661 files at test time).
- Real Chromium covered UCT empty/manual entry, all workspace sections, Northstar ordinary/unresolved/conflict/entry/award/history cases, and six PPE evidence scenarios, at 1440px and 390px. No browser errors or horizontal overflow assertions failed.
- Visual comparison: all eight settled before/after captures were pixel-identical (UCT/Northstar overview/curriculum, desktop/mobile). Capture output stayed outside the repository. Initial UCT captures varied during smooth scrolling, so the audit repeated captures after scrolling settled.
- Ruff passed for the CI Python scope plus both changed browser test files. No production Python was modified; Bandit was not rerun.
- Governance verification with `--skip-quality --json`: **PASS_WITH_WARNINGS**; manifest matches, source references valid, no semantic/provenance/governance changes. This partial gate does not claim an integrated full quality-gate run. Pytest and Ruff were run separately.
- Preserved `checksum_mismatch_unverified_source_archive`, missing provenance declaration and institutional approval `NOT_ASSESSED`. Technical success does not establish institutional source verification.
- Changed Markdown relative links/image paths and retained duplicate hashes checked before commit; full diff and whitespace reviewed.


## Closure and non-claims

**CLOSED as a bounded hygiene slice, subject to the separately recorded commit/push result.**

**The first repository hygiene pass removed only low-risk stale scripts, transient/generated baggage and frontend helpers proven unused, while preserving compatibility layers, historical evidence and current runtime semantics.**

No local transient files were deleted: the generated-file reduction was twenty exact duplicate captures. The only runtime source edit was deletion of ten proven-unused JavaScript helpers. Useful browser checks moved into pytest; no tests or CSS were deleted.

This does not establish that all legacy code is removed, all tooling is current, workflows are fully cleaned, parser/Report compatibility may be deleted, all historical artifacts are necessary, or repository structure is final. Repository cleanup is not complete.
