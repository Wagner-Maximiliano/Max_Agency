"""Kickoff expansion: an approved PLAN -> concrete coder task issues (orchestrator).

codex is mocked through harness.run_llm; the PLAN fetch (gh_text) and writer are stubbed.
"""

import base64
import json

import classifier
import executor
import gate
import harness


# ── pure parsing ──────────────────────────────────────────────────────────────
def test_parse_expand_tasks_valid_with_deps():
    out = ('here you go:\n[{"title":"A","body":"do a","depends_on":[]},'
           '{"title":"B","body":"do b","depends_on":[1]}]\nthanks')
    tasks = harness.parse_expand_tasks(out)
    assert [t["title"] for t in tasks] == ["A", "B"]
    assert tasks[0]["depends_on"] == [] and tasks[1]["depends_on"] == [1]


def test_parse_expand_drops_forward_and_self_deps():
    # depends_on must reference an EARLIER task; forward/self refs are dropped
    out = '[{"title":"A","body":"x","depends_on":[2,1]},{"title":"B","body":"y","depends_on":[]}]'
    tasks = harness.parse_expand_tasks(out)
    assert tasks[0]["depends_on"] == []  # 2 (forward) and 1 (self) both dropped


def test_parse_expand_rejects_junk():
    assert harness.parse_expand_tasks("no json here") is None
    assert harness.parse_expand_tasks("[]") is None
    assert harness.parse_expand_tasks('[{"title":"","body":"x","depends_on":[]}]') is None


def test_parse_expand_caps_at_six():
    items = ",".join('{"title":"T%d","body":"b","depends_on":[]}' % i for i in range(10))
    assert len(harness.parse_expand_tasks("[" + items + "]")) == 6


# ── pure planners ─────────────────────────────────────────────────────────────
def test_task_issue_op_ready_without_deps_backlog_with():
    op = executor.plan_task_issue_op(5, 6, "AI-GATE-TEST", "T", "do it", [])
    assert op["labels"] == ["AI-GATE-TEST", "role:coder", "ready"]
    assert "Parent: #5" in op["body"] and "Kickoff: #6" in op["body"]
    op2 = executor.plan_task_issue_op(5, 6, "AI-GATE-TEST", "T", "do it", [7, 8])
    assert op2["labels"][-1] == "backlog"
    assert "Depends-on: #7,#8" in op2["body"]


def test_classifier_skips_expanded_kickoff():
    base = ["AI-GATE-TEST", "kickoff"]
    assert classifier.classify(
        classifier.IssueContext(6, set(base))).intended_action == "would-expand-kickoff"
    assert classifier.classify(
        classifier.IssueContext(6, set(base), kickoff_expanded=True)
    ).intended_action == "no-action"


# ── end-to-end ────────────────────────────────────────────────────────────────
class _Writer:
    def __init__(self, *a, **k):
        self.ops = []
        self._n = 100

    def apply(self, op):
        self.ops.append(op)
        if op["op"] == "create_issue":
            self._n += 1
            return "https://github.com/o/r/issues/%d" % self._n
        if op["op"] == "upsert_marker" and not op.get("comment_id"):
            return "https://github.com/o/r/issues/6#issuecomment-555"
        return None


def _kickoff_issue(num=6, parent=5):
    return {"number": num, "title": "kickoff",
            "labels": [{"name": "AI-GATE-TEST"}, {"name": "kickoff"}],
            "body": f"Approved-plan: #{parent}\nPlan: /plans/issue-{parent}/PLAN.md",
            "comments": []}


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


def _wire(monkeypatch, tasks_json, writer=None):
    issues = [_kickoff_issue()]
    monkeypatch.setattr(gate, "gh_json", _fake_gh(issues))
    plan_b64 = base64.b64encode(b"## Summary\nbuild stuff\n## Steps\n1 2").decode()
    monkeypatch.setattr(gate, "gh_text", lambda args: plan_b64)
    rec = writer or _Writer()
    monkeypatch.setattr(executor, "GitHubWriter", lambda *a, **k: rec)
    monkeypatch.setattr(harness, "run_llm",
                        lambda *a, **k: {"returncode": 0, "timed_out": False,
                                         "stdout": tasks_json, "stderr": ""})
    return rec


def _run(tmp_path):
    return gate.main(["--repo", "o/r", "--runtime-dir", str(tmp_path),
                      "--mode", "dispatch-enabled"])


def test_expand_creates_tasks_then_closes_kickoff(monkeypatch, tmp_path):
    tasks = ('[{"title":"first","body":"do first","depends_on":[]},'
             '{"title":"second","body":"do second","depends_on":[1]}]')
    rec = _wire(monkeypatch, tasks)
    assert _run(tmp_path) == gate.EXIT_OK

    creates = [o for o in rec.ops if o["op"] == "create_issue"]
    assert len(creates) == 2
    assert creates[0]["labels"][-1] == "ready"           # no deps
    assert creates[1]["labels"][-1] == "backlog"          # depends on the first
    assert "Depends-on: #101" in creates[1]["body"]       # resolved to the real number
    # claim marker (expanding) precedes the creates; kickoff closed at the end
    assert rec.ops[0]["op"] == "upsert_marker"
    assert any(o["op"] == "close" and o["issue"] == 6 for o in rec.ops)
    ev = {e["event"] for e in _events(tmp_path)}
    assert "expand-done" in ev


def test_expand_unparsed_makes_no_mutation(monkeypatch, tmp_path):
    rec = _wire(monkeypatch, "the model rambled with no json")
    assert _run(tmp_path) == gate.EXIT_OK
    assert rec.ops == []
    assert any(e["event"] == "expand-unparsed" for e in _events(tmp_path))


def test_expand_claim_marker_written_before_creates(monkeypatch, tmp_path):
    """The expanding marker must land before any task issue is created (idempotency)."""
    rec = _wire(monkeypatch, '[{"title":"only","body":"x","depends_on":[]}]')
    assert _run(tmp_path) == gate.EXIT_OK
    first_create = next(i for i, o in enumerate(rec.ops) if o["op"] == "create_issue")
    assert rec.ops[0]["op"] == "upsert_marker"
    assert "status: expanding" in rec.ops[0]["body"]
    assert first_create > 0
