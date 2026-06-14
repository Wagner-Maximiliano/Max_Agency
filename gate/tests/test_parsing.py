"""Unit tests for the gate's pure parsing helpers (no GitHub access)."""

from datetime import timezone

import gate


def test_parse_marker_extracts_fields():
    body = (
        "<!-- max-agency-dispatch\n"
        "run_id: 2026-06-14T12:00:00Z-ab12\n"
        "issue: 42\n"
        "role: coder\n"
        "model: xiaomi/mimo-v2.5\n"
        "attempt: 2\n"
        "status: started\n"
        "ts: 2026-06-14T12:00:03Z\n"
        "-->"
    )
    m = gate.parse_marker(body)
    assert m["status"] == "started"
    assert m["issue"] == "42"
    assert m["model"] == "xiaomi/mimo-v2.5"


def test_parse_marker_none_when_absent():
    assert gate.parse_marker("just a normal comment") is None


def test_latest_marker_picks_newest():
    comments = [
        {"body": "<!-- max-agency-dispatch\nstatus: failed\nts: 2026-06-14T10:00:00Z\n-->"},
        {"body": "<!-- max-agency-dispatch\nstatus: started\nts: 2026-06-14T12:00:00Z\n-->"},
    ]
    assert gate.latest_marker(comments)["status"] == "started"


def test_marker_active_true_when_started_and_fresh(monkeypatch):
    from datetime import datetime
    monkeypatch.setattr(gate, "now", lambda: datetime(2026, 6, 14, 12, 30, tzinfo=timezone.utc))
    marker = {"status": "started", "ts": "2026-06-14T12:00:00Z"}
    assert gate.marker_is_active(marker, stuck_min=60) is True


def test_marker_active_false_when_stale(monkeypatch):
    from datetime import datetime
    monkeypatch.setattr(gate, "now", lambda: datetime(2026, 6, 14, 14, 0, tzinfo=timezone.utc))
    marker = {"status": "started", "ts": "2026-06-14T12:00:00Z"}
    assert gate.marker_is_active(marker, stuck_min=60) is False


def test_marker_active_false_when_failed():
    assert gate.marker_is_active({"status": "failed", "ts": "2026-06-14T12:00:00Z"}, 60) is False


def test_approval_only_from_maintainer():
    comments = [{"body": "APPROVE", "authorAssociation": "NONE"}]
    assert gate.parse_approval(comments) is None
    comments = [{"body": "APPROVE", "authorAssociation": "OWNER"}]
    assert gate.parse_approval(comments) == "approve"


def test_approval_latest_wins():
    comments = [
        {"body": "APPROVE", "authorAssociation": "OWNER"},
        {"body": "CHANGES: rework auth", "authorAssociation": "OWNER"},
    ]
    assert gate.parse_approval(comments) == "changes"


def test_approval_ignores_quoted_and_markers():
    comments = [
        {"body": "> APPROVE (quoting someone)", "authorAssociation": "OWNER"},
        {"body": "<!-- max-agency-dispatch\nstatus: started\n-->", "authorAssociation": "OWNER"},
    ]
    assert gate.parse_approval(comments) is None


def test_approval_ambiguous_treated_as_changes():
    comments = [{"body": "APPROVE but change the title", "authorAssociation": "OWNER"}]
    assert gate.parse_approval(comments) == "changes"


def test_depends_on_parsing():
    assert gate.parse_depends_on("Depends-on: #1, #2, 3") == [1, 2, 3]
    assert gate.parse_depends_on("Depends-on: none") == []
    assert gate.parse_depends_on("no dependency line") == []


def test_pr_map_by_branch_prefix():
    prs = [{"number": 88, "state": "OPEN", "body": "", "headRefName": "max-agency/issue-42/attempt-1"}]
    assert gate.build_pr_map(prs)[42] == {"state": "OPEN", "number": 88}


def test_pr_map_by_closes_fallback():
    prs = [{"number": 90, "state": "MERGED", "body": "Closes #17", "headRefName": "feature/x"}]
    assert gate.build_pr_map(prs)[17]["state"] == "MERGED"
