import inspect
import json
from pathlib import Path
from typing import Any

from engine.rule_engine import _compute_distinction
from tools import build_health_2026 as health_builder


def _requirements() -> dict[str, Any]:
    return json.loads(
        Path("data/uct_health/degree_requirements.json").read_text(encoding="utf-8")
    )


def _programme(key: str) -> dict[str, Any]:
    return _requirements()["programmes"][key]


def _rule_signature(rule: dict[str, Any]) -> dict[str, Any]:
    keys = {
        "type",
        "id",
        "label",
        "children",
        "course_codes",
        "filters",
        "required",
        "minimum_average",
        "minimum_mark",
        "verification_status",
        "status",
        "blocking",
        "assumed_complete",
        "note",
        "weighting",
    }
    return {key: rule[key] for key in sorted(keys) if key in rule}


def _award_signature(award: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": award.get("name"),
        "complete_within_years": award.get("complete_within_years"),
        "curriculum_rules": [
            _rule_signature(rule) for rule in award.get("curriculum_rules", [])
        ],
    }


def _pathway_signature(pathway: dict[str, Any]) -> dict[str, Any]:
    keys = {
        "name",
        "curriculum_rules",
        "progression_rules",
        "verification_status",
        "availability",
        "availability_note",
        "source",
    }
    return {
        **{key: pathway[key] for key in sorted(keys) if key in pathway},
        "award_rules": [
            _award_signature(award) for award in pathway.get("award_rules", [])
        ],
    }


def _mbchb_selection_from_current() -> tuple[dict[int, list[str]], list[str]]:
    current = _programme("mbchb")
    year_groups = {year: [] for year in range(1, 7)}
    for rule in current["curriculum_rules"]:
        rule_id = str(rule.get("id", ""))
        if not rule_id.startswith("mbchb_y"):
            continue
        year = int(rule_id.removeprefix("mbchb_y")[:1])
        year_groups[year].append(rule_id.removeprefix(f"mbchb_y{year}_").upper())
    ssm_rule = next(
        rule
        for rule in current["curriculum_rules"]
        if rule.get("id") == "mbchb_ssm"
    )
    ssm = list(ssm_rule["course_codes"])
    return year_groups, ssm


def test_health_rehabilitation_awards_are_builder_reproducible():
    generated = health_builder.health_rehabilitation_awards()

    for programme_key in (
        "bsc_audiology",
        "bsc_audiology_fundamentals",
        "bsc_speech_language_pathology",
        "bsc_speech_language_pathology_fundamentals",
        "bsc_occupational_therapy",
        "bsc_occupational_therapy_fundamentals",
        "bsc_physiotherapy",
        "bsc_physiotherapy_fundamentals",
    ):
        current = _programme(programme_key)["award_rules"]
        assert [_award_signature(award) for award in generated] == [
            _award_signature(award) for award in current
        ]


def test_cosmetic_diploma_awards_are_builder_reproducible():
    current_programme = _programme("advanced_diploma_cosmetic_formulation")
    course_rows = json.loads(
        Path("data/uct_health/courses.json").read_text(encoding="utf-8")
    )
    courses = {row["code"]: row for row in course_rows}
    generated = health_builder.cosmetic_formulation_awards(
        courses, current_programme["required_courses"]
    )

    assert [_award_signature(award) for award in generated] == [
        _award_signature(award) for award in current_programme["award_rules"]
    ]


def test_bsc_medicine_awards_are_builder_reproducible():
    generated = health_builder.bsc_medicine_awards()
    current = _programme("bsc_medicine")["award_rules"]

    assert [_award_signature(award) for award in generated] == [
        _award_signature(award) for award in current
    ]


def test_mbchb_pathway_awards_and_scoping_are_builder_reproducible():
    year_groups, ssm = _mbchb_selection_from_current()
    generated = health_builder.mbchb_pathway_awards(year_groups, ssm)
    current = _programme("mbchb")["pathways"]

    assert set(generated) == {"gpa_2024_plus", "legacy_pre_2024"}
    assert [_award_signature(award) for award in generated["gpa_2024_plus"]["award_rules"]] == [
        _award_signature(award)
        for award in current["gpa_2024_plus"]["award_rules"]
    ]
    assert [_award_signature(award) for award in generated["legacy_pre_2024"]["award_rules"]] == [
        _award_signature(award)
        for award in current["legacy_pre_2024"]["award_rules"]
    ]
    assert (
        generated["gpa_2024_plus"]["availability"]
        == current["gpa_2024_plus"]["availability"]
    )
    assert (
        generated["legacy_pre_2024"]["availability"]
        == current["legacy_pre_2024"]["availability"]
    )


def test_mbchb_fundamentals_reuses_the_same_pathway_award_semantics():
    mbchb = _programme("mbchb")["pathways"]
    fundamentals = _programme("mbchb_fundamentals")["pathways"]

    assert {
        key: _pathway_signature(value) for key, value in mbchb.items()
    } == {key: _pathway_signature(value) for key, value in fundamentals.items()}


def test_health_weighting_basis_remains_compatibility_default_where_unresolved():
    all_weighted_rules = []
    for programme in _requirements()["programmes"].values():
        for award in programme.get("award_rules", []):
            all_weighted_rules.extend(
                rule
                for rule in award.get("curriculum_rules", [])
                if rule.get("type") == "weighted_average"
            )
        for pathway in programme.get("pathways", {}).values():
            for award in pathway.get("award_rules", []):
                all_weighted_rules.extend(
                    rule
                    for rule in award.get("curriculum_rules", [])
                    if rule.get("type") == "weighted_average"
                )

    assert all_weighted_rules
    assert all("weighting" not in rule for rule in all_weighted_rules)
    assert all("weighting" not in _rule_signature(rule) for rule in all_weighted_rules)


def test_health_legacy_and_professional_manual_boundaries_remain_manual():
    legacy_award = _programme("mbchb")["pathways"]["legacy_pre_2024"]["award_rules"][0]
    legacy_rule = legacy_award["curriculum_rules"][0]
    assert legacy_rule["type"] == "manual"
    assert legacy_rule["status"] == "discretionary"

    mbchb_rules = _programme("mbchb")["curriculum_rules"]
    manual_rule_ids = {
        rule["id"] for rule in mbchb_rules if rule.get("type") == "manual"
    }
    assert {
        "clinical_professional_confirmation",
        "hpcsa_confirmation",
    } <= manual_rule_ids


def test_health_source_archive_authority_is_not_upgraded_by_builder_reproducibility():
    manifest = json.loads(
        Path("governance/releases/uct-2026-uploaded-baseline.manifest.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["source_status"] == "checksum_mismatch_unverified_source_archive"


def test_health_runtime_award_engine_has_no_faculty_specific_award_branch():
    source = inspect.getsource(_compute_distinction)

    assert "uct_health" not in source
    assert "mbchb" not in source.lower()
    assert "cosmetic" not in source.lower()
