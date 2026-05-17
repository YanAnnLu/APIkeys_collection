from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path

from api_launcher.db import SCRIPT_DIR, resolve_project_path
from api_launcher.integrations import database_client_profiles, integrations_path


@dataclass(frozen=True)
class EnvironmentCheck:
    name: str
    status: str
    detail: str

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def run_startup_checks(db_path: str | Path = "APIkeys_collection.sqlite") -> list[EnvironmentCheck]:
    checks = [
        check_path("project_root", SCRIPT_DIR, must_exist=True, must_be_writable=True),
        check_path("database_parent", resolve_project_path(db_path).parent, must_exist=True, must_be_writable=True),
        check_path("integration_config", integrations_path(), must_exist=True, must_be_writable=False),
        check_python_encoding(),
    ]
    checks.extend(check_database_client_paths())
    return checks


def check_path(name: str, path: Path, must_exist: bool, must_be_writable: bool) -> EnvironmentCheck:
    resolved = path.resolve()
    if must_exist and not resolved.exists():
        return EnvironmentCheck(name, "error", f"Missing path: {resolved}")
    if must_be_writable and not os.access(resolved, os.W_OK):
        return EnvironmentCheck(name, "error", f"Path is not writable: {resolved}")
    return EnvironmentCheck(name, "ok", str(resolved))


def check_python_encoding() -> EnvironmentCheck:
    preferred = os.device_encoding(1) or ""
    filesystem = os.sys.getfilesystemencoding()
    detail = f"platform={platform.system()}, filesystem={filesystem}, stdout={preferred or 'unknown'}"
    if filesystem.lower() != "utf-8":
        return EnvironmentCheck("python_encoding", "warning", detail)
    return EnvironmentCheck("python_encoding", "ok", detail)


def check_database_client_paths() -> list[EnvironmentCheck]:
    checks = []
    for profile in database_client_profiles():
        command = profile.command[0] if profile.command else ""
        if not command:
            checks.append(EnvironmentCheck(f"db_client:{profile.id}", "error", "Empty command."))
            continue
        path = Path(command)
        exists = path.exists() if path.is_absolute() else shutil.which(command) is not None
        status = "ok" if exists else "warning"
        detail = command if exists else f"Command not found on this machine: {command}"
        checks.append(EnvironmentCheck(f"db_client:{profile.id}", status, detail))
    return checks
