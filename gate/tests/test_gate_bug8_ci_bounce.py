"""BUG-8: CI-failure -> coder feedback loop (auto-fix red CI before the CTO reviews).

A coder PR opens but CI is red (lint / typography / a failing test). The gate must NOT route
it to the CTO (a pure reviewer only ever sees green PRs). Instead it pulls the failing CI log,
bounces the PR back to the coder with that log as feedback (reusing the BUG-7 channel), and
bumps the attempt. Exhausting --max-attempts parks it `needs-human` with the PR left open.
Pending CI waits; green CI routes to review as before. All deterministic (no LLM in the bounce).
"""

import json

import executor
import gate
from classifier import IssueContext, classify


# ── ci_status (tri-state rollup) ──────────────────────────────────────────────
def test_ci_status_empty_is_green():
    assert gate.ci_status(None) == "green"
    assert gate.ci_status([]) == "green"


def test_ci_status_all_passing_is_green():
    assert gate.ci_status([{"state": "SUCCESS"}, {"status": "COMPLETED",
                                                  "conclusion": "SUCCESS"}]) == "green"


def test_ci_status_failure_is_red():
    assert gate.ci_status([{"status": "COMPLETED", "conclusion": "FAILURE"}]) == "red"
    assert gate.ci_status([{"state": "ERROR"}]) == "red"


def test_ci_status_pending_when_running_and_none_failed():
    assert gate.ci_status([{"status": "IN_PROGRESS"}]) == "pending"
    assert gate.ci_status([{"state": "PENDING"}]) == "pending"


def test_ci_status_failure_dominates_pending_regardless_of_order():
    rollup = [{"status": "IN_PROGRESS"}, {"status": "COMPLETED", "conclusion": "FAILURE"}]
    assert gate.ci_status(rollup) == "red"


def test_ci_is_green_delegates():
    assert gate.ci_is_green([]) is True
    assert gate.ci_is_green([{"conclusion": "FAILURE"}]) is False
    assert gate.ci_is_green([{"status": "QUEUED"}]) is False


# ── classifier routing ───────────────────────────────────────────────────────
def _coder_inprogress(ci):
    return IssueContext(number=61, labels={"role:coder", "in-progress"},
                        linked_pr_open=True, ci=ci, attempt=1)


def test_classify_ci_red_bounces():
    d = classify(_coder_inprogress("red"))
    assert d.intended_action == "would-bounce-ci"
    assert d.llm is None  # deterministic


def test_classify_ci_pending_waits():
    d = classify(_coder_inprogress("pending"))
    assert d.intended_action == "no-action"


def test_classify_ci_green_routes_to_cto():
    d = classify(_coder_inprogress("green"))
    assert d.intended_action == "would-route-cto"


def test_classify_default_ci_routes_to_cto():
    """Back-compat: an IssueContext with no CI info defaults green -> route to review."""
    d = classify(IssueContext(number=7, labels={"role:coder", "in-progress"},
                              linked_pr_open=True))
    assert d.intended_action == "would-route-cto"


# ── pure planners ─────────────────────────────────────────────────────────────
def test_plan_bounce_ci_ops_shape_and_log():
    ops = executor.plan_bounce_ci_ops(61, 63, 2, "rid", "c1",
                                      ci_log="E501 line too long\nspell: teh -> the",
                                      ts="2026-06-19T00:00:00Z")
    kinds = [o["op"] for o in ops]
    assert kinds == ["comment", "close_pr", "edit_labels", "upsert_marker"]
    assert ops[0]["body"].startswith(executor.CI_FEEDBACK_PREFIX)
    assert "E501 line too long" in ops[0]["body"]  # log fenced into the feedback comment
    assert ops[1] == {"op": "close_pr", "pr": 63, "comment": ops[1]["comment"]}
    assert ops[2]["add"] == ["role:coder", "ready"] and ops[2]["remove"] == ["in-progress"]
    assert "status: ci-bounced" in ops[3]["body"] and "attempt: 2" in ops[3]["body"]


def test_plan_bounce_ci_ops_without_log_still_bounces():
    ops = executor.plan_bounce_ci_ops(61, 63, 1, "rid", None, ci_log="")
    assert [o["op"] for o in ops] == ["comment", "close_pr", "edit_labels", "upsert_marker"]
    assert "```" not in ops[0]["body"]  # no empty fenced block when the log is unavailable


def test_plan_ci_escalation_ops_parks_human_leaves_pr():
    ops = executor.plan_ci_escalation_ops(61, 3, "rid", "c1", ts="2026-06-19T00:00:00Z")
    kinds = [o["op"] for o in ops]
    assert kinds == ["edit_labels", "comment", "upsert_marker"]
    assert ops[0]["add"] == ["needs-human"] and ops[0]["remove"] == ["in-progress"]
    assert "close_pr" not in kinds  # PR left open for human inspection
    assert "status: ci-escalated" in ops[2]["body"]


# ── feedback forwarding ───────────────────────────────────────────────────────
def test_latest_coder_feedback_recognizes_ci_comment():
    comments = [{"authorAssociation": "NONE",
                 "body": executor.CI_FEEDBACK_PREFIX + " ...\n```\nE501 too long\n```"}]
    fb = gate.latest_coder_feedback(comments)
    assert fb.startswith(executor.CI_FEEDBACK_PREFIX) and "E501 too long" in fb


# ── log fetch (best-effort, untrusted, truncated) ─────────────────────────────
def test_fetch_failed_ci_log_truncates_tail():
    big = "x" * 9000
    def _json(args):
        assert args[:2] == ["run", "list"]
        return [{"databaseId": 999, "conclusion": "failure"}]
    def _text(args):
        assert args[:2] == ["run", "view"] and "--log-failed" in args
        return big + "FINAL_ERROR"
    out = _run_fetch(_json, _text)
    assert out.startswith("...(truncated)")
    assert "FINAL_ERROR" in out and len(out) <= gate.CI_LOG_CAP + 32


def test_fetch_failed_ci_log_failsafe_no_runs():
    out = _run_fetch(lambda a: [], lambda a: "")
    assert out == ""


def _run_fetch(json_fn, text_fn, monkeypatch=None):
    """Helper: call fetch_failed_ci_log with gh_json/gh_text swapped (no monkeypatch fixture)."""
    orig_json, orig_text = gate.gh_json, gate.gh_text
    gate.gh_json, gate.gh_text = json_fn, text_fn
    try:
        return gate.fetch_failed_ci_log("o/r", "max-agency/issue-61/attempt-1", lambda *a, **k: None)
    finally:
        gate.gh_json, gate.gh_text = orig_json, orig_text


# ── end-to-end through gate.main ──────────────────────────────────────────────
class _RecordingWriter:
    def __init__(self, *a, **k):
        self.ops = []

    def apply(self, op):
        self.ops.append(op)


def _started_marker(attempt=1):
    return executor.render_marker({"run_id": "r0", "issue": 61, "role": "coder",
                                   "model": "m", "attempt": attempt, "status": "started",
                                   "ts": "2026-06-19T00:00:00Z"})


def _coder_issue(num=61, attempt=1):
    return {"number": num, "title": "do a thing",
            "labels": [{"name": "AI-GATE-TEST"}, {"name": "role:coder"},
                       {"name": "in-progress"}],
            "body": "",
            "comments": [{"id": "m1", "authorAssociation": "OWNER",
                          "body": _started_marker(attempt)}]}


def _red_pr(num=63, attempt=1):
    return {"number": num, "state": "OPEN", "body": "Closes #61",
            "headRefName": f"max-agency/issue-61/attempt-{attempt}",
            "statusCheckRollup": [{"status": "COMPLETED", "conclusion": "FAILURE"}]}


def _events(tmp_path):
    logs = list((tmp_path / "logs" / "gate").glob("*.jsonl"))
    return [json.loads(l) for l in logs[0].read_text().splitlines()]


def _wire(monkeypatch, issues, prs, ci_log="E501 line too long"):
    def _json(args):
        if args[:2] == ["issue", "list"]:
            if "closed" in args:
                return []
            if "--label" in args:
                return issues
            return [{"number": i["number"], "labels": i["labels"]} for i in issues]
        if args[:2] == ["pr", "list"]:
            return prs
        if args[:2] == ["run", "list"]:
            return [{"databaseId": 999, "conclusion": "failure"}]
        return []
    monkeypatch.setattr(gate, "gh_json", _json)
    monkeypatch.setattr(gate, "gh_text", lambda args: ci_log)
    rec = _RecordingWriter()
    monkeypatch.setattr(executor, "GitHubWriter", lambda *a, **k: rec)
    return rec


def _run(tmp_path, mode="deterministic-only", max_attempts=3):
    return gate.main(["--repo", "o/r", "--runtime-dir", str(tmp_path), "--mode", mode,
                      "--max-attempts", str(max_attempts)])


def test_ci_red_bounces_to_coder_with_log(monkeypatch, tmp_path):
    rec = _wire(monkeypatch, [_coder_issue(attempt=1)], [_red_pr(attempt=1)])
    assert _run(tmp_path) == gate.EXIT_OK  # deterministic — no LLM needed
    kinds = [o["op"] for o in rec.ops]
    assert "close_pr" in kinds
    el = [o for o in rec.ops if o["op"] == "edit_labels"][0]
    assert el["add"] == ["role:coder", "ready"] and el["remove"] == ["in-progress"]
    fb = [o for o in rec.ops if o["op"] == "comment"][0]
    assert fb["body"].startswith(executor.CI_FEEDBACK_PREFIX) and "E501" in fb["body"]
    assert any(e["event"] == "ci-bounce" and e["pr"] == 63 for e in _events(tmp_path))


def test_ci_red_attempts_exhausted_escalates_and_leaves_pr(monkeypatch, tmp_path):
    rec = _wire(monkeypatch, [_coder_issue(attempt=3)], [_red_pr(attempt=3)])
    assert _run(tmp_path, max_attempts=3) == gate.EXIT_OK
    kinds = [o["op"] for o in rec.ops]
    assert "close_pr" not in kinds  # PR left open for the human
    el = [o for o in rec.ops if o["op"] == "edit_labels"][0]
    assert el["add"] == ["needs-human"]
    assert any(e["event"] == "ci-escalate" for e in _events(tmp_path))


def test_ci_pending_is_left_untouched(monkeypatch, tmp_path):
    pending_pr = _red_pr(attempt=1)
    pending_pr["statusCheckRollup"] = [{"status": "IN_PROGRESS"}]
    rec = _wire(monkeypatch, [_coder_issue(attempt=1)], [pending_pr])
    assert _run(tmp_path) == gate.EXIT_OK
    assert rec.ops == []  # wait for CI; no bounce, no route
    assert not any(e["event"] == "ci-bounce" for e in _events(tmp_path))


def test_ci_green_routes_to_cto_not_bounce(monkeypatch, tmp_path):
    green_pr = _red_pr(attempt=1)
    green_pr["statusCheckRollup"] = []  # no CI configured == green
    rec = _wire(monkeypatch, [_coder_issue(attempt=1)], [green_pr])
    assert _run(tmp_path) == gate.EXIT_OK
    el = [o for o in rec.ops if o["op"] == "edit_labels"][0]
    assert el["add"] == ["role:cto"]  # routed to review, not bounced
    assert not any(e["event"] == "ci-bounce" for e in _events(tmp_path))
