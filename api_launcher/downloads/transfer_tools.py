from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from api_launcher.integrations import DownloadToolProfile, active_download_tool


@dataclass(frozen=True)
class TransferCommand:
    # TransferCommand 只描述外部命令，不在這裡執行，方便 UI 先預覽或記錄。
    tool_id: str
    command: tuple[str, ...]
    supports_resume: bool
    supports_parallel: bool


def selected_transfer_tool() -> DownloadToolProfile:
    # 沒有外部工具設定時回退到內建 downloader，保證 MVP 下載流程仍可用。
    profile = active_download_tool()
    if profile is None:
        return DownloadToolProfile(
            id="python_internal",
            label="Python internal downloader",
            kind="python_internal",
            enabled=True,
            command=(),
            supports_resume=True,
            supports_parallel=True,
            notes="Fallback built into the launcher.",
        )
    return profile


def build_external_transfer_command(profile: DownloadToolProfile, url: str, output_path: str | Path) -> TransferCommand:
    # 這裡只組 argv tuple，不走 shell 字串，避免 URL/路徑含空白或特殊字元時被誤解析。
    if profile.kind != "external_cli":
        raise ValueError(f"Profile is not an external CLI transfer tool: {profile.id}")
    if not profile.command:
        raise ValueError(f"External transfer tool has no command: {profile.id}")
    clean_url = url.strip()
    if not clean_url:
        raise ValueError("Transfer URL is required.")

    target = Path(output_path)
    executable = profile.command[0]
    base_args = tuple(profile.command[1:])
    if profile.id == "aria2c":
        # aria2c 可多連線續傳；仍限制 retries/connection 數，避免對公開來源太激進。
        command = (
            executable,
            *base_args,
            "--continue=true",
            "--max-tries=5",
            "--retry-wait=5",
            "--max-connection-per-server=4",
            "--split=4",
            "--dir",
            str(target.parent),
            "--out",
            target.name,
            clean_url,
        )
    elif profile.id == "curl":
        # curl profile 使用 --continue-at - 支援續傳，並以 --fail 讓 HTTP 錯誤能傳回失敗碼。
        command = (
            executable,
            *base_args,
            "--location",
            "--fail",
            "--retry",
            "5",
            "--continue-at",
            "-",
            "--output",
            str(target),
            clean_url,
        )
    else:
        command = (executable, *base_args, clean_url)

    return TransferCommand(
        tool_id=profile.id,
        command=command,
        supports_resume=profile.supports_resume,
        supports_parallel=profile.supports_parallel,
    )


def transfer_url_from_plan_entry(plan_entry: dict[str, object]) -> str:
    # URL 優先順序從最明確的下載網址開始，最後才退到 docs_url。
    for key in ("download_url", "file_url", "api_base_url", "docs_url"):
        value = str(plan_entry.get(key) or "").strip()
        if value:
            return value
    raise ValueError("Plan entry does not include a usable transfer URL.")
