# Kernel Design: DataLoader

## 1. Scope

DataLoader is the mandatory ingress normalizer for real and synthetic samples.

## 2. Responsibilities

- normalize storage path and naming
- enforce dataset format policy
- run schema and file-level validation
- emit ingest-ready artifacts for registration

## 3. Contracts

Inputs:
- to be defined

Outputs:
- to be defined

## 4. Invariants

- no sample bypasses DataLoader before downstream stages
- DataLoader does not own global identity or dedup decisions

## 5. Open Questions

- strict-vs-lenient validation profile by source type
- batch-level error reporting format for failed samples
