# Max Agency — Setup Requirements Checklist

**This file is the single source of truth for everything that must be installed,
configured, or present for Max Agency to run.** It is maintained *incrementally*: the
moment any phase surfaces a new prerequisite, it is appended here — so requirements live
in version control from the instant they're discovered, never in one machine's state or a
developer's memory.

**Onboard a repo in one command (v1.1):**
```powershell
pwsh scripts/setup.ps1 -Repo owner/repo            # labels + verify CLIs + register the gate task
pwsh scripts/setup.ps1 -Repo owner/repo -NoAutoMerge   # first run on a LIVE repo (CTO approves, human merges)
pwsh scripts/setup.ps1 -Repo owner/repo -NoTask        # labels only, don't touch the scheduler
```
`setup.ps1` **implements this checklist** for a target repo: it verifies the vendor CLIs,
creates the full label set (§3, idempotent), and registers the gate as a single **hidden**
Windows Scheduled Task (`MaxAgencyGate`, runs via `pythonw.exe` so no console window appears;
the gate's child `gh`/`codex`/`wsl`/`claude` calls use `CREATE_NO_WINDOW`). It does not invent
setup — it automates the already-validated items below. (v1.1 covers labels + CLI check +
scheduler; it does not yet write `PROJECT_REPO`/least-priv token or reconcile the stale
`scripts/setup-project.ps1` — those remain Phase 3.)

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

> ### ⭐ Choosing & testing models (start here)
>
> **Per project (the normal way): edit `Max_AgencyConfig.md` in that project's repo root.** This
> file is the single, isolated place to set each role's model for one project — Max Agency
> itself is never touched. `setup.ps1` creates it (pre-filled with defaults + a copy-paste
> list of options); the gate reads it from the repo on every run, so editing + committing it
> takes effect on the next tick. One line per role: `GATE_CODER_MODEL`, `GATE_TRIAGE_MODEL`,
> `GATE_ARCHITECT_MODEL`, `GATE_CTO_MODEL`.
>
> **The coder is the one you'll most likely change** (e.g. a writing model for a book repo): it
> runs through OpenRouter, so its value is an OpenRouter id `provider/model` — `xiaomi/mimo-v2.5`
> for code, `anthropic/claude-sonnet-4.6`/`openai/gpt-5.4` for prose (browse
> <https://openrouter.ai/models>). **Set it at onboarding** with:
> ```powershell
> pwsh scripts/setup.ps1 -Repo owner/book-repo -CoderModel "anthropic/claude-sonnet-4.6" -NoAutoMerge
> ```
> (writes `GATE_CODER_MODEL` into the repo's `Max_AgencyConfig.md`), or just edit the file in the
> repo afterward.
>
> **Each role's id FORMAT differs** because auth is per-role (see the table below): coder =
> OpenRouter `provider/model`; triage = a codex model (`gpt-5.4-mini`); architect/CTO = a
> claude alias (`opus`/`sonnet`). The `Max_AgencyConfig.md` template lists copy-paste options
> under each field.
>
> **`gate/models.env`** in *this* repo is only the GLOBAL fallback (applies to a repo with no
> `Max_AgencyConfig.md`). Precedence: project `Max_AgencyConfig.md` → `$GATE_*_MODEL` env →
> `gate/models.env` → built-in fallback. **Only `GATE_*` keys are honored** from a project's
> config (it can never set keys/PATH — a security boundary, since it lives in the project repo).
>
> **Where the API keys live** (NOT in `models.env` — keys stay with each provider):
> | Role | Provider / CLI | Key location | Sign in / verify |
> |---|---|---|---|
> | coder | OpenRouter (via hermes/WSL) | `OPENROUTER_API_KEY` in `~/.hermes/.env` (WSL) | `wsl -e bash -lc "grep -c OPENROUTER_API_KEY ~/.hermes/.env"` |
> | triage / expansion | OpenAI (`codex` CLI) | `codex` login (ChatGPT acct or API key) | `codex` then `/login` |
> | architect / CTO | Anthropic (`claude` CLI) | `claude` login (or `ANTHROPIC_API_KEY`) | `claude` then `/login` |
>
> **Test a model in ~30s** (runs the configured model through the real CLI path and prints
> PASS/FAIL — catches a bad id, a missing CLI, or expired auth):
> ```sh
> python gate/check_model.py coder        # also: triage | architect | cto
> python gate/check_model.py coder --model anthropic/claude-sonnet-4.6   # try one before committing
> ```

- [ ] **`codex` CLI** — orchestrator harness (triage). Install: `npm install -g @openai/codex`.
      Authenticate (ChatGPT account *or* OpenAI API key). Verify: `codex --version`;
      `codex exec -m gpt-5.4-mini "Reply OK"`. **2C.** `[manual]`
  - Model `gpt-5.4-mini` must be accepted by the account (account-specific: `gpt-5-mini`
    is rejected on ChatGPT-account logins). Overridable via `--triage-model` /
    `$GATE_TRIAGE_MODEL`.
- [ ] **WSL + `hermes`** — coder harness (OpenRouter `xiaomi/mimo-v2.5`). Invoked from
      Windows as `wsl.exe -e bash -lc "hermes ..."`. Verify: `wsl -e bash -lc "which hermes"`.
      **2D.** `[manual]`
  - [ ] `OPENROUTER_API_KEY` set in `~/.hermes/.env` (WSL filesystem). Verify:
        `wsl -e bash -lc "grep -c OPENROUTER_API_KEY ~/.hermes/.env"`. **2D.** `[manual]`
  - [ ] Coder profile `model.default: xiaomi/mimo-v2.5` (repo-tracked in
        `hermes-config/profiles/coder/config.yaml`; live copy at
        `~/.hermes/profiles/coder/config.yaml`). **2D.**
  - [ ] **`gh` authenticated *inside WSL*** — the coder reads the issue and opens the PR
        via `gh` from WSL (separate from the Windows `gh` login). Verify:
        `wsl -e bash -lc "gh auth status"`. **2D.** `[manual]`
  - ⚠ **Gotcha:** hermes does **not** auto-load `~/.hermes/.env`; any ad-hoc invocation
    must `set -a; source ~/.hermes/.env; set +a` first (production systemd units use
    `EnvironmentFile=`). The gate's coder command does this automatically.
- [ ] **`claude` CLI** (Claude Opus) — architect + CTO harnesses, run headless + tool-less
      (`claude -p --tools ""`). Must be authenticated. Verify: `claude --version`;
      `echo hi | claude -p --tools "" "Reply OK"`. **2E.** `[manual]`

## 3. Repo state — labels  *(needed now — the gate's writes fail without them)*

The gate's state machine (`gate/classifier.py`) requires this **exact** label set on the
target repo. A missing label makes the gate's atomic label-edit fail safely (logged, no
comment, retried) — but it must exist for the gate to make progress. `[auto]`

- [ ] **Scope label:** `AI-GATE-TEST` (migration, phases 2A–2E) → `AI` (production, from 2F).
      This is the human's opt-in + kill-switch and the gate's entire work universe. **2A.**
- [ ] **Role labels:** `role:architect` · `role:coder` · `role:cto`. **2A.**
- [ ] **State labels:** `backlog` · `ready` · `in-progress` · `plan-ready` · `kickoff` ·
      `needs-human`. **2A.**

> ⚠ **`role:cto` is easy to miss** — the throwaway test repo had every label *except*
> `role:cto`, so the coder-PR → CTO routing failed live until it was created. The gate now
> applies label *adds before removes* (separate `gh` calls) so a missing target label can't
> half-strip an issue, but the label must still exist for the move to complete. `setup.ps1`
> must create the **whole** set above.

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

- [x] **Windows Task Scheduler** task running the gate on a cadence (the *only* scheduled
      job). Register with `scripts/register-gate-task.ps1 -Repo owner/repo` (task name
      `MaxAgencyGate`; default dispatch-enabled, 5-min, scope `AI`). Conservative options:
      `-Mode deterministic-only` or `-NoAutoMerge`. Disable/remove:
      `Disable-ScheduledTask`/`Unregister-ScheduledTask -TaskName MaxAgencyGate`. **2F.** `[auto]`
- [x] **Log-retention cleanup task** `MaxAgencyLogCleanup` — a **second** daily hidden task
      that deletes files under `runtime\logs\` (decision JSONL + LLM transcripts) and `logs\`
      older than a retention window (default **7 days**, tunable). `setup.ps1` registers it
      automatically (`-RetentionDays N`); it delegates to `scripts/register-log-cleanup-task.ps1`
      → `scripts/clean-logs.ps1`. Idempotent (re-run updates in place). Run the prune by hand:
      `pwsh scripts/clean-logs.ps1 -RetentionDays 7`. Verify the task:
      `Get-ScheduledTask -TaskName MaxAgencyLogCleanup`. **FEAT-2.** `[auto]`
- [x] **Cut scope label** `AI-GATE-TEST` → `AI` — done: the gate's `--scope-label` now
      defaults to `AI`. The target repo needs the `AI` label (§3). **2F.** `[auto]`
- [x] **Disable the old pollers** — done (Phase 2F): WSL `systemctl --user disable --now`
      the `hermes-*-tick` timers + removed their unit files (kept `hermes-gateway.service`);
      unregistered the Windows `MaxAgency-ClaudeCodeRoutine` task; deleted the legacy poller
      files from the repo. Verify no pollers remain:
      `wsl -e bash -lc "systemctl --user list-timers --all | grep -i hermes"` (none) and
      `Get-ScheduledTask | ? TaskName -match MaxAgency` (only `MaxAgencyGate`). **2F.** `[manual]`/`[auto]`

## 6. Known environment gotchas (not blockers, but document so installs don't trip on them)

- **Git Bash vs PowerShell have different PATHs** on the same machine — "resolves in one
  shell, not the other" is a PATH/stale-shell issue, never a separate filesystem. Restart
  the shell after install.
- **`codex` on Windows is a `.cmd` npm shim** that `subprocess` can't launch directly; the
  gate/bench runners handle this by invoking `node ...\codex.js` (see `gate/harness.py`
  `_runnable_argv`). No human action needed — noted so it isn't re-debugged.
- **The coder runs from a neutral working directory, never the gate's repo.** `wsl.exe`
  inherits the launching process's cwd (translated to `/mnt/c/...`), so a coder launched
  from the Max Agency checkout would run `git`/`gh` (under `--yolo`) *inside it* and can
  mutate the gate's own branch/worktree. The gate runs the coder from a throwaway temp dir
  (`gate.py` `dispatch_coder`, mirroring the Phase 0 orchestrator's neutral cwd). No human
  action needed — noted so the safeguard isn't removed.
- **Codex model availability is account-specific** — verify `gpt-5.4-mini` works on the
  actual account (§2) rather than assuming.

## 7. Observability & logs  *(where a run's output lands)*

Both log trees live under the gate's runtime dir (`--runtime-dir`, default `runtime/`) and
are **git-ignored** (`.gitignore` covers `runtime/` and `logs/`). Created lazily — an empty
board writes nothing.

- **Decision log:** `runtime/logs/gate/<run_id>.jsonl` — one correlated JSONL per run (every
  classify/mutation/dispatch event). Always written. **2A+.**
- **LLM transcripts:** `runtime/logs/transcripts/<run_id>.txt` — the exact prompt SENT to and
  raw output RECEIVED from every LLM call that run (triage/coder/expand/architect/CTO), so a
  silent failure (a model exits 0 but opens no PR) can be diagnosed by reading what it said.
  Written only when an LLM is actually invoked; **zero extra tokens**. **Secrets never land
  here** — only the prompt + model are logged (never the coder's `source ~/.hermes/.env`
  command prefix), and a defensive scrub masks any key/token shapes. **FEAT-1.**
- **Retention:** the `MaxAgencyLogCleanup` task (§5) prunes both trees daily (default 7 days).

---

*Surfaced-by log (newest first): §5 log-cleanup task + §7 transcripts — FEAT-1/FEAT-2
(2026-06-18, soak-test backlog). §3 `role:cto`-label miss + §2 `claude` headless/tool-less —
Phase 2E (2026-06-16). §2 gh-in-WSL + §6 neutral-cwd safeguard — Phase 2D
(2026-06-16, after a coder inherited the repo cwd and ran `git checkout` in it). §3 labels +
stale-installer mismatch — Phase 2C (2026-06-16). §2 codex/model — Phase 0/2C. §2 hermes
`.env` gotcha — Phase 0.*
