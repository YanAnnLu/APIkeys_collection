from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from api_launcher.models import Provider


DIRECT_DOWNLOAD_EXTENSIONS = {
    ".7z",
    ".bin",
    ".bz2",
    ".csv",
    ".geojson",
    ".grb",
    ".grib",
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
}


@dataclass(frozen=True)
class DownloadEligibility:
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
    api_url = provider.api_base_url.strip()
    docs_url = provider.docs_url.strip()
    requires_key = bool(provider.key_env_var.strip())

    if api_url and looks_like_direct_download(api_url):
        return DownloadEligibility(
            status="direct_download",
            label="Direct",
            reason="The API/download URL looks like a direct file URL.",
            direct_url=api_url,
            requires_api_key=requires_key,
        )

    if api_url:
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
    parsed = urllib.parse.urlparse(url.strip())
    suffixes = [suffix.lower() for suffix in Path(urllib.parse.unquote(parsed.path)).suffixes]
    if not suffixes:
        return False
    if suffixes[-1] in DIRECT_DOWNLOAD_EXTENSIONS:
        return True
    return any("".join(suffixes[-2:]).endswith(value) for value in (".tar.gz", ".tar.bz2", ".tar.xz"))
