from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any, Dict, List
from urllib.parse import urlencode, urlparse, urlunparse

import requests


def submit_prompt(
    base_url: str,
    workflow: Dict[str, Any],
    client_id: str,
    extra_data: Dict[str, Any] | None = None,
) -> str:
    payload: Dict[str, Any] = {"prompt": workflow, "client_id": client_id}
    if extra_data:
        payload["extra_data"] = extra_data
    resp = requests.post(f"{base_url}/prompt", json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return str(data["prompt_id"])


def upload_input_image(
    base_url: str,
    image_path: Path,
    overwrite: bool = True,
    subfolder: str = "",
) -> str:
    with image_path.open("rb") as f:
        files = {"image": (image_path.name, f, "application/octet-stream")}
        data = {"type": "input", "overwrite": str(bool(overwrite)).lower()}
        if subfolder:
            data["subfolder"] = subfolder
        resp = requests.post(f"{base_url}/upload/image", files=files, data=data, timeout=120)
    resp.raise_for_status()
    body = resp.json()
    name = body.get("name")
    if not name:
        raise RuntimeError("ComfyUI /upload/image returned payload without `name`")
    return str(name)


def wait_history(
    base_url: str, prompt_id: str, timeout_sec: int = 300, poll_interval_sec: float = 1.0
) -> Dict[str, Any]:
    start = time.time()
    while time.time() - start < timeout_sec:
        resp = requests.get(f"{base_url}/history/{prompt_id}", timeout=30)
        resp.raise_for_status()
        history = resp.json()
        if prompt_id in history:
            return history[prompt_id]
        time.sleep(poll_interval_sec)
    raise TimeoutError(f"ComfyUI prompt {prompt_id} timeout after {timeout_sec}s")


def fetch_history_once(base_url: str, prompt_id: str) -> Dict[str, Any] | None:
    resp = requests.get(f"{base_url}/history/{prompt_id}", timeout=30)
    resp.raise_for_status()
    history = resp.json()
    if prompt_id in history:
        return history[prompt_id]
    return None


def to_ws_url(base_url: str, client_id: str) -> str:
    p = urlparse(base_url)
    scheme = "wss" if p.scheme == "https" else "ws"
    query = urlencode({"clientId": client_id})
    path = p.path.rstrip("/") + "/ws"
    return urlunparse((scheme, p.netloc, path, "", query, ""))


def wait_websocket_executing_done(
    base_url: str,
    client_id: str,
    prompt_id: str,
    timeout_sec: int = 300,
) -> None:
    try:
        from websockets.sync.client import connect  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "websocket wait mode requires `websockets` package with sync client support"
        ) from exc

    ws_url = to_ws_url(base_url, client_id)
    deadline = time.time() + timeout_sec
    with connect(ws_url, open_timeout=15, close_timeout=3) as ws:
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError(
                    f"ComfyUI websocket wait timeout for prompt_id={prompt_id}"
                )
            message = ws.recv(timeout=remaining)
            if isinstance(message, bytes):
                continue
            msg = json.loads(message)
            if msg.get("type") != "executing":
                continue
            data = msg.get("data", {})
            if data.get("node") is None and str(data.get("prompt_id")) == prompt_id:
                return


def download_history_outputs(
    base_url: str,
    history_entry: Dict[str, Any],
    out_dir: Path,
    max_outputs_per_job: int,
    persist_outputs: bool,
    comfy_output_dir: Path,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    outputs = history_entry.get("outputs", {})
    output_idx = 0

    for node_id, node_out in outputs.items():
        images = node_out.get("images", [])
        for image in images:
            if max_outputs_per_job > 0 and output_idx >= max_outputs_per_job:
                return rows
            filename = str(image["filename"])
            subfolder = str(image.get("subfolder", ""))
            img_type = str(image.get("type", "output"))
            sample_id = Path(filename).stem
            out_path = (
                comfy_output_dir / subfolder / filename
                if subfolder
                else comfy_output_dir / filename
            )

            if persist_outputs or not out_path.exists():
                out_dir.mkdir(parents=True, exist_ok=True)
                resp = requests.get(
                    f"{base_url}/view",
                    params={"filename": filename, "subfolder": subfolder, "type": img_type},
                    timeout=60,
                )
                resp.raise_for_status()
                out_path = out_dir / filename
                out_path.write_bytes(resp.content)

            rows.append(
                {
                    "sample_id": sample_id,
                    "image_path": str(out_path),
                    "source": "synthetic",
                    "generation_backend": "comfyui",
                    "comfy_node_id": str(node_id),
                    "comfy_filename": filename,
                    "comfy_subfolder": subfolder,
                    "comfy_type": img_type,
                }
            )
            output_idx += 1
    return rows
