from __future__ import annotations

import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from api_launcher.db import resolve_project_path
from api_launcher.downloads.jobs import DownloadJob, DownloadJobController, DownloadProgress, JobStatus
from api_launcher.downloads.policy import HostThrottle, PoliteDownloadPolicy
from api_launcher.manifests import manifest_matches_plan_entry, read_manifest
from api_launcher.downloads.repair import verify_manifest_file
from api_launcher.downloads.staging import StagingPaths, promote_staged_payload, staging_paths_for_plan_entry
from api_launcher.downloads.transfer_tools import transfer_url_from_plan_entry


DEFAULT_DOWNLOAD_DIR = "downloads"
DEFAULT_CHUNK_SIZE = 1024 * 256


@dataclass(frozen=True)
class DownloadTarget:
    # target 同時保存 final/part/manifest 路徑，讓 resume 與 manifest 寫入邊界清楚。
    url: str
    output_path: Path
    part_path: Path
    staging_paths: StagingPaths | None = None


class HTTPDownloadAdapter:
    # HTTP adapter 只負責單檔下載與 sidecar manifest；排程/重試由 jobs 或 plan_runner 控制。
    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE, timeout: float = 30.0, policy: PoliteDownloadPolicy | None = None):
        if chunk_size < 1:
            raise ValueError("chunk_size must be at least 1.")
        self.chunk_size = chunk_size
        self.timeout = timeout
        self.policy = policy or PoliteDownloadPolicy()
        self.throttle = HostThrottle(self.policy)

    def run(self, job: DownloadJob, controller: DownloadJobController) -> Iterable[DownloadProgress]:
        target = download_target_from_plan_entry(job.plan_entry)
        reused = reusable_completed_download(target, job.plan_entry)
        if reused:
            # sidecar manifest 已驗證且與 plan 相符時直接重用，避免重複下載大型公開資料。
            size_bytes = target.output_path.stat().st_size
            yield DownloadProgress(
                job_id=job.job_id,
                provider_id=job.provider_id,
                status=JobStatus.COMPLETED,
                bytes_done=size_bytes,
                bytes_total=size_bytes,
                message=f"Reused verified download at {target.output_path}",
            )
            return
        target.output_path.parent.mkdir(parents=True, exist_ok=True)
        target.part_path.parent.mkdir(parents=True, exist_ok=True)
        migrate_legacy_part_file(target)

        for attempt in range(1, self.policy.max_retries + 1):
            controller.wait_if_paused()
            existing_bytes = target.part_path.stat().st_size if target.part_path.exists() else 0
            # 有 .part 檔時用 Range resume；若伺服器不支援，_download_once 會重頭下載。
            request = build_download_request(target.url, resume_from=existing_bytes, user_agent=self.policy.user_agent)
            self.throttle.wait_for_url(target.url)
            try:
                yield from self._download_once(job, controller, target, request, existing_bytes)
                return
            except urllib.error.HTTPError as exc:
                if attempt >= self.policy.max_retries or exc.code not in self.policy.cooldown_status_codes:
                    raise
                delay = self.policy.retry_delay(attempt, exc.headers.get("Retry-After") if exc.headers else None)
                yield DownloadProgress(
                    job_id=job.job_id,
                    provider_id=job.provider_id,
                    status=JobStatus.RUNNING,
                    bytes_done=existing_bytes,
                    bytes_total=None,
                    message=f"HTTP {exc.code}; cooling down for {delay:.1f}s",
                )
                time.sleep(delay)

    def _download_once(
        self,
        job: DownloadJob,
        controller: DownloadJobController,
        target: DownloadTarget,
        request: urllib.request.Request,
        existing_bytes: int,
    ) -> Iterable[DownloadProgress]:

        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            status_code = int(getattr(response, "status", 200))
            if existing_bytes and status_code != 206:
                # 伺服器未回 206 表示沒有接受續傳，舊 partial 不能直接 append。
                existing_bytes = 0
                target.part_path.unlink(missing_ok=True)

            total_bytes = infer_total_bytes(response.headers, existing_bytes)
            mode = "ab" if existing_bytes else "wb"
            bytes_done = existing_bytes

            yield DownloadProgress(
                job_id=job.job_id,
                provider_id=job.provider_id,
                status=JobStatus.RUNNING,
                bytes_done=bytes_done,
                bytes_total=total_bytes,
                message="Downloading",
            )

            with target.part_path.open(mode + "") as handle:
                while True:
                    controller.wait_if_paused()
                    chunk = response.read(self.chunk_size)
                    if not chunk:
                        break
                    handle.write(chunk)
                    bytes_done += len(chunk)
                    yield DownloadProgress(
                        job_id=job.job_id,
                        provider_id=job.provider_id,
                        status=JobStatus.RUNNING,
                        bytes_done=bytes_done,
                        bytes_total=total_bytes,
                        message="Downloading",
                    )

        if target.staging_paths:
            # staging 模式先 promote 再寫 final manifest，避免半成品出現在正式下載路徑。
            os.replace(target.part_path, target.staging_paths.payload_path)
            promote_staged_payload(target.staging_paths, job.plan_entry)
        else:
            os.replace(target.part_path, target.output_path)
        yield DownloadProgress(
            job_id=job.job_id,
            provider_id=job.provider_id,
            status=JobStatus.COMPLETED,
            bytes_done=target.output_path.stat().st_size,
            bytes_total=target.output_path.stat().st_size,
            message=f"Downloaded to {target.output_path}",
        )


def build_download_request(url: str, resume_from: int = 0, user_agent: str | None = None) -> urllib.request.Request:
    headers = {"User-Agent": user_agent or PoliteDownloadPolicy().user_agent}
    if resume_from > 0:
        # Range header 是續傳契約；呼叫端仍需檢查回應碼是否為 206。
        headers["Range"] = f"bytes={resume_from}-"
    return urllib.request.Request(url, headers=headers)


def infer_total_bytes(headers: object, existing_bytes: int) -> int | None:
    content_range = str(getattr(headers, "get", lambda _key, _default=None: None)("Content-Range", "") or "")
    if "/" in content_range:
        total = content_range.rsplit("/", 1)[-1].strip()
        if total.isdigit():
            return int(total)

    content_length = str(getattr(headers, "get", lambda _key, _default=None: None)("Content-Length", "") or "")
    if content_length.isdigit():
        return existing_bytes + int(content_length)
    return None


def download_target_from_plan_entry(plan_entry: dict[str, object]) -> DownloadTarget:
    url = transfer_url_from_plan_entry(plan_entry)
    output_value = (
        plan_entry.get("target_path")
        or plan_entry.get("output_path")
        or plan_entry.get("raw_path")
        or default_download_path(plan_entry, url)
    )
    output_path = resolve_project_path(str(output_value))
    use_staging = bool(plan_entry.get("use_staging", True))
    if use_staging:
        staging_paths = staging_paths_for_plan_entry(plan_entry, output_path)
        return DownloadTarget(url=url, output_path=output_path, part_path=staging_paths.part_path, staging_paths=staging_paths)
    return DownloadTarget(url=url, output_path=output_path, part_path=output_path.with_suffix(output_path.suffix + ".part"))


def reusable_completed_download(target: DownloadTarget, plan_entry: dict[str, object]) -> bool:
    # 只有 payload 存在、manifest 健康、且 manifest 仍符合 plan 時才視為可重用。
    manifest_path = target.output_path.with_suffix(target.output_path.suffix + ".manifest.json")
    if not target.output_path.exists() or not manifest_path.exists():
        return False
    verification = verify_manifest_file(manifest_path)
    if verification.status != "ok":
        return False
    try:
        manifest = read_manifest(manifest_path)
    except Exception:
        return False
    return manifest_matches_plan_entry(
        manifest,
        plan_entry,
        source_url=target.url,
        target_path=target.output_path,
    )


def migrate_legacy_part_file(target: DownloadTarget) -> None:
    # 早期版本把 .part 放在 final 旁邊；搬到 staging 後保留續傳能力。
    if not target.staging_paths:
        return
    legacy_part = target.output_path.with_suffix(target.output_path.suffix + ".part")
    if legacy_part.exists() and not target.part_path.exists():
        target.part_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(legacy_part, target.part_path)


def default_download_path(plan_entry: dict[str, object], url: str) -> Path:
    provider_id = str(plan_entry.get("provider_id") or "unknown_provider").strip() or "unknown_provider"
    parsed = urllib.parse.urlparse(url)
    filename = Path(urllib.parse.unquote(parsed.path)).name or f"{provider_id}.download"
    return Path(DEFAULT_DOWNLOAD_DIR) / provider_id / filename
