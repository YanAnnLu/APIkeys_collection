from __future__ import annotations

from typing import Callable

from api_launcher.adapter_review import adapter_review_items
from api_launcher.crawler_assets import CrawlerAsset
from frontends.tk.crawler_asset_seed_dialog import crawler_seed_dialog_import_label


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
