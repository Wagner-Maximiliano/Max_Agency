"""Phase 2C end-to-end: dispatch-enabled mode triages scope-only issues via the LLM.

The orchestrator subprocess is mocked through harness.run_llm; the gh writer is recorded.
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


def _scope_only_issue(num, title, body):
    return {"number": num, "labels": [{"name": "AI-GATE-TEST"}],
            "title": title, "body": body, "comments": []}


def _wire(monkeypatch, issues, llm_reply):
    monkeypatch.setattr(gate, "gh_json", _fake_gh(issues))
    rec = _RecordingWriter()
    monkeypatch.setattr(executor, "GitHubWriter", lambda *a, **k: rec)
    monkeypatch.setattr(harness, "run_llm",
                        lambda *a, **k: dict(llm_reply))
    return rec


def _events(tmp_path):
    logs = list((tmp_path / "logs" / "gate").glob("*.jsonl"))
    return [json.loads(l) for l in logs[0].read_text().splitlines()]


def test_triage_applies_label_and_comment(monkeypatch, tmp_path):
    issues = [_scope_only_issue(14, "Fix typo", "Goals.md has a typo")]
    rec = _wire(monkeypatch, issues,
                {"returncode": 0, "timed_out": False,
                 "stdout": "ROLE_CODER\nsmall single-file fix", "stderr": ""})

    rc = gate.main(["--repo", "o/r", "--runtime-dir", str(tmp_path),
                    "--mode", "dispatch-enabled"])
    assert rc == gate.EXIT_OK

    kinds = [(o["op"], o["issue"]) for o in rec.ops]
    assert ("edit_labels", 14) in kinds
    add = [o for o in rec.ops if o["op"] == "edit_labels"][0]["add"]
    assert add == ["role:coder", "ready"]  # coherent coder-lane entry state
    assert ("comment", 14) in kinds

    verdict = [e for e in _events(tmp_path) if e["event"] == "triage-verdict"][0]
    assert verdict["label"] == "role:coder"


def test_triage_timeout_makes_no_mutation(monkeypatch, tmp_path):
    issues = [_scope_only_issue(15, "Something", "vague")]
    rec = _wire(monkeypatch, issues,
                {"returncode": None, "timed_out": True, "stdout": "", "stderr": ""})

    assert gate.main(["--repo", "o/r", "--runtime-dir", str(tmp_path),
                      "--mode", "dispatch-enabled"]) == gate.EXIT_OK
    assert rec.ops == []
    assert any(e["event"] == "triage-timeout" for e in _events(tmp_path))


def test_triage_unparsed_verdict_makes_no_mutation(monkeypatch, tmp_path):
    issues = [_scope_only_issue(16, "Hmm", "unclear")]
    rec = _wire(monkeypatch, issues,
                {"returncode": 0, "timed_out": False,
                 "stdout": "I am not sure how to classify this", "stderr": ""})

    assert gate.main(["--repo", "o/r", "--runtime-dir", str(tmp_path),
                      "--mode", "dispatch-enabled"]) == gate.EXIT_OK
    assert rec.ops == []
    assert any(e["event"] == "triage-unparsed" for e in _events(tmp_path))


def test_triage_skips_comment_when_label_fails(monkeypatch, tmp_path):
    """A missing workflow label must not cause the rationale comment to spam every tick."""
    issues = [_scope_only_issue(18, "Fix typo", "typo")]

    class _FailLabels:
        def __init__(self, *a, **k):
            self.ops = []

        def apply(self, op):
            if op["op"] == "edit_labels":
                raise RuntimeError("'ready' not found")
            self.ops.append(op)

    monkeypatch.setattr(gate, "gh_json", _fake_gh(issues))
    rec = _FailLabels()
    monkeypatch.setattr(executor, "GitHubWriter", lambda *a, **k: rec)
    monkeypatch.setattr(harness, "run_llm",
                        lambda *a, **k: {"returncode": 0, "timed_out": False,
                                         "stdout": "ROLE_CODER\nfix", "stderr": ""})

    assert gate.main(["--repo", "o/r", "--runtime-dir", str(tmp_path),
                      "--mode", "dispatch-enabled"]) == gate.EXIT_OK
    # label raised -> no comment was attempted
    assert all(o["op"] != "comment" for o in rec.ops)
    assert any(e["event"] == "mutation-error" for e in _events(tmp_path))


def test_deterministic_only_does_not_triage(monkeypatch, tmp_path):
    issues = [_scope_only_issue(17, "Fix typo", "typo")]
    called = {"llm": False}

    monkeypatch.setattr(gate, "gh_json", _fake_gh(issues))
    rec = _RecordingWriter()
    monkeypatch.setattr(executor, "GitHubWriter", lambda *a, **k: rec)

    def _should_not_run(*a, **k):
        called["llm"] = True
        return {"returncode": 0, "timed_out": False, "stdout": "ROLE_CODER\nx", "stderr": ""}

    monkeypatch.setattr(harness, "run_llm", _should_not_run)

    # scope-only -> would-triage, but deterministic-only must NOT invoke the LLM
    assert gate.main(["--repo", "o/r", "--runtime-dir", str(tmp_path),
                      "--mode", "deterministic-only"]) == gate.EXIT_OK
    assert called["llm"] is False
    assert rec.ops == []


def test_one_issue_error_does_not_halt_the_board(monkeypatch, tmp_path):
    """An unexpected error on one issue is logged and the rest still process (fail-safe)."""
    issues = [_scope_only_issue(40, "first", "x"), _scope_only_issue(41, "second", "y")]
    monkeypatch.setattr(gate, "gh_json", _fake_gh(issues))
    rec = _RecordingWriter()
    monkeypatch.setattr(executor, "GitHubWriter", lambda *a, **k: rec)

    def _llm(cmd, timeout_s, input_text="", cwd=None, transcript=None):
        if "first" in input_text:           # blow up only on the first issue
            raise RuntimeError("boom (e.g. tempdir cleanup)")
        return {"returncode": 0, "timed_out": False,
                "stdout": "ROLE_CODER\nok", "stderr": ""}

    monkeypatch.setattr(harness, "run_llm", _llm)

    rc = gate.main(["--repo", "o/r", "--runtime-dir", str(tmp_path), "--mode", "dispatch-enabled"])
    assert rc == gate.EXIT_OK                 # tick did NOT abort with EXIT_UNEXPECTED
    events = [json.loads(l) for l in
              next((tmp_path / "logs" / "gate").glob("*.jsonl")).read_text().splitlines()]
    assert any(e["event"] == "issue-error" and e["issue"] == 40 for e in events)
    # the second issue was still triaged despite the first one erroring
    assert any(o["op"] == "edit_labels" and o["issue"] == 41 for o in rec.ops)
