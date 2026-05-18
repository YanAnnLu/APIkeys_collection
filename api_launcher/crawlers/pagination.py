from __future__ import annotations

from api_launcher.crawlers.types import DatasetCandidate


MAX_FULL_CRAWL_PAGES = 1000


def discovery_page_cap(max_pages: int) -> int:
    if max_pages > 0:
        return min(max_pages, MAX_FULL_CRAWL_PAGES)
    return MAX_FULL_CRAWL_PAGES


def append_new_candidates(candidates: list[DatasetCandidate], page_candidates: list[DatasetCandidate], seen: set[str]) -> int:
    added = 0
    for candidate in page_candidates:
        key = candidate.dataset.dataset_uid
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)
        added += 1
    return added
