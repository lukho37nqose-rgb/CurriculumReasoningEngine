# Current CRE architecture

Current documentation for the implementation accepted at `73f07140765cc0d9a0db36b4fbcd1296cbb43c37`, clarified by Current Documentation & Historical Labelling v1. This is a map of the existing modular monolith, not a planned package relocation. [Documentation hierarchy](README.md).

## Product and evidence flow

```text
UCT route + upload/manual/empty entry    Northstar identity + synthetic records
                |                                  |
                |                         Northstar evidence adapter
                +------------------+---------------+
                                   ↓
              app.py analysis + selected InstitutionRelease
                                   ↓
             scoped catalogue + typed evidence + compute_report
                                   ↓
                                 Report
                                   ↓
           StudentReasoningView / advisor_reasoning_view
                                   ↓
            StudentWorkspace → StudentPortal → StudentLanguage
```

InstitutionRelease binds institution/release metadata and supported framework/adapter contracts. UCT's public entry still uses faculty/programme keys; Northstar selects its synthetic release through its own orchestration. This is not a claim that every compatibility consumer has been made institution-neutral.

Northstar's identity service identifies a demo subject. Its record service supplies synthetic native records, and its adapter converts supported evidence domains without calculating academic outcomes. `northstar/web.py` calls the existing JSON analysis boundary. UCT supplies uploaded/user-entered information; no live UCT SIS fetch exists.

## Physical repository map

| Path | Current responsibility |
|---|---|
| `app.py` | FastAPI entry points, typed input handling, catalogue/release selection, analysis, serialization, goals/simulation, readiness and administration |
| `engine/` | Evidence models, catalogue/scoping, curriculum evaluation, recognition, entry/progression/completion/clearance/award assessments, reasoning, planning and simulation; compatibility paths also remain |
| `curriculum_reasoning_engine/institutions/` | Release registry and institutional grading, coding, credit/load, achievement, period, routing and provenance contracts/implementations |
| `curriculum_reasoning_engine/adapters/transcripts/` | Canonical UCT text/PDF transcript adapter; parser compatibility delegates here |
| `curriculum_advisor/` | Product metadata, student/advisor projections, legibility metadata and guarded administration overlays |
| `northstar/` | Executable synthetic institution: identity, records, adapter, package and presentation metadata |
| `static/` | UCT and Northstar acquisition shells, shared student workspace/components, administration UI |
| `data/uct_*`, `governance/`, `catalogue_governance/` | UCT represented packages and extraction provenance, manifests/schemas and technical release verification |
| `tests/`, `tools/` | Regression contracts, package builders and integrity tooling; browser rehearsals live in pytest |

## Truth and presentation ownership

`engine/rule_engine.py` defines `Report` and `compute_report`. The report holds canonical assessments alongside older report fields. `curriculum_advisor/presentation.py` projects student/advisor explanations; `app.py` attaches them to serialized reports. Product language does not replace the underlying institutional rule or upgrade its authority.

`static/student-workspace.js` owns shared account layout, section navigation/history, composition, course filtering and copy/print. `student-portal.js` supplies curriculum/evidence/source/help/sequence rendering; `student-language.js` supplies outcome/action wording and disclosures. `studentConclusionCard` is an existing wrapper in `app.js`.

UCT's `static/app.js` retains faculty/programme selection and upload/manual/empty entry. `static/northstar.js` retains demo login, retrieval, refresh and switching. Northstar loads `app.js` in `data-projection-only` mode for shared helpers while suppressing UCT initialization. The two shells are not two independent reasoning implementations.

The advisor/technical inspector is an explanation surface, not a production advisor permission system. Academic completion, graduation eligibility, formal award, entry and registration remain distinct questions. Course exploration displays represented curriculum/prerequisite results, not live places, timetables or registration approval.

## Surfaces and API families

| Surface | Current entry points |
|---|---|
| UCT | `/`, `/faculty/{faculty_key}`, `/api/v1/analyse`, `/api/v1/analyse/text`, `/api/v1/analyse/json` |
| Northstar | `/northstar`; `/api/northstar/accounts`, `/presentation`, `/rules/{record_id}`, `/login`, `/logout`, `/analyse` under the `/api/northstar` prefix |
| Administration | `/admin`, `/api/v1/admin/*`, `/api/v1/governance/status` |
| Planning and dependencies | `/api/v1/simulate/*`, `/api/v1/goals`, `/api/v1/dependencies*`, with retained legacy aliases |
| Operations | `/health`, `/ready`, versioned equivalents, `/docs`; static files under `/static` |

Administration is read-only by default. Explicitly enabled/token-guarded Tier 1 edits can append metadata audit events and apply runtime overlays without editing published catalogue JSON. This does not implement institutional publication/approval authority. Configuration details belong in [running and validation](RUNNING_AND_VALIDATION.md).

## Compatibility-only interfaces: retain deliberately

| Component | Why it remains |
|---|---|
| `engine/parser.py` | Legacy parser import surface; delegates to UCTTranscriptAdapter and has explicit parity tests |
| Legacy Report fields, Boolean requirement summaries and graduation status | Goals/simulation and compatibility clients still consume them; they do not replace canonical student assessments |
| `engine/utils.py` route/major/course-load helpers and model grading defaults | Tested compatibility contracts and some production fallbacks remain |
| Unversioned API aliases | Existing routes for clients; removal requires a separate compatibility decision |
| Frontend report wrappers and hidden copy/print nodes | Tests extract wrappers and initialization still binds hidden controls; remove neither in isolation |
| Northstar's projection-only `app.js` load | Shared utility/conclusion-wrapper dependency remains |
| `tests/fixtures/northstar/` | Independent synthetic regression package used by entry, completion, periods, registration and achievement tests; not a spare copy of runtime Northstar |

These are legacy interfaces retained for compatibility, not a declaration of deprecation or planned removal. Similar names (`reasoner.py`, `reasoning.py`, `knowledge_graph.py`) do not establish duplication.

## Source and record boundaries

Authoritative institutional records and formal decisions remain with the institution. CRE does not aim to become a durable student system of record. The Northstar demonstration keeps synthetic records outside the reasoning engine; sessions/reports are not evidence of a production SIS or retention/deletion system.

UCT catalogue/source files and Northstar generated reference data have distinct provenance/rebuild contracts. Even byte-identical source-extraction and catalogue files may have separately governed paths. See [current limitations and governance](CURRENT_LIMITATIONS.md); do not treat top-level historical checksum lists as today's release gate.

The older [product architecture plan](architecture/PRODUCT_ARCHITECTURE.md) and [extraction plan](migration/PRODUCT_EXTRACTION_PLAN.md) are retained history. Their target directory trees are not the physical layout or instructions for this slice.
