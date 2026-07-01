# CurriculumAdvisor governance merge validation report

## Status

**Build status:** tests passed; additive merge completed.  
**Release provenance status:** not verified against the supplied public-release checksum.  
**Deployment status:** candidate only until the source checksum mismatch is resolved.

## Inputs

| Input | SHA-256 | Verification |
|---|---|---|
| Uploaded source: `CurriculumAdvisor-UCT-2026.zip` | `cb0670cfbc36be293d992e736dbee5bc875d3afa8620322a52eb908d4055f659` | Does not match supplied public-release checksum |
| Expected public release | `800c6a4488b0630f83f9c1a24b3a87f6c608c31a4185eeb14014cbbfdb8b527c` | Expected value from supplied checksum file |
| Governance foundation v1 | `4a82423d43c9146fabff8f1fefd5a34bd43cb5e6534e76c9274f8da69bfdbff0` | Matches its supplied checksum |

The source archive may still contain valid project code, but it is not byte-for-byte the archive identified by the supplied checksum. The merge therefore records it as an unverified source archive rather than silently relabelling it as the public release.

## Merge guarantees checked

- Merge mode was additive only.
- Zero relative file-path collisions were found before copying.
- All 76 original source files remain byte-for-byte identical after the merge.
- No existing faculty catalogue, application module, static file, test, or deployment file was overwritten.
- All 22 files under `data/` were recorded in a SHA-256 baseline manifest.
- The baseline verifies with no missing, changed, or unexpected curriculum-data files.
- Timetable/course-offering data remains separate from curriculum rules and the reasoning engine.

## Test results

### Before merge

- 186 tests passed.
- 19 subtests passed.

### After merge

- 195 tests passed.
- 19 subtests passed.
- The example course-offering payload passed operational-data validation with no warnings.
- Python compilation checks passed for the application, engine, governance package, and tools.

## Added capabilities

- Non-destructive curriculum-data baselines and verification.
- Release-manifest comparison.
- Atomic manifest writing with overwrite refusal by default.
- Curriculum change-request schema.
- Faculty extraction-profile schema.
- Separate course-offering and timetable schema and validator.
- Governance, migration, and source-provenance records.

## Files of special importance

- `governance/releases/uct-2026-uploaded-baseline.manifest.json`
- `governance/releases/source_archive_verification.json`
- `governance/releases/additive_merge_audit.json`
- `docs/CURRICULUM_DATA_GOVERNANCE.md`
- `docs/FIRST_SAFE_MIGRATION.md`

## Safe next action

Use this package for review and continued development. Do not describe or deploy it as the checksum-verified public release unless either:

1. the archive matching `800c6a4488b0630f83f9c1a24b3a87f6c608c31a4185eeb14014cbbfdb8b527c` is supplied and merged; or
2. the source owner confirms that `cb0670cfbc36be293d992e736dbee5bc875d3afa8620322a52eb908d4055f659` is the intended replacement release and issues a new checksum.
