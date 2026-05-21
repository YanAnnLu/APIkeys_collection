from __future__ import annotations


SUPPORTED_ASSET_ROLES = {"source", "curated", "derived", "analysis", "cache"}


def normalize_asset_role(value: str) -> str:
    # asset_role 影響 repair/解除納管政策；未知角色不能默默寫進 registry。
    role = value.strip().lower() or "source"
    if role not in SUPPORTED_ASSET_ROLES:
        raise ValueError(f"Unsupported asset role: {value!r}")
    return role
