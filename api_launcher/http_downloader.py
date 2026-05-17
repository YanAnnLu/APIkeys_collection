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
from api_launcher.download_jobs import DownloadJob, DownloadJobController, DownloadProgress, JobStatus
from api_launcher.download_policy import HostThrottle, PoliteDownloadPolicy
from api_launcher.transfer_tools import transfer_url_from_plan_entry


DEFAULT_DOWNLOAD_DIR = "downloads"
DEFAULT_CHUNK_SIZE = 1024 * 256


@dataclass(frozen=True)
class DownloadTarget:
    url: str
    output_path: Path
    part_path: Path


class HTTPDownloadAdapter:
    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE, timeout: float = 30.0, policy: PoliteDownloadPolicy | None = None):
        if chunk_size < 1:
            raise ValueError("chunk_size must be at least 1.")
        self.chunk_size = chunk_size
        self.timeout = timeout
        self.policy = policy or PoliteDownloadPolicy()
        self.throttle = HostThrottle(self.policy)

    def run(self, job: DownloadJob, controller: DownloadJobController) -> Iterable[DownloadProgress]:
        target = download_target_from_plan_entry(job.plan_entry)
        target.output_path.parent.mkdir(parents=True, exist_ok=True)

        for attempt in range(1, self.policy.max_retries + 1):
            controller.wait_if_paused()
            existing_bytes = target.part_path.stat().st_size if target.part_path.exists() else 0
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
    return DownloadTarget(url=url, output_path=output_path, part_path=output_path.with_suffix(output_path.suffix + ".part"))


def default_download_path(plan_entry: dict[str, object], url: str) -> Path:
    provider_id = str(plan_entry.get("provider_id") or "unknown_provider").strip() or "unknown_provider"
    parsed = urllib.parse.urlparse(url)
    filename = Path(urllib.parse.unquote(parsed.path)).name or f"{provider_id}.download"
    return Path(DEFAULT_DOWNLOAD_DIR) / provider_id / filename
