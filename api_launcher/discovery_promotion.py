from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from api_launcher.crawlers.dataset_sources import (
    DatasetDiscoverySource,
    append_dataset_discovery_source,
    load_dataset_discovery_sources,
)
from api_launcher.crawlers.orchestrator import DatasetCrawlOptions, DatasetCrawlResult, crawl_dataset_sources
from api_launcher.discovery import (
    ProviderSeed,
    auth_type_requires_secret,
    key_env_var,
    load_discovery_seeds,
    provider_to_dict,
)
from api_launcher.models import Provider
from api_launcher.registry import load_provider_catalog


@dataclass(frozen=True)
class LocalDiscoveryPromotionResult:
    # promotion result 區分 promoted/skipped，讓本機草稿進 catalog 前有可審計紀錄。
    audited_source_count: int
    promoted_provider_count: int
    promoted_source_count: int
    skipped_count: int
    provider_catalog_path: str
    dataset_source_catalog_path: str
    audit: dict[str, object]
    promoted_providers: tuple[str, ...] = ()
    promoted_sources: tuple[str, ...] = ()
    skipped: tuple[dict[str, object], ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "audited_source_count": self.audited_source_count,
            "promoted_provider_count": self.promoted_provider_count,
            "promoted_source_count": self.promoted_source_count,
            "skipped_count": self.skipped_count,
            "provider_catalog_path": self.provider_catalog_path,
            "dataset_source_catalog_path": self.dataset_source_catalog_path,
            "promoted_providers": list(self.promoted_providers),
            "promoted_sources": list(self.promoted_sources),
            "skipped": list(self.skipped),
            "audit": self.audit,
        }


def promote_local_discovery_catalog(
    local_provider_seed_path: str | Path,
    local_dataset_source_path: str | Path,
    provider_catalog_path: str | Path,
    dataset_source_catalog_path: str | Path,
    options: DatasetCrawlOptions | None = None,
    source_ids: set[str] | None = None,
    dry_run: bool = False,
) -> LocalDiscoveryPromotionResult:
    # promotion 只把通過 audit 的 local staging 推進官方 catalog；dry-run 仍應產生完整摘要。
    local_provider_seed_path = Path(local_provider_seed_path)
    local_dataset_source_path = Path(local_dataset_source_path)
    provider_catalog_path = Path(provider_catalog_path)
    dataset_source_catalog_path = Path(dataset_source_catalog_path)
    options = options or DatasetCrawlOptions()

    local_sources = load_dataset_discovery_sources(local_dataset_source_path) if local_dataset_source_path.exists() else []
    if source_ids:
        local_sources = [source for source in local_sources if source.source_id in source_ids]
    crawl_result = crawl_dataset_sources(local_sources, options) if local_sources else DatasetCrawlResult(candidates=(), source_results=())
    audit_payload = crawl_result_to_audit_payload(crawl_result)

    local_provider_seeds = {
        seed.provider_id: seed
        for seed in (load_discovery_seeds(local_provider_seed_path) if local_provider_seed_path.exists() else [])
    }
    official_providers = {provider.provider_id: provider for provider in load_provider_catalog(provider_catalog_path)}
    official_sources = {
        source.source_id: source
        for source in (load_dataset_discovery_sources(dataset_source_catalog_path) if dataset_source_catalog_path.exists() else [])
    }
    source_by_id = {source.source_id: source for source in local_sources}

    promoted_providers: list[str] = []
    promoted_sources: list[str] = []
    skipped: list[dict[str, object]] = []
    for source_result in crawl_result.source_results:
        source = source_by_id[source_result.source_id]
        if source_result.audit_status != "pass":
            skipped.append(
                {
                    "source_id": source.source_id,
                    "provider_id": source.provider_id,
                    "reason": f"audit_{source_result.audit_status}",
                    "error": source_result.error,
                    "warnings": list(source_result.warnings),
                }
            )
            continue
        if source.source_id in official_sources:
            skipped.append(
                {
                    "source_id": source.source_id,
                    "provider_id": source.provider_id,
                    "reason": "source_already_in_official_catalog",
                }
            )
            continue
        provider_is_official = source.provider_id in official_providers
        provider_seed = local_provider_seeds.get(source.provider_id)
        if not provider_is_official and provider_seed is None:
            skipped.append(
                {
                    "source_id": source.source_id,
                    "provider_id": source.provider_id,
                    "reason": "missing_official_provider_and_local_seed",
                }
            )
            continue
        if not provider_is_official and provider_seed is not None:
            if not dry_run:
                append_provider_to_catalog(provider_catalog_path, provider_from_seed(provider_seed))
            official_providers[source.provider_id] = provider_from_seed(provider_seed)
            promoted_providers.append(source.provider_id)
        if not dry_run:
            append_dataset_discovery_source(dataset_source_catalog_path, source)
        promoted_sources.append(source.source_id)

    return LocalDiscoveryPromotionResult(
        audited_source_count=len(local_sources),
        promoted_provider_count=len(promoted_providers),
        promoted_source_count=len(promoted_sources),
        skipped_count=len(skipped),
        provider_catalog_path=str(provider_catalog_path),
        dataset_source_catalog_path=str(dataset_source_catalog_path),
        audit=audit_payload,
        promoted_providers=tuple(promoted_providers),
        promoted_sources=tuple(promoted_sources),
        skipped=tuple(skipped),
    )


def append_provider_to_catalog(path: str | Path, provider: Provider) -> None:
    path = Path(path)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = []
    items = [item for item in data if item.get("provider_id") != provider.provider_id]
    items.append(provider_to_dict(provider))
    items.sort(key=lambda item: item["provider_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def provider_from_seed(seed: ProviderSeed) -> Provider:
    auth_type = seed.expected_auth_type or "unknown"
    return Provider(
        provider_id=seed.provider_id,
        name=seed.name,
        owner=seed.owner,
        categories=seed.categories or ("custom",),
        geographic_scope=seed.geographic_scope or "global",
        docs_url=seed.docs_url or seed.homepage_url,
        api_base_url=seed.api_base_url,
        signup_url=seed.signup_url,
        auth_type=auth_type,
        key_env_var=key_env_var(seed.provider_id) if auth_type_requires_secret(auth_type) else "",
        notes="Promoted from local portal/discovery intake after dataset crawler audit.",
    )


def crawl_result_to_audit_payload(result: DatasetCrawlResult) -> dict[str, object]:
    return {
        "candidate_count": result.candidate_count,
        "duplicate_count": result.duplicate_count,
        "error_count": result.error_count,
        "warning_count": result.warning_count,
        "audit_issue_count": result.audit_issue_count,
        "sources": [
            {
                "source_id": source.source_id,
                "provider_id": source.provider_id,
                "source_type": source.source_type,
                "candidate_count": source.candidate_count,
                "unique_candidate_count": source.unique_candidate_count,
                "duplicate_candidate_count": source.duplicate_candidate_count,
                "audit_status": source.audit_status,
                "error": source.error,
                "warnings": list(source.warnings),
            }
            for source in result.source_results
        ],
    }
