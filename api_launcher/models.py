from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class Provider:
    provider_id: str
    name: str
    owner: str
    categories: tuple[str, ...]
    geographic_scope: str
    docs_url: str
    api_base_url: str = ""
    signup_url: str = ""
    auth_type: str = "unknown"
    key_env_var: str = ""
    secret_env_vars: tuple[str, ...] = ()
    license_url: str = ""
    terms_url: str = ""
    notes: str = ""
    crawl_urls: tuple[str, ...] = ()

    def template_env_vars(self) -> tuple[str, ...]:
        values = []
        for env_var in (self.key_env_var, *self.secret_env_vars):
            env_var = (env_var or "").strip()
            if env_var and env_var not in values:
                values.append(env_var)
        return tuple(values)

    def target_urls(self) -> tuple[str, ...]:
        urls = [self.docs_url, self.api_base_url, self.signup_url, self.license_url, self.terms_url]
        urls.extend(self.crawl_urls)
        clean = []
        seen = set()
        for url in urls:
            url = (url or "").strip()
            if not url or url in seen:
                continue
            clean.append(url)
            seen.add(url)
        return tuple(clean)


@dataclasses.dataclass(frozen=True)
class ProviderCatalogEntry:
    provider_id: str
    name: str
    owner: str
    categories: tuple[str, ...]
    geographic_scope: str
    docs_url: str
    api_base_url: str
    signup_url: str
    auth_type: str
    key_env_var: str
    notes: str
    latest_status: int | None
    latest_fetched_at: str
    latest_error: str
    remote_status: str
    local_status: str
    update_status: str
    last_downloaded_at: str
    dataset_path: str
    install_id: str
    install_fingerprint: str
    is_starred: bool
