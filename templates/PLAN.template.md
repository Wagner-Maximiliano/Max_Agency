# PLAN — {{project_name}}

**Status:** DRAFT | UNDER_REVIEW | APPROVED
**Architect:** {{model}}
**CTO sign-off:** {{date or PENDING}}
**Human approval:** {{date or PENDING}}

## Goal

{{One paragraph restating the human's intent. Specific, testable.}}

## Constraints

- **Stack:** {{languages, frameworks, runtimes}}
- **Deadlines:** {{date or NONE}}
- **Integrations:** {{external services that must work}}
- **Non-negotiables:** {{anything human flagged as must-have / must-not-have}}

## Budget

- **Token cap:** {{N}} tokens
- **$ cap:** {{$X}}
- **Time cap:** {{wall-clock estimate}}

## Phases

### Phase 1 — {{name}}

**Goal:** {{one line}}

**Acceptance criteria:**
- [ ] {{measurable}}
- [ ] {{measurable}}

**Tasks:**

| # | Title | Why | Depends on | Suggested model | Rollback |
|---|---|---|---|---|---|
| 1.1 | {{title}} | {{reason}} | — | claude-code | {{how to undo}} |
| 1.2 | {{title}} | {{reason}} | 1.1 | hermes | {{how to undo}} |

### Phase 2 — {{name}}

(repeat)

## Parallelisation map

Tasks that can run concurrently:
- 1.1 ∥ 1.3 (no file overlap)
- 2.1 ∥ 2.2 (no file overlap)

## Risks and unknowns

- {{risk}} → mitigation: {{plan}}
- {{unknown}} → resolution path: {{who decides, when}}

## Out of scope

- {{explicitly excluded — saves arguments later}}
