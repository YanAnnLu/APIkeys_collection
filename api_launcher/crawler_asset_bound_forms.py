"""Build frontend-neutral bounds forms for crawler assets.

This module is the contract layer between crawler capability metadata and UI
input controls.  It intentionally does not import Tk, Web, or Qt code.  The
service receives backend facets such as ``time`` or ``bbox`` and expands them
into stable form fields, presets, recommendations, and a normalized payload
that crawler/download services can consume.

The important boundary is:

``bounds facets -> form spec -> user values -> normalized bounds payload``

UI shells may render the form differently, but they should not reimplement the
facet expansion or payload normalization rules here.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from typing import Mapping

from api_launcher.crawler_asset_bounds import CrawlerAssetBoundFacet
from api_launcher.crawlers.types import DatasetDiscoverySource


# Presets are UX helpers, not hidden crawler defaults.  They give first-time
# users a safe one-click starting point while still preserving the explicit
# payload that will be sent to the backend.
BBOX_REGION_PRESETS: tuple[dict[str, object], ...] = (
    {
        "preset_id": "global",
        "label_zh_TW": "全球",
        "label_en": "Global",
        "description_zh_TW": "用全球經緯度範圍做第一次探索；適合還不確定區域時使用。",
        "description_en": "Use global lon/lat bounds for a first exploration pass.",
        "scope_tokens": ("global", "world", "ocean"),
        "values": {"bbox_west": -180, "bbox_south": -90, "bbox_east": 180, "bbox_north": 90},
        "tone": "neutral",
    },
    {
        "preset_id": "taiwan",
        "label_zh_TW": "台灣",
        "label_en": "Taiwan",
        "description_zh_TW": "常用台灣本島與近海粗略界域，適合展示或初次試抓。",
        "description_en": "A coarse Taiwan and nearshore bounding box for demos and first runs.",
        "scope_tokens": ("taiwan", "tw", "asia"),
        "values": {"bbox_west": 119.0, "bbox_south": 21.5, "bbox_east": 123.5, "bbox_north": 25.5},
        "tone": "success",
    },
    {
        "preset_id": "continental_us",
        "label_zh_TW": "美國本土",
        "label_en": "Continental US",
        "description_zh_TW": "美國本土粗略界域，適合 NOAA / data.gov 類型入口的第一輪查詢。",
        "description_en": "A coarse continental-US bounding box for NOAA/data.gov-style first runs.",
        "scope_tokens": ("us", "usa", "global/us", "coastal"),
        "values": {"bbox_west": -125.0, "bbox_south": 24.0, "bbox_east": -66.0, "bbox_north": 50.0},
        "tone": "neutral",
    },
    {
        "preset_id": "nyc",
        "label_zh_TW": "紐約市",
        "label_en": "New York City",
        "description_zh_TW": "NYC Open Data 類型表格與地理欄位的常用示範界域。",
        "description_en": "A common demo box for NYC Open Data tables with geospatial fields.",
        "scope_tokens": ("nyc", "new_york", "new york"),
        "values": {"bbox_west": -74.3, "bbox_south": 40.45, "bbox_east": -73.65, "bbox_north": 40.95},
        "tone": "neutral",
    },
    {
        "preset_id": "san_francisco",
        "label_zh_TW": "舊金山",
        "label_en": "San Francisco",
        "description_zh_TW": "SF Open Data 類型表格與地理欄位的常用示範界域。",
        "description_en": "A common demo box for San Francisco Open Data geospatial tables.",
        "scope_tokens": ("san_francisco", "sf", "bay"),
        "values": {"bbox_west": -122.55, "bbox_south": 37.68, "bbox_east": -122.33, "bbox_north": 37.84},
        "tone": "neutral",
    },
)


@dataclass(frozen=True)
class CrawlerAssetBoundPreset:
    """One suggested set of field values that a UI may apply on demand."""

    preset_id: str
    label_zh_TW: str
    label_en: str
    description_zh_TW: str
    description_en: str
    values: Mapping[str, object]
    tone: str = "neutral"

    def to_dict(self) -> dict[str, object]:
        return {
            "preset_id": self.preset_id,
            "label_zh_TW": self.label_zh_TW,
            "label_en": self.label_en,
            "description_zh_TW": self.description_zh_TW,
            "description_en": self.description_en,
            "values": dict(self.values),
            "tone": self.tone,
        }


@dataclass(frozen=True)
class CrawlerAssetBoundFormProfile:
    """Declarative summary for a crawler asset bounds form.

    The full form spec remains the source of field details.  This profile gives
    Tk/Web/Qt a compact contract for status, facets, presets, and next action,
    so frontends do not need to infer UI flow from raw fields.
    """

    profile_id: str
    asset_id: str
    status: str
    display_label: str
    display_tone: str
    next_action: str
    field_count: int = 0
    required_field_ids: tuple[str, ...] = ()
    optional_field_ids: tuple[str, ...] = ()
    facet_ids: tuple[str, ...] = ()
    groups: tuple[str, ...] = ()
    controls: tuple[str, ...] = ()
    schema_probe_required_count: int = 0
    schema_probe_field_ids: tuple[str, ...] = ()
    preset_count: int = 0
    preset_ids: tuple[str, ...] = ()
    recommended_value_keys: tuple[str, ...] = ()
    warning_codes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "asset_id": self.asset_id,
            "status": self.status,
            "display_label": self.display_label,
            "display_tone": self.display_tone,
            "next_action": self.next_action,
            "field_count": self.field_count,
            "required_field_ids": list(self.required_field_ids),
            "optional_field_ids": list(self.optional_field_ids),
            "facet_ids": list(self.facet_ids),
            "groups": list(self.groups),
            "controls": list(self.controls),
            "schema_probe_required_count": self.schema_probe_required_count,
            "schema_probe_field_ids": list(self.schema_probe_field_ids),
            "preset_count": self.preset_count,
            "preset_ids": list(self.preset_ids),
            "recommended_value_keys": list(self.recommended_value_keys),
            "warning_codes": list(self.warning_codes),
        }


@dataclass(frozen=True)
class CrawlerAssetBoundFormField:
    """前端中立的 crawler asset 界域表單欄位。

    這層只描述 UI 應該畫什麼，不碰 Tk/Qt widget。未來 Qt 版只要吃同一份
    form spec，就能和 Tk 版共用界域定義邏輯。
    """

    field_id: str
    facet_id: str
    label_zh_TW: str
    label_en: str
    group: str
    control: str
    value_type: str = "text"
    default: object = ""
    required: bool = False
    options: tuple[str, ...] = ()
    maps_to: tuple[str, ...] = ()
    requires_schema_probe: bool = False
    help_zh_TW: str = ""
    help_en: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "field_id": self.field_id,
            "facet_id": self.facet_id,
            "label_zh_TW": self.label_zh_TW,
            "label_en": self.label_en,
            "group": self.group,
            "control": self.control,
            "value_type": self.value_type,
            "default": self.default,
            "required": self.required,
            "options": list(self.options),
            "maps_to": list(self.maps_to),
            "requires_schema_probe": self.requires_schema_probe,
            "help_zh_TW": self.help_zh_TW,
            "help_en": self.help_en,
        }


@dataclass(frozen=True)
class CrawlerAssetBoundFormSpec:
    """Complete UI-neutral form contract for one crawler asset.

    ``fields`` describes what should be rendered.  ``recommended_values`` and
    ``presets`` are optional helpers that reduce blind typing.  ``warning_codes``
    keeps schema-probe and preset availability visible to UI shells without
    forcing the UI to inspect every field.
    """

    asset_id: str
    status: str
    fields: tuple[CrawlerAssetBoundFormField, ...] = ()
    schema_probe_required_count: int = 0
    groups: tuple[str, ...] = ()
    warning_codes: tuple[str, ...] = ()
    recommended_values: Mapping[str, object] = field(default_factory=dict)
    presets: tuple[CrawlerAssetBoundPreset, ...] = ()
    guidance_zh_TW: str = ""
    guidance_en: str = ""

    @property
    def succeeded(self) -> bool:
        return self.status == "ready"

    def to_dict(self) -> dict[str, object]:
        return {
            "asset_id": self.asset_id,
            "status": self.status,
            "form_profile": crawler_asset_bound_form_profile(self).to_dict(),
            "fields": [field.to_dict() for field in self.fields],
            "schema_probe_required_count": self.schema_probe_required_count,
            "groups": list(self.groups),
            "warning_codes": list(self.warning_codes),
            "recommended_values": dict(self.recommended_values),
            "presets": [preset.to_dict() for preset in self.presets],
            "guidance_zh_TW": self.guidance_zh_TW,
            "guidance_en": self.guidance_en,
        }


def crawler_asset_bound_form_profile(spec: CrawlerAssetBoundFormSpec) -> CrawlerAssetBoundFormProfile:
    """Summarize a full form spec into the compact status profile used by UI cards.

    The profile is derived from the full spec on purpose.  Keeping one source of
    truth prevents Tk/Web/Qt from drifting into three different interpretations
    of the same form.
    """

    fields = spec.fields
    required_field_ids = tuple(field.field_id for field in fields if field.required)
    optional_field_ids = tuple(field.field_id for field in fields if not field.required)
    facet_ids = tuple(dict.fromkeys(field.facet_id for field in fields))
    controls = tuple(dict.fromkeys(field.control for field in fields))
    schema_probe_field_ids = tuple(field.field_id for field in fields if field.requires_schema_probe)
    preset_ids = tuple(preset.preset_id for preset in spec.presets)
    recommended_value_keys = tuple(spec.recommended_values)
    if not fields:
        profile_id = "bounds_form_empty"
        display_label = "不需界域"
        display_tone = "neutral"
        next_action = "continue_to_download_plan"
    elif schema_probe_field_ids:
        profile_id = "bounds_form_schema_probe_recommended"
        display_label = "建議先探測欄位"
        display_tone = "warning"
        next_action = "apply_defaults_or_probe_schema"
    elif spec.presets or spec.recommended_values:
        profile_id = "bounds_form_ready_with_presets"
        display_label = "可套用推薦界域"
        display_tone = "success"
        next_action = "apply_recommended_values_or_preview_payload"
    else:
        profile_id = "bounds_form_ready"
        display_label = "可設定界域"
        display_tone = "success"
        next_action = "enter_bounds_then_preview_payload"
    return CrawlerAssetBoundFormProfile(
        profile_id=profile_id,
        asset_id=spec.asset_id,
        status=spec.status,
        display_label=display_label,
        display_tone=display_tone,
        next_action=next_action,
        field_count=len(fields),
        required_field_ids=required_field_ids,
        optional_field_ids=optional_field_ids,
        facet_ids=facet_ids,
        groups=spec.groups,
        controls=controls,
        schema_probe_required_count=spec.schema_probe_required_count,
        schema_probe_field_ids=schema_probe_field_ids,
        preset_count=len(spec.presets),
        preset_ids=preset_ids,
        recommended_value_keys=recommended_value_keys,
        warning_codes=spec.warning_codes,
    )


@dataclass(frozen=True)
class CrawlerAssetBoundPayload:
    """使用者填完界域表單後的中立 payload。

    `facet_values` 給 crawler/adapter 使用；`maps_to_values` 保留對既有後端欄位的
    提示，避免 UI 直接知道 `SourceDownloadBounds` 或 provider-specific 欄位細節。
    """

    asset_id: str
    facet_values: dict[str, object] = field(default_factory=dict)
    field_values: dict[str, object] = field(default_factory=dict)
    maps_to_values: dict[str, object] = field(default_factory=dict)
    warning_codes: tuple[str, ...] = ()

    @property
    def summary(self) -> str:
        if not self.facet_values:
            return "no bounds"
        return ", ".join(f"{key}={value}" for key, value in self.facet_values.items())

    def to_dict(self) -> dict[str, object]:
        return {
            "asset_id": self.asset_id,
            "facet_values": self.facet_values,
            "field_values": self.field_values,
            "maps_to_values": self.maps_to_values,
            "warning_codes": list(self.warning_codes),
            "summary": self.summary,
        }


def build_crawler_asset_bound_form_spec(
    asset_id: str,
    bounds_schema: tuple[CrawlerAssetBoundFacet, ...],
    *,
    source: DatasetDiscoverySource | None = None,
) -> CrawlerAssetBoundFormSpec:
    """Expand backend bounds facets into a concrete form specification.

    A source type owns the supported facets; this builder only turns those
    facets into renderable fields and first-click UX helpers.  It should stay
    free of provider-specific download behavior.
    """

    fields: list[CrawlerAssetBoundFormField] = []
    for facet in bounds_schema:
        fields.extend(fields_for_facet(facet))
    groups = tuple(dict.fromkeys(field.group for field in fields))
    schema_probe_required_count = sum(1 for field in fields if field.requires_schema_probe)
    recommended_values = recommended_form_values(tuple(fields), source=source)
    presets = bound_form_presets(tuple(fields), source=source)
    warnings: list[str] = []
    if schema_probe_required_count:
        warnings.append("schema_probe_recommended")
    if presets:
        warnings.append("preset_available")
    return CrawlerAssetBoundFormSpec(
        asset_id=asset_id,
        status="ready" if fields else "empty",
        fields=tuple(fields),
        schema_probe_required_count=schema_probe_required_count,
        groups=groups,
        warning_codes=tuple(warnings),
        recommended_values=recommended_values,
        presets=presets,
        guidance_zh_TW=bound_form_guidance(tuple(fields), source=source),
        guidance_en="Start with recommended values or a region preset, then preview the payload before building a plan.",
    )


def recommended_form_values(
    fields: tuple[CrawlerAssetBoundFormField, ...],
    *,
    source: DatasetDiscoverySource | None = None,
) -> dict[str, object]:
    """Build safe first-click defaults without guessing unavailable schema values.

    The recommendation layer is intentionally separate from field defaults:
    defaults are backend contract values, while recommendations are UX helpers
    that a UI may apply on demand.
    """

    field_ids = {field.field_id for field in fields}
    values: dict[str, object] = {}
    if "limit" in field_ids:
        values["limit"] = bounded_positive_int(getattr(source, "max_results", 0), fallback=25, upper=25)
    if "max_results" in field_ids:
        values["max_results"] = bounded_positive_int(getattr(source, "max_results", 0), fallback=25, upper=50)
    if "max_pages" in field_ids:
        values["max_pages"] = 1
    if "version_limit" in field_ids:
        values["version_limit"] = 1
    if source is None:
        return values
    if "search_terms" in field_ids and source.search_terms:
        values["search_terms"] = ", ".join(source.search_terms)
    if "file_pattern" in field_ids and source.file_url_regex:
        values["file_pattern"] = source.file_url_regex
    if source.dataset_id:
        for field_id in ("dataset", "collection", "package"):
            if field_id in field_ids:
                values[field_id] = source.dataset_id
    if "format" in field_ids and source.native_format:
        values["format"] = source.native_format.lower()
    return values


def bound_form_presets(
    fields: tuple[CrawlerAssetBoundFormField, ...],
    *,
    source: DatasetDiscoverySource | None = None,
) -> tuple[CrawlerAssetBoundPreset, ...]:
    """Return applicable presets for a form without changing field defaults."""

    field_ids = {field.field_id for field in fields}
    presets: list[CrawlerAssetBoundPreset] = []
    if {"bbox_west", "bbox_south", "bbox_east", "bbox_north"}.issubset(field_ids):
        presets.extend(region_bbox_presets(source))
    return tuple(presets)


def region_bbox_presets(source: DatasetDiscoverySource | None = None) -> tuple[CrawlerAssetBoundPreset, ...]:
    """Rank coarse bbox presets from source hints while keeping the list short."""

    scope = " ".join(
        str(part or "").lower()
        for part in (
            getattr(source, "geographic_scope", ""),
            " ".join(getattr(source, "categories", ()) or ()),
            getattr(source, "name", ""),
        )
    )
    ranked: list[tuple[int, dict[str, object]]] = []
    for index, preset in enumerate(BBOX_REGION_PRESETS):
        score = -index
        if any(token and token in scope for token in preset["scope_tokens"]):  # type: ignore[index]
            score += 100
        ranked.append((score, preset))
    ranked.sort(key=lambda item: item[0], reverse=True)
    # 保留少量常用 preset，避免 UI 又變成另一種選擇壓力。
    return tuple(
        CrawlerAssetBoundPreset(
            preset_id=str(preset["preset_id"]),
            label_zh_TW=str(preset["label_zh_TW"]),
            label_en=str(preset["label_en"]),
            description_zh_TW=str(preset["description_zh_TW"]),
            description_en=str(preset["description_en"]),
            values=preset["values"],  # type: ignore[arg-type]
            tone=str(preset["tone"]),
        )
        for _, preset in ranked[:4]
    )


def bound_form_guidance(
    fields: tuple[CrawlerAssetBoundFormField, ...],
    *,
    source: DatasetDiscoverySource | None = None,
) -> str:
    if not fields:
        return "這個入口目前沒有需要使用者輸入的界域。"
    if any(field.requires_schema_probe for field in fields):
        return "先套用推薦值或常用區域，再用預覽確認 payload；需要欄位清單的項目後續會接 schema/head probe。"
    return "先套用推薦值，再預覽 payload；確認後再建立下載計畫。"


def bounded_positive_int(value: object, *, fallback: int, upper: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    if parsed <= 0:
        return fallback
    return min(parsed, upper)


def fields_for_facet(facet: CrawlerAssetBoundFacet) -> tuple[CrawlerAssetBoundFormField, ...]:
    """Translate one logical facet into one or more visible form fields.

    Composite facets are expanded here: ``time`` becomes time field/start/end,
    and ``bbox`` becomes west/south/east/north.  This keeps UI code from knowing
    which backend facet is single-field versus multi-field.
    """

    base = {
        "facet_id": facet.facet_id,
        "group": facet.group,
        "required": facet.required,
        "maps_to": facet.maps_to,
        "requires_schema_probe": facet.requires_schema_probe,
    }
    if facet.control == "datetime_range":
        return (
            CrawlerAssetBoundFormField(
                field_id="time_field",
                label_zh_TW="時間欄位",
                label_en="Time field",
                control="text",
                value_type="column_name",
                help_zh_TW="若資料集有時間序列，先填入時間欄位名稱；之後可由 schema probe 自動提供選單。",
                help_en="Enter the time column name; later schema probes can turn this into a selector.",
                **base,
            ),
            CrawlerAssetBoundFormField(
                field_id="start_date",
                label_zh_TW="起始時間",
                label_en="Start time",
                control="datetime",
                value_type="datetime",
                help_zh_TW=facet.help_zh_TW,
                help_en=facet.help_en,
                **base,
            ),
            CrawlerAssetBoundFormField(
                field_id="end_date",
                label_zh_TW="結束時間",
                label_en="End time",
                control="datetime",
                value_type="datetime",
                help_zh_TW=facet.help_zh_TW,
                help_en=facet.help_en,
                **base,
            ),
        )
    if facet.control == "bbox":
        labels = (
            ("bbox_west", "西界 / 最小經度", "West / min longitude"),
            ("bbox_south", "南界 / 最小緯度", "South / min latitude"),
            ("bbox_east", "東界 / 最大經度", "East / max longitude"),
            ("bbox_north", "北界 / 最大緯度", "North / max latitude"),
        )
        return tuple(
            CrawlerAssetBoundFormField(
                field_id=field_id,
                label_zh_TW=label_zh,
                label_en=label_en,
                control="number",
                value_type="number",
                help_zh_TW=facet.help_zh_TW,
                help_en=facet.help_en,
                **base,
            )
            for field_id, label_zh, label_en in labels
        )
    control = "text"
    if facet.control in {"integer", "number", "multiselect", "credential_profile"}:
        control = facet.control
    elif facet.control == "text_list":
        control = "text_list"
    elif facet.control == "select_or_text":
        control = "select_or_text" if facet.options else "text"
    return (
        CrawlerAssetBoundFormField(
            field_id=facet.facet_id,
            label_zh_TW=facet.label_zh_TW,
            label_en=facet.label_en,
            control=control,
            value_type=facet.value_type,
            default=facet.default,
            options=facet.options,
            help_zh_TW=facet.help_zh_TW,
            help_en=facet.help_en,
            **base,
        ),
    )


def crawler_asset_bound_payload_from_form_values(
    spec: CrawlerAssetBoundFormSpec,
    values: Mapping[str, object],
) -> CrawlerAssetBoundPayload:
    """Normalize raw UI values into the backend-facing bounds payload.

    The output keeps both the original field values and facet-level values.  That
    dual shape is deliberate: display code can show what the user typed, while
    planner/downloader code can consume the normalized facet contract.
    """

    field_values: dict[str, object] = {}
    for field in spec.fields:
        field_values[field.field_id] = normalize_field_value(field, values.get(field.field_id))

    facet_values: dict[str, object] = {}
    if any(field in field_values and field_values[field] not in ("", None) for field in ("time_field", "start_date", "end_date")):
        facet_values["time"] = {
            "time_field": field_values.get("time_field", ""),
            "start_date": field_values.get("start_date", ""),
            "end_date": field_values.get("end_date", ""),
        }
    bbox = bbox_from_values(field_values)
    if bbox is not None:
        facet_values["bbox"] = bbox
    for field in spec.fields:
        if field.facet_id in {"time", "bbox"}:
            continue
        value = field_values.get(field.field_id)
        if value not in ("", None, (), []):
            facet_values[field.facet_id] = value

    maps_to_values = build_maps_to_values(spec.fields, field_values, facet_values)
    return CrawlerAssetBoundPayload(
        asset_id=spec.asset_id,
        facet_values=facet_values,
        field_values=field_values,
        maps_to_values=maps_to_values,
        warning_codes=spec.warning_codes,
    )


def normalize_field_value(field: CrawlerAssetBoundFormField, value: object) -> object:
    text = str(value or "").strip()
    if field.control in {"integer"} or field.value_type == "integer":
        if not text:
            return field.default if field.default not in ("", None) else ""
        return int(text)
    if field.control == "number" or field.value_type == "number":
        if not text:
            return ""
        return float(text)
    if field.control == "text_list" or field.value_type.endswith("_list"):
        if isinstance(value, (list, tuple, set)):
            return tuple(str(item).strip() for item in value if str(item).strip())
        if not text:
            return ()
        return tuple(item.strip() for item in next(csv.reader([text])) if item.strip())
    if field.control == "multiselect":
        if isinstance(value, (list, tuple, set)):
            return tuple(str(item).strip() for item in value if str(item).strip())
        if not text:
            return ()
        return tuple(item.strip() for item in next(csv.reader([text])) if item.strip())
    return text


def bbox_from_values(values: Mapping[str, object]) -> tuple[float, float, float, float] | None:
    keys = ("bbox_west", "bbox_south", "bbox_east", "bbox_north")
    raw_values = [values.get(key) for key in keys]
    if not any(value not in ("", None) for value in raw_values):
        return None
    if not all(value not in ("", None) for value in raw_values):
        raise ValueError("bbox requires west, south, east, and north values")
    return tuple(float(value) for value in raw_values)  # type: ignore[return-value]


def build_maps_to_values(
    fields: tuple[CrawlerAssetBoundFormField, ...],
    field_values: Mapping[str, object],
    facet_values: Mapping[str, object],
) -> dict[str, object]:
    maps: dict[str, object] = {}
    for field in fields:
        value = field_values.get(field.field_id)
        if field.facet_id == "bbox" and "bbox" in facet_values:
            for target in field.maps_to:
                if target.endswith(".bbox"):
                    maps[target] = facet_values["bbox"]
            continue
        if field.facet_id == "time" and isinstance(facet_values.get("time"), dict):
            time_values = facet_values["time"]
            assert isinstance(time_values, dict)
            for target in field.maps_to:
                suffix = target.rsplit(".", 1)[-1]
                if suffix in time_values and time_values[suffix] not in ("", None):
                    maps[target] = time_values[suffix]
            continue
        if value in ("", None, (), []):
            continue
        for target in field.maps_to:
            maps[target] = value
    return maps


__all__ = [
    "CrawlerAssetBoundFormField",
    "CrawlerAssetBoundFormProfile",
    "CrawlerAssetBoundPreset",
    "CrawlerAssetBoundFormSpec",
    "CrawlerAssetBoundPayload",
    "build_crawler_asset_bound_form_spec",
    "bound_form_presets",
    "crawler_asset_bound_form_profile",
    "crawler_asset_bound_payload_from_form_values",
    "fields_for_facet",
    "recommended_form_values",
]
