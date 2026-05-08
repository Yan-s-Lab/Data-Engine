# Architecture Style

Data Engine is organized as a config-driven pipeline. The codebase is easiest to extend when orchestration, stage implementation, and reusable logic stay separate.

## Layers

### Orchestration

Pipeline runners and CLI entry points own:

- config loading and CLI parsing
- stage ordering
- registry lookup
- run directories, logs, and artifact layout
- process-level execution concerns

Orchestration code should stay thin. It should wire stages together rather than implement stage-specific algorithms.

### Components

Pipeline stages own one unit of work, such as ingestion, generation, filtering, annotation, training, or evaluation.

A stage should:

- validate its required inputs
- write explicit outputs
- be testable in isolation
- avoid directly invoking other stages

### Core

Core modules contain reusable logic without pipeline awareness. They should avoid importing orchestration or component modules.

## Dependency Direction

```text
Orchestration -> Components -> Core
```

This keeps reusable logic independent from CLI and pipeline concerns.

## Step Contracts

Stage inputs and outputs should be explicit. Prefer typed schemas where practical; when existing code uses dictionaries or YAML sections, document the required keys near the stage or config.

Common execution context includes:

- `run_id`
- artifact root or run directory
- device/runtime settings
- seed, when randomness is involved
- logger or report path

Randomness should be controlled by config or run context so repeated runs are reproducible.

## Configuration

Pipeline order belongs in config:

```yaml
pipeline:
  steps: [dataloader, generate, filter]
```

Stage names should resolve through a registry or factory. Entry points should not grow long conditional chains to simulate a pipeline.

## File Boundaries

Prefer modules with clear responsibilities:

- `pipelines/` for orchestration
- stage packages such as `ingest/`, `synth/`, `filter/`, `label/`, `train/`, and `eval/`
- `common/` for shared utilities and pure helpers

Avoid broad utility files when a more specific module name would communicate ownership.

## Testing

Expected coverage scales with the change:

- Core logic: focused unit tests.
- Stage behavior: isolated tests with small fixtures.
- Pipeline behavior: smoke tests for registry resolution, step ordering, resume behavior, and expected artifacts.

## Documentation

Update public docs when a change affects user-facing commands, config shape, artifact layout, deployment, or pipeline behavior.
