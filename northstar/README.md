# Northstar University v1

The current presentation uses [Shared CRE Student Workspace](../docs/SHARED_STUDENT_WORKSPACE_V1.md) and the subsequent [Policy Legibility & Action Language](../docs/CRE_POLICY_LEGIBILITY_V1.md) slice. Earlier [Human Legibility](HUMAN_LEGIBILITY.md) and [Student Interface](STUDENT_INTERFACE.md) reports are historical milestones. See [current architecture](../docs/CURRENT_ARCHITECTURE.md) for ownership and compatibility.

Northstar University is a synthetic reference institution used to test portability, evidence boundaries, institutional separation and the shared student product experience. It uses materially non-UCT semantics and synthetic institutional records, with no real student data. It is an executable reference integration, not production integration or authentication.

CRE does not aim to become a durable student system of record. Authoritative institutional records and formal decisions remain with the institution; Northstar models that boundary with a read-only synthetic records service. Cacisa Systems is the broader product/company context; CRE is the curriculum reasoning engine/product in this repository.

## Run and Rehearse

From the repository root: `python -m uvicorn app:app --host 127.0.0.1 --port 8770`.
Open `/northstar`. Choose NS-001 through NS-015; the shared **demo-only** access
code is `northstar-demo`. Switch demo student ends the previous session.

Ms Loqo demonstration sequence:

1. **NS-001:** log in; watch authentication, current record retrieval and reasoning.
   Show confirmed foundation requirements, and the remaining uncertain completion.
2. **NS-003**, then **NS-002:** compare missing evidence with an explicit complete
   snapshot that supports a negative. Open the evidence receipt scopes.
3. **NS-006:** show the same recognition conflict in student and advisor views.
4. **NS-011:** entry conditions met does not mean admitted.
5. **NS-013**, **NS-014**, **NS-015:** academic completion, graduation eligibility,
   then an explicit recorded award. Eligibility never creates the award event.
6. Open a requirement source: Northstar registry record/clause, not a handbook
   page. Compare the existing UCT PPE view's document/page/section source.

All statuses describe synthetic representations; none implies real institutional
review or approval. Case descriptions in `cases.json` are rehearsal metadata,
never inputs to the adapter or engine.

## Boundaries and Lifetime

| Owner | Contract | Storage/lifetime |
|---|---|---|
| Identity (`identity.py`) | 15 synthetic subjects, constant-time demo-code check | In-memory random-token sessions, 30 minutes; erased on logout/expiry/restart |
| Student Records (`records.py`) | Read-only `fetch(institution, subject)` | Native JSON in `records/students.json`; Northstar owns it |
| Institutional Package (`package.py`, `package/`) | Explicit `northstar / northstar-v1` release | Rules, framework definitions and synthetic registry; no student data |
| Evidence Adapter (`adapter.py`) | Native domain envelope to existing analysis-input fields | Request-local conversion; no result calculation |
| Orchestration (`web.py`) | Authenticated subject -> fetch -> adapter -> existing `analyse_json` | No durable input/report store; no records in identity sessions |
| CRE | Existing typed evidence parsers and `compute_report` | Request-local student/evidence; release/catalogue caches contain package facts only |
| Cacisa | Existing `StudentReasoningView` and shared JS renderer | Current report DOM/browser memory; cleared on switch; no local/session storage |

Sessions contain only subject, institution, launch ID and expiry. Cookies are
HttpOnly, SameSite=Strict, path-scoped and intentionally local-demo/non-TLS.
Login responses contain no academic facts. Analysis cannot override the subject
with a request body. Each analysis, including one in the same session, freshly
reads the records service. No stream, queue, Redis or CRE student database exists.
HTTP responses are no-store. No new logging path prints records or credentials.

Retrieval is one bounded snapshot today; seven named domains are separately
adapted. A missing/malformed optional domain is withheld together with its
coverage, not converted to an empty-complete record. Other domains still work.
An unavailable or wrong-scope whole record returns 503 without a new report.
Domain-specific remote retrieval, authentication and retry policy remain future
integration work. Browser memory and developer tools are not secure deletion.

## Native Records and Mapping

The envelope is `person / issuer / edition / route / domains`, not serialized CRE
objects. `route` is evaluation context, not a historical registration assertion.

| Northstar domain | Native fields | Existing CRE evidence |
|---|---|---|
| academic | modules: module, score, cycle_label, attempt, optional achievement; snapshot | CourseResult, AcademicRecordCoverageEvidence |
| recognition | decisions: reference, learning, local_module, trust; snapshot | CourseCompletionRecognitionEvidence, RecognitionEvidenceCoverage |
| external | subjects: system, subject, result, reference | ExternalSubjectAchievementEvidence |
| qualifications | credentials: system, credential, reference | PriorQualificationEvidence |
| registration | episodes: block, route, state; snapshot | RegistrationHistoryEvidence and coverage |
| clearance | decisions: gate, decision, reference | GraduationClearanceEvidence |
| award | conferments: qualification, decision, reference | QualificationAwardEvidence |

There is no fabricated local result for EXT-77 -> CORE-Q2 recognition. Recognition
does not add numeric credit, mark, attempted course or award weighting. No global
equivalence exists. Requirement-targeted recognition and attempt-coverage inputs
remain supported by CRE but are deliberately not ingested by this v1 adapter.
The shared receipt lists separate domains: received does not mean applicable or
used. Identity/release mismatch in a native decision withholds that domain.
An explicitly authority-qualified local result is also withheld: CourseResult
has no per-attempt authority field, so v1 must not erase that qualifier.

## Fifteen Proof Cases

| Subject | Native case | Canonical/UI distinction |
|---|---|---|
| NS-001 | Foundation/core/studio passes | Ordinary progression, completion still unresolved |
| NS-002 | Foundation only; complete result and recognition snapshots | Core not satisfied, not mere absence |
| NS-003 | Foundation only; coverage unknown | Core unresolved |
| NS-004 | EXT-77 recognition for CORE-Q2 | Core satisfied; no local CORE-Q2 attempt or credit |
| NS-005 | Complete result snapshot; unknown recognition coverage | Core unresolved |
| NS-006 | Conflicting recognition evidence | Core conflict in canonical/student/advisor projections |
| NS-007 | Foundation and studio witnesses | Nested preparation choices satisfied despite unused unknown route |
| NS-008 | Achievement 15 on a 0-20 scale | Entry leaf satisfied, independently of the ordinary pass mark |
| NS-009 | ORION-CERT / OR-MATH achievement 8 | External leaf contributes without a synthetic course code |
| NS-010 | Exact ORA-K7 credential | Qualification-held leaf, no taxonomy inference |
| NS-011 | Qualifying internal achievement | Entry satisfied, admission not represented |
| NS-012 | Active/interrupted/active explicit episodes | Existing duration metric: two active cycles, not three result years |
| NS-013 | Every academic requirement complete; no clearances | Completion satisfied; eligibility unresolved |
| NS-014 | Academic complete and two clearances | Eligibility satisfied; formal award unresolved |
| NS-015 | Recognition, achievement, external/credential/history, clearances, conferment | Compound complete/eligible/awarded case; award only from explicit event |

All evidence/policy authority remains visibly bounded. In particular the synthetic
policies are unverified even where a positive completion witness is sufficient.
No scenario metadata selects a conclusion in runtime or browser code.

## Hostile Package and Sources

The School of Systems uses exact opaque codes and independent credits/load.
Ordinary pass is 60%; achievement comparison is a separate 0-20 scheme. Periods
P-Z, P-A and P-M form CYCLE-Q, followed by P-B/CYCLE-R and P-X/CYCLE-S. The package,
not lexical order, owns that relationship. No result year is invented.

Six curriculum requirements reuse exact/all-required/alternative/credit-pool and
choose-n semantics. Prerequisites use exact, AND, OR and shallow nested OR+AND.
Progression uses cumulative failed-attempt advisory and foundation completion
ineligibility. Distinction uses the existing 82 weighted-average / 30 earned-credit
policy. Entry combines internal achievement, external subject and exact credential
witnesses. Completion, clearances and award remain separate.

`package/registry.json` is the synthetic non-document source. The six requirement
relationships link `NS-REGISTRY` to RX identifiers and clause KAPPA, all unverified.
`GET /api/northstar/rules/RX-441` exposes a read-only registry entry. The same
generic source rendering handles UCT page/section and Northstar record/clause.
No historical UCT source lineage, manifest or interpretation was changed.

Rebuild via `python tools/build_northstar_reference.py`. This intentionally resets
the synthetic records as well as package files. Do not use it on live records.
Reproducibility tests compare all five generated files byte-for-byte. v1 is a
synthetic package, not a production governed institutional release approval.

## Presentation and Remaining Boundaries

Shared projection changes expose entry eligibility, full receipt domains,
clearance children and explicit award-evidence wording. Legacy Boolean summaries
remain available in a labelled disclosure, not among canonical assessments.
Triggered policy conditions are labelled as triggered conditions, not as completed
curriculum requirements. The student portal uses `StudentWorkspace` for shared composition/navigation, `StudentPortal` for section rendering, and `StudentLanguage` through the existing `studentConclusionCard` wrapper. UCT route initialization is disabled when its helpers are loaded in projection-only mode.

No `engine/` file was changed for this capability. `app.py` only mounts the demo
orchestrator. No UCT records, rules, builders or manifests were changed.

The annual progression-ratio path still uses legacy annual scope rather than the
opaque-cycle scheme. v1 therefore uses the supported cumulative failed metric;
it does not fabricate years or claim that annual consumer migration is complete.
Registration duration is shown through the existing explicit-history metric in
My information, not a new progression consequence or maximum-years rule.
Legacy report fields still contain calendar/NQF/semester terminology. They are
labelled compatibility output, not Northstar canonical requirements.

Formal Admission, Course Registration/Co-requisites and Qualification Taxonomy
remain source-blocked. No production SSO, advisor authorisation, consent, SIS
connector, evidence revocation, telemetry policy or deletion guarantee is supplied.
The shared workspace extends this accepted record boundary. Current sections are Overview, My Curriculum, My information, Sources, Courses to explore where supported, and Help / Limits, with supported copy/print. See the [documentation index](../docs/README.md) for current product docs and historical review records.

## Verification

`tests/test_northstar_reference_v1.py` exercises all fifteen logins and canonical
outcomes, fresh source reads, metadata independence, domain failure, scope, source
resolution, isolation, and shared rendering. Current browser regression entry: `python -m pytest -q tests/test_shared_workspace_browser.py`, run from the repository root with development dependencies and Chromium installed. See [running and validation](../docs/RUNNING_AND_VALIDATION.md). The older `tools/qa_northstar_browser.py` has superseded selectors and is retained for later tooling review, not recommended as a current command.

The original v1 validation counts and governance limitations are historical evidence recorded in
`artifacts/northstar-v1-browser/CLOSURE.md` after the final verification pass.
