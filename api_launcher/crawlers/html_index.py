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
from api_launcher.crawlers.pagination import discovery_page_cap
from api_launcher.crawlers.types import DatasetCandidate, DatasetCrawlerOutput, DatasetDiscoverySource
from api_launcher.discovery import extract_links
from api_launcher.models import Dataset


def html_file_index_candidates_from_text(
    source: DatasetDiscoverySource,
    text: str,
    source_url: str,
    limit: int,
) -> list[DatasetCandidate]:
    # HTML index crawler 只接受明確檔案連結；一般 landing page 不在這裡硬猜。
    versions = html_file_index_versions_from_text(source, text, source_url, limit)
    return html_file_index_candidates_from_versions(source, source_url, versions)


def html_file_index_versions_from_text(
    source: DatasetDiscoverySource,
    text: str,
    source_url: str,
    limit: int,
    seen: set[str] | None = None,
) -> list[dict[str, object]]:
    if not source.file_url_regex:
        raise ValueError("HTML file index source missing file_url_regex")
    pattern = re.compile(source.file_url_regex)
    versions: list[dict[str, object]] = []
    seen_links = seen if seen is not None else set()
    for link in extract_links(text, source_url):
        # regex 可比對檔名或完整 URL，支援把 shard/version 從命名規則抓出來。
        filename = Path(urllib.parse.urlparse(link).path).name
        match = pattern.search(filename) or pattern.search(link)
        if not match or link in seen_links:
            continue
        seen_links.add(link)
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
    return versions


def html_file_index_candidates_from_versions(
    source: DatasetDiscoverySource,
    source_url: str,
    versions: list[dict[str, object]],
) -> list[DatasetCandidate]:
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
    max_pages: int = 0,
) -> list[DatasetCandidate] | DatasetCrawlerOutput:
    text, final_url = fetch_text(source.endpoint_url, timeout=timeout)
    if not full_crawl:
        return html_file_index_candidates_from_text(source, text, final_url, limit)

    page_cap = discovery_page_cap(max_pages)
    seen_pages = {final_url}
    seen_files: set[str] = set()
    warnings: list[str] = []
    versions = html_file_index_versions_from_text(source, text, final_url, 0, seen_files)
    page_queue = [
        link
        for link in extract_links(text, final_url)
        if should_follow_html_index_page(final_url, link, source.file_url_regex)
    ]
    for page_url in page_queue:
        if len(seen_pages) >= page_cap:
            break
        if page_url in seen_pages:
            continue
        seen_pages.add(page_url)
        try:
            page_text, page_final_url = fetch_text(page_url, timeout=timeout)
        except Exception as exc:
            warnings.append(
                "index_page_fetch_failed: failed to fetch linked HTML index page "
                f"{page_url}: {type(exc).__name__}: {exc}"
            )
            continue
        versions.extend(html_file_index_versions_from_text(source, page_text, page_final_url, 0, seen_files))
        for link in extract_links(page_text, page_final_url):
            if link in seen_pages or link in page_queue:
                continue
            if should_follow_html_index_page(page_final_url, link, source.file_url_regex):
                page_queue.append(link)
    candidates = html_file_index_candidates_from_versions(source, final_url, versions)
    if warnings:
        return DatasetCrawlerOutput(candidates=tuple(candidates), warnings=tuple(warnings))
    return candidates


def should_follow_html_index_page(base_url: str, link: str, file_url_regex: str) -> bool:
    parsed_base = urllib.parse.urlparse(base_url)
    parsed_link = urllib.parse.urlparse(link)
    if parsed_link.scheme not in ("http", "https") or parsed_link.netloc.lower() != parsed_base.netloc.lower():
        return False
    filename = Path(parsed_link.path).name
    if re.search(file_url_regex, filename) or re.search(file_url_regex, link):
        return False
    suffix = Path(parsed_link.path).suffix.lower()
    return suffix in ("", ".html", ".htm", ".txt")
