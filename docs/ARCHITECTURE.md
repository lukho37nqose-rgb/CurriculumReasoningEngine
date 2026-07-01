# CurriculumAdvisor architecture

## 1. Architectural thesis

CurriculumAdvisor should be a modular monolith with a strict internal separation between:

- **catalogue facts**;
- **student evidence**;
- **reasoning and simulation**;
- **operational offerings**;
- **institutional decisions**;
- **presentation**;
- **release governance**.

The system is not large enough to benefit from microservices. Splitting it prematurely would make cross-service consistency, testing and provenance harder. The intellectually difficult part of this product is not throughput. It is preserving the meaning and authority of academic claims.

## 2. Layers

### Presentation

`static/index.html`, `static/app.css`, and `static/app.js` implement the student decision workspace.

`static/admin.html`, `static/admin.css`, and `static/admin.js` implement the read-only governance desk.

The browser stores route state only for the active session. Transcript files and academic reports are not written into the catalogue or browser storage.

### Versioned API

New product requests use `/api/v1`. Legacy routes remain as compatibility aliases.

The API is responsible for:

- validating faculty, programme and pathway selection;
- accepting bounded transcript evidence;
- binding transcript facts to one explicit curriculum scope;
- returning computed reports;
- exposing catalogue readiness and immutable-release integrity.

### Product orchestration

`curriculum_advisor/product.py` contains product metadata, decision lenses, capabilities and trust boundaries.

`curriculum_advisor/governance_status.py` reads and verifies the catalogue baseline. It cannot publish or edit data.

This layer may grow into route-specific services, but it must not absorb the academic rule engine itself.

### Academic domain

`engine/` remains the academic core:

- transcript parser;
- typed catalogue models;
- programme scoping;
- curriculum evaluation;
- reasoning graph;
- rule engine;
- goals and simulations.

No student-specific conclusion belongs in catalogue JSON.

### Catalogue data

`data/` contains faculty facts and curriculum rules. The redesign does not relocate or rewrite this directory.

A catalogue release is immutable. A later academic year should create another release rather than overwrite the rules governing an earlier cohort.

### Governance

`governance/` contains:

- release manifests;
- change-request schema;
- course-offering schema;
- faculty extraction-profile schema;
- safe templates;
- source and merge provenance.

## 3. Trust boundaries

### Curriculum boundary

A programme-scoped catalogue is created before analysis. Courses and majors outside that scope cannot produce positive advice.

### Operational boundary

A course definition and a term offering are different records. The existence of a curriculum course does not prove that it is scheduled, has capacity or avoids a clash.

### Discretion boundary

Concessions, substitutions, readmission decisions, clinical placement evidence, professional registration and Senate or Faculty approval are not ordinary computable facts.

### Publication boundary

The public `/admin` route is read-only. Enabling writes requires authentication, role assignments, source evidence, approval separation, audit history and rollback.

## 4. API compatibility strategy

All domain endpoints have two paths during migration:

```text
/api/v1/analyse    preferred
/analyse           compatibility alias
```

The compatibility route should be removed only through a deliberate deprecation release after clients have migrated.

## 5. Readiness versus liveness

`/health` proves that the process is running.

`/ready` proves that all six enabled catalogue roots can load. Railway uses `/ready` because a running API without readable curriculum data is not a usable CurriculumAdvisor deployment.

## 6. Future modules

The next legitimate architectural additions are:

1. authenticated draft change requests;
2. role-based review and approval;
3. impact diffs against the prior release;
4. versioned cohort assignment;
5. official timetable ingestion;
6. clash evaluation as a separate operational conclusion;
7. institutional case references without encoding discretionary decisions as universal rules.

A database becomes justified when multiple authorised editors require concurrent drafts, permissions and audit history. Published catalogue releases should still be exportable as immutable JSON for deterministic reasoning.
