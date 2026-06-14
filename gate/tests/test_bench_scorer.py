"""Unit tests for the Phase 0 benchmark scorer (pure logic, no I/O)."""

import pytest

from scorer import CRITICAL_FAILURES, Decision, RoleVerdict, TaskResult, decide, score_role


def _results(passes: int, total: int = 5, critical: frozenset = frozenset()) -> list[TaskResult]:
    out = [TaskResult(task_id=f"t{i}", passed=i < passes) for i in range(total)]
    if critical:
        out[0] = TaskResult(task_id=out[0].task_id, passed=out[0].passed, critical_failures=critical)
    return out


def test_task_result_rejects_unknown_critical_failure():
    with pytest.raises(ValueError):
        TaskResult(task_id="x", passed=True, critical_failures=frozenset({"bogus"}))


def test_task_result_accepts_known_critical_failures():
    for cf in CRITICAL_FAILURES:
        TaskResult(task_id="x", passed=False, critical_failures=frozenset({cf}))


def test_score_role_promotes_on_4_of_5_no_critical():
    v = score_role("coder", "model-a", _results(4))
    assert v.promote is True
    assert v.passed == 4 and v.total == 5
    assert v.critical_failures == frozenset()


def test_score_role_promotes_on_5_of_5():
    v = score_role("coder", "model-a", _results(5))
    assert v.promote is True


def test_score_role_rejects_below_threshold():
    v = score_role("coder", "model-a", _results(3))
    assert v.promote is False
    assert "3/5" in v.reason


def test_score_role_rejects_on_any_critical_failure_even_if_4_of_5_pass():
    v = score_role("coder", "model-a", _results(4, critical=frozenset({"secrets"})))
    assert v.promote is False
    assert "secrets" in v.reason


def test_score_role_empty_results():
    v = score_role("coder", "model-a", [])
    assert v.promote is False
    assert v.total == 0 and v.passed == 0


def test_decide_promotes_primary_when_it_passes():
    primary = score_role("coder", "primary-model", _results(5))
    fallback = score_role("coder", "fallback-model", _results(5))
    d = decide(primary, fallback)
    assert d.chosen_model == "primary-model"
    assert "primary candidate primary-model promoted" in d.reason


def test_decide_falls_back_when_primary_fails_but_fallback_passes():
    primary = score_role("coder", "primary-model", _results(2))
    fallback = score_role("coder", "fallback-model", _results(5))
    d = decide(primary, fallback)
    assert d.chosen_model == "fallback-model"
    assert "fallback fallback-model promoted" in d.reason


def test_decide_no_promotion_when_both_fail():
    primary = score_role("coder", "primary-model", _results(2))
    fallback = score_role("coder", "fallback-model", _results(1))
    d = decide(primary, fallback)
    assert d.chosen_model == ""
    assert "NO MODEL PROMOTED" in d.reason


def test_decide_no_promotion_when_fallback_not_evaluated():
    primary = score_role("coder", "primary-model", _results(2))
    d = decide(primary, None)
    assert d.chosen_model == ""
    assert "no fallback evaluated" in d.reason
