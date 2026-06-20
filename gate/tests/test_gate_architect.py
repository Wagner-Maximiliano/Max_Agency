"""Phase 2E-a: architect harness (plan generation -> plan-ready).

Claude is mocked through harness.run_llm; the gh writer is recorded.
"""

import json

import executor
import gate
import harness


def _fake_gh(issues, prs=None, closed=None):
    prs, closed = prs or [], closed or []

    def _gh(args):
        if args[:2] == ["issue", "list"]:
            if "closed" in args:
                return closed
            if "--label" in args:
                return issues
            return [{"number": i["number"], "labels": i["labels"]} for i in issues]
        if args[:2] == ["pr", "list"]:
            return prs
        return []
    return _gh


class _RecordingWriter:
    def __init__(self, *a, **k):
        self.ops = []

    def apply(self, op):
        self.ops.append(op)


def _arch_issue(num, body="Build a fuzzy multi-step feature.", comments=None):
    return {"number": num, "title": "fuzzy feature",
            "labels": [{"name": "AI-GATE-TEST"}, {"name": "role:architect"}],
            "body": body, "comments": comments or []}


_PLAN = ("## Summary\nDo the thing.\n## Scope\nx\n## Files to change\na.py\n"
         "## Steps\n1. step\n## Acceptance criteria\nworks\n## Risks\nnone")


def _events(tmp_path):
    logs = list((tmp_path / "logs" / "gate").glob("*.jsonl"))
    return [json.loads(l) for l in logs[0].read_text().splitlines()]


def _wire(monkeypatch, issues, llm_result, writer=None):
    monkeypatch.setattr(gate, "gh_json", _fake_gh(issues))
    rec = writer or _RecordingWriter()
    monkeypatch.setattr(executor, "GitHubWriter", lambda *a, **k: rec)
    seen = {"stdin": None, "cwd": None, "cmd": None}

    def _fake_llm(cmd, timeout_s, input_text="", cwd=None, transcript=None):
        seen["stdin"], seen["cwd"], seen["cmd"] = input_text, cwd, cmd
        return dict(llm_result)

    monkeypatch.setattr(harness, "run_llm", _fake_llm)
    return rec, seen


def _run(tmp_path):
    return gate.main(["--repo", "o/r", "--runtime-dir", str(tmp_path),
                      "--mode", "dispatch-enabled"])


# ── pure layer ────────────────────────────────────────────────────────────────
def test_architect_command_is_toolless_claude():
    cmd = harness.build_architect_command("opus")
    assert cmd[0] == "claude" and "-p" in cmd and "opus" in cmd
    assert "--tools" in cmd and cmd[cmd.index("--tools") + 1] == ""  # no tools
    assert any("architect" in p.lower() for p in cmd)


def test_is_plan_usable_rejects_tool_attempts_and_stubs():
    assert harness.is_plan_usable(_PLAN)
    assert not harness.is_plan_usable("too short")
    assert not harness.is_plan_usable("## Plan\n<function_calls>\n<invoke name='Bash'>")
    assert not harness.is_plan_usable("")


def test_plan_architect_ops_order_file_comment_label_marker():
    ops = executor.plan_architect_ops(7, _PLAN, "rid", None)
    assert [o["op"] for o in ops] == ["upsert_file", "comment", "edit_labels", "upsert_marker"]
    assert ops[0]["path"] == "plans/issue-7/PLAN.md"
    el = ops[2]
    assert el["add"] == ["plan-ready"] and el["remove"] == ["role:architect"]


# ── end-to-end ────────────────────────────────────────────────────────────────
def test_architect_writes_plan_and_moves_to_plan_ready(monkeypatch, tmp_path):
    issues = [_arch_issue(7)]
    rec, seen = _wire(monkeypatch, issues,
                      {"returncode": 0, "timed_out": False, "stdout": _PLAN, "stderr": ""})

    assert _run(tmp_path) == gate.EXIT_OK
    kinds = [o["op"] for o in rec.ops]
    assert kinds == ["upsert_file", "comment", "edit_labels", "upsert_marker"]
    assert seen["cwd"] is not None            # neutral cwd (defense in depth)
    assert "Title: fuzzy feature" in seen["stdin"]
    assert any(e["event"] == "architect-plan" for e in _events(tmp_path))


def test_architect_passes_changes_feedback_on_revision(monkeypatch, tmp_path):
    comments = [{"authorAssociation": "OWNER",
                 "body": "CHANGES: please split into two phases"}]
    issues = [_arch_issue(7, comments=comments)]
    rec, seen = _wire(monkeypatch, issues,
                      {"returncode": 0, "timed_out": False, "stdout": _PLAN, "stderr": ""})

    assert _run(tmp_path) == gate.EXIT_OK
    assert "split into two phases" in seen["stdin"]  # feedback fed to the architect
    assert [e for e in _events(tmp_path) if e["event"] == "architect-plan"][0]["revised"]


def test_architect_unusable_output_makes_no_mutation(monkeypatch, tmp_path):
    issues = [_arch_issue(7)]
    rec, seen = _wire(monkeypatch, issues,
                      {"returncode": 0, "timed_out": False,
                       "stdout": "<function_calls><invoke name='Bash'>", "stderr": ""})

    assert _run(tmp_path) == gate.EXIT_OK
    assert rec.ops == []
    assert any(e["event"] == "architect-unusable" for e in _events(tmp_path))


def test_architect_timeout_makes_no_mutation(monkeypatch, tmp_path):
    issues = [_arch_issue(7)]
    rec, seen = _wire(monkeypatch, issues,
                      {"returncode": None, "timed_out": True, "stdout": "", "stderr": ""})

    assert _run(tmp_path) == gate.EXIT_OK
    assert rec.ops == []
    assert any(e["event"] == "architect-timeout" for e in _events(tmp_path))


def test_architect_skips_label_when_file_write_fails(monkeypatch, tmp_path):
    """If PLAN.md can't be written, the issue must NOT advance to plan-ready."""
    issues = [_arch_issue(7)]

    class _FailFile(_RecordingWriter):
        def apply(self, op):
            if op["op"] == "upsert_file":
                raise RuntimeError("contents API 500")
            super().apply(op)

    rec, seen = _wire(monkeypatch, issues,
                      {"returncode": 0, "timed_out": False, "stdout": _PLAN, "stderr": ""},
                      writer=_FailFile())
    assert _run(tmp_path) == gate.EXIT_OK
    assert all(o["op"] != "edit_labels" for o in rec.ops)  # never flipped to plan-ready
    assert any(e["event"] == "mutation-error" for e in _events(tmp_path))


def test_deterministic_only_does_not_invoke_architect(monkeypatch, tmp_path):
    issues = [_arch_issue(7)]
    called = {"llm": False}
    monkeypatch.setattr(gate, "gh_json", _fake_gh(issues))
    rec = _RecordingWriter()
    monkeypatch.setattr(executor, "GitHubWriter", lambda *a, **k: rec)

    def _no(*a, **k):
        called["llm"] = True
        return {"returncode": 0, "timed_out": False, "stdout": _PLAN, "stderr": ""}

    monkeypatch.setattr(harness, "run_llm", _no)
    assert gate.main(["--repo", "o/r", "--runtime-dir", str(tmp_path),
                      "--mode", "deterministic-only"]) == gate.EXIT_OK
    assert called["llm"] is False
    assert rec.ops == []
