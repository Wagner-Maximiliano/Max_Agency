#!/usr/bin/env python3
"""Quick model self-test: confirm a role's configured model + its CLI/auth actually respond.

Usage:
    python gate/check_model.py <role> [--model ID] [--timeout S]

    role : coder | triage | architect | cto   (triage also covers kickoff expansion)

Runs a tiny, side-effect-free prompt through the SAME CLI path the gate uses for that role
(coder -> wsl/hermes/OpenRouter, triage -> codex, architect/cto -> claude), so a PASS means
the model id is valid, the CLI is installed, and auth/credentials work. Prints PASS/FAIL and
the model's reply. Exit 0 on PASS, 1 on FAIL.

The model id and keys are configured in gate/models.env (see that file).
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness  # noqa: E402

ROLES = ("coder", "triage", "architect", "cto")
# coder/architect/cto shell out to tool-capable CLIs -> run from a neutral cwd (never the repo)
NEUTRAL_CWD_ROLES = {"coder", "architect", "cto"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Test that a role's configured model responds.")
    ap.add_argument("role", choices=ROLES)
    ap.add_argument("--model", default=None, help="override the model id (else from models.env)")
    ap.add_argument("--timeout", type=int, default=150, help="hard timeout seconds (default 150)")
    args = ap.parse_args(argv)

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
