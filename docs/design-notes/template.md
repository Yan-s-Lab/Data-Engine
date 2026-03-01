# Design Note Template

> File name: `docs/design-notes/YYYY-MM-DD_<topic>.md`  
> This note is REQUIRED before implementation.

---

## 1) Summary
- What is the change?
- Why is it needed?

## 2) Scope
### In scope
- ...

### Out of scope
- ...

## 3) Layer Placement (Orchestration / Components / Core)
- Which layer(s) will change?
- Why is this the correct placement?

## 4) Interfaces (Signatures)
### New/changed public interfaces
- `function/class`: signature
- Inputs:
- Outputs:
- Error handling:

### Backward compatibility
- Does this break existing callers/configs?
- If yes, migration plan:

## 5) Data Contracts (Explicit Schemas)
### Step Inputs
- Schema type (dataclass/pydantic/dict contract):
- Required fields:
- Optional fields + defaults:

### Step Outputs
- Schema type:
- Fields:

## 6) Config Contract
- Config keys added/used:
- Defaults:
- Validation rules:
- Example config snippet:

## 7) Registry / Dispatch Plan (If applicable)
- Registry name/location:
- Step name(s) registered:
- How config resolves to implementation:

## 8) Dependency Direction Check
Confirm imports follow:
Orchestration → Components → Core

- Orchestration imports:
- Components imports:
- Core imports:

## 9) Test Plan (Minimum)
- Unit tests to add/modify:
- Integration test to add/modify:
- How to run tests:

## 10) Risks & Mitigations
- Potential failure modes:
- Mitigations:

## 11) Implementation Checklist
- [ ] Design note approved/ready
- [ ] Code changes implemented
- [ ] Tests added/updated
- [ ] Docs updated
- [ ] Git commit message:
- [ ] Pushed to remote