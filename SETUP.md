# Max Agency — Setup Requirements Checklist

**This file is the single source of truth for everything that must be installed,
configured, or present for Max Agency to run.** It is maintained *incrementally*: the
moment any phase surfaces a new prerequisite, it is appended here — so requirements live
in version control from the instant they're discovered, never in one machine's state or a
developer's memory.

Phase 3's one-command installer (`setup.ps1 -Repo owner/repo`) will **implement this
checklist** — it does not invent setup, it automates the already-validated items below.
Until then, this is the manual checklist a human follows to stand up Max Agency on a fresh
machine.

> **Maintenance rule (part of the per-phase build loop):** when a phase surfaces an
> install/config/repo/credential prerequisite, add it here in the same change — with which
> phase needs it, whether `setup.ps1` can automate it, and a one-line verification command.
> Nothing machine-specific (no hostnames, usernames, or absolute home paths) — use
> placeholders.

Legend: **[auto]** = `setup.ps1` can automate · **[manual]** = human/one-time (install,
login) · phase tag = earliest phase that needs it.

---

## 1. Host & runtimes  *(needed now — 2A+)*

- [ ] **Windows host** (the gate and orchestrator/coder harnesses are Windows-hosted). `[manual]`
- [ ] **`git`** on PATH. Verify: `git --version`. `[manual]`
- [ ] **Python 3.x** on PATH (runs the gate). Verify: `python --version`. `[manual]`
- [ ] **`gh` (GitHub CLI), authenticated.** Verify: `gh auth status`. `[manual]` (login),
      `[auto]` (can check)
- [ ] **Node.js** on PATH (required by the `codex` CLI; also used to launch codex's
      Windows `.cmd` shim). Verify: `node --version`. `[manual]`

## 2. Vendor CLIs & model access  *(per role)*

- [ ] **`codex` CLI** — orchestrator harness (triage). Install: `npm install -g @openai/codex`.
      Authenticate (ChatGPT account *or* OpenAI API key). Verify: `codex --version`;
      `codex exec -m gpt-5.4-mini "Reply OK"`. **2C.** `[manual]`
  - Model `gpt-5.4-mini` must be accepted by the account (account-specific: `gpt-5-mini`
    is rejected on ChatGPT-account logins). Overridable via `--triage-model` /
    `$GATE_TRIAGE_MODEL`.
- [ ] **WSL + `hermes`** — coder harness (OpenRouter `xiaomi/mimo-v2.5`). Invoked from
      Windows as `wsl.exe -e bash -lc "hermes ..."`. **2D.** `[manual]`
  - [ ] `OPENROUTER_API_KEY` set in `~/.hermes/.env` (WSL filesystem). **2D.** `[manual]`
  - [ ] Coder profile `model.default: xiaomi/mimo-v2.5` (repo-tracked in
        `hermes-config/profiles/coder/config.yaml`; live copy at
        `~/.hermes/profiles/coder/config.yaml`). **2D.**
  - ⚠ **Gotcha:** hermes does **not** auto-load `~/.hermes/.env`; any ad-hoc invocation
    must `set -a; source ~/.hermes/.env; set +a` first (production systemd units use
    `EnvironmentFile=`).
- [ ] **`claude` CLI** (Claude Opus) — architect + CTO harnesses. Verify: `claude --version`.
      **2E.** `[manual]`

## 3. Repo state — labels  *(needed now — the gate's writes fail without them)*

The gate's state machine (`gate/classifier.py`) requires this **exact** label set on the
target repo. A missing label makes the gate's atomic label-edit fail safely (logged, no
comment, retried) — but it must exist for the gate to make progress. `[auto]`

- [ ] **Scope label:** `AI-GATE-TEST` (migration, phases 2A–2E) → `AI` (production, from 2F).
      This is the human's opt-in + kill-switch and the gate's entire work universe. **2A.**
- [ ] **Role labels:** `role:architect` · `role:coder` · `role:cto`. **2A.**
- [ ] **State labels:** `backlog` · `ready` · `in-progress` · `plan-ready` · `kickoff` ·
      `needs-human`. **2A.**

Verify the full set exists:
```sh
gh label list --repo OWNER/REPO --json name --jq '[.labels[].name]'
```

> ⚠ **Reconcile the stale installer (Phase 3 task).** The existing
> `scripts/setup-project.ps1` is the **old** self-selection-era installer and does **not**
> match the gate: it omits the scope label, `plan-ready`, and `needs-human`, and creates
> stale labels (`assigned:claude-*`, `assigned:hermes-coder`, `phase:0..7`, `review`,
> `blocked`, `planned`) plus a Project-board step the gate doesn't use. It is left in place
> for now (old pollers may still rely on it; see the "build beside the old system" rule).
> Phase 3 `setup.ps1` replaces it and creates the set above.

## 4. Configuration & credentials  *(needed now — 2A+)*

- [ ] **Target repo** via `--repo OWNER/REPO` or `$PROJECT_REPO`. **2A.** `[manual]`/`[auto]`
- [ ] **Least-privilege GitHub token** (one repo; issues + contents + PR; no admin) for the
      gate's `gh` calls. **2F/production.** `[manual]`

## 5. Scheduler & cutover  *(production — 2F/3)*

- [ ] **Windows Task Scheduler** task running the gate on a cadence (the *only* scheduled
      job). **2F.** `[auto]`
- [ ] **Cut scope label** `AI-GATE-TEST` → `AI` once old pollers are retired. **2F.** `[auto]`
- [ ] **Disable the old pollers** (Hermes coder timer/self-poll; Claude Code 5-min routine).
      **2F.** `[manual]`/`[auto]`

## 6. Known environment gotchas (not blockers, but document so installs don't trip on them)

- **Git Bash vs PowerShell have different PATHs** on the same machine — "resolves in one
  shell, not the other" is a PATH/stale-shell issue, never a separate filesystem. Restart
  the shell after install.
- **`codex` on Windows is a `.cmd` npm shim** that `subprocess` can't launch directly; the
  gate/bench runners handle this by invoking `node ...\codex.js` (see `gate/harness.py`
  `_runnable_argv`). No human action needed — noted so it isn't re-debugged.
- **Codex model availability is account-specific** — verify `gpt-5.4-mini` works on the
  actual account (§2) rather than assuming.

---

*Surfaced-by log (newest first): §3 labels + stale-installer mismatch — Phase 2C
(2026-06-16). §2 codex/model — Phase 0/2C. §2 hermes `.env` gotcha — Phase 0.*
