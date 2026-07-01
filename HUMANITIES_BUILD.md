# Humanities 2026 route build

## Delivered route coverage

The site now contains all 24 undergraduate Humanities programme routes represented in the 2026 handbook, including regular, extended, structured, continuing-only, and not-offered routes.

### Flexible general degrees

- BA regular — HB003
- BSocSc regular — HB001
- BA extended — HB061
- BSocSc extended — HB062

### Education certificates and advanced diplomas

- Higher Certificate in Adult and Community Education and Training — HU052
- Advanced Certificate in Foundation Phase Teaching — HU048
- Advanced Certificate in Intermediate Phase Teaching — HU045
- Advanced Certificate in Senior Phase Teaching — HU043, with three subject pathways
- Advanced Diploma in Adult and Community Education and Training — HU051
- Advanced Diploma in School Leadership and Management — HU053, with two intake patterns

### Structured bachelor routes

- BA specialising in Screen Production — HB067
- BSocSc in Philosophy, Politics and Economics — HB027
- Bachelor of Social Work — HB063, with Psychology and Sociology routes
- BA in Fine Art regular — HB008
- BA in Fine Art extended — HB064

### Music

- Diploma in Music Performance regular — HU021, five streams
- Diploma in Music Performance extended — HU035, five streams
- Advanced Diploma in Opera — HU047
- Advanced Diploma in Music — HU046
- Bachelor of Music regular — HB010, seven streams
- Bachelor of Music extended — HB034, seven streams

### Theatre and Performance

- Diploma in Theatre and Performance — HU020, five concentrations
- Advanced Diploma in Theatre — HU050
- BA in Theatre and Performance — HB014, five concentrations

## Catalogue totals

- 24 programme routes
- 41 pathway definitions
- 888 course facts
- 42 general-degree major definitions
- 18 open routes
- 3 continuing-only routes
- 3 routes not offered in 2026

## Architectural changes

- Programme and pathway are mandatory analysis boundaries.
- Structured routes no longer masquerade as BA/BSocSc majors.
- Curriculum alternatives are represented with a composable rule tree.
- Programme pages dynamically expose pathway selection.
- Major controls disappear for structured routes.
- API, simulations, course catalogues, and transcript analysis use the same scope key.
- Route availability and verification status are visible in the interface.
- Structured qualifications do not incorrectly inherit general BA/BSocSc distinction calculations.

## Verification boundaries

Thirty programme/pathway scopes are structurally verified. Twenty-six are intentionally unverified because at least one selected pathway contains an irreducible placement, combination, continuation, or discretionary condition. This is a safety property, not a loader failure.

Most Music streams are route-complete but cannot be conclusively resolved from a transcript without the student's instrument, ensemble, placement, and approved combination. Professional and performance routes similarly retain departmental judgment conditions.

## Automated verification

- The combined Humanities + EBE regression suite passes 135 tests
- 19 subtests passed
- Python compilation passed
- Frontend JavaScript syntax passed
- All programme/pathway scopes built without missing course references
- Representative structured qualification reached verified eligibility
- Cross-pathway leakage tests passed for BSW and Theatre
- Music false-positive graduation prevention passed
- Endpoint pathway validation passed
