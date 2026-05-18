from __future__ import annotations

import unittest
from pathlib import Path

import json

from api_launcher.integrations import (
    DownloadToolProfile,
    download_policy_from_config,
    download_tool_profiles_from_config,
    example_integrations_path,
    runtime_orchestration_profiles_from_config,
)
from api_launcher.downloads.transfer_tools import build_external_transfer_command, transfer_url_from_plan_entry


class TransferToolTests(unittest.TestCase):
    def test_example_config_includes_internal_and_external_tools(self) -> None:
        config = json.loads(example_integrations_path().read_text(encoding="utf-8"))
        profiles = {profile.id: profile for profile in download_tool_profiles_from_config(config)}
        self.assertIn("python_internal", profiles)
        self.assertIn("aria2c", profiles)
        self.assertIn("curl", profiles)
        self.assertTrue(profiles["python_internal"].supports_resume)

    def test_example_config_includes_polite_download_policy(self) -> None:
        config = json.loads(example_integrations_path().read_text(encoding="utf-8"))
        policy = download_policy_from_config(config)
        self.assertEqual(3, policy.max_parallel_jobs)
        self.assertEqual(1, policy.max_parallel_per_host)
        self.assertIn(429, policy.cooldown_status_codes)

    def test_example_config_reserves_runtime_orchestration_profiles(self) -> None:
        config = json.loads(example_integrations_path().read_text(encoding="utf-8"))
        profiles = {profile.id: profile for profile in runtime_orchestration_profiles_from_config(config)}

        self.assertIn("local_docker_compose", profiles)
        self.assertIn("kubernetes_default", profiles)
        self.assertEqual("kubernetes", profiles["kubernetes_default"].kind)
        self.assertEqual("apikeys-collection", profiles["kubernetes_default"].namespace)
        self.assertIn("KUBECONFIG", profiles["kubernetes_default"].required_env_vars)

    def test_build_aria2c_command_uses_resume_and_split_flags(self) -> None:
        profile = DownloadToolProfile(
            id="aria2c",
            label="aria2c",
            kind="external_cli",
            enabled=True,
            command=("aria2c",),
            supports_resume=True,
            supports_parallel=True,
        )

        command = build_external_transfer_command(profile, "https://example.test/data.zip", Path("cache/data.zip"))

        self.assertEqual("aria2c", command.command[0])
        self.assertIn("--continue=true", command.command)
        self.assertIn("--split=4", command.command)
        self.assertEqual("data.zip", command.command[-2])
        self.assertEqual("https://example.test/data.zip", command.command[-1])

    def test_build_curl_command_uses_continue_flag(self) -> None:
        profile = DownloadToolProfile(
            id="curl",
            label="curl",
            kind="external_cli",
            enabled=True,
            command=("curl",),
            supports_resume=True,
            supports_parallel=False,
        )

        command = build_external_transfer_command(profile, "https://example.test/data.zip", Path("cache/data.zip"))

        self.assertEqual("curl", command.command[0])
        self.assertIn("--continue-at", command.command)
        self.assertIn("--output", command.command)
        self.assertFalse(command.supports_parallel)

    def test_transfer_url_from_plan_entry_prefers_direct_download_url(self) -> None:
        url = transfer_url_from_plan_entry(
            {
                "download_url": "https://example.test/file.nc",
                "docs_url": "https://example.test/docs",
            }
        )
        self.assertEqual("https://example.test/file.nc", url)


if __name__ == "__main__":
    unittest.main()
