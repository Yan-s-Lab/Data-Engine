from __future__ import annotations

from typing import Any, Dict, Optional
import requests


def request_json(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    json_payload: Optional[Dict[str, Any]] = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    resp = requests.request(
        method=method,
        url=url,
        headers=headers,
        json=json_payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()
