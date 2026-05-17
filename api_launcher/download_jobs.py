from __future__ import annotations

import concurrent.futures
import threading
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Callable, Iterable, Protocol

from api_launcher.db import utc_now_iso


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class DownloadProgress:
    job_id: str
    provider_id: str
    status: JobStatus
    bytes_done: int = 0
    bytes_total: int | None = None
    message: str = ""
    error: str = ""
    updated_at: str = field(default_factory=utc_now_iso)

    @property
    def percent(self) -> float | None:
        if not self.bytes_total:
            return None
        return min(100.0, max(0.0, self.bytes_done / self.bytes_total * 100.0))


@dataclass(frozen=True)
class DownloadJob:
    job_id: str
    provider_id: str
    plan_entry: dict[str, object]
    created_at: str = field(default_factory=utc_now_iso)


class DownloadCancelled(RuntimeError):
    pass


class DownloadJobController:
    def __init__(self) -> None:
        self._resume = threading.Event()
        self._resume.set()
        self._cancel = threading.Event()

    def pause(self) -> None:
        self._resume.clear()

    def resume(self) -> None:
        self._resume.set()

    def cancel(self) -> None:
        self._cancel.set()
        self._resume.set()

    def wait_if_paused(self) -> None:
        self.raise_if_cancelled()
        self._resume.wait()
        self.raise_if_cancelled()

    def raise_if_cancelled(self) -> None:
        if self._cancel.is_set():
            raise DownloadCancelled("Download job was cancelled.")


class DownloadAdapter(Protocol):
    def run(self, job: DownloadJob, controller: DownloadJobController) -> Iterable[DownloadProgress]:
        """Yield progress updates while downloading/importing one plan entry."""


ProgressCallback = Callable[[DownloadProgress], None]


class NonBlockingDownloadQueue:
    def __init__(self, adapter: DownloadAdapter, max_workers: int = 3):
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1.")
        self.adapter = adapter
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.lock = threading.Lock()
        self.controllers: dict[str, DownloadJobController] = {}
        self.futures: dict[str, concurrent.futures.Future[None]] = {}
        self.progress: dict[str, DownloadProgress] = {}
        self.callbacks: list[ProgressCallback] = []

    def add_callback(self, callback: ProgressCallback) -> None:
        self.callbacks.append(callback)

    def submit(self, plan_entry: dict[str, object]) -> DownloadJob:
        provider_id = str(plan_entry.get("provider_id") or "").strip()
        if not provider_id:
            raise ValueError("plan_entry must include provider_id.")
        job = DownloadJob(job_id=f"job_{uuid.uuid4().hex[:12]}", provider_id=provider_id, plan_entry=dict(plan_entry))
        controller = DownloadJobController()
        with self.lock:
            self.controllers[job.job_id] = controller
            self.progress[job.job_id] = DownloadProgress(
                job_id=job.job_id,
                provider_id=job.provider_id,
                status=JobStatus.QUEUED,
                message="Queued",
            )
        self.futures[job.job_id] = self.executor.submit(self._run_job, job, controller)
        return job

    def pause(self, job_id: str) -> None:
        controller = self._controller(job_id)
        controller.pause()
        current = self.snapshot(job_id)
        self._publish(
            DownloadProgress(
                job_id=job_id,
                provider_id=current.provider_id,
                status=JobStatus.PAUSED,
                bytes_done=current.bytes_done,
                bytes_total=current.bytes_total,
                message="Paused",
            )
        )

    def resume(self, job_id: str) -> None:
        controller = self._controller(job_id)
        controller.resume()
        current = self.snapshot(job_id)
        self._publish(
            DownloadProgress(
                job_id=job_id,
                provider_id=current.provider_id,
                status=JobStatus.RUNNING,
                bytes_done=current.bytes_done,
                bytes_total=current.bytes_total,
                message="Resumed",
            )
        )

    def cancel(self, job_id: str) -> None:
        self._controller(job_id).cancel()

    def snapshot(self, job_id: str) -> DownloadProgress:
        with self.lock:
            if job_id not in self.progress:
                raise KeyError(f"Unknown download job: {job_id}")
            return self.progress[job_id]

    def wait(self, job_id: str, timeout: float | None = None) -> None:
        self.futures[job_id].result(timeout=timeout)

    def shutdown(self) -> None:
        self.executor.shutdown(wait=True, cancel_futures=False)

    def _controller(self, job_id: str) -> DownloadJobController:
        with self.lock:
            if job_id not in self.controllers:
                raise KeyError(f"Unknown download job: {job_id}")
            return self.controllers[job_id]

    def _run_job(self, job: DownloadJob, controller: DownloadJobController) -> None:
        self._publish(
            DownloadProgress(job_id=job.job_id, provider_id=job.provider_id, status=JobStatus.RUNNING, message="Running")
        )
        try:
            for update in self.adapter.run(job, controller):
                controller.wait_if_paused()
                self._publish(update)
            current = self.snapshot(job.job_id)
            self._publish(
                DownloadProgress(
                    job_id=job.job_id,
                    provider_id=job.provider_id,
                    status=JobStatus.COMPLETED,
                    bytes_done=current.bytes_done,
                    bytes_total=current.bytes_total,
                    message="Completed",
                )
            )
        except DownloadCancelled as exc:
            current = self.snapshot(job.job_id)
            self._publish(
                DownloadProgress(
                    job_id=job.job_id,
                    provider_id=job.provider_id,
                    status=JobStatus.CANCELLED,
                    bytes_done=current.bytes_done,
                    bytes_total=current.bytes_total,
                    message=str(exc),
                )
            )
        except Exception as exc:
            current = self.snapshot(job.job_id)
            self._publish(
                DownloadProgress(
                    job_id=job.job_id,
                    provider_id=job.provider_id,
                    status=JobStatus.FAILED,
                    bytes_done=current.bytes_done,
                    bytes_total=current.bytes_total,
                    message="Failed",
                    error=f"{type(exc).__name__}: {exc}",
                )
            )

    def _publish(self, update: DownloadProgress) -> None:
        with self.lock:
            self.progress[update.job_id] = update
        for callback in self.callbacks:
            callback(update)
