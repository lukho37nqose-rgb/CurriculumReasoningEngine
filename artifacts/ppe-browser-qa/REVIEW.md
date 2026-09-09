> **Historical document**
> This file describes an earlier stage of CRE and is retained for development history. It should not be treated as the current architecture or product specification. See [current architecture](../../docs/CURRENT_ARCHITECTURE.md) and the [documentation index](../../docs/README.md). Original content below is preserved; counts, screenshots, commands and claims retain their original milestone context.

# PPE facilitated fidelity-review rehearsal

This is a technical/product rehearsal using synthetic evidence, not institutional approval.
The review scope is exactly ppe_year1, ppe_year2_fixed, ppe_year2_politics,
ppe_year2_other, ppe_eco3025, ppe_phi3 and ppe_pol3.

## Demonstration order

1. Open the Humanities workspace and select BSocSc PPE.
2. Show the satisfied fixture: POL2039F and ECO3025S have synthetic passing results.
3. Open the represented requirement detail and identify the confirmed witness.
4. Open CRE's represented source location and its qualification disclosure.
5. Compare the choose-one Politics group with the all-required first-year group.
6. Show Start empty: the seven selected requirements are unresolved, not failed.
7. Show the shortfall fixture: complete result AND recognition snapshots cover ECO3025S only.
8. Show the synthetic conflicting recognition fixture for POL2039F.
9. Show the unresolved formal-award assessment. No conferment evidence was supplied.
10. Open Evidence & limits and the grouped Humanities source directory.
11. Repeat source/detail disclosure with keyboard, then show the narrow viewport.

For evidence-rich fixtures the QA harness submits synthetic data to the existing backend
and loads the returned report into the real application renderer. The ordinary student
form does not expose recognition or coverage ingestion. This is not a portal/SIS demo.

## Facilitator introduction

We want to test whether the represented rule and student explanation preserve the
institutional meaning. We are not asking you to approve CRE.

Keep the actual handbook open separately at pages 43 and 44. Retained location labels
are not presented as verified handbook quotations.

## Ask at each of the seven requirements

1. Is CRE pointing to the right source location?
2. Does the represented rule match what you understand this source to require?
3. Does this student explanation preserve that meaning?
4. Would a student understand what they need to do?
5. Is any necessary qualification missing?
6. Does CRE overstate its authority?
7. Is there terminology you would want students to learn rather than have replaced?

Carry forward the eight substantive questions from the accepted fidelity pack unchanged.
This rehearsal neither rewrites nor answers them. No course pool, exception, recognition
permission, locator, provenance status or evaluator has been changed in this task.

## Boundaries and follow-up

- The unreviewed ppe_third_count result is not_satisfied in the empty fixture. It is
  outside these seven rules and was not semantically repaired or validated here.
- Coverage and recognition terminology still benefits from an advisor's explanation.
- Passing a witness test is not approval of recognition permissions in the real policy.
- Keyboard checks and two viewport sizes are not accessibility certification.
- Source/provenance remain incomplete; institutional approval remains NOT ASSESSED.

## Evidence

Screenshots are named by scenario, viewport width and requirement. `observations.json`
records the rendered text, canonical outcome receipts, page widths and browser errors.
`input-error.png` shows the unreadable synthetic PDF recovery message.
Reproduce with the local app on port 8765 and `python tools/qa_ppe_browser.py`.
