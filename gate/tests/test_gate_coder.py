"""Phase 2D: coder dispatch + recovery (dispatch-enabled mode).

The coder subprocess (wsl->hermes) is mocked through harness.run_llm; the gh writer is
recorded. Covers: the claim (label move + in-flight marker before the blocking run),
attempt counting, one-coder-per-tick, recovery re-dispatch, escalation at the cap, and the
fail-safe claim-abort.
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


def _coder_issue(num, labels, body="Make a one-line change.", comments=None):
    return {"number": num, "title": "do a thing",
            "labels": [{"name": l} for l in labels],
            "body": body, "comments": comments or []}


def _marker_comment(attempt, status, ts):
    body = executor.render_marker(
        {"run_id": "r0", "issue": 1, "role": "coder", "model": "m",
         "attempt": attempt, "status": status, "ts": ts})
    return {"id": "c1", "authorAssociation": "NONE", "body": body}


def _events(tmp_path):
    logs = list((tmp_path / "logs" / "gate").glob("*.jsonl"))
    return [json.loads(l) for l in logs[0].read_text().splitlines()]


def _wire(monkeypatch, issues, run_llm_result, writer=None):
    monkeypatch.setattr(gate, "gh_json", _fake_gh(issues))
    rec = writer or _RecordingWriter()
    monkeypatch.setattr(executor, "GitHubWriter", lambda *a, **k: rec)
    calls = {"n": 0, "cmds": []}

    def _fake_llm(cmd, timeout_s, input_text="", cwd=None):
        calls["n"] += 1
        calls["cmds"].append(cmd)
        calls.setdefault("cwds", []).append(cwd)
        return dict(run_llm_result)

    monkeypatch.setattr(harness, "run_llm", _fake_llm)
    return rec, calls


_OK = {"returncode": 0, "timed_out": False, "stdout": "", "stderr": ""}


def _run(tmp_path, *extra):
    return gate.main(["--repo", "o/r", "--runtime-dir", str(tmp_path),
                      "--mode", "dispatch-enabled", *extra])


# ── pure layer ────────────────────────────────────────────────────────────────
def test_coder_branch_and_command_keep_issue_text_out_of_argv():
    assert harness.coder_branch(7, 2) == "max-agency/issue-7/attempt-2"
    cmd = harness.build_coder_command("xiaomi/mimo-v2.5", "o/r", 7, 2)
    assert cmd[:4] == ["wsl.exe", "-e", "bash", "-lc"]
    script = cmd[4]
    assert "source ~/.hermes/.env" in script           # hermes doesn't auto-load .env
    assert "max-agency/issue-7/attempt-2" in script     # branch convention
    assert "[AI-7]" in script and "Closes #7" in script  # PR<->issue convention
    assert "--yolo" in script


def test_plan_coder_dispatch_ops_label_then_marker():
    ops = executor.plan_coder_dispatch_ops(5, 1, "rid", "m", None, from_label="ready",
                                           ts="2026-06-16T00:00:00Z")
    assert ops[0] == {"op": "edit_labels", "issue": 5, "add": ["in-progress"],
                      "remove": ["ready"]}
    assert ops[1]["op"] == "upsert_marker"
    assert "status: started" in ops[1]["body"] and "attempt: 1" in ops[1]["body"]


def test_plan_coder_dispatch_recovery_keeps_in_progress():
    ops = executor.plan_coder_dispatch_ops(5, 2, "rid", "m", "c1", from_label="in-progress")
    assert ops[0]["remove"] == []  # already in-progress; no redundant removal


# ── fresh dispatch ────────────────────────────────────────────────────────────
def test_fresh_dispatch_claims_then_runs_coder(monkeypatch, tmp_path):
    issues = [_coder_issue(5, ["AI-GATE-TEST", "role:coder", "ready"])]
    rec, calls = _wire(monkeypatch, issues, _OK)

    assert _run(tmp_path) == gate.EXIT_OK
    # claim: ready -> in-progress + started marker (attempt 1), BEFORE the coder ran
    el = [o for o in rec.ops if o["op"] == "edit_labels"][0]
    assert el["add"] == ["in-progress"] and el["remove"] == ["ready"]
    mk = [o for o in rec.ops if o["op"] == "upsert_marker"][0]
    assert "attempt: 1" in mk["body"] and "status: started" in mk["body"]
    assert calls["n"] == 1  # coder dispatched once
    # safety: the coder must run from a neutral cwd, never the gate's repo (see the
    # incident where hermes inherited the repo cwd and ran git checkout in it)
    assert calls["cwds"][0] is not None
    ev = {e["event"] for e in _events(tmp_path)}
    assert "coder-dispatch" in ev and "coder-done" in ev


def test_one_coder_per_tick(monkeypatch, tmp_path):
    issues = [_coder_issue(5, ["AI-GATE-TEST", "role:coder", "ready"]),
              _coder_issue(6, ["AI-GATE-TEST", "role:coder", "ready"])]
    rec, calls = _wire(monkeypatch, issues, _OK)

    assert _run(tmp_path) == gate.EXIT_OK
    assert calls["n"] == 1  # only one dispatched this tick
    assert any(e["event"] == "coder-deferred-this-tick" for e in _events(tmp_path))


def test_dispatch_timeout_is_logged_not_fatal(monkeypatch, tmp_path):
    issues = [_coder_issue(5, ["AI-GATE-TEST", "role:coder", "ready"])]
    rec, calls = _wire(monkeypatch, issues,
                       {"returncode": None, "timed_out": True, "stdout": "", "stderr": ""})

    assert _run(tmp_path) == gate.EXIT_OK  # claim still happened; run timed out
    assert any(e["event"] == "coder-timeout" for e in _events(tmp_path))


def test_claim_failure_aborts_before_running_coder(monkeypatch, tmp_path):
    """If the label edit fails (e.g. missing label) the coder must not be spawned."""
    issues = [_coder_issue(5, ["AI-GATE-TEST", "role:coder", "ready"])]

    class _FailLabels(_RecordingWriter):
        def apply(self, op):
            if op["op"] == "edit_labels":
                raise RuntimeError("'in-progress' not found")
            super().apply(op)

    rec, calls = _wire(monkeypatch, issues, _OK, writer=_FailLabels())
    assert _run(tmp_path) == gate.EXIT_OK
    assert calls["n"] == 0  # never dispatched
    assert all(o["op"] != "upsert_marker" for o in rec.ops)  # no marker after failed claim


# ── recovery ──────────────────────────────────────────────────────────────────
def _stale_in_progress(num, attempt, status="started"):
    # ts well in the past so the marker is stale (not active) -> would-recover
    return _coder_issue(num, ["AI-GATE-TEST", "role:coder", "in-progress"],
                        comments=[_marker_comment(attempt, status, "2020-01-01T00:00:00Z")])


def test_recovery_redispatches_with_incremented_attempt(monkeypatch, tmp_path):
    issues = [_stale_in_progress(5, attempt=1)]
    rec, calls = _wire(monkeypatch, issues, _OK)

    assert _run(tmp_path) == gate.EXIT_OK
    assert calls["n"] == 1
    mk = [o for o in rec.ops if o["op"] == "upsert_marker"][0]
    assert "attempt: 2" in mk["body"]  # 1 -> 2
    # already in-progress: the claim doesn't redundantly strip the label
    el = [o for o in rec.ops if o["op"] == "edit_labels"][0]
    assert el["remove"] == []
    assert any(e["event"] == "coder-dispatch" for e in _events(tmp_path))


def test_recovery_escalates_at_cap(monkeypatch, tmp_path):
    issues = [_stale_in_progress(5, attempt=3)]
    rec, calls = _wire(monkeypatch, issues, _OK, )

    assert _run(tmp_path, "--max-attempts", "3") == gate.EXIT_OK
    assert calls["n"] == 0  # no further coder run
    el = [o for o in rec.ops if o["op"] == "edit_labels"][0]
    assert el["add"] == ["needs-human"] and el["remove"] == ["in-progress"]
    assert any(o["op"] == "comment" for o in rec.ops)
    assert any(e["event"] == "coder-escalate" for e in _events(tmp_path))


def test_deterministic_only_never_dispatches_coder(monkeypatch, tmp_path):
    issues = [_coder_issue(5, ["AI-GATE-TEST", "role:coder", "ready"])]
    rec, calls = _wire(monkeypatch, issues, _OK)

    assert gate.main(["--repo", "o/r", "--runtime-dir", str(tmp_path),
                      "--mode", "deterministic-only"]) == gate.EXIT_OK
    assert calls["n"] == 0
    assert rec.ops == []
