from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from api_launcher.adapters.yfinance import normalize_yfinance_symbols
from api_launcher.crawler_asset_display import crawler_asset_download_import_display_payload, next_action_display_label
from api_launcher.data_store_connections import data_store_env_template_filename
from api_launcher.paths import PROJECT_ROOT, state_file


@dataclass(frozen=True)
class CrawlerSeedDownloadImportUiMessage:
    """Display-ready Tk message for one seed download/import completion."""

    succeeded: bool
    stage: str
    dataset_uid: str
    title: str
    status_message: str
    body: str


def database_sql_dry_run_available(suggestion: object) -> bool:
    # database_self_check 已經集中判斷安全條件；UI 只讀旗標，避免在視窗層重寫資料庫 ownership 規則。
    details = getattr(suggestion, "details", {})
    return isinstance(details, dict) and bool(details.get("sql_dry_run_available"))


def data_store_env_template_path(profile_id: str) -> Path:
    # 檔名白名單化規則放在 data_store_connections，CLI/agent/UI 才會指向同一個預設範本名稱。
    return state_file(f"data_store_env_templates/{data_store_env_template_filename(profile_id)}")


def clamp(value: int, minimum: int, maximum: int) -> int:
    """把 Tk responsive layout 的尺寸限制在安全範圍內。"""
    return max(minimum, min(maximum, value))


def yfinance_symbols_from_ui_text(text: str) -> tuple[str, ...]:
    # UI 允許使用者輸入逗號或空白分隔的 symbols；真正的格式驗證仍交給 adapter 共用規則。
    return normalize_yfinance_symbols(str(text or "").replace(",", " ").split())


def yfinance_storage_review_paths_from_ui(plan_text: str, review_text: str) -> tuple[Path, Path]:
    # storage review dialog 會同時產出 JSON/SQL/Markdown；所有路徑都必須以 project root 為基準。
    return yfinance_project_path_from_ui_text(plan_text, "Plan"), yfinance_project_path_from_ui_text(review_text, "Review")


def yfinance_project_path_from_ui_text(raw_text: str, field_name: str) -> Path:
    # yfinance UI 輸入框常填相對路徑；轉成 project-root path 可避免 cwd 改變時寫到錯誤位置。
    text = str(raw_text or "").strip()
    if not text:
        raise ValueError(f"{field_name} path is required.")
    path = Path(text).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def mvp_demo_smoke_result_message(payload: dict[str, object], tr) -> str:
    # 這個 helper 專門把 agent-readable JSON 轉成人類能採取下一步的 UI 摘要。
    # GUI 不應只顯示 succeeded=true；一般使用者需要知道資料表、筆數、artifact 與修復入口。
    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
    download_import = payload.get("download_import") if isinstance(payload.get("download_import"), dict) else {}
    result = download_import.get("result") if isinstance(download_import.get("result"), dict) else {}
    succeeded = bool(payload.get("succeeded"))
    stage = str(payload.get("stage") or "-")
    table_name = str(payload.get("table_name") or "-")
    row_count = payload.get("row_count", 0)
    completed = result.get("completed", 0)
    imported = result.get("imported", 0)
    failed = result.get("failed", 0)
    import_failed = result.get("import_failed", 0)
    next_action = next_action_display_label(payload.get("next_action"))
    flow_manifest = str(artifacts.get("flow_manifest") or "-")
    curated_sqlite = str(artifacts.get("curated_sqlite") or "-")
    status_zh = "通過" if succeeded else "未通過"
    status_en = "passed" if succeeded else "did not pass"
    message = tr(
        (
            f"MVP Demo Smoke {status_zh}\n\n"
            f"階段：{stage}\n"
            f"匯入資料表：{table_name}\n"
            f"匯入筆數：{row_count}\n"
            f"下載完成：{completed}；匯入完成：{imported}\n"
            f"下載失敗：{failed}；匯入失敗：{import_failed}\n\n"
            f"Flow：{flow_manifest}\n"
            f"Curated SQLite：{curated_sqlite}"
        ),
        (
            f"MVP Demo Smoke {status_en}\n\n"
            f"Stage: {stage}\n"
            f"Imported table: {table_name}\n"
            f"Rows imported: {row_count}\n"
            f"Downloads completed: {completed}; imports completed: {imported}\n"
            f"Downloads failed: {failed}; imports failed: {import_failed}\n\n"
            f"Flow: {flow_manifest}\n"
            f"Curated SQLite: {curated_sqlite}"
        ),
    )
    if next_action:
        message += tr(
            f"\n\n下一步：{next_action}",
            f"\n\nNext action: {next_action}",
        )
    if not succeeded:
        message += "\n\n" + tr(
            "修復建議：先開啟「工具 > 最近事件紀錄」確認失敗階段；若是 manifest 或匯入失敗，"
            "再到「工具 > 修復 / 驗證資產」檢查 sidecar manifest 與 SQLite table 狀態。",
            "Repair guide: open Tools > Recent event logs to identify the failed stage. If the issue is manifest or import related, open Tools > Repair / verify assets to inspect sidecar manifests and SQLite table state.",
        )
    return message


def crawler_seed_download_import_ui_message(
    result: object,
    tr: Callable[[str, str], str],
) -> CrawlerSeedDownloadImportUiMessage:
    """Convert backend download/import display payload into a Tk message.

    The backend helper owns outcome, stage, next-action and artifact fields.
    Tk only chooses whether the result is shown as an info or warning dialog.
    """

    display_payload = crawler_asset_download_import_display_payload(result)
    raw_payload = display_payload.get("download_result")
    payload = raw_payload if isinstance(raw_payload, dict) else {}
    raw_download_import = display_payload.get("download_import")
    download_import = raw_download_import if isinstance(raw_download_import, dict) else {}
    stage = str(download_import.get("stage") or payload.get("stage") or getattr(getattr(result, "pipeline", None), "stage", "") or "-")
    succeeded = bool(
        download_import.get("succeeded")
        if "succeeded" in download_import
        else payload.get("succeeded")
        if "succeeded" in payload
        else getattr(result, "succeeded", False)
    )
    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
    downloads_root = str(artifacts.get("downloads_root") or "")
    curated_sqlite = str(artifacts.get("curated_sqlite") or "")
    dataset_uid = str(payload.get("dataset_uid") or "").strip()
    next_action = str(display_payload.get("next_action") or download_import.get("next_action") or payload.get("next_action") or "").strip()
    next_action_label = str(display_payload.get("next_action_label") or payload.get("next_action_label") or next_action).strip()
    body = tr(
        (
            f"Seed：{dataset_uid or '-'}\n"
            f"Stage：{stage}\n"
            f"Downloads：{downloads_root or '-'}\n"
            f"SQLite：{curated_sqlite or '-'}\n"
            f"下一步：{next_action_label or '-'}"
        ),
        (
            f"Seed: {dataset_uid or '-'}\n"
            f"Stage: {stage}\n"
            f"Downloads: {downloads_root or '-'}\n"
            f"SQLite: {curated_sqlite or '-'}\n"
            f"Next: {next_action_label or '-'}"
        ),
    )
    if succeeded:
        return CrawlerSeedDownloadImportUiMessage(
            succeeded=True,
            stage=stage,
            dataset_uid=dataset_uid,
            title=tr("Seed 下載 / 匯入完成", "Seed download/import completed"),
            status_message=tr(f"Seed 下載 / 匯入完成：{dataset_uid or '-'}", f"Seed download/import completed: {dataset_uid or '-'}"),
            body=body,
        )
    return CrawlerSeedDownloadImportUiMessage(
        succeeded=False,
        stage=stage,
        dataset_uid=dataset_uid,
        title=tr("Seed 下載 / 匯入未完成", "Seed download/import incomplete"),
        status_message=tr(f"Seed 下載 / 匯入未完成：{stage}", f"Seed download/import did not complete: {stage}"),
        body=body,
    )


def mvp_demo_smoke_exception_message(error: Exception, flow_path: Path, tr) -> str:
    # 例外訊息保留技術細節，但前面先給可操作修復步驟，避免使用者只看到 traceback。
    command = (
        f"py -B APIkeys_collection.py --db {flow_path.with_name('launcher.sqlite')} "
        f"--init-db --seed --run-mvp-demo-smoke-json {flow_path}"
    )
    return tr(
        (
            f"MVP Demo Smoke 無法完成：{type(error).__name__}: {error}\n\n"
            "修復建議：\n"
            f"1. 確認 {flow_path.parent} 可以寫入，且沒有被同步軟體或防毒鎖住。\n"
            "2. 開啟「工具 > 啟動環境檢查」與「工具 > 最近事件紀錄」查看路徑、SQLite、manifest 錯誤。\n"
            "3. 若要排除 UI 因素，可在 PowerShell 執行：\n"
            f"{command}"
        ),
        (
            f"MVP Demo Smoke could not finish: {type(error).__name__}: {error}\n\n"
            "Repair guide:\n"
            f"1. Confirm {flow_path.parent} is writable and not locked by sync or antivirus software.\n"
            "2. Open Tools > Startup environment checks and Tools > Recent event logs for path, SQLite, or manifest errors.\n"
            "3. To remove UI variables, run this in PowerShell:\n"
            f"{command}"
        ),
    )


def local_file_provenance_review_message(review: object) -> str:
    # UI 成功訊息需要把後端 provenance_review 壓成短文字，讓新手知道這不是已驗證授權的外部來源。
    if not isinstance(review, dict):
        return ""
    source_label = str(review.get("source_label_zh_TW") or "使用者自備本機檔案")
    format_label = str(review.get("format_label_zh_TW") or "")
    trust_boundary = str(review.get("trust_boundary_zh_TW") or "")
    recommended = str(review.get("recommended_next_step_zh_TW") or "")
    blocked = review.get("blocked_operations_zh_TW")
    blocked_text = "、".join(str(item) for item in blocked[:3]) if isinstance(blocked, list) else ""
    heading = f"來源審查：{source_label}"
    if format_label:
        heading += f"（{format_label}）"
    lines = [heading]
    if trust_boundary:
        lines.append(f"安全邊界：{trust_boundary}")
    if blocked_text:
        lines.append(f"不會執行：{blocked_text}。")
    if recommended:
        lines.append(f"下一步：{recommended}")
    return "\n".join(lines)


def local_file_import_error_message(exc: Exception) -> str:
    # 手動匯入的格式錯誤已由後端寫成使用者可讀的修復指引；UI 不再加工程用例外類名。
    message = str(exc).strip()
    if isinstance(exc, ValueError) and message.startswith("Unsupported manual import format"):
        return message
    return f"{type(exc).__name__}: {message}" if message else type(exc).__name__
