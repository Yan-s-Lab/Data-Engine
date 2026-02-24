#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

IMAGE=""
NAME=""
OPENPOSE_BIN="$REPO_ROOT/third_party/openpose/build/examples/openpose/openpose.bin"
MODEL_DIR="$REPO_ROOT/third_party/openpose/models"
JSON_DIR="$REPO_ROOT/third_party/runs/openpose_native/json"
RENDER_DIR="$REPO_ROOT/third_party/runs/openpose_native/render_openpose"

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
    --model-dir)
      MODEL_DIR="$2"
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
  echo "Build first. See third_party/openpose/README.md" >&2
  exit 2
fi
if [[ ! -d "$MODEL_DIR" ]]; then
  echo "OpenPose model dir not found: $MODEL_DIR" >&2
  echo "Download models first. Run: (cd third_party/openpose && ./models/getModels.sh)" >&2
  exit 2
fi

mkdir -p "$JSON_DIR" "$RENDER_DIR"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
cp "$IMAGE" "$tmp_dir/${NAME}.png"

"$OPENPOSE_BIN" \
  --image_dir "$tmp_dir" \
  --write_json "$JSON_DIR" \
  --write_images "$RENDER_DIR" \
  --display 0 \
  --output_resolution -1x-1 \
  --disable_blending \
  --model_folder "$MODEL_DIR" \
  --face \
  --hand

json_path="$JSON_DIR/${NAME}_keypoints.json"
out_path="$RENDER_DIR/${NAME}_rendered.png"

echo "JSON: $json_path"
echo "POSE_IMG: $out_path"
