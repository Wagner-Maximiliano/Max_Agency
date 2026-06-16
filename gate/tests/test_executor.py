"""Phase 2B: mutation planner (pure) + gh writer argv construction."""

from classifier import Decision, IssueContext, classify
from executor import GitHubWriter, plan_actions

RUN = "2026-06-14T00:00:00Z-test"
SCOPE = "AI-GATE-TEST"


def dec(num, action, state="s", reason="r", llm=None):
    return Decision(num, state, action, reason, llm)


# ── planner: deterministic actions produce the right ops ──────────────────────
def test_promote_plan():
    ops = plan_actions(dec(7, "would-promote-ready"), IssueContext(7), RUN, SCOPE)
    assert ops == [{"op": "edit_labels", "issue": 7, "add": ["ready"], "remove": ["backlog"]}]


def test_close_plan():
    ops = plan_actions(dec(5, "would-close"), IssueContext(5), RUN, SCOPE)
    assert ops[0]["op"] == "close" and ops[0]["reason"] == "completed"


def test_reopen_architect_plan():
    ctx = IssueContext(11, marker_comment_id="c1")
    ops = plan_actions(dec(11, "would-reopen-architect"), ctx, RUN, SCOPE, ts="T")
    kinds = [o["op"] for o in ops]
    assert kinds == ["edit_labels", "comment", "upsert_marker"]
    assert ops[0]["add"] == ["role:architect"] and ops[0]["remove"] == ["plan-ready"]
    assert "changes-routed" in ops[2]["body"] and ops[2]["comment_id"] == "c1"


def test_create_kickoff_plan():
    ctx = IssueContext(11, title="build a thing", marker_comment_id=None)
    ops = plan_actions(dec(11, "would-create-kickoff"), ctx, RUN, SCOPE, ts="T")
    assert ops[0]["op"] == "create_issue"
    assert ops[0]["labels"] == [SCOPE, "kickoff"]
    assert "[AI-11] kickoff: build a thing" == ops[0]["title"]
    assert ops[1]["op"] == "upsert_marker" and "kickoff-created" in ops[1]["body"]


def test_llm_actions_produce_no_ops():
    for action in ("would-triage", "would-dispatch-coder", "would-invoke-architect",
                   "would-invoke-cto", "would-recover", "no-action"):
        assert plan_actions(dec(1, action), IssueContext(1), RUN, SCOPE) == []


# ── Phase 2C: triage verdict → ops (label first, then rationale comment) ───────
def test_plan_triage_ops_coder_enters_ready_then_comment():
    from executor import plan_triage_ops
    ops = plan_triage_ops(7, "role:coder", "small single-file fix")
    # coder enters the lane at `ready` (coherent next state, not lone role:coder)
    assert ops[0] == {"op": "edit_labels", "issue": 7,
                      "add": ["role:coder", "ready"], "remove": []}
    assert ops[1]["op"] == "comment"
    assert "role:coder" in ops[1]["body"] and "small single-file fix" in ops[1]["body"]


def test_plan_triage_ops_architect_single_label():
    from executor import plan_triage_ops
    ops = plan_triage_ops(8, "role:architect", "needs a plan")
    assert ops[0]["add"] == ["role:architect"]


def test_plan_triage_ops_no_comment_when_reason_blank():
    from executor import plan_triage_ops
    ops = plan_triage_ops(7, "needs-human", "")
    assert len(ops) == 1 and ops[0]["op"] == "edit_labels"
    assert ops[0]["add"] == ["needs-human"]


# ── idempotency: once a kickoff marker exists, classifier stops re-creating ───
def test_kickoff_idempotent_via_marker():
    base = dict(labels={SCOPE, "plan-ready"}, approval="approve")
    assert classify(IssueContext(11, **base)).intended_action == "would-create-kickoff"
    done = classify(IssueContext(11, kickoff_created=True, **base))
    assert done.intended_action == "no-action"
    assert plan_actions(done, IssueContext(11, kickoff_created=True, **base), RUN, SCOPE) == []


# ── writer: correct gh argv per op (runner mocked) ────────────────────────────
def _capture():
    calls = []
    return calls, (lambda args: calls.append(args) or "")


def test_writer_edit_labels_adds_before_removes_in_separate_calls():
    # adds and removes are separate gh calls (adds first) so a missing label can't
    # half-strip the issue (a mixed gh call applies non-atomically).
    calls, runner = _capture()
    GitHubWriter("o/r", runner=runner).apply(
        {"op": "edit_labels", "issue": 7, "add": ["ready"], "remove": ["backlog"]})
    assert calls[0] == ["issue", "edit", "7", "--repo", "o/r", "--add-label", "ready"]
    assert calls[1] == ["issue", "edit", "7", "--repo", "o/r", "--remove-label", "backlog"]


def test_writer_edit_labels_add_failure_skips_removes():
    seen = []

    def runner(args):
        seen.append(args)
        if "--add-label" in args:
            raise RuntimeError("'role:cto' not found")
        return ""

    try:
        GitHubWriter("o/r", runner=runner).apply(
            {"op": "edit_labels", "issue": 7, "add": ["role:cto"],
             "remove": ["role:coder", "in-progress"]})
    except RuntimeError:
        pass
    # the failed add must run before (and prevent) any remove
    assert all("--remove-label" not in a for a in seen)


def test_writer_close():
    calls, runner = _capture()
    GitHubWriter("o/r", runner=runner).apply(
        {"op": "close", "issue": 5, "reason": "completed", "comment": "done"})
    assert calls[0] == ["issue", "close", "5", "--repo", "o/r",
                        "--reason", "completed", "--comment", "done"]


def test_writer_create_issue():
    calls, runner = _capture()
    GitHubWriter("o/r", runner=runner).apply(
        {"op": "create_issue", "title": "T", "body": "B", "labels": ["AI-GATE-TEST", "kickoff"]})
    assert calls[0] == ["issue", "create", "--repo", "o/r", "--title", "T", "--body", "B",
                        "--label", "AI-GATE-TEST", "--label", "kickoff"]


def test_writer_upsert_marker_edits_node_id_via_graphql():
    # `gh ... --json comments` yields a GraphQL node id (IC_…); REST PATCH 404s on it,
    # so an in-place edit must go through the GraphQL updateIssueComment mutation.
    calls, runner = _capture()
    GitHubWriter("o/r", runner=runner).apply(
        {"op": "upsert_marker", "issue": 11, "comment_id": "IC_kwDOabc", "body": "M"})
    assert calls[0][:2] == ["api", "graphql"]
    assert "updateIssueComment" in calls[0][3]
    assert "id=IC_kwDOabc" in calls[0] and "body=M" in calls[0]


def test_writer_upsert_marker_edits_numeric_id_via_rest():
    calls, runner = _capture()
    GitHubWriter("o/r", runner=runner).apply(
        {"op": "upsert_marker", "issue": 11, "comment_id": "12345", "body": "M"})
    assert calls[0] == ["api", "repos/o/r/issues/comments/12345", "-X", "PATCH", "-f", "body=M"]


def test_writer_upsert_marker_creates_when_no_id():
    calls, runner = _capture()
    GitHubWriter("o/r", runner=runner).apply(
        {"op": "upsert_marker", "issue": 11, "comment_id": None, "body": "M"})
    assert calls[0] == ["issue", "comment", "11", "--repo", "o/r", "--body", "M"]
