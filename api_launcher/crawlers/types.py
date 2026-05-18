from __future__ import annotations

from dataclasses import dataclass, replace

from api_launcher.models import Dataset


@dataclass(frozen=True)
class DatasetDiscoverySource:
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
    notes: str = ""


@dataclass(frozen=True)
class DatasetCandidate:
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


def dataset_with_candidate_metadata(candidate: DatasetCandidate) -> Dataset:
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
