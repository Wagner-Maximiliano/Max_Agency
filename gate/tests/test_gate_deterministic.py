"""Phase 2B end-to-end: deterministic-only mode executes the right mutations."""

import json

import executor
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


class _RecordingWriter:
    def __init__(self, *a, **k):
        self.ops = []

    def apply(self, op):
        self.ops.append(op)


def test_deterministic_executes_promote_and_close(monkeypatch, tmp_path):
    issues = [
        # backlog with a closed dep -> promote
        {"number": 7, "labels": [{"name": "AI-GATE-TEST"}, {"name": "role:coder"},
                                 {"name": "backlog"}], "body": "Depends-on: #3", "comments": []},
        # in-progress with a merged PR -> close
        {"number": 8, "labels": [{"name": "AI-GATE-TEST"}, {"name": "role:coder"},
                                 {"name": "in-progress"}], "body": "", "comments": []},
        # ready -> would-dispatch-coder, an LLM action -> NO mutation in 2B
        {"number": 9, "labels": [{"name": "AI-GATE-TEST"}, {"name": "role:coder"},
                                 {"name": "ready"}], "body": "", "comments": []},
    ]
    prs = [{"number": 88, "state": "MERGED", "body": "Closes #8", "headRefName": "x"}]
    closed = [{"number": 3}]

    monkeypatch.setattr(gate, "gh_json", _fake_gh(issues, prs, closed))
    rec = _RecordingWriter()
    monkeypatch.setattr(executor, "GitHubWriter", lambda *a, **k: rec)

    rc = gate.main(["--repo", "o/r", "--runtime-dir", str(tmp_path),
                    "--mode", "deterministic-only"])
    assert rc == gate.EXIT_OK

    kinds = [(o["op"], o["issue"]) for o in rec.ops]
    assert ("edit_labels", 7) in kinds          # promoted backlog->ready
    assert ("close", 8) in kinds                # closed on merged PR
    assert all(o["issue"] != 9 for o in rec.ops)  # ready -> deferred to dispatch phase

    logs = list((tmp_path / "logs" / "gate").glob("*.jsonl"))
    events = [json.loads(l) for l in logs[0].read_text().splitlines()]
    done = [e for e in events if e["event"] == "done"][0]
    assert done["dry_run"] is False and done["mutations"] == 2


def test_dry_run_still_makes_no_writer(monkeypatch, tmp_path):
    monkeypatch.setattr(gate, "gh_json", _fake_gh([], [], []))
    # If dry-run wrongly built a writer, this would raise.
    monkeypatch.setattr(executor, "GitHubWriter",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no writer in dry-run")))
    assert gate.main(["--repo", "o/r", "--runtime-dir", str(tmp_path)]) == gate.EXIT_OK
