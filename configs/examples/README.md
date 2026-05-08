# Example Configs

已按当前实测范围整理；主流程建议只使用：
`dataloader -> generation -> filter(siglip2-margin)`

保留项：
- `dataloader_norm_test_generation_yk002.yaml`
- `dataloader_norm_test_generation_yk002_managed.yaml`
- `comfyui_generate_from_norm_yk001_prompt_canny_managed.yaml`
- `comfyui_generate_from_norm_yk001_prompt_only_managed.yaml`
- `comfyui/*.json`（generate workflow 示例）
- `arm_deltoid_template.txt`（generate prompt 模板）
- `comfyui.env.example`
- `label_studio.env.example`

说明：
- `dataloader_norm_test.yaml` 与 `comfyui_generate_from_norm_yk001_prompt_canny.yaml` 保留用于历史兼容，不再作为主文档推荐入口。
- Filter 入口使用：
  - `configs/coco_pose_2017__expansion/filter/body_pose_coco_filter_input_construction.yaml`
  - `configs/coco_pose_2017__expansion/filter/body_pose_coco_filter_pipiline.yaml`
