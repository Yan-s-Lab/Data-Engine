import json
from pathlib import Path
from typing import Dict, Any
import requests
from .base import GenerationBackend

class ComfyUIBackend(GenerationBackend):
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.base_url = config["base_url"]
        self.workflow_file = Path(config["workflow_file"]).resolve()
        self.workflow = json.loads(self.workflow_file.read_text(encoding="utf-8"))

    def _build_prompt(self, idx: int) -> str:
        tpl = self.config.get("prompt_template", "image {idx}")
        seed_base = int(self.config.get("seed_start", 1))
        return tpl.format(idx=idx, seed=seed_base + idx)

    def _update_workflow_for_job(self, idx: int) -> Dict[str, Any]:
        """
        这里你要根据自己的 ComfyUI workflow 结构，
        动态改 prompt / seed / 输出路径节点。
        下面只是一个示意。
        """
        wf = json.loads(json.dumps(self.workflow))  # 深拷贝
        prompt = self._build_prompt(idx)
        seed = int(self.config.get("seed_start", 1)) + idx

        # 举例：假设有个 nodes["prompt"] / nodes["seed"]…
        # wf["nodes"]["prompt"]["inputs"]["text"] = prompt
        # wf["nodes"]["seed"]["inputs"]["seed"] = seed

        return wf

    def generate_one(self, idx: int, out_dir: Path) -> Dict[str, Any]:
        out_dir.mkdir(parents=True, exist_ok=True)
        wf = self._update_workflow_for_job(idx)

        # 1. 调 ComfyUI API 提交 workflow（具体 endpoint 你按自己现有的来）
        # 这里用示意版:
        resp = requests.post(f"{self.base_url}/prompt", json=wf, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        # 2. 等任务完成 + 拿到图片数据 / 文件名
        # 实战里可能要轮询 history / queue，这里简化成一次拿回（你可以以后自己加强）
        img_bytes = data["image_bytes"]  # 只是示例，按你实际返回改

        # 3. 保存文件
        filename = f"{self.name}_{idx:04d}.png"
        out_path = out_dir / filename
        out_path.write_bytes(img_bytes)

        meta = {
            "backend": self.name,
            "type": "comfyui",
            "filename": filename,
            "prompt": self._build_prompt(idx),
            "idx": idx,
            "config_snapshot": self.config,
        }
        return meta
