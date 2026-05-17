from __future__ import annotations

import platform
import re
from collections.abc import Mapping


WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def platform_name() -> str:
    return platform.system()


def is_windows_absolute_path(value: str) -> bool:
    raw = value.strip()
    return bool(WINDOWS_ABSOLUTE_RE.match(raw)) or raw.startswith("\\\\")


def is_posix_absolute_path(value: str) -> bool:
    return value.strip().startswith("/")


def is_foreign_platform_path(raw_path: str, system: str | None = None) -> bool:
    value = raw_path.strip()
    if not value:
        return False
    current = system or platform_name()
    if current != "Windows" and is_windows_absolute_path(value):
        return True
    if current == "Windows" and is_posix_absolute_path(value):
        return True
    return False


def normalize_path_for_platform(raw_path: str, system: str | None = None) -> str:
    value = raw_path.strip()
    if not value or is_foreign_platform_path(value, system):
        return ""
    current = system or platform_name()
    if current == "Windows":
        return value.replace("/", "\\") if is_windows_absolute_path(value) else value
    return value.replace("\\", "/")


def platform_config_path(
    item: Mapping[str, object],
    key: str,
    system: str | None = None,
) -> str:
    current = system or platform_name()
    by_platform = item.get(f"{key}_by_platform") or {}
    if isinstance(by_platform, Mapping) and current in by_platform:
        return normalize_path_for_platform(str(by_platform.get(current) or ""), current)
    return normalize_path_for_platform(str(item.get(key) or ""), current)
