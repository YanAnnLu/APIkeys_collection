from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any


USER_AGENT = "APIkeys_collection/0.4 (+dataset-discovery; metadata only)"
DEFAULT_MAX_CRAWLER_RESPONSE_BYTES = 8 * 1024 * 1024


def search_endpoint_url(endpoint_url: str, params: dict[str, str]) -> str:
    # 共用 query builder 只加入有值參數，避免 crawler 各自處理多餘空 query。
    clean_params = {key: value for key, value in params.items() if value}
    if not clean_params:
        return endpoint_url
    parsed = urllib.parse.urlparse(endpoint_url)
    extra_query = urllib.parse.urlencode(clean_params)
    query = parsed.query + ("&" if parsed.query else "") + extra_query
    # URL 可能帶有 UI 或文件錨點；query 必須寫回 parsed 結構，避免接到 #fragment 後面。
    return urllib.parse.urlunparse(parsed._replace(query=query))


def fetch_json(url: str, timeout: float, max_bytes: int = DEFAULT_MAX_CRAWLER_RESPONSE_BYTES) -> dict[str, Any]:
    # crawler 只接受 JSON object 作為 catalog payload；陣列或文字頁面應由專屬 crawler 處理。
    text, _ = fetch_text(url, timeout=timeout, max_bytes=max_bytes)
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object from {url}")
    return payload


def fetch_text(url: str, timeout: float, max_bytes: int = DEFAULT_MAX_CRAWLER_RESPONSE_BYTES) -> tuple[str, str]:
    # 回傳 final_url 是為了保留 redirect 後的 evidence/source_url。
    if max_bytes < 1:
        raise ValueError("max_bytes must be at least 1.")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError(f"Crawler metadata response exceeded {max_bytes} bytes: {url}")
        charset = response.headers.get_content_charset() or "utf-8"
        final_url = response.geturl()
    return data.decode(charset, errors="replace"), final_url
