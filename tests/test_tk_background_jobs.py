from __future__ import annotations

import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from frontends.tk.background_job_policies import (
    MAX_CRAWLER_ASSET_BACKGROUND_JOBS,
    MAX_TK_AI_SUMMARY_BACKGROUND_JOBS,
    MAX_TK_DISCOVERY_BACKGROUND_JOBS,
    MAX_TK_OAUTH_BACKGROUND_JOBS,
    MAX_TK_PLAN_BOUNDS_PROBE_JOBS,
    MAX_TK_SIDEBAR_FAVICON_JOBS,
    MAX_TK_SOURCE_ACTION_BACKGROUND_JOBS,
    MAX_TK_SQLITE_IMPORT_JOBS,
    iter_tk_background_job_policies,
    tk_background_job_policy,
)
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

    def test_start_single_flight_thread_rejects_capacity_before_spawning_thread(self) -> None:
        owner = SimpleNamespace(
            active_jobs={
                ("seed_schema_probe", "asset_a", "seed_1"),
                ("seed_download_import", "asset_b", "seed_2"),
            },
            active_jobs_lock=threading.Lock(),
        )
        calls: list[str] = []

        with patch("frontends.tk.background_jobs.threading.Thread") as thread_class:
            started = start_single_flight_thread(
                owner,
                ("asset_listing", "asset_c", ""),
                lambda: calls.append("ran"),
                (),
                active_jobs_attr="active_jobs",
                active_jobs_lock_attr="active_jobs_lock",
                on_duplicate=lambda: calls.append("duplicate"),
                max_active_jobs=2,
                on_capacity=lambda: calls.append("capacity"),
            )

        self.assertFalse(started)
        self.assertEqual(["capacity"], calls)
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

    def test_background_job_policies_are_listed_in_stable_order(self) -> None:
        policies = list(iter_tk_background_job_policies())
        self.assertEqual(sorted(policy.policy_id for policy in policies), [policy.policy_id for policy in policies])
        self.assertIn("crawler_asset", {policy.policy_id for policy in policies})
        for policy in policies:
            self.assertGreaterEqual(policy.max_active_jobs, 1)
            self.assertTrue(policy.active_jobs_attr.endswith("_active_jobs"))
            self.assertTrue(policy.active_jobs_lock_attr.endswith("_active_jobs_lock"))

    def test_background_job_policy_constants_match_registry(self) -> None:
        expected = {
            "ai_summary": MAX_TK_AI_SUMMARY_BACKGROUND_JOBS,
            "crawler_asset": MAX_CRAWLER_ASSET_BACKGROUND_JOBS,
            "discovery": MAX_TK_DISCOVERY_BACKGROUND_JOBS,
            "oauth": MAX_TK_OAUTH_BACKGROUND_JOBS,
            "plan_bounds_probe": MAX_TK_PLAN_BOUNDS_PROBE_JOBS,
            "sidebar_favicon": MAX_TK_SIDEBAR_FAVICON_JOBS,
            "source_action": MAX_TK_SOURCE_ACTION_BACKGROUND_JOBS,
            "sqlite_import": MAX_TK_SQLITE_IMPORT_JOBS,
        }
        for policy_id, max_active_jobs in expected.items():
            self.assertEqual(max_active_jobs, tk_background_job_policy(policy_id).max_active_jobs)

    def test_background_job_policy_fails_fast_for_unknown_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown Tk background job policy"):
            tk_background_job_policy("not_a_policy")


if __name__ == "__main__":
    unittest.main()
