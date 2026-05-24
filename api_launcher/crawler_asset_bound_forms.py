from __future__ import annotations

import csv
from dataclasses import dataclass, field
from typing import Mapping

from api_launcher.crawler_asset_bounds import CrawlerAssetBoundFacet


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
    asset_id: str
    status: str
    fields: tuple[CrawlerAssetBoundFormField, ...] = ()
    schema_probe_required_count: int = 0
    groups: tuple[str, ...] = ()
    warning_codes: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        return self.status == "ready"

    def to_dict(self) -> dict[str, object]:
        return {
            "asset_id": self.asset_id,
            "status": self.status,
            "fields": [field.to_dict() for field in self.fields],
            "schema_probe_required_count": self.schema_probe_required_count,
            "groups": list(self.groups),
            "warning_codes": list(self.warning_codes),
        }


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
) -> CrawlerAssetBoundFormSpec:
    fields: list[CrawlerAssetBoundFormField] = []
    for facet in bounds_schema:
        fields.extend(fields_for_facet(facet))
    groups = tuple(dict.fromkeys(field.group for field in fields))
    schema_probe_required_count = sum(1 for field in fields if field.requires_schema_probe)
    warnings: list[str] = []
    if schema_probe_required_count:
        warnings.append("schema_probe_recommended")
    return CrawlerAssetBoundFormSpec(
        asset_id=asset_id,
        status="ready" if fields else "empty",
        fields=tuple(fields),
        schema_probe_required_count=schema_probe_required_count,
        groups=groups,
        warning_codes=tuple(warnings),
    )


def fields_for_facet(facet: CrawlerAssetBoundFacet) -> tuple[CrawlerAssetBoundFormField, ...]:
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
    "CrawlerAssetBoundFormSpec",
    "CrawlerAssetBoundPayload",
    "build_crawler_asset_bound_form_spec",
    "crawler_asset_bound_payload_from_form_values",
    "fields_for_facet",
]
