# CLI Rewrite Quickstart

This branch is the CLI-first rewrite scaffold.

## 中文手册（傻瓜式）
- `docs/README_PIPELINE_ZH.md`
- OpenPose 前置（submodule + 构建 + pose 控制图生成）：`third_party/posedetection/README.md`

## 1) Generate synthetic images via ComfyUI
```bash
python synth/comfyui_generate.py \
  --workflow /path/to/workflow.json \
  --base-url http://127.0.0.1:8188 \
  --out-dir ./artifacts/comfy_round_001 \
  --num-images 10
```

## 2) Ingest generated images to collection-gateway
```bash
export COLLECTION_GATEWAY_URL=http://localhost:8001
python synth/comfyui_to_collection.py \
  --images-dir ./artifacts/comfy_round_001 \
  --collection-name comfy_round_001 \
  --source-type manual
```

## 3) Push uncertain samples to Label Studio
`manifest.jsonl` rows should include `image_url` by default.
```bash
python label/label_studio_push.py \
  --base-url http://localhost:8080 \
  --token $LABEL_STUDIO_TOKEN \
  --project-id 1 \
  --manifest ./artifacts/uncertain_manifest.jsonl
```

## 4) Pull labels from Label Studio
```bash
python label/label_studio_pull.py \
  --base-url http://localhost:8080 \
  --token $LABEL_STUDIO_TOKEN \
  --project-id 1 \
  --out ./artifacts/labels/label_studio_pull.jsonl
```

## 5) Minimal runnable loop stub (`filter -> train -> eval`)
```bash
conda run -n open_data_engine python pipelines/filter_train_eval_round.py \
  --config configs/examples/min_closed_loop_stub.yaml
```

Key outputs are under:
`artifacts/runs/m1_filter_train_eval_demo/{filter,train,eval}/`

## 6) Single-node minimal closed loop (`DataLoader -> generate -> filter -> train -> eval`)
```bash
python pipelines/run_yaml_pipeline.py \
  --config configs/examples/min_single_node_closed_loop.yaml
```

Key outputs are under:
`artifacts/runs/m2_single_node_closed_loop_demo/{dataloader,generate,filter,train,eval}/`

## 7) Single-node closed loop with real ComfyUI generation
```bash
python pipelines/run_yaml_pipeline.py \
  --config configs/examples/min_single_node_closed_loop_comfyui.yaml
```

This uses `generate.backend: comfyui` in `synth/run_generate.py`.
