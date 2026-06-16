"""Phase 2E-b: CTO harness (PR review -> verdict routing) + in-progress->cto routing.

Claude is mocked through harness.run_llm; gh reads (diff/meta) and the writer are stubbed.
"""

import json

import executor
import gate
import harness


class _RecordingWriter:
    def __init__(self, *a, **k):
        self.ops = []

    def apply(self, op):
        self.ops.append(op)


def _cto_issue(num, body="do a thing"):
    return {"number": num, "title": "thing",
            "labels": [{"name": "AI-GATE-TEST"}, {"name": "role:cto"}],
            "body": body, "comments": []}


def _fake_gh(issues, prs, closed=None, rollup=None):
    closed = closed or []

    def _gh(args):
        if args[:2] == ["issue", "list"]:
            if "closed" in args:
                return closed
            if "--label" in args:
                return issues
            return [{"number": i["number"], "labels": i["labels"]} for i in issues]
        if args[:2] == ["pr", "list"]:
            return prs
        if args[:2] == ["pr", "view"]:
            return {"title": "PR title", "body": "Closes #%s" % args[2],
                    "statusCheckRollup": rollup or []}
        return []
    return _gh


def _events(tmp_path):
    logs = list((tmp_path / "logs" / "gate").glob("*.jsonl"))
    return [json.loads(l) for l in logs[0].read_text().splitlines()]


def _wire(monkeypatch, issues, prs, cto_stdout, rollup=None, writer=None):
    monkeypatch.setattr(gate, "gh_json", _fake_gh(issues, prs, rollup=rollup))
    monkeypatch.setattr(gate, "gh_text", lambda args: "diff --git a/x b/x\n+ok")
    rec = writer or _RecordingWriter()
    monkeypatch.setattr(executor, "GitHubWriter", lambda *a, **k: rec)
    seen = {"stdin": None, "cwd": None}

    def _fake_llm(cmd, timeout_s, input_text="", cwd=None):
        seen["stdin"], seen["cwd"] = input_text, cwd
        return {"returncode": 0, "timed_out": False, "stdout": cto_stdout, "stderr": ""}

    monkeypatch.setattr(harness, "run_llm", _fake_llm)
    return rec, seen


def _run(tmp_path, *extra):
    return gate.main(["--repo", "o/r", "--runtime-dir", str(tmp_path),
                      "--mode", "dispatch-enabled", *extra])


# a PR linked to the issue, open
def _pr(num, issue):
    return {"number": num, "state": "OPEN", "body": "Closes #%d" % issue,
            "headRefName": "max-agency/issue-%d/attempt-1" % issue}


# ── pure verdict parsing ──────────────────────────────────────────────────────
def test_parse_verdict_approve_merge_no():
    v, hr, reason = harness.parse_cto_verdict("APPROVE_MERGE\nHUMAN-REVIEW: NO\nlooks good")
    assert v == "APPROVE_MERGE" and hr is False and reason == "looks good"


def test_parse_verdict_approve_merge_defaults_human_yes():
    v, hr, _ = harness.parse_cto_verdict("APPROVE_MERGE\n(forgot the human-review line)")
    assert v == "APPROVE_MERGE" and hr is True  # safe default: require a human


def test_parse_verdict_request_changes_and_reject():
    assert harness.parse_cto_verdict("REQUEST_CHANGES\nfix x")[0] == "REQUEST_CHANGES"
    assert harness.parse_cto_verdict("`REJECT_CLOSE`\nwrong approach")[0] == "REJECT_CLOSE"


def test_parse_verdict_unrecognized():
    assert harness.parse_cto_verdict("hmm not sure") == (None, None, "")


# ── pure routing ──────────────────────────────────────────────────────────────
def test_plan_cto_ops_merge_when_clear():
    ops = executor.plan_cto_ops("APPROVE_MERGE", False, "ok", 9, 30, "rid", "c1",
                                ci_green=True, auto_merge=True)
    kinds = [o["op"] for o in ops]
    assert "merge_pr" in kinds and kinds[0] == "comment"


def test_plan_cto_ops_holds_for_human_when_ci_red():
    ops = executor.plan_cto_ops("APPROVE_MERGE", False, "ok", 9, 30, "rid", "c1",
                                ci_green=False, auto_merge=True)
    assert all(o["op"] != "merge_pr" for o in ops)
    el = [o for o in ops if o["op"] == "edit_labels"][0]
    assert el["add"] == ["needs-human"]


def test_plan_cto_ops_request_changes_bounces_to_coder():
    ops = executor.plan_cto_ops("REQUEST_CHANGES", None, "fix", 9, 30, "rid", "c1")
    assert any(o["op"] == "close_pr" for o in ops)
    el = [o for o in ops if o["op"] == "edit_labels"][0]
    assert el["add"] == ["role:coder", "ready"] and el["remove"] == ["role:cto"]


def test_plan_cto_ops_reject_closes_pr_and_issue():
    ops = executor.plan_cto_ops("REJECT_CLOSE", None, "no", 9, 30, "rid", "c1")
    kinds = [o["op"] for o in ops]
    assert "close_pr" in kinds and "close" in kinds


# ── deterministic routing: in-progress + PR -> role:cto ───────────────────────
def test_in_progress_pr_routes_to_cto_deterministically(monkeypatch, tmp_path):
    issue = {"number": 9, "title": "t", "body": "b", "comments": [],
             "labels": [{"name": "AI-GATE-TEST"}, {"name": "role:coder"},
                        {"name": "in-progress"}]}
    monkeypatch.setattr(gate, "gh_json", _fake_gh([issue], [_pr(30, 9)]))
    rec = _RecordingWriter()
    monkeypatch.setattr(executor, "GitHubWriter", lambda *a, **k: rec)
    # deterministic-only is enough — no LLM for the routing move
    assert gate.main(["--repo", "o/r", "--runtime-dir", str(tmp_path),
                      "--mode", "deterministic-only"]) == gate.EXIT_OK
    el = [o for o in rec.ops if o["op"] == "edit_labels"][0]
    assert el["add"] == ["role:cto"] and set(el["remove"]) == {"role:coder", "in-progress"}


# ── end-to-end CTO dispatch ───────────────────────────────────────────────────
def test_cto_approve_merge_merges(monkeypatch, tmp_path):
    rec, seen = _wire(monkeypatch, [_cto_issue(9)], [_pr(30, 9)],
                      "APPROVE_MERGE\nHUMAN-REVIEW: NO\nsolid")
    assert _run(tmp_path) == gate.EXIT_OK
    assert any(o["op"] == "merge_pr" and o["pr"] == 30 for o in rec.ops)
    assert seen["cwd"] is not None  # neutral cwd
    assert "## Diff" in seen["stdin"]
    v = [e for e in _events(tmp_path) if e["event"] == "cto-verdict"][0]
    assert v["verdict"] == "APPROVE_MERGE"


def test_cto_approve_yes_holds_for_human(monkeypatch, tmp_path):
    rec, seen = _wire(monkeypatch, [_cto_issue(9)], [_pr(30, 9)],
                      "APPROVE_MERGE\nHUMAN-REVIEW: YES\nrisky")
    assert _run(tmp_path) == gate.EXIT_OK
    assert all(o["op"] != "merge_pr" for o in rec.ops)
    assert any(o["op"] == "edit_labels" and o["add"] == ["needs-human"] for o in rec.ops)


def test_cto_no_auto_merge_flag_holds(monkeypatch, tmp_path):
    rec, seen = _wire(monkeypatch, [_cto_issue(9)], [_pr(30, 9)],
                      "APPROVE_MERGE\nHUMAN-REVIEW: NO\nsolid")
    assert _run(tmp_path, "--no-auto-merge") == gate.EXIT_OK
    assert all(o["op"] != "merge_pr" for o in rec.ops)


def test_cto_red_ci_blocks_merge(monkeypatch, tmp_path):
    rollup = [{"conclusion": "FAILURE", "status": "COMPLETED"}]
    rec, seen = _wire(monkeypatch, [_cto_issue(9)], [_pr(30, 9)],
                      "APPROVE_MERGE\nHUMAN-REVIEW: NO\nsolid", rollup=rollup)
    assert _run(tmp_path) == gate.EXIT_OK
    assert all(o["op"] != "merge_pr" for o in rec.ops)
    assert [e for e in _events(tmp_path) if e["event"] == "cto-verdict"][0]["ci_green"] is False


def test_cto_unparsed_makes_no_mutation(monkeypatch, tmp_path):
    rec, seen = _wire(monkeypatch, [_cto_issue(9)], [_pr(30, 9)], "I cannot decide")
    assert _run(tmp_path) == gate.EXIT_OK
    assert rec.ops == []
    assert any(e["event"] == "cto-unparsed" for e in _events(tmp_path))


def test_ci_is_green_helper():
    assert gate.ci_is_green(None) is True
    assert gate.ci_is_green([]) is True
    assert gate.ci_is_green([{"conclusion": "SUCCESS", "status": "COMPLETED"}]) is True
    assert gate.ci_is_green([{"status": "IN_PROGRESS"}]) is False
    assert gate.ci_is_green([{"state": "FAILURE"}]) is False
