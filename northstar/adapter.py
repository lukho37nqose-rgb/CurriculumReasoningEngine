"""Native records -> existing analysis input; no reasoning or scenario outcomes."""

from dataclasses import dataclass

from .package import CODES, INSTITUTION, PROGRAMME, RELEASE, read_package

DOMAIN_NAMES = ("academic", "recognition", "external", "qualifications", "registration", "clearance", "award")
PERIOD_LABELS = {"Opening block": "P-Z", "Middle block": "P-A", "Closing block": "P-M"}


@dataclass(frozen=True)
class AdaptedRecord:
    body: dict
    domain_receipt: tuple[dict, ...]


def adapt(record, session):
    if (record.get("person"), record.get("issuer"), record.get("edition"), record.get("route")) != (
            session.subject_reference, session.institution_id, RELEASE, PROGRAMME):
        raise ValueError("Record does not match the authenticated launch scope")
    body = dict(institution_id=INSTITUTION, release_id=RELEASE, faculty="systems", programme_key=PROGRAMME,
                programme="Diploma in Systems Inquiry", student_id=session.subject_reference,
                subject_reference=session.subject_reference, name=session.subject_reference,
                context_provenance="SYNTHETIC_IDENTITY", launch_request_id=session.launch_request_id, results=[])
    receipt = []
    domains = record.get("domains", {})
    if not isinstance(domains, dict):
        raise ValueError("Invalid records-domain envelope")
    for domain in DOMAIN_NAMES:
        if domain not in domains:
            receipt.append(dict(domain=domain, state="NOT_SUPPLIED"))
            continue
        try:
            data = domains[domain]
            if not isinstance(data, dict):
                raise ValueError("Malformed domain")
            converted = _domain(domain, data, session.subject_reference)
        except (KeyError, TypeError, ValueError):
            # Drop the whole branch including coverage; malformed is never empty-complete.
            receipt.append(dict(domain=domain, state="UNAVAILABLE_OR_MALFORMED"))
        else:
            body.update(converted)
            receipt.append(dict(domain=domain, state="RECEIVED"))
    return AdaptedRecord(body, tuple(receipt))


def _domain(domain, data, subject):
    common = dict(authority="Northstar synthetic registrar", source_reference="Northstar synthetic student register",
                  verification_status="unverified")

    def fact(row):
        if not isinstance(row, dict):
            raise ValueError("Expected a native evidence record")
        if row.get("edition", RELEASE) != RELEASE or row.get("person", subject) != subject or row.get("issuer", INSTITUTION) != INSTITUTION:
            raise ValueError("Evidence scope mismatch")
        status = row.get("trust", "unverified")
        if status not in {"verified", "unverified", "conflict", "provisional"}:
            raise ValueError("Invalid evidence authority")
        for key in ("reference", "learning", "attempt", "system", "subject", "credential", "qualification", "route", "gate"):
            if key in row and (not isinstance(row[key], str) or not row[key].strip()):
                raise ValueError("Invalid institutional identifier")
        return dict(common, verification_status=status)

    def scope(snapshot, key):
        values = snapshot[key]
        if not isinstance(values, list) or not values or not all(isinstance(x, str) for x in values):
            raise ValueError("Invalid scope")
        if snapshot["completeness"] not in {"complete", "partial", "unknown"}:
            raise ValueError("Invalid completeness")
        return values

    output = {}
    if domain == "academic":
        catalogue = {c["code"]: c for c in read_package("courses.json")}
        rows = []
        for row in data["modules"]:
            fact(row)
            if "trust" in row and row["trust"] != "verified":
                # CourseResult has no per-result authority slot. Withhold rather than erase a qualifier.
                raise ValueError("Qualified local result cannot be faithfully represented")
            course = catalogue[row["module"]]
            score = row.get("score")
            if score is not None and (isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 100):
                raise ValueError("Invalid score")
            achievement = row.get("achievement")
            if achievement is not None and (isinstance(achievement, bool) or not isinstance(achievement, (int, float)) or not 0 <= achievement <= 20):
                raise ValueError("Invalid achievement")
            rows.append(dict(code=course["code"], name=course["name"], nqf_credits=course["credits"], nqf_level=course["nqf_level"],
                             mark=score, achievement_value=achievement, academic_period_key=PERIOD_LABELS[row["cycle_label"]], attempt_id=row["attempt"]))
        output["results"] = rows
        if "snapshot" in data:
            snapshot = data["snapshot"]
            codes = scope(snapshot, "modules")
            if not set(codes) <= set(CODES):
                raise ValueError("Unknown coverage module")
            output["academic_record_coverage"] = [dict(fact(snapshot), course_codes=codes, coverage_state=snapshot["completeness"])]
    elif domain == "recognition":
        rows = []
        for row in data["decisions"]:
            if row["local_module"] not in CODES:
                raise ValueError("Unknown recognition target")
            rows.append(dict(fact(row), recognition_id=row["reference"], target_course_code=row["local_module"],
                             source_learning_identity=row["learning"]))
        output["course_completion_recognition"] = rows
        if "snapshot" in data:
            snapshot = data["snapshot"]
            codes = scope(snapshot, "modules")
            if not set(codes) <= set(CODES):
                raise ValueError("Unknown recognition scope")
            if snapshot["completeness"] == "complete":
                output["recognition_coverage"] = [dict(fact(snapshot), course_codes=codes)]
    elif domain == "external":
        output["external_subject_achievement_evidence"] = [dict(fact(row), evidence_id=row["reference"],
            qualification_system_id=row["system"], subject_id=row["subject"], achievement_value=row["result"]) for row in data["subjects"]]
    elif domain == "qualifications":
        output["prior_qualification_evidence"] = [dict(fact(row), evidence_id=row["reference"],
            qualification_system_id=row["system"], qualification_id=row["credential"]) for row in data["credentials"]]
    elif domain == "registration":
        rows = []
        for row in data["episodes"]:
            if row["block"] not in {"P-Z", "P-A", "P-M", "P-B", "P-X"} or row["state"] not in {"active", "interrupted"}:
                raise ValueError("Unknown registration coordinate")
            rows.append(dict(fact(row), evidence_id=row["reference"], academic_period_key=row["block"],
                             programme_key=row["route"], registration_state=row["state"]))
        output["registration_history"] = rows
        if "snapshot" in data:
            snapshot = data["snapshot"]
            blocks = scope(snapshot, "blocks")
            if not set(blocks) <= {"P-Z", "P-A", "P-M", "P-B", "P-X"} or snapshot["completeness"] == "unknown":
                raise ValueError("Unknown registration scope")
            output["registration_history_coverage"] = [dict(fact(snapshot), academic_period_keys=blocks,
                programme_key=PROGRAMME, coverage_state=snapshot["completeness"])]
    elif domain == "clearance":
        rows = []
        for row in data["decisions"]:
            if row["decision"] not in {"satisfied", "not_satisfied", "unresolved", "conflict"}:
                raise ValueError("Invalid clearance")
            rows.append(dict(fact(row), evidence_id=row["reference"], clearance_id=row["gate"], outcome=row["decision"]))
        output["graduation_clearances"] = rows
    elif domain == "award":
        rows = []
        for row in data["conferments"]:
            if row["decision"] not in {"awarded", "not_awarded"}:
                raise ValueError("Invalid conferment")
            rows.append(dict(fact(row), award_evidence_id=row["reference"], qualification_key=row["qualification"],
                             outcome=row["decision"], applicable_release_id=RELEASE))
        output["qualification_award_evidence"] = rows
    return output
