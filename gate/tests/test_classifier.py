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


# ── BUG-5: human-initiated bounce of a held coder PR ──────────────────────────
def test_needs_human_changes_with_open_pr_bounces_coder():
    d = classify(ctx(61, ["AI-GATE-TEST", "needs-human"],
                      approval="changes", linked_pr_open=True, changes_fresh=True))
    assert (d.detected_state, d.intended_action, d.reason) == (
        "needs-human", "would-bounce-coder", "owner requested changes on held PR")


def test_needs_human_changes_without_pr_stays_dead_stop():
    # CHANGES: but no open PR -> nothing to bounce -> unchanged dead stop
    d = classify(ctx(61, ["AI-GATE-TEST", "needs-human"],
                      approval="changes", changes_fresh=True))
    assert d.intended_action == "no-action"


def test_needs_human_stale_changes_does_not_rebounce():
    # CHANGES: present + open PR, but already acted on (not fresh) -> no loop
    d = classify(ctx(61, ["AI-GATE-TEST", "needs-human"],
                      approval="changes", linked_pr_open=True, changes_fresh=False))
    assert d.intended_action == "no-action"


def test_needs_human_approve_does_not_bounce():
    # only CHANGES: triggers a bounce; an APPROVE on a held PR is still a human merge
    d = classify(ctx(61, ["AI-GATE-TEST", "needs-human"],
                      approval="approve", linked_pr_open=True))
    assert d.intended_action == "no-action"


def test_merged_pr_still_wins_over_needs_human_bounce():
    d = classify(ctx(61, ["AI-GATE-TEST", "needs-human"],
                      approval="changes", linked_pr_open=True, changes_fresh=True,
                      pr_merged=True))
    assert d.intended_action == "would-close"


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
    d = classify(ctx(5, ["AI-GATE-TEST", "plan-ready"], approval="changes", changes_fresh=True))
    assert d.intended_action == "would-reopen-architect"


def test_plan_ready_stale_changes_does_not_reopen_architect():
    # BUG-6: a CHANGES: already acted on (architect revised, newer marker) must not reopen
    # the architect again — wait for the owner to respond to the revised plan.
    d = classify(ctx(5, ["AI-GATE-TEST", "plan-ready"], approval="changes", changes_fresh=False))
    assert d.intended_action == "no-action"


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


def test_in_progress_pr_open_routes_to_cto():
    # an open PR routes to review immediately, even with a still-active marker
    for active in (False, True):
        d = classify(ctx(9, ["AI-GATE-TEST", "role:coder", "in-progress"],
                          marker_active=active, linked_pr_open=True))
        assert d.intended_action == "would-route-cto"


def test_cto_invoked_when_pr_no_verdict():
    d = classify(ctx(10, ["AI-GATE-TEST", "role:cto"], linked_pr_open=True,
                      cto_verdict_present=False))
    assert d.intended_action == "would-invoke-cto"
    assert d.llm == "cto"


def test_cto_noop_when_verdict_present():
    d = classify(ctx(10, ["AI-GATE-TEST", "role:cto"], linked_pr_open=True,
                      cto_verdict_present=True))
    assert d.intended_action == "no-action"
