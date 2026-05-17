from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AssetRecord:
    asset_id: str
    install_id: str
    provider_id: str
    asset_kind: str
    engine: str
    asset_name: str
    install_location: str = ""
    asset_role: str = "source"
    derived_from_asset_id: str = ""
    source_format: str = "unknown"
    source_uri: str = ""
    schema_fingerprint: str = ""
    data_store_profile_id: str = ""
    schema_name: str = ""


@dataclass(frozen=True)
class AssetVerificationResult:
    asset_id: str
    status: str
    error: str = ""


class AssetVerifier(Protocol):
    def verify(self, asset: AssetRecord) -> AssetVerificationResult:
        """Return present, missing, or error for the given managed asset."""


class RegistryOnlyVerifier:
    def verify(self, asset: AssetRecord) -> AssetVerificationResult:
        if asset.asset_kind != "database":
            return AssetVerificationResult(asset.asset_id, "error", f"Unsupported asset kind: {asset.asset_kind}")
        return AssetVerificationResult(
            asset.asset_id,
            "error",
            f"No verifier configured for {asset.engine or 'unknown'} database assets.",
        )
