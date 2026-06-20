"""Sanity checks on the Phase 0 benchmark task definitions (pure data)."""

from tasks import CODER_TASKS, MODEL_CANDIDATES, TRIAGE_TASKS
from scorer import CRITICAL_FAILURES


def test_five_coder_and_triage_tasks():
    assert len(CODER_TASKS) == 5
    assert len(TRIAGE_TASKS) == 5


def test_coder_task_ids_and_branches_unique():
    ids = [t.id for t in CODER_TASKS]
    branches = [t.branch for t in CODER_TASKS]
    assert len(set(ids)) == len(ids)
    assert len(set(branches)) == len(branches)


def test_coder_tasks_have_acceptance_and_allowed_paths():
    for t in CODER_TASKS:
        assert t.acceptance, t.id
        assert t.allowed_paths, t.id
        # The brief must spell out the PR convention.
        assert t.branch in t.body
        assert "Refs #" in t.body


def test_triage_task_ids_unique_and_have_rubric():
    ids = [t.id for t in TRIAGE_TASKS]
    assert len(set(ids)) == len(ids)
    for t in TRIAGE_TASKS:
        assert t.rubric, t.id
        assert t.expected_labels, t.id


def test_model_candidates_cover_both_roles():
    assert set(MODEL_CANDIDATES) == {"coder", "orchestrator"}
    for role, cfg in MODEL_CANDIDATES.items():
        assert cfg["primary"], role
        assert cfg["fallback"], role
        assert cfg["primary"] != cfg["fallback"], role


def test_critical_failures_vocabulary_is_used_consistently():
    # Just confirms scorer's vocabulary is non-empty and importable from here too.
    assert "no_pr" in CRITICAL_FAILURES
    assert "secrets" in CRITICAL_FAILURES
