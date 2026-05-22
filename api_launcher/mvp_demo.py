from __future__ import annotations

import json
import re
import sqlite3
import urllib.parse
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from api_launcher.adapter_review import adapter_review_agent_payload
from api_launcher.dataset_versions import DatasetVersionOption
from api_launcher.db import utc_now_iso
from api_launcher.importers.csv_importer import unique_table_name
from api_launcher.ingestion_pipeline import (
    DownloadImportPipelineOptions,
    DownloadImportPipelineRun,
    run_download_import_slice,
)
from api_launcher.models import Dataset, Provider
from api_launcher.paths import PROJECT_ROOT
from api_launcher.plans import build_dataset_download_plan, provider_dataset_version_plan_entry
from api_launcher.repository import ApiCatalogRepository


MVP_DEMO_FLOW_ID = "canonical_socrata_311_small_sample"
MVP_DEMO_PROVIDER_ID = "nyc_open_data_socrata"
MVP_DEMO_DATASET_ID = "erm2-nwe9"
MVP_DEMO_DATASET_UID = f"{MVP_DEMO_PROVIDER_ID}:{MVP_DEMO_DATASET_ID}:mvp_demo"
MVP_DEMO_LANDING_URL = "https://data.cityofnewyork.us/Social-Services/311-Service-Requests/erm2-nwe9"
MVP_DEMO_API_VIEW_URL = f"https://data.cityofnewyork.us/api/views/{MVP_DEMO_DATASET_ID}"
MVP_DEMO_RESOURCE_URL = f"https://data.cityofnewyork.us/resource/{MVP_DEMO_DATASET_ID}.json"


@dataclass(frozen=True)
class MvpDemoFlowWriteResult:
    flow_path: Path
    db_path: Path
    review_plan_path: Path
    review_payload_path: Path
    offline_sample_path: Path
    offline_plan_path: Path
    resolved_plan_path: Path
    downloads_root: Path
    import_sqlite_path: Path
    flow_payload: dict[str, object]


@dataclass(frozen=True)
class MvpDemoSmokeResult:
    flow: MvpDemoFlowWriteResult
    run: DownloadImportPipelineRun
    table_name: str
    row_count: int

    @property
    def succeeded(self) -> bool:
        return self.run.succeeded and self.row_count > 0

    def to_dict(self) -> dict[str, object]:
        # 這份 JSON 是給 heartbeat/下一位 agent 讀的，不需要解析人類 CLI 摘要。
        return {
            "flow_id": MVP_DEMO_FLOW_ID,
            "stage": self.run.stage,
            "succeeded": self.succeeded,
            "table_name": self.table_name,
            "row_count": self.row_count,
            "artifacts": {
                "flow_manifest": _project_display_path(self.flow.flow_path),
                "launcher_db": _project_display_path(self.flow.db_path),
                "review_plan": _project_display_path(self.flow.review_plan_path),
                "adapter_review_json": _project_display_path(self.flow.review_payload_path),
                "offline_sample": _project_display_path(self.flow.offline_sample_path),
                "offline_direct_plan": _project_display_path(self.flow.offline_plan_path),
                "resolved_plan": _project_display_path(self.flow.resolved_plan_path),
                "downloads_root": _project_display_path(self.flow.downloads_root),
                "curated_sqlite": _project_display_path(self.flow.import_sqlite_path),
            },
            "download_import": self.run.to_dict(),
            "next_action": self.run.next_action,
            "acceptance_zh_TW": "離線 fixture 已完成 download -> manifest -> SQLite import，且匯入表格可讀到資料列。",
        }


def build_mvp_demo_review_plan(downloads_root: str | Path = "state/mvp_demo/downloads") -> dict[str, object]:
    # 這份 plan 是固定 demo fixture：用真實公開來源驗證流程，但不取代 crawler-first 的正式資料發現路線。
    provider = Provider(
        provider_id=MVP_DEMO_PROVIDER_ID,
        name="NYC Open Data Socrata",
        owner="City of New York",
        categories=("open_data", "socrata", "city_services"),
        geographic_scope="New York City, US",
        docs_url="https://dev.socrata.com/foundry/data.cityofnewyork.us/erm2-nwe9",
        api_base_url=MVP_DEMO_API_VIEW_URL,
        signup_url="",
        auth_type="none",
        notes="Canonical MVP demo provider used to prove adapter review -> bounded sample -> download/import.",
    )
    dataset = Dataset(
        dataset_uid=MVP_DEMO_DATASET_UID,
        provider_id=MVP_DEMO_PROVIDER_ID,
        dataset_id=MVP_DEMO_DATASET_ID,
        title="NYC 311 Service Requests small Socrata sample",
        categories=("open_data", "socrata", "city_services"),
        data_type="table_sample",
        native_format="socrata_resource",
        geographic_scope="New York City, US",
        landing_url=MVP_DEMO_LANDING_URL,
        api_url=MVP_DEMO_API_VIEW_URL,
        version="mvp-demo",
        metadata={
            "candidate_status": "approved",
            "data_family": "table_sample",
            "discovery_source_id": "canonical_mvp_demo_fixture",
            "discovery_source_type": "socrata_catalog_search",
            "source_url": "https://api.us.socrata.com/api/catalog/v1?domains=data.cityofnewyork.us&q=311",
            "socrata_dataset_id": MVP_DEMO_DATASET_ID,
            "socrata_domain": "data.cityofnewyork.us",
            "socrata_api_view_url": MVP_DEMO_API_VIEW_URL,
            "socrata_resource_url": MVP_DEMO_RESOURCE_URL,
        },
    )
    option = DatasetVersionOption(
        dataset_uid=dataset.dataset_uid,
        dataset_id=dataset.dataset_id,
        label="Socrata API view before bounded-sample resolution",
        version="mvp-demo",
        status="demo_review",
        download_url=MVP_DEMO_API_VIEW_URL,
        landing_url=MVP_DEMO_LANDING_URL,
        update_strategy="sample_then_review",
        notes="Resolver should turn this API view into a $limit=25 Socrata JSON sample.",
        metadata=dict(dataset.metadata),
    )
    entry = provider_dataset_version_plan_entry(provider, dataset, option, downloads_root=downloads_root)
    entry["candidate_review"] = {
        "candidate_status": "approved",
        "discovery_source_id": "canonical_mvp_demo_fixture",
        "discovery_source_type": "socrata_catalog_search",
        "source_url": dataset.metadata["source_url"],
        "confidence": "demo_fixture",
    }
    entry["mvp_demo"] = {
        "flow_id": MVP_DEMO_FLOW_ID,
        "purpose_zh_TW": "固定驗證 MVP 主線：adapter review -> bounded sample -> download -> manifest -> SQLite import。",
        "not_canonical_catalog_seed": True,
    }
    payload = build_dataset_download_plan([entry], plan_name="canonical_mvp_demo_socrata_311")
    payload["source"] = {
        "kind": "canonical_mvp_demo_flow",
        "flow_id": MVP_DEMO_FLOW_ID,
        "crawler_first_note_zh_TW": "這是可重複 demo fixture；正式擴充仍應先走 crawler/source/candidate。",
    }
    return payload


def build_mvp_demo_offline_direct_plan(
    sample_path: str | Path,
    downloads_root: str | Path = "state/mvp_demo/downloads",
) -> dict[str, object]:
    # 離線 plan 用同一個資料概念，但來源是本機 fixture；這讓 demo 的下載/匯入驗收不被外部網站 timeout 影響。
    provider = Provider(
        provider_id=MVP_DEMO_PROVIDER_ID,
        name="NYC Open Data Socrata",
        owner="City of New York",
        categories=("demo", "offline_fixture", "json"),
        geographic_scope="local",
        docs_url="",
        api_base_url="",
        auth_type="none",
        notes="Offline fixture for proving download, manifest, and SQLite import without network access.",
    )
    dataset = Dataset(
        dataset_uid=f"{MVP_DEMO_PROVIDER_ID}:socrata_311_sample:offline_mvp_demo",
        provider_id=provider.provider_id,
        dataset_id="socrata_311_sample",
        title="Offline Socrata 311 JSON fixture",
        categories=("demo", "json", "table_sample"),
        data_type="table_sample",
        native_format="json",
        geographic_scope="local",
        landing_url=MVP_DEMO_LANDING_URL,
        api_url=local_file_url(Path(sample_path)),
        version="offline-mvp-demo",
        metadata={
            "data_family": "table_sample",
            "native_format": "json",
            "resolver_id": "local_mvp_demo_fixture",
            "source_demo_flow_id": MVP_DEMO_FLOW_ID,
        },
    )
    option = DatasetVersionOption(
        dataset_uid=dataset.dataset_uid,
        dataset_id=dataset.dataset_id,
        label="Offline JSON fixture for MVP demo import",
        version=dataset.version,
        status="demo_fixture",
        download_url=dataset.api_url,
        landing_url=dataset.landing_url,
        update_strategy="replace_demo_fixture",
        notes="Local file URL used to prove the runner/importer path without network access.",
        metadata=dict(dataset.metadata),
    )
    entry = provider_dataset_version_plan_entry(provider, dataset, option, downloads_root=downloads_root)
    entry["mvp_demo"] = {
        "flow_id": MVP_DEMO_FLOW_ID,
        "purpose_zh_TW": "離線驗證下載器、manifest 登錄與 SQLite 匯入閉環。",
        "offline_fixture": True,
    }
    payload = build_dataset_download_plan([entry], plan_name="canonical_mvp_demo_offline_direct")
    payload["source"] = {
        "kind": "canonical_mvp_demo_offline_fixture",
        "flow_id": MVP_DEMO_FLOW_ID,
        "sample_path": str(sample_path),
    }
    return payload


def mvp_demo_offline_sample_rows() -> list[dict[str, object]]:
    return [
        {
            "unique_key": "demo-001",
            "created_date": "2026-01-01T00:00:00",
            "agency": "DEMO",
            "complaint_type": "Street Condition",
            "borough": "MANHATTAN",
            "latitude": 40.758,
            "longitude": -73.9855,
        },
        {
            "unique_key": "demo-002",
            "created_date": "2026-01-01T01:00:00",
            "agency": "DEMO",
            "complaint_type": "Noise",
            "borough": "BROOKLYN",
            "latitude": 40.6782,
            "longitude": -73.9442,
        },
        {
            "unique_key": "demo-003",
            "created_date": "2026-01-01T02:00:00",
            "agency": "DEMO",
            "complaint_type": "Water System",
            "borough": "QUEENS",
            "latitude": 40.7282,
            "longitude": -73.7949,
        },
    ]


def build_mvp_demo_flow_payload(
    *,
    flow_path: Path,
    db_path: Path,
    review_plan_path: Path,
    review_payload_path: Path,
    offline_sample_path: Path,
    offline_plan_path: Path,
    resolved_plan_path: Path,
    downloads_root: Path,
    import_sqlite_path: Path,
    review_plan_summary: dict[str, object],
) -> dict[str, object]:
    flow_arg = _command_arg(_project_display_path(flow_path))
    db_arg = _command_arg(_project_display_path(db_path))
    review_arg = _command_arg(_project_display_path(review_plan_path))
    review_payload_arg = _command_arg(_project_display_path(review_payload_path))
    offline_plan_arg = _command_arg(_project_display_path(offline_plan_path))
    resolved_arg = _command_arg(_project_display_path(resolved_plan_path))
    downloads_arg = _command_arg(_project_display_path(downloads_root))
    sqlite_arg = _command_arg(_project_display_path(import_sqlite_path))
    base = f"py -B APIkeys_collection.py --db {db_arg}"
    return {
        "schema_version": 1,
        "flow_id": MVP_DEMO_FLOW_ID,
        "created_at": utc_now_iso(),
        "purpose_zh_TW": "建立一條可重複執行的 MVP Demo Flow，證明 plan 解析、下載、manifest 與 SQLite 匯入可以串起來。",
        "checkpoint_zh_TW": "Canonical MVP Demo Flow",
        "mvp_segment": "seed -> candidate/plan -> adapter resolver -> download -> import -> verify",
        "artifacts": {
            "flow_manifest": _project_display_path(flow_path),
            "launcher_db": _project_display_path(db_path),
            "review_plan": _project_display_path(review_plan_path),
            "adapter_review_json": _project_display_path(review_payload_path),
            "offline_sample": _project_display_path(offline_sample_path),
            "offline_direct_plan": _project_display_path(offline_plan_path),
            "resolved_plan": _project_display_path(resolved_plan_path),
            "downloads_root": _project_display_path(downloads_root),
            "curated_sqlite": _project_display_path(import_sqlite_path),
        },
        "commands": [
            {
                "step": 1,
                "name_zh_TW": "產生 demo flow 與 review plan",
                "command": f"{base} --init-db --seed --write-mvp-demo-flow {flow_arg}",
                "expected_zh_TW": "寫出 flow JSON 與 Socrata adapter review plan；這一步不下載資料。",
            },
            {
                "step": 2,
                "name_zh_TW": "一鍵離線 smoke 驗證",
                "command": f"{base} --init-db --seed --run-mvp-demo-smoke-json {flow_arg}",
                "expected_zh_TW": "重新寫出同一組 demo artifacts，離線跑完下載、manifest 與 SQLite 匯入，並輸出 JSON 驗收摘要。",
            },
            {
                "step": 3,
                "name_zh_TW": "查看 adapter 待辦",
                "command": f"{base} --adapter-review-plan {review_arg} --write-adapter-review-json {review_payload_arg}",
                "expected_zh_TW": "看到 1 筆需要解析的 Socrata API view。",
            },
            {
                "step": 4,
                "name_zh_TW": "解析成 bounded direct sample",
                "command": (
                    f"{base} --resolve-adapter-plan {review_arg} "
                    f"--write-resolved-adapter-plan {resolved_arg} --downloads-root {downloads_arg}"
                ),
                "expected_zh_TW": "產生含有 $limit=25 的 direct download plan entry。",
            },
            {
                "step": 5,
                "name_zh_TW": "離線下載並匯入 SQLite",
                "command": (
                    f"{base} --init-db --seed --run-download-plan {offline_plan_arg} --downloads-root {downloads_arg} "
                    f"--import-supported-plan-results --import-sqlite-db {sqlite_arg} "
                    "--plan-import-existing-table-policy rename"
                ),
                "expected_zh_TW": "用本機 JSON fixture 下載小樣本、寫出 sidecar manifest，並匯入 curated SQLite。",
            },
            {
                "step": 6,
                "name_zh_TW": "線上 Socrata 樣本下載（選用）",
                "command": (
                    f"{base} --init-db --seed --run-download-plan {resolved_arg} --downloads-root {downloads_arg} "
                    f"--import-supported-plan-results --import-sqlite-db {sqlite_arg} "
                    "--plan-import-existing-table-policy rename"
                ),
                "expected_zh_TW": "若網路穩定，可下載真正的 Socrata $limit=25 小樣本；timeout 時不影響離線 checkpoint。",
            },
            {
                "step": 7,
                "name_zh_TW": "驗證下載與登錄狀態",
                "command": f"{base} --init-db --seed --verify-downloads --downloads-root {downloads_arg} --manifest-health --summary",
                "expected_zh_TW": "manifest health 可被掃描，SQLite catalog 能看到已登錄資產。",
            },
        ],
        "acceptance_checks_zh_TW": [
            "review plan 的 summary.review_required_count 為 1。",
            "resolver 輸出 direct_added=1，resolved plan 的 download_url 含有 $limit=25。",
            "離線 direct plan 可下載本機 fixture，並產生 payload 與 .manifest.json。",
            "匯入後 curated SQLite 至少有一張 demo table，並且 registry 登錄 table asset；線上 Socrata 下載是額外 smoke test。",
        ],
        "risk_notes_zh_TW": [
            "步驟 1 到 4 可離線測試；線上 Socrata 步驟需要 data.cityofnewyork.us 可連線。",
            "這是固定 demo fixture，不應變成新增正式供應商時的捷徑；正式資料仍要走 crawler-first。",
        ],
        "review_plan_summary": review_plan_summary,
    }


def write_mvp_demo_flow(flow_path: str | Path) -> MvpDemoFlowWriteResult:
    flow_path = Path(flow_path)
    flow_path.parent.mkdir(parents=True, exist_ok=True)
    review_plan_path = flow_path.with_name("socrata_311.review.json")
    review_payload_path = flow_path.with_name("socrata_311.adapter_review.json")
    db_path = flow_path.with_name("launcher.sqlite")
    offline_sample_path = flow_path.with_name("socrata_311.offline_sample.json")
    offline_plan_path = flow_path.with_name("socrata_311.offline_direct.json")
    resolved_plan_path = flow_path.with_name("socrata_311.resolved.json")
    downloads_root = flow_path.parent / "downloads"
    import_sqlite_path = flow_path.parent / "curated_demo.sqlite"

    review_plan = build_mvp_demo_review_plan(downloads_root=_project_display_path(downloads_root))
    review_plan_path.write_text(json.dumps(review_plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    review_payload_path.write_text(
        json.dumps(adapter_review_agent_payload(review_plan), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    offline_sample_path.write_text(json.dumps(mvp_demo_offline_sample_rows(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    offline_plan = build_mvp_demo_offline_direct_plan(
        offline_sample_path,
        downloads_root=_project_display_path(downloads_root),
    )
    offline_plan_path.write_text(json.dumps(offline_plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    flow_payload = build_mvp_demo_flow_payload(
        flow_path=flow_path,
        db_path=db_path,
        review_plan_path=review_plan_path,
        review_payload_path=review_payload_path,
        offline_sample_path=offline_sample_path,
        offline_plan_path=offline_plan_path,
        resolved_plan_path=resolved_plan_path,
        downloads_root=downloads_root,
        import_sqlite_path=import_sqlite_path,
        review_plan_summary=dict(review_plan.get("summary") or {}),
    )
    flow_path.write_text(json.dumps(flow_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return MvpDemoFlowWriteResult(
        flow_path=flow_path,
        db_path=db_path,
        review_plan_path=review_plan_path,
        review_payload_path=review_payload_path,
        offline_sample_path=offline_sample_path,
        offline_plan_path=offline_plan_path,
        resolved_plan_path=resolved_plan_path,
        downloads_root=downloads_root,
        import_sqlite_path=import_sqlite_path,
        flow_payload=flow_payload,
    )


def run_mvp_demo_offline_smoke(flow_path: str | Path, repository: ApiCatalogRepository) -> MvpDemoSmokeResult:
    # smoke 會先重寫 canonical artifacts，再執行離線 plan；因此新 agent 不必記住多步手動命令。
    flow = write_mvp_demo_flow(flow_path)
    plan_payload = json.loads(flow.offline_plan_path.read_text(encoding="utf-8"))
    table_name = _predict_offline_import_table(plan_payload, flow.import_sqlite_path)
    run = run_download_import_slice(
        plan_payload,
        repository,
        DownloadImportPipelineOptions(
            import_supported_results=True,
            import_sqlite_path=flow.import_sqlite_path,
            import_existing_table_policy="rename",
        ),
    )
    row_count = _sqlite_table_row_count(flow.import_sqlite_path, table_name)
    return MvpDemoSmokeResult(flow=flow, run=run, table_name=table_name, row_count=row_count)


def _predict_offline_import_table(plan_payload: dict[str, object], sqlite_path: Path) -> str:
    # 目前 canonical offline plan 只有一筆 direct entry；這裡仍從 plan 讀 table_hint，避免硬編碼 importer 命名。
    for entry in plan_payload.get("providers", []):
        if not isinstance(entry, dict):
            continue
        import_plan = entry.get("import_plan") if isinstance(entry.get("import_plan"), dict) else {}
        table_hint = str(import_plan.get("table_hint") or "").strip()
        if table_hint:
            return unique_table_name(sqlite_path, table_hint)
    return ""


def _sqlite_table_row_count(sqlite_path: Path, table_name: str) -> int:
    if not table_name or not sqlite_path.exists():
        return 0
    with closing(sqlite3.connect(sqlite_path)) as conn:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        if not exists:
            return 0
        row = conn.execute(f"SELECT COUNT(*) FROM {_quote_sql_identifier(table_name)}").fetchone()
    return int(row[0] if row else 0)


def _quote_sql_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _project_display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _command_arg(value: str) -> str:
    if not value:
        return '""'
    if re.search(r"\s", value):
        return f'"{value}"'
    return value


def local_file_url(path: Path) -> str:
    # Windows mapped/cloud drives may resolve to UNC paths; urllib needs the localhost UNC form to open them reliably.
    raw = str(path.absolute())
    posix = raw.replace("\\", "/")
    if posix.startswith("//"):
        return "file://localhost" + urllib.parse.quote(posix, safe="/:")
    return "file:///" + urllib.parse.quote(posix, safe="/:")
