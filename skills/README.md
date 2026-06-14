# Skills

Reusable instructions, recipes, and capability descriptions that any agent can pull in when relevant. Skills keep the core agent prompts short — instead of every system prompt knowing how to write a database migration, set up logging, or scaffold a CLI, that knowledge lives here and is loaded on demand.

## Format

Every skill is a single `.md` file in this directory with a frontmatter header:

```markdown
---
name: <kebab-case-name>
when_to_use: <one short sentence describing the trigger condition>
applies_to: [architect, cto, orchestrator, coder]   # which roles may use it
---

# Skill body

<Instructions, code patterns, examples, gotchas — whatever the agent needs.>
```

Required fields:

- **`name`** — kebab-case, unique. Filename should match.
- **`when_to_use`** — used by agents to decide if the skill applies. Be specific. Bad: "for Python code". Good: "when adding a new Python CLI subcommand using Click".
- **`applies_to`** — list of roles that may load this skill. Limits scope so an Architect doesn't load coder-only patterns.

## How agents use skills

On every task pickup, an agent must:

1. List the files in `skills/`.
2. Read each skill's frontmatter only (not the body).
3. Match `when_to_use` against the current task description.
4. For each match, read the full skill body and follow it.
5. If multiple skills match and conflict, prefer the more specific one. If still ambiguous, escalate.

This is mandatory. Skipping skill discovery is a standards violation.

## Authoring skills

Good skills:

- Solve one problem each. No mega-skills.
- Have unambiguous `when_to_use` triggers.
- Include a worked example, not just abstract advice.
- Reference `CODING_STANDARDS.md` rather than restating it.
- Get updated when the underlying pattern changes — stale skills are worse than missing ones.

Start from [`_template.md`](_template.md).

## Index

Update this section when you add a skill. Keep one line per skill.

### Max Agency native

- `architect-planning/` — progressive-disclosure interview, assumption ledger, PLAN.md drafting. (architect)
- `coder-build-task/` — single-issue implementation, in-scope, with tests and a draft PR. (coder)
- `cto-review/` — adversarial single-pass review with skepticism score and structured verdict. (cto)
- `github-workflow/` — branch-per-issue, draft PR, CI gate, PR-driven merge. (orchestrator, coder, cto)
- `quota-guard/` — free-first routing across rolling vendor windows. (orchestrator)
- `human-testing/` — optional plain-language test guides for GUI phases. (orchestrator)

## Format note

Skills in this repo follow the agentskills.io shape: one directory per skill containing a `SKILL.md`
with the frontmatter described above. The flat-file form (`skills/<name>.md`) also works — the
mandatory discovery rule reads frontmatter from whichever `.md` exists.
