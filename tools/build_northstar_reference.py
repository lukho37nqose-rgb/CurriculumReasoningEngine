"""Rebuild the synthetic rules, native records and separate rehearsal metadata."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "northstar"
CODES = ["FOUND-X7", "CORE-Q2", "PATH-Z9", "ALT-V8", "CAP-R4", "LAB-T6"]
SOURCE = "Northstar Academic Rules Registry (synthetic)"


def completed(code):
    return {"type": "course_completed", "course_code": code}


def package():
    expressions = [None, None, completed(CODES[0]),
                   {"type": "all_of", "conditions": [completed(c) for c in CODES[:2]]},
                   {"type": "one_of", "conditions": [completed(c) for c in CODES[2:4]]},
                   {"type": "all_of", "conditions": [
                       {"type": "one_of", "conditions": [completed(c) for c in CODES[2:4]]}, completed(CODES[1])]}]
    courses = []
    for code, title, credits, level, expr in zip(CODES,
            ["Ways of Inquiry", "Systems Foundations", "Systems Studio", "Inquiry Studio", "Synthesis", "Applied Inquiry"],
            [6, 9, 15, 6, 9, 15], [1, 1, 2, 2, 3, 3], expressions, strict=True):
        row = dict(code=code, name=title, credits=credits, nqf_level=level, department="systems",
                   offered=["P-Z", "P-B"], prerequisites=[], verification_status="unverified",
                   source={"reference": SOURCE})
        if expr:
            row["prerequisite_expression"] = dict(expr, verification_status="unverified", source_reference=SOURCE)
        courses.append(row)
    rules = [
        dict(id="foundation", type="course", label="Foundation completion", course_codes=CODES[:1]),
        dict(id="core", type="all_courses", label="Foundation and core completion", course_codes=CODES[:2]),
        dict(id="studio", type="course", label="One studio requirement", course_codes=CODES[2:4], required=1),
        dict(id="studio_credit", type="credit_pool", label="Studio credit requirement", course_codes=CODES[2:4], required=15),
        dict(id="capstone", type="course", label="Capstone completion", course_codes=CODES[4:5]),
        dict(id="route_choices", type="choose_n", label="Two supported preparation routes", required=2, children=[
            dict(type="all_courses", label="Foundation route", course_codes=CODES[:2]),
            dict(type="course", label="Studio route", required=1, course_codes=CODES[2:4]),
            dict(type="course", label="Synthesis route", course_codes=CODES[4:5]),
        ]),
    ]
    for rule in rules:
        rule["verification_status"] = "unverified"
    metric = dict(type="failed_metric", label="Cumulative failed-attempt advisory", temporal_scope="cumulative",
                  metric_basis="course_count", identity="attempt", threshold=2)

    def policy(ident, condition, consequence, label):
        return dict(type="progression_policy", policy_id=ident, verification_status="unverified", source_reference=SOURCE,
                    condition=condition, consequence=dict(type=consequence, label=label))

    programme = dict(
        name="Diploma in Systems Inquiry", programme_type="structured", verification_status="unverified", scope_verified=True,
        total_nqf_credits=45, minimum_duration_years=0, level_7_nqf_credits=0,
        semester_course_equivalents=0, senior_course_equivalents=0, humanities_course_equivalents=0,
        required_majors=0, required_humanities_majors=0,
        required_courses=[CODES[i] for i in [0, 1, 4, 5]], support_course_codes=CODES[2:4], curriculum_rules=rules,
        programme_entry_eligibility=dict(eligibility_spec_id="NS-V1-ENTRY", programme_key="systems_inquiry",
            verification_status="unverified", source_reference=SOURCE,
            condition={"type": "one_of", "conditions": [
                {"type": "course_achievement", "course_code": CODES[0], "comparator": "gte", "threshold": 12,
                 "attempt_selection": "any_qualifying_attempt"},
                {"type": "external_subject_achievement", "qualification_system_id": "ORION-CERT", "subject_id": "OR-MATH", "comparator": "gte", "threshold": 7},
                {"type": "qualification_held", "qualification_system_id": "ORION-CERT", "qualification_id": "ORA-K7"}]}),
        qualification_completion=dict(completion_spec_id="NS-V1-COMPLETION", required_requirement_ids=[r["id"] for r in rules],
                                      source_reference=SOURCE, verification_status="unverified"),
        graduation_eligibility=dict(eligibility_spec_id="NS-V1-GRADUATION", requires_academic_completion=True,
                                   required_clearance_ids=["NS-GATE-A", "NS-GATE-Z"], source_reference=SOURCE, verification_status="unverified"),
        progression_rules=[policy("NS-V1-FAILED-ATTEMPTS", metric, "advisory_risk", "Cumulative failed-attempt advisory"),
            policy("NS-V1-FOUNDATION", dict(type="required_course_pool_incomplete", label="Foundation requirements incomplete", course_codes=CODES[:2]),
                   "progression_ineligible", "Foundation progression prerequisite not met")],
    )
    return courses, dict(catalogue_version="northstar-v1", source=SOURCE, programmes={"systems_inquiry": programme}, majors={},
        award_rules=[dict(id="NS-V1-DISTINCTION", name="Systems Inquiry Achievement", type="qualification_distinction", applies_to="structured",
            verification_status="unverified", source={"reference": SOURCE}, curriculum_rules=[
                dict(id="award_average", type="weighted_average", label="Achievement average", course_codes=CODES, minimum_average=82, weighting={"basis": "credit_value"}),
                dict(id="award_credits", type="credits", label="Award credits", required=30)])],
        institution_sources=[dict(source_id="NS-REGISTRY", institution_id="northstar", release_id="northstar-v1",
                                  source_kind="rules_registry", title=SOURCE, source_status="unverified")],
        requirement_source_relationships=[dict(relationship_id=f"NS-LINK-{r['id']}", institution_id="northstar", release_id="northstar-v1",
            programme_key="systems_inquiry", requirement_id=r["id"], source_id="NS-REGISTRY", relationship_type="DIRECT_RULE_SOURCE",
            locator={"record_id": record_id, "clause": "KAPPA"}, relationship_status="unverified", rule_status="unverified")
            for r, record_id in zip(rules, ["RX-441", "RX-812", "RX-209", "RX-034", "RX-651", "RX-908"], strict=True)])


def records():
    purposes = ["Ordinary progress", "Complete negative evidence", "Partial academic record", "Exact-course recognition",
                "Unknown recognition coverage", "Conflicting recognition", "Alternative completion witness", "Twenty-point achievement",
                "External subject achievement", "Exact prior qualification", "Entry eligibility is not admission", "Explicit registration history",
                "Academic completion without clearance", "Eligible but not awarded", "Explicit award and compound evidence"]
    rows, cases = [], []
    for n, purpose in enumerate(purposes, 1):
        subject = f"NS-{n:03}"
        indices = [0, 1, 2] if n == 1 else [0]
        if n in (7,):
            indices = [0, 1, 2]
        if n >= 13:
            indices = [0, 1, 2, 4, 5]
        if n == 15:
            indices.remove(1)
        modules = [dict(module=CODES[i], score=72, cycle_label="Opening block", attempt=f"{subject}-{i}") for i in indices]
        if n in (8, 11, 15):
            modules[0]["achievement"] = 15
        domains = {"academic": {"modules": modules}}
        if n in (2, 5):
            domains["academic"]["snapshot"] = dict(modules=CODES, completeness="complete")
        if n == 2:
            domains["recognition"] = dict(decisions=[], snapshot=dict(modules=CODES, completeness="complete"))
        if n in (4, 6, 15):
            domains["recognition"] = dict(decisions=[dict(reference=f"REC-{subject}", learning="EXT-77", local_module="CORE-Q2",
                                                         trust="conflict" if n == 6 else "unverified")])
        if n in (9, 15):
            domains["external"] = {"subjects": [dict(reference=f"EXT-{subject}", system="ORION-CERT", subject="OR-MATH", result=8)]}
        if n in (10, 15):
            domains["qualifications"] = {"credentials": [dict(reference=f"QUAL-{subject}", system="ORION-CERT", credential="ORA-K7")]}
        if n in (12, 15):
            domains["registration"] = dict(episodes=[dict(reference=f"H-{subject}-{p}", block=p, route="systems_inquiry", state=s)
                for p, s in [("P-Z", "active"), ("P-B", "interrupted"), ("P-X", "active")]],
                snapshot={"blocks": ["P-Z", "P-B", "P-X"], "completeness": "complete"})
        if n >= 14:
            domains["clearance"] = {"decisions": [dict(reference=f"{subject}-{gate}", gate=gate, decision="satisfied") for gate in ["NS-GATE-A", "NS-GATE-Z"]]}
        if n == 15:
            domains["award"] = {"conferments": [dict(reference="CONF-NS-015", qualification="systems_inquiry", decision="awarded")]}
        rows.append(dict(person=subject, issuer="northstar", edition="northstar-v1", route="systems_inquiry", domains=domains))
        cases.append(dict(subject=subject, purpose=purpose, expected_boundary={
            2: "Absence becomes negative only with both complete coverage domains",
            3: "Partial records remain unresolved", 4: "Recognition creates no local attempt or credit",
            5: "Result coverage alone cannot prove missing recognition", 6: "Conflict is not a failure or success",
            7: "A sufficient alternative witness does not need unused alternatives",
            8: "Achievement 15 is compared on the institution's 0-20 scale, not percentage marks",
            9: "External subject evidence is not a university course result", 10: "Exact credential is not a taxonomy inference",
            11: "Entry eligibility does not establish admission", 12: "History comes from registration episodes, not marks",
            13: "Academic completion does not establish graduation eligibility", 14: "Eligibility is not conferment",
            15: "Only explicit conferment establishes the historical award fact"}.get(n, "Ordinary completion with bounded evidence"),
            expected_student_behavior={
                1: "Show confirmed foundation completion and remaining uncertainty.",
                2: "Show Not met with named complete coverage scopes.",
                3: "Show Not enough information yet, not a shortfall.",
                4: "Show core completion and receipt of recognition separately from results.",
                5: "Show unresolved core completion despite result coverage.",
                6: "Show Conflicting evidence and an advisor review action.",
                7: "Show Met for sufficient alternatives without treating unused branches as failures.",
                8: "Show entry conditions met using a twenty-point achievement witness.",
                9: "Show entry conditions met and a distinct external-achievement receipt.",
                10: "Show entry conditions met and a distinct prior-qualification receipt.",
                11: "Show entry eligibility with the explicit not-admission boundary.",
                12: "Show two active cycles in the advisor history metric.",
                13: "Show academic completion Met and clearance-dependent eligibility unresolved.",
                14: "Show eligibility Met but no recorded formal award.",
                15: "Show explicit recorded award, with source and unverified representation authority.",
            }[n],
            intentionally_unexercised=["formal admission", "course registration/co-requisites", "qualification taxonomy"]))
    return rows, cases


def build(destination=ROOT):
    courses, requirements = package()
    rows, cases = records()
    registry = [dict(record_id=record_id, clause="KAPPA", statement=statement,
                     institution_id="northstar", release_id="northstar-v1", verification_status="unverified",
                     synthetic=True) for record_id, statement in [
        ("RX-441", "Complete FOUND-X7."),
        ("RX-812", "Complete both FOUND-X7 and CORE-Q2."),
        ("RX-209", "Complete at least one of PATH-Z9 and ALT-V8."),
        ("RX-034", "Earn at least 15 course-result credits from PATH-Z9 and ALT-V8."),
        ("RX-651", "Complete CAP-R4."),
        ("RX-908", "Complete at least two routes: both foundation courses; one studio alternative; or CAP-R4. Unused routes need not be complete."),
    ]]
    outputs = {"package/courses.json": courses, "package/degree_requirements.json": requirements,
               "package/registry.json": registry, "records/students.json": rows, "cases.json": cases}
    for path, value in outputs.items():
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        # Preserve the accepted fixture bytes on every build host.
        target.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\r\n")


if __name__ == "__main__":
    build()
