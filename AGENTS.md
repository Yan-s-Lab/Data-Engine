# AGENTS.md

## Agent Execution Rules (Mandatory)

This document defines **how agents must operate in this repository**.

It does not describe system architecture, project vision, or business goals.
It exists solely to constrain execution behavior and prevent scope drift.

---

## 1. Pre-Execution Requirements (Must Do Before Any Action)

Before implementing, modifying, or proposing any functionality, agents **must**:

1. Read relevant documents under the `docs/` directory.
2. Review existing logs, notes, or records related to the target functionality.
3. Inspect the current directory structure and related subdirectories.
4. Examine existing code implementations that are relevant to the task.

Agents must **not**:
- Start implementation based only on assumptions or prior context.
- Propose changes without checking whether similar work already exists.
- Skip document or code inspection.

If required context is missing or unclear, the agent must stop and ask.

---

## 2. Execution Scope Constraint (Critical)

Agents must strictly operate **within the scope of the current task or request**.

Agents must **not**:
- Introduce designs for future stages or unrelated tasks.
- Extend implementation beyond the explicitly requested functionality.
- Combine multiple independent tasks into a single execution.
- Perform speculative refactors or architectural changes.

Over-design and cross-task expansion are explicitly disallowed.

---

## 3. Decision Authority and Dispute Handling

If a requirement, design choice, or behavior is unclear or disputed:

1. The agent must consult `./.temp/methods.tex` as the **primary reference** for
   paper-level methodology and system design intent.
2. If ambiguity remains, the agent must discuss the issue with the project owner
   and obtain explicit confirmation before proceeding.

Agents must **not**:
- Resolve ambiguities independently.
- Introduce alternative designs without discussion.
- Deviate from the methodology described in `methods.tex`.

---

## 4. Post-Execution Obligations (Mandatory)

After completing any functional implementation or modification, agents **must**:

1. Update relevant documentation under the `docs/` directory, or
   create a concise implementation or change log if none exists.
2. Commit the changes to git with a meaningful message.
3. Push the commit to the repository.

Changes without documentation or git commits are considered **incomplete**.

---

## 5. Prohibited Behaviors

Agents must **not**:
- Perform silent changes.
- Modify functionality without recording it.
- Continue implementing additional features after task completion.
- Redefine task goals during execution.

When the requested task is completed, the agent must stop.

---

## 6. Termination Rule

Once the specified task is finished and recorded:

**Do not continue working unless explicitly instructed.**

## 7. Currrent Enviroment
conda name: "open_data_engine"