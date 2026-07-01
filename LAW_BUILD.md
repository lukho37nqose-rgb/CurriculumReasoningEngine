# Law Faculty 2026 build record

## Scope

This phase enables the **undergraduate Basic Legal Education programme leading to the LLB**. The Law handbook also contains postgraduate diplomas, LLM/MPhil programmes and doctoral rules; those are deliberately outside the present undergraduate transcript-advising product.

## Routes represented

1. `llb_four_year_undergraduate` — four-year undergraduate LLB, LB002.
   - `numeracy_course_required`: official numeracy test below 66%, so MAM1013F is compulsory.
   - `numeracy_test_passed`: official numeracy test at least 66%, so an additional non-law semester course replaces MAM1013F.
2. `llb_three_year_graduate` — three-year graduate LLB, LP001.
3. `llb_two_year_combined` — two-year graduate phase after the Law-and-Humanities/Commerce preliminary curriculum, LP001.
4. `llb_five_year_continuing` — LB003 continuing-student curriculum for students first registered in or before 2019.

The five-year route recognises the published legacy/replacement pairs for PVL1006W/PVL1003W, PVL1009S/PVL1008H, PVL1007F/PVL1004F and PBL2002W/PBL2000W.

## Law-specific architecture

Law is represented as three curriculum levels rather than as majors:

- Preliminary Level;
- Intermediate Level;
- Final Level, including the compulsory community-service, skills and Integrative Assessment Moot components.

The scope layer now supports **programme-specific prerequisite and co-requisite overrides**. This is necessary because the six Preliminary courses are concurrent in the three-year graduate route, while the four-year route separates them across two years.

The curriculum rule language was extended with:

- `maximum_credit_pool` — enforces the 54-credit Final Level elective ceiling;
- `same_department_credit_pool` — checks that the two 2000-level non-law courses come from one discipline;
- `no_failures` — supports the FP18 award screen while preserving Senate condonation as a discretionary possibility;
- `passed_mark_equivalents` — counts first-class law-course equivalents by 36-credit full-course units;
- `failed_course_equivalents` — supports the FP11 annual readmission-risk thresholds.

## Final Level research component

The engine separately checks:

- at least 36 elective/research credits;
- at least one seminar-and-research-paper elective, an 8,000-word independent research paper, or the approved DOL3000X Moot Caput substitution;
- no more than 54 Final Level elective credits.

Courses marked not offered in 2026 remain available for historical transcript recognition but are excluded from course recommendations.

## Non-law curriculum

The four- and five-year curricula represent:

- the English/Word Power choice;
- the numeracy pathway;
- first-year courses in another faculty;
- a two-semester or whole-course language sequence;
- 40 credits of 2000-level courses in one non-law discipline.

Known 2026 cross-faculty course facts are evaluated directly. A transcript-only course can satisfy a published category only provisionally, with Faculty recognition still requiring confirmation.

## Progression and awards

The readmission indicator represents FP11's failed-course-equivalent threshold and the prescribed duration plus one year. It does not predict a Faculty Examinations Committee, Readmission Appeal Committee or Senate decision.

Cum laude and magna cum laude screens represent minimum-time completion, absence of uncondoned failures, the cumulative law-course average, and the required number of first-class full-course equivalents. Senate remains the awarding authority.

## Known limits

- An ordinary transcript does not disclose the mark obtained in the final examination, so FP14's 45% examination subminimum cannot be independently verified.
- The app cannot prove that the numeracy test was passed; the student must select the route from the official result.
- Admission to the two-year graduate phase is not automatic.
- Law Clinic admission, Moot Competition approval, timetable compatibility, concessions and course capacity are live institutional decisions.
- Completion of the LLB is not itself admission to legal practice.
