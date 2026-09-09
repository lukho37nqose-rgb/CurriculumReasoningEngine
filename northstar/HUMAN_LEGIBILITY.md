> **Historical document**
> This file describes an earlier stage of CRE and is retained for development history. It should not be treated as the current architecture or product specification. See [current architecture](../docs/CURRENT_ARCHITECTURE.md) and the [documentation index](../docs/README.md). Original content below is preserved; counts, screenshots, commands and claims retain their original milestone context.

> **Current guidance:** Use [running and validation](../docs/RUNNING_AND_VALIDATION.md). Earlier launch/QA selectors, unconditional read-only administration claims and complete-report print claims below are not current behavior.

# Northstar Human Legibility Pass v1

## Audit Before Editing

The accepted interface was exercised in Chromium before changes. Its ten-student,
two-viewport captures remain in `artifacts/northstar-legibility/before/`.
The audit found semantic fidelity but unnecessary repetition and technical density.

| Surface | Essential now | Useful on expand | Advisor/debug only | Removed from ordinary view |
| --- | --- | --- | --- | --- |
| Dashboard | Curriculum counts, material conflicts/shortfalls, next step | Full requirements | Exact outcomes and completeness | Zero-count noise; repeated aggregate next actions |
| Curriculum | Requirement title, outcome, plain meaning | Required courses, options, witnesses | Full generated detail | Operators and implementation vocabulary |
| Satisfied cards | Met, interpretation qualification | Confirmed supporting courses | Witness/status mechanics | Repeated raw completion counts |
| Shortfall | Definitive not-met meaning | Why the condition is known | Evidence completeness coordinates | Raw Boolean/status tokens |
| Unresolved | Cannot determine from supplied information | Missing domain where established | Coverage objects | Missing-as-failed implication |
| Conflict | Conflicting information; institution must clarify | Recognition explanation | Conflicting records and raw detail | Evidence IDs in default text |
| Evidence | Received/not supplied by category | Specific completeness statement | Scope IDs and evidence class names | Receipt/coverage terminology as headings |
| Recognition | Institution supplied or must clarify decision | Recognition contribution where explicitly described | Decision IDs and full explanations | Recognition disguised as a local attempt |
| Sources | Human source title | Record/clause or page/section; qualification | Relationship/source IDs and status | Relationship categories as student headings |
| Help | What this does, cannot do, and why it may be uncertain | Source/evidence explanation | Architecture | Adapter/orchestration language |
| Session | Programme, institution, information retrieval | Records ownership | Subject/release/session identity | Subject and release IDs in session disclosure |
| Actions/errors | Safe action, responsible institution, stale-result notice | Affected information category | Diagnostics | Invented offices or mandatory decision claims |
| Mobile | Outcome, meaning, action | Lists and source locators | Inspector | First-screen option lists and technical detail |

All six catalogue courses have names: Ways of Inquiry, Systems Foundations,
Systems Studio, Inquiry Studio, Synthesis and Applied Inquiry. The six curriculum
labels already have human meaning and are retained. Two progression display
titles are shortened from governed condition/consequence descriptions, without
changing their identities or conditions. Exact qualification ORA-K7, external
subject OR-MATH and clearance IDs lack useful governed display names. No names,
offices, equivalences or institutional duties were invented to fill these gaps.

## Final Report

1. Current complexity audit: completed before edits; the table and before captures
   record the findings. Technical richness was useful but occupied the default
   reading path rather than supporting it.
2. Essential-now fields are title, plain state, one-sentence meaning, applicable
   next action and critical institutional qualification.
3. Expandable fields include Why, named courses, required alternatives, supported
   recognition/achievement explanations, source locators and source qualification.
4. Advisor-only fields include original detail, canonical outcome, completeness,
   status, evidence receipts/scopes, source relationships and exact identity.
5. Raw operators, coverage enums, authority tokens, requirement IDs and decision
   IDs are absent from ordinary Northstar pages, including student disclosures.
   They remain in the projection and inspector, not deleted from the system.
6. Dashboard now leads with My curriculum, non-zero meaningful counts and at most
   three curriculum review items. One separately identified institutional handoff
   may appear. Completion, eligibility and formal award remain separate.
7. Shared cards use title/state -> meaning -> critical boundary -> action -> Why
   -> rule source. Lists no longer precede the meaning. Award evidence is not
   given a misleading rule-source accordion.
8. Satisfied: "Based on the represented rules, you meet this requirement."
   Where authority is weaker, institutional confirmation remains visibly qualified.
9. Shortfall: "This requirement is not currently met. CRE has enough information
   to determine this." This does not imply disciplinary or formal standing action.
10. Unresolved: CRE cannot determine the requirement from information supplied
    this session. A missing recognition domain is explained where the existing
    result identifies it; absence is never rewritten as failure.
11. Conflict: supplied information points to different conclusions; CRE will not
    select one automatically. Next action asks Northstar to clarify it.
12. Alternatives: metadata descriptions preserve "every listed course", "one
    course from this group", minimum credits and "at least two" preparation
    options. Confirmed courses are shown without labelling unused options failed.
13. Recognition: explicitly described recognition is attributed to Northstar's
    supplied decision, not to a fabricated local attempt, mark or CRE approval.
    Missing and conflicting recognition retain different explanations.
14. Achievement: a confirmed supporting achievement can be explained as meeting
    the represented requirement. The original value 15 and 0-to-20 description
    remain available on expansion; no percentage or ordering conversion occurs.
15. Prior qualification: an already-satisfied result leaf supports the wording
    "qualifying prior qualification on record". Exact attainment is explicitly
    not equivalence. No title is invented for ORA-K7.
16. NS-011: "The represented entry requirements are met", immediately followed
    by "This is not an admission decision or applicant acceptance."
17. NS-012: the existing duration result is described as historical information,
    with its counting unit retained. It is not called a current enrolment decision
    or a newly satisfied duration policy.
18. NS-013/014/015 retain academic requirements, graduation eligibility and formal
    award as separate concepts. Missing award evidence never means an award
    cannot exist; supplied award evidence is not an event created by CRE.
19. Evidence is now "Information Northstar supplied", with eight plain category
    labels and concise receipt states. Completeness details are collapsed.
20. Coverage becomes "CRE does not know whether the supplied information is
    complete for this question" or a bounded completeness statement for specified
    items. It never expands into a whole-record completeness claim.
21. Sources show registry, Record RX-441 and Clause KAPPA, or document/page/section
    through the same renderer. Relationship tokens remain in the inspector.
22. Rule sources and information-about-the-student remain separate both on cards
    and in navigation. Award evidence references are not described as rule sources.
23. Actions say Provide more information, Recognition needs review or Ask Northstar
    to clarify this information. No-action sections are omitted.
24. SEEK_INSTITUTIONAL_DECISION is deliberately phrased as asking Northstar about
    the institutional decision. That action token alone does not establish a
    mandatory new institutional act. No office routing is invented.
25. Help answers what this does, what it cannot replace, why information may be
    insufficient, and where the linked rules come from.
26. Session context now states records ownership and information retrieved for
    this session. Exact subject and release identity are inspector-only.
27. The fifteen-case selector is unchanged as demo navigation. Case labels and
    expected results are not copied into the signed-in academic explanation.
    A generic demonstration-student label remains because no personal display
    names are held in the accepted records.
28. Inspector now includes the entire advisor view, original recognition detail,
    evidence scopes, entry child results, registration result and source links.
29. Shared components are `StudentLanguage`, `studentConclusionCard` and
    `StudentPortal`. Both UCT and Northstar load the same language/card code.
30. Northstar presentation configuration supplies its short name and two title
    aliases. The presentation endpoint reads course names and generates display
    instructions from unchanged governed curriculum metadata.
31. No institution-specific semantic branch was introduced. Institution URL and
    branding remain edge configuration. Generic code branches on existing result
    kinds/outcomes or display metadata, never Northstar IDs/student cases.
32. Fifteen pre-edit canonical-report digests are compared after the changes.
    Every digest matches. Recognition, alternatives, evidence authority and all
    qualification boundaries also retain their dedicated assertions.
33. Forty-five new tests cover semantic preservation, ordinary text, metadata
    descriptions, named courses, recognition, entry paths, source separation and
    dashboard density. Existing presentation assertions were updated for the new
    wording; no existing test case or reasoning test was removed.
34. Chromium: twenty Northstar login/fetch/report/logout cases (ten students,
    desktop/mobile), plus the existing two domain-failure/keyboard/error tests.
    UCT PPE additionally passes six scenarios at each viewport.
35. Mobile: no horizontal overflow in tested pages, disclosures or inspector.
    Course lists and completeness information begin collapsed. This is a visual
    and technical review, not evidence that real students find it usable.
36. Textual states, native keyboard disclosures, focus movement, labels and skip
    navigation remain intact. No accessibility certification is claimed.
37. UCT PPE retains all seven requirements and document source format. Actual
    browser scenarios cover satisfied, unresolved, shortfall, conflict and both
    recognition forms. Northstar branding is not supplied to those components.
38. Before/after examples are below; raw detail moved, not discarded.
39. Production files: `curriculum_advisor/legibility.py` (metadata-to-copy only),
    `curriculum_advisor/presentation.py` (already-satisfied entry supporting detail),
    `northstar/web.py`, `northstar/presentation.json`, `static/student-language.js`,
    `static/student-portal.js`, `static/app.js`, `static/index.html`,
    `static/northstar.html`, `static/northstar.js`, `static/northstar.css`.
    No engine, governed rule, case, evidence, source relationship or grading file
    was changed by this capability.
40. Full suite: 1,191 passed, including the 45 additions to the accepted 1,146.
    The final combined Northstar/PPE focused run passed 210 checks.
41. Targeted Ruff and changed production Python Bandit pass. The pre-existing
    local Node test harness retains its disclosed low-severity subprocess notices;
    this capability introduces no production subprocess or infrastructure.
42. All four affected JavaScript files pass syntax validation. Component tests
    and real Chromium runs exercise the shared code rather than a mock renderer.
43. UCT release gate: PASS_WITH_WARNINGS. Manifest/requirement sources/tests/Ruff/
    Bandit pass. Source status and provenance remain INCOMPLETE; institutional
    approval remains NOT ASSESSED. No status upgrade was made.
44. Earned claim: Northstar absorbs complex institutional reasoning/evidence
    through the existing contracts while presenting a simpler meaning-first
    student surface; the technical distinctions remain inspectable.
45. Remaining gaps: missing human names for some external/clearance identities,
    no governed office routing, limited structured explanation of the particular
    accepted entry path, and a long full curriculum page despite lower text
    complexity. No claimed universal natural-language explanation engine.
46. Human review: confirm that short labels, hierarchy, action wording and source
    qualifications work for Ms Loqo and students. Supporting-detail translation
    covers explicit existing generated statements only; unfamiliar explanations
    stay in the inspector rather than being assigned an invented meaning.
47. Recommendation: CLOSED for this bounded legibility capability, not real-user
    usability validation, institutional interpretation approval or production use.

## Before / After

| Case | Before | After | Detail retained |
| --- | --- | --- | --- |
| NS-001 | Met plus authority token, code, repeated completion and locator | Meaning first; Why names Ways of Inquiry | Original detail/status/IDs in inspector |
| NS-003 | Unknown completion and coverage terminology | Not enough information yet; safe next step | Bounded completeness inside evidence disclosure |
| NS-006 | Conflict plus technical recognition explanation | Northstar supplied conflicting information; ask it to clarify | Recognition identifiers and explanations in inspector |
| NS-007 | "2 of 2 alternatives" and codes | Complete at least two named preparation options on expand | Full original aggregate detail retained |
| NS-008 | Value plus scheme-related explanation | Entry conditions met; achievement evidence on expand | Unconverted 15 on 0-to-20 scale |
| NS-011 | Generic met, full entry assessment detail | Entry requirements met; not admission | Child evidence statements retained |
| NS-013 | Multiple generic statuses and clearance IDs | Academic requirements complete; graduation not established | Individual clearance states in Why; IDs in inspector |
| NS-014 | Met and missing formal-award assessment | Graduation conditions met; award not established | No award or approval inferred |
| NS-015 | Qualification awarded plus raw source details | Northstar supplied formal-award evidence | Evidence source distinct from rule sources |

## Rehearsal and Reproduction

Open `/northstar`; use `northstar-demo`. Show NS-001, NS-003, NS-006, NS-011,
then NS-014 and NS-015. Begin with ordinary meaning, open Why and a source,
then open the inspector to demonstrate what the infrastructure distinguishes.

Run `python tools/qa_northstar_browser.py --output artifacts/northstar-legibility/after`.
The before captures, canonical digests, after captures and separate UCT browser
observations are retained under `artifacts/northstar-legibility/`.

The earlier Northstar reference/interface closure reports are historical records
and have not been retroactively rewritten by this pass.
