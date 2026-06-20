"""BUG-1: approve -> kickoff -> expand must complete in ONE tick (no idle wait).

When the owner approves a plan-ready issue, the gate creates the kickoff issue AND expands
it into coder task issues within the same run, instead of leaving the kickoff to sit until
the next scan. The standalone would-expand-kickoff path remains the recovery fallback.
"""

import base64
import json

import executor
import gate
import harness


class _Writer:
    """Records ops; mints sequential issue numbers for create_issue (like the real gh URL)."""

    def __init__(self, *a, **k):
        self.ops = []
        self._n = 200

    def apply(self, op):
        self.ops.append(op)
        if op["op"] == "create_issue":
            self._n += 1
            return "https://github.com/o/r/issues/%d" % self._n
        if op["op"] == "upsert_marker" and not op.get("comment_id"):
            return "https://github.com/o/r/issues/0#issuecomment-9"
        return None


def _approved_plan_issue(num=50):
    """A plan-ready issue with an owner APPROVE comment -> would-create-kickoff."""
    return {"number": num, "title": "build a phase",
            "labels": [{"name": "AI-GATE-TEST"}, {"name": "plan-ready"}],
            "body": "",
            "comments": [{"id": "c1", "authorAssociation": "OWNER", "body": "APPROVE"}]}


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


def _wire(monkeypatch, tasks_json):
    monkeypatch.setattr(gate, "gh_json", _fake_gh([_approved_plan_issue()]))
    plan_b64 = base64.b64encode(b"## Summary\nbuild stuff\n## Steps\n1 2").decode()
    monkeypatch.setattr(gate, "gh_text", lambda args: plan_b64)  # PLAN.md fetch
    rec = _Writer()
    monkeypatch.setattr(executor, "GitHubWriter", lambda *a, **k: rec)
    monkeypatch.setattr(harness, "run_llm",
                        lambda *a, **k: {"returncode": 0, "timed_out": False,
                                         "stdout": tasks_json, "stderr": ""})
    return rec


def _run(tmp_path):
    return gate.main(["--repo", "o/r", "--runtime-dir", str(tmp_path), "--mode", "dispatch-enabled"])


def test_approve_creates_kickoff_and_expands_same_tick(monkeypatch, tmp_path):
    tasks = ('[{"title":"first","body":"do first","depends_on":[]},'
             '{"title":"second","body":"do second","depends_on":[1]}]')
    rec = _wire(monkeypatch, tasks)
    assert _run(tmp_path) == gate.EXIT_OK

    creates = [o for o in rec.ops if o["op"] == "create_issue"]
    # one kickoff issue + two coder task issues, all in this single tick
    assert any("kickoff" in o.get("labels", []) for o in creates)
    task_creates = [o for o in creates if "role:coder" in o.get("labels", [])]
    assert len(task_creates) == 2
    assert task_creates[0]["labels"][-1] == "ready"      # no deps
    assert task_creates[1]["labels"][-1] == "backlog"     # depends on first
    # the kickoff (#201, the first create) was closed after expansion, same tick
    assert any(o["op"] == "close" and o["issue"] == 201 for o in rec.ops)

    ev = {e["event"] for e in _events(tmp_path)}
    assert "kickoff-expand-inline" in ev
    assert "expand-done" in ev


def test_inline_expand_failure_leaves_kickoff_for_fallback(monkeypatch, tmp_path):
    """If the in-tick expand produces nothing usable, the kickoff is still created (the
    standalone path recovers it next tick) — and no task issues are created."""
    rec = _wire(monkeypatch, "the model rambled, no json")
    assert _run(tmp_path) == gate.EXIT_OK

    creates = [o for o in rec.ops if o["op"] == "create_issue"]
    assert len(creates) == 1 and "kickoff" in creates[0]["labels"]  # only the kickoff
    ev = {e["event"] for e in _events(tmp_path)}
    assert "kickoff-expand-inline" in ev and "expand-unparsed" in ev
    # the kickoff was NOT closed (nothing to expand into) -> fallback will retry
    assert not any(o["op"] == "close" for o in rec.ops)
