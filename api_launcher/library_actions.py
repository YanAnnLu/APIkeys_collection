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


def enabled_action_ids(context: LibraryContext) -> tuple[str, ...]:
    return tuple(action.action_id for action in build_library_actions(context) if action.enabled)
