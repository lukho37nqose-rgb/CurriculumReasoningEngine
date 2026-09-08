# Shared CRE Student Workspace v1

Technical closure: CLOSED. Verified 8 September 2026.

This is a bounded product extraction, not institutional approval. The existing
Report and StudentReasoningView remain the truth owners. No Python production
code, institutional rules, demo records, source relationships, source status,
builders or manifests were changed.

## Ownership

```text
UCT entry: faculty / programme / upload / manual / empty
Northstar entry: demo identity / record retrieval / student switching
                         |
             existing Report + StudentReasoningView
                         |
             StudentWorkspace + StudentPortal + StudentLanguage
                         |
         Overview / Curriculum / Evidence / Sources / Explore / Help
```

The shared workspace receives the report, presentation configuration and optional
session context. It does not fetch institutional records, evaluate requirements,
derive academic outcomes, grant recognition or infer institutional decisions.

## Completion Report

| # | Requested finding | Result |
|---|---|---|
| 1 | Pre-extraction UCT | `app.js` owned entry and report composition. The overview repeated canonical cards, legacy risk/distinction output, summary figures and requirement rows. |
| 2 | Pre-extraction Northstar | A separate `nsShow` selected StudentPortal surfaces. Cards were already shared, but dashboard navigation/composition and course exploration were not. |
| 3 | Shared boundary | `StudentWorkspace.mount` owns the account header, navigation, section composition, search, copy/print and browser section history. |
| 4 | Shell boundary | Entry, identity, acquisition, refresh and student switching remain in the respective shells. |
| 5 | Workspace model | Existing Report/StudentReasoningView plus lightweight presentation configuration; no parallel Northstar response model or backend schema. |
| 6 | Navigation | Overview, My Curriculum, Evidence, Sources, capability-gated Next courses, Help / Limits. Northstar supplies its sidebar as the shared navigation host. |
| 7 | Current position | Counts of represented curriculum outcomes and existing credit totals, never an invented completion percentage. Programme context explicitly does not prove admission or current registration. |
| 8 | Attention | Up to three canonical issues, ordered for scanning. Full assessments remain in Curriculum. Unresolved, conflict, unsupported and definitive shortfall retain distinct wording/styles. |
| 9 | Next action | Existing action vocabulary translated by StudentLanguage. No invented office routing or institutional decision. |
| 10 | Curriculum | Each canonical conclusion appears once in the full curriculum collection. Existing configured groups are retained; ungrouped requirements remain visible rather than being guessed into new categories. |
| 11 | Evidence | Existing receipt categories, named coverage scopes, achievement observations and optional registration-duration context. Receipt is separate from use by a particular conclusion. |
| 12 | Evidence origin | `evidence_origin`: institution_supplied, demo_record, user_supplied, manual_entry, synthetic, or neutral unknown. UCT upload/manual/empty flows assign acquisition context; Northstar assigns demo_record. This is presentation context, not authority. |
| 13 | Sources | Shared document/page/section and registry/record/clause rendering. Direct, inherited and package-level relationship labels remain distinct. Existing status language is displayed. Unlinked directory entries are separately disclosed. |
| 14 | Source/evidence separation | EVIDENCE_SOURCE references remain under Evidence/Why, not rule sources. Rule disclosures and source directory answer a different question from the evidence receipt. |
| 15 | Exploration | Shared search over existing eligible_courses, including opaque codes and supplied offering metadata. No course-code parsing, grading or prerequisite evaluation in the renderer. |
| 16 | Capabilities | Only course_exploration and export flags are introduced. UCT derives exploration availability from the existing report collection; Northstar enables its accepted report capability. |
| 17 | Print/export | One visible control set. Copy exports canonical conclusions with verification qualifiers and origin limits. Print is a view of the current section, not a certified or exhaustive academic record. Both explicitly disclaim official-record status. |
| 18 | UCT compatibility | Faculty/programme selection, manual marks, empty exploration, upload endpoint and analysis panel remain. Old report helpers delegate to the shared workspace. |
| 19 | Northstar compatibility | Same demo login, normal record retrieval, refresh, domain-failure handling and 15-account switcher. Switching destroys the old history listener and clears displayed student content. |
| 20 | Requirement card | StudentLanguage.card, reached through the existing generic studentConclusionCard wrapper. No separate institution-specific canonical renderer. |
| 21 | Status rendering | Existing outcomes are displayed, not recalculated. Unused alternatives are not created as failed cards. Policy consequence-established state continues to distinguish progression conditions from their consequences. |
| 22 | Completion boundaries | Academic requirements, graduation eligibility and formal award remain three separate sections/assessments. NS-013/014/015 explicitly demonstrate the separation. |
| 23 | Help | Shared student-language explanation plus supplied projection limitations. Origin-aware copy; demonstration notice only for demo/synthetic contexts. |
| 24 | Errors | Shared safe status-to-message mapping; shells retain transport and retry responsibilities. Raw response JSON/diagnostics are not exposed as student errors. Service failure does not create an academic failure. |
| 25 | Inspector | Collapsed advisor/technical information remains. UCT legacy majors/distinction/risk values are available there, not promoted into canonical overview judgments. Northstar retains its existing demo inspector. |
| 26 | Branding | Institution names, existing labels/course titles/instructions/groups and shell styling remain presentation inputs. No theme platform or policy-affecting configuration. |
| 27 | Design primitives | Shared green account panel, restrained gold accents, serif headings, three-question layout, disclosures, status accents and responsive grids. The UCT cream shell and Northstar neutral portal shell remain distinct. |
| 28 | Remaining branches | Existing UCT faculty grouping in the entry wizard remains. Northstar endpoints, login and records wording remain in its shell. No institution-ID or student-ID semantic branch was added to shared product modules. |
| 29 | Unsafe duplication removed | The old UCT overview/risk/distinction/requirement duplicate composition and legacy graduation-status copy export were removed. Northstar's separate dashboard now delegates. Origin assumptions in recognition/prior-qualification copy were made neutral. |
| 30 | UCT crowding | The overview no longer starts with every conclusion and then repeats academic-position/risk/requirements. The complete collection belongs in My Curriculum. Duplicate Copy/Print controls are hidden compatibility elements only. |
| 31 | Northstar hierarchy | The same three questions, account header, actions and exploration now organise the portal. Duplicate programme-context wording above the account header was removed. |
| 32 | UCT origin repair | Empty/manual reports say information you supplied; uploaded records say the same without claiming that UCT directly supplied them. Unknown origin remains neutral. |
| 33 | UCT before/after | Historical README report and prior PPE screenshots versus shared overview/curriculum screenshots linked below. The original navigation intent is retained without restoring old Boolean certainty. |
| 34 | Northstar before/after | Prior legibility-pass portal screenshot versus the shared account/three-question overview below. Login and record ownership remain Northstar-specific. |
| 35 | Desktop browser QA | Real Chromium at 1440px: nine Northstar students, UCT PPE empty/manual, all sections, source-to-requirement focus, back/forward and export. No page errors in tested journeys. |
| 36 | Mobile QA | Same journeys at 390px, disclosure/search/receipt checks, no horizontal document overflow. Final screenshots reviewed. No accessibility certification claimed. |
| 37 | Generic proof | The same components render PPE document/page sources and Northstar registry sources, opaque codes and the non-percentage achievement observation. Configuration mutation tests leave report data unchanged. |
| 38 | Focused validation | 252 tests passed across shared workspace, browser journeys, PPE fidelity, Northstar reference/legibility/interface and product regressions. |
| 39 | Full suite | 1,228 passed in 148.27 seconds. Previous baseline 1,192; 36 new parameterised cases. No existing semantic test cases were deleted. |
| 40 | Frontend validation | New suite includes 30 executable projection/component cases and six browser cases that exercise multiple students/sections. Existing two domain-failure browser cases also pass. JS syntax, copy clipboard output and print-media boundary checked. |
| 41 | Ruff/Bandit | Ruff passed on the standard application/governance targets and all changed/new Python tests. Bandit passed on app.py, curriculum_advisor and engine. No Python production files changed. |
| 42 | Release gate | UCT gate exit 0, PASS_WITH_WARNINGS. Manifest and source references pass; full tests, Ruff and Bandit pass. Existing archive-status and missing-declaration warnings remain. No unexplained drift, semantic changes or governance changes. |
| 43 | Production files | Nine frontend files only, listed below. |
| 44 | New generic files | `static/student-workspace.js` and `static/student-workspace.css`. |
| 45 | UCT shell changes | `static/app.js`, `static/index.html`: delegation, acquisition-origin context, generic safe errors and shared resources; entry behaviour preserved. |
| 46 | Northstar shell changes | `static/northstar.js`, `.html`, `.css`: delegation, shared navigation host/errors/resources, listener cleanup and removal/extraction of duplicated presentation. |
| 47 | New claim | The same student workspace supports materially different institutions through existing reasoning/product projections, with institution-specific entry, evidence acquisition, labels and supported capabilities. |
| 48 | Non-claims | No production authentication, SIS, persistent student storage, registration promise, admission, institutional approval, new qualification award, source-status upgrade or new academic semantics. |
| 49 | Remaining gaps | See bounded limitations below. |
| 50 | Recommendation | CLOSED as the bounded shared frontend capability. This does not close institutional source review, production integration or missing canonical academic semantics. |

## Changed Files

- New: `static/student-workspace.js`, `static/student-workspace.css`.
- Shared existing presentation: `static/student-language.js`, `static/student-portal.js`.
- UCT shell: `static/app.js`, `static/index.html`.
- Northstar shell: `static/northstar.js`, `static/northstar.html`, `static/northstar.css`.
- New tests: `tests/test_shared_student_workspace.py`, `tests/test_shared_workspace_browser.py`.
- Adapted guards: Northstar human-legibility/reference/interface tests and PPE browser/fidelity tests.
- This report and eight generated review screenshots under `artifacts/shared-workspace`.

## Visual Comparison

These are illustrative screenshots, not identical student/evidence comparisons.
The README baseline is an older design, not a capture of the immediate pre-change
commit. Existing legibility/PPE artifacts supply the more recent reference.

| View | Earlier reference | Shared workspace |
|---|---|---|
| UCT report | [README report](redesign-report.png) | [Overview desktop](../artifacts/shared-workspace/uct-overview-1440.png) |
| UCT PPE | [Prior PPE unresolved](../artifacts/northstar-legibility/uct/unresolved-1440-ppe_eco3025.png) | [Manual PPE curriculum](../artifacts/shared-workspace/uct-curriculum-1440.png) |
| Northstar | [Prior legibility overview](../artifacts/northstar-legibility/after/desktop-NS-001.png) | [Shared overview](../artifacts/shared-workspace/northstar-overview-1440.png) |
| UCT mobile | [Prior PPE mobile](../artifacts/northstar-legibility/uct/unresolved-390-ppe_eco3025.png) | [Shared overview](../artifacts/shared-workspace/uct-overview-390.png) |
| Northstar mobile | [Prior portal mobile](../artifacts/northstar-legibility/after/mobile-NS-001.png) | [Shared overview](../artifacts/shared-workspace/northstar-overview-390.png) |

## Reproduce

```powershell
python -m pytest -q tests/test_shared_student_workspace.py tests/test_shared_workspace_browser.py
python -m pytest -q
python -m catalogue_governance --institution uct --release uct-2026-uploaded-baseline --json
```

Set `CRE_WORKSPACE_SCREENSHOTS=artifacts/shared-workspace` when running the browser
suite to regenerate screenshots. Tests use an ephemeral local server and Chromium;
they do not depend on the development server or on saved student sessions.

The gate preserves `checksum_mismatch_unverified_source_archive` and
`declaration not supplied` warnings. Its technical pass does not establish source
fidelity or institutional authorisation.

## Bounded Limitations

- UCT PPE's existing "Six third-year PPE courses in total" projection returns a
  definitive shortfall for the tested empty/manual records while individual
  course requirements remain unresolved. This slice displays that supplied
  canonical result; it neither fixes nor hides it with frontend reasoning.
  Review that aggregate contract separately before making broader fidelity claims.
- When an academic-completion or graduation assessment is absent, the sequence
  says it is not assessed. The UI does not manufacture an assessment from credits.
- Existing detail-template translation remains in StudentLanguage; richer generic
  explanation metadata could eventually reduce that presentation dependency.
- Some legacy report fields and unused compatibility helper definitions remain;
  they do not drive shared canonical outcome cards or copied conclusions.
- Programme group metadata is not inferred from course codes. UCT requirements
  without configured product grouping use the visible ungrouped collection.
- Section history is session-local. Refreshing does not restore a persisted
  academic record; evidence must enter through the normal shell again.
- Printing concerns the current view, not a new full-report document generator.
- Production authentication, institutional clearance/decision workflows, live
  registration availability and source review remain outside this slice.

No commit or push was made for this task.
