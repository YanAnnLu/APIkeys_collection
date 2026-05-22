from __future__ import annotations

import dataclasses
from dataclasses import field
from typing import Literal


ActionRisk = Literal["safe", "state_change", "destructive"]
REPAIRABLE_MANIFEST_HEALTH = {"missing", "checksum_mismatch", "size_mismatch", "manifest_error", "error"}


@dataclasses.dataclass(frozen=True)
class LibraryContext:
    # UI、CLI 與 agent 都只提供這個 context；真正的 action 規則集中在本模組，避免各端重寫判斷。
    provider_id: str
    local_status: str = "not_imported"
    remote_status: str = "unchecked"
    update_status: str = "unknown"
    install_id: str = ""
    manifest_health: str = "unknown"
    manifest_path: str = ""
    repair_suggestion: dict[str, object] = field(default_factory=dict)
    has_direct_download: bool = False
    has_adapter: bool = False
    has_render_assets: bool = False

    @property
    def is_installed(self) -> bool:
        return bool(self.install_id) and self.local_status in {"downloaded", "imported", "managed", "installed", "present"}


@dataclasses.dataclass(frozen=True)
class LibraryAction:
    action_id: str
    label: str
    enabled: bool
    reason: str
    status_badge: str
    risk: ActionRisk = "safe"
    related_repair_suggestion: dict[str, object] = field(default_factory=dict)


DEFAULT_LIBRARY_ACTION_ORDER = (
    "add_to_plan",
    "install",
    "update",
    "repair",
    "open_database",
    "render_preview",
    "uninstall",
)

STATUS_BADGE_LABELS_ZH_TW = {
    "ready_to_plan": "可加入計畫",
    "blocked_no_download_or_adapter": "需解析下載方式",
    "already_installed": "已安裝",
    "ready_to_install": "可安裝",
    "update_available": "可更新",
    "up_to_date": "已是最新",
    "not_installed": "未安裝",
    "repair_requeue_ready": "可重排修復",
    "repair_review_needed": "需審核修復",
    "repair_needed": "需修復",
    "healthy_or_unknown": "健康或未知",
    "ready_to_open": "可開啟",
    "missing_render_assets": "缺少渲染資產",
    "render_ready": "可預覽渲染",
    "guarded_uninstall_ready": "可受控移除",
}

STATUS_BADGE_LABELS_EN_US = {
    "ready_to_plan": "Ready to plan",
    "blocked_no_download_or_adapter": "Needs download resolver",
    "already_installed": "Installed",
    "ready_to_install": "Ready to install",
    "update_available": "Update available",
    "up_to_date": "Up to date",
    "not_installed": "Not installed",
    "repair_requeue_ready": "Repair requeue ready",
    "repair_review_needed": "Repair review needed",
    "repair_needed": "Repair needed",
    "healthy_or_unknown": "Healthy or unknown",
    "ready_to_open": "Ready to open",
    "missing_render_assets": "Missing render assets",
    "render_ready": "Render ready",
    "guarded_uninstall_ready": "Guarded uninstall ready",
}


def library_action_status_badge_label(status_badge: str, language: str = "zh-TW") -> str:
    # badge 代碼保留給 JSON/agent routing；UI 只透過這個 helper 取得人類可讀短標籤。
    labels = STATUS_BADGE_LABELS_EN_US if language == "en-US" else STATUS_BADGE_LABELS_ZH_TW
    return labels.get(status_badge, status_badge)


def build_library_actions(context: LibraryContext) -> tuple[LibraryAction, ...]:
    # action policy 是資料資產右鍵選單與 CLI JSON 的共同來源，修改時要同時考慮 UI 與 agent 可解析性。
    downloadable = context.has_direct_download or context.has_adapter
    installed = context.is_installed
    needs_repair = context.manifest_health in REPAIRABLE_MANIFEST_HEALTH
    update_available = context.update_status in {"available", "stale", "upgrade_available", "newer_remote"}
    repair_suggestion = dict(context.repair_suggestion or {})
    repair_action_id = str(repair_suggestion.get("action_id") or "")
    repair_can_requeue = bool(repair_suggestion.get("can_requeue"))

    # repair reason 先說明可走哪一種修復路徑；真正能不能執行仍交給 guarded repair command 判斷。
    if needs_repair and repair_can_requeue:
        repair_reason = "Manifest repair stream has a safe requeue plan."
    elif needs_repair and repair_action_id:
        repair_reason = f"Manifest repair stream suggests {repair_action_id}."
    elif needs_repair:
        repair_reason = "Manifest health indicates missing or corrupted assets."
    else:
        repair_reason = "No repair issue is known."

    # status_badge 是短狀態碼，給 UI 徽章、agent routing、日後 action filter 共用。
    add_to_plan_badge = "ready_to_plan" if downloadable else "blocked_no_download_or_adapter"
    install_badge = "already_installed" if installed else ("ready_to_install" if downloadable else "blocked_no_download_or_adapter")
    update_badge = "update_available" if installed and update_available else ("up_to_date" if installed else "not_installed")
    if installed and needs_repair and repair_can_requeue:
        repair_badge = "repair_requeue_ready"
    elif installed and needs_repair and repair_action_id:
        repair_badge = "repair_review_needed"
    elif installed and needs_repair:
        repair_badge = "repair_needed"
    else:
        repair_badge = "healthy_or_unknown" if installed else "not_installed"
    open_database_badge = "ready_to_open" if installed else "not_installed"
    render_badge = "render_ready" if installed and context.has_render_assets else ("missing_render_assets" if installed else "not_installed")
    uninstall_badge = "guarded_uninstall_ready" if installed else "not_installed"

    return (
        LibraryAction(
            "add_to_plan",
            "Add to download plan",
            downloadable,
            "A direct download or dataset adapter is available." if downloadable else "No direct download or adapter is available yet.",
            add_to_plan_badge,
        ),
        LibraryAction(
            "install",
            "Install / manage",
            downloadable and not installed,
            "Ready to download/import into the managed library." if downloadable and not installed else "Already installed or not downloadable.",
            install_badge,
            risk="state_change",
        ),
        LibraryAction(
            "update",
            "Update",
            installed and update_available,
            "A newer or stale remote version is available." if installed and update_available else "No applicable update is known.",
            update_badge,
            risk="state_change",
        ),
        LibraryAction(
            "repair",
            "Repair / verify",
            installed and needs_repair,
            repair_reason if installed and needs_repair else "No repair issue is known.",
            repair_badge,
            risk="state_change",
            related_repair_suggestion=repair_suggestion,
        ),
        LibraryAction(
            "open_database",
            "Open in database tool",
            installed,
            "Managed local data exists." if installed else "No managed local installation is known.",
            open_database_badge,
        ),
        LibraryAction(
            "render_preview",
            "Render preview",
            installed and context.has_render_assets,
            "Renderer bridge assets are available." if installed and context.has_render_assets else "Renderer bridge assets are not available yet.",
            render_badge,
        ),
        LibraryAction(
            "uninstall",
            "Uninstall / remove from library",
            installed,
            "Managed install_id exists; destructive execution still requires guarded adapters." if installed else "Nothing managed to uninstall.",
            uninstall_badge,
            risk="destructive",
        ),
    )


def library_action_map(context: LibraryContext) -> dict[str, LibraryAction]:
    return {action.action_id: action for action in build_library_actions(context)}


def ordered_library_actions(
    context: LibraryContext,
    action_ids: tuple[str, ...] = DEFAULT_LIBRARY_ACTION_ORDER,
) -> tuple[LibraryAction, ...]:
    # 順序由共用常數控制，避免 Tk menu、CLI、agent payload 各自排出不同操作順序。
    actions = library_action_map(context)
    return tuple(actions[action_id] for action_id in action_ids if action_id in actions)


def library_action_menu_label(
    action: LibraryAction,
    include_disabled_reason: bool = True,
    max_reason_chars: int = 56,
    include_status_badge: bool = False,
    badge_language: str = "zh-TW",
) -> str:
    # menu label 是 UI 的最後一哩路；disabled reason 說明為何不能按，badge 讓使用者先看到狀態分類。
    label = action.label
    if not action.enabled and include_disabled_reason and action.reason:
        reason = action.reason
        if len(reason) > max_reason_chars:
            reason = f"{reason[: max_reason_chars - 1]}..."
        label = f"{label} - {reason}"
    if include_status_badge and action.status_badge:
        label = f"{label} [{library_action_status_badge_label(action.status_badge, badge_language)}]"
    return label


def enabled_action_ids(context: LibraryContext) -> tuple[str, ...]:
    return tuple(action.action_id for action in build_library_actions(context) if action.enabled)


def library_action_agent_payload(context: LibraryContext) -> dict[str, object]:
    # agent payload 保留完整 context/action，讓外部工具不用猜 UI 狀態或重建 policy。
    actions = build_library_actions(context)
    return {
        "provider_id": context.provider_id,
        "context": dataclasses.asdict(context),
        "enabled_action_ids": [action.action_id for action in actions if action.enabled],
        "actions": [dataclasses.asdict(action) for action in actions],
    }
