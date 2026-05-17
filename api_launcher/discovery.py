from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from api_launcher.models import Provider


USER_AGENT = "APIkeys_collection/0.3 (+provider-discovery; metadata only)"
DEFAULT_SEEDS_NAME = "provider_discovery_seeds.json"
LOCAL_SEEDS_NAME = "provider_discovery_seeds.local.json"


@dataclass(frozen=True)
class ProviderSeed:
    provider_id: str
    name: str
    owner: str
    categories: tuple[str, ...]
    geographic_scope: str
    homepage_url: str
    docs_url: str = ""
    api_base_url: str = ""
    signup_url: str = ""
    expected_auth_type: str = "unknown"


@dataclass(frozen=True)
class ProviderCandidate:
    provider: Provider
    dedupe_key: str
    source_url: str
    confidence: float
    evidence: tuple[str, ...]
    source_role: str = "download_source"

    def to_dict(self) -> dict[str, object]:
        return {
            "dedupe_key": self.dedupe_key,
            "source_url": self.source_url,
            "source_role": self.source_role,
            "confidence": self.confidence,
            "evidence": self.evidence,
            **provider_to_dict(self.provider),
        }


def load_discovery_seeds(path: str | Path) -> list[ProviderSeed]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        ProviderSeed(
            provider_id=str(item["provider_id"]).strip(),
            name=str(item["name"]).strip(),
            owner=str(item["owner"]).strip(),
            categories=tuple(str(value).strip() for value in item.get("categories", []) if str(value).strip()),
            geographic_scope=str(item.get("geographic_scope") or "global").strip(),
            homepage_url=str(item["homepage_url"]).strip(),
            docs_url=str(item.get("docs_url") or "").strip(),
            api_base_url=str(item.get("api_base_url") or "").strip(),
            signup_url=str(item.get("signup_url") or "").strip(),
            expected_auth_type=str(item.get("expected_auth_type") or "unknown").strip(),
        )
        for item in data.get("seeds", [])
    ]


def load_all_discovery_seeds(primary_path: str | Path, local_path: str | Path | None = None) -> list[ProviderSeed]:
    paths = [Path(primary_path)]
    if local_path is not None:
        paths.append(Path(local_path))
    seeds: list[ProviderSeed] = []
    seen: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        for seed in load_discovery_seeds(path):
            if seed.provider_id in seen:
                continue
            seen.add(seed.provider_id)
            seeds.append(seed)
    return seeds


def append_discovery_seed(path: str | Path, seed: ProviderSeed) -> None:
    path = Path(path)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = {"schema_version": 1, "seeds": []}
    seeds = [item for item in data.get("seeds", []) if item.get("provider_id") != seed.provider_id]
    seeds.append(seed_to_dict(seed))
    data["seeds"] = sorted(seeds, key=lambda item: item["provider_id"])
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def seed_to_dict(seed: ProviderSeed) -> dict[str, object]:
    return {
        "provider_id": seed.provider_id,
        "name": seed.name,
        "owner": seed.owner,
        "categories": list(seed.categories),
        "geographic_scope": seed.geographic_scope,
        "homepage_url": seed.homepage_url,
        "docs_url": seed.docs_url,
        "api_base_url": seed.api_base_url,
        "signup_url": seed.signup_url,
        "expected_auth_type": seed.expected_auth_type,
    }


def discover_provider_candidates(
    seeds: list[ProviderSeed],
    existing_provider_ids: set[str] | None = None,
    timeout: float = 12.0,
    max_bytes: int = 120_000,
) -> list[ProviderCandidate]:
    existing_provider_ids = existing_provider_ids or set()
    candidates = []
    seen: set[str] = set()
    for seed in seeds:
        if seed.provider_id in existing_provider_ids:
            continue
        candidate = discover_provider_candidate(seed, timeout=timeout, max_bytes=max_bytes)
        if candidate.dedupe_key in seen:
            continue
        seen.add(candidate.dedupe_key)
        candidates.append(candidate)
    return candidates


def discover_provider_candidate(seed: ProviderSeed, timeout: float, max_bytes: int) -> ProviderCandidate:
    url = seed.docs_url or seed.homepage_url
    text, final_url = fetch_text(url, timeout=timeout, max_bytes=max_bytes)
    links = extract_links(text, final_url)
    docs_url = seed.docs_url or choose_link(links, ("doc", "developer", "api"))
    signup_url = seed.signup_url or choose_link(links, ("signup", "register", "key", "token", "account"))
    api_base_url = seed.api_base_url or choose_api_base(links, text)
    auth_type, auth_evidence = infer_auth_type(text, seed.expected_auth_type)
    evidence = tuple(value for value in (auth_evidence, f"crawled: {final_url}") if value)
    provider = Provider(
        provider_id=seed.provider_id,
        name=seed.name,
        owner=seed.owner,
        categories=seed.categories or ("discovered",),
        geographic_scope=seed.geographic_scope,
        docs_url=docs_url or final_url,
        api_base_url=api_base_url,
        signup_url=signup_url,
        auth_type=auth_type,
        key_env_var=key_env_var(seed.provider_id) if auth_type_requires_secret(auth_type) else "",
        notes="Discovered from official metadata seed; review before promoting to the built-in catalog.",
    )
    confidence = 0.5 + 0.15 * bool(docs_url) + 0.15 * bool(api_base_url) + 0.1 * bool(auth_evidence)
    return ProviderCandidate(
        provider=provider,
        dedupe_key=dedupe_key(provider),
        source_url=final_url,
        confidence=min(confidence, 0.95),
        evidence=evidence,
    )


def fetch_text(url: str, timeout: float, max_bytes: int) -> tuple[str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read(max_bytes)
        charset = response.headers.get_content_charset() or "utf-8"
        final_url = response.geturl()
    return data.decode(charset, errors="replace"), final_url


def extract_links(text: str, base_url: str) -> list[str]:
    links = []
    for match in re.finditer(r"""href=["']([^"']+)["']""", text, flags=re.IGNORECASE):
        value = html.unescape(match.group(1)).strip()
        if not value or value.startswith("#"):
            continue
        links.append(urllib.parse.urljoin(base_url, value))
    return links


def choose_link(links: list[str], keywords: tuple[str, ...]) -> str:
    for link in links:
        lowered = link.lower()
        if any(keyword in lowered for keyword in keywords):
            return link
    return ""


def choose_api_base(links: list[str], text: str) -> str:
    for value in re.findall(r"https?://[^\s\"'<>]+", text):
        lowered = value.lower()
        if "api" in lowered and not lowered.endswith((".png", ".jpg", ".svg", ".css", ".js")):
            return value.rstrip(".,)")
    return choose_link(links, ("api",))


def infer_auth_type(text: str, expected: str) -> tuple[str, str]:
    if expected and expected != "unknown":
        return expected, "seed expected auth type"
    lowered = text.lower()
    if "api key" in lowered or "apikey" in lowered:
        if "optional" in lowered or "limit" in lowered:
            return "api_key_optional_or_required_for_limits", "mentions API key and limits"
        return "api_key_required", "mentions API key"
    if "oauth" in lowered:
        return "oauth2_or_account", "mentions OAuth"
    if "token" in lowered:
        return "api_token_required", "mentions token"
    return "unknown", ""


def auth_type_requires_secret(auth_type: str) -> bool:
    lowered = auth_type.lower()
    if lowered.startswith("no_key"):
        return False
    return "api_key" in lowered or "api_token" in lowered or "token" in lowered or "oauth" in lowered


def dedupe_key(provider: Provider) -> str:
    base = provider.api_base_url or provider.docs_url or provider.provider_id
    parsed = urllib.parse.urlparse(base)
    normalized = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path.rstrip('/').lower()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def key_env_var(provider_id: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", provider_id.upper()).strip("_") + "_API_KEY"


def provider_to_dict(provider: Provider) -> dict[str, object]:
    return {
        "provider_id": provider.provider_id,
        "name": provider.name,
        "owner": provider.owner,
        "categories": list(provider.categories),
        "geographic_scope": provider.geographic_scope,
        "docs_url": provider.docs_url,
        "api_base_url": provider.api_base_url,
        "signup_url": provider.signup_url,
        "auth_type": provider.auth_type,
        "key_env_var": provider.key_env_var,
        "license_url": provider.license_url,
        "terms_url": provider.terms_url,
        "notes": provider.notes,
    }
