from __future__ import annotations

from typing import Iterable

from api_launcher.db import utc_now_iso
from api_launcher.models import Provider


def build_download_plan(
    providers: Iterable[Provider],
    plan_name: str,
    downstream_renderer: str = "taichi_global_bathymetry.py",
) -> dict[str, object]:
    provider_list = list(providers)
    return {
        "schema_version": 1,
        "created_at": utc_now_iso(),
        "plan_name": plan_name.strip() or "Untitled download plan",
        "role": "download plan only; no bulk data has been downloaded",
        "downstream_renderer": downstream_renderer,
        "summary": {
            "provider_count": len(provider_list),
            "status": "planned",
        },
        "download_policy": {
            "io_model": "nonblocking",
            "max_parallel_jobs": 3,
            "supports_pause": True,
            "supports_resume": True,
            "supports_retry": True,
        },
        "providers": [provider_plan_entry(provider) for provider in provider_list],
    }


def provider_plan_entry(provider: Provider) -> dict[str, object]:
    return {
        "provider_id": provider.provider_id,
        "name": provider.name,
        "owner": provider.owner,
        "categories": provider.categories,
        "auth_type": provider.auth_type,
        "key_env_var": provider.key_env_var,
        "docs_url": provider.docs_url,
        "api_base_url": provider.api_base_url,
        "signup_url": provider.signup_url,
        "geographic_scope": provider.geographic_scope,
        "plan_status": "planned",
        "priority": "normal",
        "target": "local_dataset_or_database",
        "notes": provider.notes,
    }
