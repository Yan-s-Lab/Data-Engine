# Kernel Design: ArtifactSync

Status: post-MVP extension (not required for single-node closed-loop startup).

## 1. Scope

ArtifactSync moves and verifies artifacts between worker nodes and root host for downstream processing.

## 2. Responsibilities

- pull/push artifact batches by task and policy
- verify integrity (count/hash/size/checkpoint markers)
- normalize artifact landing layout on root host
- emit sync reports for pipeline handoff

## 3. Contracts

Inputs:
- to be defined

Outputs:
- to be defined

## 4. Invariants

- sync is resumable for interrupted transfers
- integrity verification is required before downstream use
- sync actions are logged with source/target provenance

## 5. Open Questions

- transport abstraction (rsync/scp/object-store) selection rule
- retention policy for remote artifacts after successful pull
