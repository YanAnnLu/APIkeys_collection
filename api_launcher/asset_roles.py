from __future__ import annotations


SUPPORTED_ASSET_ROLES = {"source", "curated", "derived", "analysis", "cache"}


def normalize_asset_role(value: str) -> str:
    role = value.strip().lower() or "source"
    if role not in SUPPORTED_ASSET_ROLES:
        raise ValueError(f"Unsupported asset role: {value!r}")
    return role
