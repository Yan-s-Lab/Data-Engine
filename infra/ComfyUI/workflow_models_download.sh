
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONFIG_FILE="$SCRIPT_DIR/models.yaml"

BASE_DIR="$PROJECT_ROOT/data/comfyui/models"

# 依赖检查
command -v yq >/dev/null 2>&1 || { echo "❌ 需要安装 yq 解析 YAML"; exit 1; }
command -v hf >/dev/null 2>&1 || { echo "❌ 需要安装 huggingface-cli (pip install hf-transfer)"; exit 1; }

MODEL_COUNT=$(yq '.models | length' "$CONFIG_FILE")
echo "📦 共有 $MODEL_COUNT 个模型需要检查/下载"

for i in $(seq 0 $((MODEL_COUNT - 1))); do
  name=$(yq ".models[$i].name" "$CONFIG_FILE")
  type=$(yq ".models[$i].type" "$CONFIG_FILE")
  dest=$(yq ".models[$i].dest" "$CONFIG_FILE")
  source=$(yq ".models[$i].source" "$CONFIG_FILE")

  TARGET_DIR="$BASE_DIR/$dest" # models 存储目录
  mkdir -p "$TARGET_DIR"

  echo "-------------------------------------------"
  echo "⬇️  [$name] ($type)   来源: $source"
  echo "    目标目录: $TARGET_DIR"
  echo "-------------------------------------------"

  if [[ "$source" == "huggingface" ]]; then
    repo=$(yq ".models[$i].repo" "$CONFIG_FILE")
    files=$(yq ".models[$i].files[]" "$CONFIG_FILE")

    for file in $files; do
      echo "   ➤ 下载 $repo / $file"
      hf download "$repo" --include "$file" --local-dir "$TARGET_DIR"
    done

  elif [[ "$source" == "civitai" ]]; then
    url=$(yq ".models[$i].url" "$CONFIG_FILE")
    filename=$(yq ".models[$i].filename" "$CONFIG_FILE")

    echo "   ➤ 下载 Civitai 文件: $filename"
    wget -q "$url" -O "$TARGET_DIR/$filename"
  fi

  echo "   ✔ 完成 $name"
  echo
done

echo "🎉 所有模型已下载/更新完毕！"
