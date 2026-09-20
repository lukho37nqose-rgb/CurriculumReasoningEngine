import inspect
import json
from pathlib import Path
from typing import Any

from engine import award_policy
from engine.curriculum import CurriculumEvaluator
from engine.rule_engine import _compute_distinction
from tools import build_commerce_2026 as commerce_builder

COMMERCE_STATUS_TREATMENT = {
    "AB": "zero",
    "DPR": "zero",
    "INC": "zero",
    "EXA": "zero",
}


def _requirements() -> dict[str, Any]:
    return json.loads(Path("data/uct_commerce/degree_requirements.json").read_text())


def _programme(key: str) -> dict[str, Any]:
    return _requirements()["programmes"][key]


def _spec(code: str) -> dict[str, Any]:
    return next(spec for spec in commerce_builder.route_specs() if spec["code"] == code)


def _degree_average_rule(awards: list[dict[str, Any]]) -> dict[str, Any]:
    return awards[0]["curriculum_rules"][0]


def _all_codes_from_current_programme(key: str) -> list[str]:
    return list(_degree_average_rule(_programme(key)["award_rules"])["course_codes"])


def _generated_awards_for(programme_key: str) -> list[dict[str, Any]]:
    code = programme_key.upper()
    return commerce_builder.degree_award_rules(
        _spec(code),
        _all_codes_from_current_programme(programme_key),
    )


def _award_signature(award: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": award.get("name"),
        "complete_within_years": award.get("complete_within_years"),
        "curriculum_rules": [_rule_signature(rule) for rule in award.get("curriculum_rules", [])],
    }


def _rule_signature(rule: dict[str, Any]) -> dict[str, Any]:
    keys = {
        "type",
        "id",
        "label",
        "course_codes",
        "required",
        "minimum_average",
        "minimum_mark",
        "minimum_mark_count",
        "mandatory_course_codes",
        "level_weights",
        "include_failed_as_zero",
        "status_treatment",
        "verification_status",
        "status",
        "blocking",
        "assumed_complete",
        "note",
    }
    return {key: rule[key] for key in sorted(keys) if key in rule}


def test_builder_degree_average_rules_preserve_stage7s_status_treatment():
    generated = [
        _degree_average_rule(
            commerce_builder.degree_award_rules(
                spec,
                ["ACC1021F", "ACC1022Z"],
            )
        )
        for spec in commerce_builder.route_specs()
        if spec["family"] != "advanced"
    ]

    assert len(generated) == 68
    assert all(rule["status_treatment"] == COMMERCE_STATUS_TREATMENT for rule in generated)


def test_generated_bcom_degree_award_semantics_match_governed_package():
    current = _programme("cb001eco02")["award_rules"]
    generated = _generated_awards_for("cb001eco02")

    assert [_award_signature(award) for award in generated] == [
        _award_signature(award) for award in current
    ]


def test_generated_iop_manual_award_semantics_match_governed_package():
    current = _programme("cb004bus28")["award_rules"]
    generated = _generated_awards_for("cb004bus28")

    current_iop = next(
        award for award in current if award["name"] == "Industrial and Organisational Psychology subject distinction"
    )
    generated_iop = next(
        award for award in generated if award["name"] == "Industrial and Organisational Psychology subject distinction"
    )

    assert _award_signature(generated_iop) == _award_signature(current_iop)


def test_generated_advanced_actuarial_conflict_semantics_match_governed_package():
    current = _programme("cu020bus01")["award_rules"]
    generated = commerce_builder.degree_award_rules(_spec("CU020BUS01"), [])

    assert [_award_signature(award) for award in generated] == [
        _award_signature(award) for award in current
    ]
    assert generated[0]["curriculum_rules"][0]["verification_status"] == "conflict"


def test_builder_preserves_unknown_configured_status_treatment_tokens():
    rule = commerce_builder.first_attempt_weighted_average_rule(
        rule_id="synthetic_average",
        label="Synthetic average",
        course_codes=["OPAQUE_A", "OPAQUE_B"],
        minimum_average=75,
        level_weights={"5": 1},
        status_treatment={"VOID": "exclude"},
    )

    assert rule["status_treatment"] == {"VOID": "exclude"}
    assert "VOID" not in inspect.getsource(CurriculumEvaluator.evaluate)


def test_generated_package_preserves_source_authority_distinction_for_exa():
    programme = _programme("cb001eco02")
    notes = " ".join(programme["progression_notes"] + programme["award_notes"])
    generated_rule = _degree_average_rule(_generated_awards_for("cb001eco02"))

    assert "AB, DPR and INC contribute zero" in notes
    assert "EXA" not in notes
    assert generated_rule["status_treatment"]["EXA"] == "zero"


def test_generation_does_not_upgrade_commerce_source_archive_authority():
    manifest = json.loads(
        Path("governance/releases/uct-2026-uploaded-baseline.manifest.json").read_text()
    )

    assert manifest["source_status"] == "checksum_mismatch_unverified_source_archive"


def test_stage7t_architecture_guards_generation_and_runtime_boundaries():
    evaluator_source = inspect.getsource(CurriculumEvaluator.evaluate)
    distinction_source = inspect.getsource(_compute_distinction) + "\n" + inspect.getsource(award_policy)
    builder_source = inspect.getsource(commerce_builder.first_attempt_weighted_average_rule)

    for token in ("AB", "DPR", "INC", "EXA"):
        assert token not in evaluator_source
        assert token not in distinction_source
    assert "status_treatment" in builder_source
    assert "uct_commerce" not in builder_source
