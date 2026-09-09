> **Accepted milestone record**
> This is bounded implementation/review evidence, not a rolling test count. The two presentation slices were subsequently committed at `73f07140765cc0d9a0db36b4fbcd1296cbb43c37`; original no-commit statements refer to the original task. See the [documentation index](README.md) for current authority and limitations.

# CRE Policy Legibility & Action Language v1

## Scope and Grammar

Presentation only, on the accepted Shared Student Workspace baseline. Personalise
the application of policy, not the policy. The student is the subject of a
position statement; the institution is the subject of an institutional action;
CRE is the subject of an information/capability limit; the rule remains public.
No canonical outcome, action token, evidence, rule, source relationship, locator,
authority, ingestion contract or release manifest changed.

## Copy Audit

| Surface | Classification | Finding and treatment |
| --- | --- | --- |
| Overview | Over-qualified/system-like | Removed repeated "represented" from requirement counts and the account heading. Counts still have no invented percentage denominator. |
| Met cards | Policy-like | Lead with "You meet this requirement." Scope and authority remain inspectable. |
| Shortfall cards | Passive/policy-like | "You do not meet this requirement yet" is distinct from uncertainty. No new shortfall arithmetic. |
| Unresolved cards | System-like/too vague | Name CRE's information limit directly. Do not invent the missing course from a title. |
| Conflicts | Good but wordy | Keep the explicit conflict label and refusal to choose evidence automatically. |
| Actions | Too vague | Existing tokens now provide what needs to happen, what the student can do, and a question to ask where justified. |
| Rule instructions | Good but misplaced | Move existing supplied instructions out of personal evidence explanation into "What the rule requires". |
| Sources | Good but misplaced | "Where this comes from" leads to the same public locator and qualified relationship. |
| Information receipt | System-like | "Information available to CRE" avoids claiming every received item was used. |
| Recognition | Potentially misleading shorthand | Replace "Confirmed completion" witness heading with "Information supporting this result relates to". Recognition is not a new course attempt or mark. |
| Entry | Over-qualified/passive | Direct personal statement; immediate admission/acceptance boundary retained. |
| Completion | Over-qualified | Requirements "assessed here" instead of "represented academic requirements". |
| Graduation/award | Necessary qualification | Keep eligibility separate from approval and award. Missing award evidence does not establish absence. |
| Registration history | Necessary vocabulary | Keep historical duration and current-enrolment distinction; no new history interpretation. |
| Explore | Too certain/system-like | "Courses to explore"; live registration, timetable, places, permission and concurrency remain unconfirmed. |
| Help | System-like | Explain how information relates to curriculum; Sources and My information answer different questions. |
| UCT entry/wizard | Ambiguous pronouns | Replace we/our/us with CRE or direct instructions; programme selection is not admission/registration. |
| Errors | Already bounded | Retain safe retry/input guidance and no-new-conclusion language. No stack traces. |
| Export | Necessary qualification | Reuses updated shared meanings; retains not-official-record, origin and verification limits. |
| Mobile | Good hierarchy, long collection | Outcome and action precede collapsed explanations; full curriculum remains a long page, not a shortened or filtered truth set. |

The pronoun search found no ambiguous we/our/us in the revised ordinary shared
copy or UCT entry text. Technical inspector content is not rewritten. Existing
backend explanations/limitations and institution-owned terminology are not edited.
"Represented" remains where it limits entry/graduation/course claims. "Supplied"
remains where origin or receipt scope matters, not as a universal sentence prefix.

## Before and After

| Before | After | Why it helps | Meaning preserved |
| --- | --- | --- | --- |
| Based on the represented rules, you meet this requirement. | You meet this requirement. | Position first. | Same satisfied outcome; shared disclaimer and case qualification remain. |
| This requirement is not currently met. CRE has enough information to determine this. | You do not meet this requirement yet. CRE has enough information to establish this shortfall. | Direct, non-punitive subject. | Definitive negative, not missing evidence. |
| CRE cannot determine this requirement from the demonstration information Northstar supplied for this session. | CRE does not have enough information to decide this yet. | Removes repeated receipt preamble. | Unresolved remains unresolved; origin is on My information. |
| The supplied information points to different conclusions... | Two pieces of information point to different conclusions, so CRE will not choose one automatically. | Explains the practical limit. | No conflict resolution invented. |
| Recognition needs review. | A recognition decision needs review. Ask Northstar to check whether previous study counts toward this requirement. | Names what is reviewed and who can act. | Existing REVIEW_RECOGNITION token only. |
| Ask Northstar about the institutional decision. | Northstar still needs to decide this. | Names responsibility. | SEEK_INSTITUTIONAL_DECISION does not become a new canonical state. |
| Not assessed by CRE. | CRE cannot assess this question. | Distinguishes capability from missing data. | Unsupported does not become not met. |
| The represented entry requirements are met. | You meet the represented entry requirements. | Student-centred. | Immediate "not an admission decision or applicant acceptance". |
| Your represented academic requirements are complete. | Your academic requirements assessed here are complete. | More natural scope qualifier. | No graduation inference. |
| Northstar's represented graduation conditions are not yet established. | CRE cannot yet tell whether all required graduation conditions are met. | Explains uncertainty rather than suggesting refusal. | No false/award inference. |
| A formal award has not been established from the information supplied. | There is not enough information here to establish a formal award. This does not mean no award exists. | Names the evidence limit. | Missing evidence is not a negative award decision. |
| Information supplied for this session. | Information available to CRE. | Receipt, not universal use. | Category and coverage data unchanged. |
| Provide more information. | More information is needed to answer this question. Check the information available here against your records. | A bounded next step, not an unspecified upload demand. | No invented missing item or route. |
| Where is the rule? | Where this comes from. | Natural traceability question. | Same source title, locator and direct/inherited/package relationship. |
| Confirmed completion (including recognised completion where supplied). | Information supporting this result relates to... A recognition decision is not a course attempt. | Avoids conflating recognition with taking a course. | Existing used-course identifiers only. |
| Next courses. | Courses to explore. | Avoids an implicit registration promise. | Same eligible-course collection; no new eligibility calculation. |
| 5 represented requirements met. | 5 requirements met. | Less system vocabulary. | Same canonical counts, explicit no-percentage qualifier. |
| Your programme sets what we'll check. | Your programme sets which rules CRE checks. | Removes ambiguous speaker. | Current evaluation context, not admission/history. |

## Shared Implementation and Boundaries

- `static/student-language.js`: central meanings, labels, actionDetail, receiptIntro,
  evidence wording and rule/source disclosures. action() remains the summary
  accessor. Existing tokens are not changed. Questions never invent an office,
  required procedure, deadline, future course or approval.
- `static/student-portal.js`: shared receipt/help/curriculum headings. Rule summary
  is separate from evidence explanation. Information origin does not establish
  authority, and receipt does not establish use by every conclusion.
- `static/student-workspace.js`: shared navigation, overview and source/exploration
  wording. Export consumes the same meanings. No new response model or fetch path.
- `static/student-workspace.css`: explicit left alignment and bounded action text.
  Northstar keeps its sidebar; UCT keeps its existing shell and left-aligned
  responsive workspace navigation. This is not a sidebar or design-system rewrite.
- `static/index.html` and one message in `static/app.js`: UCT entry-copy pronouns
  only in this slice. Northstar-specific files and configuration were not edited
  for this slice; their existing uncommitted Shared Workspace changes remain.

No institution-specific semantic branch was introduced. Tests substitute UCT,
Northstar and Another University as presentation subjects. Identical result
objects are rendered without mutation. There are no backend/engine/data changes.

Met requirements normally have no action. A canonical action, when present, is
honoured rather than overridden from the outcome. Unknown next steps get a
clarification statement, not a fabricated procedure. An institutional action
does not erase the underlying unresolved/other result label.

Progression condition `not_satisfied` is still "No issue identified by this rule",
not a student shortfall. Established review/ineligibility/advisory consequences
remain distinct; none means exclusion. Prior-qualification wording retains exact
match, not general equivalence. Positive award evidence says CRE did not confer
the qualification. Non-percentage achievement values are displayed unchanged.

## Disclosure and Qualifications

Visible: title, state, personal meaning, critical admission/completion/graduation/
formal-act boundary, existing unconfirmed-interpretation qualification, and action
where supplied. Expanded: What to ask, Why?, What the rule requires, Where this
comes from. Critical institutional limits intentionally remain visible rather
than being moved into an optional Limits disclosure.

General scope is carried by the curriculum header and Help. Case-specific
qualifications remain: simplification must not turn an unverified answer into
institutional confirmation. Source precision remains in expanded material.

There is no safe generic missing-course/shortfall-count field in the existing
student projection. No count or missing identifier is reconstructed from labels,
course-code patterns or group position. Northstar's existing instruction metadata
supplies safe descriptions. PPE has no corresponding instruction mapping in this
surface: the explicit fallback directs the reader to the linked source and says
CRE has not reconstructed the rule from its title. This is a legibility gap, not
permission to change product-projection semantics in this slice.

## Validation

- New `test_policy_legibility.py`: 42 cases covering personal outcomes, unchanged
  canonical input, six action tokens across three institution subjects, no invented
  procedure, met/no-action, four exact PPE cases, eight Northstar flagships, four
  receipt origins, progression-negative-condition distinction, public rule/source
  preservation, and ordinary-language technical-token lint.
- Focused language/workspace/Northstar/PPE run: 207 passed.
- Chromium shared workspace and service-failure journeys: 8 passed, desktop 1440
  and mobile 390. Northstar 001/003/006/007/008/011/013/014/015; UCT empty/manual
  entry; all shared sections, source disclosures and back-links, navigation,
  export/print, student switching, failed retrieval and no overflow.
- Full suite: 1,270 passed (157.97 seconds), including the 42 new cases.
- Ruff: passed for the established application/governance checks and changed tests.
- Bandit: passed for app.py, curriculum_advisor and engine using pyproject config.
  Production changes in this slice are JavaScript/HTML/CSS, not Python logic.
- `git diff --check`: passed. No diff in engine, curriculum_advisor, app.py, data,
  northstar, catalogue_governance or tools versus the accepted repository baseline.
- Release verification result is recorded in the closure note below.

Existing tests were updated only where they asserted replaced text, origin location
or disclosure labels. No valid semantic test was removed. The pre-existing
Northstar canonical digest assertions continue to pass.

## Browser Review Artifacts

Before: `artifacts/shared-workspace/`. After: `artifacts/policy-legibility/after/`.
Both contain UCT and Northstar overview/curriculum screenshots at 1440 and 390.
Reviewed changes: shorter overview headings, clearer personal statements, distinct
uncertainty/conflict labels, visible actions, separate rule/evidence disclosures,
non-PDF registry locators, and left-aligned navigation. Source lists remain
collapsible. Full curriculum pages remain long; no rule was hidden for brevity.

UCT's original entry chrome remains separate and comparatively dense on mobile.
This slice did not redesign it. The known PPE third-year aggregate shortfall on
partial input remains visible exactly as projected, not presented as a clean
fidelity exemplar. The definitive-negative test uses `ppe_eco3025` with explicitly
complete academic and recognition coverage instead.

## Human Review Script

This is preparation, not evidence of actual comprehension or behavioural change.
Use the same prompts without coaching. Record the answer verbatim, then compare
with the canonical fixture and inspect the source with the reviewer.

1. Comprehension: In your own words, what is this telling you?
2. Reason: Why does the system think this?
3. Action: What would you do next?
4. Authority: Has the institution formally decided this?
5. Traceability: Where would you check the rule?

| Case | What the reviewer should be able to distinguish |
| --- | --- |
| PPE exact positive | Met from the existing witness; source is public; not official approval. |
| PPE exact missing | Not enough information, not a failed requirement. |
| PPE recognition | Decision counts; no new attempt, mark or institutional-origin claim for manual input. |
| PPE exact negative with complete coverage | Known shortfall, unlike missing information; not the third-year aggregate. |
| NS-001 | Met requirements alongside remaining unanswered questions. |
| NS-003 | Partial information and a bounded clarification step. |
| NS-006 | Conflict requires clarification, not choosing a preferred record. |
| NS-007 | One accepted path can satisfy a requirement; unused alternatives are not failures. |
| NS-011 | Entry requirements are not an admission decision. |
| NS-013 | Academic completion is not sufficient to establish graduation eligibility. |
| NS-014 | Graduation eligibility is not evidence of a formal award. |
| NS-015 | Explicit award evidence, not an award inferred by CRE. |

Probe whether "recognition", "progression" and "graduation eligibility" are
understood, whether disclosure labels help find the rule, whether generic action
questions are usable, and whether repeated necessary qualifications still distract.
Do not treat a correct click as proof that the student understood the distinction.

## Claim and Remaining Gaps

Technical claim: CRE presents the application of policy through shared
meaning-first student language while the institutional rule, source and authority
remain unchanged. The interface exposes position, explanation, bounded action and
institutional limits without requiring the raw engine vocabulary.

Not claimed: proven student comprehension, behavioural improvement, institutional
approval, official advice, formal decision-making, production readiness, complete
UCT source fidelity, or full PPE fidelity. The PPE aggregate issue, unavailable
safe PPE summaries, generic action questions where missing-item metadata is absent,
existing detail-template translation, and mobile entry-shell density remain gaps.
Next step is the bounded human teach-back review, not new reasoning or rule changes.

## Closure

Recommendation: **CLOSED as a bounded technical presentation slice**, with the
explicit legibility/source-fidelity gaps above. No real-user validation claimed.

UCT release gate: **PASS_WITH_WARNINGS**, exit 0. Manifest and source references
pass; full tests, Ruff and Bandit pass. No semantic/governance/provenance changes,
no unexplained drift. Existing warnings remain
`checksum_mismatch_unverified_source_archive` and `declaration not supplied`.
Institutional approval, source fidelity and institutional authorisation remain
blocked claims. No authority was upgraded.

| Review | Before | After |
| --- | --- | --- |
| Northstar desktop overview | [Before](../artifacts/shared-workspace/northstar-overview-1440.png) | [After](../artifacts/policy-legibility/after/northstar-overview-1440.png) |
| Northstar mobile curriculum | [Before](../artifacts/shared-workspace/northstar-curriculum-390.png) | [After](../artifacts/policy-legibility/after/northstar-curriculum-390.png) |
| UCT desktop curriculum | [Before](../artifacts/shared-workspace/uct-curriculum-1440.png) | [After](../artifacts/policy-legibility/after/uct-curriculum-1440.png) |
| UCT mobile overview | [Before](../artifacts/shared-workspace/uct-overview-390.png) | [After](../artifacts/policy-legibility/after/uct-overview-390.png) |

Other widths/views are in the same directories. No commit or push was made.
