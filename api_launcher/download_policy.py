from __future__ import annotations

import time
import threading
import urllib.parse
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PoliteDownloadPolicy:
    max_parallel_jobs: int = 3
    max_parallel_per_host: int = 1
    min_delay_per_host_seconds: float = 1.0
    max_retries: int = 5
    retry_base_delay_seconds: float = 2.0
    retry_max_delay_seconds: float = 120.0
    cooldown_status_codes: tuple[int, ...] = (429, 503)
    user_agent: str = "APIkeys_collection/0.3 (+polite-downloader; contact: local-user)"

    def retry_delay(self, attempt: int, retry_after: str | None = None) -> float:
        parsed_retry_after = parse_retry_after_seconds(retry_after)
        if parsed_retry_after is not None:
            return min(self.retry_max_delay_seconds, parsed_retry_after)
        delay = self.retry_base_delay_seconds * (2 ** max(0, attempt - 1))
        return min(self.retry_max_delay_seconds, delay)


@dataclass
class HostThrottle:
    policy: PoliteDownloadPolicy
    last_request_at: dict[str, float] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def wait_for_url(self, url: str) -> float:
        host = host_key(url)
        with self.lock:
            now = time.monotonic()
            last = self.last_request_at.get(host)
            wait_seconds = 0.0
            if last is not None:
                elapsed = now - last
                wait_seconds = max(0.0, self.policy.min_delay_per_host_seconds - elapsed)
                if wait_seconds:
                    time.sleep(wait_seconds)
            self.last_request_at[host] = time.monotonic()
            return wait_seconds


def host_key(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    return parsed.netloc.lower()


def parse_retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    try:
        seconds = float(stripped)
    except ValueError:
        return None
    return max(0.0, seconds)
