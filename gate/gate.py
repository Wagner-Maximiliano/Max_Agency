#!/usr/bin/env python3
"""Max Agency gate — runner (Phases 2A dry-run · 2B deterministic · 2C triage).

The core loop:
  1. Read open issues with the scope label (default AI; migration testing used AI-GATE-TEST)
  2. Classify each using the state-machine table (classifier.py)
  3. Print the intended action (unknown/conflicting -> "unknown-state", no action)
  4. Write a structured log to runtime/logs/gate/<run_id>.jsonl
  5. Use gate.lock so runs cannot overlap

Modes:
  dry-run            print only; change nothing (2A). `--audit-all-open` also reports
                     open issues that would be ignored (no scope label).
  deterministic-only also execute non-LLM moves: promote/close/approval routing (2B).
  dispatch-enabled   additionally invoke the orchestrator to triage scope-only issues
                     (2C). The LLM only classifies (read-only); the gate applies the
                     verdict label deterministically, under a hard subprocess timeout.

Exit codes: 0 ok (incl. lock-held-skip) · 2 auth/permission · 3 unexpected.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import executor
import harness
from classifier import IssueContext, classify

MARKER_TOKEN = "max-agency-dispatch"
APPROVAL_AUTHORS = {"OWNER", "MEMBER", "COLLABORATOR"}
BRANCH_PREFIX = "max-agency/issue-"

EXIT_OK = 0
EXIT_AUTH = 2
EXIT_UNEXPECTED = 3

# On Windows, suppress the console window for child processes (gh/codex/wsl/claude) so the
# scheduled gate runs silently in the background. No-op (0) on POSIX.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


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
        out = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60,
                             creationflags=NO_WINDOW)
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


def gh_text(args: list[str]) -> str:
    """Run a read-only `gh` command and return raw stdout (e.g. `gh pr diff`)."""
    try:
        out = subprocess.run(["gh", *args], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=60,
                             creationflags=NO_WINDOW)
    except FileNotFoundError as e:
        raise GhError("gh CLI not found on PATH") from e
    except subprocess.TimeoutExpired as e:
        raise GhError("gh call timed out") from e
    if out.returncode != 0:
        raise GhError((out.stderr or "").strip() or "gh call failed")
    return out.stdout or ""


def ci_is_green(rollup: list | None) -> bool:
    """True if the PR's statusCheckRollup has no failing/pending checks (empty = no CI)."""
    for c in rollup or []:
        state = (c.get("state") or "").upper()
        status = (c.get("status") or "").upper()
        concl = (c.get("conclusion") or "").upper()
        if state in ("FAILURE", "ERROR") or concl in (
                "FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE"):
            return False
        if state == "PENDING" or status in ("IN_PROGRESS", "QUEUED", "PENDING", "WAITING"):
            return False
    return True


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


def latest_changes_feedback(comments: list[dict]) -> str:
    """The text of the latest owner `CHANGES:` comment (fed to the architect on a revision)."""
    feedback = ""
    for c in comments:
        body = c.get("body", "") or ""
        if MARKER_TOKEN in body:
            continue
        if (c.get("authorAssociation") or "").upper() not in APPROVAL_AUTHORS:
            continue
        if any(line.strip().lower().startswith("changes:") for line in body.splitlines()):
            feedback = body.strip()
    return feedback


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
        kickoff_expanded=bool(marker_fields and
                              marker_fields.get("status") in ("expanding", "expanded")),
        attempt=_marker_attempt(marker_fields),
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


def _marker_attempt(marker_fields: dict | None) -> int:
    """The coder attempt count recorded in the latest marker (0 if absent/unparseable)."""
    if not marker_fields:
        return 0
    raw = str(marker_fields.get("attempt", "")).strip()
    return int(raw) if raw.isdigit() else 0


PROJECT_CONFIG_FILE = "Max_AgencyConfig.md"


def fetch_project_models(repo: str, log) -> dict:
    """Fetch + parse the project repo's Max_AgencyConfig.md (per-project model overrides).

    Fail-safe: a missing/unreadable/malformed file → {} (the gate uses the global defaults).
    Only GATE_* keys are honored (security boundary; see harness.parse_model_config).
    """
    try:
        encoded = gh_text(["api", f"repos/{repo}/contents/{PROJECT_CONFIG_FILE}", "--jq", ".content"])
    except GhError:
        return {}  # no config file (or unreadable) — global defaults
    try:
        text = base64.b64decode(encoded).decode("utf-8", "replace") if encoded.strip() else ""
    except (ValueError, TypeError):
        return {}
    cfg = harness.parse_model_config(text)
    if cfg:
        log("project-config", file=PROJECT_CONFIG_FILE, models=cfg)
    return cfg


def resolve_models(args, project_cfg: dict, log) -> None:
    """Resolve each role's model in place: CLI flag > project Max_AgencyConfig.md > global
    default (gate/models.env or hardcoded). Mutates args; logs the effective models."""
    args.coder_model = (args.coder_model or project_cfg.get("GATE_CODER_MODEL")
                        or harness.DEFAULT_CODER_MODEL)
    args.triage_model = (args.triage_model or project_cfg.get("GATE_TRIAGE_MODEL")
                         or harness.DEFAULT_TRIAGE_MODEL)
    args.architect_model = (args.architect_model or project_cfg.get("GATE_ARCHITECT_MODEL")
                            or harness.DEFAULT_ARCHITECT_MODEL)
    args.cto_model = (args.cto_model or project_cfg.get("GATE_CTO_MODEL")
                      or harness.DEFAULT_CTO_MODEL)
    log("models", coder=args.coder_model, triage=args.triage_model,
        architect=args.architect_model, cto=args.cto_model,
        per_project=bool(project_cfg))


def parse_parent_ref(body: str) -> int | None:
    """The parent issue number a kickoff was created from (`Approved-plan: #N`)."""
    m = re.search(r"Approved-plan:\s*#(\d+)", body or "")
    return int(m.group(1)) if m else None


def _issue_number_from_url(url: str | None) -> int | None:
    m = re.search(r"/issues/(\d+)", url or "")
    return int(m.group(1)) if m else None


def _comment_id_from_url(url: str | None) -> str | None:
    m = re.search(r"#issuecomment-(\d+)", url or "")
    return m.group(1) if m else None


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
    ap.add_argument("--scope-label", default="AI",
                    help="the human opt-in/kill-switch label that scopes the gate's work "
                         "(production: AI, from Phase 2F; migration testing used AI-GATE-TEST)")
    ap.add_argument("--mode", choices=["dry-run", "deterministic-only", "dispatch-enabled"],
                    default="dry-run",
                    help="dry-run prints only; deterministic-only also executes non-LLM "
                         "moves (promote/close/approval routing); dispatch-enabled additionally "
                         "invokes the orchestrator to triage scope-only issues (Phase 2C)")
    ap.add_argument("--audit-all-open", action="store_true",
                    help="also report open issues that would be ignored (no scope label)")
    ap.add_argument("--stuck-min", type=int, default=60)
    ap.add_argument("--stale-min", type=int, default=15, help="lock staleness threshold")
    ap.add_argument("--triage-model", default=None,
                    help="orchestrator model for triage/expand (else the project's "
                         "Max_AgencyConfig.md, then gate/models.env, then gpt-5.4-mini)")
    ap.add_argument("--llm-timeout", type=int, default=harness.DEFAULT_LLM_TIMEOUT_S,
                    help="hard timeout (s) per LLM/CLI call; a hung harness is killed")
    ap.add_argument("--coder-model", default=None,
                    help="coder model via wsl->hermes/OpenRouter (else the project's "
                         "Max_AgencyConfig.md, then gate/models.env, then xiaomi/mimo-v2.5)")
    ap.add_argument("--coder-timeout", type=int, default=harness.DEFAULT_CODER_TIMEOUT_S,
                    help="hard timeout (s) for one coder run (does real work; default 1800). "
                         "When dispatching, set --stale-min >= this/60 so the lock isn't "
                         "reclaimed mid-build")
    ap.add_argument("--max-attempts", type=int, default=3,
                    help="coder dispatch attempts before a stuck issue is parked needs-human")
    ap.add_argument("--architect-model", default=None,
                    help="Claude model for the architect (else project Max_AgencyConfig.md / "
                         "models.env / opus)")
    ap.add_argument("--cto-model", default=None,
                    help="Claude model for the CTO (else project Max_AgencyConfig.md / "
                         "models.env / opus)")
    ap.add_argument("--claude-timeout", type=int, default=harness.DEFAULT_CLAUDE_TIMEOUT_S,
                    help="hard timeout (s) for a Claude architect/CTO call (default 300)")
    ap.add_argument("--auto-merge", action=argparse.BooleanOptionalAction, default=True,
                    help="on CTO APPROVE_MERGE + HUMAN-REVIEW:NO + CI green, squash-merge; "
                         "--no-auto-merge holds every approved PR for a human instead")
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
        writes_enabled = args.mode in ("deterministic-only", "dispatch-enabled")
        writer = executor.GitHubWriter(args.repo) if writes_enabled else None

        # Per-project model selection: the repo's own Max_AgencyConfig.md (if present) overrides
        # the global defaults. CLI flag > project config > gate/models.env > hardcoded.
        resolve_models(args, fetch_project_models(args.repo, log), log)

        log("scan", scoped_issue_count=len(issues))
        counts: dict[str, int] = {}
        mutations = 0
        # At most one coder is dispatched per tick (roadmap: "for one ready issue") — a coder
        # run is long and synchronous; fanning out would serialize 30-min builds per tick.
        coder_dispatched = False
        for issue in issues:
            # Per-issue isolation: any unexpected error on one issue is logged and the board
            # keeps processing the rest (fail-safe — one bad issue never halts the tick).
            try:
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

                    # Phase 2C–2E LLM-dispatch actions (only in dispatch-enabled mode). Each is
                    # fail-safe: a hung/failed harness is a logged no-op, retried next tick.
                    if args.mode == "dispatch-enabled":
                        act = decision.intended_action
                        if act == "would-triage":
                            mutations += dispatch_triage(writer, issue, decision, args, log)
                        elif act == "would-expand-kickoff":
                            mutations += dispatch_expand(writer, issue, ctx, decision,
                                                         run_id, args, log)
                        elif act == "would-invoke-architect":
                            mutations += dispatch_architect(writer, issue, ctx, decision,
                                                            run_id, args, log)
                        elif act == "would-invoke-cto":
                            mutations += dispatch_cto(writer, issue, ctx, decision,
                                                      run_id, args, log, pr_map)
                        elif act == "would-recover" and ctx.attempt >= args.max_attempts:
                            # Cheap (label + comment), not a coder run — never budget-limited.
                            mutations += escalate_coder(writer, ctx, decision, run_id, args, log)
                        elif act in ("would-dispatch-coder", "would-recover"):
                            if coder_dispatched:
                                log("coder-deferred-this-tick", issue=decision.number, action=act)
                            else:
                                from_label = "ready" if act == "would-dispatch-coder" else "in-progress"
                                mutations += dispatch_coder(writer, ctx, decision, run_id,
                                                            args, log, from_label)
                                coder_dispatched = True
            except Exception as e:  # fail-safe: isolate this issue, keep the board moving
                log("issue-error", issue=issue.get("number"), detail=repr(e))
                print(f"ISSUE_FAIL #{issue.get('number')}: {e!r}", file=sys.stderr)

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


def dispatch_triage(writer, issue: dict, decision, args, log) -> int:
    """Invoke the orchestrator to triage one scope-only issue; apply the label deterministically.

    Returns the number of mutations applied (0 on any failure — fail safe). The LLM only
    classifies (read-only, no tools); the gate applies the verdict label via the executor.
    """
    n = decision.number
    cmd = harness.build_triage_command(args.triage_model)
    stdin = harness.issue_to_stdin(issue.get("title", "") or "", issue.get("body", "") or "")
    result = harness.run_llm(cmd, args.llm_timeout, input_text=stdin)

    if result["timed_out"]:
        log("triage-timeout", issue=n, timeout_s=args.llm_timeout)
        return 0
    if result["returncode"] != 0:
        log("triage-failed", issue=n, returncode=result["returncode"],
            detail=(result["stderr"] or "")[:300])
        return 0

    label, reason = harness.parse_triage_verdict(result["stdout"])
    if label is None:
        log("triage-unparsed", issue=n, stdout=(result["stdout"] or "")[:300])
        return 0

    log("triage-verdict", issue=n, label=label, model=args.triage_model, reason=reason[:200])
    mutations = 0
    for op in executor.plan_triage_ops(n, label, reason):
        try:
            writer.apply(op)
            mutations += 1
            log("mutation", issue=n, op=op["op"])
        except Exception as e:  # one bad write must not halt the board
            log("mutation-error", issue=n, op=op["op"], detail=repr(e))
            # If the label didn't land (e.g. a workflow label is missing from the repo),
            # the issue stays scope-only — do NOT post the rationale comment, or it would
            # duplicate every tick. Stop; next tick retries cleanly once labels exist.
            if op["op"] == "edit_labels":
                break
    return mutations


def _apply_ops(writer, n: int, ops: list[dict], log,
               critical_ops: tuple[str, ...] = ("edit_labels",)) -> int:
    """Apply mutation ops fail-safe; abort if a *critical* op fails (so a follow-on
    comment/marker can't spam every tick, and we don't advance state on a failed write).
    Returns the count applied. `edit_labels` is critical by default; the architect also
    treats `upsert_file` as critical (no plan persisted ⇒ don't flip to plan-ready)."""
    mutations = 0
    for op in ops:
        try:
            writer.apply(op)
            mutations += 1
            log("mutation", issue=n, op=op["op"])
        except Exception as e:  # one bad write must not halt the board
            log("mutation-error", issue=n, op=op["op"], detail=repr(e))
            if op["op"] in critical_ops:
                break  # state-changing write didn't land; stop before trailing ops
    return mutations


def dispatch_coder(writer, ctx, decision, run_id, args, log, from_label) -> int:
    """Claim a coder issue (label + in-flight marker) then run the coder under a hard timeout.

    Fail-safe: a hung/failed coder is a logged outcome, never fatal. No post-run marker
    write — recovery is driven next tick by marker-staleness + PR presence. `from_label`
    is `ready` for a fresh dispatch, `in-progress` for a recovery re-dispatch.
    """
    n = decision.number
    attempt = ctx.attempt + 1  # marker records the new attempt before the blocking run
    model = args.coder_model

    # 1. Claim: label move + in-flight marker (label first; abort if the claim fails).
    start_ops = executor.plan_coder_dispatch_ops(
        n, attempt, run_id, model, ctx.marker_comment_id, from_label)
    mutations = _apply_ops(writer, n, start_ops, log)
    if mutations < len(start_ops):
        return mutations  # claim didn't fully land; next tick retries cleanly

    # 2. Dispatch the coder (blocking, hard timeout). Only the integer issue number reaches
    #    the command; hermes reads the untrusted issue text itself via gh (least exposure).
    #    Run from a NEUTRAL temp dir, never the gate's repo: the coder does git/gh under
    #    --yolo and a child launched from our checkout would mutate it (wsl.exe starts in
    #    the translated Windows cwd). Same safeguard the Phase 0 orchestrator got.
    branch = harness.coder_branch(n, attempt)
    log("coder-dispatch", issue=n, attempt=attempt, model=model, branch=branch,
        timeout_s=args.coder_timeout)
    cmd = harness.build_coder_command(model, args.repo, n, attempt)
    with tempfile.TemporaryDirectory(prefix="maxagency-coder-", ignore_cleanup_errors=True) as neutral_cwd:
        result = harness.run_llm(cmd, args.coder_timeout, cwd=neutral_cwd)

    if result["timed_out"]:
        log("coder-timeout", issue=n, attempt=attempt, timeout_s=args.coder_timeout)
    elif result["returncode"] not in (0, None):
        log("coder-failed", issue=n, attempt=attempt, returncode=result["returncode"],
            detail=(result["stderr"] or "")[:300])
    else:
        log("coder-done", issue=n, attempt=attempt, returncode=result["returncode"])
    return mutations


def dispatch_expand(writer, issue, ctx, decision, run_id, args, log) -> int:
    """Expand a kickoff issue's approved PLAN into concrete coder task issues (orchestrator).

    Read-only generation (codex, PLAN on stdin, neutral cwd); the gate creates the issues,
    resolving each task's deps to the real numbers created earlier in this run. An in-flight
    `expanding` marker is written BEFORE any create, so a crash can't trigger a re-expand
    (duplicate tasks); on success the kickoff is marked `expanded` and closed. Fail-safe.
    """
    n = decision.number  # the kickoff issue
    parent = parse_parent_ref(issue.get("body", "") or "")
    if parent is None:
        log("expand-no-parent", issue=n)
        return 0
    try:
        encoded = gh_text(["api", f"repos/{args.repo}/contents/plans/issue-{parent}/PLAN.md",
                           "--jq", ".content"])
        plan_md = base64.b64decode(encoded).decode("utf-8", "replace") if encoded.strip() else ""
    except (GhError, ValueError) as e:
        log("expand-no-plan", issue=n, parent=parent, detail=str(e)[:200])
        return 0
    if not plan_md.strip():
        log("expand-empty-plan", issue=n, parent=parent)
        return 0

    cmd = harness.build_expand_command(args.triage_model)
    with tempfile.TemporaryDirectory(prefix="maxagency-expand-", ignore_cleanup_errors=True) as neutral_cwd:
        result = harness.run_llm(cmd, args.llm_timeout, input_text=plan_md, cwd=neutral_cwd)
    if result["timed_out"]:
        log("expand-timeout", issue=n, timeout_s=args.llm_timeout)
        return 0
    if result["returncode"] not in (0, None):
        log("expand-failed", issue=n, returncode=result["returncode"],
            detail=(result["stderr"] or "")[:300])
        return 0
    tasks = harness.parse_expand_tasks(result["stdout"])
    if not tasks:
        log("expand-unparsed", issue=n, stdout=(result["stdout"] or "")[:300])
        return 0

    # In-flight claim FIRST (idempotency). Capture the new marker comment id so the
    # `expanded` finalize edits the same comment in place rather than adding a second.
    mutations = 0
    marker_cid = ctx.marker_comment_id
    try:
        out = writer.apply(executor.plan_expand_claim_op(n, run_id, marker_cid))
        marker_cid = marker_cid or _comment_id_from_url(out)
        mutations += 1
        log("mutation", issue=n, op="upsert_marker")
    except Exception as e:
        log("mutation-error", issue=n, op="upsert_marker", detail=repr(e))
        return mutations  # couldn't claim; next tick retries cleanly

    created: list[int] = []
    for task in tasks:
        dep_numbers = [created[j - 1] for j in task["depends_on"] if 1 <= j <= len(created)]
        op = executor.plan_task_issue_op(parent, n, args.scope_label,
                                         task["title"], task["body"], dep_numbers)
        try:
            num = _issue_number_from_url(writer.apply(op))
            if num is not None:
                created.append(num)
            mutations += 1
            log("mutation", issue=n, op="create_issue", created=num)
        except Exception as e:  # stop (later tasks may depend on this one); marker stays expanding
            log("mutation-error", issue=n, op="create_issue", detail=repr(e))
            break

    log("expand-done", issue=n, parent=parent, created=created, n_tasks=len(tasks))
    for op in executor.plan_kickoff_finalize_ops(n, created, run_id, marker_cid):
        try:
            writer.apply(op)
            mutations += 1
            log("mutation", issue=n, op=op["op"])
        except Exception as e:
            log("mutation-error", issue=n, op=op["op"], detail=repr(e))
    return mutations


def dispatch_architect(writer, issue, ctx, decision, run_id, args, log) -> int:
    """Invoke the architect (Claude) to produce a plan; persist it + move to plan-ready.

    Pure text-gen (no tools), brief on stdin, run from a neutral cwd. Fail-safe: a
    hung/failed/unusable generation is a logged no-op, retried next tick — nothing is
    written to the repo and the issue stays role:architect.
    """
    n = decision.number
    comments = issue.get("comments", []) or []
    feedback = latest_changes_feedback(comments)  # non-empty on a CHANGES revision
    cmd = harness.build_architect_command(args.architect_model)
    stdin = harness.issue_to_architect_stdin(
        issue.get("title", "") or "", issue.get("body", "") or "", feedback)
    with tempfile.TemporaryDirectory(prefix="maxagency-arch-", ignore_cleanup_errors=True) as neutral_cwd:
        result = harness.run_llm(cmd, args.claude_timeout, input_text=stdin, cwd=neutral_cwd)

    if result["timed_out"]:
        log("architect-timeout", issue=n, timeout_s=args.claude_timeout)
        return 0
    if result["returncode"] not in (0, None):
        log("architect-failed", issue=n, returncode=result["returncode"],
            detail=(result["stderr"] or "")[:300])
        return 0
    plan = result["stdout"] or ""
    if not harness.is_plan_usable(plan):
        log("architect-unusable", issue=n, stdout=plan[:300])
        return 0

    log("architect-plan", issue=n, chars=len(plan), revised=bool(feedback))
    ops = executor.plan_architect_ops(n, plan, run_id, ctx.marker_comment_id)
    return _apply_ops(writer, n, ops, log, critical_ops=("upsert_file", "edit_labels"))


def dispatch_cto(writer, issue, ctx, decision, run_id, args, log, pr_map) -> int:
    """Invoke the CTO (Claude) to review the linked PR; route the verdict deterministically.

    Pure text-gen (no tools): the gate fetches the diff + PR meta and feeds them on stdin;
    Claude returns a first-line verdict token; the gate applies the route (merge / hold /
    bounce / escalate / reject). Fail-safe: a hung/failed/unparsed review is a logged no-op.
    """
    n = decision.number
    pr = pr_map.get(n)
    if not pr or pr.get("number") is None:
        log("cto-no-pr", issue=n)
        return 0
    pr_number = pr["number"]
    try:
        diff = gh_text(["pr", "diff", str(pr_number), "--repo", args.repo])
        meta = gh_json(["pr", "view", str(pr_number), "--repo", args.repo,
                        "--json", "title,body,statusCheckRollup"]) or {}
    except GhError as e:
        log("cto-fetch-error", issue=n, detail=str(e)[:200])
        return 0

    stdin = harness.pr_to_cto_stdin(
        issue.get("title", "") or "", issue.get("body", "") or "",
        meta.get("title", "") or "", meta.get("body", "") or "", diff)
    cmd = harness.build_cto_command(args.cto_model)
    with tempfile.TemporaryDirectory(prefix="maxagency-cto-", ignore_cleanup_errors=True) as neutral_cwd:
        result = harness.run_llm(cmd, args.claude_timeout, input_text=stdin, cwd=neutral_cwd)

    if result["timed_out"]:
        log("cto-timeout", issue=n, timeout_s=args.claude_timeout)
        return 0
    if result["returncode"] not in (0, None):
        log("cto-failed", issue=n, returncode=result["returncode"],
            detail=(result["stderr"] or "")[:300])
        return 0
    verdict, human_review, reason = harness.parse_cto_verdict(result["stdout"])
    if verdict is None:
        log("cto-unparsed", issue=n, stdout=(result["stdout"] or "")[:300])
        return 0

    ci_green = ci_is_green(meta.get("statusCheckRollup"))
    log("cto-verdict", issue=n, verdict=verdict, human_review=human_review,
        ci_green=ci_green, pr=pr_number, reason=reason[:200])
    ops = executor.plan_cto_ops(verdict, human_review, reason, n, pr_number, run_id,
                                ctx.marker_comment_id, ci_green=ci_green,
                                auto_merge=args.auto_merge)
    return _apply_ops(writer, n, ops, log,
                      critical_ops=("edit_labels", "merge_pr", "close", "close_pr"))


def escalate_coder(writer, ctx, decision, run_id, args, log) -> int:
    """Retry cap reached for a stuck coder issue → park it `needs-human`."""
    n = decision.number
    log("coder-escalate", issue=n, attempt=ctx.attempt, max_attempts=args.max_attempts)
    ops = executor.plan_recovery_escalation_ops(n, ctx.attempt, run_id, ctx.marker_comment_id)
    return _apply_ops(writer, n, ops, log)


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
