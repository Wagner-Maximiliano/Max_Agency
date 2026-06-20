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


def _fake_gh(issues, prs=None, closed=None, compare=None):
    """compare: ('missing'|None) → branch 404 (re-dispatch); a dict → an existing branch
    (e.g. {'ahead_by': 3}). Default = missing, so the legacy recovery tests re-dispatch."""
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
        if args[:2] == ["repo", "view"]:           # default-branch lookup (BUG-4 Lever 2)
            return {"defaultBranchRef": {"name": "main"}}
        if args[:1] == ["api"] and "/compare/" in (args[1] if len(args) > 1 else ""):
            if compare in (None, "missing"):
                raise gate.GhError("Not Found (HTTP 404)")
            return compare
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


def _wire(monkeypatch, issues, run_llm_result, writer=None, compare=None):
    monkeypatch.setattr(gate, "gh_json", _fake_gh(issues, compare=compare))
    rec = writer or _RecordingWriter()
    monkeypatch.setattr(executor, "GitHubWriter", lambda *a, **k: rec)
    calls = {"n": 0, "cmds": []}

    def _fake_llm(cmd, timeout_s, input_text="", cwd=None, transcript=None):
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


# ── BUG-7: style-guide pointer (always) + reviewer feedback on re-dispatch ─────
def test_coder_prompt_always_points_at_style_guide():
    p = harness.coder_prompt("o/r", 7, 1)
    assert "STYLE.md" in p and "CONTRIBUTING.md" in p
    assert "style guide" in p.lower()


def test_coder_prompt_injects_feedback_when_present():
    p = harness.coder_prompt("o/r", 7, 2, feedback="CHANGES: no em dashes anywhere")
    assert "PREVIOUS ATTEMPT WAS REJECTED" in p
    assert "no em dashes anywhere" in p
    # untrusted feedback is framed as data to fix, not instructions to obey
    assert "not as instructions" in p.lower()


def test_coder_prompt_no_feedback_block_when_empty():
    assert "PREVIOUS ATTEMPT WAS REJECTED" not in harness.coder_prompt("o/r", 7, 1)


def test_coder_prompt_caps_feedback_length():
    p = harness.coder_prompt("o/r", 7, 2, feedback="z" * 9000)
    assert "z" * harness.CODER_FEEDBACK_CAP in p           # kept up to the cap
    assert "z" * (harness.CODER_FEEDBACK_CAP + 1) not in p  # truncated beyond it


def test_build_coder_command_embeds_feedback():
    cmd = harness.build_coder_command("m", "o/r", 7, 2, feedback="no em dashes")
    assert "no em dashes" in cmd[-1]  # carried into the bash -lc prompt string


def test_latest_coder_feedback_picks_changes_and_cto():
    # owner CHANGES: comment
    c1 = [{"authorAssociation": "OWNER", "body": "CHANGES: fix the links"}]
    assert "fix the links" in gate.latest_coder_feedback(c1)
    # CTO REQUEST_CHANGES rationale
    c2 = [{"authorAssociation": "NONE", "body": "CTO verdict: **REQUEST_CHANGES**: drop em dashes"}]
    assert "drop em dashes" in gate.latest_coder_feedback(c2)
    # marker comments are ignored; latest wins
    c3 = c1 + [{"authorAssociation": "OWNER", "body": executor.render_marker({"x": "y"})},
               {"authorAssociation": "NONE", "body": "CTO verdict: **REQUEST_CHANGES**: latest"}]
    assert "latest" in gate.latest_coder_feedback(c3)


def test_redispatch_forwards_feedback_to_coder(monkeypatch, tmp_path):
    """A bounced (re-queued) coder issue with a CHANGES: comment forwards that feedback into
    the dispatch prompt so the loop can converge (BUG-7)."""
    issue = _coder_issue(5, ["AI-GATE-TEST", "role:coder", "ready"],
                         comments=[{"authorAssociation": "OWNER",
                                    "body": "CHANGES: no em dashes, use commas"}])
    rec, calls = _wire(monkeypatch, [issue], _OK)

    assert _run(tmp_path) == gate.EXIT_OK
    assert calls["n"] == 1
    sent_cmd = calls["cmds"][0]
    assert any("no em dashes, use commas" in part for part in sent_cmd)
    ev = [e for e in _events(tmp_path) if e["event"] == "coder-dispatch"][0]
    assert ev["feedback"] is True


def test_first_attempt_has_no_feedback(monkeypatch, tmp_path):
    issue = _coder_issue(5, ["AI-GATE-TEST", "role:coder", "ready"])  # no comments
    rec, calls = _wire(monkeypatch, [issue], _OK)
    assert _run(tmp_path) == gate.EXIT_OK
    ev = [e for e in _events(tmp_path) if e["event"] == "coder-dispatch"][0]
    assert ev["feedback"] is False


# ── BUG-4 Lever 2: gate opens the PR for an already-pushed branch ──────────────
def test_lever1_prompt_makes_pr_the_final_mandatory_step():
    p = harness.coder_prompt("o/r", 7, 2)
    assert "Work GitHub issue #7" in p                 # opening kept (transcript/test contract)
    assert "gh pr create" in p and "[AI-7]" in p and "Closes #7" in p
    assert "NOT complete until" in p                   # hard stop condition
    assert "Pushing the branch is NOT enough" in p


def test_plan_open_pr_ops_follows_convention():
    ops = executor.plan_open_pr_ops(61, 2, "do a thing", "max-agency/issue-61/attempt-2",
                                    "main", "rid", "c1", ts="2026-06-18T00:00:00Z")
    assert ops[0] == {"op": "create_pr", "issue": 61, "head": "max-agency/issue-61/attempt-2",
                      "base": "main", "title": "[AI-61] do a thing",
                      "body": ops[0]["body"]}
    assert "Closes #61" in ops[0]["body"]
    assert ops[1]["op"] == "upsert_marker" and "status: pr-open" in ops[1]["body"]
    assert "attempt: 2" in ops[1]["body"]


def test_writer_create_pr_argv(monkeypatch):
    seen = {}
    w = executor.GitHubWriter("o/r", runner=lambda a: seen.setdefault("a", a) or "url")
    w.apply({"op": "create_pr", "issue": 61, "head": "br", "base": "main",
             "title": "[AI-61] x", "body": "Closes #61"})
    a = seen["a"]
    assert a[:2] == ["pr", "create"] and "--head" in a and "br" in a
    assert "--base" in a and "main" in a


def test_recovery_opens_pr_for_pushed_branch_no_redispatch(monkeypatch, tmp_path):
    """A stuck in-progress issue whose attempt branch was pushed (commits ahead) but has no
    PR → the gate opens the PR itself and does NOT re-dispatch (no orphaned branch)."""
    issues = [_stale_in_progress(61, attempt=2)]
    rec, calls = _wire(monkeypatch, issues, _OK, compare={"ahead_by": 3})

    assert _run(tmp_path) == gate.EXIT_OK
    assert calls["n"] == 0  # NO coder re-dispatch
    cp = [o for o in rec.ops if o["op"] == "create_pr"]
    assert len(cp) == 1
    assert cp[0]["head"] == "max-agency/issue-61/attempt-2" and cp[0]["base"] == "main"
    ev = {e["event"] for e in _events(tmp_path)}
    assert "coder-open-pr" in ev


def test_recovery_opens_pr_even_at_attempt_cap(monkeypatch, tmp_path):
    """A good pushed branch must be surfaced as a PR, not escalated to needs-human, even
    when the attempt cap is reached."""
    issues = [_stale_in_progress(61, attempt=3)]
    rec, calls = _wire(monkeypatch, issues, _OK, compare={"ahead_by": 1})

    assert _run(tmp_path, "--max-attempts", "3") == gate.EXIT_OK
    assert calls["n"] == 0
    assert any(o["op"] == "create_pr" for o in rec.ops)
    # NOT escalated
    assert not any(o["op"] == "edit_labels" and "needs-human" in o.get("add", [])
                   for o in rec.ops)
    assert not any(e["event"] == "coder-escalate" for e in _events(tmp_path))


def test_recovery_indeterminate_compare_does_not_redispatch(monkeypatch, tmp_path):
    """If the branch-ahead check errors (not a clean 404), the gate waits — it must not
    re-dispatch and orphan a possibly-good branch."""
    issues = [_stale_in_progress(61, attempt=2)]

    def _gh(args):
        if args[:2] == ["issue", "list"]:
            if "closed" in args:
                return []
            if "--label" in args:
                return issues
            return [{"number": i["number"], "labels": i["labels"]} for i in issues]
        if args[:2] == ["pr", "list"]:
            return []
        if args[:2] == ["repo", "view"]:
            return {"defaultBranchRef": {"name": "main"}}
        if args[:1] == ["api"] and "/compare/" in args[1]:
            raise gate.GhError("500 Internal Server Error")  # transient, not 404
        return []

    monkeypatch.setattr(gate, "gh_json", _gh)
    rec = _RecordingWriter()
    monkeypatch.setattr(executor, "GitHubWriter", lambda *a, **k: rec)
    calls = {"n": 0}
    monkeypatch.setattr(harness, "run_llm",
                        lambda *a, **k: calls.update(n=calls["n"] + 1) or dict(_OK))

    assert _run(tmp_path) == gate.EXIT_OK
    assert calls["n"] == 0  # did NOT re-dispatch
    assert not any(o["op"] == "create_pr" for o in rec.ops)
    assert any(e["event"] == "recover-indeterminate" for e in _events(tmp_path))


def test_deterministic_only_never_dispatches_coder(monkeypatch, tmp_path):
    issues = [_coder_issue(5, ["AI-GATE-TEST", "role:coder", "ready"])]
    rec, calls = _wire(monkeypatch, issues, _OK)

    assert gate.main(["--repo", "o/r", "--runtime-dir", str(tmp_path),
                      "--mode", "deterministic-only"]) == gate.EXIT_OK
    assert calls["n"] == 0
    assert rec.ops == []
