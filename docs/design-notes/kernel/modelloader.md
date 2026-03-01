# Kernel Design: ModelLoader

## 1. Scope

ModelLoader resolves model artifacts and runtime handles for train/eval/filter stages.

## 2. Responsibilities

- register model artifact metadata
- load model variants by config and stage
- attach model provenance to downstream outputs

## 3. Contracts

Inputs:
- to be defined

Outputs:
- to be defined

## 4. Invariants

- no implicit model version switching during one run
- loaded model identity must be logged in run artifacts

## 5. Open Questions

- model cache policy across machines
- compatibility policy for mixed framework artifacts
