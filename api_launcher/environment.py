from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path

from api_launcher.db import SCRIPT_DIR, resolve_project_path
from api_launcher.integrations import database_client_profiles, download_tool_profiles, integrations_path, unreal_project_profiles
from api_launcher.platform_paths import is_foreign_platform_path


@dataclass(frozen=True)
class EnvironmentCheck:
    # 啟動檢查回傳狀態物件，不直接印出或中止，讓 CLI/Tk 可以自行決定呈現方式。
    name: str
    status: str
    detail: str

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def run_startup_checks(db_path: str | Path = "APIkeys_collection.sqlite") -> list[EnvironmentCheck]:
    # 這裡只檢查環境可用性，不建立缺失檔案，也不修正使用者設定。
    checks = [
        check_path("project_root", SCRIPT_DIR, must_exist=True, must_be_writable=True),
        check_path("database_parent", resolve_project_path(db_path).parent, must_exist=True, must_be_writable=True),
        check_path("integration_config", integrations_path(), must_exist=True, must_be_writable=False),
        check_python_encoding(),
    ]
    # 下列 profile 檢查只回報本機工具狀態，不會嘗試安裝或修改使用者環境。
    checks.extend(check_database_client_paths())
    checks.extend(check_download_tool_paths())
    checks.extend(check_unreal_project_profiles())
    return checks


def check_path(name: str, path: Path, must_exist: bool, must_be_writable: bool) -> EnvironmentCheck:
    # path.resolve() 只用於回報清楚路徑；跨平台外來路徑要在呼叫前先被 guard 掉。
    resolved = path.resolve()
    if must_exist and not resolved.exists():
        return EnvironmentCheck(name, "error", f"Missing path: {resolved}")
    if must_be_writable and not os.access(resolved, os.W_OK):
        # 寫入權限是啟動/匯入常見故障點，提前回報比等下載或 SQLite 失敗更容易理解。
        return EnvironmentCheck(name, "error", f"Path is not writable: {resolved}")
    return EnvironmentCheck(name, "ok", str(resolved))


def check_python_encoding() -> EnvironmentCheck:
    # Windows/macOS 的編碼差異會影響中文 UI 與 log；warning 足夠，不阻擋啟動。
    preferred = os.device_encoding(1) or ""
    filesystem = os.sys.getfilesystemencoding()
    detail = f"platform={platform.system()}, filesystem={filesystem}, stdout={preferred or 'unknown'}"
    if filesystem.lower() != "utf-8":
        return EnvironmentCheck("python_encoding", "warning", detail)
    return EnvironmentCheck("python_encoding", "ok", detail)


def check_database_client_paths() -> list[EnvironmentCheck]:
    # 外部 DB client 是便利工具，不是核心啟動條件；找不到時用 warning。
    checks = []
    for profile in database_client_profiles():
        command = profile.command[0] if profile.command else ""
        if not command:
            # 設定檔存在但 command 空白通常代表手動編輯不完整，應標 error 讓使用者修 config。
            checks.append(EnvironmentCheck(f"db_client:{profile.id}", "error", "Empty command."))
            continue
        path = Path(command)
        exists = path.exists() if path.is_absolute() else shutil.which(command) is not None
        status = "ok" if exists else "warning"
        detail = command if exists else f"Command not found on this machine: {command}"
        checks.append(EnvironmentCheck(f"db_client:{profile.id}", status, detail))
    return checks


def check_download_tool_paths() -> list[EnvironmentCheck]:
    # python_internal 是內建下載器；curl/aria2c 這類外部工具才需要檢查 PATH。
    checks = []
    for profile in download_tool_profiles():
        if not profile.enabled:
            continue
        if profile.kind == "python_internal":
            checks.append(EnvironmentCheck(f"download_tool:{profile.id}", "ok", "Built-in Python transfer engine."))
            continue
        command = profile.command[0] if profile.command else ""
        if not command:
            # 外部下載工具沒有 command 時不能執行，回報 error；未安裝則只是 warning。
            checks.append(EnvironmentCheck(f"download_tool:{profile.id}", "error", "Empty command."))
            continue
        path = Path(command)
        exists = path.exists() if path.is_absolute() else shutil.which(command) is not None
        status = "ok" if exists else "warning"
        detail = command if exists else f"Command not found on this machine: {command}"
        checks.append(EnvironmentCheck(f"download_tool:{profile.id}", status, detail))
    return checks


def check_unreal_project_profiles() -> list[EnvironmentCheck]:
    # Unreal 是 renderer bridge 的中期路徑；缺設定要回報，但不能阻擋資料管理 MVP。
    checks = []
    system = platform.system()
    for profile in unreal_project_profiles():
        if not profile.enabled:
            continue
        if profile.engine_root:
            checks.append(check_path(f"unreal_engine:{profile.id}", Path(profile.engine_root), must_exist=True, must_be_writable=False))
        if profile.editor_command:
            command = profile.editor_command[0]
            path = Path(command)
            exists = path.exists() if path.is_absolute() else shutil.which(command) is not None
            status = "ok" if exists else "warning"
            detail = command if exists else f"Unreal editor command not found: {command}"
            checks.append(EnvironmentCheck(f"unreal_editor:{profile.id}", status, detail))
        if profile.project_path:
            checks.append(
                check_unreal_profile_path(
                    f"unreal_project:{profile.id}",
                    profile.project_path,
                    system,
                    must_be_writable=False,
                )
            )
        else:
            checks.append(EnvironmentCheck(f"unreal_project:{profile.id}", "warning", "No Unreal .uproject configured yet."))
        if profile.content_root:
            checks.append(
                check_unreal_profile_path(
                    f"unreal_content:{profile.id}",
                    profile.content_root,
                    system,
                    must_be_writable=True,
                )
            )
    return checks


def check_unreal_profile_path(
    name: str,
    raw_path: str,
    system: str,
    must_be_writable: bool,
) -> EnvironmentCheck:
    # 先辨識外平台路徑，再交給 Path；避免 macOS/Linux 把 Windows `K:\...` 誤解析。
    if is_foreign_platform_path(raw_path, system):
        return EnvironmentCheck(
            name,
            "warning",
            f"Path is for another platform and was skipped on {system}: {raw_path}",
        )
    return check_path(name, Path(raw_path), must_exist=True, must_be_writable=must_be_writable)
