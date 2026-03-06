## 1) Summary
- Add config-driven post-actions in serial plan runner, executed after each task.
- Primary goal: allow stage/task-level ComfyUI queue checks and GPU memory release between generation/filter/train tasks.

## 2) Scope
### In scope
- `pipelines/run_serial_plan.py` supports `post_actions` at:
  - `serial_plan.post_actions` (global defaults)
  - `serial_plan.stages[].post_actions`
  - `serial_plan.stages[].tasks[].post_actions`
- Built-in post-action registry entries:
  - `comfyui.queue_empty_check`
  - `comfyui.free_memory`
- Plan config update for `configs/coco_pose_2017__expansion/pipeline_serial_plan.yk003.yaml`.
- Unit tests for parse/dispatch behavior.
- Docs update for serial plan config usage.

### Out of scope
- Changing managed pipeline stage orchestration model.
- Introducing parallel task execution.
- Modifying generation/filter algorithm internals.

## 3) Layer Placement (Orchestration / Components / Core)
- Layer changed: Orchestration (`pipelines/run_serial_plan.py`).
- Why: post-task checks/cleanup are execution control concerns and must remain in pipeline orchestrator, not component/core logic.

## 4) Interfaces (Signatures)
### New/changed public interfaces
- Plan config contract is extended; CLI signature remains unchanged.
- Internal dataclass extension:
  - `PlanTask(stage_name: str, task_name: str, config_path: str, post_actions: List[Dict[str, Any]])`

### Backward compatibility
- Existing serial plans without `post_actions` remain valid.
- Default behavior unchanged when no post-actions configured.

## 5) Data Contracts (Explicit Schemas)
### Step Inputs
- Not applicable (no step interface change).

### Step Outputs
- Serial plan summary `results[]` adds optional `post_actions` execution reports.

## 6) Config Contract
- New keys:
  - `serial_plan.post_actions: List[Action]` (optional)
  - `serial_plan.stages[].post_actions: List[Action]` (optional)
  - `serial_plan.stages[].tasks[].post_actions: List[Action]` (optional)

- Action schema (dict):
  - `type: str` (required)
  - `on: success|failure|always` (optional, default `always`)
  - `enabled: bool` (optional, default `true`)
  - `continue_on_error: bool` (optional, default `false`)
  - `timeout_sec: int` (optional, default `10`)
  - `params: mapping` (optional)

- Built-in action types:
  - `comfyui.queue_empty_check`
    - params:
      - `base_url: str` (default `http://127.0.0.1:8188`)
  - `comfyui.free_memory`
    - params:
      - `base_url: str` (default `http://127.0.0.1:8188`)
      - `unload_models: bool` (default `true`)
      - `free_memory: bool` (default `true`)

- Merge rule:
  - effective task post-actions = global + stage + task

## 7) Registry / Dispatch Plan (If applicable)
- Registry location: `pipelines/run_serial_plan.py` action dispatcher.
- Dispatch by `action.type` -> built-in implementation.

## 8) Dependency Direction Check
- Orchestration imports: standard library + `common.config_io` only.
- Components/Core unchanged.
- Direction remains valid.

## 9) Test Plan (Minimum)
- Unit tests:
  - parse and merge post-actions precedence/order.
  - action run condition (`on`).
  - built-in action request contract (`queue_empty_check`, `free_memory`).
- Run:
  - `python test/test_serial_plan_post_actions.py`

## 10) Risks & Mitigations
- Risk: post-action API call fails and blocks plan unexpectedly.
- Mitigation: explicit per-action `continue_on_error`, with detailed report in summary/log.
- Risk: over-coupling to ComfyUI.
- Mitigation: generic action registry + config-driven type dispatch.

## 11) Implementation Checklist
- [x] Design note approved/ready
- [x] Code changes implemented
- [x] Tests added/updated
- [x] Docs updated
- [ ] Git commit message:
- [ ] Pushed to remote
