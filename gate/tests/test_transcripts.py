"""FEAT-1: full LLM transcript logging at the single harness.run_llm chokepoint.

Covers the writer + redaction (pure), the run_llm integration (real run_llm, subprocess
mocked), the opt-out (no transcript dict => no file), and the gate wiring (each dispatch
passes a transcript descriptor pointing at runtime/logs/transcripts/<run_id>.txt).
"""

import json

import executor
import gate
import harness


# ── pure: writer + redaction ──────────────────────────────────────────────────
def test_append_transcript_writes_sent_and_received(tmp_path):
    path = str(tmp_path / "t" / "run.txt")  # nested dir is created lazily
    harness.append_transcript(
        path, run_id="r1", issue=61, role="coder", model="xiaomi/mimo-v2.5",
        sent="please open a PR", result={"returncode": 0, "timed_out": False,
                                          "stdout": "I refuse, here is prose instead", "stderr": ""})
    body = open(path, encoding="utf-8").read()
    assert "run=r1 issue=#61 role=coder model=xiaomi/mimo-v2.5" in body
    assert "--- SENT ---" in body and "please open a PR" in body
    assert "--- RECEIVED (exit=0 timed_out=False) ---" in body
    assert "I refuse, here is prose instead" in body  # the BUG-3 smoking gun is on disk


def test_redact_strips_env_source_prefix_and_keys():
    raw = ("set -a; source ~/.hermes/.env; set +a; hermes -p coder chat -q 'hi'\n"
           "OPENROUTER_API_KEY=sk-or-abc123def456 and token: sk-secretvalue99")
    out = harness._redact(raw)
    assert ".env" not in out or "[redacted env-source]" in out
    assert "source ~/.hermes/.env" not in out
    assert "sk-or-abc123def456" not in out
    assert "sk-secretvalue99" not in out
    assert "[redacted" in out


def test_append_transcript_never_fails_the_caller(tmp_path):
    # A bad path must be swallowed, not raised (best-effort observability).
    harness.append_transcript(
        "", run_id="r", issue=1, role="x", model="m", sent="s",
        result={"returncode": 0, "timed_out": False, "stdout": "", "stderr": ""})


# ── run_llm integration (subprocess mocked, real run_llm) ─────────────────────
def _mock_subprocess(monkeypatch, stdout="READY", stderr="", rc=0):
    class Done:
        returncode = rc
        def __init__(self): self.stdout, self.stderr = stdout, stderr
    monkeypatch.setattr(harness.subprocess, "run", lambda *a, **k: Done())


def test_run_llm_writes_transcript_when_given(monkeypatch, tmp_path):
    _mock_subprocess(monkeypatch, stdout="ROLE_CODER\nok")
    path = str(tmp_path / "logs" / "transcripts" / "run9.txt")
    harness.run_llm(["codex", "exec"], 30, input_text="Title: fix",
                    transcript={"path": path, "run_id": "run9", "issue": 9,
                                "role": "triage", "model": "gpt-5.4-mini"})
    body = open(path, encoding="utf-8").read()
    assert "role=triage" in body and "Title: fix" in body and "ROLE_CODER" in body


def test_run_llm_never_logs_the_argv_env_prefix(monkeypatch, tmp_path):
    """SECURITY: even when the argv carries `source ~/.hermes/.env`, run_llm logs only the
    caller-provided `sent` — the command/secret prefix never reaches the transcript."""
    _mock_subprocess(monkeypatch, stdout="done")
    path = str(tmp_path / "t.txt")
    argv = harness.build_coder_command("xiaomi/mimo-v2.5", "o/r", 5, 1)
    assert any("source ~/.hermes/.env" in part for part in argv)  # secret is in the argv
    harness.run_llm(argv, 60, transcript={"path": path, "run_id": "r", "issue": 5,
                                          "role": "coder", "model": "m",
                                          "sent": harness.coder_prompt("o/r", 5, 1)})
    body = open(path, encoding="utf-8").read()
    assert "source ~/.hermes/.env" not in body
    assert "Work GitHub issue #5" in body  # the safe prompt half is present


def test_run_llm_no_transcript_writes_nothing(monkeypatch, tmp_path):
    _mock_subprocess(monkeypatch)
    harness.run_llm(["codex", "exec"], 30)  # no transcript dict
    assert list(tmp_path.glob("**/*.txt")) == []


# ── gate wiring: each dispatch passes a transcript descriptor ─────────────────
def _fake_gh(issues):
    def _gh(args):
        if args[:2] == ["issue", "list"]:
            if "closed" in args:
                return []
            if "--label" in args:
                return issues
            return [{"number": i["number"], "labels": i["labels"]} for i in issues]
        return []
    return _gh


def test_gate_passes_transcript_path_to_run_llm(monkeypatch, tmp_path):
    seen = {}
    issues = [{"number": 14, "labels": [{"name": "AI-GATE-TEST"}],
               "title": "Fix typo", "body": "typo", "comments": []}]
    monkeypatch.setattr(gate, "gh_json", _fake_gh(issues))
    monkeypatch.setattr(executor, "GitHubWriter", lambda *a, **k: type(
        "W", (), {"apply": lambda self, op: None})())

    def _spy(cmd, timeout_s, input_text="", cwd=None, transcript=None):
        seen["transcript"] = transcript
        return {"returncode": 0, "timed_out": False, "stdout": "ROLE_CODER\nok", "stderr": ""}

    monkeypatch.setattr(harness, "run_llm", _spy)
    rc = gate.main(["--repo", "o/r", "--runtime-dir", str(tmp_path), "--mode", "dispatch-enabled"])
    assert rc == gate.EXIT_OK
    t = seen["transcript"]
    assert t["role"] == "triage" and t["issue"] == 14
    assert t["path"].replace("\\", "/").endswith("logs/transcripts/" + t["run_id"] + ".txt")
    assert "logs/transcripts" in t["path"].replace("\\", "/")


def test_empty_board_writes_no_transcript(monkeypatch, tmp_path):
    monkeypatch.setattr(gate, "gh_json", _fake_gh([]))
    assert gate.main(["--repo", "o/r", "--runtime-dir", str(tmp_path),
                      "--mode", "dispatch-enabled"]) == gate.EXIT_OK
    assert not (tmp_path / "logs" / "transcripts").exists()
