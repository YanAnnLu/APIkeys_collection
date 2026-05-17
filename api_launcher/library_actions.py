from __future__ import annotations

import dataclasses
from typing import Literal


ActionRisk = Literal["safe", "state_change", "destructive"]


@dataclasses.dataclass(frozen=True)
class LibraryContext:
    provider_id: str
    local_status: str = "not_imported"
    remote_status: str = "unchecked"
    update_status: str = "unknown"
    install_id: str = ""
    manifest_health: str = "unknown"
    has_direct_download: bool = False
    has_adapter: bool = False
    has_render_assets: bool = False

    @property
    def is_installed(self) -> bool:
        return bool(self.install_id) and self.local_status in {"downloaded", "managed", "installed", "present"}


@dataclasses.dataclass(frozen=True)
class LibraryAction:
    action_id: str
    label: str
    enabled: bool
    reason: str
    risk: ActionRisk = "safe"


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
    downloadable = context.has_direct_download or context.has_adapter
    installed = context.is_installed
    needs_repair = context.manifest_health in {"missing", "checksum_mismatch", "size_mismatch", "error"}
    update_available = context.update_status in {"available", "stale", "upgrade_available", "newer_remote"}

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
            "Manifest health indicates missing or corrupted assets." if installed and needs_repair else "No repair issue is known.",
            risk="state_change",
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
    actions = library_action_map(context)
    return tuple(actions[action_id] for action_id in action_ids if action_id in actions)


def library_action_menu_label(action: LibraryAction, include_disabled_reason: bool = True, max_reason_chars: int = 56) -> str:
    if action.enabled or not include_disabled_reason or not action.reason:
        return action.label
    reason = action.reason
    if len(reason) > max_reason_chars:
        reason = f"{reason[: max_reason_chars - 1]}..."
    return f"{action.label} - {reason}"


def enabled_action_ids(context: LibraryContext) -> tuple[str, ...]:
    return tuple(action.action_id for action in build_library_actions(context) if action.enabled)


def library_action_agent_payload(context: LibraryContext) -> dict[str, object]:
    actions = build_library_actions(context)
    return {
        "provider_id": context.provider_id,
        "context": dataclasses.asdict(context),
        "enabled_action_ids": [action.action_id for action in actions if action.enabled],
        "actions": [dataclasses.asdict(action) for action in actions],
    }
