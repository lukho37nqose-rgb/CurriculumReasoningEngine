"""Compatibility and dependency boundary for the three shared adapters."""

import subprocess
import sys
from unittest.mock import Mock

import pytest

from engine import framework_adapters, rule_engine
from engine.models import CourseResult


@pytest.mark.parametrize("name", ["_credit_value", "_is_senior_level", "_load_equivalent"])
def test_rule_engine_reexports_same_function(name):
    assert getattr(rule_engine, name) is getattr(framework_adapters, name)


def test_explicit_frameworks_receive_original_item_and_propagate_errors():
    item = CourseResult("OPAQUE", "Opaque", 1, 7, 60, None)
    for name, method, value in [
        ("_credit_value", "credit_value", 23),
        ("_is_senior_level", "is_senior_level", True),
        ("_load_equivalent", "load_equivalent", 0.25),
    ]:
        framework = Mock()
        getattr(framework, method).return_value = value
        helper = getattr(framework_adapters, name)
        assert helper(item, framework) == value
        getattr(framework, method).assert_called_once_with(item)
        assert getattr(framework, method).call_args.args[0] is item
        error = ValueError("framework error")
        getattr(framework, method).side_effect = error
        with pytest.raises(ValueError) as caught:
            helper(item, framework)
        assert caught.value is error
    assert item.nqf_level == 1 and item.nqf_credits == 7


@pytest.mark.parametrize("level,senior", [(5, False), (6, True), (7, True)])
def test_none_preserves_legacy_values_and_load(level, senior):
    item = CourseResult("AAA1001W", "A", level, 18, 70, None)
    assert framework_adapters._credit_value(item, None) == 18
    assert framework_adapters._is_senior_level(item, None) is senior
    assert framework_adapters._load_equivalent(item, None) == 2.0
    assert framework_adapters._load_equivalent("AAA1001W", None) == 2.0
    assert framework_adapters._load_equivalent("OPAQUE", None) == 1.0


def test_independent_import_has_no_upward_dependency():
    script = "import sys; import engine.framework_adapters; assert 'engine.rule_engine' not in sys.modules"
    subprocess.run([sys.executable, "-B", "-c", script], check=True)
