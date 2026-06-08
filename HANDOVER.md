# Max Agency — Session Handover

**Written:** 2026-06-08  
**Handed to:** Next session  
**Project repo:** `Wagner-Maximiliano/Surviving_The_AI_World`  
**Agency repo (Windows):** `C:\Users\lobster\Github_Projects\Max_Agency`

---

## What happened in the previous sessions (brief summary)

Two prior sessions ran a live end-to-end test of the Max Agency autonomous pipeline. The full pipeline was confirmed working on one task (issue #10 — banned-phrases bug fix) but failed on a second task (issue #21 — GLOSSARY.md) due to two infrastructure bugs and two design gaps. All infrastructure bugs were fixed. The user decided to reset the stale issue/PR state and redesign the issue and PR body templates before restarting work.

---

## Current state — what is already done

### Infrastructure (DO NOT re-fix these — they are working)

| System | Fix applied | Status |
|--------|-------------|--------|
| `run-tick.ps1` line 62 | Added `--dangerously-skip-permissions` so Claude Code can perform git/file ops unattended | **COMMITTED to Max_Agency main** (commit `4d62611`) |
| WSL Hermes orchestrator service | Changed `--max-turns 10` → `--max-turns 20` so all 11 orchestrator steps run | **LIVE in WSL service file only** — NOT committed to repo |
| Windows Scheduled Task `MaxAgency-ClaudeCodeRoutine` | Confirmed present, fires every 5 min | Working |
| WSL `hermes-orchestrator-tick.timer` | Confirmed present, fires every 5 min | Working |
| OpenRouter/nemotron model | Configured in `~/.hermes/config.yaml` (global) only — profile configs have no `model:` key | Working |

**Important:** The `--max-turns 20` change is only in the live WSL service file at  
`~/.config/systemd/user/hermes-orchestrator-tick.service`. It was NOT committed to  
`Max_Agency/hermes-config/`. The next session should either:
- Document it in `Human_Runbook.md`, OR
- Commit the canonical value to the service template in the repo  

### Repo reset (Surviving_The_AI_World) — COMPLETE

The following were closed/deleted in this session:
- PRs #23, #26, #28 — all closed (stale rework attempts for issue #21)
- Issues #21 (task) and #29 (CTO review) — both closed
- Remote branches `phase-1/21-add-docs-glossary`, `phase-1/21-glossary`, `phase-1/21-add-glossary` — all deleted

**Current state of `Wagner-Maximiliano/Surviving_The_AI_World`:**
- Open issues: 0
- Open PRs: 0
- Branches: `main` only

The only completed/merged work on `main` is from Phase 0 (repo bootstrap — all Phase 0 tasks done). Phase 1 has not been restarted.

---

## Design gaps found — what broke and why

### Gap 1: Rework creates a new branch instead of amending the existing one

**What happened:** CTO issued `VERDICT: CHANGES REQUIRED` on issue #21 (GLOSSARY.md). The orchestrator correctly routed the verdict back to the task issue (removed assignee, re-labelled `in-progress`). However, the coder (`poll-and-pickup.md`) has no instruction to check for an existing branch. So on the next tick, haiku created a brand-new branch (`phase-1/21-glossary`, then `phase-1/21-add-glossary`) and opened a new PR, leaving the prior PR open. After three rework loops, three open stale PRs accumulated.

**Fix needed (in `poll-and-pickup.md`):** Coder step 9 must be updated with these rules:
1. Before creating a branch, check `gh api repos/$env:PROJECT_REPO/branches` for any existing `phase-<n>/<N>-*` branch.
2. If one exists, check it out and commit amendments to it — do NOT create a new branch.
3. Before opening a PR, check if an open PR already exists for that branch: `gh pr list --repo $PROJECT_REPO --head <branch-name> --state open`. If one exists, push to it rather than opening a new one. Only close a stale PR if there is already a different open PR for the same issue.
4. Read ALL comments on the issue before starting work — especially any `VERDICT: CHANGES REQUIRED` blocks posted by the CTO. Every numbered item in the CHANGES REQUIRED list must be addressed before pushing.

### Gap 2: Issues and PRs have too little information for a low-reasoning model

**What happened:** The GLOSSARY.md task issue body contained only the brief description from PLAN.md and a `Depends-on:` line. When the CTO issued CHANGES REQUIRED (e.g., "8 of 10 entries contain 3 sentences — all must be exactly 2"), haiku fixed only the two explicitly named entries, not the other 8. Because the original issue had no exhaustive step-by-step spec, haiku had to infer the pattern — and inferred wrong.

**Fix needed:** See the template design section below.

### Gap 3: `--max-turns 10` was too low for the orchestrator

**What happened:** The orchestrator consumed all 10 turns on steps 1–7 and logged `"Steps 7.5–9 not executed this tick; will resume next tick."` Steps 7.5–9 are what creates CTO review issues and handles verdicts. With 10 turns, the orchestrator could never close the loop.

**Fix already applied:** Changed to `--max-turns 20` in the live WSL service. Confirmed working — orchestrator now completes all 11 steps in a single tick.

### Gap 4: `--dangerously-skip-permissions` was missing from `run-tick.ps1`

**What happened:** Every Claude Code coder tick was posting a "Permission blocker: Unable to create branch or edit files in project repo" comment and exiting with no work done.

**Fix already applied:** Added `--dangerously-skip-permissions` to `run-tick.ps1` line 62. Committed to Max_Agency main.

---

## User's requirements for the new issue/PR template

The user stated (verbatim, cleaned up for readability):

> "I want to have more information. The PRs and Issues must have the exact steps that need to be followed by the model so that we can actually trust that a low-end model will be able to carry out the work without the need for a high reasoning model. This will also reduce errors. It is also important to explain in simple terms too — the Human needs to be able to understand, so maybe a small section at the beginning of the body with a summary in a language as if it is speaking to an 18-year-old, that the human can quickly read and understand exactly what that task is about, why and how it is done."

### Derived template structure (4 sections, required in every issue body)

```
## What is this task? (For the human reading this)
<!-- Plain English, no jargon, as if explaining to an 18-year-old. 3–5 sentences max.
     Answer: what are we building/changing? why does it matter? what will it look like when done? -->

## Acceptance Criteria
<!-- Exact, exhaustive checklist. Every item must be independently verifiable.
     No item can be inferred — if it matters, spell it out. -->
- [ ] <specific, measurable criterion>
- [ ] <specific, measurable criterion>
...

## Step-by-Step Instructions for the Agent
<!-- Exact shell commands, file paths, content requirements.
     Written so a low-reasoning model (claude-haiku) can follow mechanically without inference.
     Include: what file to create/edit, exactly what content it must contain, exact format rules,
     exact commands to run, exact success checks. -->

### Step 1 — <name>
```sh
<exact command>
```
Expected output: <what to check>

### Step 2 — ...

## Definition of Done
<!-- Specific, verifiable endpoint.
     Example: "File `docs/GLOSSARY.md` exists with exactly 10 entries.
     Each entry is formatted as `## Term\n<exactly 2 sentences>`.
     `wc -l docs/GLOSSARY.md` returns between 30 and 50 lines." -->
```

---

## What the next session must implement

### Task A — Update `poll-and-pickup.md` (rework loop fix)

File: `C:\Users\lobster\Github_Projects\Max_Agency\claude-code-routine\poll-and-pickup.md`

Replace the current Coder section of step 9 with this expanded version:

```
- **Coder**:
  1. **Check for an existing branch.** Run:
     `gh api repos/$env:PROJECT_REPO/branches --jq '.[].name'`
     Look for any branch matching `phase-<n>/<N>-*` where N is the issue number.
     - If one exists: `git fetch origin && git checkout <existing-branch>`. Do NOT create a new branch.
     - If none exists: create `phase-<n>/<N>-<slug>` from main.
  2. **Read ALL issue comments** before writing any code:
     `gh issue view <N> --repo $env:PROJECT_REPO --comments`
     If any comment contains `VERDICT: CHANGES REQUIRED`, extract every numbered item from the
     list and address ALL of them — not just the examples explicitly called out.
     Apply the fix pattern globally to all affected content, not just the named instances.
  3. **Make the changes.** Edit files, commit incrementally with message `phase-<n>/<N>: <subject>`.
  4. **Push.** `git push origin <branch-name>`.
  5. **Open or update a PR.** Check if an open PR exists for this branch:
     `gh pr list --repo $env:PROJECT_REPO --head <branch-name> --state open --json number`
     - If a PR exists: push has already updated it — do nothing else.
     - If no PR exists: `gh pr create --title "phase-<n>/<N>: <slug>" --body "Closes #<N>" --repo $env:PROJECT_REPO`
  6. **Label the task issue `review`** and remove `in-progress`:
     `gh issue edit <N> --repo $env:PROJECT_REPO --add-label review --remove-label in-progress`
```

Also add this to the Hard Rules section:
```
- **Never create a second branch for the same issue.** If `phase-<n>/<N>-*` exists on origin, use it.
- **Never open a second PR for the same branch.** Check first.
- **Always read all issue comments before writing code.** CHANGES REQUIRED items must ALL be addressed — not just the named examples. Apply fixes globally across all affected content.
```

### Task B — Update `orchestrator-tick.md` step 4b (issue creation body template)

File: `C:\Users\lobster\Github_Projects\Max_Agency\hermes-config\poll-prompts\orchestrator-tick.md`

Replace the `--body` block in step 4b with the new 4-section template. The orchestrator must populate each section from the PLAN.md task data. Here is the updated `--body` content:

```
      --body "$(cat <<EOF
## What is this task? (For the human reading this)
<Write 3–5 plain English sentences explaining: what is being built or changed, why it matters to the book project, and what the result will look like. Use everyday language — no jargon. Imagine explaining to a curious 18-year-old who has never seen the codebase.>

## Acceptance Criteria
<List every acceptance criterion from PLAN.md for this task. Then add any criteria that are implied by the task description but not explicitly listed. Every criterion must be independently verifiable without reading the code.>
- [ ] <criterion>
- [ ] <criterion>

## Step-by-Step Instructions for the Agent
<Provide exact, mechanical instructions. Include:
- The exact file path(s) to create or edit
- The exact content format required (e.g., "Each entry must be formatted as: ## Term\n<exactly 2 sentences>")
- The exact shell commands to run to create files, verify output, run tests
- Any format constraints stated in the PLAN.md or phase bible documents
- How to verify each step succeeded before moving to the next>

### Step 1 — Read context
\`\`\`sh
gh issue view <N> --repo $PROJECT_REPO --comments
cat ~/.hermes-cache/$PROJECT_REPO/PLAN.md
# Also read the relevant bible document if one exists for this task:
# cat ~/.hermes-cache/$PROJECT_REPO/bible/<relevant-doc>.md
\`\`\`

### Step 2 — Create / edit the file
File to create/edit: \`<exact path>\`
Required content format:
<describe exactly what the content must look like — no inference required>

### Step 3 — Verify
\`\`\`sh
<exact verification command — e.g., wc -l, grep, cat>
\`\`\`
Expected output: <what a passing result looks like>

### Step 4 — Commit and push
\`\`\`sh
cd ~/.hermes-cache/$PROJECT_REPO
git add <file-path>
git commit -m "phase-<n>/<N>: <short description>"
git push origin <branch-name>
\`\`\`

## Definition of Done
File \`<exact path>\` exists on the branch with the following measurable properties:
- <specific measurable property — e.g., "exactly 10 entries", "each entry is 2 sentences">
- <specific measurable property>
CI passes (if applicable). PR is open with \`Closes #<N>\` in the body.

Depends-on: #<comma-separated issue numbers, or 'none'>
EOF
      )"
```

**Important note for the orchestrator:** When populating the Step-by-Step Instructions section for a given task, the orchestrator must read the PLAN.md task description AND any relevant constraints (model roster, phase acceptance criteria, bible documents referenced). For Phase 1 tasks specifically, the bible documents in `bible/` don't exist yet — so the instructions must derive requirements purely from PLAN.md.

### Task C — Re-create issue #21 (GLOSSARY.md) with the new template

After Tasks A and B are committed, re-create the issue manually using the new template:

**Title:** `phase-1/1.7: add docs/GLOSSARY.md — 10 key AI/tech terms`

**Labels:** `phase:1`, `assigned:claude-haiku`, `role:coder`, `in-progress`

**Body — fill in per template:**

```markdown
## What is this task? (For the human reading this)

We are building a Glossary file — a short dictionary of 10 key words that appear in our AI survival book. Think of it like a mini-dictionary at the back of a textbook. Each word gets its own entry with a brief explanation. This glossary lives in a file called `docs/GLOSSARY.md` in the book's project folder. The goal is to help readers quickly look up any confusing AI or tech word without having to Google it. When this task is done, there will be a file with exactly 10 definitions, each written in exactly 2 clear sentences.

## Acceptance Criteria

- [ ] File `docs/GLOSSARY.md` exists on the branch
- [ ] The file contains exactly 10 entries
- [ ] Each entry uses this exact format: a level-2 heading (`## Term`) followed by exactly 2 sentences of explanation on the next line (no blank line between heading and sentences)
- [ ] Every term relates to AI or technology relevant to the book's subject matter (surviving AI disruption)
- [ ] Each explanation uses plain English accessible to a non-technical reader — no unexplained jargon inside the definition itself
- [ ] The file starts with a top-level heading: `# Glossary`
- [ ] No entry has fewer than 2 sentences and no entry has more than 2 sentences
- [ ] Entries are sorted alphabetically by term name
- [ ] The file ends with a newline character (no trailing blank lines)
- [ ] PR is open with `Closes #<N>` in the body

## Step-by-Step Instructions for the Agent

### Step 1 — Read the issue and check for an existing branch
```sh
gh issue view <N> --repo $env:PROJECT_REPO --comments
gh api repos/$env:PROJECT_REPO/branches --jq '.[].name' | grep "phase-1/<N>"
```
If a branch exists already, check it out. If not, create `phase-1/<N>-glossary` from main.

### Step 2 — Navigate to the project repo and set up the branch
```sh
cd $env:USERPROFILE\.hermes-cache\Wagner-Maximiliano\Surviving_The_AI_World
git fetch --all --prune
git checkout main && git pull --rebase
# Only if no existing branch:
git checkout -b phase-1/<N>-glossary
```

### Step 3 — Create the file with exactly this structure

Create file `docs/GLOSSARY.md`. The file MUST follow this exact pattern — apply it to ALL 10 entries without exception:

```
# Glossary

## Artificial Intelligence
Two sentences here. Second sentence here.

## Automation
Two sentences here. Second sentence here.

## [Term 3]
...
```

Rules that apply to EVERY entry (not just some):
- Each entry is a `## ` heading (two hash symbols, one space, then the term)
- After the heading comes exactly one blank line, then exactly 2 sentences on consecutive lines (or the same line — both are acceptable as long as there are exactly 2 sentences total)
- Exactly 2 sentences means: count the periods (or `?` or `!`) that end sentences. There must be exactly 2 per entry. If you write 3, delete one. If you write 1, add another.
- Alphabetical order: entries must be sorted A→Z by the first letter of the term
- Plain English: define the term as if the reader has never heard of AI

Suggested terms (you may adjust, but must end up with exactly 10):
Algorithm, Artificial Intelligence, Automation, Bias (AI), Data, Large Language Model, Machine Learning, Neural Network, Parameter, Training Data

### Step 4 — Verify the file

```sh
# Count entries (should output 10):
grep -c "^## " docs/GLOSSARY.md

# Check no entry has 3+ sentences (look for entries with 3 periods in a row of text):
grep -A2 "^## " docs/GLOSSARY.md

# View the full file to manually check format:
cat docs/GLOSSARY.md
```

Expected: `grep -c "^## " docs/GLOSSARY.md` outputs `10`. Each entry block has exactly 2 sentences when you count the `.` characters.

### Step 5 — Commit and push

```sh
git add docs/GLOSSARY.md
git commit -m "phase-1/<N>: add docs/GLOSSARY.md with 10 key AI/tech terms"
git push origin phase-1/<N>-glossary
```

### Step 6 — Open PR

```sh
gh pr create \
  --repo Wagner-Maximiliano/Surviving_The_AI_World \
  --title "phase-1/<N>: add docs/GLOSSARY.md with 10 key AI/tech terms" \
  --body "Closes #<N>" \
  --head phase-1/<N>-glossary \
  --base main
```

### Step 7 — Label the issue as review

```sh
gh issue edit <N> --repo Wagner-Maximiliano/Surviving_The_AI_World \
  --add-label review --remove-label in-progress
```

## Definition of Done

File `docs/GLOSSARY.md` exists on branch `phase-1/<N>-glossary` with:
- Exactly 10 entries (`grep -c "^## " docs/GLOSSARY.md` → `10`)
- Every entry has exactly 2 sentences (count `.` per entry)
- Alphabetical order (A before B before C…)
- Starts with `# Glossary` heading
- PR open with `Closes #<N>` in body
- Task issue labelled `review`

Depends-on: none
```

**Replace `<N>` with the actual issue number created by `gh issue create`.**

### Task D — Document `--max-turns 20` in `Human_Runbook.md`

File: Look for `C:\Users\lobster\Github_Projects\Max_Agency\Human_Runbook.md` or similar.

Add a note in the WSL setup section:

```markdown
### Orchestrator turn budget

The orchestrator service file must use `--max-turns 20` (not 10). With 10 turns,
steps 7.5–9 (CTO issue creation, verdict routing, auto-merge) are skipped.

If you re-install Hermes on WSL, run:
```sh
sed -i 's/--max-turns 10/--max-turns 20/' \
  ~/.config/systemd/user/hermes-orchestrator-tick.service
systemctl --user daemon-reload
```
```

---

## Commit order for next session

1. Fix `poll-and-pickup.md` (Task A) → commit to Max_Agency main
2. Fix `orchestrator-tick.md` step 4b (Task B) → commit to Max_Agency main
3. Update `Human_Runbook.md` with `--max-turns 20` note (Task D) → commit to Max_Agency main
4. Push all commits to origin
5. Create issue #21 replacement with the new template (Task C) — do this manually via `gh issue create` so you can control the exact body
6. Verify the orchestrator picks it up on the next tick and dispatches it
7. Watch the coder tick: confirm it reads comments, uses the existing branch if present, and creates a properly formatted GLOSSARY.md

---

## Reference: key file paths

| What | Path |
|------|------|
| Claude Code routine launch script | `C:\Users\lobster\Github_Projects\Max_Agency\claude-code-routine\run-tick.ps1` |
| Claude Code coder/CTO prompt | `C:\Users\lobster\Github_Projects\Max_Agency\claude-code-routine\poll-and-pickup.md` |
| Orchestrator tick prompt | `C:\Users\lobster\Github_Projects\Max_Agency\hermes-config\poll-prompts\orchestrator-tick.md` |
| Orchestrator systemd service (WSL) | `~/.config/systemd/user/hermes-orchestrator-tick.service` |
| Hermes global model config (WSL) | `~/.hermes/config.yaml` |
| Project repo local clone (Windows) | `C:\Users\lobster\.hermes-cache\Wagner-Maximiliano\Surviving_The_AI_World` |
| Project repo on GitHub | `https://github.com/Wagner-Maximiliano/Surviving_The_AI_World` |
| Agency repo on Windows | `C:\Users\lobster\Github_Projects\Max_Agency` |

---

## What NOT to touch

- Do NOT re-apply the `--dangerously-skip-permissions` fix — it is already committed.
- Do NOT re-create any of the closed issues/PRs (#21, #23, #26, #28, #29) — use `gh issue create` for a fresh issue.
- Do NOT change the orchestrator model config — it inherits from `~/.hermes/config.yaml` and is working.
- Do NOT modify the Windows Scheduled Task — it is working.

---

*End of handover.*
