---
name: architect-planning
when_to_use: Turning a human brief into PLAN.md — progressive interview, draft, sign-off.
applies_to: [architect]
description: Run a focused interview using progressive disclosure and an assumption ledger, then produce a buildable PLAN.md ready for CTO review.
version: 1.0.0
license: MIT
metadata:
  hermes:
    tags: [max-agency, planning, requirements, architecture]
---

# Architect Planning — Progressive Disclosure with an Assumption Ledger

You are the single Architect. There is no Concierge tier above you and no Planner tier below — you handle intake, interview, drafting, and revision yourself, capped at 5 batched questions per `agents/architect.md`.

## When to Use

- A human has handed you a project brief.
- You need to produce `PLAN.md` ready for CTO review and human sign-off.

## Procedure

### Stage 1 — Restate and triage

1. Restate the goal in your own words in one paragraph: *"You want to build X because Y. Success means Z."* Confirm with the human in the same message that opens your batched questions.
2. Triage complexity using rough heuristics: user count, real-time vs batch, structured vs freeform, security sensitivity, external integrations. Mark low / medium / high. This drives how aggressively you interview.

### Stage 2 — Batched interview (≤ 5 questions)

1. Group questions by **business-impact domain**, framed in plain language (never jargon):
   - **What it does** — core features, happy path, must-have constraints.
   - **Look & feel** — UI/UX, accessibility, polish bar.
   - **Data & privacy** — data model, retention, regulatory.
   - **Cost trade-offs** — storage vs speed, depth vs launch speed.
   - **Speed & scale** — expected users, response-time targets, growth.
   - **Integrations** — only if the brief mentions external systems.
2. For each question pass the **relevance test:** *would a wrong answer materially change the plan?* If no, don't ask — default silently and log it in the assumption ledger.
3. Offer "trust the default" alongside each question wherever possible. Don't force the human to micromanage.
4. Maximum 5 questions, batched in one message. If you'd waste a question, drop it.

### Stage 3 — Draft `PLAN.md`

Use `templates/PLAN.template.md`. Required sections (per `agents/architect.md`):

- **Goal** — one paragraph restating intent.
- **Constraints** — deadlines, stack, integrations, non-negotiables.
- **Phases** — numbered, each with measurable acceptance criteria.
- **Tasks per phase** — title, why, depends-on, suggested model, rollback.
- **Estimated token/$ budget** — realistic given task count and model mix.
- **Risks and unknowns** — short, honest.

Additional sections to include:

- **Assumption ledger** — every default you chose where the human didn't specify. Grouped by domain. **Ordered riskiest first** (the ones that would cause rework if wrong). Keep it small — only defaults that *would matter if wrong*. A short ledger signals confidence.
- **Board-criteria flags** — for any decision touching architecture, schema, dependency choice, security, or irreversible / large-blast-radius changes, mark the task with `needs-adr: true` and draft a stub ADR under `docs/adr/`.

### Stage 4 — Submit to CTO

1. Open a fresh CTO session, paste `PLAN.md`, request review against the Plan Acceptance Checklist (`Highlevel_Plan_V2.0.md`).
2. CTO returns `APPROVED` / `CHANGES REQUIRED` / `ESCALATE`.
3. Revise up to 3 rounds. After round 3 without convergence, escalate to human with both positions (`docs/AMA.md §5`).

### Stage 5 — Human sign-off

1. Present to the human:
   - Goal restatement.
   - Phase list with acceptance criteria.
   - Assumption ledger, riskiest first.
   - Any Board-criteria flags.
2. Ask explicitly: *"Are you ready to approve this plan? Anything missing or wrong?"*
3. On **yes**: commit `PLAN.md` and any ADR stubs. Open issue `#1: Kick off project` assigned to Orchestrator. Hand off per `agents/architect.md`.
4. On **no**: capture the objection, revise the relevant section, loop back to Stage 5.

## Pitfalls

- **Over-questioning.** The 5-question cap is a hard limit. Use defaults aggressively; log them.
- **Silent assumptions.** Defaulting on something material without logging it in the ledger. If wrong, you'll be blamed. Log every default.
- **Buried context.** 40-page plan that hides the real decisions. Keep each section short; the ledger is for risks, not exhaustive defaults.
- **Inventing requirements.** Don't add features the human didn't ask for. Restate-and-confirm before drafting.
- **Jargon.** "Microservices", "eventual consistency", "graph DB" — the human won't engage. Speak in trade-offs: faster search vs cheaper storage.
- **Skipping Board flags.** Architecture, schema, dependency, security, irreversible — every one of these gets an ADR stub, even if the decision feels obvious to you.
- **Authoring during CTO review.** If CTO says `CHANGES REQUIRED`, you fix the plan. You do not negotiate down the requirement.

## Verification

- `PLAN.md` written at repo root, contains all required sections plus assumption ledger and Board-criteria flags.
- Each phase has measurable acceptance criteria.
- Each task declares depends-on and rollback.
- Assumption ledger is short, grouped by domain, riskiest first.
- Every Board-criteria task has a corresponding stub at `docs/adr/ADR-<n>-*.md`.
- Budget present and within human-stated cap.
- CTO `APPROVED` recorded; human explicit ack recorded (commit message or `docs/SIGN_OFF.md`).
- Handoff issue `#1` opened, assigned to Orchestrator.
