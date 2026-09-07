from types import SimpleNamespace

from curriculum_advisor.presentation import presentation_context_from_request, student_reasoning_view


def _report(outcome="unresolved", status="unverified"):
    return SimpleNamespace(
        requirements=[SimpleNamespace(id="R1", label="Core requirement", complete=False, outcome="unsupported" if status == "unsupported" else outcome, assessment_complete=False, status=status, detail="Missing evidence", explanation="")],
        progression_policy_assessments=[], qualification_completion=None,
        graduation_eligibility_assessment=None,
    )


def test_unresolved_is_not_projected_as_not_met():
    view = student_reasoning_view(_report(status="unresolved"))
    item = view["conclusions"][0]
    assert item["outcome"] == "unresolved"
    assert item["outcome_label"] == "Not enough information yet"
    assert item["next_action"] == "SUPPLY_EVIDENCE"


def test_projection_exposes_blocked_boundaries_and_no_engine_re_evaluation():
    view = student_reasoning_view(_report(status="unsupported"))
    assert view["conclusions"][0]["outcome"] == "unsupported"
    assert any("does not make" in item for item in view["limitations"])


def test_missing_source_is_not_projected_as_a_source_entry():
    view = student_reasoning_view(_report())
    conclusion = view["conclusions"][0]
    assert conclusion["source_references"] == []
    assert conclusion["source_missing"] is True
    assert view["source_directory"] == []


def test_direct_assessment_source_has_explicit_relationship():
    report = _report()
    report.progression_policy_assessments = [SimpleNamespace(
        policy_id="P1", consequence_label="Academic risk", outcome="satisfied",
        assessment_complete=True, status="unverified", source_reference="Handbook p. 4",
        detail="Policy evaluated.", consequence_established=True,
    )]
    view = student_reasoning_view(report)
    source = view["conclusions"][1]["source_references"][0]
    assert source["relationship"] == "DIRECT_RULE_SOURCE"
    assert source["locator"] == "Handbook p. 4"
    assert view["source_relationships"][0]["conclusion_id"] == "P1"


def test_receipt_and_launch_context_are_request_derived_and_non_evidential():
    context = presentation_context_from_request(
        {"institution_id": "northstar", "release_id": "r1", "programme_key": "p1",
         "context_provenance": "INSTITUTIONAL_LAUNCH", "subject_reference": "subject-1"},
        academic_record_supplied=False,
    )
    view = student_reasoning_view(_report(), context=context)
    assert view["evidence_receipt"]["academic_record"] == "NOT_SUPPLIED"
    assert view["launch_context"]["context_provenance"] == "INSTITUTIONAL_LAUNCH"
    assert view["launch_context"]["subject_reference"] == "subject-1"
    assert "admission" not in view["evidence_receipt"]
