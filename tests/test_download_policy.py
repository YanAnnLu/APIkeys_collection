from __future__ import annotations

import unittest

from api_launcher.downloads.policy import HostThrottle, PoliteDownloadPolicy, host_key, parse_retry_after_seconds


class DownloadPolicyTests(unittest.TestCase):
    def test_host_key_normalizes_host(self) -> None:
        self.assertEqual("example.test:443", host_key("https://EXAMPLE.test:443/data/file.nc"))

    def test_retry_after_seconds(self) -> None:
        self.assertEqual(12.0, parse_retry_after_seconds("12"))
        self.assertEqual(0.0, parse_retry_after_seconds("-3"))
        self.assertIsNone(parse_retry_after_seconds("Wed, 21 Oct 2015 07:28:00 GMT"))

    def test_exponential_retry_delay_is_capped(self) -> None:
        policy = PoliteDownloadPolicy(retry_base_delay_seconds=2, retry_max_delay_seconds=10)
        self.assertEqual(2, policy.retry_delay(1))
        self.assertEqual(4, policy.retry_delay(2))
        self.assertEqual(10, policy.retry_delay(9))

    def test_retry_after_overrides_exponential_delay(self) -> None:
        policy = PoliteDownloadPolicy(retry_base_delay_seconds=2, retry_max_delay_seconds=10)
        self.assertEqual(7.0, policy.retry_delay(1, retry_after="7"))

    def test_host_throttle_reports_wait_time(self) -> None:
        throttle = HostThrottle(PoliteDownloadPolicy(min_delay_per_host_seconds=0.01))
        self.assertEqual(0.0, throttle.wait_for_url("https://example.test/a"))
        self.assertGreaterEqual(throttle.wait_for_url("https://example.test/b"), 0.0)


if __name__ == "__main__":
    unittest.main()
