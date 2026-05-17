from __future__ import annotations

import hashlib
import io
import urllib.parse
import urllib.request
from pathlib import Path

from api_launcher.paths import STATE_DIR


FAVICON_CACHE_DIR = STATE_DIR / "favicons"
FAVICON_USER_AGENT = "APIkeys_collection/0.3 (+favicon-cache; metadata only)"


def provider_home_url(*urls: str) -> str:
    for value in urls:
        normalized = normalize_http_url(value)
        if normalized:
            return normalized
    return ""


def normalize_http_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


def favicon_url_for_page(url: str) -> str:
    home = normalize_http_url(url)
    if not home:
        return ""
    parsed = urllib.parse.urlparse(home)
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "/favicon.ico", "", "", ""))


def favicon_cache_path(favicon_url: str) -> Path:
    digest = hashlib.sha1(favicon_url.encode("utf-8")).hexdigest()[:16]
    return FAVICON_CACHE_DIR / f"{digest}.png"


def download_favicon_png(favicon_url: str, target_path: Path | None = None, size: int = 16, timeout: float = 4.0) -> Path:
    if not favicon_url:
        raise RuntimeError("Missing favicon URL.")
    target = target_path or favicon_cache_path(favicon_url)
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(favicon_url, headers={"User-Agent": FAVICON_USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read(128 * 1024)
    try:
        from PIL import Image
    except Exception as exc:
        raise RuntimeError("Pillow is required to normalize favicon images.") from exc
    image = Image.open(io.BytesIO(payload)).convert("RGBA")
    image.thumbnail((size, size))
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    x = max((size - image.width) // 2, 0)
    y = max((size - image.height) // 2, 0)
    canvas.paste(image, (x, y), image)
    canvas.save(target, format="PNG")
    return target
