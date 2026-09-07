import pytest
from fixtures.northstar import select_release

from engine.registration import (
    RegistrationHistoryCoverage,
    RegistrationHistoryEvidence,
    evaluate_registration_duration,
)


def _entry(period, programme="systems_inquiry", state="active", ident=None):
    return RegistrationHistoryEvidence(
        ident or f"reg-{period}",
        "N-REG",
        "northstar",
        "northstar-fixture-2027",
        period,
        programme,
        registration_state=state,
        authority="Northstar registry",
        verification_status="verified",
        source_reference="Synthetic registration register",
    )


def _coverage(periods, state="complete"):
    return RegistrationHistoryCoverage(
        "N-REG",
        "northstar",
        "northstar-fixture-2027",
        tuple(periods),
        "Northstar registry",
        "Synthetic registration coverage",
        state,
        "verified",
        "systems_inquiry",
    )


def test_continuous_active_history_counts_cycles():
    release = select_release("northstar", "northstar-fixture-2027")
    result = evaluate_registration_duration(
        tuple(_entry(p) for p in ("NS-27-A", "NS-28-A", "NS-28-B")),
        (_coverage(("NS-27-A", "NS-28-A", "NS-28-B")),),
        student_id="N-REG",
        institution_id="northstar",
        release_id=release.release_id,
        period_scheme=release.period_scheme,
        programme_key="systems_inquiry",
    )
    assert (result.outcome, result.value, result.status) == ("known", 2, "verified")


def test_active_and_elapsed_basis_are_distinct():
    release = select_release("northstar", "northstar-fixture-2027")
    entries = tuple(
        _entry(p, state="interrupted" if p == "NS-28-A" else "active")
        for p in ("NS-27-A", "NS-28-A", "NS-29-A")
    )
    coverage = (_coverage(("NS-27-A", "NS-28-A", "NS-29-A")),)
    active = evaluate_registration_duration(
        entries,
        coverage,
        student_id="N-REG",
        institution_id="northstar",
        release_id=release.release_id,
        period_scheme=release.period_scheme,
        programme_key="systems_inquiry",
    )
    elapsed = evaluate_registration_duration(
        entries,
        coverage,
        student_id="N-REG",
        institution_id="northstar",
        release_id=release.release_id,
        period_scheme=release.period_scheme,
        programme_key="systems_inquiry",
        count_basis="elapsed_academic_cycles",
    )
    assert active.value == 2
    assert elapsed.value == 3


def test_transfer_is_excluded_from_current_programme_scope():
    release = select_release("northstar", "northstar-fixture-2027")
    entries = (_entry("NS-27-A", "alpha"), _entry("NS-28-A", "systems_inquiry"))
    result = evaluate_registration_duration(
        entries,
        (_coverage(("NS-27-A", "NS-28-A")),),
        student_id="N-REG",
        institution_id="northstar",
        release_id=release.release_id,
        period_scheme=release.period_scheme,
        programme_key="systems_inquiry",
    )
    assert result.value == 1


def test_partial_history_is_unresolved_not_authoritative_duration():
    release = select_release("northstar", "northstar-fixture-2027")
    result = evaluate_registration_duration(
        (_entry("NS-28-A"),),
        (),
        student_id="N-REG",
        institution_id="northstar",
        release_id=release.release_id,
        period_scheme=release.period_scheme,
        programme_key="systems_inquiry",
    )
    assert result.outcome == "unresolved"
    assert result.assessment_complete is False


def test_unknown_period_and_wrong_student_are_rejected():
    release = select_release("northstar", "northstar-fixture-2027")
    with pytest.raises(ValueError, match="Unknown academic period"):
        evaluate_registration_duration(
            (_entry("UNKNOWN"),),
            (),
            student_id="N-REG",
            institution_id="northstar",
            release_id=release.release_id,
            period_scheme=release.period_scheme,
            programme_key="systems_inquiry",
        )
    wrong = _entry("NS-27-A")
    object.__setattr__(wrong, "student_id", "OTHER")
    with pytest.raises(ValueError, match="different student"):
        evaluate_registration_duration(
            (wrong,),
            (),
            student_id="N-REG",
            institution_id="northstar",
            release_id=release.release_id,
            period_scheme=release.period_scheme,
            programme_key="systems_inquiry",
        )


def test_history_does_not_create_course_results_or_stage_repeat_evidence():
    entry = _entry("NS-27-A")
    assert not hasattr(entry, "mark")
    assert not hasattr(entry, "repeat_state")
