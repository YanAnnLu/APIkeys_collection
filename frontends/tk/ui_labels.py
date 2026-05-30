"""Tk UI 狀態與修復建議文字 helper。"""

from __future__ import annotations

from collections.abc import Callable

from api_launcher.data_store_connections import data_store_connection_next_action
from frontends.tk.ui_helpers import database_sql_dry_run_available

Translator = Callable[[str, str], str]


def localized_download_label(eligibility: object, ui_language: str) -> str:
    """把下載資格狀態轉成表格短標籤。"""

    # backend eligibility 保留英文穩定碼；UI 顯示才轉繁中，避免資料層混入介面語言。
    label = str(getattr(eligibility, "label", ""))
    if ui_language != "en-US":
        labels = {
            "direct_download": "直接下載",
            "adapter_required": "需要轉接器",
            "metadata_only": "僅文件",
            "unavailable": "不可用",
        }
        label = labels.get(str(getattr(eligibility, "status", "")), label)
    if bool(getattr(eligibility, "requires_api_key", False)):
        return f"{label}+Key" if ui_language == "en-US" else f"{label}+金鑰"
    return label


def localized_download_reason(eligibility: object, ui_language: str) -> str:
    """把下載資格原因轉成 detail panel 可讀說明。"""

    reason = str(getattr(eligibility, "reason", ""))
    if ui_language == "en-US":
        return reason
    reasons = {
        "direct_download": "這個 API 或下載網址看起來可以直接取得檔案。",
        "adapter_required": "這個來源提供 API，需要資料轉接器把資料整理成本機檔案。",
        "metadata_only": "目前只有文件或註冊頁，還沒有直接資料下載網址。",
        "unavailable": "尚未設定可用的文件、API 或下載網址。",
    }
    return reasons.get(str(getattr(eligibility, "status", "")), reason)


def localized_download_repair_label(suggestion: object, ui_language: str) -> str:
    """把下載 manifest repair suggestion 轉成 UI 短標籤。"""

    if ui_language == "en-US":
        return str(getattr(suggestion, "label", ""))
    labels = {
        "none": "不需處理",
        "inspect_manifest": "檢查 manifest",
        "inspect": "檢查狀態",
        "manual_recover": "需要手動修復",
        "requeue_download": "重新排下載",
    }
    return labels.get(str(getattr(suggestion, "action_id", "")), str(getattr(suggestion, "label", "")))


def localized_database_repair_label(suggestion: object, ui_language: str) -> str:
    """把 database self-check repair suggestion 轉成 UI 短標籤。"""

    if ui_language == "en-US":
        return str(getattr(suggestion, "label", ""))
    labels = {
        "configure_data_store_env": "設定資料儲存環境變數",
        "install_optional_driver_in_project_env": "安裝選用 SQL driver",
        "fix_data_store_profile_mapping": "修正資料儲存 profile",
        "review_schema_drift": "檢查 schema 變動",
        "restore_or_reimport_table": "還原或重新匯入資料表",
        "restore_or_reimport_sqlite_database": "還原或重新匯入 SQLite",
        "test_data_store_connection": "測試資料儲存連線",
        "implement_database_self_check_adapter": "新增自檢 adapter",
        "fix_registry_asset_kind": "修正 registry 資產種類",
        "inspect_database_asset": "檢查資料庫資產",
    }
    return labels.get(str(getattr(suggestion, "action_id", "")), str(getattr(suggestion, "label", "")))


def localized_database_repair_description(suggestion: object, ui_language: str, tr: Translator) -> str:
    """把 database self-check repair suggestion 轉成下一步修復說明。"""

    # 非 SQLite 自動修復仍維持 dry-run / DBA review 邊界；UI 只顯示可審核的下一步。
    if database_sql_dry_run_available(suggestion):
        return tr(
            "這個 MySQL/PostgreSQL 資料表不存在，但 registry 有健康 manifest；可先產生 dry-run SQL 交給人類或 DBA 審核。",
            "This MySQL/PostgreSQL table is missing and has a healthy manifest; write dry-run SQL for human/DBA review first.",
        )
    if ui_language == "en-US":
        return str(getattr(suggestion, "description", ""))
    descriptions = {
        "configure_data_store_env": "設定必要的資料庫環境變數，然後重新執行資料庫自檢。",
        "install_optional_driver_in_project_env": "把選用資料庫 driver 安裝在專案 Python 環境，不要裝到 base。",
        "fix_data_store_profile_mapping": "目前 SQL profile 指到的資料庫和 registry 期待的資料庫不同；請修正 profile/env 或資產歸屬資料。",
        "review_schema_drift": "比對 registry 記錄的 schema fingerprint 和實際資料庫結構，再決定要 migrate、重新匯入，或更新 registry fingerprint。",
        "restore_or_reimport_table": "這個納管資料表不存在；請從備份還原，或重新跑擁有這張表的匯入流程。",
        "restore_or_reimport_sqlite_database": "這個納管 SQLite 檔案不存在；請還原檔案，或重新跑建立它的匯入流程。",
        "test_data_store_connection": "先測試資料儲存連線，檢查 host、database、帳密、網路與 driver 相容性。",
        "implement_database_self_check_adapter": "這個資料庫引擎還沒有自檢 adapter；請新增 adapter，或先把此資產標成非納管。",
        "fix_registry_asset_kind": "registry 的資產種類不是 database self-check 支援的類型，請先修正資產 metadata。",
        "inspect_database_asset": "這個錯誤還沒有對應到明確修復規則；請先檢查資產紀錄、資料儲存 profile 與最新錯誤訊息。",
    }
    return descriptions.get(str(getattr(suggestion, "action_id", "")), str(getattr(suggestion, "description", "")))


def data_store_next_action_message(result: object, tr: Translator) -> str:
    """把 data-store tester 的 next_action 轉成人類可操作的下一步。"""

    # UI 顯示的是同一份 backend next_action 的人類版；避免 Tk 自己猜修復流程。
    action = data_store_connection_next_action(result)
    action_id = str(action.get("action_id") or "")
    if action_id == "write_env_template":
        return tr(
            "下一步：按「寫出 env 範本」，在本機填入環境變數後重新測試。",
            "Next: click Write env template, fill values locally, then rerun the test.",
        )
    if action_id == "install_optional_driver":
        return tr(
            "下一步：只在專案環境安裝選用資料庫 driver，然後重新測試。",
            "Next: install the optional database driver in the project environment only, then rerun the test.",
        )
    if action_id == "inspect_connection":
        return tr(
            "下一步：檢查 host、port、database、帳號權限、網路與 driver 相容性。",
            "Next: inspect host, port, database, user permissions, network reachability, and driver compatibility.",
        )
    if action_id == "reserved_profile":
        return tr(
            "下一步：這是保留 profile，目前只作 handoff，尚未實作 live tester。",
            "Next: this is a reserved profile for handoff; no live tester is implemented yet.",
        )
    return ""


def crawler_next_action_label(action: str, tr: Translator) -> str:
    """把 crawler audit next_action 穩定碼轉成 UI 下一步文字。"""

    # Crawler 後端輸出的是穩定狀態碼；Tk 只負責翻成使用者能採取的下一步，不在 UI 層重寫 audit 規則。
    labels = {
        "inspect_source_audit_results_before_upsert_or_promotion": tr(
            "先查看來源審核結果，再決定是否寫入候選或提升 catalog。",
            "Inspect source audit results before upserting candidates or promoting catalog entries.",
        ),
        "review_or_upsert_dataset_candidates": tr(
            "已有可信候選，接著開啟候選審核並加入下載計畫。",
            "Review or upsert the credible candidates, then add them to the download plan.",
        ),
        "configure_or_select_dataset_discovery_sources": tr(
            "尚無候選，請先設定或選取有 crawler 的資料源。",
            "No candidates were found; configure or select sources with crawler support first.",
        ),
        "inspect_crawler_error": tr(
            "Crawler 發生錯誤，請先檢查 endpoint、網路、權限或 parser 例外。",
            "The crawler errored; inspect the endpoint, network, access, or parser exception first.",
        ),
        "repair_crawler_query_or_parser": tr(
            "回傳 0 筆，請檢查搜尋詞、分頁停止條件或 parser 是否失準。",
            "Zero candidates were returned; check search terms, pagination stop rules, or parser mapping.",
        ),
        "adjust_query_or_min_expected_candidates": tr(
            "候選少於預期，請放寬查詢、調整最低筆數或確認 source 覆蓋範圍。",
            "Candidate count is below expectation; adjust the query, minimum count, or source coverage.",
        ),
        "review_source_overlap_or_dedupe": tr(
            "重複候選偏高，請檢查 source 重疊、dataset id mapping 或 pagination。",
            "Duplicate output is high; review source overlap, dataset id mapping, or pagination.",
        ),
        "repair_candidate_metadata_mapping": tr(
            "候選 metadata 缺欄，請修 dataset id、title、source URL 或 evidence mapping。",
            "Candidate metadata is incomplete; repair dataset id, title, source URL, or evidence mapping.",
        ),
        "inspect_crawler_audit_warnings": tr(
            "請查看 crawler warning 明細，再決定是否審核候選或修 parser。",
            "Inspect crawler warnings before reviewing candidates or repairing the parser.",
        ),
        "review_candidates": tr(
            "來源結果可審核，接著確認候選並加入下載計畫。",
            "Review the source candidates and add selected entries to the download plan.",
        ),
        "no_candidates_but_allowed": tr(
            "這個來源沒有候選但未被視為錯誤；請確認它是否應該產出資料集。",
            "This source returned no candidates without failing; confirm whether it should produce datasets.",
        ),
    }
    action = str(action or "").strip()
    if not action:
        return tr("查看 crawler 審核結果。", "Review crawler audit results.")
    return labels.get(action, tr("查看 crawler 審核結果。", "Review crawler audit results."))
