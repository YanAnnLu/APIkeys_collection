from __future__ import annotations

from api_launcher.crawlers.types import DatasetCandidate


MAX_FULL_CRAWL_PAGES = 1000


def discovery_page_cap(max_pages: int) -> int:
    # 即使使用者要求 full crawl，也要有全域上限，避免 crawler 對公開 API 無限翻頁。
    if max_pages > 0:
        return min(max_pages, MAX_FULL_CRAWL_PAGES)
    return MAX_FULL_CRAWL_PAGES


def append_new_candidates(candidates: list[DatasetCandidate], page_candidates: list[DatasetCandidate], seen: set[str]) -> int:
    # 用 dataset_uid 去重，讓跨頁重複結果不會讓 provider 看起來有假增長。
    added = 0
    for candidate in page_candidates:
        key = candidate.dataset.dataset_uid
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)
        added += 1
    return added
