"""Unit tests for the Phase 0 benchmark runner's command-building and timeout wrapper.

No real `wsl`/`hermes`/`codex`/`gh` calls — subprocess is mocked.
"""

import os
import subprocess

import runner


def test_build_coder_command_uses_wsl_hermes_with_model_and_issue():
    cmd = runner.build_coder_command("xiaomi/mimo-v2.5", "owner/repo", 42)
    assert cmd[:3] == ["wsl.exe", "-e", "bash"]
    joined = " ".join(cmd)
    assert "hermes -p coder chat" in joined
    assert "-m xiaomi/mimo-v2.5" in joined
    assert "#42 in owner/repo" in joined
    assert "--yolo" in joined and "--max-turns" in joined


def test_build_orchestrator_command_uses_codex_with_model_and_issue():
    cmd = runner.build_orchestrator_command("gpt-5.4-mini", "owner/repo", 7)
    assert cmd[0] == "codex"
    assert "exec" in cmd
    assert "gpt-5.4-mini" in cmd
    assert "danger-full-access" in cmd
    assert any("#7 in owner/repo" in part for part in cmd)


def test_runnable_argv_noop_on_posix(monkeypatch):
    monkeypatch.setattr(runner.os, "name", "posix")
    cmd = ["codex", "exec", "-m", "gpt-5.4-mini"]
    assert runner._runnable_argv(cmd) == cmd


def test_runnable_argv_rewrites_windows_cmd_shim_to_node(monkeypatch):
    monkeypatch.setattr(runner.os, "name", "nt")

    def fake_which(name):
        return {
            "codex": r"C:\npm\codex.CMD",
            "node": r"C:\nodejs\node.EXE",
        }.get(name)

    monkeypatch.setattr(runner.shutil, "which", fake_which)
    monkeypatch.setattr(runner.os.path, "exists", lambda p: True)
    out = runner._runnable_argv(["codex", "exec", "-m", "gpt-5.4-mini"])
    assert out[0] == r"C:\nodejs\node.EXE"
    assert out[1].endswith(os.path.join("bin", "codex.js"))
    assert out[2:] == ["exec", "-m", "gpt-5.4-mini"]


def test_runnable_argv_passthrough_for_real_exe(monkeypatch):
    monkeypatch.setattr(runner.os, "name", "nt")
    monkeypatch.setattr(runner.shutil, "which", lambda n: r"C:\Windows\System32\wsl.exe")
    out = runner._runnable_argv(["wsl.exe", "-e", "bash"])
    assert out == [r"C:\Windows\System32\wsl.exe", "-e", "bash"]


def test_run_with_timeout_returns_timed_out_on_timeout(monkeypatch):
    def fake_run(*a, **k):
        raise subprocess.TimeoutExpired(cmd=a[0], timeout=k.get("timeout"))

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    result = runner.run_with_timeout(["sleep", "100"], timeout_s=1)
    assert result["timed_out"] is True
    assert result["returncode"] is None


def test_run_with_timeout_missing_binary_does_not_raise(monkeypatch):
    def fake_run(*a, **k):
        raise FileNotFoundError("codex not found")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    result = runner.run_with_timeout(["codex", "exec"], timeout_s=10)
    assert result["timed_out"] is False
    assert result["returncode"] is None
    assert "codex not found" in result["stderr"]


def test_run_with_timeout_success(monkeypatch):
    class FakeCompleted:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: FakeCompleted())
    result = runner.run_with_timeout(["true"], timeout_s=10)
    assert result == {"returncode": 0, "timed_out": False, "stdout": "ok", "stderr": ""}


def test_dispatch_dry_run_does_not_call_subprocess(monkeypatch, capsys):
    called = []
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: called.append(1))
    rc = runner.main([
        "dispatch", "--role", "coder", "--task-id", "coder-1",
        "--repo", "owner/repo", "--issue", "1",
    ])
    assert rc == 0
    assert called == []
    out = capsys.readouterr().out
    assert "[dry-run]" in out
    assert "wsl.exe" in out


def test_dispatch_unknown_task_id_errors():
    rc = runner.main([
        "dispatch", "--role", "coder", "--task-id", "nope",
        "--repo", "owner/repo", "--issue", "1",
    ])
    assert rc == 2


def test_list_command_runs(capsys):
    rc = runner.main(["list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "coder-1" in out
    assert "triage-1" in out
    assert "Model candidates" in out
