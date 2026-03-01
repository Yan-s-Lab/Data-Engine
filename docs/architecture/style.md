# Engineering Style Guide (Pipeline-Style, Design-First)

This document defines implementation style and conventions.
`AGENTS.md` is the enforcement policy; this file is the reference manual.

---

## 1) Layering Model

### 1.1 Orchestration Layer (Pipeline / CLI / Entry)
**Owns:**
- reading config + CLI parsing
- selecting and ordering steps
- building execution context (paths, device, run_id, seed, logging)
- artifact layout and I/O policy

**Must NOT:**
- implement business logic / algorithms
- contain step-specific data processing

### 1.2 Component Layer (Steps)
**Owns:**
- single responsibility step implementation
- validating inputs and producing outputs per contract
- being testable in isolation

**Must NOT:**
- parse CLI directly
- decide pipeline order
- call other steps directly (must go through orchestrator)

### 1.3 Core Layer (Pure Libs / Algorithms / Utilities)
**Owns:**
- pure functions and reusable utilities
- algorithms without pipeline awareness

**Must NOT:**
- import orchestration/components
- depend on global config/env variables
- perform orchestration or hidden I/O

---

## 2) Standard Step Interface (Contract)

All pipeline steps MUST be implementable with a stable interface:

- `run(inputs: StepInput, context: RunContext) -> StepOutput`

Where:
- `StepInput` and `StepOutput` are typed schemas (prefer `dataclass` or `pydantic`)
- `RunContext` carries execution-wide info (paths, seeds, device, run_id)

### 2.1 Input/Output Contracts
- Inputs/outputs MUST be explicit fields, not “loose dicts” unless the project already standardizes dicts.
- If using dicts, define and document required keys and value types.

### 2.2 Determinism
- Steps should be deterministic given (inputs + context + config)
- Any randomness MUST be explicit via seed in `RunContext` or config

---

## 3) RunContext (Execution Context) Convention

`RunContext` should include (minimum suggested fields):
- `run_id: str`
- `artifact_dir: Path` (root for outputs)
- `cache_dir: Path` (optional)
- `device: str | torch.device` (if relevant)
- `seed: int` (if relevant)
- `logger` (optional, but prefer structured logging)

Steps MUST NOT:
- compute global artifact paths on their own
- read env vars for core behavior (except explicitly documented toggles)

---

## 4) Configuration-Driven Pipeline Convention

### 4.1 Step Ordering
Pipeline ordering MUST live in config, e.g.:

```yaml
pipeline:
  steps:
    - name: ingest
      params: { ... }
    - name: generate
      params: { ... }
    - name: filter
      params: { ... }
```

### 4.2 Step Registry
Step implementations MUST be resolved via registry:
    - registry["filter"] -> FilterStep

Adding a new step should mean:

    1. implement the step class/function

    2. register it under a stable name

    3. add a config entry to include it

It MUST NOT require editing the orchestrator logic beyond standard registration patterns.

## 5) File and Responsibility Boundaries
### 5.1 Keep Entry Thin

Entry points (main.py, CLI handlers) should be “wiring-only”.
They should not grow into business logic files.

### 5.2 Split by Responsibility

Prefer small modules:

orchestrator/ for pipeline runners and registries

components/steps/ for step implementations

core/ for algorithms/utilities

(Names can be adapted to your repo; the layer responsibilities must remain.)

## 6) Anti-Patterns (Forbidden)

“God main”: CLI entry contains core logic and branching

“Step chaining”: step A directly instantiates/calls step B

“Config ignored”: changing workflow by code edits instead of config

“Deep if/else”: feature variations implemented as nested conditionals

“Reverse imports”: core imports components/orchestrator


## 7) Tests (Minimum Expectations)

Core layer: unit tests for key functions

Step layer: unit test step run() with minimal fixture inputs

Orchestration: minimal integration test verifying:

config step list is executed in order

registry resolution works

outputs are produced to artifact_dir as expected (can be temp dir)

## 8) Documentation Expectations

Any functional change should update:

a Design Note (docs/design-notes/...)

this style guide only if conventions change (avoid frequent edits)