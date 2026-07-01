# Science Faculty 2026 implementation

## Scope

This phase implements the undergraduate Bachelor of Science qualification described in the 2026 UCT Faculty of Science handbook. Postgraduate Science qualifications are deliberately excluded.

## Route architecture

```text
Science
└── Bachelor of Science route
    ├── Regular BSc [SB001]
    │   ├── Current cohort: first registered from 2023
    │   └── Legacy cohort: first registered before 2023
    └── Extended Degree Programme [SB016]
        ├── Current cohort: first registered from 2023
        └── Legacy cohort: first registered before 2023
            ↓
        Intended major or majors
            ↓
        Transcript-scoped reasoning
```

The cohort is a required pathway because readmission rules changed from course-equivalent thresholds to NQF-credit thresholds for students first registered from 2023.

## General BSc rules represented

- minimum 360 NQF credits;
- minimum 180 Science credits;
- minimum 120 credits at NQF level 7;
- the first-year Science Mathematics/Statistics foundation;
- at least one recognised Science major;
- route-specific registration duration and readmission expectations;
- non-Science elective recognition and approval boundaries;
- distinction in a major and in the degree as a whole.

## Major catalogue

The 22 published undergraduate majors are represented:

1. Applied Mathematics (`MAM01`)
2. Applied Statistics (`STA01`)
3. Archaeology (`AGE01`)
4. Artificial Intelligence (`CSC08`)
5. Astrophysics (`AST02`)
6. Biochemistry (`MCB01`)
7. Biology (`BIO12`)
8. Business Computing (`CSC02`)
9. Chemistry (`CEM01`)
10. Computer Engineering (`CSC03`)
11. Computer Science (`CSC05`)
12. Environmental & Geographical Science (`EGS02`)
13. Genetics (`MCB04`)
14. Geology (`GEO02`)
15. Human Anatomy & Physiology (`HUB17`)
16. Marine Biology (`BIO05`)
17. Mathematical Statistics (`STA02`)
18. Mathematics (`MAM02`)
19. Ocean & Atmosphere Science (`SEA03`)
20. Physics (`PHY01`)
21. Quantitative Biology (`BIO13`)
22. Statistics & Data Science (`STA13`)

Each major uses composable curriculum nodes rather than a flat required-course list. This permits `all_of`, `any_of`, `choose_n`, mark conditions and equivalent sequences without mislabelling every alternative as compulsory.

## Major-combination rules

- Business Computing requires Computer Science as a co-major.
- Computer Engineering requires Computer Science as a co-major.
- Applied Statistics, Mathematical Statistics and Statistics & Data Science may not be combined with one another.
- Each major ordinarily requires at least 72 distinct level-7 credits recognised for that major.
- A controlled 36-credit overlap can be represented as requiring Deputy Dean approval; the system does not grant that approval itself.

## Course recognition and equivalence

The catalogue stores 241 undergraduate Science and required cross-faculty course facts. It represents the common equivalences published with the major rules, including:

- `BIO1000H` / `BIO1000F`;
- `CEM1009H + CEM1010H` / `CEM1000W`;
- EDP and mainstream Computer Science sequences;
- EDP and mainstream Mathematics sequences;
- `PHY1023H` / `PHY1031F`;
- the mark-dependent `MAM1004F/S` substitution for `MAM1031F`.

Equivalent courses satisfy curriculum requirements but do not create duplicate credit.

Courses from other faculties that are compulsory for a Science major can be marked as Science credits in that context. This includes the required EEE, HUB and INF courses used by certain majors.

## Non-Science electives

A non-Science course can contribute only where it meets the published recognition conditions. The engine distinguishes:

- up to 72 approved non-Science elective credits subject to the exclusion list;
- additional non-Science credits that must form a hierarchical sequence;
- courses explicitly excluded from Science-degree recognition;
- Science service courses that may not be taken by students registered in Science;
- historical transfer evidence that requires departmental equivalence confirmation.

An unknown transcript course is never silently promoted to an approved elective. It is treated as provisional and can force `requires_verification`.

## Progression and readmission

The current regular BSc route checks:

- 72 Science credits after first year;
- 144 cumulative credits and all first-year major requirements after second year;
- 228 cumulative credits and a viable one-year completion path after third year;
- expected qualification completion after fourth year;
- at least 72 credits completed in the preceding year where applicable.

The current EDP route checks the separate 54/108/180/252-credit cumulative pattern and its senior-credit conditions.

Legacy routes use the published full-course-equivalent thresholds. These results are risk indicators: the Faculty Examinations Committee and Senate retain decision-making authority.

## Limited-major admission

Biochemistry, Genetics and Human Anatomy & Physiology are marked admission-limited. Geology is also marked for confirmation because its individual major table states that entry is limited while the general faculty note names a shorter list.

Passing the relevant first-year courses does not prove that the student was formally admitted. A completed limited major therefore remains unverified unless institutional admission evidence is available.

## Awards

The engine evaluates:

- major-specific first-class course patterns;
- degree distinction requiring a distinction in at least one major;
- the alternative degree-wide first-class credit/course pattern;
- first-attempt restrictions;
- exclusion of supplementary examination passes from award evidence.

Where the handbook permits Faculty substitution of a cognate course, the result remains discretionary.

## Verification performed

- 241 catalogue facts load without data issues;
- 22 major definitions load;
- 2 routes and 4 cohort scopes load;
- all 4 scopes are structurally verified;
- every major rule tree was exercised with a satisfying set of represented courses;
- API, compilation and JavaScript smoke checks passed;
- the full project test suite passes 156 tests and 19 subtests.

## Explicit limitations

The application cannot determine from a static transcript alone:

- whether a student was formally accepted into a capacity-limited major;
- live course availability, lecture periods or timetable clashes;
- Student Advisor or Deputy Dean approval of electives or major overlap;
- individual probationary conditions;
- Senate concessions or readmission decisions;
- post-publication curriculum amendments;
- whether a course-level examination or coursework subminimum was met when the transcript records only a final result.
