from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from api_launcher.integrations import DownloadToolProfile, active_download_tool


@dataclass(frozen=True)
class TransferCommand:
    tool_id: str
    command: tuple[str, ...]
    supports_resume: bool
    supports_parallel: bool


def selected_transfer_tool() -> DownloadToolProfile:
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
    for key in ("download_url", "file_url", "api_base_url", "docs_url"):
        value = str(plan_entry.get(key) or "").strip()
        if value:
            return value
    raise ValueError("Plan entry does not include a usable transfer URL.")
