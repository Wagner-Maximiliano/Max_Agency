#!/usr/bin/env python3
"""Quick model self-test: confirm a role's configured model + its CLI/auth actually respond.

Usage:
    python gate/check_model.py <role> [--model ID] [--timeout S]
    python gate/check_model.py coder --smoke --repo owner/repo [--model ID]

    role : coder | triage | architect | cto   (triage also covers kickoff expansion)

Default (ping): runs a tiny, side-effect-free prompt through the SAME CLI path the gate uses
for that role (coder -> wsl/hermes/OpenRouter, triage -> codex, architect/cto -> claude), so
a PASS means the model id is valid, the CLI is installed, and auth/credentials work.

--smoke (coder only, BUG-3): a ping only proves the model *responds*, not that it *uses* its
file/git tools — a model can answer in text, hermes exits 0, and no PR is ever opened. The
smoke test forces the full agentic round-trip on a throwaway repo: create a branch, commit a
file, open a draft PR, then verify the PR actually landed (PASS only if it did) and clean up
(close the PR + delete the branch). Use it before trusting a new coder model.

Prints PASS/FAIL and the model's reply. Exit 0 on PASS, 1 on FAIL.

The model id and keys are configured in gate/models.env (see that file).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness  # noqa: E402

ROLES = ("coder", "triage", "architect", "cto")
# coder/architect/cto shell out to tool-capable CLIs -> run from a neutral cwd (never the repo)
NEUTRAL_CWD_ROLES = {"coder", "architect", "cto"}

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _gh(args: list[str], check: bool = False):
    """Thin gh runner for the smoke test's verify/cleanup steps. Returns CompletedProcess."""
    out = subprocess.run(["gh", *args], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=60,
                         creationflags=NO_WINDOW)
    if check and out.returncode != 0:
        raise RuntimeError((out.stderr or "gh failed").strip())
    return out


def _smoke_cleanup(repo: str, branch: str, pr_numbers: list[int]) -> None:
    """Always-run teardown: close any smoke PR (deletes its branch) and delete the branch ref
    if it lingers. Best-effort — a cleanup failure is reported but never raised."""
    for n in pr_numbers:
        _gh(["pr", "close", str(n), "--repo", repo, "--delete-branch",
             "--comment", "Closing Max Agency coder smoke-test PR (throwaway)."])
    # Delete the branch ref directly too, in case no PR was opened (or close didn't remove it).
    _gh(["api", "-X", "DELETE", f"repos/{repo}/git/refs/heads/{branch}"])


def run_smoke(model: str, repo: str, timeout: int) -> int:
    """Coder agentic smoke test (BUG-3): real branch -> commit -> draft PR -> verify -> clean up."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    branch = f"max-agency/smoke-{ts}"
    fname = f"maxagency-smoke-{ts}.md"
    print(f"[smoke] coder model={model} repo={repo} branch={branch} (timeout {timeout}s)")

    cmd = harness.build_coder_smoke_command(model, repo, branch, fname)
    with tempfile.TemporaryDirectory(prefix="maxagency-smoke-", ignore_cleanup_errors=True) as cwd:
        result = harness.run_llm(cmd, timeout, cwd=cwd)
    if result["timed_out"]:
        print(f"[FAIL] coder smoke timed out after {timeout}s")
        _smoke_cleanup(repo, branch, [])
        return 1
    exited_clean = result["returncode"] in (0, None)
    if not exited_clean:
        print(f"[warn] hermes returncode={result['returncode']} "
              f"(verifying the PR regardless)")
        err = (result.get("stderr") or "").strip()
        if err:
            print("  stderr:", err[:300])

    # The real test: did a PR actually land? (exit 0 != PR opened — that's BUG-3.)
    try:
        out = _gh(["pr", "list", "--repo", repo, "--head", branch, "--state", "all",
                   "--json", "number,url,isDraft"], check=True)
        prs = json.loads(out.stdout or "[]")
    except (RuntimeError, ValueError) as e:
        print(f"[FAIL] could not verify the smoke PR: {e}")
        _smoke_cleanup(repo, branch, [])
        return 1

    pr_numbers = [p["number"] for p in prs]
    try:
        if not prs:
            print("[FAIL] hermes finished but opened NO pull request for the smoke branch.")
            print("       The model did not use its file/git tools (BUG-3) -- do NOT rely on it.")
            return 1
        pr = prs[0]
        print(f"[PASS] coder opened a real PR: {pr.get('url')} (draft={pr.get('isDraft')})")
        return 0
    finally:
        print("[smoke] cleaning up (closing PR + deleting branch)...")
        try:
            _smoke_cleanup(repo, branch, pr_numbers)
            print("[smoke] cleanup done.")
        except Exception as e:  # noqa: BLE001 — report, never mask the PASS/FAIL
            print(f"[smoke] cleanup warning (remove manually): {e}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Test that a role's configured model responds.")
    ap.add_argument("role", choices=ROLES)
    ap.add_argument("--model", default=None, help="override the model id (else from models.env)")
    ap.add_argument("--timeout", type=int, default=150, help="hard timeout seconds (default 150)")
    ap.add_argument("--smoke", action="store_true",
                    help="coder only: full agentic round-trip (branch+commit+draft PR) on "
                         "--repo, verify the PR landed, then clean up (BUG-3)")
    ap.add_argument("--repo", default=None, help="target repo for --smoke (owner/repo)")
    args = ap.parse_args(argv)

    if args.smoke:
        if args.role != "coder":
            ap.error("--smoke is only meaningful for the coder role (agentic tool use)")
        if not args.repo:
            ap.error("--smoke requires --repo owner/repo (it creates a throwaway PR there)")
        model = args.model or harness.PING_DEFAULT_MODEL["coder"]()
        # the smoke test does real work -> allow much more time than a ping
        return run_smoke(model, args.repo, max(args.timeout, harness.DEFAULT_CODER_TIMEOUT_S))

    model = args.model or harness.PING_DEFAULT_MODEL[args.role]()
    cmd, stdin_text = harness.PING_BUILDERS[args.role](model)
    print(f"[check] role={args.role}  model={model}  (timeout {args.timeout}s)")

    cwd = None
    ctx = tempfile.TemporaryDirectory(prefix="maxagency-check-", ignore_cleanup_errors=True) \
        if args.role in NEUTRAL_CWD_ROLES else None
    try:
        if ctx is not None:
            cwd = ctx.__enter__()
        result = harness.run_llm(cmd, args.timeout, input_text=stdin_text, cwd=cwd)
    finally:
        if ctx is not None:
            ctx.__exit__(None, None, None)

    reply = (result.get("stdout") or "").strip()
    if result["timed_out"]:
        print(f"[FAIL] timed out after {args.timeout}s (model/CLI not responding)")
        return 1
    if result["returncode"] not in (0, None) or not reply:
        err = (result.get("stderr") or "").strip()
        print(f"[FAIL] returncode={result['returncode']}")
        if err:
            print("  stderr:", err[:500])
        if reply:
            print("  stdout:", reply[:500])
        return 1
    print(f"[PASS] {args.role} model responded:")
    print("  " + reply.replace("\n", "\n  ")[:500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
