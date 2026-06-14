"""State-machine coverage for the gate classifier, incl. the four worked examples."""

from classifier import IssueContext, classify


def ctx(num=1, labels=(), **kw):
    return IssueContext(number=num, labels=set(labels), **kw)


# ── The four worked examples from the roadmap (must match exactly) ────────────
def test_example_12_scope_only_triage():
    d = classify(ctx(12, ["AI-GATE-TEST"]))
    assert (d.detected_state, d.intended_action, d.reason) == (
        "scope-only", "would-triage", "no workflow labels")
    assert d.llm == "orchestrator"


def test_example_15_ready_dispatch():
    d = classify(ctx(15, ["AI-GATE-TEST", "role:coder", "ready"], marker_active=False))
    assert (d.detected_state, d.intended_action, d.reason) == (
        "ready", "would-dispatch-coder", "no active marker")
    assert d.llm == "coder"


def test_example_19_in_progress_active_marker_noop():
    d = classify(ctx(19, ["AI-GATE-TEST", "role:coder", "in-progress"], marker_active=True))
    assert (d.detected_state, d.intended_action, d.reason) == (
        "in-progress", "no-action", "active marker not stale")
    assert d.llm is None


def test_example_21_conflicting_roles_unknown():
    d = classify(ctx(21, ["AI-GATE-TEST", "role:coder", "role:cto"]))
    assert (d.detected_state, d.intended_action, d.reason) == (
        "unknown-state", "no-action", "conflicting role labels")


# ── Remaining table rows ──────────────────────────────────────────────────────
def test_merged_pr_closes_issue_first():
    # pr_merged wins even with other labels present
    d = classify(ctx(2, ["AI-GATE-TEST", "role:coder", "in-progress"], pr_merged=True))
    assert d.intended_action == "would-close"


def test_needs_human_waits():
    d = classify(ctx(3, ["AI-GATE-TEST", "needs-human", "role:coder"]))
    assert (d.detected_state, d.intended_action) == ("needs-human", "no-action")


def test_architect_no_plan():
    d = classify(ctx(4, ["AI-GATE-TEST", "role:architect"]))
    assert d.intended_action == "would-invoke-architect"
    assert d.llm == "architect"


def test_plan_ready_waits_without_approval():
    d = classify(ctx(5, ["AI-GATE-TEST", "plan-ready"]))
    assert (d.detected_state, d.intended_action) == ("plan-ready", "no-action")


def test_plan_ready_approve():
    d = classify(ctx(5, ["AI-GATE-TEST", "plan-ready"], approval="approve"))
    assert d.intended_action == "would-create-kickoff"


def test_plan_ready_changes():
    d = classify(ctx(5, ["AI-GATE-TEST", "plan-ready"], approval="changes"))
    assert d.intended_action == "would-reopen-architect"


def test_kickoff_expands():
    d = classify(ctx(6, ["AI-GATE-TEST", "kickoff"]))
    assert d.intended_action == "would-expand-kickoff"
    assert d.llm == "orchestrator"


def test_backlog_blocked_by_deps():
    d = classify(ctx(7, ["AI-GATE-TEST", "role:coder", "backlog"], deps_closed=False))
    assert (d.detected_state, d.intended_action) == ("backlog", "no-action")


def test_backlog_promotes_when_deps_closed():
    d = classify(ctx(7, ["AI-GATE-TEST", "role:coder", "backlog"], deps_closed=True))
    assert d.intended_action == "would-promote-ready"


def test_ready_with_active_marker_noop():
    d = classify(ctx(8, ["AI-GATE-TEST", "role:coder", "ready"], marker_active=True))
    assert d.intended_action == "no-action"


def test_in_progress_recovers_when_stuck():
    d = classify(ctx(9, ["AI-GATE-TEST", "role:coder", "in-progress"],
                      marker_active=False, linked_pr_open=False))
    assert d.intended_action == "would-recover"


def test_in_progress_pr_open_awaits_routing():
    d = classify(ctx(9, ["AI-GATE-TEST", "role:coder", "in-progress"],
                      marker_active=False, linked_pr_open=True))
    assert d.intended_action == "no-action"


def test_cto_invoked_when_pr_no_verdict():
    d = classify(ctx(10, ["AI-GATE-TEST", "role:cto"], linked_pr_open=True,
                      cto_verdict_present=False))
    assert d.intended_action == "would-invoke-cto"
    assert d.llm == "cto"


def test_cto_noop_when_verdict_present():
    d = classify(ctx(10, ["AI-GATE-TEST", "role:cto"], linked_pr_open=True,
                      cto_verdict_present=True))
    assert d.intended_action == "no-action"
