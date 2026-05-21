from __future__ import annotations

import json
import re
import urllib.parse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from api_launcher.crawlers.dataset_sources import (
    SUPPORTED_DATASET_SOURCE_TYPES,
    DatasetDiscoverySource,
    append_dataset_discovery_source,
)
from api_launcher.discovery import ProviderSeed, append_discovery_seed


DEFAULT_PORTAL_INTAKE_PATH = "docs/DATABASE_PORTAL_INTAKE.zh-TW.md"

# Portal intake 是團隊蒐集入口的 staging，不直接改 catalog，也不下載資料。
PORTAL_TABLE_HEADING = "待整理入口"
PORTAL_TABLE_COLUMNS = (
    "狀態",
    "優先",
    "網站 / 入口",
    "URL",
    "擁有者",
    "入口類型",
    "主題 / 資料類型",
    "地理範圍",
    "授權 / 登入",
    "建議 crawler 類型",
    "填寫人",
    "備註",
)

SUPPORTED_CRAWLER_TYPES = set(SUPPORTED_DATASET_SOURCE_TYPES)

ACTION_LABELS = {
    "provider_seed_draft": "可轉成 provider seed 草稿",
    "dataset_discovery_source_draft": "可轉成 dataset discovery source 草稿",
    "crawler_mapping_needed": "需要判斷或新增 crawler",
    "dataset_candidate_review": "先放入 dataset candidate / adapter review",
    "direct_resource_review": "直接檔案需先檢查大小、授權與格式",
    "integration_backlog": "登入/授權平台，放入 integration backlog",
    "triage_needed": "入口類型待判斷",
    "incomplete": "資料不足，請補欄位",
    "already_handled": "狀態顯示已處理，保留紀錄",
    "ignore_empty": "空白列，忽略",
    "ignore_example": "範例列，忽略",
}


@dataclass(frozen=True)
class PortalIntakeEntry:
    # 每列 Markdown 表格先轉成固定欄位，後續推薦流程才不依賴欄位位置猜測。
    row_number: int
    status: str
    priority: str
    name: str
    url: str
    owner: str
    entry_type: str
    topics: str
    geographic_scope: str
    access: str
    suggested_crawler_type: str
    submitted_by: str
    notes: str

    def to_dict(self) -> dict[str, object]:
        return {
            "row_number": self.row_number,
            "status": self.status,
            "priority": self.priority,
            "name": self.name,
            "url": self.url,
            "owner": self.owner,
            "entry_type": self.entry_type,
            "topics": self.topics,
            "geographic_scope": self.geographic_scope,
            "access": self.access,
            "suggested_crawler_type": self.suggested_crawler_type,
            "submitted_by": self.submitted_by,
            "notes": self.notes,
        }


def build_portal_intake_payload(path: str | Path = DEFAULT_PORTAL_INTAKE_PATH) -> dict[str, object]:
    # payload 是 review JSON，不是正式 catalog；必須保留 warnings 讓人類審核。
    path = Path(path)
    entries, parse_warnings = load_portal_intake_entries(path)
    recommendations = [recommend_entry(entry) for entry in entries]
    action_counts = Counter(str(item["recommended_action"]) for item in recommendations)
    warning_count = len(parse_warnings) + sum(len(item.get("warnings", [])) for item in recommendations)
    ignored_count = sum(1 for item in recommendations if str(item["recommended_action"]).startswith("ignore_"))
    actionable_count = len(recommendations) - ignored_count
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "role": "team portal intake review; metadata only; no secrets and no downloads",
        "source_path": str(path),
        "summary": {
            "row_count": len(entries),
            "actionable_count": actionable_count,
            "ignored_count": ignored_count,
            "warning_count": warning_count,
            "actions": dict(sorted(action_counts.items())),
        },
        "parse_warnings": parse_warnings,
        "entries": recommendations,
    }


def load_portal_intake_entries(path: str | Path) -> tuple[list[PortalIntakeEntry], list[str]]:
    # 解析失敗回傳 warnings 而不是丟例外，讓 CLI/UI 能顯示哪一列需要修正。
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    table_lines, warnings = extract_markdown_table(lines, PORTAL_TABLE_HEADING)
    if not table_lines:
        warnings.append(f"Could not find a Markdown table under heading: {PORTAL_TABLE_HEADING}")
        return [], warnings
    header = split_markdown_table_row(table_lines[0])
    if tuple(header) != PORTAL_TABLE_COLUMNS:
        warnings.append(f"Unexpected intake table header: {header}")
    entries: list[PortalIntakeEntry] = []
    for offset, line in enumerate(table_lines[2:], start=3):
        cells = split_markdown_table_row(line)
        if not cells:
            continue
        if len(cells) != len(PORTAL_TABLE_COLUMNS):
            warnings.append(f"Row {offset} has {len(cells)} cells; expected {len(PORTAL_TABLE_COLUMNS)}")
            continue
        entries.append(entry_from_cells(offset, cells))
    return entries, warnings


def extract_markdown_table(lines: list[str], heading: str) -> tuple[list[str], list[str]]:
    # 只讀指定 heading 底下第一張表，避免同文件其他範例表格被誤當 intake。
    warnings: list[str] = []
    in_section = False
    table: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            title = stripped.lstrip("#").strip()
            if in_section and title != heading:
                break
            in_section = title == heading
            continue
        if not in_section:
            continue
        if stripped.startswith("|"):
            table.append(stripped)
        elif table:
            break
    if table and len(table) < 2:
        warnings.append(f"Table under {heading} is missing a separator row")
    return table, warnings


def split_markdown_table_row(line: str) -> list[str]:
    line = line.strip()
    if not line.startswith("|"):
        return []
    if line.endswith("|"):
        line = line[1:-1]
    else:
        line = line[1:]
    return [normalize_cell(cell) for cell in line.split("|")]


def normalize_cell(value: str) -> str:
    value = value.strip()
    if value.startswith("`") and value.endswith("`") and len(value) >= 2:
        value = value[1:-1].strip()
    value = value.replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ")
    return re.sub(r"\s+", " ", value).strip()


def entry_from_cells(row_number: int, cells: list[str]) -> PortalIntakeEntry:
    return PortalIntakeEntry(
        row_number=row_number,
        status=cells[0],
        priority=cells[1],
        name=cells[2],
        url=cells[3],
        owner=cells[4],
        entry_type=cells[5],
        topics=cells[6],
        geographic_scope=cells[7],
        access=cells[8],
        suggested_crawler_type=cells[9],
        submitted_by=cells[10],
        notes=cells[11],
    )


def recommend_entry(entry: PortalIntakeEntry) -> dict[str, object]:
    # 推薦結果仍是草稿分類；只有 promote 流程會寫入 ignored local config。
    if entry_is_empty_placeholder(entry) or entry_is_example(entry):
        warnings: list[str] = []
    else:
        warnings = entry_warnings(entry)
    action = recommended_action(entry, warnings)
    record: dict[str, object] = {
        **entry.to_dict(),
        "recommended_action": action,
        "action_label": ACTION_LABELS[action],
        "warnings": warnings,
    }
    if action == "provider_seed_draft":
        record["provider_seed_draft"] = provider_seed_draft(entry)
    elif action == "dataset_discovery_source_draft":
        record["dataset_discovery_source_draft"] = dataset_discovery_source_draft(entry)
    return record


def recommended_action(entry: PortalIntakeEntry, warnings: list[str]) -> str:
    # 先處理忽略/不完整狀態，再依入口類型決定 provider、source、candidate 或 integration backlog。
    if entry_is_empty_placeholder(entry):
        return "ignore_empty"
    if entry_is_example(entry):
        return "ignore_example"
    if entry.status.strip().lower() in {"seeded", "crawler_supported", "rejected"}:
        return "already_handled"
    if any(warning.startswith("missing_") for warning in warnings):
        return "incomplete"
    normalized_type = normalize_entry_type(entry.entry_type)
    if normalized_type == "provider_homepage":
        return "provider_seed_draft"
    if normalized_type == "dataset_catalog_api":
        return "dataset_discovery_source_draft" if crawler_is_supported(entry.suggested_crawler_type) else "crawler_mapping_needed"
    if normalized_type == "single_dataset_page":
        return "dataset_candidate_review"
    if normalized_type == "direct_file":
        return "direct_resource_review"
    if normalized_type == "login_platform":
        return "integration_backlog"
    return "triage_needed"


def entry_is_empty_placeholder(entry: PortalIntakeEntry) -> bool:
    return (
        not any(
            (
                entry.name,
                entry.url,
                entry.owner,
                entry.topics,
                entry.geographic_scope,
                entry.access,
                entry.suggested_crawler_type,
                entry.submitted_by,
                entry.notes,
            )
        )
        and normalize_entry_type(entry.entry_type) == "unknown"
    )


def entry_is_example(entry: PortalIntakeEntry) -> bool:
    return "範例" in entry.name or entry.url.startswith("https://example.")


def entry_warnings(entry: PortalIntakeEntry) -> list[str]:
    warnings: list[str] = []
    if not entry.name:
        warnings.append("missing_name")
    if not entry.url:
        warnings.append("missing_url")
    elif not looks_like_url(entry.url):
        warnings.append("url_not_http_or_https")
    if not entry.owner and normalize_entry_type(entry.entry_type) == "provider_homepage":
        warnings.append("missing_owner_for_provider_seed")
    if entry.suggested_crawler_type and not crawler_is_supported(entry.suggested_crawler_type):
        warnings.append(f"unsupported_crawler_type:{entry.suggested_crawler_type}")
    if access_mentions_secret(entry.access) or access_mentions_secret(entry.notes):
        warnings.append("possible_secret_or_private_access_note")
    return warnings


def normalize_entry_type(value: str) -> str:
    compact = value.replace(" ", "").replace("/", "").strip().lower()
    if not compact or "待判斷" in value:
        return "unknown"
    if "資料商" in value or "機構首頁" in value:
        return "provider_homepage"
    if "資料目錄" in value or "catalog" in compact or "api" in compact:
        return "dataset_catalog_api"
    if "單一資料集" in value:
        return "single_dataset_page"
    if "直接檔案" in value or "direct" in compact:
        return "direct_file"
    if "登入" in value or "oauth" in compact or "login" in compact:
        return "login_platform"
    return "unknown"


def crawler_is_supported(value: str) -> bool:
    return value.strip() in SUPPORTED_CRAWLER_TYPES


def looks_like_url(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def access_mentions_secret(value: str) -> bool:
    lowered = value.lower()
    secret_terms = ("api key:", "token:", "cookie:", "password:", "secret:")
    return any(term in lowered for term in secret_terms)


def provider_seed_draft(entry: PortalIntakeEntry) -> dict[str, object]:
    provider_id = stable_id(entry.url, entry.name)
    return {
        "provider_id": provider_id,
        "name": entry.name,
        "owner": entry.owner or entry.name,
        "categories": topic_list(entry.topics),
        "geographic_scope": entry.geographic_scope or "global",
        "homepage_url": entry.url,
        "docs_url": "",
        "api_base_url": "",
        "signup_url": "",
        "expected_auth_type": infer_expected_auth_type(entry.access),
    }


def dataset_discovery_source_draft(entry: PortalIntakeEntry) -> dict[str, object]:
    provider_id = stable_id(entry.url, entry.owner or entry.name)
    crawler_type = entry.suggested_crawler_type.strip()
    return {
        "source_id": f"{provider_id}_{crawler_type}",
        "provider_id": provider_id,
        "name": entry.name,
        "source_type": crawler_type,
        "endpoint_url": entry.url,
        "docs_url": "",
        "search_terms": topic_list(entry.topics)[:6],
        "categories": topic_list(entry.topics),
        "geographic_scope": entry.geographic_scope or "global",
        "max_results": 10,
        "min_expected_candidates": 1,
        "notes": "Drafted from docs/DATABASE_PORTAL_INTAKE.zh-TW.md; review provider_id/source_id before committing.",
    }


def stable_id(url: str, fallback: str) -> str:
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower().split("@")[-1].split(":")[0]
    if domain.startswith("www."):
        domain = domain[4:]
    candidate = domain or fallback
    candidate = candidate.replace(".", "_").replace("-", "_")
    candidate = re.sub(r"[^0-9a-zA-Z_]+", "_", candidate.lower())
    candidate = re.sub(r"_+", "_", candidate).strip("_")
    if not candidate:
        candidate = "portal"
    if candidate[0].isdigit():
        candidate = f"portal_{candidate}"
    return candidate


def topic_list(value: str) -> list[str]:
    parts = re.split(r"[,，、/]+", value)
    return [normalize_topic(part) for part in parts if normalize_topic(part)]


def normalize_topic(value: str) -> str:
    value = value.strip().lower().replace(" ", "_")
    return re.sub(r"_+", "_", value).strip("_")


def infer_expected_auth_type(access: str) -> str:
    value = access.lower()
    if not value:
        return "unknown"
    if any(term in value for term in ("不需要", "public", "公開", "no_key", "no key")):
        return "no_key_for_public_data"
    if "oauth" in value or "google" in value or "登入" in value:
        return "oauth_or_account_required"
    if "api key" in value.lower() or "token" in value.lower() or "key" in value.lower():
        return "api_key_required"
    return "unknown"


def portal_intake_payload_to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def promote_portal_intake_payload(
    payload: dict[str, Any],
    provider_seed_path: str | Path,
    dataset_source_path: str | Path,
) -> dict[str, object]:
    provider_seed_path = Path(provider_seed_path)
    dataset_source_path = Path(dataset_source_path)
    provider_seed_count = 0
    dataset_source_count = 0
    skipped: list[dict[str, object]] = []
    promoted_provider_ids: set[str] = set()

    if payload.get("parse_warnings"):
        return {
            "provider_seed_count": 0,
            "dataset_source_count": 0,
            "skipped_count": len(payload.get("entries", [])),
            "provider_seed_path": str(provider_seed_path),
            "dataset_source_path": str(dataset_source_path),
            "skipped": [
                {
                    "row_number": entry.get("row_number"),
                    "name": entry.get("name"),
                    "reason": "parse_warnings_present",
                }
                for entry in payload.get("entries", [])
            ],
        }

    for entry in payload.get("entries", []):
        action = str(entry.get("recommended_action") or "")
        if entry.get("warnings"):
            skipped.append(skipped_entry(entry, "warnings_present"))
            continue
        if action == "provider_seed_draft":
            seed = provider_seed_from_draft(entry.get("provider_seed_draft") or {})
            append_discovery_seed(provider_seed_path, seed)
            provider_seed_count += 1
            promoted_provider_ids.add(seed.provider_id)
        elif action == "dataset_discovery_source_draft":
            source = dataset_source_from_draft(entry.get("dataset_discovery_source_draft") or {})
            append_dataset_discovery_source(dataset_source_path, source)
            dataset_source_count += 1
            if source.provider_id not in promoted_provider_ids:
                append_discovery_seed(provider_seed_path, provider_seed_for_dataset_source_entry(entry, source))
                provider_seed_count += 1
                promoted_provider_ids.add(source.provider_id)
        else:
            skipped.append(skipped_entry(entry, f"not_promotable:{action}"))

    return {
        "provider_seed_count": provider_seed_count,
        "dataset_source_count": dataset_source_count,
        "skipped_count": len(skipped),
        "provider_seed_path": str(provider_seed_path),
        "dataset_source_path": str(dataset_source_path),
        "skipped": skipped,
    }


def skipped_entry(entry: dict[str, Any], reason: str) -> dict[str, object]:
    return {
        "row_number": entry.get("row_number"),
        "name": entry.get("name"),
        "recommended_action": entry.get("recommended_action"),
        "reason": reason,
    }


def provider_seed_from_draft(draft: object) -> ProviderSeed:
    if not isinstance(draft, dict):
        raise ValueError("provider_seed_draft must be an object")
    return ProviderSeed(
        provider_id=str(draft["provider_id"]).strip(),
        name=str(draft["name"]).strip(),
        owner=str(draft["owner"]).strip(),
        categories=tuple(str(value).strip() for value in draft.get("categories", []) if str(value).strip()),
        geographic_scope=str(draft.get("geographic_scope") or "global").strip(),
        homepage_url=str(draft["homepage_url"]).strip(),
        docs_url=str(draft.get("docs_url") or "").strip(),
        api_base_url=str(draft.get("api_base_url") or "").strip(),
        signup_url=str(draft.get("signup_url") or "").strip(),
        expected_auth_type=str(draft.get("expected_auth_type") or "unknown").strip(),
    )


def dataset_source_from_draft(draft: object) -> DatasetDiscoverySource:
    if not isinstance(draft, dict):
        raise ValueError("dataset_discovery_source_draft must be an object")
    return DatasetDiscoverySource(
        source_id=str(draft["source_id"]).strip(),
        provider_id=str(draft["provider_id"]).strip(),
        name=str(draft["name"]).strip(),
        source_type=str(draft["source_type"]).strip(),
        endpoint_url=str(draft["endpoint_url"]).strip(),
        docs_url=str(draft.get("docs_url") or "").strip(),
        search_terms=tuple(str(value).strip() for value in draft.get("search_terms", []) if str(value).strip()),
        categories=tuple(str(value).strip() for value in draft.get("categories", []) if str(value).strip()),
        geographic_scope=str(draft.get("geographic_scope") or "global").strip(),
        max_results=int(draft.get("max_results") or 10),
        dataset_id=str(draft.get("dataset_id") or "").strip(),
        dataset_title=str(draft.get("dataset_title") or "").strip(),
        data_type=str(draft.get("data_type") or "").strip(),
        native_format=str(draft.get("native_format") or "").strip(),
        file_url_regex=str(draft.get("file_url_regex") or "").strip(),
        min_expected_candidates=int(draft.get("min_expected_candidates") or 1),
        notes=str(draft.get("notes") or "").strip(),
    )


def provider_seed_for_dataset_source_entry(entry: dict[str, Any], source: DatasetDiscoverySource) -> ProviderSeed:
    url = str(entry.get("url") or source.endpoint_url)
    parsed = urllib.parse.urlparse(url)
    homepage_url = f"{parsed.scheme}://{parsed.netloc}/" if parsed.scheme and parsed.netloc else url
    return ProviderSeed(
        provider_id=source.provider_id,
        name=str(entry.get("owner") or entry.get("name") or source.name).strip(),
        owner=str(entry.get("owner") or entry.get("name") or source.name).strip(),
        categories=tuple(source.categories or ("custom",)),
        geographic_scope=source.geographic_scope,
        homepage_url=homepage_url,
        docs_url="",
        api_base_url=source.endpoint_url,
        signup_url="",
        expected_auth_type=infer_expected_auth_type(str(entry.get("access") or "")),
    )
