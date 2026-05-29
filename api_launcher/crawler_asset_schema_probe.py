"""UI-neutral schema probe service for crawler asset bounds forms.

Tk, Web, and future Qt surfaces should only choose the seed/resource URL.  This
module owns the backend contract that turns that URL into an enriched bounds
form, keeping column inference and source-specific form enrichment out of UI
files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from api_launcher.crawler_asset_bound_forms import (
    CrawlerAssetBoundFormSpec,
    apply_schema_probe_to_crawler_asset_bound_form_spec,
    build_crawler_asset_bound_form_spec,
)
from api_launcher.crawler_asset_bound_display import crawler_asset_bound_form_payload
from api_launcher.crawler_next_action_display import next_action_display_label
from api_launcher.crawler_assets import BUILD_DOWNLOAD_PLAN, CrawlerAsset, load_crawler_asset_source, load_crawler_assets
from api_launcher.schema_probe import SchemaProbeResult, probe_plan_entry_schema


@dataclass(frozen=True)
class CrawlerAssetSchemaProbeResult:
    """Backend result shared by Web payloads and Tk dialogs."""

    asset_id: str
    probe: SchemaProbeResult
    bound_form: CrawlerAssetBoundFormSpec
    next_action: str = "choose_schema_backed_bounds"

    def to_dict(self) -> dict[str, object]:
        return {
            "asset_id": self.asset_id,
            "schema_probe": self.probe.to_dict(),
            "bound_form": crawler_asset_bound_form_payload(self.bound_form),
            "next_action": self.next_action,
            "next_action_label": next_action_display_label(self.next_action),
        }


def crawler_asset_bound_form_schema_probe(
    asset_id: str,
    payload: Mapping[str, object],
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
    schema_probe_runner: Callable[..., SchemaProbeResult] = probe_plan_entry_schema,
) -> dict[str, object]:
    """Probe one candidate entry and return a browser/agent-ready payload."""

    return crawler_asset_bound_form_schema_probe_result(
        asset_id,
        payload,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
        schema_probe_runner=schema_probe_runner,
    ).to_dict()


def crawler_asset_bound_form_schema_probe_result(
    asset_id: str,
    payload: Mapping[str, object],
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
    schema_probe_runner: Callable[..., SchemaProbeResult] = probe_plan_entry_schema,
) -> CrawlerAssetSchemaProbeResult:
    """Probe one candidate entry and keep the enriched form object available."""

    entry = schema_probe_entry_from_payload(payload)
    row_limit = min(25, _positive_int(payload.get("row_limit"), 5))
    timeout = _bounded_float(payload.get("timeout"), default=8.0, lower=1.0, upper=20.0)
    form_spec = crawler_asset_bound_form_spec(
        asset_id,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
    )
    probe = schema_probe_runner(entry, row_limit=row_limit, timeout=timeout)
    return CrawlerAssetSchemaProbeResult(
        asset_id=asset_id,
        probe=probe,
        bound_form=apply_schema_probe_to_crawler_asset_bound_form_spec(form_spec, probe),
    )


def crawler_asset_bound_form_spec(
    asset_id: str,
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> CrawlerAssetBoundFormSpec:
    """Build the base bounds form spec for one crawler asset."""

    asset = _crawler_asset(asset_id, primary_path=primary_path, local_path=local_path, profile_path=profile_path)
    plan_capability = next(
        (capability for capability in asset.capabilities if capability.capability_id == BUILD_DOWNLOAD_PLAN),
        None,
    )
    bounds_schema = plan_capability.bounds_schema if plan_capability is not None else ()
    source = load_crawler_asset_source(asset_id, primary_path, local_path)
    return build_crawler_asset_bound_form_spec(asset.asset_id, bounds_schema, source=source)


def schema_probe_entry_from_payload(payload: Mapping[str, object]) -> dict[str, object]:
    """Normalize Web/Tk seed payloads into the entry shape expected by probes."""

    entry = payload.get("entry")
    if isinstance(entry, Mapping):
        probe_entry = dict(entry)
        if "download_url" not in probe_entry and "api_url" not in probe_entry:
            url = str(probe_entry.get("url") or probe_entry.get("content_url") or "").strip()
            if url:
                probe_entry["download_url"] = url
        return probe_entry
    probe_entry = {
        key: payload[key]
        for key in ("download_url", "api_url")
        if isinstance(payload.get(key), str) and str(payload.get(key)).strip()
    }
    if not probe_entry:
        url = str(payload.get("url") or payload.get("content_url") or "").strip()
        if url:
            probe_entry["download_url"] = url
    return probe_entry


def _crawler_asset(
    asset_id: str,
    *,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> CrawlerAsset:
    for asset in load_crawler_assets(primary_path, local_path, profile_path):
        if asset.asset_id == asset_id:
            return asset
    raise KeyError(f"Crawler asset not found: {asset_id}")


def _positive_int(value: object, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _bounded_float(value: object, *, default: float, lower: float, upper: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return min(upper, max(lower, parsed))


__all__ = [
    "CrawlerAssetSchemaProbeResult",
    "crawler_asset_bound_form_schema_probe",
    "crawler_asset_bound_form_schema_probe_result",
    "crawler_asset_bound_form_spec",
    "schema_probe_entry_from_payload",
]
