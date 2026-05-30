"""Formal crawler asset download/import service.

This module is the production-shaped path behind "download/import this crawler
asset" and "download/import this seed".  It keeps Web/Tk/Qt out of the details:
the UI passes an asset id, optional bounds payload, and destination, then
receives a structured result containing plan, download, import, and artifact
locations.

The boundary is deliberately explicit:

``crawler asset/seed -> resolved download plan -> direct downloads -> import``

Review-only, credential-blocked, or unsupported content paths still return a
result object; they are not silently treated as successful downloads.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from api_launcher.crawler_asset_bound_forms import CrawlerAssetBoundPayload
from api_launcher.crawler_next_action_display import next_action_display_label_or_fallback
from api_launcher.crawler_asset_service import (
    CrawlerAssetDownloadPlanResult,
    build_crawler_asset_download_plan,
    build_crawler_seed_download_plan,
)
from api_launcher.ingestion_pipeline import DownloadImportPipelineOptions, DownloadImportPipelineRun, run_download_import_slice
from api_launcher.repository import ApiCatalogRepository


@dataclass(frozen=True)
class CrawlerAssetDownloadImportResult:
    """Result for the formal crawler-asset download/import lane.

    This is the production-shaped counterpart to the old Web real-download
    demo: the input is a crawler asset plus bounds payload, not a hard-coded
    demo CSV.  UI shells should render this payload instead of reconstructing
    download/import state from the resolved plan.
    """

    asset_id: str
    plan_result: CrawlerAssetDownloadPlanResult
    pipeline: DownloadImportPipelineRun
    downloads_root: Path
    curated_sqlite_path: Path
    plan_path: Path | None = None
    dataset_uid: str = ""

    @property
    def succeeded(self) -> bool:
        return self.pipeline.succeeded

    def to_dict(self) -> dict[str, object]:
        next_action = self.pipeline.next_action or self.plan_result.user_next_action
        artifacts: dict[str, object] = {
            "downloads_root": str(self.downloads_root),
            "curated_sqlite": str(self.curated_sqlite_path),
        }
        if self.plan_path is not None:
            artifacts["plan"] = str(self.plan_path)
        payload = {
            "asset_id": self.asset_id,
            "stage": self.pipeline.stage,
            "succeeded": self.succeeded,
            "outcome_bucket": self.plan_result.outcome_bucket,
            "direct_download_count": self.plan_result.direct_download_count,
            "review_required_count": self.plan_result.review_required_count,
            "plan_result": self.plan_result.to_dict(),
            "download_import": self.pipeline.to_dict(),
            "artifacts": artifacts,
            "next_action": next_action,
            "next_action_label": next_action_display_label_or_fallback(
                next_action,
                fallback="檢查下載 / 匯入結果",
            ),
        }
        if self.dataset_uid:
            payload["dataset_uid"] = self.dataset_uid
        return payload


def run_crawler_asset_download_import(
    asset_id: str,
    repository: ApiCatalogRepository,
    downloads_root: str | Path,
    *,
    bounds_payload: CrawlerAssetBoundPayload | None = None,
    import_sqlite_path: str | Path | None = None,
    plan_path: str | Path | None = None,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
    timeout: float = 30.0,
    max_results: int = 5,
    max_pages: int = 1,
    download_limit: int = 1,
    import_existing_table_policy: str = "rename",
) -> CrawlerAssetDownloadImportResult:
    """Build, run, and optionally import a crawler-asset download plan.

    The service keeps the sequence explicit and testable:

    crawler asset + bounds -> resolved plan -> direct downloads -> import

    Review-only or credential-blocked assets still return a structured
    pipeline result; they are not treated as successful downloads.
    """

    # Destination creation is the only filesystem side effect before the plan is
    # resolved.  Everything after this point flows through the standard download
    # and import pipeline so UI shells do not need their own shortcut path.
    destination = Path(downloads_root).expanduser()
    destination.mkdir(parents=True, exist_ok=True)
    curated_sqlite = Path(import_sqlite_path) if import_sqlite_path is not None else destination / "curated_sources.db"
    plan_result = build_crawler_asset_download_plan(
        asset_id,
        repository.conn,
        bounds_payload=bounds_payload,
        downloads_root=destination,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
        timeout=timeout,
        max_results=max_results,
        max_pages=max_pages,
    )
    resolved_plan = plan_result.resolved_plan
    output_plan_path = Path(plan_path) if plan_path is not None else None
    if output_plan_path is not None:
        output_plan_path.parent.mkdir(parents=True, exist_ok=True)
        output_plan_path.write_text(json.dumps(resolved_plan, ensure_ascii=False, indent=2), encoding="utf-8")
    # The import pipeline is responsible for deciding which downloaded artifacts
    # are actually importable.  This service does not guess content formats.
    pipeline = run_download_import_slice(
        resolved_plan,
        repository,
        DownloadImportPipelineOptions(
            timeout=timeout,
            limit=download_limit,
            import_supported_results=True,
            import_sqlite_path=curated_sqlite,
            import_existing_table_policy=import_existing_table_policy,
        ),
    )
    return CrawlerAssetDownloadImportResult(
        asset_id=asset_id,
        plan_result=plan_result,
        pipeline=pipeline,
        downloads_root=destination,
        curated_sqlite_path=curated_sqlite,
        plan_path=output_plan_path,
    )


def run_crawler_seed_download_import(
    asset_id: str,
    dataset_uid: str,
    repository: ApiCatalogRepository,
    downloads_root: str | Path,
    *,
    bounds_payload: CrawlerAssetBoundPayload | None = None,
    import_sqlite_path: str | Path | None = None,
    plan_path: str | Path | None = None,
    primary_path: str | Path | None = None,
    local_path: str | Path | None = None,
    profile_path: str | Path | None = None,
    timeout: float = 30.0,
    download_limit: int = 1,
    import_existing_table_policy: str = "rename",
) -> CrawlerAssetDownloadImportResult:
    """Build, run, and import a formal plan for one visible seed row.

    The seed must already belong to the selected crawler asset.  This path does
    not rerun live discovery; it turns one catalog seed into a bounded download
    plan and then uses the same import pipeline as the asset-level action.
    """

    destination = Path(downloads_root).expanduser()
    destination.mkdir(parents=True, exist_ok=True)
    curated_sqlite = Path(import_sqlite_path) if import_sqlite_path is not None else destination / "curated_sources.db"
    plan_result = build_crawler_seed_download_plan(
        asset_id,
        dataset_uid,
        repository.conn,
        bounds_payload=bounds_payload,
        downloads_root=destination,
        primary_path=primary_path,
        local_path=local_path,
        profile_path=profile_path,
        timeout=timeout,
    )
    resolved_plan = plan_result.resolved_plan
    output_plan_path = Path(plan_path) if plan_path is not None else None
    if output_plan_path is not None:
        output_plan_path.parent.mkdir(parents=True, exist_ok=True)
        output_plan_path.write_text(json.dumps(resolved_plan, ensure_ascii=False, indent=2), encoding="utf-8")
    pipeline = run_download_import_slice(
        resolved_plan,
        repository,
        DownloadImportPipelineOptions(
            timeout=timeout,
            limit=download_limit,
            import_supported_results=True,
            import_sqlite_path=curated_sqlite,
            import_existing_table_policy=import_existing_table_policy,
        ),
    )
    return CrawlerAssetDownloadImportResult(
        asset_id=asset_id,
        dataset_uid=dataset_uid,
        plan_result=plan_result,
        pipeline=pipeline,
        downloads_root=destination,
        curated_sqlite_path=curated_sqlite,
        plan_path=output_plan_path,
    )


__all__ = [
    "CrawlerAssetDownloadImportResult",
    "run_crawler_asset_download_import",
    "run_crawler_seed_download_import",
]
