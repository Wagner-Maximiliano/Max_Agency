#!/usr/bin/env python3
"""Max Agency gate — Phase 2A (dry-run, read-only).

The six things, nothing more:
  1. Read open issues with the scope label (default AI-GATE-TEST)
  2. Classify each using the state-machine table (classifier.py)
  3. Print the intended action (unknown/conflicting -> "unknown-state", no action)
  4. Write a structured log to runtime/logs/gate/<run_id>.jsonl
  5. Use gate.lock so runs cannot overlap
  6. Change nothing

Modes: only `dry-run` is implemented in 2A. `--audit-all-open` additionally reports which
open issues would be ignored (no scope label) — audit only, never acted on.

Exit codes: 0 ok (incl. lock-held-skip) · 2 auth/permission · 3 unexpected.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import executor
from classifier import IssueContext, classify

MARKER_TOKEN = "max-agency-dispatch"
APPROVAL_AUTHORS = {"OWNER", "MEMBER", "COLLABORATOR"}
BRANCH_PREFIX = "max-agency/issue-"

EXIT_OK = 0
EXIT_AUTH = 2
EXIT_UNEXPECTED = 3


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ── GitHub access (read-only) ────────────────────────────────────────────────
class GhError(Exception):
    pass


def gh_json(args: list[str]) -> object:
    """Run a read-only `gh` command and parse JSON stdout. Raises GhError on failure."""
    try:
        out = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60)
    except FileNotFoundError as e:
        raise GhError("gh CLI not found on PATH") from e
    except subprocess.TimeoutExpired as e:
        raise GhError("gh call timed out") from e
    if out.returncode != 0:
        err = (out.stderr or "").strip()
        if re.search(r"(?i)permission|403|401|auth", err):
            raise GhError(f"AUTH: {err}")
        raise GhError(err or "gh call failed")
    return json.loads(out.stdout or "null")


# ── Marker + approval parsing ────────────────────────────────────────────────
def parse_marker(body: str) -> dict | None:
    """Parse the fields of a max-agency-dispatch HTML-comment marker, or None."""
    if MARKER_TOKEN not in body:
        return None
    fields: dict[str, str] = {}
    for line in body.splitlines():
        m = re.match(r"\s*([a-z_]+):\s*(.+?)\s*$", line)
        if m and m.group(1) in {"run_id", "issue", "role", "model", "attempt", "status", "ts"}:
            fields[m.group(1)] = m.group(2)
    return fields or None


def latest_marker(comments: list[dict]) -> dict | None:
    markers = [m for c in comments if (m := parse_marker(c.get("body", "") or ""))]
    if not markers:
        return None
    return markers[-1]  # comments arrive chronological; last marker is newest


def find_marker(comments: list[dict]) -> tuple[dict | None, str | None]:
    """Return (fields, comment_id) of the newest marker comment, or (None, None)."""
    found: tuple[dict | None, str | None] = (None, None)
    for c in comments:
        fields = parse_marker(c.get("body", "") or "")
        if fields:
            cid = c.get("id")
            found = (fields, str(cid) if cid is not None else None)
    return found


def marker_is_active(marker: dict | None, stuck_min: int) -> bool:
    if not marker or marker.get("status") not in {"started", "pr-open"}:
        return False
    ts = marker.get("ts")
    if not ts:
        return False
    try:
        age_min = (now() - datetime.fromisoformat(ts.replace("Z", "+00:00"))).total_seconds() / 60
    except ValueError:
        return False
    return age_min < stuck_min


def parse_approval(comments: list[dict]) -> str | None:
    """Latest owner/maintainer approval intent on a plan-ready issue: approve|changes|None."""
    result = None
    for c in comments:
        body = c.get("body", "") or ""
        if MARKER_TOKEN in body:
            continue  # never treat a machine marker as approval
        if (c.get("authorAssociation") or "").upper() not in APPROVAL_AUTHORS:
            continue
        for raw in body.splitlines():
            line = raw.strip()
            if line.startswith(">"):
                continue  # ignore quoted text
            low = line.lower()
            if low.startswith("changes:"):
                result = "changes"
            elif low.startswith("approve"):
                # ambiguous "approve but change X" -> treat as changes
                result = "changes" if ("change" in low or "but" in low) else "approve"
    return result


# ── Context assembly ─────────────────────────────────────────────────────────
def build_context(issue: dict, pr_map: dict, closed_numbers: set[int], stuck_min: int) -> IssueContext:
    labels = {l["name"] for l in issue.get("labels", [])}
    comments = issue.get("comments", []) or []
    marker = latest_marker(comments)
    marker_fields, marker_comment_id = find_marker(comments)
    num = issue["number"]
    pr = pr_map.get(num)
    deps = parse_depends_on(issue.get("body", "") or "")
    return IssueContext(
        number=num,
        labels=labels,
        title=issue.get("title", "") or "",
        approval=parse_approval(comments),
        marker_active=marker_is_active(marker, stuck_min),
        kickoff_created=bool(marker_fields and marker_fields.get("status") == "kickoff-created"),
        marker_comment_id=marker_comment_id,
        linked_pr_open=bool(pr and pr["state"] == "OPEN"),
        pr_merged=bool(pr and pr["state"] == "MERGED"),
        deps_closed=bool(deps) and all(d in closed_numbers for d in deps),
        cto_verdict_present=any(
            re.match(r"\s*(APPROVE_MERGE|REQUEST_CHANGES|ESCALATE_HUMAN|REJECT_CLOSE)\b",
                     (c.get("body", "") or "").strip())
            for c in comments
        ),
    )


def parse_depends_on(body: str) -> list[int]:
    m = re.search(r"Depends-on:\s*(.+)", body)
    if not m:
        return []
    raw = m.group(1).strip()
    if raw.lower() in ("none", ""):
        return []
    return [int(x.strip().lstrip("#")) for x in raw.split(",") if x.strip().lstrip("#").isdigit()]


def build_pr_map(prs: list[dict]) -> dict:
    """Map issue number -> {state, number} via head-branch prefix or 'Closes #N'."""
    out: dict[int, dict] = {}
    for pr in prs:
        num = None
        head = pr.get("headRefName", "") or ""
        m = re.match(rf"{re.escape(BRANCH_PREFIX)}(\d+)/", head)
        if m:
            num = int(m.group(1))
        else:
            mb = re.search(r"(?:Closes|Fixes)\s+#(\d+)", pr.get("body", "") or "", re.IGNORECASE)
            if mb:
                num = int(mb.group(1))
        if num is not None:
            out[num] = {"state": pr.get("state", ""), "number": pr.get("number")}
    return out


# ── Lock ─────────────────────────────────────────────────────────────────────
def acquire_lock(lock_path: Path, run_id: str, stale_min: int, log) -> bool:
    """Return True if we hold the lock; False if a fresh lock is held (skip this run)."""
    if lock_path.exists():
        try:
            data = json.loads(lock_path.read_text())
            started = datetime.fromisoformat(data["start"].replace("Z", "+00:00"))
            age_min = (now() - started).total_seconds() / 60
        except (ValueError, KeyError, json.JSONDecodeError):
            age_min = stale_min + 1  # corrupt lock => treat as stale
        if age_min < stale_min:
            log("lock-held-skip", held_by=_safe_lock_owner(lock_path), age_min=round(age_min, 1))
            return False
        log("lock-stale-reclaim", age_min=round(age_min, 1))
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps({"run_id": run_id, "start": iso(now())}))
    return True


def _safe_lock_owner(lock_path: Path) -> str | None:
    try:
        return json.loads(lock_path.read_text()).get("run_id")
    except Exception:
        return None


def release_lock(lock_path: Path, run_id: str) -> None:
    # Only remove the lock if it's still ours (avoid deleting a reclaimer's lock).
    if lock_path.exists() and _safe_lock_owner(lock_path) == run_id:
        lock_path.unlink()


# ── Main ─────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Max Agency gate (Phase 2A dry-run)")
    ap.add_argument("--repo", default=os.environ.get("PROJECT_REPO"), help="owner/repo")
    ap.add_argument("--scope-label", default="AI-GATE-TEST")
    ap.add_argument("--mode", choices=["dry-run", "deterministic-only"], default="dry-run",
                    help="dry-run prints only; deterministic-only also executes "
                         "non-LLM moves (promote/close/approval routing)")
    ap.add_argument("--audit-all-open", action="store_true",
                    help="also report open issues that would be ignored (no scope label)")
    ap.add_argument("--stuck-min", type=int, default=60)
    ap.add_argument("--stale-min", type=int, default=15, help="lock staleness threshold")
    ap.add_argument("--runtime-dir", default="runtime")
    args = ap.parse_args(argv)

    if not args.repo:
        print("NO_REPO: set --repo or PROJECT_REPO", file=sys.stderr)
        return EXIT_AUTH

    run_id = f"{now().strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:4]}"
    runtime = Path(args.runtime_dir)
    log_path = runtime / "logs" / "gate" / f"{run_id}.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fp = log_path.open("a")

    def log(event: str, **kw) -> None:
        log_fp.write(json.dumps({"run_id": run_id, "ts": iso(now()), "event": event, **kw}) + "\n")
        log_fp.flush()

    lock_path = runtime / "gate.lock"
    try:
        log("start", repo=args.repo, mode=args.mode, scope=args.scope_label)
        if not acquire_lock(lock_path, run_id, args.stale_min, log):
            return EXIT_OK  # another run holds a fresh lock — not a failure

        try:
            issues = gh_json(["issue", "list", "--repo", args.repo, "--label", args.scope_label,
                              "--state", "open", "--json", "number,title,labels,body,comments",
                              "--limit", "100"]) or []
            prs = gh_json(["pr", "list", "--repo", args.repo, "--state", "all",
                           "--json", "number,state,body,headRefName", "--limit", "100"]) or []
            closed = gh_json(["issue", "list", "--repo", args.repo, "--state", "closed",
                              "--json", "number", "--limit", "200"]) or []
        except GhError as e:
            if str(e).startswith("AUTH"):
                log("auth-error", detail=str(e))
                print(f"TICK_FAIL auth: {e}", file=sys.stderr)
                return EXIT_AUTH
            log("gh-error", detail=str(e))
            print(f"TICK_FAIL gh: {e}", file=sys.stderr)
            return EXIT_UNEXPECTED

        pr_map = build_pr_map(prs)
        closed_numbers = {c["number"] for c in closed}
        writer = executor.GitHubWriter(args.repo) if args.mode == "deterministic-only" else None

        log("scan", scoped_issue_count=len(issues))
        counts: dict[str, int] = {}
        mutations = 0
        for issue in issues:
            ctx = build_context(issue, pr_map, closed_numbers, args.stuck_min)
            decision = classify(ctx)
            counts[decision.detected_state] = counts.get(decision.detected_state, 0) + 1
            labels_str = "+".join(sorted(issue_label_names(issue)))
            print(f"#{decision.number} · {labels_str} · {decision.detected_state} · "
                  f"{decision.intended_action} · {decision.reason}")
            log("decision", issue=decision.number, labels=sorted(issue_label_names(issue)),
                detected_state=decision.detected_state, intended_action=decision.intended_action,
                reason=decision.reason, llm=decision.llm)

            if writer is not None:
                ops = executor.plan_actions(decision, ctx, run_id, args.scope_label)
                for op in ops:
                    try:
                        writer.apply(op)
                        mutations += 1
                        log("mutation", issue=decision.number, op=op["op"])
                    except Exception as e:  # one bad write must not halt the board
                        log("mutation-error", issue=decision.number, op=op["op"], detail=repr(e))

        if args.audit_all_open:
            audit_ignored(args, log)

        log("done", counts=counts, dry_run=(args.mode == "dry-run"), mutations=mutations)
        return EXIT_OK
    except Exception as e:  # fail-safe: never crash mid-board without a logged reason
        log("unexpected", detail=repr(e))
        print(f"TICK_FAIL unexpected: {e!r}", file=sys.stderr)
        return EXIT_UNEXPECTED
    finally:
        release_lock(lock_path, run_id)
        log_fp.close()


def issue_label_names(issue: dict) -> list[str]:
    return [l["name"] for l in issue.get("labels", [])]


def audit_ignored(args, log) -> None:
    """Report (never act on) open issues lacking the scope label."""
    try:
        all_open = gh_json(["issue", "list", "--repo", args.repo, "--state", "open",
                            "--json", "number,labels", "--limit", "200"]) or []
    except GhError as e:
        log("audit-error", detail=str(e))
        return
    for issue in all_open:
        names = issue_label_names(issue)
        if args.scope_label not in names:
            print(f"#{issue['number']} · {'+'.join(sorted(names)) or '(none)'} · ignored · "
                  f"no-action · no scope label")
            log("audit-ignored", issue=issue["number"], labels=sorted(names))


if __name__ == "__main__":
    sys.exit(main())
