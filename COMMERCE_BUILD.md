# Commerce 2026 implementation

## Source and scope

The Commerce catalogue was built from the **2026 UCT Faculty of Commerce Undergraduate Handbook** and must be read with the 2026 General Rules and Policies handbook.

The undergraduate destination contains:

- 3 Advanced Diploma routes;
- 32 Bachelor of Business Science routes;
- 36 Bachelor of Commerce routes;
- standard, augmented and extended curricula as separate reasoning scopes;
- 316 course facts used by those curricula.

This phase encodes undergraduate curriculum and transcript reasoning. It does not claim to determine professional-body exemptions, postgraduate admission, current timetable availability or discretionary Faculty/Senate decisions.

## Commerce architecture

Commerce is not modelled as one generic degree with a loose list of electives.

```text
Commerce
├── qualification family
│   ├── Advanced Diploma
│   ├── Bachelor of Commerce
│   └── Bachelor of Business Science
├── delivery route
│   ├── standard
│   ├── augmented
│   └── extended
├── named specialisation
└── programme-scoped curriculum and progression rules
```

Each published plan code is a separate route. A course required by Financial Accounting, Actuarial Science or Information Systems cannot enter an unrelated Management Studies or Economics report merely because it appears somewhere in the Commerce handbook.

## Route coverage

| Qualification family | Standard | Augmented | Extended | Total |
|---|---:|---:|---:|---:|
| Advanced Diplomas | 3 | 0 | 0 | 3 |
| Bachelor of Business Science | 11 | 11 | 10 | 32 |
| Bachelor of Commerce | 12 | 12 | 12 | 36 |
| **Total** | **26** | **23** | **22** | **71** |

The routes include Actuarial Science, Quantitative Finance, Statistics and Data Science, Finance, Finance with Accounting, Computer Science, Information Systems, Economics, Economics with Law, Marketing, Industrial and Organisational Psychology, Financial Accounting, PPE, Economics and Finance, Economics and Statistics, Information Systems combinations and Management Studies.

## Curriculum representation

The builder preserves:

- compulsory courses by year;
- `or` substitutions and equivalent course groups;
- choose-N option groups;
- approved or open elective-credit pools;
- level-specific and total-credit requirements;
- standard versus augmented/extended support courses;
- programme-specific progression gates;
- programme-switch conditions;
- Law-course allocation as a competitive and discretionary condition;
- entry conditions for senior Actuarial, Accounting, Computer Science and Information Systems sequences.

Open or approved elective descriptions do not become blanket permission for every course in the university. Unlisted courses remain provisional until Faculty approval is confirmed.

## GPA and award logic

Commerce requires a distinct GPA model. For BCom and BBusSci curricula, the first attempt at a required course is normally used in the degree GPA even where a later attempt is passed. Results such as `AB`, `DPR` and `INC` may therefore contribute zero to the GPA while a later successful equivalent contributes credit toward completion.

The shared rule language now supports:

- `first_attempt_weighted_average`;
- `best_n_average`;
- programme-specific distinction rules;
- first-attempt-only award conditions.

The Management Studies elective rule is treated separately because the handbook allows a failed elective to be displaced by a different passed elective in defined circumstances.

## Progression and readmission

Commerce progression now supports:

- annual passed-course equivalents;
- cumulative failed-course equivalents;
- repeated failure of a required course;
- maximum-duration rules;
- specialisation-specific minimum course or mark gates;
- Actuarial Science exit conditions;
- forced movement from standard to extended routes where the published rule applies;
- programme transfer as a required response to failed senior-entry conditions.

These are risk indicators. The application does not impersonate the Faculty Examinations Committee, Readmission Review Committee, Dean or Senate.

## Source conflicts preserved

Five conflicting curriculum-table facts were retained for review rather than silently overwritten:

- `BUS2016H`;
- `BUS2033F`;
- `BUS4028F`;
- `ECO1111F`;
- `ECO1111S`.

The detailed course-outline fact is used provisionally as the stronger course source, while the conflicting table value remains recorded in `source_extraction/course_fact_conflicts.json`.

Further visible conflicts include:

- BCom Management Studies published curriculum totals that do not reconcile with the general 440-credit minimum;
- the Advanced Diploma in Actuarial Science table listing six prescribed courses while the distinction text refers to the best four results of five prescribed courses.

These conflicts block an unqualified positive conclusion where they matter.

## Course-data confidence

Of the 316 Commerce course facts:

- 303 are marked verified;
- 13 are provisional substitution shells needed to represent published equivalents;
- prerequisites are included only where they could be extracted conservatively and unambiguously.

A missing prerequisite is not interpreted as proof that none exists. Recommendation logic therefore remains conservative.

## External and discretionary boundaries

The static engine cannot establish:

- current lecture and examination timetable clashes;
- whether an elective or substitution has actually been approved;
- allocation of limited Law places;
- professional-body exemptions or accreditation outcomes;
- admission to PGDA, LLB, actuarial professional stages or other postgraduate study;
- current course capacity or post-publication curriculum amendments;
- an actual concession, readmission or programme-transfer decision.

## Verification

- all 71 Commerce programme scopes load;
- all 71 are structurally verified against the generated Commerce catalogue;
- 316 course facts load without catalogue validation errors;
- the Commerce builder is deterministic in the build environment;
- endpoint, isolation, progression, GPA, award and conflict tests pass;
- the full project passes 186 tests and 19 subtests.
