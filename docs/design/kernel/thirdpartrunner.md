# Kernel Design: ThirdPartRunner

## 1. Scope

ThirdPartRunner wraps third-party tools as auditable CLI tasks.

## 2. Responsibilities

- launch external tools with explicit config
- capture execution metadata and outputs
- normalize outputs into kernel-compatible artifacts

## 3. Contracts

Inputs:
- to be defined

Outputs:
- to be defined

## 4. Invariants

- external tool runs must be reproducible from run config + artifacts
- third-party failures surface as explicit run states

## 5. Open Questions

- retry and timeout policy per tool type
- secure handling of external credentials/secrets
