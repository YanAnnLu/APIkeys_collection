from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any


USER_AGENT = "APIkeys_collection/0.4 (+dataset-discovery; metadata only)"


def search_endpoint_url(endpoint_url: str, params: dict[str, str]) -> str:
    clean_params = {key: value for key, value in params.items() if value}
    separator = "&" if urllib.parse.urlparse(endpoint_url).query else "?"
    return endpoint_url + separator + urllib.parse.urlencode(clean_params)


def fetch_json(url: str, timeout: float) -> dict[str, Any]:
    text, _ = fetch_text(url, timeout=timeout)
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object from {url}")
    return payload


def fetch_text(url: str, timeout: float) -> tuple[str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        final_url = response.geturl()
    return data.decode(charset, errors="replace"), final_url
