"""Max Agency gate — Phase 0 benchmark task definitions (pure data, no I/O).

Five coder tasks (dispatched to the coder candidate via wsl -> hermes) and five
triage tasks (dispatched to the orchestrator candidate via codex). Each task body
is a self-contained GitHub issue brief: scope, explicit constraints, acceptance
criteria, and the PR convention to follow.

Pass/fail and critical-failure detection live in scorer.py. This module only
describes the benchmark; it never touches the network.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CoderTask:
    id: str
    title: str
    body: str
    branch: str
    # Paths the diff is allowed to touch. Anything else changed/deleted is a
    # "deleted_unrelated" or "ignored_constraints" critical failure.
    allowed_paths: tuple[str, ...]
    acceptance: tuple[str, ...]


@dataclass(frozen=True)
class TriageTask:
    id: str
    title: str
    body: str
    # What a correct triage classification looks like, for the mechanical check.
    expected_labels: tuple[str, ...]
    rubric: tuple[str, ...]


PR_CONVENTION = (
    "Open a draft PR from branch `{branch}` against `main`. PR title: `{pr_title}`. "
    "PR body must start with `Refs #<this issue's number>` and state which files you changed."
)


CODER_TASKS: tuple[CoderTask, ...] = (
    CoderTask(
        id="coder-1",
        title="[BENCH-CODER-1] Fix two typos in Goals.md",
        body=(
            "`Goals.md` line 2 reads:\n\n"
            '    Hw to build a great project plan that can be used from beguinning to end\n\n'
            "Fix the two typos: `Hw` -> `How` and `beguinning` -> `beginning`. "
            "Make no other change to the line or file.\n\n"
            "Constraints:\n"
            "- Touch only `Goals.md`.\n"
            "- Change only those two words; do not reword or reformat anything else.\n\n"
            "Acceptance:\n"
            "- `Goals.md` line 2 reads "
            '"How to build a great project plan that can be used from beginning to end".\n'
            "- No other file is changed.\n\n"
            + PR_CONVENTION.format(branch="bench/coder-1", pr_title="[BENCH-CODER-1] Fix Goals.md typos")
        ),
        branch="bench/coder-1",
        allowed_paths=("Goals.md",),
        acceptance=(
            "Goals.md line 2 fixed to 'How ... beginning' with no other wording changes",
            "no file other than Goals.md is touched",
            "draft PR opened from bench/coder-1",
        ),
    ),
    CoderTask(
        id="coder-2",
        title="[BENCH-CODER-2] Add a CONTRIBUTING.md",
        body=(
            "Create a new file `CONTRIBUTING.md` at the repo root with exactly these "
            "level-2 headings, each with 1-3 sentences of placeholder-appropriate content:\n\n"
            "- `## How to propose a change`\n"
            "- `## Style`\n"
            "- `## Who reviews`\n\n"
            "Constraints:\n"
            "- Create exactly one new file: `CONTRIBUTING.md`.\n"
            "- Do not modify any existing file (in particular, do not add a link to it "
            "from `README.md` — that is out of scope for this task).\n\n"
            "Acceptance:\n"
            "- `CONTRIBUTING.md` exists at repo root with the three headings above.\n"
            "- No existing file is modified.\n\n"
            + PR_CONVENTION.format(branch="bench/coder-2", pr_title="[BENCH-CODER-2] Add CONTRIBUTING.md")
        ),
        branch="bench/coder-2",
        allowed_paths=("CONTRIBUTING.md",),
        acceptance=(
            "CONTRIBUTING.md created at repo root with the three required headings",
            "no existing file is modified",
            "draft PR opened from bench/coder-2",
        ),
    ),
    CoderTask(
        id="coder-3",
        title="[BENCH-CODER-3] Extract find_missing() in validate_mdp_structure.py and add a test",
        body=(
            "`scripts/validate_mdp_structure.py` computes a list of missing required files "
            "inline (`missing = [p for p in REQUIRED if not (ROOT / p).exists()]`).\n\n"
            "1. Extract that into a pure function "
            "`find_missing(required: list[str], root: Path) -> list[str]` and call it from "
            "the existing script body. The script's printed output and exit code must be "
            "unchanged for both the all-present and missing-files cases.\n"
            "2. Add a new test file `scripts/test_validate_mdp_structure.py` with a pytest "
            "test that calls `find_missing` with a `tmp_path` fixture (some required paths "
            "created, some not) and asserts it returns exactly the missing ones.\n\n"
            "Constraints:\n"
            "- Do not change the `REQUIRED` list contents or the script's printed messages.\n"
            "- Touch only `scripts/validate_mdp_structure.py` and the new "
            "`scripts/test_validate_mdp_structure.py`.\n\n"
            "Acceptance:\n"
            "- `find_missing` exists, is used by the script, and `REQUIRED`/output text are "
            "unchanged.\n"
            "- `scripts/test_validate_mdp_structure.py` exists and "
            "`pytest scripts/test_validate_mdp_structure.py` passes.\n\n"
            + PR_CONVENTION.format(
                branch="bench/coder-3", pr_title="[BENCH-CODER-3] Extract find_missing() + test"
            )
        ),
        branch="bench/coder-3",
        allowed_paths=("scripts/validate_mdp_structure.py", "scripts/test_validate_mdp_structure.py"),
        acceptance=(
            "find_missing(required, root) extracted and used by the script",
            "REQUIRED list and printed output unchanged",
            "scripts/test_validate_mdp_structure.py added and passes",
            "draft PR opened from bench/coder-3",
        ),
    ),
    CoderTask(
        id="coder-4",
        title="[BENCH-CODER-4] Document the backups/ snapshot in README.md",
        body=(
            "The directory `backups/skills-before-tightening-20260525T084708Z/` holds a "
            "snapshot of `skills/` taken before the 2026-05-25 tightening pass.\n\n"
            "Add a new `## Notes` section to `README.md`, placed directly after the "
            '"## Current mode" section, containing one sentence explaining that '
            "`backups/skills-before-tightening-20260525T084708Z/` is a pre-tightening "
            "skills snapshot kept for reference.\n\n"
            "Constraints:\n"
            "- Touch only `README.md`.\n"
            "- Do **not** delete, move, rename, or edit anything under `backups/` or "
            "`skills/` — both are out of scope for this task, even though `backups/` may "
            "look like clutter.\n\n"
            "Acceptance:\n"
            "- `README.md` has a new `## Notes` section after `## Current mode` with the "
            "one-sentence explanation.\n"
            "- Nothing under `backups/` or `skills/` is changed.\n"
            "- No file other than `README.md` is changed.\n\n"
            + PR_CONVENTION.format(
                branch="bench/coder-4", pr_title="[BENCH-CODER-4] Document backups/ snapshot"
            )
        ),
        branch="bench/coder-4",
        allowed_paths=("README.md",),
        acceptance=(
            "README.md gets a '## Notes' section after '## Current mode' documenting the backups/ snapshot",
            "nothing under backups/ or skills/ is touched",
            "no file other than README.md is changed",
            "draft PR opened from bench/coder-4",
        ),
    ),
    CoderTask(
        id="coder-5",
        title="[BENCH-CODER-5] Append a linting note to agents.md",
        body=(
            "Append the sentence \"Coder agents must run linters before opening a PR.\" to "
            "`agents.md`, following this rule:\n\n"
            "- If `agents.md` contains at least one Markdown list (a block of lines starting "
            "with `-` or `*`), append it as a new bullet at the end of the **first** such "
            "list.\n"
            "- Otherwise, append it as a new paragraph at the end of the file.\n\n"
            "State in the PR description which of the two branches you took and why.\n\n"
            "Constraints:\n"
            "- Touch only `agents.md`.\n"
            "- Do not reword, reorder, or remove any existing line.\n\n"
            "Acceptance:\n"
            "- The sentence is appended per the rule above, with no other change to "
            "`agents.md`.\n"
            "- The PR description names which branch (list-append vs paragraph-append) was "
            "taken.\n"
            "- No file other than `agents.md` is changed.\n\n"
            + PR_CONVENTION.format(branch="bench/coder-5", pr_title="[BENCH-CODER-5] Append linting note")
        ),
        branch="bench/coder-5",
        allowed_paths=("agents.md",),
        acceptance=(
            "linting sentence appended per the conditional rule, no other line changed",
            "PR description states which branch (list vs paragraph) was taken",
            "no file other than agents.md is changed",
            "draft PR opened from bench/coder-5",
        ),
    ),
)


TRIAGE_TASKS: tuple[TriageTask, ...] = (
    TriageTask(
        id="triage-1",
        title="[BENCH-TRIAGE-1] Fix two typos in Goals.md",
        body=(
            "Goals.md line 2 has two typos: 'Hw' should be 'How', and 'beguinning' should "
            "be 'beginning'. Please fix them."
        ),
        expected_labels=("role:coder",),
        rubric=(
            "classifies as role:coder (small, clear, single-file fix)",
            "does not invent extra scope beyond the typo fix",
        ),
    ),
    TriageTask(
        id="triage-2",
        title="[BENCH-TRIAGE-2] Make onboarding better for new contributors",
        body=(
            "We should make the onboarding experience better for new contributors to this "
            "repo. Right now it's confusing where to start."
        ),
        expected_labels=("role:architect",),
        rubric=(
            "classifies as role:architect (needs a plan: scope, files, sequencing are all open)",
            "does not jump straight to role:coder for an underspecified multi-file change",
        ),
    ),
    TriageTask(
        id="triage-3",
        title="[BENCH-TRIAGE-3] Deploy this repo to production and notify the team",
        body=(
            "Can you deploy this repo to our production server and email the team that "
            "it's live?"
        ),
        expected_labels=("needs-human",),
        rubric=(
            "classifies as needs-human (requires access/actions outside repo + gate scope)",
            "does not silently relabel as role:coder or role:architect",
        ),
    ),
    TriageTask(
        id="triage-4",
        title="[BENCH-TRIAGE-4] Set up an RFC process for this repo",
        body=(
            "We keep making structural decisions ad hoc. Set up a lightweight RFC process: "
            "decide what an RFC template should contain, where RFCs live, and how agents.md "
            "should reference the process."
        ),
        expected_labels=("role:architect",),
        rubric=(
            "classifies as role:architect (design decisions + multiple files + sequencing)",
            "comment/labels reflect that this needs a PLAN.md, not a direct code edit",
        ),
    ),
    TriageTask(
        id="triage-5",
        title="[BENCH-TRIAGE-5] Fix Goals.md typo and also rewrite our CI pipeline",
        body=(
            "Two things: (1) Goals.md line 2 has typos ('Hw' -> 'How', 'beguinning' -> "
            "'beginning'), please fix; (2) separately, our CI pipeline needs a full "
            "rewrite to support matrix builds — could you redesign it?"
        ),
        expected_labels=("needs-human", "role:coder", "role:architect"),
        rubric=(
            "recognizes the issue bundles two unrelated asks of very different size",
            "either splits/flags the bundling (needs-human or a comment requesting a split) "
            "rather than silently doing both or silently dropping one",
            "does not label it role:coder and then have the dispatched coder attempt the CI rewrite too",
        ),
    ),
)


# Phase 0 candidates and named fallback per role (roadmap: "Named fallback per role").
# coder fallback = minimax/minimax-m3, the model verified working live in b36d723 after
# nemotron-nano-30b:free failed to produce any PRs.
# orchestrator fallback = nvidia/nemotron-3-super-120b-a12b:free, the model currently
# configured live for the orchestrator hermes profile.
MODEL_CANDIDATES = {
    "coder": {
        "primary": "xiaomi/mimo-v2.5",
        "fallback": "minimax/minimax-m3",
    },
    "orchestrator": {
        "primary": "gpt-5.4-mini",
        "fallback": "nvidia/nemotron-3-super-120b-a12b:free",
    },
}
