"""Compatibility exports for dataset discovery crawlers.

New crawler code should live under :mod:`api_launcher.crawlers`.
"""

# 這個模組是舊 import path 的相容層；新邏輯請放在 api_launcher.crawlers 內。
from api_launcher.crawlers.dataset_sources import *  # noqa: F401,F403
from api_launcher.crawlers.metadata import (  # noqa: F401
    analysis_hint_for_family,
    choose_native_format,
    first_link_url,
    infer_data_family,
    matches_any_term,
    merge_categories,
    safe_dataset_id,
    sql_role_for_family,
    storage_hint_for_family,
    temporal_coverage,
    tuple_names,
    viewer_hint_for_family,
)
from api_launcher.crawlers.orchestrator import *  # noqa: F401,F403
