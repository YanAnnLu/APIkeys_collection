from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from api_launcher.adapter_plan_resolver import AdapterPlanResolution, resolve_adapter_review_plan_payload
from api_launcher.downloads.jobs import DownloadProgress
from api_launcher.downloads.policy import PoliteDownloadPolicy
from api_launcher.ingestion_pipeline import DownloadImportPipelineOptions, DownloadImportPipelineRun, run_download_import_slice
from api_launcher.mvp_demo import (
    MVP_DEMO_API_VIEW_URL,
    MVP_DEMO_DATASET_ID,
    MVP_DEMO_DATASET_UID,
    MVP_DEMO_FLOW_ID,
    MVP_DEMO_LANDING_URL,
    MVP_DEMO_PROVIDER_ID,
    MVP_DEMO_RESOURCE_URL,
    build_mvp_demo_review_plan,
)
from api_launcher.models import Dataset, Provider
from api_launcher.repository import ApiCatalogRepository


SHOWCASE_DOWNLOAD_DIRNAME = "RuRuKa Asset Launcher Showcase"
SHOWCASE_CURATED_DB_NAME = "curated_showcase.db"
SHOWCASE_RESUMABLE_PLAN_NAME = "showcase_resumable_full_csv.plan.json"
SHOWCASE_RESUMABLE_CSV_NAME = "nyc_311_full_export.csv"
SHOWCASE_FULL_EXPORT_URL = f"https://data.cityofnewyork.us/api/views/{MVP_DEMO_DATASET_ID}/rows.csv?accessType=DOWNLOAD"
SHOWCASE_FALLBACK_PROVIDER_ID = "rawgithub_covid19_countries"
SHOWCASE_FALLBACK_DATASET_ID = "countries_aggregated"
SHOWCASE_FALLBACK_DATASET_UID = f"{SHOWCASE_FALLBACK_PROVIDER_ID}:{SHOWCASE_FALLBACK_DATASET_ID}"
SHOWCASE_FALLBACK_CSV_NAME = "countries-aggregated.csv"
SHOWCASE_FALLBACK_CSV_URL = "https://raw.githubusercontent.com/datasets/covid-19/main/data/countries-aggregated.csv"
SHOWCASE_DEFAULT_SAMPLE_LIMIT = 100
SHOWCASE_MAX_SAMPLE_LIMIT = 50_000
ShowcaseProgressCallback = Callable[[float, str, dict[str, object]], None]


@dataclass(frozen=True)
class ShowcaseDownloadPaths:
    root: Path
    downloads_root: Path
    curated_sqlite: Path
    review_plan: Path
    resolved_plan: Path
    summary_json: Path

    def to_dict(self) -> dict[str, str]:
        return {
            "root": str(self.root),
            "downloads_root": str(self.downloads_root),
            "curated_sqlite": str(self.curated_sqlite),
            "review_plan": str(self.review_plan),
            "resolved_plan": str(self.resolved_plan),
            "summary_json": str(self.summary_json),
        }


@dataclass(frozen=True)
class ShowcaseDownloadRun:
    paths: ShowcaseDownloadPaths
    resolution: AdapterPlanResolution
    pipeline: DownloadImportPipelineRun
    table_counts: dict[str, int]
    sample_limit: int
    used_fallback: bool = False
    primary_error: str = ""

    @property
    def succeeded(self) -> bool:
        return self.pipeline.succeeded and any(count > 0 for count in self.table_counts.values())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "flow_id": MVP_DEMO_FLOW_ID,
            "mode": "showcase_public_socrata_download",
            "succeeded": self.succeeded,
            "sample_limit": self.sample_limit,
            "used_fallback": self.used_fallback,
            "primary_error": self.primary_error,
            "paths": self.paths.to_dict(),
            "adapter_resolution": self.resolution.to_dict(),
            "download_import": self.pipeline.to_dict(),
            "table_counts": dict(self.table_counts),
            "notes_zh_TW": (
                f"展示短路徑會從公開 Socrata demo source 下載使用者指定的有界樣本（目前上限 {self.sample_limit} 筆），"
                "寫出 payload/manifest，並匯入使用者選定資料夾內的 SQLite .db。"
            ),
        }


@dataclass(frozen=True)
class ShowcaseResumablePlan:
    paths: ShowcaseDownloadPaths
    plan_path: Path
    plan_payload: dict[str, object]
    target_path: Path

    @property
    def part_glob_hint(self) -> Path:
        # 專案外下載會把 staging/.part 放在 final 旁邊的 .apikeys_staging 目錄，現場展示時可用這個提示說明續傳邊界。
        return self.paths.downloads_root / "nyc_open_data_socrata" / ".apikeys_staging"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "mode": "showcase_resumable_full_csv_download",
            "paths": self.paths.to_dict(),
            "plan_path": str(self.plan_path),
            "target_path": str(self.target_path),
            "part_glob_hint": str(self.part_glob_hint),
            "download_url": SHOWCASE_FULL_EXPORT_URL,
            "notes_zh_TW": (
                "這是展示暫停/繼續/續傳能力的完整 CSV 匯出下載計畫。"
                "它只把 payload/manifest 寫到使用者選定資料夾，不自動匯入 SQL。"
            ),
        }


def showcase_download_paths(destination_dir: str | Path) -> ShowcaseDownloadPaths:
    # 使用者選資料夾時只選「根目錄」；實際展示輸出集中到子資料夾，避免混進一般 Downloads。
    root = Path(destination_dir).expanduser() / SHOWCASE_DOWNLOAD_DIRNAME
    return ShowcaseDownloadPaths(
        root=root,
        downloads_root=root / "downloads",
        curated_sqlite=root / SHOWCASE_CURATED_DB_NAME,
        review_plan=root / "socrata_311.review.json",
        resolved_plan=root / "socrata_311.resolved.json",
        summary_json=root / "showcase_download_summary.json",
    )


def emit_showcase_progress(
    callback: ShowcaseProgressCallback | None,
    percent: float,
    stage: str,
    **context: object,
) -> None:
    # 展示模式的百分比必須可追溯：這裡只接收已完成階段或 downloader
    # 送出的實際 byte 進度；不在 UI 層憑空捏造下載百分比。
    if callback is None:
        return
    bounded_percent = min(100.0, max(0.0, float(percent)))
    callback(bounded_percent, stage, dict(context))


def showcase_download_flow_percent(update: DownloadProgress, *, fallback_active: bool = False) -> float:
    """Return the honest overall-flow percent for a downloader progress event.

    展示模式的流程百分比有兩層：下載器提供的 byte 百分比，以及整體
    download -> manifest -> import 流程百分比。主來源失敗後若切到 fallback，
    後續下載百分比不得倒退到 fallback 提示之前，否則現場會誤判為重新卡住。
    """

    floor = 37.0 if fallback_active else 35.0
    ceiling = 75.0
    if update.percent is not None:
        byte_percent = min(100.0, max(0.0, update.percent))
        return floor + (byte_percent * ((ceiling - floor) / 100.0))
    if update.bytes_done > 0:
        return max(floor, 42.0)
    return floor


def build_showcase_resumable_download_plan(destination_dir: str | Path) -> ShowcaseResumablePlan:
    # 這條展示線刻意不走 SQL 匯入：它把「來源大型資料庫匯出」短路成使用者 Downloads 內的 CSV 檔，
    # 並交給正式 HTTP queue 下載，讓 Pause/Resume/.part 行為可以在 UI 直接演示。
    paths = showcase_download_paths(destination_dir)
    target_path = paths.downloads_root / MVP_DEMO_PROVIDER_ID / SHOWCASE_RESUMABLE_CSV_NAME
    plan_path = paths.root / SHOWCASE_RESUMABLE_PLAN_NAME
    entry = {
        "provider_id": MVP_DEMO_PROVIDER_ID,
        "name": "NYC Open Data Socrata Catalog",
        "dataset_uid": MVP_DEMO_DATASET_UID,
        "dataset_id": MVP_DEMO_DATASET_ID,
        "dataset_title": "NYC 311 Service Requests full CSV export",
        "source_format": "csv",
        "data_type": "table_full_export",
        "target": "local_file_asset",
        "use_staging": True,
        "landing_url": MVP_DEMO_LANDING_URL,
        "download_url": SHOWCASE_FULL_EXPORT_URL,
        "target_path": str(target_path),
        "download_eligibility": {
            "status": "direct_download",
            "reason": "Showcase full CSV export; uses the normal HTTP queue so Pause/Resume can be demonstrated.",
            "direct_url": SHOWCASE_FULL_EXPORT_URL,
        },
        "dataset_version": {
            "dataset_uid": MVP_DEMO_DATASET_UID,
            "dataset_id": MVP_DEMO_DATASET_ID,
            "label": "Full CSV export for pause/resume showcase",
            "version": "showcase-full-export",
            "version_status": "showcase_resumable_download",
            "download_url": SHOWCASE_FULL_EXPORT_URL,
            "landing_url": MVP_DEMO_LANDING_URL,
            "update_strategy": "full_export_manual_control",
            "notes": "Large public CSV export used to demonstrate pause/resume; import is intentionally not automatic.",
            "metadata": {
                "showcase_mode": "resumable_full_csv_download",
                "flow_id": MVP_DEMO_FLOW_ID,
                "socrata_dataset_id": MVP_DEMO_DATASET_ID,
                "socrata_api_view_url": MVP_DEMO_API_VIEW_URL,
                "import_short_circuit": "local_download_folder_only",
            },
        },
        "import_plan": {
            "status": "manual_review_required",
            "reason": "展示續傳路徑先只下載 CSV 到本機資料夾；中午展示不自動匯入 SQL。",
            "table_hint": "nyc_open_data_socrata_311_full_export",
        },
        "showcase": {
            "kind": "resumable_full_csv_download",
            "purpose_zh_TW": "讓展示者按下下載後，可用既有下載面板操作暫停、繼續、取消、重試與 .part 續傳。",
            "short_circuit_sql": True,
        },
    }
    plan_payload: dict[str, object] = {
        "schema_version": 1,
        "flow_id": MVP_DEMO_FLOW_ID,
        "created_for": "showcase_resumable_download",
        "plan_name": "showcase_resumable_nyc_311_full_csv",
        "role": "large CSV download plan only; import is intentionally manual/review-only",
        "download_policy": {
            "io_model": "nonblocking",
            "supports_pause": True,
            "supports_resume": True,
            "supports_retry": True,
        },
        "summary": {
            "provider_count": 1,
            "dataset_version_count": 1,
            "direct_download_count": 1,
            "review_required_count": 0,
            "status": "planned",
            "sql_short_circuit": "local_folder_only",
        },
        "providers": [entry],
    }
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.downloads_root.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return ShowcaseResumablePlan(paths=paths, plan_path=plan_path, plan_payload=plan_payload, target_path=target_path)


def build_showcase_fallback_csv_plan(paths: ShowcaseDownloadPaths, sample_limit: int) -> dict[str, object]:
    # 展示現場不能只依賴單一遠端 API；當 Socrata live endpoint timeout 時，
    # 改下載另一個公開 CSV，仍走同一套 download -> manifest -> SQLite import 管線。
    target_path = paths.downloads_root / SHOWCASE_FALLBACK_PROVIDER_ID / SHOWCASE_FALLBACK_CSV_NAME
    entry = {
        "provider_id": SHOWCASE_FALLBACK_PROVIDER_ID,
        "name": "Raw GitHub public COVID-19 country time-series CSV",
        "owner": "datasets/covid-19 public dataset",
        "categories": ["showcase", "public_csv", "fallback"],
        "geographic_scope": "global",
        "docs_url": "https://github.com/datasets/covid-19",
        "auth_type": "none",
        "dataset_uid": SHOWCASE_FALLBACK_DATASET_UID,
        "dataset_id": SHOWCASE_FALLBACK_DATASET_ID,
        "dataset_title": "Country-level COVID-19 aggregated public CSV",
        "source_format": "csv",
        "data_type": "public_health_time_series",
        "target": "local_file_asset",
        "use_staging": True,
        "landing_url": "https://github.com/datasets/covid-19",
        "download_url": SHOWCASE_FALLBACK_CSV_URL,
        "target_path": str(target_path),
        "download_eligibility": {
            "status": "direct_download",
            "reason": "Showcase fallback public CSV; used only when the primary Socrata live source times out.",
            "direct_url": SHOWCASE_FALLBACK_CSV_URL,
        },
        "dataset_version": {
            "dataset_uid": SHOWCASE_FALLBACK_DATASET_UID,
            "dataset_id": SHOWCASE_FALLBACK_DATASET_ID,
            "label": "Raw GitHub public CSV fallback",
            "version": "showcase-fallback-rawgithub",
            "version_status": "showcase_fallback_public_csv",
            "download_url": SHOWCASE_FALLBACK_CSV_URL,
            "landing_url": "https://github.com/datasets/covid-19",
            "update_strategy": "showcase_retry_fallback",
            "notes": f"Fallback public CSV imported with GUI-controlled row limit={sample_limit}.",
            "metadata": {
                "native_format": "csv",
                "showcase_mode": "fallback_public_csv",
                "showcase_sample_limit": sample_limit,
                "fallback_for": MVP_DEMO_PROVIDER_ID,
            },
        },
        "import_plan": {
            "target_engine": "sqlite_mvp",
            "source_format": "csv",
            "data_family": "public_health_time_series",
            "table_hint": "rawgithub_covid19_countries_aggregated",
            "post_download": True,
            "status": "supported_after_download",
            "importer": "csv_to_sqlite",
            "reason": "CSV fallback can be imported by the current SQLite MVP importer after download verification.",
        },
        "showcase": {
            "kind": "fallback_public_csv",
            "purpose_zh_TW": "主展示來源逾時時，改用另一個公開 CSV 維持真下載、真 manifest、真 SQLite 匯入。",
            "short_circuit_sql": False,
        },
    }
    return {
        "schema_version": 1,
        "flow_id": MVP_DEMO_FLOW_ID,
        "created_for": "showcase_fallback_public_csv",
        "plan_name": "showcase_fallback_public_csv_download_import",
        "role": "fallback real public CSV download/import plan for time-boxed internal showcase",
        "summary": {
            "status": "fallback_planned",
            "showcase_sample_limit": sample_limit,
            "primary_source": MVP_DEMO_PROVIDER_ID,
            "fallback_source": SHOWCASE_FALLBACK_PROVIDER_ID,
        },
        "providers": [entry],
    }


def run_showcase_download_to_folder(
    destination_dir: str | Path,
    repository: ApiCatalogRepository,
    *,
    policy: PoliteDownloadPolicy | None = None,
    timeout: float = 45.0,
    sample_limit: int = SHOWCASE_DEFAULT_SAMPLE_LIMIT,
    progress_callback: ShowcaseProgressCallback | None = None,
) -> ShowcaseDownloadRun:
    # 這是展示用短路徑，不是完整 crawler 全量下載器。它固定選一個公開、可驗證的資料源，
    # 以證明「選資料夾 -> 下載 -> manifest -> 匯入 .db」的使用者操作閉環。
    bounded_limit = normalize_showcase_sample_limit(sample_limit)
    paths = showcase_download_paths(destination_dir)
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.downloads_root.mkdir(parents=True, exist_ok=True)
    emit_showcase_progress(progress_callback, 5, "prepare_paths", destination=str(paths.root), sample_limit=bounded_limit)

    review_plan = build_mvp_demo_review_plan(downloads_root=paths.downloads_root)
    emit_showcase_progress(progress_callback, 15, "build_review_plan", review_entries=len(review_plan.get("providers", [])))
    resolved_plan, resolution = resolve_adapter_review_plan_payload(
        review_plan,
        downloads_root=paths.downloads_root,
    )
    resolved_plan = apply_socrata_sample_limit(resolved_plan, bounded_limit)
    emit_showcase_progress(
        progress_callback,
        25,
        "resolve_adapter_plan",
        direct_entries_added=resolution.direct_entries_added,
        unresolved_entries=resolution.unresolved_review_entries,
    )
    seed_showcase_repository(repository, resolved_plan)
    emit_showcase_progress(progress_callback, 30, "seed_repository", provider_count=len(resolved_plan.get("providers", [])))
    paths.review_plan.write_text(json.dumps(review_plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths.resolved_plan.write_text(json.dumps(resolved_plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    emit_showcase_progress(progress_callback, 35, "write_plans", review_plan=str(paths.review_plan), resolved_plan=str(paths.resolved_plan))

    fallback_active = False

    def download_progress(update: DownloadProgress) -> None:
        # 下載階段只在 HTTP 層提供 bytes_total 時換算 byte 百分比；
        # chunked/keep-alive 來源沒有總長度時，仍回報實際 bytes_done，
        # 但流程百分比只停在下載階段範圍，避免展示假的下載百分比。
        context: dict[str, object] = {
            "bytes_done": update.bytes_done,
            "bytes_total": update.bytes_total,
            "download_percent": update.percent,
            "status": str(update.status),
            "message": update.message,
            "error": update.error,
        }
        emit_showcase_progress(
            progress_callback,
            showcase_download_flow_percent(update, fallback_active=fallback_active),
            "download",
            **context,
        )

    pipeline = run_download_import_slice(
        resolved_plan,
        repository,
        DownloadImportPipelineOptions(
            policy=policy,
            timeout=timeout,
            limit=1,
            import_supported_results=True,
            import_sqlite_path=paths.curated_sqlite,
            import_row_limit=bounded_limit,
            import_existing_table_policy="rename",
            download_progress_callback=download_progress,
        ),
    )
    used_fallback = False
    primary_error = "; ".join(pipeline.result.errors)
    if not pipeline.succeeded:
        # 展示模式的目的不是掩蓋 live API failure，而是把 failure 轉成可說明的回退流程。
        # 因此 summary 會記錄 primary_error，UI 也能清楚說明目前使用 fallback public CSV。
        emit_showcase_progress(
            progress_callback,
            36,
            "fallback_public_csv",
            primary_source=MVP_DEMO_PROVIDER_ID,
            fallback_source=SHOWCASE_FALLBACK_PROVIDER_ID,
            primary_error=primary_error,
        )
        fallback_active = True
        fallback_plan = build_showcase_fallback_csv_plan(paths, bounded_limit)
        seed_showcase_repository(repository, fallback_plan)
        fallback_plan_path = paths.root / "fallback_public_csv.resolved.json"
        fallback_plan_path.write_text(json.dumps(fallback_plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        pipeline = run_download_import_slice(
            fallback_plan,
            repository,
            DownloadImportPipelineOptions(
                policy=policy,
                timeout=max(timeout, 60.0),
                limit=1,
                import_supported_results=True,
                import_sqlite_path=paths.curated_sqlite,
                import_row_limit=bounded_limit,
                import_existing_table_policy="rename",
                download_progress_callback=download_progress,
            ),
        )
        used_fallback = True
    emit_showcase_progress(progress_callback, 82, "download_import_pipeline_completed", pipeline_stage=pipeline.stage)
    run = ShowcaseDownloadRun(
        paths=paths,
        resolution=resolution,
        pipeline=pipeline,
        table_counts=sqlite_table_counts(paths.curated_sqlite),
        sample_limit=bounded_limit,
        used_fallback=used_fallback,
        primary_error=primary_error if used_fallback else "",
    )
    emit_showcase_progress(progress_callback, 95, "count_tables", table_counts=dict(run.table_counts))
    paths.summary_json.write_text(json.dumps(run.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    emit_showcase_progress(progress_callback, 100, "completed", succeeded=run.succeeded, summary_json=str(paths.summary_json))
    return run


def normalize_showcase_sample_limit(value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = SHOWCASE_DEFAULT_SAMPLE_LIMIT
    return min(SHOWCASE_MAX_SAMPLE_LIMIT, max(1, parsed))


def seed_showcase_repository(repository: ApiCatalogRepository, plan_payload: dict[str, object]) -> None:
    # 展示模式不能假設主 catalog 已經先跑過 seed；先從 plan 反推最小 Provider/Dataset，避免 FK 保護擋住下載註冊。
    for raw_entry in plan_payload.get("providers", []):
        if not isinstance(raw_entry, dict):
            continue
        categories = tuple(str(value) for value in raw_entry.get("categories", ()) if str(value).strip())
        dataset_version = raw_entry.get("dataset_version") if isinstance(raw_entry.get("dataset_version"), dict) else {}
        metadata = dict(dataset_version.get("metadata") or {})
        metadata.setdefault("showcase_seeded_from_plan", True)
        provider = Provider(
            provider_id=str(raw_entry.get("provider_id") or MVP_DEMO_PROVIDER_ID),
            name=str(raw_entry.get("name") or "Showcase data source"),
            owner=str(raw_entry.get("owner") or "Unknown"),
            categories=categories or ("showcase",),
            geographic_scope=str(raw_entry.get("geographic_scope") or ""),
            docs_url=str(raw_entry.get("docs_url") or raw_entry.get("landing_url") or ""),
            api_base_url=str(raw_entry.get("api_base_url") or ""),
            signup_url=str(raw_entry.get("signup_url") or ""),
            auth_type=str(raw_entry.get("auth_type") or "none"),
            license_url=str(raw_entry.get("license_url") or ""),
            terms_url=str(raw_entry.get("terms_url") or ""),
            notes=str(raw_entry.get("notes") or "Showcase-mode seed generated from a resolved download plan."),
        )
        dataset = Dataset(
            dataset_uid=str(raw_entry.get("dataset_uid") or dataset_version.get("dataset_uid") or MVP_DEMO_DATASET_UID),
            provider_id=provider.provider_id,
            dataset_id=str(raw_entry.get("dataset_id") or dataset_version.get("dataset_id") or ""),
            title=str(raw_entry.get("dataset_title") or raw_entry.get("title") or dataset_version.get("label") or "Showcase dataset"),
            categories=categories or provider.categories,
            data_type=str(raw_entry.get("data_type") or ""),
            native_format=str(raw_entry.get("source_format") or metadata.get("native_format") or ""),
            geographic_scope=str(raw_entry.get("geographic_scope") or provider.geographic_scope),
            landing_url=str(raw_entry.get("landing_url") or dataset_version.get("landing_url") or ""),
            api_url=str(raw_entry.get("api_url") or raw_entry.get("download_url") or dataset_version.get("download_url") or ""),
            license_url=str(raw_entry.get("license_url") or ""),
            version=str(dataset_version.get("version") or raw_entry.get("version") or "showcase"),
            metadata=metadata,
        )
        repository.upsert_provider(provider)
        repository.upsert_dataset(dataset)


def apply_socrata_sample_limit(plan_payload: dict[str, object], sample_limit: int) -> dict[str, object]:
    # resolver 會先產生 canonical $limit=25；展示模式再把 limit 改成使用者指定值，
    # 讓現場可以調整大小，同時仍保留有界查詢與 manifest/source_url 比對。
    updated = dict(plan_payload)
    sample_url = showcase_socrata_rows_json_url(sample_limit)
    entries = []
    for raw_entry in updated.get("providers", []):
        entry = dict(raw_entry) if isinstance(raw_entry, dict) else raw_entry
        if isinstance(entry, dict):
            url = str(entry.get("download_url") or "")
            if MVP_DEMO_RESOURCE_URL in url:
                # Socrata resource endpoint 在部分網路環境會長時間等待；rows API 仍是真實公開資料，
                # 但能用 length 控制樣本大小，展示現場更穩定。
                entry["download_url"] = sample_url
                version_meta = entry.get("dataset_version")
                if isinstance(version_meta, dict):
                    version_meta = dict(version_meta)
                    version_meta["download_url"] = entry["download_url"]
                    version_meta["notes"] = f"Showcase bounded Socrata rows API sample, user-selected length={sample_limit}."
                    metadata = dict(version_meta.get("metadata") or {})
                    metadata["showcase_sample_limit"] = sample_limit
                    metadata["showcase_sample_url_kind"] = "socrata_rows_json_window"
                    version_meta["metadata"] = metadata
                    entry["dataset_version"] = version_meta
                eligibility = dict(entry.get("download_eligibility") or {})
                if eligibility:
                    eligibility["direct_url"] = sample_url
                    eligibility["reason"] = "Showcase rows API sample; length is controlled from the GUI."
                    entry["download_eligibility"] = eligibility
                adapter_resolution = dict(entry.get("adapter_resolution") or {})
                if adapter_resolution:
                    adapter_resolution["sample_url"] = sample_url
                    adapter_resolution["sample_limit"] = sample_limit
                    adapter_resolution["policy"] = "showcase_rows_api_bounded_length"
                    entry["adapter_resolution"] = adapter_resolution
                showcase = dict(entry.get("showcase") or {})
                showcase["sample_limit"] = sample_limit
                showcase["sample_url_kind"] = "socrata_rows_json_window"
                entry["showcase"] = showcase
        entries.append(entry)
    updated["providers"] = entries
    summary = dict(updated.get("summary") or {})
    summary["showcase_sample_limit"] = sample_limit
    updated["summary"] = summary
    return updated


def showcase_socrata_rows_json_url(sample_limit: int) -> str:
    from urllib.parse import urlencode

    query = urlencode(
        {
            "accessType": "DOWNLOAD",
            "method": "getByIds",
            "asHashes": "true",
            "start": "0",
            "length": str(normalize_showcase_sample_limit(sample_limit)),
        }
    )
    return f"{MVP_DEMO_API_VIEW_URL}/rows.json?{query}"


def socrata_url_with_limit(url: str, sample_limit: int) -> str:
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    parts = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key != "$limit"]
    query.append(("$limit", str(normalize_showcase_sample_limit(sample_limit))))
    # urlencode 會把 `$limit` 變成 `%24limit`；HTTP 上可行，但展示與除錯時保留 Socrata 慣用寫法更直觀。
    encoded_query = urlencode(query).replace("%24limit=", "$limit=")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, encoded_query, parts.fragment))


def sqlite_table_counts(sqlite_path: str | Path) -> dict[str, int]:
    path = Path(sqlite_path)
    if not path.exists():
        return {}
    with closing(sqlite3.connect(path)) as conn:
        table_rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        counts: dict[str, int] = {}
        for (table_name,) in table_rows:
            quoted = '"' + str(table_name).replace('"', '""') + '"'
            row = conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()
            counts[str(table_name)] = int(row[0] if row else 0)
    return counts
