from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from api_launcher.paths import PROJECT_ROOT


SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "state", "downloads"}
PYTHON_LINE_LIMIT = 600


@dataclass(frozen=True)
class WorkspaceInventory:
    # workspace inventory 是整理/交接用快照，不應被當成強制刪檔清單。
    root: str
    category_counts: dict[str, int]
    large_python_files: tuple[dict[str, object], ...]
    root_runtime_files: tuple[str, ...]
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "root": self.root,
            "category_counts": self.category_counts,
            "large_python_files": list(self.large_python_files),
            "root_runtime_files": list(self.root_runtime_files),
            "notes": list(self.notes),
        }


def build_workspace_inventory(root: str | Path = PROJECT_ROOT) -> WorkspaceInventory:
    # inventory 排除 runtime/venv/cache，專注在 repo 結構與可維護性風險。
    root = Path(root)
    files = sorted(iter_workspace_files(root), key=lambda path: relative_path(path, root))
    category_counts = Counter(category_for_path(path, root) for path in files)
    large_python_files = tuple(
        sorted(large_python_file_items(files, root), key=lambda item: int(item["line_count"]), reverse=True)
    )
    root_runtime_files = tuple(
        relative_path(path, root)
        for path in files
        if path.parent == root and looks_like_runtime_root_file(path)
    )
    return WorkspaceInventory(
        root=str(root),
        category_counts=dict(sorted(category_counts.items())),
        large_python_files=large_python_files,
        root_runtime_files=root_runtime_files,
        notes=(
            "Do not move files automatically from this report; use it as a handoff/cleanup checklist.",
            "Runtime output should stay in ignored state/ or downloads/ unless a compatibility wrapper requires root placement.",
            "Large Python files should be split by stable subsystem boundaries, not by arbitrary line count alone.",
        ),
    )


def iter_workspace_files(root: Path) -> tuple[Path, ...]:
    pending = [root]
    files: list[Path] = []
    while pending:
        current = pending.pop()
        try:
            children = sorted(current.iterdir(), key=lambda path: path.name)
        except OSError:
            continue
        for child in children:
            if child.is_dir():
                if child.name not in SKIP_DIRS:
                    pending.append(child)
                continue
            if child.is_file() and not should_skip(child, root):
                files.append(child)
    return tuple(files)


def large_python_file_items(files: tuple[Path, ...], root: Path) -> tuple[dict[str, object], ...]:
    items: list[dict[str, object]] = []
    for path in files:
        if path.suffix != ".py":
            continue
        lines = line_count(path)
        if lines >= PYTHON_LINE_LIMIT:
            items.append(
                {
                    "path": relative_path(path, root),
                    "line_count": lines,
                    "suggestion": split_suggestion(path, root),
                }
            )
    return tuple(items)


def should_skip(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(part in SKIP_DIRS for part in parts)


def category_for_path(path: Path, root: Path) -> str:
    rel = path.relative_to(root)
    first = rel.parts[0]
    if first == "api_launcher":
        return api_launcher_category(rel)
    if first == "frontends":
        return "frontend"
    if first == "renderers":
        return "renderer"
    if first == "tests":
        return "tests"
    if first == "docs":
        return "docs"
    if first == "catalog":
        return "catalog"
    if first == "config":
        return "config"
    if first == "scripts":
        return "scripts"
    if path.parent == root:
        return "root_compat_or_project"
    return "other"


def api_launcher_category(rel: Path) -> str:
    parts = rel.parts
    if len(parts) > 1 and parts[1] in {"adapters", "crawlers", "downloads", "importers"}:
        return f"api_launcher/{parts[1]}"
    filename = rel.name
    if filename.startswith("cli_"):
        return "api_launcher/cli"
    if filename in {"core.py", "repository.py", "db.py", "models.py", "paths.py", "registry.py"}:
        return "api_launcher/core_infra"
    if filename in {"handoff.py", "event_log.py", "environment.py"}:
        return "api_launcher/ops"
    if filename in {"integrations.py", "google_auth.py", "oauth_device.py", "account_links.py", "ai_api_keys.py", "ai_prompts.py"}:
        return "api_launcher/integrations"
    return "api_launcher/domain"


def line_count(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return 0


def split_suggestion(path: Path, root: Path) -> str:
    rel = relative_path(path, root)
    if rel == "frontends/tk/launcher_ui.py":
        return "Split into view panels/dialogs after backend MVP; keep Tk as a thin caller of api_launcher services."
    if rel == "api_launcher/core.py":
        return "Move more CLI command groups into api_launcher/cli_*.py modules; keep CatalogLauncherCli orchestration only."
    if rel == "api_launcher/crawlers/dataset_sources.py":
        return "Split by source type, e.g. crawlers/ckan.py, stac.py, erddap.py, repository_sources.py."
    if rel == "api_launcher/repository.py":
        return "Split table groups when schema stabilizes: providers, datasets, manifests/install registry."
    if rel == "api_launcher/data_store_connections.py":
        return "Split drivers by engine family after profile contract stops changing."
    return "Review subsystem boundary before splitting."


def looks_like_runtime_root_file(path: Path) -> bool:
    name = path.name
    return (
        name.endswith(".sqlite")
        or name.endswith(".sqlite-shm")
        or name.endswith(".sqlite-wal")
        or name.endswith(".discovered.json")
        or name.endswith(".local.json")
    )


def relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def workspace_inventory_to_json(inventory: WorkspaceInventory) -> str:
    return json.dumps(inventory.to_dict(), indent=2, ensure_ascii=False) + "\n"


def render_workspace_inventory(inventory: WorkspaceInventory) -> str:
    lines: list[str] = ["# Workspace Inventory", "", f"root: {inventory.root}", ""]
    lines.append("## Categories")
    for category, count in inventory.category_counts.items():
        lines.append(f"- {category}: {count}")
    lines.extend(["", "## Large Python Files"])
    if not inventory.large_python_files:
        lines.append("- none")
    for item in inventory.large_python_files:
        lines.append(f"- {item['path']}: {item['line_count']} lines")
        lines.append(f"  suggestion: {item['suggestion']}")
    lines.extend(["", "## Root Runtime Files"])
    if not inventory.root_runtime_files:
        lines.append("- none")
    for path in inventory.root_runtime_files:
        lines.append(f"- {path}")
    lines.extend(["", "## Notes"])
    for note in inventory.notes:
        lines.append(f"- {note}")
    return "\n".join(lines) + "\n"
