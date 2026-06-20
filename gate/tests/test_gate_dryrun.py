"""End-to-end dry-run smoke test with gh mocked — proves the print/log/lock path."""

import json

import gate


def _fake_gh(issues, prs, closed):
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


def test_dryrun_prints_examples_and_changes_nothing(monkeypatch, tmp_path, capsys):
    issues = [
        {"number": 12, "labels": [{"name": "AI-GATE-TEST"}], "body": "", "comments": []},
        {"number": 15, "labels": [{"name": "AI-GATE-TEST"}, {"name": "role:coder"},
                                  {"name": "ready"}], "body": "", "comments": []},
    ]
    mutated = []
    monkeypatch.setattr(gate, "gh_json", _fake_gh(issues, [], []))
    # any write would go through subprocess.run; fail loudly if the dry-run tries to mutate
    monkeypatch.setattr(gate.subprocess, "run",
                        lambda *a, **k: mutated.append(a) or (_ for _ in ()).throw(
                            AssertionError("dry-run attempted a subprocess write")))

    rc = gate.main(["--repo", "x/y", "--runtime-dir", str(tmp_path)])
    out = capsys.readouterr().out

    assert rc == gate.EXIT_OK
    assert "#12 · AI-GATE-TEST · scope-only · would-triage · no workflow labels" in out
    assert ("#15 · AI-GATE-TEST+ready+role:coder · ready · would-dispatch-coder · "
            "no active marker") in out
    assert mutated == []  # changed nothing

    # a structured log file exists and records dry_run with zero mutations
    logs = list((tmp_path / "logs" / "gate").glob("*.jsonl"))
    assert len(logs) == 1
    events = [json.loads(l) for l in logs[0].read_text().splitlines()]
    done = [e for e in events if e["event"] == "done"][0]
    assert done["dry_run"] is True and done["mutations"] == 0
    # lock released at the end
    assert not (tmp_path / "gate.lock").exists()


def test_no_repo_exits_auth(tmp_path, monkeypatch):
    monkeypatch.delenv("PROJECT_REPO", raising=False)
    assert gate.main(["--runtime-dir", str(tmp_path)]) == gate.EXIT_AUTH


def test_fresh_lock_causes_skip(monkeypatch, tmp_path):
    issues = []
    monkeypatch.setattr(gate, "gh_json", _fake_gh(issues, [], []))
    # pre-create a fresh lock owned by someone else
    lock = tmp_path / "gate.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps({"run_id": "other", "start": gate.iso(gate.now())}))
    rc = gate.main(["--repo", "x/y", "--runtime-dir", str(tmp_path), "--stale-min", "15"])
    assert rc == gate.EXIT_OK
    # the foreign lock must be left intact (we skipped, didn't reclaim)
    assert json.loads(lock.read_text())["run_id"] == "other"
