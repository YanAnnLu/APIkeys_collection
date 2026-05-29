from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from api_launcher.adapter_review import adapter_review_items
from api_launcher.crawler_asset_display import (
    crawler_asset_download_import_display_payload,
    crawler_asset_plan_outcome_payload,
    next_action_display_label,
)
from api_launcher.crawler_assets import CrawlerAsset
from api_launcher.downloads.staging import safe_path_part
from api_launcher.paths import default_local_downloads_root, state_file
from frontends.tk.crawler_asset_seed_dialog import crawler_seed_dialog_import_label


@dataclass(frozen=True)
class CrawlerSeedDownloadImportUiMessage:
    """Display-ready Tk message for one seed download/import completion."""

    succeeded: bool
    stage: str
    dataset_uid: str
    title: str
    status_message: str
    body: str


@dataclass(frozen=True)
class CrawlerSeedDownloadImportTargetPaths:
    """Filesystem targets for one Tk seed download/import worker."""

    downloads_root: Path
    import_sqlite_path: Path
    plan_path: Path


def crawler_seed_download_import_target_paths(
    asset_id: str,
    dataset_uid: str,
) -> CrawlerSeedDownloadImportTargetPaths:
    """Return stable Tk filesystem targets for one seed download/import job."""

    safe_asset = safe_path_part(asset_id)[:96]
    safe_seed = safe_path_part(dataset_uid)[:96]
    downloads_root = default_local_downloads_root() / "crawler_assets" / safe_asset / safe_seed
    return CrawlerSeedDownloadImportTargetPaths(
        downloads_root=downloads_root,
        import_sqlite_path=downloads_root / "curated_sources.db",
        plan_path=state_file(f"crawler_asset_seed_plans/{safe_asset}.{safe_seed}.resolved.json"),
    )


def crawler_asset_download_plan_summary_text(
    result: object,
    added_count: int,
    resolved_path: str,
    tr: Callable[[str, str], str],
) -> str:
    """Convert a backend plan outcome into the Tk download-plan message.

    The backend display payload owns bucket labels and next-action text. Tk
    only adds desktop-specific wording and optional resolved-plan path context.
    """

    bucket = str(getattr(result, "outcome_bucket", "") or "")
    direct = int(getattr(result, "direct_download_count", 0) or 0)
    review = int(getattr(result, "review_required_count", 0) or 0)
    blocked = bool(getattr(result, "blocked", False))
    blocked_reason = str(getattr(result, "blocked_reason", "") or "-")
    next_action = str(getattr(result, "user_next_action", "") or getattr(result, "next_action", "") or "-")
    outcome_payload = crawler_asset_plan_outcome_payload(result, added_count=added_count)
    next_action_label = str(outcome_payload.get("next_action_label") or next_action).strip()

    if blocked or bucket == "blocked":
        zh = f"這個爬蟲資產暫時不能建立下載計畫：{blocked_reason}。\n下一步：{next_action_label or next_action}"
        en = f"This crawler asset cannot build a download plan: {blocked_reason}.\nNext: {next_action_label or next_action}"
        return tr(zh, en)
    if bucket == "partial_review_required":
        zh = (
            f"已加入下載器 {added_count} 筆，可先展示或開始下載；另有 {review} 筆需要 Adapter 待辦。\n"
            "下一步：到下載器確認隊列，剩餘項目再進 Adapter review 或調整界域。"
        )
        en = (
            f"Added {added_count} item(s) to Downloader; {review} item(s) still need Adapter review.\n"
            "Next: confirm the queue in Downloader, then review adapters or adjust bounds."
        )
    elif bucket == "ready_to_download":
        zh = (
            f"已建立可下載計畫：直接下載 {direct} 筆，已加入下載器 {added_count} 筆。\n"
            "下一步：到下載器使用開始 / 暫停控制隊列。"
        )
        en = (
            f"Download plan is ready: direct {direct}, added {added_count} item(s) to Downloader.\n"
            "Next: use start / pause in Downloader."
        )
    elif bucket == "review_required":
        zh = (
            f"已建立計畫，但目前沒有可直接下載項目；{review} 筆需要 Adapter 待辦。\n"
            "下一步：開 Adapter review，或回到界域設定調整條件。"
        )
        en = (
            f"Plan built, but no direct downloads are ready; {review} item(s) require Adapter review.\n"
            "Next: open Adapter review or adjust bounds."
        )
    elif bucket == "zero_candidates":
        zh = "沒有找到符合界域的候選資料。\n下一步：放寬時間 / 空間 / 筆數條件，或先重新擷取清單。"
        en = "No candidates matched the selected bounds.\nNext: loosen time / spatial / limit bounds, or refresh the source listing."
    else:
        zh = "已建立下載計畫，但沒有可執行的下載項目。\n下一步：檢查 resolved plan，或調整界域後重試。"
        en = "Plan built, but no executable download item was produced.\nNext: inspect the resolved plan, or adjust bounds and retry."

    content_review_label = str(outcome_payload.get("content_review_label") or "").strip()
    if content_review_label:
        zh = f"{zh}\n內容格式待辦：{content_review_label}"
        en = f"{en}\nContent review: {content_review_label}"

    if resolved_path:
        zh = f"{zh}\n\nResolved plan：{resolved_path}"
        en = f"{en}\n\nResolved plan: {resolved_path}"
    return tr(zh, en)


def crawler_asset_listing_blocked_status_text(result: object, tr: Callable[[str, str], str]) -> str:
    """Render blocked listing status without leaking raw backend next_action ids."""

    blocked_reason = str(getattr(result, "blocked_reason", "") or "-").strip()
    next_action = str(getattr(result, "next_action", "") or "").strip()
    next_action_label = next_action_display_label(next_action) if next_action else ""
    zh = f"爬蟲資產暫停執行：{blocked_reason}；下一步：{next_action_label or '-'}"
    en = f"Crawler asset blocked: {blocked_reason}; next action: {next_action_label or '-'}"
    return tr(zh, en)


def crawler_asset_plan_outcome_label(result: object, added_count: int) -> str:
    """Return the compact Tk table label for a backend plan outcome."""

    payload = crawler_asset_plan_outcome_payload(result, added_count=added_count)
    short_label = str(payload.get("short_label") or "").strip()
    return short_label or str(payload.get("display_label") or "需檢查")


def crawler_asset_plan_passport_summary_text(
    plan_passport: object,
    tr: Callable[[str, str], str],
) -> str:
    """Render a compact plan passport into the Tk crawler-asset sidebar."""

    if not isinstance(plan_passport, dict) or not plan_passport:
        return ""
    candidates = _plan_passport_count(plan_passport.get("candidate_count"))
    direct = _plan_passport_count(plan_passport.get("direct_download_count"))
    review = _plan_passport_count(plan_passport.get("review_required_count"))
    adapter = _plan_passport_count(plan_passport.get("adapter_review_count"))
    content = _plan_passport_count(plan_passport.get("content_review_count"))
    credentials = _plan_passport_count(plan_passport.get("blocked_credential_count"))
    missing = _plan_passport_count(plan_passport.get("missing_provider_count"))
    has_plan = bool(plan_passport.get("has_resolved_plan"))
    is_stale = bool(plan_passport.get("stale"))
    snapshot_changed = bool(plan_passport.get("candidate_snapshot_changed"))
    stale_reason = str(plan_passport.get("stale_reason") or "profile_changed").strip()
    stale_label = str(plan_passport.get("stale_label") or "").strip()
    stale_next_action = str(plan_passport.get("stale_next_action") or "").strip()
    state_zh = "resolved plan 已建立" if has_plan else "resolved plan 尚未建立"
    state_en = "resolved plan available" if has_plan else "resolved plan unavailable"
    zh = (
        f"Plan Passport：{state_zh}；候選 {candidates}；可下載 {direct}；待 Adapter {review}；"
        f"Adapter 佇列 {adapter}；內容待辦 {content}"
    )
    en = (
        f"Plan Passport: {state_en}; candidates {candidates}; direct {direct}; review {review}; "
        f"adapter {adapter}; content {content}"
    )
    if credentials or missing:
        zh = f"{zh}；憑證阻擋 {credentials}；缺 Provider {missing}"
        en = f"{en}; credentials blocked {credentials}; missing providers {missing}"
    if is_stale:
        zh = f"{zh}；狀態可能過期：{stale_label or stale_reason}"
        en = f"{en}; stale {stale_next_action or stale_reason}"
    if snapshot_changed:
        zh = f"{zh}；候選快照已變更"
        en = f"{en}; candidate snapshot changed"
    return tr(zh, en)


def _plan_passport_count(value: object) -> int:
    """Old events may contain non-numeric counts; keep Tk summaries tolerant."""

    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def crawler_asset_credential_guard_message(
    credential_guard: object,
    tr: Callable[[str, str], str],
) -> str:
    """Translate backend credential guard payload into a Tk-safe prompt."""

    guard = credential_guard if isinstance(credential_guard, dict) else {}
    display_profile = guard.get("display_profile") if isinstance(guard.get("display_profile"), dict) else {}
    label = str(display_profile.get("label") or guard.get("display_label") or "需要登入 / API Key").strip()
    provider_name = str(guard.get("provider_name") or guard.get("provider_id") or "").strip()
    missing = guard.get("missing_required") if isinstance(guard.get("missing_required"), list) else []
    missing_text = ", ".join(str(item) for item in missing if str(item).strip()) or "-"
    next_action = str(guard.get("next_action") or "edit_local_credentials_before_live_download").strip()
    next_action_zh = str(
        guard.get("next_action_label_zh_TW")
        or display_profile.get("next_action_label_zh_TW")
        or display_profile.get("next_action_label")
        or next_action
    ).strip()
    next_action_en = str(
        guard.get("next_action_label_en")
        or display_profile.get("next_action_label_en")
        or next_action
    ).strip()
    entry_label = str(guard.get("credential_entry_label") or "").strip()
    zh_lines = [
        f"{label}。",
        f"來源：{provider_name or '-'}",
        f"缺少欄位：{missing_text}",
        "請先完成登入設定；如果需要 API Key，請到官方入口申請後再回來下載。",
        f"下一步：{next_action_zh or next_action}",
    ]
    if entry_label:
        zh_lines.append(f"可用入口：{entry_label}")
    en_lines = [
        f"{label}.",
        f"Source: {provider_name or '-'}",
        f"Missing fields: {missing_text}",
        "Finish login settings first. If an API key is required, get it from the official portal before downloading.",
        f"Next action: {next_action_en or next_action}",
    ]
    if entry_label:
        en_lines.append(f"Available entry: {entry_label}")
    return tr("\n".join(zh_lines), "\n".join(en_lines))


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
    raw_callback_diagnostics = display_payload.get("callback_diagnostics")
    callback_diagnostics = raw_callback_diagnostics if isinstance(raw_callback_diagnostics, dict) else {}
    callback_count = int(callback_diagnostics.get("count") or download_import.get("callback_error_count") or 0)
    callback_label = str(callback_diagnostics.get("display_label") or "").strip()
    callback_next_action = str(callback_diagnostics.get("next_action_label") or callback_diagnostics.get("summary") or "").strip()
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
    if callback_count:
        body += "\n" + tr(
            f"\n進度回報：{callback_label or '進度回報有警告'} ({callback_count})\n建議：{callback_next_action or '檢查事件紀錄或 UI 進度回報'}",
            f"\nProgress callback: {callback_label or 'callback warning'} ({callback_count})\nNext: {callback_next_action or 'Inspect event logs or UI progress callbacks'}",
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


def crawler_asset_review_count_from_plan(payload: object) -> int:
    """Count adapter-review items in a resolved plan for compact Tk labels."""

    if not isinstance(payload, dict):
        return 0
    return len(adapter_review_items(payload))


def crawler_asset_seed_page_status_text(
    payload: object,
    tr: Callable[[str, str], str],
) -> str:
    """Render the shared seed-page payload into a Tk status-bar message."""

    if not isinstance(payload, dict):
        return tr("尚未讀取 seed 清單。", "No seed page loaded.")
    summary = payload.get("page_summary") if isinstance(payload.get("page_summary"), dict) else {}
    total = int(payload.get("total") or 0)
    shown_start = int(summary.get("shown_start") or 0)
    shown_end = int(summary.get("shown_end") or 0)
    remaining = int(summary.get("remaining") or 0)
    if total <= 0:
        return tr("本機 catalog 目前沒有這個入口的 seed；請先執行清單擷取。", "No seeds for this source in the local catalog yet; run listing first.")
    if remaining:
        return tr(
            f"Seed 清單：顯示第 {shown_start}-{shown_end} 筆，共 {total} 筆；還有 {remaining} 筆可展開。",
            f"Seed page: showing {shown_start}-{shown_end} of {total}; {remaining} remaining.",
        )
    return tr(
        f"Seed 清單：顯示第 {shown_start}-{shown_end} 筆，共 {total} 筆；已到最後一頁。",
        f"Seed page: showing {shown_start}-{shown_end} of {total}; final page.",
    )


def crawler_asset_seed_page_preview_text(
    payload: object,
    tr: Callable[[str, str], str],
    *,
    preview_limit: int = 8,
    listing_outcome: object | None = None,
) -> str:
    """Render a seed-page payload into the Tk sidebar preview.

    The paging window and completeness semantics stay in the backend seed
    registry.  Tk only projects that payload into a compact text preview.
    """

    listing_note = crawler_asset_seed_enumeration_note_text(listing_outcome, tr)
    if not isinstance(payload, dict):
        base = tr("尚未讀取 seed。先執行清單擷取，再查看本機 seed 視窗。", "No seed page loaded yet. Run listing first, then inspect local seeds.")
        return f"{listing_note}\n\n{base}" if listing_note else base
    seeds = payload.get("seeds") if isinstance(payload.get("seeds"), list) else []
    status = crawler_asset_seed_page_status_text(payload, tr)
    if not seeds:
        return f"{status}\n\n{listing_note}" if listing_note else status
    lines: list[str] = [status, ""]
    if listing_note:
        lines.extend([listing_note, ""])
    for index, row in enumerate(seeds[: max(1, preview_limit)], start=1):
        if not isinstance(row, dict):
            continue
        favorite = "★ " if row.get("favorite") else ""
        title = str(row.get("title") or row.get("dataset_id") or row.get("dataset_uid") or "-").strip()
        native_format = str(row.get("native_format") or row.get("data_type") or "").strip()
        version = str(row.get("version") or "").strip()
        import_label = crawler_seed_dialog_import_label(row)
        suffix_parts = [part for part in (native_format, version, import_label) if part]
        suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""
        lines.append(f"{index:02d}. {favorite}{title}{suffix}")
    remaining_on_page = max(0, len(seeds) - preview_limit)
    if remaining_on_page:
        lines.append(tr(f"...本頁另有 {remaining_on_page} 筆", f"...{remaining_on_page} more on this page"))
    if payload.get("has_more"):
        lines.append(tr("按「顯示更多 Seed」展開下一批。", "Use Show more seeds for the next page."))
    return "\n".join(lines)


def crawler_asset_credential_badge_label(credential_status: object) -> str:
    """Return the short credential label used in the crawler asset table."""

    status = credential_status if isinstance(credential_status, dict) else {}
    badge = str(status.get("display_badge_label") or "").strip()
    if badge:
        return badge
    label = str(status.get("display_label") or "").strip()
    configured = int(status.get("configured_count") or 0)
    total = int(status.get("field_count") or 0)
    if label and total:
        return f"{label} {configured}/{total}"
    return label or "免登入"


def crawler_asset_credential_summary_text(
    credential_status: object,
    tr: Callable[[str, str], str],
) -> str:
    """Render credential status from the backend UI-safe payload.

    Tk may describe status and next action, but it must not inspect raw secrets
    or duplicate credential-blocking policy.  Those rules stay in
    ``api_launcher.local_credentials``.
    """

    status = credential_status if isinstance(credential_status, dict) else {}
    display_profile = status.get("display_profile") if isinstance(status.get("display_profile"), dict) else {}
    summary_zh = str(status.get("display_summary_zh_TW") or "").strip()
    summary_en = str(status.get("display_summary_en") or "").strip()
    if summary_zh or summary_en:
        return tr(summary_zh or summary_en, summary_en or summary_zh)
    label = str(status.get("display_label") or "免登入").strip()
    configured = int(status.get("configured_count") or 0)
    total = int(status.get("field_count") or 0)
    next_action = str(status.get("next_action") or "").strip()
    next_action_zh = str(
        status.get("next_action_label_zh_TW")
        or display_profile.get("next_action_label_zh_TW")
        or display_profile.get("next_action_label")
        or next_action
    ).strip()
    next_action_en = str(
        status.get("next_action_label_en")
        or display_profile.get("next_action_label_en")
        or next_action
    ).strip()
    missing = status.get("missing_required") if isinstance(status.get("missing_required"), list) else []
    missing_text = ", ".join(str(item) for item in missing if str(item).strip())
    if total:
        zh = f"登入：{label}（{configured}/{total}）"
        en = f"Login: {label} ({configured}/{total})"
    else:
        zh = f"登入：{label}"
        en = f"Login: {label}"
    if missing_text:
        zh = f"{zh}；缺少 {missing_text}"
        en = f"{en}; missing {missing_text}"
    if next_action_zh or next_action_en:
        zh = f"{zh}；下一步：{next_action_zh or next_action}"
        en = f"{en}; next: {next_action_en or next_action}"
    return tr(zh, en)


def crawler_asset_credential_event_context(asset: CrawlerAsset, credential_status: object) -> dict[str, object]:
    """Return a sanitized event payload for credential changes.

    This intentionally excludes raw field values.  Event logs should only show
    status, counts, and field names so local secrets never leak into JSONL.
    """

    status = credential_status if isinstance(credential_status, dict) else {}
    fields = status.get("fields") if isinstance(status.get("fields"), list) else []
    field_names = [
        str(field.get("env_var") or "")
        for field in fields
        if isinstance(field, dict) and str(field.get("env_var") or "").strip()
    ]
    return {
        "asset_id": asset.asset_id,
        "provider_id": asset.provider_id,
        "status": str(status.get("status") or ""),
        "display_label": str(status.get("display_label") or ""),
        "configured_count": int(status.get("configured_count") or 0),
        "field_count": int(status.get("field_count") or 0),
        "missing_required": list(status.get("missing_required") or []),
        "field_names": field_names,
        "remember_local": bool(status.get("remember_local")),
        "next_action": str(status.get("next_action") or ""),
    }


def crawler_asset_listing_event_preview_payload(context: object) -> dict[str, object]:
    """Keep only listing fields that Tk needs to explain seed enumeration state."""

    if not isinstance(context, dict):
        return {}
    seed_enumeration = context.get("seed_enumeration") if isinstance(context.get("seed_enumeration"), dict) else {}
    remote_pagination = context.get("remote_pagination") if isinstance(context.get("remote_pagination"), dict) else {}
    return {
        "asset_id": str(context.get("asset_id") or ""),
        "candidate_count": int(context.get("candidate_count") or 0),
        "upserted_count": int(context.get("upserted_count") or 0),
        "warning_count": int(context.get("warning_count") or 0),
        "error_count": int(context.get("error_count") or 0),
        "max_results": int(context.get("max_results") or 0),
        "complete_seed": bool(context.get("complete_seed")),
        "next_action": str(context.get("next_action") or ""),
        "seed_enumeration": dict(seed_enumeration),
        "remote_pagination": dict(remote_pagination),
    }


def crawler_asset_seed_enumeration_note_text(
    listing_outcome: object,
    tr: Callable[[str, str], str],
) -> str:
    """Render backend seed-enumeration confidence without exposing raw pagination tokens."""

    if not isinstance(listing_outcome, dict):
        return ""
    enumeration = listing_outcome.get("seed_enumeration") if isinstance(listing_outcome.get("seed_enumeration"), dict) else {}
    remote = enumeration.get("remote_pagination") if isinstance(enumeration.get("remote_pagination"), dict) else {}
    if not remote:
        remote = listing_outcome.get("remote_pagination") if isinstance(listing_outcome.get("remote_pagination"), dict) else {}
    label = str(enumeration.get("label") or "").strip()
    help_text = str(enumeration.get("help") or "").strip()
    status = str(remote.get("status") or "").strip()
    exhausted = remote.get("exhausted")
    token_present = bool(remote.get("next_page_token_present"))
    if status == "has_more":
        remote_text = tr(
            "遠端狀態：crawler 回報還有下一頁線索；token 已由後端遮蔽。",
            "Remote status: crawler reported another page; token is hidden by the backend.",
        )
    elif status == "exhausted" or exhausted is True:
        remote_text = tr(
            "遠端狀態：crawler 回報已列完。",
            "Remote status: crawler reported that the remote listing is exhausted.",
        )
    elif status and status != "not_reported":
        remote_text = tr(
            f"遠端狀態：{status}。",
            f"Remote status: {status}.",
        )
    elif token_present:
        remote_text = tr(
            "遠端狀態：偵測到下一頁線索；token 已由後端遮蔽。",
            "Remote status: detected another page; token is hidden by the backend.",
        )
    else:
        remote_text = tr(
            "遠端完整度：這個 handler 尚未回報，只能依本機 catalog 視窗判斷。",
            "Remote completeness: this handler has not reported it; rely on the local catalog window.",
        )
    lines = [part for part in (label, help_text, remote_text) if part]
    return "\n".join(lines)


def crawler_asset_state_label(asset: CrawlerAsset) -> str:
    """Return the compact state label for the crawler asset table and passport."""

    if getattr(asset, "health", None) is not None:
        code = asset.health.status_code
        labels = {
            "archived": "封存",
            "disabled": "停用",
            "missing_handler": "待實作",
            "needs_bounds": "需界域",
            "review_needed": "待審",
            "healthy": "可用",
            "unknown": "未知",
        }
        return f"{asset.health.status_emoji} {labels.get(code, code)}"
    if asset.archived:
        return "📦 封存"
    if not asset.enabled:
        return "⏸ 停用"
    if asset.risk_tier == "needs_handler":
        return "⚙️ 待補"
    if asset.risk_tier == "needs_review":
        return "🟡 待審"
    return "🟢 啟用"
