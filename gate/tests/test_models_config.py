"""models.env loader + the model-check ping builders (gate/check_model.py)."""

import os

import harness


def test_load_model_env_does_not_override_existing(monkeypatch, tmp_path):
    cfg = tmp_path / "models.env"
    cfg.write_text("GATE_CODER_MODEL=from-file\nGATE_TRIAGE_MODEL=triage-file\n")
    monkeypatch.setattr(harness.os.path, "dirname", lambda _f: str(tmp_path))
    monkeypatch.setenv("GATE_CODER_MODEL", "from-env")   # already set -> must win
    monkeypatch.delenv("GATE_TRIAGE_MODEL", raising=False)

    harness._load_model_env()

    assert os.environ["GATE_CODER_MODEL"] == "from-env"   # env wins over the file
    assert os.environ["GATE_TRIAGE_MODEL"] == "triage-file"  # file fills an unset key


def test_load_model_env_missing_file_is_silent(monkeypatch, tmp_path):
    monkeypatch.setattr(harness.os.path, "dirname", lambda _f: str(tmp_path / "nope"))
    harness._load_model_env()  # must not raise


def test_ping_builders_shape():
    coder_cmd, coder_stdin = harness.PING_BUILDERS["coder"]("some/model")
    assert coder_cmd[:4] == ["wsl.exe", "-e", "bash", "-lc"]
    assert "hermes -p coder" in coder_cmd[4] and "some/model" in coder_cmd[4]
    assert coder_stdin == ""  # coder prompt goes via -q, not stdin

    triage_cmd, _ = harness.PING_BUILDERS["triage"]("m")
    assert triage_cmd[0] == "codex" and "read-only" in triage_cmd

    # claude ping must NOT end on a positional (its variadic --tools would eat it); prompt
    # is on stdin and the argv ends on a flag value.
    arch_cmd, arch_stdin = harness.PING_BUILDERS["architect"]("opus")
    assert arch_cmd[0] == "claude" and "--tools" in arch_cmd
    assert arch_cmd[-2] == "--append-system-prompt"
    assert arch_stdin and "READY" in arch_stdin
    assert harness.PING_BUILDERS["cto"] is harness.PING_BUILDERS["architect"]


def test_ping_default_model_keys():
    assert set(harness.PING_DEFAULT_MODEL) == {"coder", "triage", "architect", "cto"}
    assert callable(harness.PING_DEFAULT_MODEL["coder"])
