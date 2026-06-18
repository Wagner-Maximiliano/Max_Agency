"""BUG-3: `check_model coder --smoke` runs a real agentic round-trip and verifies a PR
actually landed (a clean hermes exit is NOT proof — that's the bug).

harness.run_llm (hermes) and check_model._gh (verify/cleanup) are mocked; no network.
"""

import json

import pytest

import check_model
import harness


# ── pure command builders ─────────────────────────────────────────────────────
def test_smoke_prompt_names_branch_file_and_draft_pr():
    p = harness.coder_smoke_prompt("o/r", "max-agency/smoke-X", "maxagency-smoke-X.md")
    assert "max-agency/smoke-X" in p and "maxagency-smoke-X.md" in p
    assert "DRAFT pull request" in p and "[AI-smoke]" in p


def test_build_smoke_command_has_env_prefix_and_model_not_raw_injection():
    cmd = harness.build_coder_smoke_command("xiaomi/mimo-v2.5", "o/r", "br", "f.md")
    assert cmd[0] == "wsl.exe"
    joined = cmd[-1]
    assert "source ~/.hermes/.env" in joined            # hermes env loaded
    assert "xiaomi/mimo-v2.5" in joined                  # model passed
    assert "--yolo" in joined and "--max-turns 30" in joined


# ── smoke flow (run_llm + gh mocked) ──────────────────────────────────────────
def _mock_run_llm(monkeypatch, returncode=0, timed_out=False):
    monkeypatch.setattr(harness, "run_llm",
                        lambda *a, **k: {"returncode": returncode, "timed_out": timed_out,
                                         "stdout": "ok", "stderr": ""})


def _mock_gh(monkeypatch, pr_list):
    calls = []

    class _Out:
        def __init__(self, stdout="", rc=0):
            self.stdout, self.returncode, self.stderr = stdout, rc, ""

    def fake_gh(args, check=False):
        calls.append(args)
        if args[:2] == ["pr", "list"]:
            return _Out(json.dumps(pr_list))
        return _Out("")  # pr close / api delete

    monkeypatch.setattr(check_model, "_gh", fake_gh)
    return calls


def test_smoke_pass_when_pr_lands(monkeypatch, capsys):
    _mock_run_llm(monkeypatch, returncode=0)
    calls = _mock_gh(monkeypatch, [{"number": 7, "url": "https://x/pr/7", "isDraft": True}])
    rc = check_model.run_smoke("xiaomi/mimo-v2.5", "o/r", timeout=10)
    assert rc == 0
    out = capsys.readouterr().out
    assert "[PASS]" in out
    # cleanup ran: a PR close and a branch-ref delete were issued
    assert any(c[:2] == ["pr", "close"] for c in calls)
    assert any(c[:2] == ["api", "-X"] or (len(c) > 1 and c[0] == "api") for c in calls)


def test_smoke_fail_when_exit0_but_no_pr(monkeypatch, capsys):
    """The exact BUG-3 case: hermes exits 0 but never opened a PR -> FAIL, not PASS."""
    _mock_run_llm(monkeypatch, returncode=0)
    _mock_gh(monkeypatch, [])  # no PR
    rc = check_model.run_smoke("deepseek/deepseek-v4-flash", "o/r", timeout=10)
    assert rc == 1
    assert "NO pull request" in capsys.readouterr().out


def test_smoke_fail_on_timeout(monkeypatch, capsys):
    _mock_run_llm(monkeypatch, returncode=None, timed_out=True)
    calls = _mock_gh(monkeypatch, [])
    rc = check_model.run_smoke("m", "o/r", timeout=5)
    assert rc == 1
    assert "timed out" in capsys.readouterr().out
    # even on timeout we attempt branch cleanup
    assert any(c[0] == "api" for c in calls)


def test_smoke_passes_even_if_hermes_nonzero_but_pr_exists(monkeypatch, capsys):
    """PR presence is the source of truth, not the exit code."""
    _mock_run_llm(monkeypatch, returncode=1)
    _mock_gh(monkeypatch, [{"number": 9, "url": "u", "isDraft": True}])
    assert check_model.run_smoke("m", "o/r", timeout=10) == 0


# ── CLI guards ────────────────────────────────────────────────────────────────
def test_smoke_rejects_non_coder_role():
    with pytest.raises(SystemExit):
        check_model.main(["triage", "--smoke", "--repo", "o/r"])


def test_smoke_requires_repo():
    with pytest.raises(SystemExit):
        check_model.main(["coder", "--smoke"])
