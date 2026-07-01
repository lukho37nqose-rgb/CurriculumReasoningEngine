# CurriculumAdvisor governance foundation — build report

**Build date:** 1 July 2026  
**Implementation type:** additive, non-destructive patch  
**Existing curriculum files modified:** none  
**Existing application files modified:** none

## Purpose

This milestone establishes the safety layer required before an administrator interface, annual handbook refreshes, or timetable integration can be introduced responsibly.

## Implemented

- deterministic SHA-256 manifests for the current `data/` tree;
- verification of changed, missing and unexpected files;
- explicit comparison of two catalogue releases;
- atomic manifest writes;
- refusal to overwrite an existing manifest unless explicitly forced;
- a versioned schema for release manifests;
- a versioned schema for curriculum change requests;
- a versioned faculty extraction-profile schema;
- a separate term-specific course offering/timetable schema;
- operational-data validation for status, duplicate offering identity, meeting times and internal overlaps;
- governance rules for ownership, review, publication and historical protection;
- a first safe migration procedure.

## Deliberate boundaries

This patch does not:

- edit or relocate any existing faculty catalogue;
- alter `app.py`, the catalogue loader, scope builder or reasoning engine;
- add an unauthenticated administrator endpoint;
- introduce a database;
- allow timetable data to grant credit or change graduation outcomes;
- treat extraction as publication;
- overwrite historical curricula.

## Verification

- `pytest -q`: **9 passed**;
- Python compilation: passed;
- synthetic baseline creation: passed;
- synthetic baseline verification: passed;
- example operational offering validation: passed.

## Integration requirement

The patch should first be merged into a new branch and the existing full CurriculumAdvisor test suite should be run unchanged. Only after that should the first real `data/` baseline manifest be generated and committed in a separate commit.

## Next milestone

After the real baseline is committed and verified, the next safe addition is a **draft-only change workspace**. It should copy selected records into an isolated proposal, validate references and show an impact diff. It must not publish or alter live catalogue files.
