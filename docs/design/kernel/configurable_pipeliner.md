# Kernel Design: ConfigurablePipeliner

## 1. Scope

ConfigurablePipeliner composes CLI modules into closed-loop runs using declarative configs.

## 2. Responsibilities

- parse and validate pipeline config
- orchestrate module execution order
- track stage boundaries and handoff artifacts

## 3. Contracts

Inputs:
- to be defined

Outputs:
- to be defined

## 4. Invariants

- pipeline execution graph is explicit in config
- stage outputs are materialized as artifacts, not hidden memory state

## 5. Open Questions

- branching/merge semantics for experimental pipelines
- resume strategy for partially completed runs
