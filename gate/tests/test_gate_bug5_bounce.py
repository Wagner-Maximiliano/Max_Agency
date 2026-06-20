"""BUG-5: human-initiated bounce of a held coder PR back to the coder lane.

Owner posts `CHANGES:` on a `needs-human` issue that still has an open coder PR -> the gate
closes the PR, re-queues `role:coder`+`ready`, and carries the feedback forward. Deterministic
(no LLM), so it works in deterministic-only mode too.
"""

import json

import executor
import gate


# ── pure planner ──────────────────────────────────────────────────────────────
def test_plan_bounce_coder_ops_shape_and_feedback():
    ops = executor.plan_bounce_coder_ops(61, 63, 2, "rid", "c1",
                                         feedback="CHANGES: fix the broken links",
                                         ts="2026-06-19T00:00:00Z")
    kinds = [o["op"] for o in ops]
    assert kinds == ["comment", "close_pr", "edit_labels", "upsert_marker"]
    assert ops[0]["issue"] == 61 and "fix the broken links" in ops[0]["body"]
    assert ops[1] == {"op": "close_pr", "pr": 63,
                      "comment": ops[1]["comment"]}
    assert ops[2]["add"] == ["role:coder", "ready"] and ops[2]["remove"] == ["needs-human"]
    assert "status: bounced" in ops[3]["body"] and "attempt: 2" in ops[3]["body"]


# ── end-to-end ────────────────────────────────────────────────────────────────
class _RecordingWriter:
    def __init__(self, *a, **k):
        self.ops = []

    def apply(self, op):
        self.ops.append(op)


def _fake_gh(issues, prs):
    def _gh(args):
        if args[:2] == ["issue", "list"]:
            if "closed" in args:
                return []
            if "--label" in args:
                return issues
            return [{"number": i["number"], "labels": i["labels"]} for i in issues]
        if args[:2] == ["pr", "list"]:
            return prs
        return []
    return _gh


def _events(tmp_path):
    logs = list((tmp_path / "logs" / "gate").glob("*.jsonl"))
    return [json.loads(l) for l in logs[0].read_text().splitlines()]


def _held_issue(num=61, with_changes=True, changes_ts="2026-06-19T10:00:00Z", marker=None):
    comments = [{"id": "c1", "authorAssociation": "NONE",
                 "body": "CTO verdict: **APPROVE_MERGE** but holding for a human (nits)."}]
    if marker:  # a prior gate marker (so freshness can be evaluated against its ts)
        comments.append({"id": "m1", "authorAssociation": "OWNER", "body": marker})
    if with_changes:
        comments.append({"id": "c2", "authorAssociation": "OWNER", "createdAt": changes_ts,
                         "body": "CHANGES: the markdown links in section 2 are broken."})
    return {"number": num, "title": "do a thing",
            "labels": [{"name": "AI-GATE-TEST"}, {"name": "needs-human"}],
            "body": "", "comments": comments}


def _run(tmp_path, mode="deterministic-only"):
    return gate.main(["--repo", "o/r", "--runtime-dir", str(tmp_path), "--mode", mode])


def test_bounce_closes_pr_and_requeues_coder(monkeypatch, tmp_path):
    issues = [_held_issue(61, with_changes=True)]
    prs = [{"number": 63, "state": "OPEN", "body": "Closes #61",
            "headRefName": "max-agency/issue-61/attempt-2"}]
    monkeypatch.setattr(gate, "gh_json", _fake_gh(issues, prs))
    rec = _RecordingWriter()
    monkeypatch.setattr(executor, "GitHubWriter", lambda *a, **k: rec)

    assert _run(tmp_path) == gate.EXIT_OK  # deterministic-only: no LLM needed
    kinds = [o["op"] for o in rec.ops]
    assert "close_pr" in kinds
    cp = [o for o in rec.ops if o["op"] == "close_pr"][0]
    assert cp["pr"] == 63
    el = [o for o in rec.ops if o["op"] == "edit_labels"][0]
    assert el["add"] == ["role:coder", "ready"] and el["remove"] == ["needs-human"]
    # feedback carried forward into the gate's bounce comment
    assert any(o["op"] == "comment" and "broken" in o["body"] for o in rec.ops)
    assert any(e["event"] == "coder-bounce" and e["pr"] == 63 for e in _events(tmp_path))


def test_needs_human_without_changes_is_untouched(monkeypatch, tmp_path):
    issues = [_held_issue(61, with_changes=False)]
    prs = [{"number": 63, "state": "OPEN", "body": "Closes #61",
            "headRefName": "max-agency/issue-61/attempt-2"}]
    monkeypatch.setattr(gate, "gh_json", _fake_gh(issues, prs))
    rec = _RecordingWriter()
    monkeypatch.setattr(executor, "GitHubWriter", lambda *a, **k: rec)

    assert _run(tmp_path) == gate.EXIT_OK
    assert rec.ops == []  # dead stop preserved
    assert not any(e["event"] == "coder-bounce" for e in _events(tmp_path))


def test_bounce_without_open_pr_is_noop(monkeypatch, tmp_path):
    """CHANGES: on a needs-human issue with no open PR -> classifier won't even route it."""
    issues = [_held_issue(61, with_changes=True)]
    monkeypatch.setattr(gate, "gh_json", _fake_gh(issues, []))  # no PRs
    rec = _RecordingWriter()
    monkeypatch.setattr(executor, "GitHubWriter", lambda *a, **k: rec)

    assert _run(tmp_path) == gate.EXIT_OK
    assert rec.ops == []


def test_stale_changes_after_prior_marker_does_not_rebounce(monkeypatch, tmp_path):
    """If the latest gate marker is NEWER than the CHANGES: comment, the request was already
    acted on -> no re-bounce (prevents re-closing every freshly-built PR)."""
    later_marker = executor.render_marker(
        {"run_id": "r1", "issue": 61, "role": "cto", "status": "cto-approved-human",
         "ts": "2026-06-19T12:00:00Z"})  # marker AFTER the 10:00 CHANGES comment
    issues = [_held_issue(61, with_changes=True, changes_ts="2026-06-19T10:00:00Z",
                          marker=later_marker)]
    prs = [{"number": 63, "state": "OPEN", "body": "Closes #61",
            "headRefName": "max-agency/issue-61/attempt-2"}]
    monkeypatch.setattr(gate, "gh_json", _fake_gh(issues, prs))
    rec = _RecordingWriter()
    monkeypatch.setattr(executor, "GitHubWriter", lambda *a, **k: rec)

    assert _run(tmp_path) == gate.EXIT_OK
    assert rec.ops == []  # stale CHANGES -> dead stop, PR untouched
    assert not any(e["event"] == "coder-bounce" for e in _events(tmp_path))


def test_fresh_changes_after_prior_marker_bounces(monkeypatch, tmp_path):
    """A CHANGES: comment NEWER than the latest marker is a fresh request -> bounce."""
    older_marker = executor.render_marker(
        {"run_id": "r1", "issue": 61, "role": "cto", "status": "cto-approved-human",
         "ts": "2026-06-19T08:00:00Z"})  # marker BEFORE the 10:00 CHANGES comment
    issues = [_held_issue(61, with_changes=True, changes_ts="2026-06-19T10:00:00Z",
                          marker=older_marker)]
    prs = [{"number": 63, "state": "OPEN", "body": "Closes #61",
            "headRefName": "max-agency/issue-61/attempt-2"}]
    monkeypatch.setattr(gate, "gh_json", _fake_gh(issues, prs))
    rec = _RecordingWriter()
    monkeypatch.setattr(executor, "GitHubWriter", lambda *a, **k: rec)

    assert _run(tmp_path) == gate.EXIT_OK
    assert any(o["op"] == "close_pr" for o in rec.ops)
    assert any(e["event"] == "coder-bounce" for e in _events(tmp_path))
