"""Shared Tk display helpers for provider labels.

UI workflows often need a human-facing provider label while still keeping the
stable provider id for repository calls, plan keys, and background jobs. This
module keeps that fallback rule in one place so different Tk mixins do not
reintroduce raw or blank provider names independently.
"""

from __future__ import annotations


def provider_display_label(row: object | None, provider_id: str) -> str:
    """Return a user-facing provider label with an explicit id fallback."""

    name = str(getattr(row, "name", "") or "").strip() if row is not None else ""
    if name:
        return name
    provider_id = str(provider_id or "").strip()
    return f"Provider ID：{provider_id}" if provider_id else "Provider 待確認"
