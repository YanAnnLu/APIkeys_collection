from __future__ import annotations

import time
import threading
import urllib.parse
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PoliteDownloadPolicy:
    # 下載政策預設偏保守；公開資料入口常有 rate limit，MVP 先保護供應商與使用者 IP。
    max_parallel_jobs: int = 3
    max_parallel_per_host: int = 1
    min_delay_per_host_seconds: float = 1.0
    max_retries: int = 5
    retry_base_delay_seconds: float = 2.0
    retry_max_delay_seconds: float = 120.0
    cooldown_status_codes: tuple[int, ...] = (429, 503)
    user_agent: str = "APIkeys_collection/0.3 (+polite-downloader; contact: local-user)"

    def retry_delay(self, attempt: int, retry_after: str | None = None) -> float:
        # 伺服器給 Retry-After 時優先遵守；否則用 bounded exponential backoff。
        parsed_retry_after = parse_retry_after_seconds(retry_after)
        if parsed_retry_after is not None:
            return min(self.retry_max_delay_seconds, parsed_retry_after)
        delay = self.retry_base_delay_seconds * (2 ** max(0, attempt - 1))
        return min(self.retry_max_delay_seconds, delay)


@dataclass
class HostThrottle:
    # HostThrottle 是共享狀態，因此用 lock 包住 last_request_at，避免多下載執行緒同時放行。
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
                    # sleep 放在 lock 內代表同一 host 會序列化，符合 per-host polite limit。
                    time.sleep(wait_seconds)
            self.last_request_at[host] = time.monotonic()
            return wait_seconds


def host_key(url: str) -> str:
    # 只用 netloc 做節流 key；不同 path 的請求仍屬於同一個供應商 host。
    parsed = urllib.parse.urlparse(url)
    return parsed.netloc.lower()


def parse_retry_after_seconds(value: str | None) -> float | None:
    # 目前只接受秒數格式；HTTP-date Retry-After 之後可再補，先避免解析錯日期造成過長等待。
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
