from __future__ import annotations

import re
import urllib.parse
from pathlib import Path

from api_launcher.adapters.base import dataset_uid
from api_launcher.crawlers.fetch import fetch_text
from api_launcher.crawlers.metadata import (
    analysis_hint_for_family,
    infer_data_family,
    safe_dataset_id,
    sql_role_for_family,
    storage_hint_for_family,
    viewer_hint_for_family,
)
from api_launcher.crawlers.types import DatasetCandidate, DatasetDiscoverySource
from api_launcher.discovery import extract_links
from api_launcher.models import Dataset


def html_file_index_candidates_from_text(
    source: DatasetDiscoverySource,
    text: str,
    source_url: str,
    limit: int,
) -> list[DatasetCandidate]:
    # HTML index crawler 只接受明確檔案連結；一般 landing page 不在這裡硬猜。
    if not source.file_url_regex:
        raise ValueError("HTML file index source missing file_url_regex")
    pattern = re.compile(source.file_url_regex)
    versions: list[dict[str, object]] = []
    seen: set[str] = set()
    for link in extract_links(text, source_url):
        # regex 可比對檔名或完整 URL，支援把 shard/version 從命名規則抓出來。
        filename = Path(urllib.parse.urlparse(link).path).name
        match = pattern.search(filename) or pattern.search(link)
        if not match or link in seen:
            continue
        seen.add(link)
        version = match.groupdict().get("version") if match.groupdict() else ""
        versions.append(
            {
                "label": filename,
                "version": version or filename,
                "version_status": "discovered_file_shard",
                "download_url": link,
                "landing_url": source.docs_url or source_url,
                "update_strategy": "append_or_partition_by_discovered_shard",
                "notes": "Discovered from an HTML file index; review size and scope before bulk download.",
            }
        )
        if limit > 0 and len(versions) >= limit:
            break
    if not versions:
        return []
    # HTML index 通常代表「同一資料集的多個檔案 shard」，所以輸出單一 Dataset + available_versions。
    dataset_id = safe_dataset_id(source.dataset_id or source.source_id)
    data_family = infer_data_family(" ".join((source.dataset_title, source.data_type, " ".join(source.categories))))
    dataset = Dataset(
        dataset_uid=dataset_uid(source.provider_id, dataset_id),
        provider_id=source.provider_id,
        dataset_id=dataset_id,
        title=source.dataset_title or source.name,
        categories=source.categories or ("discovered",),
        data_type=source.data_type or data_family,
        native_format=source.native_format,
        geographic_scope=source.geographic_scope,
        landing_url=source.docs_url or source_url,
        api_url=str(versions[0]["download_url"]),
        version=str(versions[0]["version"]),
        metadata={
            "candidate_status": "needs_review",
            "discovery_source_id": source.source_id,
            "discovery_source_type": source.source_type,
            "source_url": source_url,
            "provider_backed": True,
            "data_family": data_family,
            "storage_hint": storage_hint_for_family(data_family),
            "sql_role": sql_role_for_family(data_family),
            "analysis_hint": analysis_hint_for_family(data_family),
            "viewer_hint": viewer_hint_for_family(data_family),
            "available_versions": versions,
            "chunking_hint": "file_shard_index",
            "notes": source.notes,
        },
    )
    return [
        DatasetCandidate(
            dataset=dataset,
            source_id=source.source_id,
            source_type=source.source_type,
            source_url=source_url,
            confidence=0.8,
            evidence=(f"matched {len(versions)} file links",),
        )
    ]


def html_file_index_candidates_for_source(
    source: DatasetDiscoverySource,
    timeout: float,
    limit: int,
    full_crawl: bool,
) -> list[DatasetCandidate]:
    # full_crawl 時 limit=0 代表收集同頁所有匹配檔案，仍不追外部分頁。
    text, final_url = fetch_text(source.endpoint_url, timeout=timeout)
    return html_file_index_candidates_from_text(source, text, final_url, 0 if full_crawl else limit)
