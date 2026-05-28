from __future__ import annotations

import urllib.parse
from typing import Any

from api_launcher.adapters.base import dataset_uid
from api_launcher.crawlers.fetch import fetch_json, search_endpoint_url
from api_launcher.crawlers.metadata import (
    analysis_hint_for_family,
    infer_data_family,
    merge_categories,
    safe_dataset_id,
    sql_role_for_family,
    storage_hint_for_family,
    viewer_hint_for_family,
)
from api_launcher.crawlers.pagination import append_new_candidates, discovery_page_cap, polite_crawl_delay
from api_launcher.crawlers.registry import crawler
from api_launcher.crawlers.types import DatasetCandidate, DatasetCrawlerOutput, DatasetDiscoverySource
from api_launcher.models import Dataset


OPENALEX_SELECT_FIELDS = ",".join(
    (
        "id",
        "doi",
        "display_name",
        "type",
        "publication_year",
        "publication_date",
        "updated_date",
        "primary_location",
        "open_access",
        "cited_by_count",
        "authorships",
        "concepts",
        "keywords",
    )
)


def openalex_works_search_url(
    endpoint_url: str,
    search_term: str,
    limit: int,
    cursor: str | None = None,
) -> str:
    # OpenAlex work 是研究 metadata，不代表直接資料檔；後續需透過 DOI/DataCite 找 contentUrl。
    params = {
        "filter": "type:dataset",
        "search": search_term,
        "per-page": str(max(1, limit)),
        "select": OPENALEX_SELECT_FIELDS,
    }
    if cursor is not None:
        params["cursor"] = cursor
    return search_endpoint_url(endpoint_url, params)


def openalex_payload_items(payload: dict[str, Any]) -> list[Any]:
    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError("OpenAlex works payload missing results list")
    return results


def openalex_candidates_from_payload(
    source: DatasetDiscoverySource,
    payload: dict[str, Any],
    source_url: str,
    limit: int,
) -> list[DatasetCandidate]:
    # OpenAlex candidate 保留 DOI/host venue 線索，讓 adapter review 能追到 repository data。
    items = openalex_payload_items(payload)
    candidates: list[DatasetCandidate] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        openalex_id = str(item.get("id") or "").strip()
        doi = str(item.get("doi") or "").strip()
        dataset_id = safe_dataset_id(openalex_doi_suffix(doi) or openalex_id.rsplit("/", 1)[-1] or item.get("display_name") or "dataset")
        title = str(item.get("display_name") or dataset_id).strip()
        concepts = openalex_names(item.get("concepts"), ("display_name", "name"))[:12]
        keywords = openalex_names(item.get("keywords"), ("display_name", "keyword", "name"))[:12]
        authors, institutions = openalex_authorship_names(item.get("authorships"))
        primary_location = item.get("primary_location") if isinstance(item.get("primary_location"), dict) else {}
        source_meta = primary_location.get("source") if isinstance(primary_location.get("source"), dict) else {}
        searchable = " ".join(
            (
                title,
                " ".join(concepts),
                " ".join(keywords),
                " ".join(source.categories),
                str(item.get("type") or ""),
                str(source_meta.get("display_name") or ""),
            )
        )
        data_family = infer_data_family(searchable)
        landing_url = first_openalex_text(
            primary_location.get("landing_page_url"),
            primary_location.get("pdf_url"),
            doi,
            openalex_id,
            source.docs_url,
            source_url,
        )
        dataset = Dataset(
            dataset_uid=dataset_uid(source.provider_id, dataset_id),
            provider_id=source.provider_id,
            dataset_id=dataset_id,
            title=title,
            categories=merge_categories(source.categories, concepts[:6], keywords[:6], (str(item.get("type") or ""),)),
            data_type=data_family,
            native_format="openalex_work",
            geographic_scope=source.geographic_scope,
            landing_url=landing_url,
            api_url=openalex_work_api_url(source.endpoint_url, openalex_id) or source_url,
            version=str(item.get("updated_date") or item.get("publication_date") or item.get("publication_year") or "discovered"),
            remote_updated_at=str(item.get("updated_date") or ""),
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
                "openalex_id": openalex_id,
                "doi": doi,
                "work_type": item.get("type") or "",
                "publication_year": item.get("publication_year") or "",
                "publication_date": item.get("publication_date") or "",
                "cited_by_count": item.get("cited_by_count") or 0,
                "open_access": item.get("open_access") or {},
                "primary_location": primary_location,
                "source_display_name": source_meta.get("display_name") or "",
                "authors": authors[:12],
                "institutions": institutions[:12],
                "concepts": concepts,
                "keywords": keywords,
                "notes": source.notes,
            },
        )
        candidates.append(
            DatasetCandidate(
                dataset=dataset,
                source_id=source.source_id,
                source_type=source.source_type,
                source_url=source_url,
                confidence=0.78,
                evidence=("OpenAlex Works metadata", f"id: {openalex_id or 'unknown'}"),
            )
        )
    return candidates


def paginated_openalex_candidates(
    source: DatasetDiscoverySource,
    search_term: str,
    timeout: float,
    page_size: int,
    max_pages: int,
) -> list[DatasetCandidate]:
    return list(paginated_openalex_output(source, search_term, timeout, page_size, max_pages).candidates)


def paginated_openalex_output(
    source: DatasetDiscoverySource,
    search_term: str,
    timeout: float,
    page_size: int,
    max_pages: int,
) -> DatasetCrawlerOutput:
    candidates: list[DatasetCandidate] = []
    seen: set[str] = set()
    cursor = "*"
    next_url = openalex_works_search_url(source.endpoint_url, search_term, page_size, cursor=cursor)
    remote_exhausted: bool | None = None
    remote_next_page_token = ""
    for _page in range(discovery_page_cap(max_pages)):
        payload = fetch_json(next_url, timeout=timeout)
        items = openalex_payload_items(payload)
        page_candidates = openalex_candidates_from_payload(source, payload, next_url, page_size)
        added = append_new_candidates(candidates, page_candidates, seen)
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        next_cursor = str(meta.get("next_cursor") or "")
        if not items:
            remote_exhausted = True
            break
        if len(items) < page_size:
            remote_exhausted = True
            break
        if added == 0:
            remote_exhausted = None
            break
        if not next_cursor:
            remote_exhausted = True
            break
        polite_crawl_delay(source.crawl_rate_limit_seconds)
        next_url = openalex_works_search_url(source.endpoint_url, search_term, page_size, cursor=next_cursor)
    else:
        remote_exhausted = False
        remote_next_page_token = next_cursor
    status = "exhausted" if remote_exhausted is True else "has_more" if remote_exhausted is False else "not_reported"
    return DatasetCrawlerOutput(
        candidates=tuple(candidates),
        remote_pagination_status=status,
        remote_exhausted=remote_exhausted,
        remote_next_page_token=remote_next_page_token,
    )


@crawler(
    source_type="openalex_works_search",
    source_family="catalog_search",
    transport="json",
    auth_profile="none",
    result_shape="dataset_list",
    supports_full_crawl=True,
)
def openalex_candidates_for_source(
    source: DatasetDiscoverySource,
    timeout: float,
    limit: int,
    search_terms: tuple[str, ...],
    full_crawl: bool,
    max_pages: int,
) -> DatasetCrawlerOutput:
    candidates: list[DatasetCandidate] = []
    remote_exhausted: bool | None = None
    remote_next_page_token = ""
    for term in search_terms or ("",):
        if full_crawl:
            output = paginated_openalex_output(source, term, timeout, limit, max_pages)
            candidates.extend(output.candidates)
            if output.remote_exhausted is False:
                remote_exhausted = False
                remote_next_page_token = output.remote_next_page_token
            elif output.remote_exhausted is True and remote_exhausted is not False:
                remote_exhausted = True
            elif remote_exhausted is not False:
                remote_exhausted = None
            continue
        url = openalex_works_search_url(source.endpoint_url, term, limit)
        payload = fetch_json(url, timeout=timeout)
        candidates.extend(openalex_candidates_from_payload(source, payload, url, limit))
    status = "exhausted" if remote_exhausted is True else "has_more" if remote_exhausted is False else "not_reported"
    return DatasetCrawlerOutput(
        candidates=tuple(candidates),
        remote_pagination_status=status,
        remote_exhausted=remote_exhausted,
        remote_next_page_token=remote_next_page_token,
    )


def openalex_names(value: object, keys: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    names: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        name = first_openalex_text(*(item.get(key) for key in keys))
        if name and name not in seen:
            names.append(name)
            seen.add(name)
    return tuple(names)


def openalex_authorship_names(value: object) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not isinstance(value, list):
        return (), ()
    authors: list[str] = []
    institutions: list[str] = []
    seen_authors: set[str] = set()
    seen_institutions: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        author = item.get("author") if isinstance(item.get("author"), dict) else {}
        author_name = first_openalex_text(author.get("display_name"), author.get("id"))
        if author_name and author_name not in seen_authors:
            authors.append(author_name)
            seen_authors.add(author_name)
        for institution_name in openalex_names(item.get("institutions"), ("display_name", "id")):
            if institution_name not in seen_institutions:
                institutions.append(institution_name)
                seen_institutions.add(institution_name)
    return tuple(authors), tuple(institutions)


def openalex_work_api_url(endpoint_url: str, openalex_id: str) -> str:
    work_id = openalex_id.rstrip("/").rsplit("/", 1)[-1].strip()
    if not work_id:
        return ""
    parsed = urllib.parse.urlparse(endpoint_url)
    if parsed.scheme and parsed.netloc:
        return urllib.parse.urlunparse(parsed._replace(path=f"/works/{urllib.parse.quote(work_id, safe='')}", query="", fragment=""))
    return f"https://api.openalex.org/works/{urllib.parse.quote(work_id, safe='')}"


def openalex_doi_suffix(doi: str) -> str:
    parsed = urllib.parse.urlparse(doi)
    if parsed.netloc.lower() in {"doi.org", "dx.doi.org"}:
        return urllib.parse.unquote(parsed.path.lstrip("/"))
    return doi


def first_openalex_text(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""
