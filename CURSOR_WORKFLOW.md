# CURSOR_AGENT_GUIDE.md
> Purpose: Make the Cursor agent consistently productive, token-efficient, and correct in a Python codebase.
> Mental model: The agent is an extremely confident junior dev with amnesia. Our job is to give it guardrails,
> progressive context, and automated quality checks.  :contentReference[oaicite:1]{index=1}

---

## 0) Non-Negotiables (Always)
1. **Plan first, implement second.** For any non-trivial change: produce a plan, risks, and a task checklist before editing. :contentReference[oaicite:2]{index=2}
2. **Work in small slices.** Implement 1–2 checklist items at a time; pause for review/testing between slices. :contentReference[oaicite:3]{index=3}
3. **Never leave errors behind.** If you edited code, you must run the relevant checks (lint/type/test) and fix failures before moving on. :contentReference[oaicite:4]{index=4}
4. **Be explicit about what changed.** Every response that edits code must include:
   - Files changed (paths)
   - Why the change is correct
   - How it was validated (commands + outcome)
5. **If you’re stuck for 30 minutes, stop.** Ask for a narrower scope or propose a different approach; don’t thrash. :contentReference[oaicite:5]{index=5}

---

## 1) Token Efficiency Rules (Progressive Disclosure)
### 1.1 Keep “global docs” short and point to deeper docs
- Maintain a small “root” guide (this file + a short `PROJECT_KNOWLEDGE.md`).
- Put details in focused resource docs (per area/package). Don’t bloat primary instructions. :contentReference[oaicite:6]{index=6}

### 1.2 Ask for *only* the context you need
When you need repo context, request it in this order:
1. Relevant file(s) the user mentions
2. Entry points: `pyproject.toml`, `README.md`, app bootstrap
3. Only then: wider search
Avoid “read the whole repo”.

### 1.3 Don’t repeat large code blocks
- Reference paths + symbols instead.
- If code must be shown, show only the minimal diff or the single function/class being changed.

### 1.4 Compaction protocol (session reset)
Before the user compacts / starts a fresh chat:
- Update dev docs (plan/context/tasks) with:
  - completed items
  - decisions & rationale
  - next steps
This preserves intent across context loss. :contentReference[oaicite:7]{index=7}

---

## 2) Dev Docs System (Prevents “Losing the Plot”)
For any feature/refactor > ~30 minutes, create a task folder:

`dev/active/<task-name>/`
- `<task-name>-plan.md`     (approved plan)
- `<task-name>-context.md`  (key files, decisions, constraints)
- `<task-name>-tasks.md`    (checkbox execution list)

Always:
- Read all three before continuing work on that task.
- Update tasks immediately when completed.
- Update context when decisions change. :contentReference[oaicite:8]{index=8}

### 2.1 Templates

#### `<task-name>-plan.md`
- Goal
- Non-goals (YAGNI guard)
- Proposed design (components + responsibilities)
- Data flow
- Public API changes
- Migration plan (if needed)
- Risks & mitigations
- Validation plan (exact commands)

#### `<task-name>-context.md`
- Key files (paths)
- Assumptions
- Decisions (with rationale)
- Edge cases discovered
- Observability notes (logging/metrics/tracing)

#### `<task-name>-tasks.md`
- [ ] Slice 1: …
- [ ] Slice 2: …
- [ ] Tests: …
- [ ] Docs: …
- [ ] Release/rollback: …

---

## 3) “Skills” as Guardrails (Python Edition)
The article’s key win is separating:
- **How we write code** (skills/guidelines)
from
- **How this project works** (project knowledge). :contentReference[oaicite:9]{index=9}

Create small, focused “skill” docs (or “rules” docs) and load them only when relevant:
- `skills/python-architecture.md` (SOLID, layering, boundaries)
- `skills/python-testing.md` (pytest patterns, fixtures, contract tests)
- `skills/python-data-access.md` (repos/UoW, transactions, idempotency)
- `skills/python-observability.md` (structured logs, correlation IDs)
- `skills/security.md` (input validation, secrets handling, SSRF, etc.)

**Keep each skill short** and push examples into `skills/resources/*` to reduce token load. :contentReference[oaicite:10]{index=10}

### 3.1 Python architecture defaults
- Layering: `api/ (controllers)` → `service/ (use-cases)` → `domain/` → `infra/ (repos, clients)`
- Dependency direction: inner layers do not import from outer layers.
- Use explicit interfaces (Protocols/ABCs) at boundaries.
- Prefer composition over inheritance; avoid “god” services.

---

## 4) Hook Mindset in Cursor (Emulate Automation)
The article’s system relies on hooks that:
- activate the right skills before work
- run checks at the end (“no mess left behind”) :contentReference[oaicite:11]{index=11}

Cursor may not expose the same hooks; emulate them with a strict protocol:

### 4.1 Pre-Work “Skill Activation Check”
Before you propose code changes, state which skill docs apply, e.g.:
- `python-architecture` + `security` + `testing`

### 4.2 Post-Work “Stop Checklist” (mandatory)
After code edits, always run and report:
- `ruff` (lint)
- `mypy` or `pyright` (types) if present
- `pytest` (tests)
- any repo-specific checks (`pre-commit`, `make test`, etc.)

If failures exist:
- fix them before continuing.
- do not declare “unrelated errors are fine.” :contentReference[oaicite:12]{index=12}

---

## 5) Planning & Prompting Protocol (Accuracy > Vibes)
### 5.1 Planning mode
When asked to build something non-trivial, you must:
1. Ask for the minimum needed context (files/constraints).
2. Produce a plan with phases + tasks + risks + success criteria.
3. Wait for plan acceptance before implementation. :contentReference[oaicite:13]{index=13}

### 5.2 Neutral questions (avoid leading yourself)
When reviewing or judging code/design, don’t ask “is this good?”.
Ask: “What are the tradeoffs? What breaks? What’s missing? Alternatives?” :contentReference[oaicite:14]{index=14}

### 5.3 Re-prompting
If output is off:
- restate constraints
- add a “Do NOT do X; instead do Y” section
- keep the plan stable; adjust only the failing slice :contentReference[oaicite:15]{index=15}

---

## 6) Specialized Agents (Roles, Not Generalists)
The article’s “army of agents” works because each has a narrow contract and clear output requirements. :contentReference[oaicite:16]{index=16}

Define these roles (even if you’re not literally spawning subagents, follow the contract):

1. **Plan Architect**
   - Output: plan + risks + tasks checklist + impacted files list

2. **Code Reviewer (Architecture)**
   - Output: violations of SOLID/layering, API design issues, edge cases, maintainability

3. **Test Engineer**
   - Output: test plan + missing tests + suggested fixtures + failure scenarios

4. **Security Reviewer**
   - Output: input validation gaps, injection surfaces, secrets, authz/authn, SSRF/file handling

5. **Build/Fail Fixer**
   - Output: ordered list of failures + minimal fixes + verification commands

**Rule:** No agent response is valid without listing what changed and how it was verified. :contentReference[oaicite:17]{index=17}

---

## 7) “PM2 Insight” for Python: Give the Agent Logs
The article’s PM2 setup matters because it lets the agent fetch logs and debug autonomously. :contentReference[oaicite:18]{index=18}

Python equivalents (choose what exists in the repo):
- Docker Compose: `docker compose logs -f <service> --tail=200`
- systemd journal: `journalctl -u <service> -n 200 -f`
- supervisord: `supervisorctl tail -f <name>`
- uvicorn/gunicorn logs: structured to stdout; aggregated by container runtime

**Requirement:** Services must log to stdout in structured form (JSON preferred) with correlation IDs.

---

## 8) Definition of Done (per slice)
A slice is “done” only when:
- Code compiles / imports cleanly
- Lint + types pass (if configured)
- Tests pass (or new tests added with rationale if not)
- Edge cases addressed
- Observability updated if behavior changed
- Dev docs updated (tasks checked, context updated)

---

## 9) Quick Start Checklist (Agent)
When the user asks for a change:
1. Identify scope size:
   - small fix (no dev-docs)
   - large task (create dev-docs folder)
2. Activate relevant skills.
3. Produce plan + tasks (if non-trivial).
4. Implement 1–2 tasks.
5. Run checks and fix failures.
6. Summarize:
   - files changed
   - commands run
   - next slice

---

## 10) Recommended Repo Layout (Python)
(Adjust to existing conventions; do not force a rewrite.)

- `src/<app>/api/`          (FastAPI routers/controllers)
- `src/<app>/service/`      (use-cases)
- `src/<app>/domain/`       (entities, value objects, interfaces)
- `src/<app>/infra/`        (db/repos, external clients)
- `tests/`                  (pytest)
- `skills/`                 (guidelines + resource docs)
- `dev/active/`             (task dev-docs)

---

## 11) Operating Principles (OOP/SOLID/KISS/YAGNI)
- Prefer small, testable units with explicit boundaries.
- Avoid speculative abstractions; introduce patterns only when pressure exists.
- Optimize for readability and correctness over cleverness.
- Always consider failure modes: retries, idempotency, timeouts, partial failure.
- Maintain security posture: validate inputs, least privilege, safe defaults.

---
