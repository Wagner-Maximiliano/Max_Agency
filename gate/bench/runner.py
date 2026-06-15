#!/usr/bin/env python3
"""Max Agency gate — Phase 0 benchmark runner (thin CLI; pure logic stays in tasks.py/scorer.py).

Subcommands:
  list                                          print all coder/triage tasks
  prep --repo OWNER/REPO --role {coder,orchestrator} [--live]
                                                 create the benchmark issues (dry-run prints
                                                 the `gh issue create` calls; --live runs them)
  dispatch --role {coder,orchestrator} --task-id ID --repo OWNER/REPO --issue N
           [--model NAME] [--timeout SECONDS] [--live]
                                                 print (default) or run (--live) the harness
                                                 command for one task, under a hard timeout

Every live call is subprocess-based with a mandatory timeout (roadmap: "hard subprocess
timeout ... mandatory for every LLM/CLI call from now on"). A hung `hermes`/`codex` is
killed and reported as `timed_out`, never left to hang the benchmark.
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from tasks import CODER_TASKS, MODEL_CANDIDATES, TRIAGE_TASKS

DEFAULT_TIMEOUT_S = 1800  # 30 min


def build_coder_command(model: str, repo: str, issue: int) -> list[str]:
    """wsl.exe -> hermes coder profile, single non-interactive query, hard turn cap."""
    prompt = (
        f"Work GitHub issue #{issue} in {repo}. Read the issue body for the full brief, "
        "constraints, and acceptance criteria, then implement it and open the draft PR "
        "it describes."
    )
    hermes_cmd = (
        f"hermes -p coder chat -q {_shquote(prompt)} -m {model} -Q "
        "--accept-hooks --yolo --max-turns 30"
    )
    # Mirror the production systemd unit's `EnvironmentFile=~/.hermes/.env`:
    # hermes reads provider credentials via os.getenv(), which only sees
    # vars exported into the process environment, not the .env file itself.
    full_cmd = f"set -a; source ~/.hermes/.env; set +a; {hermes_cmd}"
    return ["wsl.exe", "-e", "bash", "-lc", full_cmd]


def build_orchestrator_command(model: str, repo: str, issue: int) -> list[str]:
    """codex exec, single non-interactive run.

    -c model_reasoning_effort=low: triage is simple classification, low effort
    keeps usage-quota consumption down (verified against gpt-5.5, the only model
    this host's ChatGPT-account Codex login currently accepts).
    -s danger-full-access: triage applies labels/comments via `gh`, which needs
    network + no sandbox approval prompts (mirrors hermes's --yolo).
    --skip-git-repo-check: the target repo isn't necessarily checked out locally.
    """
    prompt = (
        f"Triage GitHub issue #{issue} in {repo}: read it, classify it per the Max Agency "
        "gate state machine (role:coder / role:architect / needs-human), and apply the "
        "resulting label(s) with a one-line comment explaining the classification."
    )
    return [
        "codex", "exec", "-m", model,
        "-c", "model_reasoning_effort=low",
        "-s", "danger-full-access",
        "--skip-git-repo-check",
        prompt,
    ]


def _shquote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def run_with_timeout(cmd: list[str], timeout_s: int) -> dict:
    """Thin: run cmd, hard-kill on timeout. Returns a result dict, never raises on timeout."""
    try:
        # wsl.exe / hermes output isn't reliably in the Windows console's locale
        # encoding (cp1252); decode as UTF-8 and replace anything that isn't,
        # rather than crashing the reader thread on a stray byte.
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout_s)
    except subprocess.TimeoutExpired as e:
        return {
            "returncode": None, "timed_out": True,
            "stdout": (e.stdout or ""), "stderr": (e.stderr or ""),
        }
    except FileNotFoundError as e:
        return {"returncode": None, "timed_out": False, "stdout": "", "stderr": str(e)}
    return {
        "returncode": out.returncode, "timed_out": False,
        "stdout": out.stdout, "stderr": out.stderr,
    }


def cmd_list(_args: argparse.Namespace) -> int:
    print("Coder tasks:")
    for t in CODER_TASKS:
        print(f"  {t.id}: {t.title}")
    print("\nTriage tasks:")
    for t in TRIAGE_TASKS:
        print(f"  {t.id}: {t.title}")
    print("\nModel candidates:")
    for role, cfg in MODEL_CANDIDATES.items():
        print(f"  {role}: primary={cfg['primary']} fallback={cfg['fallback']}")
    return 0


def cmd_prep(args: argparse.Namespace) -> int:
    tasks = CODER_TASKS if args.role == "coder" else TRIAGE_TASKS
    for t in tasks:
        gh_cmd = ["gh", "issue", "create", "--repo", args.repo, "--title", t.title,
                  "--body-file", "-"]
        if args.live:
            out = subprocess.run(gh_cmd, input=t.body, capture_output=True, text=True, timeout=60)
            print(f"{t.id}: {(out.stdout or out.stderr).strip()}")
        else:
            print(f"[dry-run] {' '.join(gh_cmd)}  (body piped on stdin, {len(t.body)} chars)")
    return 0


def cmd_dispatch(args: argparse.Namespace) -> int:
    tasks = CODER_TASKS if args.role == "coder" else TRIAGE_TASKS
    matches = [t for t in tasks if t.id == args.task_id]
    if not matches:
        print(f"unknown task id: {args.task_id}", file=sys.stderr)
        return 2

    model = args.model or MODEL_CANDIDATES[args.role]["primary"]
    if args.role == "coder":
        cmd = build_coder_command(model, args.repo, args.issue)
    else:
        cmd = build_orchestrator_command(model, args.repo, args.issue)

    if not args.live:
        print(f"[dry-run] timeout={args.timeout}s")
        print(" ".join(cmd))
        return 0

    result = run_with_timeout(cmd, args.timeout)
    print(f"timed_out={result['timed_out']} returncode={result['returncode']}")
    print("--- stdout ---")
    print(result["stdout"])
    print("--- stderr ---")
    print(result["stderr"])
    return 0 if not result["timed_out"] and result["returncode"] == 0 else 1


def main(argv: list[str] | None = None) -> int:
    # Harness output (e.g. hermes/wsl) may contain characters the Windows console's
    # cp1252 stdout can't encode; don't crash the runner over a print().
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list").set_defaults(func=cmd_list)

    p_prep = sub.add_parser("prep")
    p_prep.add_argument("--repo", required=True)
    p_prep.add_argument("--role", choices=["coder", "orchestrator"], required=True)
    p_prep.add_argument("--live", action="store_true")
    p_prep.set_defaults(func=cmd_prep)

    p_dispatch = sub.add_parser("dispatch")
    p_dispatch.add_argument("--role", choices=["coder", "orchestrator"], required=True)
    p_dispatch.add_argument("--task-id", required=True)
    p_dispatch.add_argument("--repo", required=True)
    p_dispatch.add_argument("--issue", type=int, required=True)
    p_dispatch.add_argument("--model", default=None)
    p_dispatch.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S)
    p_dispatch.add_argument("--live", action="store_true")
    p_dispatch.set_defaults(func=cmd_dispatch)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
