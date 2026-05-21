from __future__ import annotations

import json
from pathlib import Path

from api_launcher.models import Provider


PROVIDER_CATALOG_NAME = "APIkeys_collection_catalog.json"

PROVIDER_OVERLAYS: dict[str, dict[str, object]] = {
    # overlay 用來補舊 catalog 尚未表示的安全/secret 欄位，避免直接改歷史 JSON 結構。
    "noaa_ncei_cdo": {
        "terms_url": "https://www.ncei.noaa.gov/cdo-web/webservices/v2",
        "notes": "NOAA was written as NAOO in the request; this entry targets NOAA/NCEI CDO.",
    },
    "nasa_earthdata": {
        "secret_env_vars": ("NASA_EARTHDATA_USERNAME", "NASA_EARTHDATA_PASSWORD"),
    },
    "copernicus_marine": {
        "secret_env_vars": ("COPERNICUS_MARINE_PASSWORD",),
    },
    "opensky_network": {
        "secret_env_vars": ("OPENSKY_PASSWORD",),
    },
}


def provider_from_dict(data: dict[str, object]) -> Provider:
    # catalog JSON 轉 Provider 的唯一入口，避免欄位預設值在多處分歧。
    categories = data.get("categories") or ()
    secret_env_vars = data.get("secret_env_vars") or ()
    crawl_urls = data.get("crawl_urls") or ()
    return Provider(
        provider_id=str(data.get("provider_id") or "").strip(),
        name=str(data.get("name") or "").strip(),
        owner=str(data.get("owner") or "").strip(),
        categories=tuple(str(value) for value in categories),
        geographic_scope=str(data.get("geographic_scope") or "").strip(),
        docs_url=str(data.get("docs_url") or "").strip(),
        api_base_url=str(data.get("api_base_url") or "").strip(),
        signup_url=str(data.get("signup_url") or "").strip(),
        auth_type=str(data.get("auth_type") or "unknown").strip(),
        key_env_var=str(data.get("key_env_var") or "").strip(),
        secret_env_vars=tuple(str(value) for value in secret_env_vars),
        license_url=str(data.get("license_url") or "").strip(),
        terms_url=str(data.get("terms_url") or "").strip(),
        notes=str(data.get("notes") or "").strip(),
        crawl_urls=tuple(str(value) for value in crawl_urls),
    )


def load_provider_catalog(path: Path) -> tuple[Provider, ...]:
    # catalog 檔不存在時回空集合，讓測試/最小環境可以只初始化 schema。
    if not path.exists():
        return ()
    raw_items = json.loads(path.read_text(encoding="utf-8"))
    providers = []
    for item in raw_items:
        provider_id = str(item.get("provider_id") or "").strip()
        merged = {**item, **PROVIDER_OVERLAYS.get(provider_id, {})}
        provider = provider_from_dict(merged)
        if provider.provider_id and provider.name and provider.docs_url:
            # 缺最小欄位的項目不進 catalog，避免 UI 顯示不可操作的空資料源。
            providers.append(provider)
    return tuple(providers)
