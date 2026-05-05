## 1) Summary
- 从两个 Label Studio 导出的 `receive_reject` 标注文件提炼并合并为一个 baseline 文件。
- 输出仅保留 `image_path` 与 `label` 两个字段，并将 Label Studio 本地文件 URL 映射为宿主机绝对路径。

## 2) Scope
### In scope
- 读取并合并：
  - `artifacts/datasets/rawdatasets/coco_pose/coco_real_receive_reject.json`
  - `artifacts/datasets/rawdatasets/coco_pose/synthetic_receive_reject.json`
- 路径映射规则（来源 `third_party/label_studio/docker-compose.label-studio.yml`）：
  - `d=artifacts/...` -> `<repo>/artifacts/...`
  - `d=comfyui_output/...` -> `<repo>/data/comfyui/output/...`
- 生成输出：`artifacts/datasets/rawdatasets/coco_pose/baseline_.josn`

### Out of scope
- 不修改现有 pipeline/orchestrator。
- 不改变标签语义（`accept/reject` 原样保留）。

## 3) Layer Placement (Orchestration / Components / Core)
- 本次仅进行数据工件构建与文档更新，不引入新的分层代码。
- 不新增跨层依赖。

## 4) Interfaces (Signatures)
### New/changed public interfaces
- 无新增 public function/class。

### Backward compatibility
- 无代码接口变更。

## 5) Data Contracts (Explicit Schemas)
### Step Inputs
- 输入 JSON（list[dict]）要求字段：
  - `image: str`（`/data/local-files/?d=...`）
  - `label: str`

### Step Outputs
- 输出 JSON（list[dict]）字段：
  - `image_path: str`（绝对路径）
  - `label: str`
- 过滤规则：
  - 跳过 `label` 为空（`None` 或空串）的输入样本。

## 6) Config Contract
- 无新增配置键。
- 路径映射依据现有 compose 挂载，不引入额外配置。

## 7) Registry / Dispatch Plan (If applicable)
- 不适用。

## 8) Dependency Direction Check
- 无新增代码依赖。

## 9) Test Plan (Minimum)
- 运行一次生成与校验脚本：
  - 校验输出总条数 = 两输入条数之和 - 空标签条数
  - 校验每条仅包含 `image_path`/`label`
  - 校验 `image_path` 为绝对路径

## 10) Risks & Mitigations
- 风险：Label Studio URL 不是预期前缀。
- 缓解：生成时显式校验并在异常时失败，避免静默错误映射。

## 11) Implementation Checklist
- [x] Design note approved/ready
- [x] Code changes implemented
- [x] Tests added/updated
- [x] Docs updated
- [ ] Git commit message:
- [ ] Pushed to remote
