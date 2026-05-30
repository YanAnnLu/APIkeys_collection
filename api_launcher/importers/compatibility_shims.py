from __future__ import annotations

import ast
import json
import math
import re
from dataclasses import dataclass
from collections.abc import Mapping, Sequence


PANDAS_UNNAMED_HEADER_RE = re.compile(r"^Unnamed:\s*\d+(?:_level_\d+)?$", re.IGNORECASE)


@dataclass(frozen=True)
class ImporterCompatibilityShimProfile:
    shim_id: str
    stage: str
    applies_to: tuple[str, ...]
    normalizes: tuple[str, ...]
    boundary: str
    runtime_scope: str

    def to_dict(self) -> dict[str, object]:
        return {
            "shim_id": self.shim_id,
            "stage": self.stage,
            "applies_to": list(self.applies_to),
            "normalizes": list(self.normalizes),
            "boundary": self.boundary,
            "runtime_scope": self.runtime_scope,
        }


IMPORTER_COMPATIBILITY_SHIMS: tuple[ImporterCompatibilityShimProfile, ...] = (
    ImporterCompatibilityShimProfile(
        shim_id="external_table_shape_normalizer",
        stage="before_sqlite_import",
        applies_to=("csv_to_sqlite", "json_to_sqlite"),
        normalizes=(
            "tuple_or_list_header_labels",
            "pandas_multiindex_repr_headers",
            "pandas_unnamed_level_headers",
            "dict_list_tuple_cell_values",
            "none_and_nan_cell_values",
        ),
        boundary="api_launcher.importers",
        runtime_scope="scoped_importer_boundary",
    ),
)


def iter_importer_compatibility_shims() -> tuple[ImporterCompatibilityShimProfile, ...]:
    return IMPORTER_COMPATIBILITY_SHIMS


def importer_compatibility_shim_report() -> dict[str, object]:
    shims = iter_importer_compatibility_shims()
    return {
        "shim_count": len(shims),
        "runtime_scope": "scoped_importer_boundary",
        "global_monkeypatch": False,
        "shims": [shim.to_dict() for shim in shims],
    }


def normalize_external_header_label(value: object) -> str:
    """Flatten external table labels before SQL identifier normalization.

    This is the scoped, importer-side version of the "hijack" pattern: external
    libraries may expose tuple/list labels, pandas MultiIndex labels, or string
    reprs of those labels.  We normalize only this boundary value and do not
    patch pandas, print, imports, or process-wide state.
    """

    parsed = _literal_sequence(value)
    label = parsed if parsed is not None else value
    parts = tuple(_label_parts(label))
    return " ".join(parts)


def normalize_external_cell_value(value: object) -> str:
    if value is None or _is_nan(value):
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (Mapping, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _literal_sequence(value: object) -> object | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text[0] not in "([" or text[-1:] not in ")]":
        return None
    try:
        parsed = ast.literal_eval(text)
    except (SyntaxError, ValueError):
        return None
    if isinstance(parsed, (tuple, list)):
        return parsed
    return None


def _label_parts(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        text = value.strip()
        if not text or PANDAS_UNNAMED_HEADER_RE.match(text):
            return ()
        return (text,)
    if value is None or _is_nan(value):
        return ()
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        parts: list[str] = []
        for item in value:
            parts.extend(_label_parts(item))
        return tuple(parts)
    text = str(value).strip()
    if not text or PANDAS_UNNAMED_HEADER_RE.match(text):
        return ()
    return (text,)


def _is_nan(value: object) -> bool:
    return isinstance(value, float) and math.isnan(value)
