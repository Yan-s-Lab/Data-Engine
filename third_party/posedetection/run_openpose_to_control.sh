#!/usr/bin/env bash
set -euo pipefail

IMAGE=""
NAME=""
OPENPOSE_BIN="third_party/openpose/build/examples/openpose/openpose.bin"
JSON_DIR="third_party/runs/openpose_native/json"
RENDER_DIR="third_party/runs/openpose_native/render_black"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --image)
      IMAGE="$2"
      shift 2
      ;;
    --name)
      NAME="$2"
      shift 2
      ;;
    --openpose-bin)
      OPENPOSE_BIN="$2"
      shift 2
      ;;
    --json-dir)
      JSON_DIR="$2"
      shift 2
      ;;
    --render-dir)
      RENDER_DIR="$2"
      shift 2
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$IMAGE" ]]; then
  echo "--image is required" >&2
  exit 2
fi
if [[ ! -f "$IMAGE" ]]; then
  echo "Image not found: $IMAGE" >&2
  exit 2
fi

if [[ -z "$NAME" ]]; then
  base="$(basename "$IMAGE")"
  NAME="${base%.*}"
fi

if [[ ! -x "$OPENPOSE_BIN" ]]; then
  echo "OpenPose binary not executable: $OPENPOSE_BIN" >&2
  echo "Build first. See third_party/posedetection/README.md" >&2
  exit 2
fi

mkdir -p "$JSON_DIR" "$RENDER_DIR"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
cp "$IMAGE" "$tmp_dir/${NAME}.png"

"$OPENPOSE_BIN" \
  --image_dir "$tmp_dir" \
  --write_json "$JSON_DIR" \
  --display 0 \
  --render_pose 0

json_path="$JSON_DIR/${NAME}_keypoints.json"
out_path="$RENDER_DIR/${NAME}_rendered.png"

python third_party/posedetection/openpose_json_render.py \
  --json "$json_path" \
  --ref-image "$IMAGE" \
  --out "$out_path" \
  --body-line 2 \
  --body-point 2 \
  --face-point 0 \
  --hand-point 0

echo "JSON: $json_path"
echo "POSE_IMG: $out_path"
