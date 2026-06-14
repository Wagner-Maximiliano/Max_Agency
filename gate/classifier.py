"""Max Agency gate — pure issue classifier (Phase 2A).

This module is deliberately I/O-free: it takes an already-gathered IssueContext and
returns a Decision. All GitHub access lives in gate.py. Keeping this pure is what makes
the dry-run gate testable by diffing printed runs (see tests/test_classifier.py).

It implements the state-machine table from the approved roadmap (v3) literally. Any state
not covered, or with conflicting labels, returns action "no-action" with state
"unknown-state" — the gate logs it and moves on (one corrupt issue never halts the board).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

ROLE_LABELS = ("role:architect", "role:coder", "role:cto")
STATE_LABELS = ("backlog", "ready", "in-progress", "plan-ready", "kickoff", "needs-human")


@dataclass
class IssueContext:
    """Everything the classifier needs about one issue, pre-gathered by the I/O layer.

    Fields the I/O layer cannot cheaply determine may be left at their defaults; the
    classifier degrades gracefully (treats unknowns as "not yet / waiting").
    """

    number: int
    labels: set[str] = field(default_factory=set)
    # latest human approval comment on a plan-ready issue: "approve" | "changes" | None
    approval: Optional[str] = None
    # latest dispatch marker is active (status started/pr-open AND not stale)
    marker_active: bool = False
    # a PR is linked to this issue and is open
    linked_pr_open: bool = False
    # a PR linked to this issue has merged
    pr_merged: bool = False
    # backlog dependency gate: True when all Depends-on issues are closed
    deps_closed: bool = False
    # role:cto issue whose PR has no verdict comment yet
    cto_verdict_present: bool = False


@dataclass
class Decision:
    number: int
    detected_state: str
    intended_action: str
    reason: str
    llm: Optional[str] = None  # which LLM would be woken, or None for deterministic/no-op


def _roles(labels: set[str]) -> list[str]:
    return [l for l in ROLE_LABELS if l in labels]


def _has_workflow_labels(labels: set[str]) -> bool:
    return any(l in labels for l in (*ROLE_LABELS, *STATE_LABELS))


def classify(ctx: IssueContext) -> Decision:
    """Map one IssueContext to a Decision per the approved state-machine table."""
    labels = ctx.labels

    def d(state: str, action: str, reason: str, llm: Optional[str] = None) -> Decision:
        return Decision(ctx.number, state, action, reason, llm)

    # 1. Terminal/highest-priority: a linked PR merged → close the issue.
    if ctx.pr_merged:
        return d("merged", "would-close", "linked PR merged")

    # 2. Explicitly parked for a human.
    if "needs-human" in labels:
        return d("needs-human", "no-action", "waiting for human")

    # 3. Conflicting role labels → unknown, do nothing (fail safe).
    roles = _roles(labels)
    if len(roles) > 1:
        return d("unknown-state", "no-action", "conflicting role labels")

    # 4. Scope label only, no workflow labels yet → triage.
    if not _has_workflow_labels(labels):
        return d("scope-only", "would-triage", "no workflow labels", llm="orchestrator")

    # 5. Architect brief awaiting a plan.
    if "role:architect" in labels and "plan-ready" not in labels:
        return d("role:architect", "would-invoke-architect", "no plan yet", llm="architect")

    # 6. Plan awaiting human approval.
    if "plan-ready" in labels:
        if ctx.approval == "approve":
            return d("plan-ready", "would-create-kickoff", "owner approved")
        if ctx.approval == "changes":
            return d("plan-ready", "would-reopen-architect", "owner requested changes")
        return d("plan-ready", "no-action", "awaiting approval comment")

    # 7. Kickoff issue → expand the PLAN into task issues.
    if "kickoff" in labels:
        return d("kickoff", "would-expand-kickoff", "kickoff present", llm="orchestrator")

    # 8–10. Coder lane.
    if "role:coder" in labels:
        if "backlog" in labels:
            if ctx.deps_closed:
                return d("backlog", "would-promote-ready", "all deps closed")
            return d("backlog", "no-action", "waiting on dependencies")
        if "ready" in labels:
            if ctx.marker_active:
                return d("ready", "no-action", "active marker present")
            return d("ready", "would-dispatch-coder", "no active marker", llm="coder")
        if "in-progress" in labels:
            if ctx.marker_active:
                return d("in-progress", "no-action", "active marker not stale")
            if ctx.linked_pr_open:
                return d("in-progress", "no-action", "PR open, awaiting review routing")
            return d("in-progress", "would-recover", "no active marker and no PR")

    # 11. CTO review awaiting a verdict.
    if "role:cto" in labels:
        if ctx.linked_pr_open and not ctx.cto_verdict_present:
            return d("role:cto", "would-invoke-cto", "PR ready, no verdict", llm="cto")
        return d("role:cto", "no-action", "verdict present or no PR yet")

    # 12. Anything else → unknown, fail safe.
    return d("unknown-state", "no-action", "no matching rule")
