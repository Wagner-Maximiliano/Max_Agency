"""BUG-6: a stale CHANGES: on a plan-ready issue must not re-reopen the architect every tick.

Mirrors the BUG-5 freshness guard: the architect's plan-ready CHANGES: path now fires only
when the owner's CHANGES: comment is newer than the last gate marker. Exercised end-to-end
through build_context (real freshness computation), deterministic-only mode.
"""

import json

import executor
import gate


class _RecordingWriter:
    def __init__(self, *a, **k):
        self.ops = []

    def apply(self, op):
        self.ops.append(op)


def _fake_gh(issues):
    def _gh(args):
        if args[:2] == ["issue", "list"]:
            if "closed" in args:
                return []
            if "--label" in args:
                return issues
            return [{"number": i["number"], "labels": i["labels"]} for i in issues]
        if args[:2] == ["pr", "list"]:
            return []
        return []
    return _gh


def _events(tmp_path):
    logs = list((tmp_path / "logs" / "gate").glob("*.jsonl"))
    return [json.loads(l) for l in logs[0].read_text().splitlines()]


def _plan_ready_issue(num, changes_ts, marker_ts):
    """A plan-ready issue carrying a plan-generated marker + an owner CHANGES: comment."""
    marker = executor.render_marker(
        {"run_id": "r1", "issue": num, "role": "architect", "status": "plan-generated",
         "ts": marker_ts})
    return {"number": num, "title": "build a phase",
            "labels": [{"name": "AI-GATE-TEST"}, {"name": "plan-ready"}],
            "body": "",
            "comments": [{"id": "m1", "authorAssociation": "OWNER", "body": marker},
                         {"id": "c2", "authorAssociation": "OWNER", "createdAt": changes_ts,
                          "body": "CHANGES: please split into two phases"}]}


def _run(tmp_path):
    return gate.main(["--repo", "o/r", "--runtime-dir", str(tmp_path),
                      "--mode", "deterministic-only"])


def test_stale_changes_does_not_reopen_architect(monkeypatch, tmp_path):
    # marker (12:00) is NEWER than the CHANGES comment (10:00) -> already revised -> no reopen
    issues = [_plan_ready_issue(50, changes_ts="2026-06-19T10:00:00Z",
                                marker_ts="2026-06-19T12:00:00Z")]
    monkeypatch.setattr(gate, "gh_json", _fake_gh(issues))
    rec = _RecordingWriter()
    monkeypatch.setattr(executor, "GitHubWriter", lambda *a, **k: rec)

    assert _run(tmp_path) == gate.EXIT_OK
    assert rec.ops == []  # no reopen-architect loop
    dec = [e for e in _events(tmp_path) if e["event"] == "decision"][0]
    assert dec["intended_action"] == "no-action"


def test_fresh_changes_reopens_architect(monkeypatch, tmp_path):
    # CHANGES (12:00) is NEWER than the marker (08:00) -> a fresh request -> reopen
    issues = [_plan_ready_issue(50, changes_ts="2026-06-19T12:00:00Z",
                                marker_ts="2026-06-19T08:00:00Z")]
    monkeypatch.setattr(gate, "gh_json", _fake_gh(issues))
    rec = _RecordingWriter()
    monkeypatch.setattr(executor, "GitHubWriter", lambda *a, **k: rec)

    assert _run(tmp_path) == gate.EXIT_OK
    el = [o for o in rec.ops if o["op"] == "edit_labels"]
    assert el and el[0]["add"] == ["role:architect"] and el[0]["remove"] == ["plan-ready"]
