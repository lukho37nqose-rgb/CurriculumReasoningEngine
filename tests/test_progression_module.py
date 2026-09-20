"""Ownership checks complement the existing progression characterization suites."""

import ast
import inspect
import subprocess
import sys

from engine import framework_adapters, progression, rule_engine


def owned_names():
    return [node.name for node in ast.parse(inspect.getsource(progression)).body
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))]


def test_all_domain_symbols_have_one_owner_and_compatible_imports():
    names = owned_names()
    assert len(names) == 66
    old_source = ast.parse(inspect.getsource(rule_engine))
    retained = {node.name for node in old_source.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    for name in names:
        implementation = getattr(progression, name)
        assert implementation.__module__ == "engine.progression"
        assert getattr(rule_engine, name) is implementation
        assert name not in retained
        assert inspect.getsourcefile(implementation) == progression.__file__


def test_domain_imports_without_report_layer():
    code = "import sys; import engine.progression; assert 'engine.rule_engine' not in sys.modules; assert 'app' not in sys.modules"
    subprocess.run([sys.executable, "-B", "-c", code], check=True)


def test_shared_adapters_are_imported_without_duplicate_implementations():
    for name in ("_credit_value", "_is_senior_level", "_load_equivalent"):
        assert getattr(progression, name) is getattr(framework_adapters, name)
        assert name not in owned_names()


def test_report_orchestration_and_unrelated_views_remain_in_rule_engine():
    for name in ("_compute_exclusion_risk", "compute_report", "_academic_level", "Report",
                 "ExclusionRisk", "Requirement", "MajorProgress", "EligibleCourse",
                 "QualificationCompletionAssessment", "SubjectDistinction", "Distinction"):
        assert getattr(rule_engine, name).__module__ == "engine.rule_engine"
        assert not hasattr(progression, name)
    assert not hasattr(progression, "EvaluationContext")
