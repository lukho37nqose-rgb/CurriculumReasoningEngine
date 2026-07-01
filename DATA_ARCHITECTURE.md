# CurriculumAdvisor data and reasoning architecture

## 1. Boundary before reasoning

The full faculty catalogue is an ingestion store, not a student's reasoning universe.

```text
faculty
└── programme / qualification
    └── pathway / stream / specialisation / curriculum cohort (where required)
        └── majors (only where the qualification uses majors)
            └── programme-scoped course and rule graph
                └── transcript evidence
```

Every analysis, simulation and recommendation endpoint receives the same explicit route context. Missing or invalid context is rejected rather than inferred into a positive conclusion.

## 2. Source layers

```text
University-wide rules (Handbook 3)
        ↓
Faculty rules and programme curricula
        ↓
Course facts and prerequisites
        ↓
Current operational or discretionary facts
```

The first three layers can be represented in static data. Current offerings, timetable capacity, placements, granted concessions, professional exemptions and authorised decisions remain external evidence.

## 3. Data packages

```text
data/
├── uct_humanities/
├── uct_ebe/
├── uct_law/
├── uct_science/
├── uct_health/
└── uct_commerce/
    ├── courses.json
    ├── degree_requirements.json
    └── source_extraction/
```

Each faculty package is independently loadable and independently scoped.

## 4. Programme model

A `ProgrammeRules` record stores:

- qualification and plan codes;
- minimum duration and ordinary maximum registration period;
- required courses and composable curriculum rules;
- permitted majors or elective pools where relevant;
- required pathways, streams, specialisations or cohorts;
- progression and award rules;
- route-specific prerequisite and corequisite overrides;
- availability, provenance and verification state.

A required route choice cannot be omitted.

## 5. Curriculum rule language

| Node | Meaning |
|---|---|
| `course`, `all_courses`, `choose_n` | compulsory and alternative course requirements |
| `all_of`, `any_of` | nested Boolean curriculum structures |
| `credits`, `level_credits` | aggregate credit requirements |
| `credit_pool`, `approved_credit_pool` | minimum credits in an explicit or approved pool |
| `maximum_credit_pool` | upper boundary on a credit category |
| `same_department_credit_pool` | one disciplinary sequence |
| `minimum_mark` | mark-dependent requirement |
| `weighted_average` | credit-weighted award or programme average |
| `first_attempt_weighted_average` | Commerce-style average using first attempts at relevant courses |
| `best_n_average` | average over the strongest N qualifying results |
| `no_failures` | no recorded failure condition |
| `passed_mark_count`, `passed_mark_equivalents` | mark/equivalent award conditions |
| `first_class_group` | first-attempt first-class course pattern |
| `course_count` | number of matching completed courses |
| `manual` | admission, placement, permission, professional or other non-computable condition |

Every node carries an identifier, label, blocking semantics and verification state. A complex handbook rule remains a tree rather than being flattened into misleading compulsory-course rows.

## 6. Progression rule language

Progression/readmission indicators support:

- `annual_credits` and `cumulative_credits`;
- `science_cumulative_credits` and `senior_cumulative_credits`;
- legacy course-equivalent thresholds;
- `annual_course_equivalents`;
- `cumulative_failed_course_equivalents`;
- `selected_major_stage_complete`;
- `qualification_expected`;
- `pass_rate`;
- `failed_any` and `repeat_failure`;
- `failed_course_equivalents`;
- `failed_course_count`;
- `failed_course_fraction`;
- `failed_courses_by_group`;
- `curriculum_stage_complete`;
- `repeat_year_failure`;
- `maximum_years`;
- `manual` Faculty confirmation.

These produce risk indicators, not predictions of a Faculty Examinations Committee, Readmission Committee or Senate decision. Missing academic-year evidence produces an unverified assessment.

## 7. Course facts and recognition

A `CourseFact` stores:

- code, name, credits and NQF level;
- prerequisites and corequisites;
- offering status;
- department/faculty ownership;
- whether it is credit-bearing;
- recognition and elective flags;
- equivalent course or clinical-block codes where published;
- source and verification state.

Catalogue facts outrank transcript-layout inference. Repeated attempts remain evidence while credit is awarded once per course code. Zero-credit projects and assessments can satisfy curriculum nodes without inflating credits.

## 8. Elective allocation

Open or approved elective categories are explicit rule nodes. The allocator:

- filters by department, level, course code, credits and recognition state;
- prevents one course satisfying several pools unless explicitly permitted;
- marks unlisted transcript courses provisional;
- does not infer institutional approval.

This supports Humanities general electives, EBE controlled options, Law non-law requirements, Science non-Science elective limits and Commerce programme-specific option pools. Health Sciences normally uses closed prescribed curricula instead.

## 9. Attempt history, credit and GPA

Three questions are kept separate:

1. Did the student pass the course at least once?
2. Which successful attempt awards credit?
3. Which attempt must be used for a faculty-specific GPA or award rule?

This distinction is essential in Commerce, where a first failed attempt may count as zero in the degree GPA even though a later attempt or equivalent course supplies credit for curriculum completion.

## 10. Progression and awards are separate

Graduation completion, progression/readmission risk and awards are evaluated independently. A student may complete a qualification without meeting distinction, honours or professional-entry criteria.

Selected pathway award rules are combined with programme award rules without contaminating other routes.

## 11. Epistemic states

Requirement and conclusion states include:

- `verified`;
- incomplete;
- `provisional` or `unverified`;
- `discretionary`;
- `conflict`.

Graduation has three public outcomes:

- `eligible`;
- `not_eligible`;
- `requires_verification`.

No verified positive conclusion may depend on a provisional, discretionary or conflicting blocking requirement.

## 12. Faculty-specific models

### Humanities

Flexible majors coexist with prescribed professional, arts, music, theatre, education and social-work curricula.

### EBE

Prescribed yearly curricula, ASPECT routes, transition cohorts, practical requirements and controlled elective categories dominate.

### Law

Preliminary, Intermediate and Final Levels, route-specific concurrency, a research/elective component, non-law sequences and Law-specific award rules dominate.

### Science

A flexible BSc combines general degree minima with one or more composable majors, equivalent course sequences, distinct level-7 major depth, Science-credit recognition, non-Science elective boundaries and cohort-specific readmission rules.

### Health Sciences

Prescribed professional curricula dominate. Standard and Fundamentals routes are separate scopes. Academic-year gates, clinical blocks, practice learning, professional registration and fitness-to-practise conditions are separated into transcript-computable and human-confirmation evidence.

### Commerce

BCom, BBusSci and Advanced Diploma qualification families are separate. Standard, augmented and extended routes are separate scopes. Named specialisations carry prescribed course sequences, controlled electives, mark-dependent entry gates, professional progression conditions, first-attempt GPA rules and programme-transfer consequences.

## 13. Source conflicts and provenance

Static rules carry document, page/section and verification metadata. Conflicting values are retained in extraction reports rather than silently harmonised. A conflict that affects a blocking requirement produces `requires_verification` or prevents a positive award conclusion.

## 14. Source hierarchy

1. The relevant 2026 faculty handbook.
2. The 2026 General Rules and Policies handbook.
3. Current institutional systems and authorised decisions.

Live operational facts and discretionary decisions remain outside deterministic handbook reasoning.
