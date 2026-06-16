"""Phase 2C: orchestrator triage harness — pure prompt/command/parse + timeout runner.

No real `codex` is spawned; subprocess is mocked.
"""

import subprocess

import harness


def test_build_triage_command_is_readonly_codex():
    cmd = harness.build_triage_command("gpt-5.4-mini")
    assert cmd[0] == "codex" and "exec" in cmd
    assert "gpt-5.4-mini" in cmd
    # least privilege: classify only, never danger-full-access
    assert "read-only" in cmd
    assert "danger-full-access" not in cmd
    # the untrusted issue text is NOT in argv (it goes on stdin)
    assert all("Title:" not in part for part in cmd)


def test_issue_to_stdin_carries_title_and_body():
    s = harness.issue_to_stdin("Fix typo", "line 2 has a typo")
    assert "Title: Fix typo" in s
    assert "line 2 has a typo" in s


def test_parse_verdict_role_coder():
    label, reason = harness.parse_triage_verdict("ROLE_CODER\nsmall single-file fix")
    assert label == "role:coder"
    assert reason == "small single-file fix"


def test_parse_verdict_needs_human_for_bundled():
    label, reason = harness.parse_triage_verdict("NEEDS_HUMAN\nbundles two unrelated asks")
    assert label == "needs-human"
    assert "bundles" in reason


def test_parse_verdict_tolerates_backticks_and_blank_lines():
    label, reason = harness.parse_triage_verdict("\n`ROLE_ARCHITECT`\n\nneeds a plan\n")
    assert label == "role:architect"
    assert reason == "needs a plan"


def test_parse_verdict_unrecognized_returns_none():
    label, reason = harness.parse_triage_verdict("I think this is probably a coder task maybe")
    assert label is None
    assert reason == ""


def test_parse_verdict_empty_returns_none():
    assert harness.parse_triage_verdict("") == (None, "")


def test_run_llm_passes_stdin_and_returns_stdout(monkeypatch):
    seen = {}

    class Done:
        returncode = 0
        stdout = "ROLE_CODER\nok"
        stderr = ""

    def fake_run(cmd, **kw):
        seen["input"] = kw.get("input")
        seen["timeout"] = kw.get("timeout")
        return Done()

    monkeypatch.setattr(harness.subprocess, "run", fake_run)
    result = harness.run_llm(["codex", "exec"], timeout_s=30, input_text="Title: x")
    assert result["returncode"] == 0
    assert result["stdout"].startswith("ROLE_CODER")
    assert seen["input"] == "Title: x"
    assert seen["timeout"] == 30


def test_run_llm_timeout_is_not_fatal(monkeypatch):
    def fake_run(*a, **k):
        raise subprocess.TimeoutExpired(cmd=a[0], timeout=k.get("timeout"))

    monkeypatch.setattr(harness.subprocess, "run", fake_run)
    result = harness.run_llm(["codex", "exec"], timeout_s=1)
    assert result["timed_out"] is True
    assert result["returncode"] is None


def test_run_llm_missing_codex_is_not_fatal(monkeypatch):
    def fake_run(*a, **k):
        raise FileNotFoundError("codex not found")

    monkeypatch.setattr(harness.subprocess, "run", fake_run)
    result = harness.run_llm(["codex", "exec"], timeout_s=10)
    assert result["timed_out"] is False
    assert result["returncode"] is None
    assert "codex not found" in result["stderr"]
