from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from api_launcher.models import Provider


DIRECT_DOWNLOAD_EXTENSIONS = {
    ".7z",
    ".bin",
    ".bz2",
    ".cdf",
    ".csv",
    ".geojson",
    ".gpkg",
    ".grb",
    ".grb2",
    ".grib",
    ".grib2",
    ".gz",
    ".h5",
    ".hdf",
    ".hdf5",
    ".json",
    ".nc",
    ".npy",
    ".parquet",
    ".tar",
    ".tif",
    ".tiff",
    ".txt",
    ".xz",
    ".zip",
    ".zst",
}


@dataclass(frozen=True)
class DownloadEligibility:
    # eligibility 是 plan 階段判斷，真正下載前仍要走 staging、manifest 與 repair policy。
    status: str
    label: str
    reason: str
    direct_url: str = ""
    requires_adapter: bool = False
    requires_api_key: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "label": self.label,
            "reason": self.reason,
            "direct_url": self.direct_url,
            "requires_adapter": self.requires_adapter,
            "requires_api_key": self.requires_api_key,
        }


def assess_provider_download(provider: Provider) -> DownloadEligibility:
    # eligibility 是保守分類：無法證明 direct file URL 時，就交給 adapter/review 流程。
    api_url = provider.api_base_url.strip()
    docs_url = provider.docs_url.strip()
    requires_key = bool(provider.key_env_var.strip())

    if api_url and looks_like_direct_download(api_url):
        # 只有副檔名明確像資料檔，才允許走通用 HTTP downloader。
        return DownloadEligibility(
            status="direct_download",
            label="Direct",
            reason="The API/download URL looks like a direct file URL.",
            direct_url=api_url,
            requires_api_key=requires_key,
        )

    if api_url:
        # 有 API endpoint 但不是檔案 URL，通常需要 adapter 產生 bounded query 或轉換格式。
        return DownloadEligibility(
            status="adapter_required",
            label="Adapter",
            reason="This source exposes an API endpoint; a provider-specific adapter should turn it into dataset files.",
            requires_adapter=True,
            requires_api_key=requires_key,
        )

    if docs_url:
        return DownloadEligibility(
            status="metadata_only",
            label="Docs",
            reason="Only documentation/signup pages are known; no direct dataset URL is available yet.",
            requires_adapter=True,
            requires_api_key=requires_key,
        )

    return DownloadEligibility(
        status="unavailable",
        label="Unavailable",
        reason="No usable docs, API, or direct download URL is configured.",
        requires_adapter=True,
        requires_api_key=requires_key,
    )


def looks_like_direct_download(url: str) -> bool:
    # 副檔名判斷不是安全保證，只是把明顯檔案 URL 分流到直接下載。
    parsed = urllib.parse.urlparse(url.strip())
    suffixes = [suffix.lower() for suffix in Path(urllib.parse.unquote(parsed.path)).suffixes]
    if not suffixes:
        return False
    if suffixes[-1] in DIRECT_DOWNLOAD_EXTENSIONS:
        return True
    return any("".join(suffixes[-2:]).endswith(value) for value in (".tar.gz", ".tar.bz2", ".tar.xz"))
