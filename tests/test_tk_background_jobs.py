from __future__ import annotations

import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from frontends.tk.background_jobs import (
    release_single_flight_job,
    single_flight_job_is_active,
    start_single_flight_thread,
)


class TkBackgroundJobTests(unittest.TestCase):
    def test_start_single_flight_thread_runs_worker_and_releases_key(self) -> None:
        owner = SimpleNamespace()
        calls: list[str] = []
        job_key = ("seed_schema_probe", "demo_asset", "seed_1")

        class FakeThread:
            def __init__(self, target, args, daemon):
                self.target = target
                self.args = args
                self.daemon = daemon

            def start(self):
                self.target(*self.args)

        with patch("frontends.tk.background_jobs.threading.Thread", FakeThread):
            started = start_single_flight_thread(
                owner,
                job_key,
                lambda value: calls.append(value),
                ("ran",),
                active_jobs_attr="active_jobs",
                active_jobs_lock_attr="active_jobs_lock",
                on_duplicate=lambda: calls.append("duplicate"),
            )

        self.assertTrue(started)
        self.assertEqual(["ran"], calls)
        self.assertEqual(set(), owner.active_jobs)

    def test_start_single_flight_thread_rejects_duplicate_before_spawning_thread(self) -> None:
        job_key = ("asset_listing", "demo_asset", "")
        owner = SimpleNamespace(active_jobs={job_key}, active_jobs_lock=threading.Lock())
        duplicate_calls: list[str] = []

        with patch("frontends.tk.background_jobs.threading.Thread") as thread_class:
            started = start_single_flight_thread(
                owner,
                job_key,
                lambda: None,
                (),
                active_jobs_attr="active_jobs",
                active_jobs_lock_attr="active_jobs_lock",
                on_duplicate=lambda: duplicate_calls.append("duplicate"),
            )

        self.assertFalse(started)
        self.assertEqual(["duplicate"], duplicate_calls)
        thread_class.assert_not_called()

    def test_active_and_release_helpers_are_safe_without_lock(self) -> None:
        job_key = ("asset_download_plan", "demo_asset", "")
        owner = SimpleNamespace(active_jobs={job_key})
        duplicate_calls: list[str] = []

        self.assertTrue(
            single_flight_job_is_active(
                owner,
                job_key,
                active_jobs_attr="active_jobs",
                on_duplicate=lambda: duplicate_calls.append("duplicate"),
            )
        )
        release_single_flight_job(
            owner,
            job_key,
            active_jobs_attr="active_jobs",
            active_jobs_lock_attr="active_jobs_lock",
        )

        self.assertEqual(["duplicate"], duplicate_calls)
        self.assertEqual(set(), owner.active_jobs)


if __name__ == "__main__":
    unittest.main()
