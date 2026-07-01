# CurriculumAdvisor UCT Undergraduate 2026 — build report

## Outcome

The website now enables all six UCT undergraduate faculty destinations:

- Humanities;
- Engineering & the Built Environment;
- Law;
- Science;
- Health Sciences;
- Commerce.

The faculties share transcript parsing, evidence handling and conclusion states, but retain different curriculum architectures.

## Combined coverage

| Faculty | Routes | Scopes | Course facts | Majors | Verified scopes |
|---|---:|---:|---:|---:|---:|
| Humanities | 24 | 56 | 888 | 42 | 30 |
| EBE | 28 | 40 | 354 | 0 | 14 |
| Law | 4 | 5 | 499 | 0 | 5 |
| Science | 2 | 4 | 241 | 22 | 4 |
| Health Sciences | 14 | 16 | 433 | 0 | 16 |
| Commerce | 71 | 71 | 316 | 0 | 71 |
| **Total** | **143** | **192** | **2,731** | **64** | **140** |

All 192 scopes load. The 52 unverified Humanities/EBE scopes remain intentionally marked as such because their static rule or pathway evidence is incomplete.

## Commerce outcome

Commerce adds 71 independently scoped routes:

- 3 Advanced Diplomas;
- 32 Bachelor of Business Science routes;
- 36 Bachelor of Commerce routes;
- 26 standard, 23 augmented and 22 extended routes.

The Commerce model separates qualification family, delivery route and named specialisation. It represents compulsory curricula, substitutions, controlled elective groups, professional progression gates, first-attempt GPA behaviour, readmission thresholds and programme-transfer conditions.

## Reusable reasoning capabilities added

The curriculum engine now supports:

- `best_n_average`;
- `first_attempt_weighted_average`.

The progression engine now supports:

- `annual_course_equivalents`;
- `cumulative_failed_course_equivalents`.

These are general rule types rather than Commerce-only hard-coded checks.

## Evidence and conflict handling

- 303 Commerce course facts are verified and 13 are provisional substitution shells.
- Five curriculum-table course-fact conflicts are retained in an extraction report.
- BCom Management Studies credit-total discrepancies remain blocking source conflicts.
- The Advanced Diploma in Actuarial Science distinction wording conflict remains visible.
- Approved/open electives cannot create a verified positive conclusion without adequate course and approval evidence.
- Law-stream course allocation remains discretionary and competitive.

## Shared safety behaviour

- Faculty, programme and required pathway are backend boundaries.
- Repeated attempts cannot award duplicate credit.
- Programme-specific courses cannot leak into unrelated programme scopes.
- The attempt used for Commerce GPA is not confused with the attempt used to award course credit.
- Clinical, professional, accreditation and discretionary decisions are not inferred from transcript marks.
- Positive graduation conclusions require every blocking rule to be complete and verified.

## Validation

- **186 tests passed**;
- **19 subtests passed**;
- all Python modules compile;
- frontend JavaScript passes syntax validation;
- all **192** programme/pathway scopes load;
- all **71 Commerce scopes** are structurally verified;
- all six faculty endpoints return successfully;
- Commerce catalogue rebuilding is deterministic in the build environment;
- a complete synthetic Advanced Diploma in Management Development record produces a verified eligible result and distinction;
- route isolation, progression, first-attempt GPA, award conflicts and discretionary Law allocation tests pass;
- ZIP integrity passes.

## Remaining institutional boundaries

Static handbook reasoning cannot establish current timetable clashes, course capacity, a granted concession, approved substitutions, professional-body exemptions, limited-course allocation, current clinical or placement evidence, an actual FEC/RAC/Senate decision, or post-publication curriculum amendments.
