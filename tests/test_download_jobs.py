# 這份測試鎖定非阻塞下載 queue，避免 pause/resume/cancel 狀態傳遞回歸。
from __future__ import annotations

import threading
import unittest

from api_launcher.downloads.jobs import DownloadProgress, JobStatus, NonBlockingDownloadQueue


class BlockingFakeAdapter:
    def __init__(self) -> None:
        self.first_update = threading.Event()
        self.continue_download = threading.Event()

    def run(self, job, controller):
        yield DownloadProgress(
            job_id=job.job_id,
            provider_id=job.provider_id,
            status=JobStatus.RUNNING,
            bytes_done=25,
            bytes_total=100,
            message="First chunk",
        )
        self.first_update.set()
        self.continue_download.wait(timeout=2)
        controller.wait_if_paused()
        yield DownloadProgress(
            job_id=job.job_id,
            provider_id=job.provider_id,
            status=JobStatus.RUNNING,
            bytes_done=100,
            bytes_total=100,
            message="Final chunk",
        )


class ImmediateFakeAdapter:
    def run(self, job, controller):
        yield DownloadProgress(
            job_id=job.job_id,
            provider_id=job.provider_id,
            status=JobStatus.RUNNING,
            bytes_done=1,
            bytes_total=1,
            message="Only chunk",
        )


class DownloadQueueTests(unittest.TestCase):
    def test_nonblocking_queue_tracks_progress_and_completion(self) -> None:
        adapter = BlockingFakeAdapter()
        queue = NonBlockingDownloadQueue(adapter, max_workers=2)
        try:
            job = queue.submit({"provider_id": "noaa_ncei_cdo"})
            self.assertTrue(adapter.first_update.wait(timeout=2))
            self.assertEqual(queue.snapshot(job.job_id).bytes_done, 25)

            adapter.continue_download.set()
            queue.wait(job.job_id, timeout=2)

            final = queue.snapshot(job.job_id)
            self.assertEqual(final.status, JobStatus.COMPLETED)
            self.assertEqual(final.percent, 100.0)
        finally:
            queue.shutdown()

    def test_pause_resume_and_cancel_update_job_state(self) -> None:
        adapter = BlockingFakeAdapter()
        queue = NonBlockingDownloadQueue(adapter, max_workers=1)
        try:
            job = queue.submit({"provider_id": "gebco"})
            self.assertTrue(adapter.first_update.wait(timeout=2))

            queue.pause(job.job_id)
            self.assertEqual(queue.snapshot(job.job_id).status, JobStatus.PAUSED)

            queue.resume(job.job_id)
            self.assertEqual(queue.snapshot(job.job_id).status, JobStatus.RUNNING)

            queue.cancel(job.job_id)
            adapter.continue_download.set()
            queue.wait(job.job_id, timeout=2)
            self.assertEqual(queue.snapshot(job.job_id).status, JobStatus.CANCELLED)
        finally:
            queue.shutdown()

    def test_callback_failure_does_not_fail_download_job(self) -> None:
        queue = NonBlockingDownloadQueue(ImmediateFakeAdapter(), max_workers=1)
        received: list[JobStatus] = []

        def broken_callback(update: DownloadProgress) -> None:
            raise RuntimeError(f"callback failed at {update.status}")

        def collecting_callback(update: DownloadProgress) -> None:
            received.append(update.status)

        queue.add_callback(broken_callback)
        queue.add_callback(collecting_callback)
        try:
            job = queue.submit({"provider_id": "gebco"})
            queue.wait(job.job_id, timeout=2)

            final = queue.snapshot(job.job_id)
            self.assertEqual(final.status, JobStatus.COMPLETED)
            self.assertIn(JobStatus.COMPLETED, received)
            callback_errors = queue.callback_error_snapshot()
            self.assertGreaterEqual(len(callback_errors), 1)
            self.assertEqual(callback_errors[0].job_id, job.job_id)
            self.assertIn("RuntimeError", callback_errors[0].error)
        finally:
            queue.shutdown()


if __name__ == "__main__":
    unittest.main()
