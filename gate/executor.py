"""Max Agency gate — deterministic action executor (Phase 2B).

Two layers, mirroring the classifier split:

* `plan_actions(decision, ctx, ...)` is **pure**: it turns a Decision into a list of mutation
  ops (plain dicts). No I/O, fully unit-tested.
* `GitHubWriter` applies ops via the `gh` CLI. Thin; the runner is injectable for tests.

Phase 2B executes only the **deterministic** actions (no LLM):
  - would-promote-ready   → backlog → ready
  - would-close           → close issue (linked PR merged)
  - would-reopen-architect→ plan-ready → role:architect (+ feedback comment + marker)
  - would-create-kickoff  → create a linked kickoff issue (+ idempotency marker)

Every LLM action (triage / dispatch-coder / invoke-architect / invoke-cto / recover) produces
NO ops here — it is logged as deferred and left for the dispatch phases (2C–2E).
"""

from __future__ import annotations

import base64
import json
import subprocess
from datetime import datetime, timezone

from classifier import Decision, IssueContext

MARKER_TOKEN = "max-agency-dispatch"

# Actions Phase 2B is allowed to execute. Anything else is deferred (no ops).
DETERMINISTIC_ACTIONS = {
    "would-promote-ready",
    "would-close",
    "would-reopen-architect",
    "would-create-kickoff",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def render_marker(fields: dict) -> str:
    lines = "\n".join(f"{k}: {v}" for k, v in fields.items())
    return f"<!-- {MARKER_TOKEN}\n{lines}\n-->"


def plan_actions(decision: Decision, ctx: IssueContext, run_id: str,
                 scope_label: str, ts: str | None = None) -> list[dict]:
    """Pure: map a Decision to deterministic mutation ops. Empty list if nothing to do."""
    action = decision.intended_action
    if action not in DETERMINISTIC_ACTIONS:
        return []  # LLM actions and no-ops are not executed in 2B
    ts = ts or _now_iso()
    n = decision.number

    if action == "would-promote-ready":
        return [{"op": "edit_labels", "issue": n, "add": ["ready"], "remove": ["backlog"]}]

    if action == "would-close":
        return [{"op": "close", "issue": n, "reason": "completed",
                 "comment": "Closed by gate: linked PR merged."}]

    if action == "would-reopen-architect":
        marker = {"run_id": run_id, "issue": n, "status": "changes-routed", "ts": ts}
        return [
            {"op": "edit_labels", "issue": n, "add": ["role:architect"],
             "remove": ["plan-ready"]},
            {"op": "comment", "issue": n,
             "body": "Gate: owner requested CHANGES (see latest comment). Routing back to "
                     "the architect to revise the plan."},
            {"op": "upsert_marker", "issue": n, "comment_id": ctx.marker_comment_id,
             "body": render_marker(marker)},
        ]

    if action == "would-create-kickoff":
        title = f"[AI-{n}] kickoff: {ctx.title}".strip()
        body = (f"Auto-created by gate after owner approval.\n\n"
                f"Approved-plan: #{n}\nPlan: /plans/issue-{n}/PLAN.md\n\n"
                f"Expand this PLAN into task issues (orchestrator).")
        marker = {"run_id": run_id, "issue": n, "status": "kickoff-created", "ts": ts}
        return [
            {"op": "create_issue", "title": title, "body": body,
             "labels": [scope_label, "kickoff"]},
            {"op": "upsert_marker", "issue": n, "comment_id": ctx.marker_comment_id,
             "body": render_marker(marker)},
        ]

    return []  # unreachable, but fail safe


# A triage verdict label → the full label set that lands the issue in a *coherent* next
# state (else a lone role:coder falls through the classifier to unknown-state). A directly
# triaged coder task has no plan dependencies, so it enters the coder lane at `ready`
# (→ would-dispatch-coder in 2D). Architect/needs-human need no companion state label.
TRIAGE_ENTRY_LABELS = {
    "role:coder": ["role:coder", "ready"],
    "role:architect": ["role:architect"],
    "needs-human": ["needs-human"],
}


def plan_triage_ops(issue_number: int, label: str, reason: str) -> list[dict]:
    """Pure: turn an orchestrator triage verdict into mutation ops (Phase 2C).

    Labels first (the state-changing, idempotency-critical op): once they land the issue
    is no longer scope-only, so it won't re-triage even if the rationale comment fails. The
    scope label is intentionally left in place (it's the human's opt-in/kill-switch).
    """
    add = TRIAGE_ENTRY_LABELS.get(label, [label])
    ops: list[dict] = [
        {"op": "edit_labels", "issue": issue_number, "add": add, "remove": []},
    ]
    if reason:
        ops.append({"op": "comment", "issue": issue_number,
                    "body": f"Gate triaged as `{label}`: {reason}"})
    return ops


# ── Phase 2E: architect (plan generation) ─────────────────────────────────────
def plan_architect_ops(issue_number: int, plan_md: str, run_id: str,
                       comment_id: str | None, ts: str | None = None) -> list[dict]:
    """Pure: persist an architect-generated plan and move the issue to plan-ready (Phase 2E).

    Order: write PLAN.md → post the plan comment → flip the label (the idempotency guard:
    once `plan-ready` lands the issue won't re-invoke the architect) → marker. A retry
    after a mid-run crash regenerates + re-comments (at most one duplicate comment), then
    flips the label cleanly. Approval routing (APPROVE/CHANGES) is the existing 2B path.
    """
    ts = ts or _now_iso()
    path = f"plans/issue-{issue_number}/PLAN.md"
    marker = {"run_id": run_id, "issue": issue_number, "role": "architect",
              "status": "plan-generated", "ts": ts}
    comment = (f"Gate: the architect produced a plan at `{path}`. Reply `APPROVE` to kick "
               f"off the build, or `CHANGES: <feedback>` to revise.\n\n---\n\n{plan_md}")
    return [
        {"op": "upsert_file", "path": path, "content": plan_md,
         "message": f"plan(issue-{issue_number}): architect-generated PLAN"},
        {"op": "comment", "issue": issue_number, "body": comment},
        {"op": "edit_labels", "issue": issue_number, "add": ["plan-ready"],
         "remove": ["role:architect"]},
        {"op": "upsert_marker", "issue": issue_number, "comment_id": comment_id,
         "body": render_marker(marker)},
    ]


# ── Phase 2D: coder dispatch + recovery ───────────────────────────────────────
def _coder_marker(issue: int, attempt: int, run_id: str, model: str,
                  status: str, ts: str) -> dict:
    return {"run_id": run_id, "issue": issue, "role": "coder", "model": model,
            "attempt": attempt, "status": status, "ts": ts}


def plan_coder_dispatch_ops(issue_number: int, attempt: int, run_id: str, model: str,
                            comment_id: str | None, from_label: str = "ready",
                            ts: str | None = None) -> list[dict]:
    """Pure: claim a coder issue for dispatch (Phase 2D).

    Label move first (`ready`/`backlog` → `in-progress`), then the **in-flight marker** —
    the crash-safe claim written BEFORE the long blocking coder run. If the gate dies
    mid-build, the next tick sees `in-progress` + a fresh `started` marker and waits out
    STUCK_MIN before recovering. `attempt` is recorded so recovery can cap retries. There
    is deliberately no post-run marker write: recovery is driven by marker-staleness + PR
    presence (a real PR moves the issue to the review lane), per the roadmap.
    """
    ts = ts or _now_iso()
    remove = [from_label] if from_label and from_label != "in-progress" else []
    marker = _coder_marker(issue_number, attempt, run_id, model, "started", ts)
    return [
        {"op": "edit_labels", "issue": issue_number, "add": ["in-progress"], "remove": remove},
        {"op": "upsert_marker", "issue": issue_number, "comment_id": comment_id,
         "body": render_marker(marker)},
    ]


def plan_recovery_escalation_ops(issue_number: int, attempt: int, run_id: str,
                                 comment_id: str | None, ts: str | None = None) -> list[dict]:
    """Pure: retry cap reached — park the issue for a human (Phase 2D)."""
    ts = ts or _now_iso()
    marker = _coder_marker(issue_number, attempt, run_id, "", "escalated", ts)
    return [
        {"op": "edit_labels", "issue": issue_number, "add": ["needs-human"],
         "remove": ["in-progress"]},
        {"op": "comment", "issue": issue_number,
         "body": (f"Gate: the coder did not produce a PR after {attempt} attempt(s) "
                  f"(max reached). Parking for a human (`needs-human`).")},
        {"op": "upsert_marker", "issue": issue_number, "comment_id": comment_id,
         "body": render_marker(marker)},
    ]


class GitHubWriter:
    """Applies mutation ops via the `gh` CLI. Inject `runner` for testing."""

    def __init__(self, repo: str, runner=None, timeout: int = 60):
        self.repo = repo
        self._run = runner or self._default_runner
        self.timeout = timeout

    def _default_runner(self, args: list[str]) -> str:
        out = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=self.timeout)
        if out.returncode != 0:
            raise RuntimeError((out.stderr or "gh failed").strip())
        return out.stdout

    def apply(self, op: dict) -> None:
        kind = op["op"]
        repo = ["--repo", self.repo]
        if kind == "edit_labels":
            args = ["issue", "edit", str(op["issue"]), *repo]
            for lab in op.get("add", []):
                args += ["--add-label", lab]
            for lab in op.get("remove", []):
                args += ["--remove-label", lab]
            self._run(args)
        elif kind == "close":
            self._run(["issue", "close", str(op["issue"]), *repo,
                       "--reason", op["reason"], "--comment", op["comment"]])
        elif kind == "comment":
            self._run(["issue", "comment", str(op["issue"]), *repo, "--body", op["body"]])
        elif kind == "create_issue":
            args = ["issue", "create", *repo, "--title", op["title"], "--body", op["body"]]
            for lab in op.get("labels", []):
                args += ["--label", lab]
            self._run(args)
        elif kind == "upsert_marker":
            cid = op.get("comment_id")
            if cid:  # edit the existing per-issue marker in place
                self._update_comment(cid, op["body"])
            else:
                self._run(["issue", "comment", str(op["issue"]), *repo, "--body", op["body"]])
        elif kind == "upsert_file":
            self._upsert_file(op["path"], op["content"], op["message"], op.get("branch"))
        else:
            raise ValueError(f"unknown op: {kind}")

    def _update_comment(self, comment_id: str, body: str) -> None:
        """Edit an issue comment in place. `gh ... --json comments` yields a GraphQL *node*
        id (e.g. `IC_kwDO…`), which the REST `issues/comments/{id}` PATCH 404s on — it needs
        the numeric db id. So update via GraphQL (node id) unless the id is purely numeric."""
        if str(comment_id).isdigit():  # a REST numeric id (defensive; reads give node ids)
            self._run(["api", f"repos/{self.repo}/issues/comments/{comment_id}",
                       "-X", "PATCH", "-f", f"body={body}"])
            return
        self._run([
            "api", "graphql",
            "-f", "query=mutation($id:ID!,$body:String!){updateIssueComment("
                  "input:{id:$id,body:$body}){clientMutationId}}",
            "-f", f"id={comment_id}", "-f", f"body={body}",
        ])

    def _upsert_file(self, path: str, content: str, message: str, branch: str | None) -> None:
        """Create-or-update a repo file via the contents API (needs the current sha to update)."""
        api = f"repos/{self.repo}/contents/{path}"
        sha = None
        try:  # absent file => GET fails => create (no sha)
            sha = (self._run(["api", api, "--jq", ".sha"]) or "").strip() or None
        except Exception:
            sha = None
        b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
        args = ["api", api, "-X", "PUT", "-f", f"message={message}", "-f", f"content={b64}"]
        if sha:
            args += ["-f", f"sha={sha}"]
        if branch:
            args += ["-f", f"branch={branch}"]
        self._run(args)
