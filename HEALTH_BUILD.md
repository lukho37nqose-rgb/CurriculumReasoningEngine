# Faculty of Health Sciences 2026 build

## Scope

The Health Sciences destination models undergraduate professional programmes as fixed, programme-scoped curricula rather than as majors or open elective degrees. It is grounded in the 2026 Faculty of Health Sciences Undergraduate Handbook and the shared 2026 General Rules and Policies.

## Routes

Fourteen undergraduate routes are represented:

- Advanced Diploma in Cosmetic Formulation Science (`MU003`)
- BSc Audiology (`MB011`) and Fundamentals route (`MB019`)
- BSc Speech-Language Pathology (`MB010`) and Fundamentals route (`MB018`)
- BSc Occupational Therapy (`MB003`) and Fundamentals route (`MB016`)
- BSc Physiotherapy (`MB004`) and Fundamentals route (`MB017`)
- MBChB (`MB014`) and Fundamentals route (`MB020`)
- BSc Medicine (`MB001`)
- Higher Certificate in Disability Practice (`MU002`)
- Nelson Mandela Fidel Castro Medical Training Programme (`MZ010`)

MBChB and MBChB Fundamentals each contain separate award cohorts for students first enrolled from 2024 and students governed by legacy pre-2024 award rules. This produces **16 programme/pathway scopes**.

## Health-specific architecture

The build represents:

- fixed professional curricula and academic-year sequencing;
- standard and Fundamentals routes as separate programme boundaries;
- the Fundamentals of Health Sciences gateway course;
- MBChB clinical stages and cohort-specific award logic;
- course aliases for clinical block allocations;
- first-year semester failure groups;
- annual failed-course proportions and repeat-year failure patterns;
- route-specific maximum registration periods;
- BSc Medicine credit recognition and level caps;
- clinical/practice-learning and professional confirmation nodes;
- restricted and externally controlled training routes.

## Epistemic boundary

A transcript cannot prove all clinical hours, logbook completion, placement sign-off, professional conduct clearance, fitness to practise, HPCSA registration, vaccination compliance or approval of concessions. These remain explicit blocking verification conditions. A complete-looking clinical transcript therefore normally produces `requires_verification`, not a false verified clearance.

The Occupational Therapy table also contains a published internal credit reconciliation problem: the listed rows sum differently from the printed programme total and expose only 112 level-7 credits against the general 120-credit HEQSF statement. The engine surfaces this as a conflict requiring Faculty confirmation rather than making the prescribed curriculum impossible to complete.

## Validation

- **433** Health Sciences course facts
- **14** programme routes
- **16** programme/pathway scopes
- all Health Sciences scopes load without missing programme references
- Fundamentals routes enforce the gateway course
- Audiology and Speech-Language Pathology remain isolated
- clinical routes remain verification-bound
- MBChB equivalent block codes satisfy canonical requirements
- BSc Medicine credit/level/cap rules are tested
- the NMFC route cannot self-certify a UCT medical qualification
- combined and split Disability Practice curricula are supported
- Health-specific progression thresholds are regression-tested
