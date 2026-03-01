# Kernel Design: TaskOrchestrator

Status: post-MVP extension (not required for single-node closed-loop startup).

## 1. Scope

TaskOrchestrator manages distributed task assignment and lifecycle across root host and worker nodes.

## 2. Responsibilities

- define task units and dispatch to nodes
- track task state (`pending/running/done/failed/stopped`)
- enforce stop conditions (for example target sample count)
- record task-level execution events

## 3. Non-scope

- global sample identity and dedup resolution (owned by DataRegistry)
- artifact transfer, checksum verification, and landing layout (owned by ArtifactSync)
- tool-specific generation execution logic (owned by ThirdPartRunner / node-side agent)

## 4. Task model

Minimum task identity:
- `task_id`
- `task_type` (for example `synthetic_generation`, `augmentation`)
- `policy_version`
- `requested_count` and stop condition block
- `dispatch_spec` (node selector, resource hints, priority)

Minimum assignment identity:
- `assignment_id`
- `task_id`
- `node_id`
- `attempt_id`
- `idempotency_key`

`idempotency_key` must ensure replay-safe dispatch under retries.

## 5. State machine

Task lifecycle states:
- `pending`: accepted by root, not dispatched
- `running`: at least one active assignment
- `stopping`: stop condition reached, waiting for node wind-down
- `done`: stop condition satisfied and all tracked assignments finalized
- `failed`: terminal failure by policy
- `canceled`: operator-triggered termination

Assignment lifecycle states:
- `assigned`
- `acknowledged`
- `running`
- `succeeded`
- `failed`
- `timed_out`
- `canceled`

Allowed transitions must be explicit and append-only in event logs.

## 6. Stop policy

TaskOrchestrator supports policy-driven stop conditions:
- target accepted sample count (checked against DataRegistry accepted count)
- deadline/time budget
- max failed attempts or failure-rate threshold
- manual stop signal from operator

Stop semantics:
- `soft_stop`: no new assignments; allow in-flight work to finish
- `hard_stop`: cancel in-flight assignments after grace period

## 7. Reliability and recovery model

- delivery model is at-least-once for assignments
- assignment execution must be idempotent by `idempotency_key`
- root restart must recover task state from append-only event log + checkpoints
- node liveness is heartbeat-based with timeout escalation

## 8. Contracts

Inputs:
- task submission spec
- node inventory/capability snapshot
- runtime signals (heartbeat, assignment status, operator commands)
- registry progress signals for stop-condition checks

Outputs:
- assignment dispatch records
- task/assignment state transition events
- stop decisions and termination commands
- orchestration summary for downstream sync/filter stages

## 9. Invariants

- task transitions are explicit and auditable
- retries do not create inconsistent final task states
- orchestration metadata is recoverable after root restart
- stop-by-count uses DataRegistry accepted samples as source of truth
- no node-local success is treated as final until root records it

## 10. Cross-kernel boundaries

- DataRegistry provides accepted-count and identity-backed progress signals.
- ArtifactSync consumes finalized assignment outputs after orchestrator marks them ready.
- ConfigurablePipeliner can compose multiple orchestrated tasks but must not bypass task state contracts.

## 11. Open Questions

- pull-vs-push node scheduling model
- retry/backoff defaults by task type and node class
- fairness policy when mixed-priority tasks compete for the same nodes
