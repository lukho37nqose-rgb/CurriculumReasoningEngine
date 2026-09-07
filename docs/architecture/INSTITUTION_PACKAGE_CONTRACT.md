# Institution Package Contract

An institution package supplies release-specific facts, configuration, and policy hooks to the Curriculum Reasoning Engine. UCT 2026 should become the first implementation of this contract.

## Implemented Today

UCT 2026 data is distributed across:

- `data/uct_commerce`
- `data/uct_ebe`
- `data/uct_health`
- `data/uct_humanities`
- `data/uct_law`
- `data/uct_science`
- `governance/releases`
- `governance/schemas`
- `tools/build_*_2026.py`

Stage 1 introduces an explicit metadata boundary in `curriculum_reasoning_engine/institutions/`. UCT 2026 academic units are represented by immutable `InstitutionRelease` and `AcademicUnit` models, and `app.py` derives its faculty metadata from that release. Stage 2 adds institution-owned route resolution for external programme labels. Stage 3 adds institution-owned catalogue resolution from stable academic-unit keys to existing UCT catalogue packages. Stage 4 binds the release to an explicit UCT transcript adapter. Stage 5 binds the release to an explicit UCT grading scheme. Faculty keys still appear in public compatibility routes, and most configuration remains partly data and partly code.

## Target Contract

Each institution release should provide:

```text
institution_id
release_id
display_name
academic_year_or_period
terminology
grading_scheme
credit_framework
academic_units
programme_catalogue
course_catalogue
recognition_rules
policy_hooks
adapter_bindings
governance_manifest
source_archive
verification_rules
```

## Required Files

Proposed UCT 2026 package shape:

```text
curriculum_reasoning_engine/institutions/uct/releases/y2026/
  institution.json
  terminology.json
  grading_scheme.json
  credit_framework.json
  academic_units.json
  data/
    commerce/
      courses.json
      degree_requirements.json
    ebe/
    health/
    humanities/
    law/
    science/
  policy/
    routing.py
    recognition.py
    award.py
    readmission.py
  adapters.json
  manifest.json
```

During gradual migration, these can be introduced as wrappers over existing `data/uct_*` files before any physical data move.

## Contract Semantics

- Package data may be incomplete, provisional, or conflicting. The engine must expose those statuses rather than repair them.
- Package policy hooks may return verified, provisional, unverified, conflict, or discretionary evaluations.
- Human-discretion conditions must be represented as discretion/verification requirements, not deterministic outcomes.
- A package may define transcript labels and aliases, but those aliases belong to institutional routing, not the generic core.
- A package may define course-code grammar and level inference, but the engine must not assume UCT code shape globally.

## Implemented Stage 1 API

The implemented compatibility API is intentionally small:

```python
@dataclass(frozen=True, slots=True)
class AcademicUnit:
    key: str
    name: str
    short_name: str
    description: str
    available: bool
    catalogue_key: str

@dataclass(frozen=True, slots=True)
class InstitutionRelease:
    institution_id: str
    institution_display_name: str
    release_id: str
    academic_year: int
    academic_units: tuple[AcademicUnit, ...]
    route_resolver: InstitutionRouteResolver
    catalogue_resolver: InstitutionCatalogueResolver
    transcript_adapter: TranscriptAdapter
    grading_scheme: GradingScheme
```

`get_institution_release("uct", "2026")` resolves the current UCT release. The release exposes legacy faculty-card projections so current API payloads remain unchanged.

Stage 2 also implements:

```python
@dataclass(frozen=True, slots=True)
class RouteResolution:
    source_label: str
    academic_unit_key: str
    catalogue_key: str
    programme_key: str
    pathway_key: str = ""
    status: str = "resolved"
    confidence: float = 1.0

class InstitutionRouteResolver(Protocol):
    def infer_academic_unit(self, programme_label: str) -> str: ...
    def infer_programme(self, programme_label: str) -> str: ...
    def resolve(self, programme_label: str) -> RouteResolution: ...
```

The generic routing contract contains no UCT programme mappings. UCT mappings are implemented in `curriculum_reasoning_engine/institutions/uct.py`.

Stage 3 also implements:

```python
@dataclass(frozen=True, slots=True)
class CatalogueDescriptor:
    institution_id: str
    release_id: str
    academic_unit_key: str
    catalogue_key: str
    courses_path: Path
    requirements_path: Path
    enabled: bool = True
    catalogue_version: str = ""

class InstitutionCatalogueResolver(Protocol):
    def resolve_academic_unit(self, unit_key: str) -> str: ...
    def resolve_catalogue(self, unit_key: str) -> CatalogueDescriptor: ...
    def available_catalogues(self) -> tuple[CatalogueDescriptor, ...]: ...
```

The generic catalogue contract contains no UCT academic policy. UCT 2026 maps stable aliases such as `humanities` to existing package keys such as `uct_humanities` in `curriculum_reasoning_engine/institutions/uct.py`. The physical data still lives in `data/uct_*`.

Stage 4 implements:

```python
class TranscriptAdapter(Protocol):
    adapter_id: str
    institution_id: str
    supported_formats: tuple[str, ...]

    def parse_text(self, text: str) -> StudentRecord: ...
    def parse_pdf(self, pdf_path_or_file) -> StudentRecord: ...
```

UCT transcript parsing lives in `curriculum_reasoning_engine/adapters/transcripts/uct.py`. `engine/parser.py` remains a compatibility shim, not the canonical parser.

Stage 5 implements:

```python
class ResultState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    PENDING = "pending"

class GradingScheme(Protocol):
    scheme_id: str
    institution_id: str

    def classify(self, result: Any) -> ResultState: ...
    def is_passed(self, result: Any) -> bool: ...
    def is_failed(self, result: Any) -> bool: ...
    def is_pending(self, result: Any) -> bool: ...
```

UCT pass/fail/pending semantics live in `curriculum_reasoning_engine/institutions/uct_grading.py`. `CourseResult.is_passed`, `CourseResult.is_failed`, `CourseResult.is_pending`, and the classification-derived `StudentRecord` helpers remain compatibility surfaces that delegate to an immutable legacy UCT default unless an explicit grading scheme is supplied.

## Future Minimum API

Later stages can extend the interface toward:

```python
class InstitutionRelease:
    institution_id: str
    release_id: str
    display_name: str
    academic_year: int | None

    def faculty_cards(self) -> list[dict]: ...
    def load_catalogue(self, unit_key: str) -> Catalogue: ...
    def grading_scheme(self) -> GradingScheme: ...
    def credit_framework(self) -> CreditFramework: ...
    def policy_hooks(self) -> PolicyHooks: ...
```

Those methods are not implemented yet.

## UCT 2026 Package Responsibilities

UCT 2026 should own:

- `uct_*` faculty keys and faculty metadata.
- UCT transcript programme/plan routing.
- UCT transcript text/PDF parsing.
- UCT grade tokens and mark thresholds.
- NQF assumptions and course-equivalent suffix weights.
- Humanities BA/BSocSc identity rules.
- Humanities FB5.1 and FB5.5 recognition constraints.
- Science major co-requirements, overlap policy, and FB7.7 discretion.
- UCT readmission, award, distinction, and professional-programme rules.
- UCT source archives, conflicts, verification notes, and release manifests.
