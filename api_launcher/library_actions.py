from __future__ import annotations

import dataclasses
from dataclasses import field
from typing import Literal


ActionRisk = Literal["safe", "state_change", "destructive"]
REPAIRABLE_MANIFEST_HEALTH = {"missing", "checksum_mismatch", "size_mismatch", "manifest_error", "error"}


@dataclasses.dataclass(frozen=True)
class LibraryContext:
    # context 將 UI 狀態壓成 action policy 所需欄位，避免右鍵選單自行猜行為。
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


def build_library_actions(context: LibraryContext) -> tuple[LibraryAction, ...]:
    # 所有 UI/agent 可執行動作都從這裡推導，避免不同入口各自判斷 install/update/repair。
    downloadable = context.has_direct_download or context.has_adapter
    installed = context.is_installed
    needs_repair = context.manifest_health in REPAIRABLE_MANIFEST_HEALTH
    update_available = context.update_status in {"available", "stale", "upgrade_available", "newer_remote"}
    repair_suggestion = dict(context.repair_suggestion or {})
    repair_action_id = str(repair_suggestion.get("action_id") or "")
    repair_can_requeue = bool(repair_suggestion.get("can_requeue"))
    # repair reason 優先說明「能不能安全重排下載」，因為這決定是否可自動化。
    if needs_repair and repair_can_requeue:
        repair_reason = "Manifest repair stream has a safe requeue plan."
    elif needs_repair and repair_action_id:
        repair_reason = f"Manifest repair stream suggests {repair_action_id}."
    elif needs_repair:
        repair_reason = "Manifest health indicates missing or corrupted assets."
    else:
        repair_reason = "No repair issue is known."

    return (
        LibraryAction(
            "add_to_plan",
            "Add to download plan",
            downloadable,
            "A direct download or dataset adapter is available." if downloadable else "No direct download or adapter is available yet.",
        ),
        LibraryAction(
            "install",
            "Install / manage",
            downloadable and not installed,
            "Ready to download/import into the managed library." if downloadable and not installed else "Already installed or not downloadable.",
            risk="state_change",
        ),
        LibraryAction(
            "update",
            "Update",
            installed and update_available,
            "A newer or stale remote version is available." if installed and update_available else "No applicable update is known.",
            risk="state_change",
        ),
        LibraryAction(
            "repair",
            "Repair / verify",
            installed and needs_repair,
            repair_reason if installed and needs_repair else "No repair issue is known.",
            risk="state_change",
            related_repair_suggestion=repair_suggestion,
        ),
        LibraryAction(
            "open_database",
            "Open in database tool",
            installed,
            "Managed local data exists." if installed else "No managed local installation is known.",
        ),
        LibraryAction(
            "render_preview",
            "Render preview",
            installed and context.has_render_assets,
            "Renderer bridge assets are available." if installed and context.has_render_assets else "Renderer bridge assets are not available yet.",
        ),
        LibraryAction(
            "uninstall",
            "Uninstall / remove from library",
            installed,
            "Managed install_id exists; destructive execution still requires guarded adapters." if installed else "Nothing managed to uninstall.",
            risk="destructive",
        ),
    )


def library_action_map(context: LibraryContext) -> dict[str, LibraryAction]:
    return {action.action_id: action for action in build_library_actions(context)}


def ordered_library_actions(
    context: LibraryContext,
    action_ids: tuple[str, ...] = DEFAULT_LIBRARY_ACTION_ORDER,
) -> tuple[LibraryAction, ...]:
    # action order 由呼叫端指定；政策仍由 build_library_actions 統一產生。
    actions = library_action_map(context)
    return tuple(actions[action_id] for action_id in action_ids if action_id in actions)


def library_action_menu_label(action: LibraryAction, include_disabled_reason: bool = True, max_reason_chars: int = 56) -> str:
    # disabled reason 截短後放進選單，讓使用者知道為什麼按鈕目前不能用。
    if action.enabled or not include_disabled_reason or not action.reason:
        return action.label
    reason = action.reason
    if len(reason) > max_reason_chars:
        reason = f"{reason[: max_reason_chars - 1]}..."
    return f"{action.label} - {reason}"


def enabled_action_ids(context: LibraryContext) -> tuple[str, ...]:
    return tuple(action.action_id for action in build_library_actions(context) if action.enabled)


def library_action_agent_payload(context: LibraryContext) -> dict[str, object]:
    # agent payload 保留完整 context/action 表，避免自動化流程重建 UI 私有規則。
    actions = build_library_actions(context)
    return {
        "provider_id": context.provider_id,
        "context": dataclasses.asdict(context),
        "enabled_action_ids": [action.action_id for action in actions if action.enabled],
        "actions": [dataclasses.asdict(action) for action in actions],
    }
