"""Per-project Max_AgencyConfig: parsing, fetch, and model resolution."""

import base64
import json
import types

import gate
import harness


# ── pure parser (security boundary: GATE_* only) ──────────────────────────────
def test_parse_model_config_gate_keys_only():
    text = (
        "# a comment\n"
        "GATE_CODER_MODEL=anthropic/claude-sonnet-4.6   \n"
        'GATE_TRIAGE_MODEL="gpt-5.4"\n'
        "PATH=/evil\n"            # must be ignored (not GATE_*)
        "OPENROUTER_API_KEY=leak\n"  # must be ignored
        "GATE_EMPTY=\n"           # empty value ignored
        "junk line without equals\n"
    )
    cfg = harness.parse_model_config(text)
    assert cfg == {"GATE_CODER_MODEL": "anthropic/claude-sonnet-4.6",
                   "GATE_TRIAGE_MODEL": "gpt-5.4"}
    assert "PATH" not in cfg and "OPENROUTER_API_KEY" not in cfg


def test_parse_model_config_empty():
    assert harness.parse_model_config("") == {}
    assert harness.parse_model_config("# only comments\n\n") == {}


# ── resolution precedence ─────────────────────────────────────────────────────
def _args(**kw):
    base = dict(coder_model=None, triage_model=None, architect_model=None, cto_model=None)
    base.update(kw)
    return types.SimpleNamespace(**base)


def test_resolve_models_precedence():
    logs = []
    args = _args(coder_model="cli/override")  # explicit CLI flag set for coder only
    project = {"GATE_CODER_MODEL": "proj/coder", "GATE_ARCHITECT_MODEL": "sonnet"}
    gate.resolve_models(args, project, lambda *a, **k: logs.append((a, k)))

    assert args.coder_model == "cli/override"          # CLI flag wins over project file
    assert args.architect_model == "sonnet"            # project file wins over default
    assert args.triage_model == harness.DEFAULT_TRIAGE_MODEL  # neither -> default
    assert args.cto_model == harness.DEFAULT_CTO_MODEL


def test_resolve_models_empty_project_uses_defaults():
    args = _args()
    gate.resolve_models(args, {}, lambda *a, **k: None)
    assert args.coder_model == harness.DEFAULT_CODER_MODEL
    assert args.cto_model == harness.DEFAULT_CTO_MODEL


# ── fetch (fail-safe) ─────────────────────────────────────────────────────────
def test_fetch_project_models_parses_base64(monkeypatch):
    body = "GATE_CODER_MODEL=openai/gpt-5.4\n"
    monkeypatch.setattr(gate, "gh_text",
                        lambda args: base64.b64encode(body.encode()).decode())
    cfg = gate.fetch_project_models("o/r", lambda *a, **k: None)
    assert cfg == {"GATE_CODER_MODEL": "openai/gpt-5.4"}


def test_fetch_project_models_missing_file_is_empty(monkeypatch):
    def _raise(args):
        raise gate.GhError("Not Found (HTTP 404)")
    monkeypatch.setattr(gate, "gh_text", _raise)
    assert gate.fetch_project_models("o/r", lambda *a, **k: None) == {}


def test_fetch_project_models_empty_content(monkeypatch):
    monkeypatch.setattr(gate, "gh_text", lambda args: "")
    assert gate.fetch_project_models("o/r", lambda *a, **k: None) == {}


# ── end-to-end: a project config drives the model the gate dispatches ──────────
def test_project_config_selects_coder_model_end_to_end(monkeypatch, tmp_path):
    issue = {"number": 5, "title": "t", "body": "b", "comments": [],
             "labels": [{"name": "AI"}, {"name": "role:coder"}, {"name": "ready"}]}

    def _gh(args):
        if args[:2] == ["issue", "list"]:
            if "closed" in args:
                return []
            if "--label" in args:
                return [issue]
            return [{"number": 5, "labels": issue["labels"]}]
        if args[:2] == ["pr", "list"]:
            return []
        return []
    monkeypatch.setattr(gate, "gh_json", _gh)
    # the project repo ships a Max_AgencyConfig choosing a writing model for the coder
    cfg_b64 = base64.b64encode(b"GATE_CODER_MODEL=anthropic/claude-sonnet-4.6\n").decode()
    monkeypatch.setattr(gate, "gh_text", lambda args: cfg_b64)

    seen = {}
    monkeypatch.setattr(gate.executor, "GitHubWriter", lambda *a, **k: types.SimpleNamespace(apply=lambda op: None))

    def _fake_coder_cmd(model, repo, issue_n, attempt, feedback=""):
        seen["model"] = model
        return ["wsl.exe", "-e", "bash", "-lc", "true"]
    monkeypatch.setattr(gate.harness, "build_coder_command", _fake_coder_cmd)
    monkeypatch.setattr(gate.harness, "run_llm",
                        lambda *a, **k: {"returncode": 0, "timed_out": False, "stdout": "", "stderr": ""})

    rc = gate.main(["--repo", "o/r", "--runtime-dir", str(tmp_path),
                    "--mode", "dispatch-enabled", "--scope-label", "AI"])
    assert rc == gate.EXIT_OK
    assert seen["model"] == "anthropic/claude-sonnet-4.6"  # project config won
    events = [json.loads(l) for l in
              next((tmp_path / "logs" / "gate").glob("*.jsonl")).read_text().splitlines()]
    m = [e for e in events if e["event"] == "models"][0]
    assert m["coder"] == "anthropic/claude-sonnet-4.6" and m["per_project"] is True
