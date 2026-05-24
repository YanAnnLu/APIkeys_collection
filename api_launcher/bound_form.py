from __future__ import annotations

import csv
from dataclasses import dataclass, field
from typing import Mapping

from api_launcher.schema_probe import SchemaProbeColumn, SchemaProbeResult
from api_launcher.source_download import SourceDownloadBounds


@dataclass(frozen=True)
class BoundFormOption:
    value: str
    label: str
    inferred_type: str = ""
    sample_value: str = ""
    role_hint: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "value": self.value,
            "label": self.label,
            "inferred_type": self.inferred_type,
            "sample_value": self.sample_value,
            "role_hint": self.role_hint,
        }


@dataclass(frozen=True)
class BoundFormField:
    field_id: str
    label_zh_TW: str
    label_en: str
    control: str
    value_type: str = "text"
    default: object = ""
    required: bool = False
    options: tuple[BoundFormOption, ...] = ()
    depends_on: tuple[str, ...] = ()
    help_zh_TW: str = ""
    help_en: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "field_id": self.field_id,
            "label_zh_TW": self.label_zh_TW,
            "label_en": self.label_en,
            "control": self.control,
            "value_type": self.value_type,
            "default": self.default,
            "required": self.required,
            "options": [option.to_dict() for option in self.options],
            "depends_on": list(self.depends_on),
            "help_zh_TW": self.help_zh_TW,
            "help_en": self.help_en,
        }


@dataclass(frozen=True)
class BoundFormSpec:
    status: str
    source_url: str
    row_count: int = 0
    columns: tuple[SchemaProbeColumn, ...] = ()
    fields: tuple[BoundFormField, ...] = ()
    inferred_roles: dict[str, list[str]] = field(default_factory=dict)
    error: str = ""

    @property
    def succeeded(self) -> bool:
        return self.status == "ok"

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_url": self.source_url,
            "row_count": self.row_count,
            "columns": [column.to_dict() for column in self.columns],
            "fields": [field.to_dict() for field in self.fields],
            "inferred_roles": self.inferred_roles,
            "error": self.error,
        }


def build_bound_form_spec(probe: SchemaProbeResult, *, default_sample_limit: int = 25) -> BoundFormSpec:
    """Build a frontend-neutral form contract from a small schema probe.

    這裡刻意只輸出「表單規格」，不畫 Tk/Qt 元件。Tk Lite、未來 Qt Pro、
    CLI wizard 都應該讀同一份 spec，避免界域規則散落在不同前端。
    """

    if not probe.succeeded:
        return BoundFormSpec(
            status="schema_probe_failed",
            source_url=probe.source_url,
            row_count=probe.row_count,
            columns=probe.columns,
            error=probe.error or "schema probe did not return usable columns",
            fields=(
                sample_limit_field(default_sample_limit),
            ),
        )

    column_options = column_select_options(probe.columns)
    time_options = role_options(probe.columns, "time")
    longitude_options = role_options(probe.columns, "longitude")
    latitude_options = role_options(probe.columns, "latitude")
    fields: list[BoundFormField] = [
        sample_limit_field(default_sample_limit),
        BoundFormField(
            field_id="time_field",
            label_zh_TW="時間欄位",
            label_en="Time field",
            control="select",
            value_type="column_name",
            default=time_options[0].value if time_options else "",
            options=time_options or column_options,
            help_zh_TW="先用 schema probe 推測時間欄位；使用者仍可改選其他欄位。",
            help_en="Schema probe suggests a time field first; users can choose another column.",
        ),
        BoundFormField(
            field_id="start_date",
            label_zh_TW="開始時間",
            label_en="Start time",
            control="datetime",
            value_type="datetime",
            depends_on=("time_field",),
            help_zh_TW="只有選定時間欄位後才會套用到下載查詢。",
            help_en="Applied only when a time field is selected.",
        ),
        BoundFormField(
            field_id="end_date",
            label_zh_TW="結束時間",
            label_en="End time",
            control="datetime",
            value_type="datetime",
            depends_on=("time_field",),
            help_zh_TW="可留空；留空代表不限制結束時間。",
            help_en="Optional; blank means no upper time bound.",
        ),
        BoundFormField(
            field_id="longitude_field",
            label_zh_TW="經度欄位",
            label_en="Longitude field",
            control="select",
            value_type="column_name",
            default=longitude_options[0].value if longitude_options else "",
            options=longitude_options or column_options,
            help_zh_TW="用來判斷 bbox 是否能安全套用；沒有經緯度欄位時不應產生空間界域。",
            help_en="Used to decide whether a bbox can be safely applied.",
        ),
        BoundFormField(
            field_id="latitude_field",
            label_zh_TW="緯度欄位",
            label_en="Latitude field",
            control="select",
            value_type="column_name",
            default=latitude_options[0].value if latitude_options else "",
            options=latitude_options or column_options,
            help_zh_TW="用來判斷 bbox 是否能安全套用；沒有經緯度欄位時不應產生空間界域。",
            help_en="Used to decide whether a bbox can be safely applied.",
        ),
    ]
    fields.extend(bbox_fields())
    fields.append(
        BoundFormField(
            field_id="required_columns",
            label_zh_TW="需要保留的欄位",
            label_en="Required columns",
            control="multiselect",
            value_type="column_names",
            options=column_options,
            help_zh_TW="下載或匯入前用來確認資料集至少包含這些欄位；不代表立刻裁欄。",
            help_en="Used to verify that the dataset contains these columns; not an immediate projection.",
        )
    )
    fields.append(
        BoundFormField(
            field_id="max_bytes",
            label_zh_TW="最大下載位元組數",
            label_en="Max download bytes",
            control="integer",
            value_type="integer",
            default=0,
            help_zh_TW="0 代表不設定；正式大量下載前可用於安全預檢。",
            help_en="0 means unset; useful as a safety review before large downloads.",
        )
    )

    return BoundFormSpec(
        status="ok",
        source_url=probe.source_url,
        row_count=probe.row_count,
        columns=probe.columns,
        fields=tuple(fields),
        inferred_roles={
            "time": [option.value for option in time_options],
            "longitude": [option.value for option in longitude_options],
            "latitude": [option.value for option in latitude_options],
        },
    )


def sample_limit_field(default_sample_limit: int) -> BoundFormField:
    return BoundFormField(
        field_id="sample_limit",
        label_zh_TW="樣本筆數上限",
        label_en="Sample row limit",
        control="integer",
        value_type="integer",
        default=max(1, default_sample_limit),
        required=True,
        help_zh_TW="先用小界線驗證資料形狀；之後可改成較大的下載界線。",
        help_en="Start with a small bound to validate shape, then increase it when needed.",
    )


def bbox_fields() -> list[BoundFormField]:
    labels = {
        "bbox_west": ("西界 / 最小經度", "West / min longitude"),
        "bbox_south": ("南界 / 最小緯度", "South / min latitude"),
        "bbox_east": ("東界 / 最大經度", "East / max longitude"),
        "bbox_north": ("北界 / 最大緯度", "North / max latitude"),
    }
    return [
        BoundFormField(
            field_id=field_id,
            label_zh_TW=label_zh,
            label_en=label_en,
            control="number",
            value_type="number",
            depends_on=("longitude_field", "latitude_field"),
            help_zh_TW="只有經度欄位與緯度欄位都已選定時才套用。",
            help_en="Applied only when both longitude and latitude fields are selected.",
        )
        for field_id, (label_zh, label_en) in labels.items()
    ]


def column_select_options(columns: tuple[SchemaProbeColumn, ...]) -> tuple[BoundFormOption, ...]:
    return tuple(
        BoundFormOption(
            value=column.name,
            label=column_label(column),
            inferred_type=column.inferred_type,
            sample_value=column.sample_value,
            role_hint=column_role_hint(column),
        )
        for column in columns
    )


def role_options(columns: tuple[SchemaProbeColumn, ...], role: str) -> tuple[BoundFormOption, ...]:
    matched = [column for column in columns if column_role_hint(column) == role]
    return column_select_options(tuple(matched))


def column_label(column: SchemaProbeColumn) -> str:
    sample = f" = {column.sample_value}" if column.sample_value else ""
    return f"{column.name} ({column.inferred_type}{sample})"


def column_role_hint(column: SchemaProbeColumn) -> str:
    name = column.name.strip().lower()
    inferred = column.inferred_type
    if inferred in {"date", "datetime"} or any(token in name for token in ("time", "date", "timestamp", "datetime")):
        return "time"
    if name in {"lon", "lng", "long", "longitude", "x"} or "longitude" in name:
        return "longitude"
    if name in {"lat", "latitude", "y"} or "latitude" in name:
        return "latitude"
    return ""


def source_download_bounds_from_form_values(values: Mapping[str, object]) -> SourceDownloadBounds:
    """Convert dynamic form values back into the backend download-bounds contract."""

    bbox = bbox_from_form_values(values)
    return SourceDownloadBounds(
        sample_limit=int_from_form_value(values.get("sample_limit"), default=25),
        start_date=str(values.get("start_date") or "").strip(),
        end_date=str(values.get("end_date") or "").strip(),
        bbox=bbox,
        max_bytes=int_from_form_value(values.get("max_bytes"), default=0),
        required_columns=tuple_from_form_value(values.get("required_columns")),
        time_field=str(values.get("time_field") or "").strip(),
        longitude_field=str(values.get("longitude_field") or "").strip(),
        latitude_field=str(values.get("latitude_field") or "").strip(),
        schema_probe_required=True,
    )


def bbox_from_form_values(values: Mapping[str, object]) -> tuple[float, float, float, float] | None:
    keys = ("bbox_west", "bbox_south", "bbox_east", "bbox_north")
    raw_values = [str(values.get(key) or "").strip() for key in keys]
    if not any(raw_values):
        return None
    if not all(raw_values):
        raise ValueError("bbox requires west, south, east, and north values")
    return tuple(float(value) for value in raw_values)  # type: ignore[return-value]


def int_from_form_value(value: object, *, default: int) -> int:
    text = str(value or "").strip()
    if not text:
        return default
    return int(text)


def tuple_from_form_value(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    text = str(value).strip()
    if not text:
        return ()
    return tuple(item.strip() for item in next(csv.reader([text])) if item.strip())
