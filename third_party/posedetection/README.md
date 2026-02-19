# OpenPose Preprocess for ComfyUI Pose Control

This repository uses OpenPose as a preprocessing step for `configs/examples/comfyui/2_pass_pose_control.json`.

Goal:
- Input: real PNG/JPG image
- Step 1: run OpenPose to output keypoint JSON
- Step 2: render JSON to black-background pose map
- Output: pose control image for ComfyUI ControlNet/OpenPose

## 1) Recommended: use git submodule

For fresh clone:

```bash
git clone --recurse-submodules <your_repo_url>
```

For existing local repo:

```bash
git submodule update --init --recursive
```

If you are setting this project up for the first time, add OpenPose as submodule:

```bash
git submodule add https://github.com/CMU-Perceptual-Computing-Lab/openpose.git third_party/openpose
git submodule update --init --recursive
```

## 2) Build OpenPose (Linux)

Run in conda env `open_data_engine`.

```bash
cd third_party/openpose
mkdir -p build
cd build
cmake ..
cmake --build . --config Release -j"$(nproc)"
```

Expected binary:
- `third_party/openpose/build/examples/openpose/openpose.bin`

## 3) Download OpenPose models

```bash
cd third_party/openpose
./models/getModels.sh
```

## 4) Convert real image -> pose control image

Use helper script:

```bash
bash third_party/posedetection/run_openpose_to_control.sh \
  --image third_party/pose_controlnet_2_pass.png \
  --name pose_controlnet_2_pass
```

Default outputs:
- JSON: `third_party/runs/openpose_native/json/<name>_keypoints.json`
- black pose image: `third_party/runs/openpose_native/render_black/<name>_rendered.png`

## 5) Use in ComfyUI workflow

Load the rendered black pose image into your control node input (e.g. `LoadImage` in `2_pass_pose_control.json`).

## 6) Notes

- `third_party/runs/` is experiment output and should usually stay untracked.
- Do not commit `third_party/openpose/build/` artifacts.
- If OpenPose is unavailable, keep `openpose_json_render.py` as renderer-only utility (requires existing JSON input).
