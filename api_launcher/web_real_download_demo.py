from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from api_launcher.dataset_versions import DatasetVersionOption
from api_launcher.db import connect_db, utc_now_iso
from api_launcher.ingestion_pipeline import DownloadImportPipelineOptions, DownloadImportPipelineRun, run_download_import_slice
from api_launcher.models import Dataset, Provider
from api_launcher.paths import state_file
from api_launcher.plans import build_dataset_download_plan, provider_dataset_version_plan_entry
from api_launcher.repository import ApiCatalogRepository


WEB_REAL_DEMO_PROVIDER_ID = "web_demo_public_csv"
WEB_REAL_DEMO_DATASET_ID = "country_list"
WEB_REAL_DEMO_TABLE = "web_demo_country_list"
WEB_REAL_DEMO_URL = "https://raw.githubusercontent.com/datasets/country-list/master/data.csv"
WEB_REAL_DEMO_RETIREMENT_TRIGGER = "remove_after_crawler_asset_download_import_path_is_connected"

PipelineRunner = Callable[[dict[str, object], ApiCatalogRepository, DownloadImportPipelineOptions], DownloadImportPipelineRun]


@dataclass(frozen=True)
class WebRealDownloadDemoResult:
    plan_path: Path
    launcher_db_path: Path
    downloads_root: Path
    import_sqlite_path: Path
    target_path: Path
    manifest_path: Path
    table_name: str
    row_count: int
    run: DownloadImportPipelineRun

    def to_dict(self) -> dict[str, object]:
        return {
            "demo_id": "web_real_download_public_csv",
            "source_url": WEB_REAL_DEMO_URL,
            "stage": self.run.stage,
            "succeeded": self.run.succeeded and self.row_count > 0,
            "row_count": self.row_count,
            "table_name": self.table_name,
            "artifacts": {
                "plan": str(self.plan_path),
                "launcher_db": str(self.launcher_db_path),
                "downloads_root": str(self.downloads_root),
                "downloaded_file": str(self.target_path),
                "manifest": str(self.manifest_path),
                "curated_sqlite": str(self.import_sqlite_path),
            },
            "download_import": self.run.to_dict(),
            "next_action": self.run.next_action or "open_downloaded_file_or_review_sqlite_import",
        }


def run_web_real_download_demo(
    *,
    runner: PipelineRunner = run_download_import_slice,
    root: str | Path | None = None,
) -> WebRealDownloadDemoResult:
    """Run a small real HTTP download/import proof for the Web Preview.

    This is intentionally a narrow proof path: it reuses the production
    download/import pipeline, writes all runtime artifacts under ignored
    ``state/web_demo/``, and avoids pretending that every crawler asset is
    already a direct-download source.

    This endpoint is temporary scaffolding for explaining and verifying the
    browser-driven download/import UX.  Once crawler assets can complete the
    same flow from source selection, bounds, plan build, download, and import,
    remove this from the primary UI instead of promoting it as a product mode.
    """

    demo_root = Path(root) if root is not None else state_file("web_demo")
    demo_root.mkdir(parents=True, exist_ok=True)
    downloads_root = demo_root / "downloads"
    launcher_db_path = demo_root / "web_real_download.sqlite"
    import_sqlite_path = demo_root / "web_real_download_curated.sqlite"
    plan_path = demo_root / "web_real_download_plan.json"
    version = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    plan_payload = build_web_real_download_plan(downloads_root=downloads_root, version=version)
    plan_path.write_text(json.dumps(plan_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    with closing(connect_db(launcher_db_path)) as conn:
        repository = ApiCatalogRepository(conn)
        repository.init_schema()
        provider, dataset = web_real_download_provider_dataset(version)
        repository.upsert_provider(provider)
        repository.upsert_dataset(dataset)
        run = runner(
            plan_payload,
            repository,
            DownloadImportPipelineOptions(
                timeout=30.0,
                import_supported_results=True,
                import_sqlite_path=import_sqlite_path,
                import_row_limit=0,
                import_replace=True,
                import_existing_table_policy="replace",
            ),
        )
        conn.commit()

    entry = plan_payload["providers"][0]
    target_path = Path(str(entry["target_path"]))
    manifest_path = target_path.with_suffix(target_path.suffix + ".manifest.json")
    row_count = sqlite_table_row_count(import_sqlite_path, WEB_REAL_DEMO_TABLE)
    return WebRealDownloadDemoResult(
        plan_path=plan_path,
        launcher_db_path=launcher_db_path,
        downloads_root=downloads_root,
        import_sqlite_path=import_sqlite_path,
        target_path=target_path,
        manifest_path=manifest_path,
        table_name=WEB_REAL_DEMO_TABLE,
        row_count=row_count,
        run=run,
    )


def build_web_real_download_plan(*, downloads_root: str | Path, version: str) -> dict[str, object]:
    provider, dataset = web_real_download_provider_dataset(version)
    option = DatasetVersionOption(
        dataset_uid=dataset.dataset_uid,
        dataset_id=dataset.dataset_id,
        label="Public country list CSV",
        version=version,
        status="web_demo_real_download",
        download_url=WEB_REAL_DEMO_URL,
        landing_url="https://github.com/datasets/country-list",
        update_strategy="replace_demo_snapshot",
        notes="Small public CSV used to prove Web Preview can trigger a real download/import pipeline run.",
        metadata=dict(dataset.metadata),
    )
    entry = provider_dataset_version_plan_entry(provider, dataset, option, downloads_root=downloads_root)
    entry["import_plan"] = {
        **dict(entry.get("import_plan") if isinstance(entry.get("import_plan"), dict) else {}),
        "table_hint": WEB_REAL_DEMO_TABLE,
    }
    payload = build_dataset_download_plan([entry], plan_name="web_preview_real_public_csv_download")
    payload["source"] = {
        "kind": "web_preview_real_download_demo",
        "created_at": utc_now_iso(),
        "truth_boundary": "real HTTP download plus manifest and SQLite import; not a crawler coverage claim",
        "retirement_trigger": WEB_REAL_DEMO_RETIREMENT_TRIGGER,
    }
    return payload


def web_real_download_provider_dataset(version: str) -> tuple[Provider, Dataset]:
    provider = Provider(
        provider_id=WEB_REAL_DEMO_PROVIDER_ID,
        name="Web Demo Public CSV",
        owner="datasets GitHub organization",
        categories=("demo", "public_csv", "web_preview"),
        geographic_scope="global",
        docs_url="https://github.com/datasets/country-list",
        api_base_url=WEB_REAL_DEMO_URL,
        signup_url="",
        auth_type="none",
        notes="Small public CSV source for proving a real browser-triggered download/import path.",
    )
    dataset = Dataset(
        dataset_uid=f"{WEB_REAL_DEMO_PROVIDER_ID}:{WEB_REAL_DEMO_DATASET_ID}:{version}",
        provider_id=provider.provider_id,
        dataset_id=WEB_REAL_DEMO_DATASET_ID,
        title="Country list public CSV",
        categories=("demo", "public_csv"),
        data_type="table_sample",
        native_format="csv",
        geographic_scope="global",
        landing_url="https://github.com/datasets/country-list",
        api_url=WEB_REAL_DEMO_URL,
        version=version,
        metadata={
            "data_family": "table_sample",
            "native_format": "csv",
            "download_url": WEB_REAL_DEMO_URL,
            "source_url": WEB_REAL_DEMO_URL,
            "demo_scope": "web_preview_real_download",
        },
    )
    return provider, dataset


def sqlite_table_row_count(sqlite_path: str | Path, table_name: str) -> int:
    path = Path(sqlite_path)
    if not path.exists():
        return 0
    with closing(sqlite3.connect(path)) as conn:
        try:
            row = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()
        except sqlite3.Error:
            return 0
    return int(row[0]) if row else 0


__all__ = [
    "WEB_REAL_DEMO_URL",
    "WebRealDownloadDemoResult",
    "build_web_real_download_plan",
    "run_web_real_download_demo",
]
