# Northstar Reference Student Interface v1

## Run and Rehearse

Start `python -m uvicorn app:app --host 127.0.0.1 --port 8770`, then open
`http://127.0.0.1:8770/northstar`. Choose a demonstration account; the synthetic
access code is `northstar-demo`. No real student data or production authentication.

Ms Loqo rehearsal: NS-001 (ordinary position), NS-003 (partial evidence), NS-006
(recognition conflict), NS-011 (entry conditions, not admission), NS-014
(graduation eligibility, no award), NS-015 (explicit institutional award).
Use **Switch demo student** between cases. For each case open My Curriculum,
Academic Evidence and Sources. The optional inspector exposes exact outcomes,
completeness, authority and request/release identity. NS-007 demonstrates
alternatives; NS-008 demonstrates achievement 15 on the supplied 0-to-20 scale.

## Product Closure Report

1. Architecture: identity -> fresh Records retrieval -> existing adapter -> CRE
   -> StudentReasoningView -> shared portal renderer. Presentation never evaluates
   rules, grades, recognition, entry, clearance or award decisions.
2. Shared components: existing `studentConclusionCard` in `static/app.js` plus
   pure `StudentPortal` functions for dashboard, curriculum groups, counts,
   evidence, generic source locators/cards and help. UCT retains its existing UI
   and uses the same requirement card. No parallel Northstar assessment model.
3. `northstar/presentation.json` configures names, navigation, achievement display
   and presentation groups by existing requirement identities. The config is not
   passed to evaluation. Ungrouped requirements are always retained.
4. Login identifies the synthetic institution, accounts and access code. The case
   directory is supplied by the server and excludes expected-answer metadata.
5. Dashboard separates five canonical curriculum outcomes, review alerts, next
   actions and the three completion/eligibility/award assessments.
6. Programme text explicitly identifies the currently evaluated workspace, not
   admission, current registration or official candidacy.
7. My Curriculum groups existing foundation/core, studio/options and synthesis
   rules. Entry, progression, completion, eligibility and award remain separate.
8. Shared cards expose the represented title, state, authority, explanation,
   detail, witness where supplied, next action and qualified source disclosure.
   They never infer a result from copy or a detail string.
9. Satisfied requirements show Met and supplied completion witnesses. Entry
   achievement witnesses say Evidence witness, not Confirmed completion.
10. Definitive shortfalls say Not met and are distinct from unavailable evidence.
11. Unresolved says Not enough information yet with neutral styling and safe
    evidence/advisor guidance. Not confirmed does not mean not completed.
12. Conflict has a dedicated text state and styling. Neither renderer nor adapter
    chooses a preferred conflicting record. Unsupported renders Not assessed by
    CRE; no artificial unsupported student case was introduced.
13. Academic Evidence presents eight receipt categories and named coverage scopes
    rather than raw student records. Receipt never claims universal contribution.
14. Records ownership is explicit: Northstar Student Records supplied session
    evidence; CRE does not own the academic record.
15. Sources renders registry/record/clause and document/page/section through the
    same locator/card functions, including relationship and source qualification.
16. Rule-source relationships are in Sources; EVIDENCE_SOURCE relationships are
    in Academic Evidence. Source locations are not misrepresented as quotations.
17. Opaque course IDs, registry references, periods and qualifications remain
    institution-native. No conversion back to UCT suffix or faculty vocabulary.
18. An additive generic receipt observation projects supplied course achievement
    values. NS-008 shows FOUND-X7: 15, labelled with Northstar's 0-to-20 scheme.
    No percentage conversion or grade ordering occurs in the UI.
19. NS-004 recognised completion, NS-005 missing recognition and NS-006 conflict
    retain their canonical differences. No fabricated attempts, marks or credits.
20. NS-011 entry eligibility includes the explicit admission-decision boundary.
21. NS-012 displays the existing explicit-history duration result, with the
    qualification that historical evidence is not a current enrolment decision.
22. NS-013 academic completion is satisfied but eligibility unresolved; NS-014
    eligibility is satisfied but award unresolved; NS-015 reports supplied award
    evidence. Each occupies a separately titled assessment.
23. Subtle session context contains subject, human-readable release and Records
    retrieval statement. No invented timestamp or production freshness guarantee.
24. Switching ends the session and clears displayed results; the next login uses
    the normal fresh Records fetch. Refresh failure labels retained results stale.
25. All fifteen accounts remain reachable via the secondary demo selector.
26. Help explains ownership, uncertainty, rules versus evidence and institutional
    decisions in student language, without a dashboard architecture diagram.
27. Account/session, unusable release/evidence, unavailable record/reasoning and
    network errors receive safe messages, not stack traces or response bodies.
28. A browser test injects an unavailable recognition domain before the real
    adapter. The affected requirement remains unresolved and the UI explains
    unavailable evidence. No fake reasoning response is used for this proof.
29. Chromium desktop 1440 and mobile 390 checks cover navigation, long curriculum
    content, registry disclosures, receipts and inspector with no horizontal
    overflow. Screenshots are under `artifacts/northstar-student-interface`.
30. States have text, disclosures are native keyboard controls, navigation has
    current-page labels, focus is visible, content receives focus on navigation,
    and a skip link is supplied. No WCAG certification claim.
31. The technical inspector is optional and closed in the ordinary flow; no
    production advisor permissions are implied.
32. The rehearsal above demonstrates institution-owned identity, records, rules
    and decisions; CRE returns bounded reasoning, uncertainty and explanation.
33. Generic product changes: `curriculum_advisor/presentation.py` (additive kind,
    achievement observations and entry witnesses), `static/app.js` (shared card
    wording/style), `static/student-portal.js` (shared pure renderers).
34. Institution edge files: `northstar/web.py` adds only presentation-directory
    access; `northstar/presentation.json`, `static/northstar.html`, `.css`, `.js`
    supply branding, navigation and request transport. Zero institution-comparison
    branches introduced in shared product or reasoning code. The explicit
    Northstar URL namespace remains an expected edge, not a semantic branch.
35. Thirty new Node-backed projection/component tests cover all accounts,
    canonical state preservation, grouping fallback, sources, achievements,
    alternatives, receipt separation and config non-interference.
36. Existing seventy Northstar backend tests retain fresh retrieval, isolation,
    recognition, hostile frameworks and builder reproducibility coverage.
37. UCT PPE and Northstar render through the same tested card/source functions.
    Existing alternating-institution backend tests continue to pass. No source,
    record or release leakage is introduced.
38. The updated browser rehearsal passes twenty actual login-to-report cases
    (ten students at each width). Two additional Chromium tests cover domain
    failure, safe service errors and keyboard behavior at both widths.
39. Full suite: **1,146 passed** (accepted baseline 1,114 plus 32 new cases).
40. Targeted Ruff and all three JavaScript syntax checks pass.
41. Bandit on changed production Python is clean. Test/tool scan with assertions
    excluded reports three low-severity subprocess warnings in the Node harness
    (B404/B603/B607): fixed local script, no shell, JSON supplied on stdin. These
    are disclosed test-runner warnings, not production findings.
42. Release verification details are recorded in the artifact closure alongside
    the final run. Existing UCT provenance/source limitations are not upgraded.
43. Earned claim: the same generic reasoning/projection/card contracts support
    this materially non-UCT student portal using institution presentation data
    and edge transport, without institution-specific reasoning branches.
44. Non-claims: production security/SSO, formal admission, current enrolment,
    approval, automatic award, complete institutional policy coverage, source
    verification and accessibility certification. No engine, UCT data, builder
    or manifest change was made in this interface slice.
45. Remaining gaps: source facsimile/document viewers, governed contact routing,
    production advisor access, explicit publication/retrieval timestamps and
    operational identity/privacy review. Source locators remain the represented
    references, not a new quotation/authority claim. No new reasoning feature
    should be added to compensate for one of these product gaps.
46. Recommendation: close the bounded interface after the final technical gate;
    retain the documented source/governance warnings and non-production limits.

## Reproduce Verification

`python -m pytest -q tests/test_northstar_student_interface.py tests/test_northstar_portal_browser.py tests/test_northstar_reference_v1.py tests/test_ppe_pilot_fidelity_repair.py tests/test_ppe_browser_presentation.py`

`python tools/qa_northstar_browser.py`

`python -m pytest -q`

`python -m catalogue_governance --institution uct --release 2026`

The original `artifacts/northstar-v1-browser/CLOSURE.md` describes the accepted
record demonstrator, before this portal. It is deliberately not rewritten.
