from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class CleaningIssue:
    severity: str
    field: str
    message: str


@dataclass(frozen=True)
class CleaningResult:
    rows: list[dict[str, Any]]
    issues: list[CleaningIssue] = field(default_factory=list)


@dataclass(frozen=True)
class FieldRule:
    source: str
    target: str
    required: bool = False
    default: Any = None
    cast: str = "str"


@dataclass(frozen=True)
class CleaningSpec:
    name: str
    fields: tuple[FieldRule, ...]
    dedupe_keys: tuple[str, ...] = ()


def clean_records(records: Iterable[dict[str, Any]], spec: CleaningSpec) -> CleaningResult:
    clean_rows: list[dict[str, Any]] = []
    issues: list[CleaningIssue] = []
    seen: set[tuple[Any, ...]] = set()
    for index, record in enumerate(records):
        output: dict[str, Any] = {}
        skip = False
        for rule in spec.fields:
            raw = record.get(rule.source, rule.default)
            if _is_empty(raw):
                if rule.required:
                    issues.append(CleaningIssue("error", rule.target, f"row {index}: missing required value"))
                    skip = True
                    break
                raw = rule.default
            try:
                output[rule.target] = cast_value(raw, rule.cast)
            except ValueError as exc:
                issues.append(CleaningIssue("error", rule.target, f"row {index}: {exc}"))
                skip = True
                break
        if skip:
            continue
        if spec.dedupe_keys:
            key = tuple(output.get(name) for name in spec.dedupe_keys)
            if key in seen:
                issues.append(CleaningIssue("warning", ",".join(spec.dedupe_keys), f"row {index}: duplicate skipped"))
                continue
            seen.add(key)
        clean_rows.append(output)
    return CleaningResult(clean_rows, issues)


def cast_value(value: Any, cast: str) -> Any:
    if value is None:
        return None
    if cast == "str":
        return str(value).strip()
    if cast == "int":
        return int(value)
    if cast == "float":
        return float(value)
    if cast == "bool":
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "y"}:
            return True
        if text in {"0", "false", "no", "n"}:
            return False
        raise ValueError(f"cannot cast {value!r} to bool")
    return value


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())
