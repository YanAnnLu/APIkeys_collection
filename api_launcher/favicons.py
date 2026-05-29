from __future__ import annotations

import hashlib
import io
import urllib.parse
import urllib.request
from pathlib import Path

from api_launcher.paths import STATE_DIR


FAVICON_CACHE_DIR = STATE_DIR / "favicons"
FAVICON_USER_AGENT = "APIkeys_collection/0.3 (+favicon-cache; metadata only)"
DEFAULT_FAVICON_MAX_BYTES = 128 * 1024


def provider_home_url(*urls: str) -> str:
    # provider 可能同時有首頁、API、文件 URL；取第一個可正規化的網址當 icon 來源。
    for value in urls:
        normalized = normalize_http_url(value)
        if normalized:
            return normalized
    return ""


def normalize_http_url(value: str) -> str:
    # 這個函式只接受 HTTP(S) 網站，不處理本機檔案或自訂 scheme，避免 UI 背景工作碰到私有路徑。
    raw = str(value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    # 用網站根目錄做快取鍵，避免同一供應商因 docs/API 深層路徑產生多個圖示。
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


def favicon_url_for_page(url: str) -> str:
    # 目前 Tk MVP 走保守的 /favicon.ico；中期要升級為解析 HTML link/icon 並優先保留 SVG。
    home = normalize_http_url(url)
    if not home:
        return ""
    parsed = urllib.parse.urlparse(home)
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "/favicon.ico", "", "", ""))


def favicon_cache_path(favicon_url: str) -> Path:
    # hash 完整 favicon URL，避免不安全檔名，也避免 http/https 撞到同一個 cache。
    # 這裡仍回傳 .png 是因為 Tk 顯示層目前需要 bitmap；未來 SVG canonical cache 應另設路徑。
    digest = hashlib.sha1(favicon_url.encode("utf-8")).hexdigest()[:16]
    return FAVICON_CACHE_DIR / f"{digest}.png"


def download_favicon_png(
    favicon_url: str,
    target_path: Path | None = None,
    size: int = 16,
    timeout: float = 4.0,
    max_bytes: int = DEFAULT_FAVICON_MAX_BYTES,
) -> Path:
    # 這個函式產出的 PNG 是 Tk 顯示用衍生快取，不應被視為正式 icon asset 格式。
    if not favicon_url:
        raise RuntimeError("Missing favicon URL.")
    target = target_path or favicon_cache_path(favicon_url)
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(favicon_url, headers={"User-Agent": FAVICON_USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        # favicon 只是 UI 裝飾；限制讀取大小，避免異常伺服器塞入過大 payload。
        payload = response.read(max(1, int(max_bytes)))
    try:
        from PIL import Image
    except Exception as exc:
        raise RuntimeError("Pillow is required to normalize favicon images.") from exc
    image = Image.open(io.BytesIO(payload)).convert("RGBA")
    # thumbnail 會維持原圖比例；下面再置中貼到固定尺寸畫布，避免小圖拉伸變形。
    image.thumbnail((size, size))
    # 統一轉成透明正方形 PNG，讓 Tk 顯示尺寸穩定；SVG-first 會在未來 UI 層處理。
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    x = max((size - image.width) // 2, 0)
    y = max((size - image.height) // 2, 0)
    canvas.paste(image, (x, y), image)
    canvas.save(target, format="PNG")
    return target
