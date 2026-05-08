# AGENTS.md

## Purpose

This file defines working rules for agents modifying this repository. It is kept as an internal operating guide so public documentation can stay focused on Data Engine usage.

## Required References

Before making code or workflow changes, read:

1. `docs/architecture/style.md`
   - Layering, pipeline structure, config conventions, and testing expectations.
2. `docs/data_flow.md`
   - Current public pipeline flow and artifact references.
3. Relevant docs/configs/code near the requested change.

If `AGENTS.md` conflicts with `docs/architecture/style.md`, `AGENTS.md` wins. If ambiguity remains, ask the project owner.

## Pre-Execution Requirements

Before modifying functionality:

1. Inspect the current directory structure relevant to the task.
2. Search existing code for similar implementations to reuse.
3. Check for existing configs, schemas, registries, and tests that already support the request.
4. Keep changes scoped to the current request.

## Architecture Rules

Code should follow this dependency direction:

```text
Orchestration (CLI/Pipeline/Entry) -> Components (Steps) -> Core (Pure libs)
```

Allowed imports:

- Orchestration may import Components and Core.
- Components may import Core.
- Core may import only Core.

Avoid:

- Core importing Components or Orchestration.
- Components importing Orchestration.
- Steps calling other steps directly to bypass the orchestrator.
- Hardcoded workflow order in entry points when config can express it.

## Config-Driven Pipeline Rule

Workflow ordering belongs in configuration:

```yaml
pipeline:
  steps: [dataloader, generate, filter]
```

Step implementations should be resolved through a registry or factory. Adding a step should normally mean adding the implementation, registering a stable stage name, and including it in config.

## Complexity and Decomposition

Line count is a signal, not a rule by itself.

- If a file grows beyond roughly 400 lines, keep it only when it still represents one coherent responsibility.
- If a function grows beyond roughly 80 lines, consider whether named sub-functions would clarify the behavior.
- Avoid splitting code only to satisfy line counts.
- Avoid generic helper modules without a clear semantic role.

If feature variation adds another branch to already complex logic, prefer strategy or registry dispatch selected by config.

## Completion Expectations

Before finishing a change:

1. Update relevant public docs when behavior or usage changes.
2. Add or update tests when code behavior changes.
3. Run focused verification for the touched area.
4. Commit with a meaningful message.
5. Push the branch.

Stop when the requested task is complete unless the project owner asks for more.

## Current Environment

conda name: `dataengine`
