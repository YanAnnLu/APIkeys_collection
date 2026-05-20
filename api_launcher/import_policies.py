from __future__ import annotations


UI_IMPORT_POLICY_CONFIG_KEY = "ui_import_existing_table_policy"
DEFAULT_UI_IMPORT_POLICY = "rename"
UI_IMPORT_POLICIES = {"rename", "skip", "replace"}


def normalized_ui_import_policy(value: object, default: str = DEFAULT_UI_IMPORT_POLICY) -> str:
    fallback = default if default in UI_IMPORT_POLICIES else DEFAULT_UI_IMPORT_POLICY
    normalized = str(value or "").strip().lower()
    return normalized if normalized in UI_IMPORT_POLICIES else fallback
