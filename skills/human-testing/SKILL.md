---
name: human-testing
when_to_use: A completed phase includes a GUI or any human-perceivable behaviour and needs a human PASS/FAIL before merging the phase.
applies_to: [orchestrator]
description: Generate a plain-language 5-section test guide, spin up an isolated test environment with seeded data, deliver to the human, collect PASS/FAIL feedback.
version: 1.0.0
license: MIT
metadata:
  hermes:
    tags: [max-agency, testing, human, gui, qa]
    optional: true
---

# Human Testing — Per-Phase GUI Validation

Machines can run unit tests. They cannot judge a GUI the way a user does. Any phase with a graphical surface or human-perceivable behaviour gets a human PASS before merge. Backend-only phases skip this skill.

**This skill is optional.** If the project has no GUI, do not load it. If it does, gate phase merge on a human PASS.

## When to Use

- A phase is code-complete, CI is green, CTO has `APPROVED` all PRs in the phase.
- The phase delivered any of: web UI, mobile UI, desktop UI, visual output, user-facing workflow.
- You need a human PASS before marking the phase Done.

Skip when the phase is purely backend (API, schema, data pipelines, etc.) — automated verification is sufficient.

## Procedure

### 1. Decide if testing is needed

Yes:
- Any visible UI element or layout change.
- Subjective polish (fonts, spacing, colour, copy clarity).
- Workflow involving clicks, navigation, or perceived performance.

No:
- API endpoints (covered by integration tests).
- Data correctness (covered by unit tests).
- Performance benchmarks (covered by load tests).

### 2. Generate the test guide

Plain-language Markdown, **exactly 5 sections**. Auto-assemble from the phase's tasks and acceptance criteria. Write it for someone with zero dev skills — no jargon, numbered steps, screenshots where helpful.

```
# Phase <n> test guide

## 1. What was done
Two to three sentences in plain language.

## 2. How to run it
Literal commands or clicks. Example:
1. Open a terminal.
2. cd <repo-path>
3. Run: ./run-test-env.sh
4. Wait for "App ready at http://localhost:3000".
5. Open that URL in your browser.

## 3. What to check
Numbered checklist, one clear action per item.
1. Click "Sign Up" at top-right.
2. Fill in email and password.
3. Click "Create Account".
4. Look for a welcome message with your email.

## 4. What you should see
For each item in section 3, the expected result. Screenshots if helpful.

## 5. If it doesn't match
How to report the mismatch and what to include (screenshot, the step that failed).
```

### 3. Spin up an isolated test environment

Self-contained, reproducible, never touches production data.

1. Use an isolated dependency install (e.g. `python -m venv .venv-test` or `npm ci`).
2. Provide a single launcher script in repo root, e.g. `run-test-env.sh` (or `.ps1` on Windows). It must:
   - Activate the isolated environment.
   - Seed sample data via a `seed_test_data.*` script.
   - Start the app.
3. **Test the test environment yourself first.** Boot it, verify the seeded data renders, before delivering to the human.

### 4. Deliver to the human

Default delivery channel: whichever is configured in `Human_Runbook.md` (Telegram, email, direct message — project-dependent). If no channel is configured, post the guide as a comment on the phase tracking issue and ask the human via `Human_Runbook.md`'s usual prompt path.

Message shape:

```
Phase <n> is ready to test.

What was done:
<two sentences>

To test:
1. cd <repo-path>
2. ./run-test-env.sh
3. Wait for "App ready at …" and follow the guide:
<link or pasted guide>

Reply with:
PASS — everything worked
FAIL — <one line on what didn't match>
```

Set a patience window of 8–24 hours (configurable per phase). Other phases continue in parallel; do not stall the whole build waiting.

### 5. Collect feedback

**On PASS:**
1. Merge the phase to `main` (Orchestrator requests human merge per `agents/orchestrator.md`).
2. Log in `State.md` recent escalations or a `Human tests` table:
   ```
   - Phase <n>: PASS at <timestamp>
   ```
3. Move the phase tracker issue to Done.

**On FAIL:**
1. Open a new issue with the human's note and screenshot. Label `phase:<n>`, `bug`, `assigned:<coder>`.
2. Coder fixes, opens PR, CI green, CTO approves.
3. Regenerate the test guide (only the changed parts need re-testing if scope is narrow) and re-deliver: "Phase <n> test — round 2."
4. Loop until PASS.

### 6. Archive

After PASS:
1. Commit the seed data, the launcher script, and the test guide to the repo so future regressions can replay it.
2. Clean up scratch state (temporary databases, snapshots).

## Pitfalls

- **Jargon.** "Instantiate the component" → wrong. "Click the sign-up button" → right. Re-read out loud as a non-dev would.
- **Empty database.** An unseeded UI is useless for testing. Always seed realistic sample data.
- **Untested launcher.** Always boot the test environment yourself before delivering. Missing-dependency failures on the human's machine waste their time.
- **Over-testing.** Don't ask the human to verify every pixel. Focus on the user's actual workflow.
- **Missing screenshots for visual things.** Layout, colour, spacing — show them.
- **Stalling on slow feedback.** If the human is busy past the patience window, mark the phase as awaiting human, move on with other parallel work.
- **Not logging the result.** PASS / FAIL goes into `State.md` with timestamp so the audit trail is complete.

## Verification

- Test guide is plain-language, 5 sections, no jargon.
- Test environment boots cleanly on a fresh checkout — you have verified this yourself.
- Seeded data is visible on first load.
- Human has received the guide via the configured channel.
- Human's PASS or FAIL is recorded in `State.md`.
- On PASS: phase merged to `main`, tracker issue closed.
- On FAIL: a new issue captures the human's note, assigned, and in progress.
