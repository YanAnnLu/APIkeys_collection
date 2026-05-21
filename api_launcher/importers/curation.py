from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class CleaningIssue:
    # 清洗問題保留 severity/field/message，讓 CLI、UI、agent 可以用同一份結果呈現。
    severity: str
    field: str
    message: str


@dataclass(frozen=True)
class CleaningResult:
    rows: list[dict[str, Any]]
    issues: list[CleaningIssue] = field(default_factory=list)


@dataclass(frozen=True)
class FieldRule:
    # FieldRule 是 raw -> curated 的最小規格；目前先支援欄位改名、必填、預設值與型別轉換。
    source: str
    target: str
    required: bool = False
    default: Any = None
    cast: str = "str"


@dataclass(frozen=True)
class CleaningSpec:
    # dedupe_keys 只在清洗後的欄位上運作，避免來源欄位命名差異讓去重規則失效。
    name: str
    fields: tuple[FieldRule, ...]
    dedupe_keys: tuple[str, ...] = ()


def clean_records(records: Iterable[dict[str, Any]], spec: CleaningSpec) -> CleaningResult:
    # 這裡不丟棄整批資料：單列錯誤會變成 issue，讓匯入流程可以回報哪些列被跳過。
    clean_rows: list[dict[str, Any]] = []
    issues: list[CleaningIssue] = []
    seen: set[tuple[Any, ...]] = set()
    for index, record in enumerate(records):
        output: dict[str, Any] = {}
        skip = False
        for rule in spec.fields:
            # 空值與缺欄位統一在這裡處理，adapter 不需要各自重寫必填欄位規則。
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
                # 型別轉換失敗代表這列不可信；保留錯誤並跳過，避免髒資料進 curated table。
                issues.append(CleaningIssue("error", rule.target, f"row {index}: {exc}"))
                skip = True
                break
        if skip:
            continue
        if spec.dedupe_keys:
            # 去重發生在 clean output 上，確保欄位已被正規化且型別也已轉換。
            key = tuple(output.get(name) for name in spec.dedupe_keys)
            if key in seen:
                issues.append(CleaningIssue("warning", ",".join(spec.dedupe_keys), f"row {index}: duplicate skipped"))
                continue
            seen.add(key)
        clean_rows.append(output)
    return CleaningResult(clean_rows, issues)


def cast_value(value: Any, cast: str) -> Any:
    # cast 名稱保持簡單字串，方便之後把 CleaningSpec 寫進 JSON/YAML 或 adapter metadata。
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
    # 只有 None 與空白字串視為空；0、False 仍是有效值，不能被必填檢查誤殺。
    return value is None or (isinstance(value, str) and not value.strip())
