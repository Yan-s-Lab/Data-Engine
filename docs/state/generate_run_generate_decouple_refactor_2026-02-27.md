# Generation 重构：run_generate 解耦瘦身（2026-02-27）

## Scope
- 仅重构 generation 阶段代码组织，不改核心行为语义。
- 目标：降低 `synth/run_generate.py` 耦合与长度，清理不必要臃肿。

## Changes
- 拆分 `synth/run_generate.py`：
  - `synth/comfyui_client.py`
    - `submit_prompt`
    - `upload_input_image`
    - `wait_history` / `fetch_history_once`
    - `wait_websocket_executing_done` / `to_ws_url`
    - `download_history_outputs`
  - `synth/comfyui_workflow.py`
    - prompt graph 校验与加载
    - seed/prompt/filename/anchor 注入
    - anchor 配置规范化与尺寸过滤
  - `synth/generate_manifest.py`
    - manifest 配置规范化
    - core synth manifest 构建
    - report/synth_manifest 写出
- `synth/run_generate.py`
  - 收敛为编排层，保留主流程调度。
  - 文件行数由约 1200+ 降到约 600 行。
  - 保持测试依赖的函数导出兼容（通过模块导入暴露）。

## Removed / Simplified
- 删除 `run_generate.py` 中与编排无关的大段 ComfyUI 请求与 workflow 注入实现（迁移到独立模块）。
- 删除输出落盘路径注入的重复代码，统一在 `generate_manifest.write_generate_outputs` 内处理。

## Validation
- `python -m py_compile synth/run_generate.py synth/comfyui_client.py synth/comfyui_workflow.py synth/generate_manifest.py`
- `conda run -n dataengine python -m unittest discover -s test -p 'test_generate_manifest_profile.py' -v`
- `conda run -n dataengine python -m unittest discover -s test -p 'test_generate_anchor_filter.py' -v`
