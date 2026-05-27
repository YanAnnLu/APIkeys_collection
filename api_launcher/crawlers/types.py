from __future__ import annotations

from dataclasses import dataclass, replace

from api_launcher.models import Dataset


@dataclass(frozen=True)
class DatasetDiscoverySource:
    # source 是 crawler 的設定單位，不是單一 dataset；一個 source 可以產出多筆 candidate。
    source_id: str
    provider_id: str
    name: str
    source_type: str
    endpoint_url: str
    docs_url: str = ""
    search_terms: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    geographic_scope: str = "global"
    max_results: int = 10
    dataset_id: str = ""
    dataset_title: str = ""
    data_type: str = ""
    native_format: str = ""
    file_url_regex: str = ""
    min_expected_candidates: int = 1
    seed_discovery_mode: str = "auto"
    notes: str = ""


@dataclass(frozen=True)
class DatasetCandidate:
    # candidate 保留 evidence 與 confidence，讓後續 plan/export 仍能追溯 crawler 判斷。
    dataset: Dataset
    source_id: str
    source_type: str
    source_url: str
    confidence: float
    evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "dataset": dataset_to_dict(self.dataset),
        }


@dataclass(frozen=True)
class DatasetCrawlerOutput:
    """可選的 richer crawler 回傳值。

    只知道 candidates 的舊 handler 可以繼續回傳 list。知道遠端是否還有
    下一頁的 handler 應回傳這個物件，讓 UI shell 能呈現完整度而不用靠
    本機上限猜測。
    """

    candidates: tuple[DatasetCandidate, ...] = ()
    remote_pagination_status: str = "not_reported"
    remote_exhausted: bool | None = None
    remote_next_page_token: str = ""


def dataset_with_candidate_metadata(candidate: DatasetCandidate) -> Dataset:
    # 把 crawler 脈絡塞回 Dataset.metadata，讓 UI/adapter plan 不需要額外攜帶 candidate 物件。
    metadata = dict(candidate.dataset.metadata)
    metadata["confidence"] = candidate.confidence
    metadata["evidence"] = list(candidate.evidence)
    metadata["source_url"] = candidate.source_url
    metadata["discovery_source_id"] = candidate.source_id
    metadata["discovery_source_type"] = candidate.source_type
    return replace(candidate.dataset, metadata=metadata)


def dataset_to_dict(dataset: Dataset) -> dict[str, object]:
    return {
        "dataset_uid": dataset.dataset_uid,
        "provider_id": dataset.provider_id,
        "dataset_id": dataset.dataset_id,
        "title": dataset.title,
        "categories": list(dataset.categories),
        "data_type": dataset.data_type,
        "native_format": dataset.native_format,
        "geographic_scope": dataset.geographic_scope,
        "temporal_coverage": dataset.temporal_coverage,
        "landing_url": dataset.landing_url,
        "api_url": dataset.api_url,
        "license_url": dataset.license_url,
        "version": dataset.version,
        "remote_updated_at": dataset.remote_updated_at,
        "remote_etag": dataset.remote_etag,
        "remote_hash": dataset.remote_hash,
        "metadata": dataset.metadata,
    }
