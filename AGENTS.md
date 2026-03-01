# AGENTS.md

## Purpose
This file defines **mandatory execution constraints** for agents working in this repository.
It exists to prevent scope drift, feature hacking, uncontrolled coupling, and “god files”.

---

## 0) Mandatory References (Must Read)
Agents MUST read and follow:

1) `docs/architecture/style.md`  
   - Implementation style, layering rules, step interfaces, config conventions.

2) `docs/design-notes/template.md`  
   - The required Design Note format and content.

3) `./.temp/methods.tex`  
   - Primary authority for paper-level methodology when a design decision is disputed.

**Conflict rule:** If `AGENTS.md` conflicts with `docs/architecture/style.md`, `AGENTS.md` wins.  
If ambiguity remains, STOP and ask the project owner.

---

## 1) Pre-Execution Requirements (Must Do Before Any Code Change)

Before implementing/modifying ANY functionality, agents must:

1) Read relevant docs under `docs/` (including style.md)
2) Inspect the current directory structure relevant to the task
3) Search existing code for similar implementations to reuse
4) Check for existing configs/schema/registries that already support the request

If required context is missing or unclear, STOP and ask.

---

## 2) Design-First Gate (No Design Note = No Coding)

Before writing code, agents MUST create or update a Design Note:

- Location: `docs/design-notes/YYYY-MM-DD_<topic>.md`
- Format: MUST follow `docs/design-notes/template.md`

The Design Note MUST explicitly state:
- what layer(s) are modified and why
- the interface signatures and data contracts
- the exact config keys involved
- how the change conforms to `docs/architecture/style.md`
- minimal test plan

---

## 3) Layering and Dependency Direction (Hard Rule)

Code MUST conform to the layering model:

- Orchestration (CLI/Pipeline/Entry) → Components (Steps) → Core (Pure libs)

Allowed imports:
- Orchestration may import Components and Core
- Components may import Core
- Core may import only Core

Forbidden:
- Core importing Components or Orchestration
- Components importing Orchestration
- Steps calling other steps directly to bypass the orchestrator

---

## 4) Config-Driven Pipeline Rule (Critical)

Any change affecting workflow ordering MUST be expressed via configuration:
- Pipeline step order MUST be defined in config (e.g., `pipeline.steps`)
- Step resolution MUST use a registry/factory (step name → implementation)

Forbidden:
- Hardcoding step order in `main()` or CLI handlers
- “Hidden” behavior toggles without config keys
- Long if/else chains in entry code to simulate a pipeline

---

## 5) Complexity and Decomposition Policy (Hard Rule)

Line count is a SIGNAL, not an automatic violation.

### Soft Thresholds (Design Review Triggers)
- If a single file exceeds ~400 lines, the agent MUST:
  1) justify why the file represents a single coherent responsibility, OR
  2) propose a meaningful decomposition with clear responsibility boundaries

- If a single function exceeds ~80 lines, the agent MUST:
  1) explain why splitting would reduce clarity or cohesion, OR
  2) refactor into semantically meaningful sub-functions

The justification MUST be documented in the Design Note.

Deep branching rule:
- If adding a third conditional branch to support feature variation,
  refactor into strategy/registry dispatch selected by config.

### Prohibited Decompositions
Agents must NOT:
- split code solely to satisfy line counts
- create “utility” or “helper” modules without a clear semantic role
- introduce thin pass-through functions with no independent meaning


## 6) Post-Execution Obligations (Required for Completion)

After implementation/modification, agents MUST:

1) Update docs:
   - finalize Design Note + update relevant docs under `docs/`
2) Add/Update tests:
   - unit tests for core/components, and minimal integration test if pipeline changes
3) Git discipline:
   - commit with meaningful message
   - push to repository

Changes without documentation, tests, commits, and push are incomplete.

---

## 7) Scope Constraint and Termination Rule

Agents MUST operate strictly within the scope of the current request.

Agents MUST NOT:
- introduce unrelated features
- perform speculative refactors
- redesign architecture beyond what the task requires

Once the requested task is complete and recorded (docs + tests + commit + push),
STOP and do not continue unless explicitly instructed.

---

## 8) Current Environment
conda name: "dataengine"