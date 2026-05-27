from __future__ import annotations

import contextlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from api_launcher.crawler_assets import CrawlerAsset
from api_launcher.models import Provider
from api_launcher.paths import PROJECT_ROOT, catalog_file
from api_launcher.registry import PROVIDER_CATALOG_NAME, load_provider_catalog


ENV_LINE_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")
ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
PLACEHOLDER_PREFIXES = (
    "your_",
    "paste_your_own",
    "replace_with",
    "changeme",
    "todo",
)
SECRET_PREFIXES = ("sk-", "ghp_", "github_pat_", "eyj")
CREDENTIAL_BLOCKING_STATUSES = frozenset(
    {
        "missing_credentials",
        "partial_credentials",
        "credential_profile_required",
    }
)


@dataclass(frozen=True)
class CredentialFieldStatus:
    env_var: str
    configured: bool
    configured_source: str
    required: bool
    value_preview: str
    label: str
    help_text: str

    def to_dict(self) -> dict[str, object]:
        return {
            "env_var": self.env_var,
            "configured": self.configured,
            "configured_source": self.configured_source,
            "required": self.required,
            "value_preview": self.value_preview,
            "label": self.label,
            "help_text": self.help_text,
            "control": "password",
        }


@dataclass(frozen=True)
class CredentialDisplayProfile:
    """UI-neutral credential display contract for Tk/Web/future Qt."""

    status: str
    label: str
    tone: str
    badge_label: str
    summary_zh_TW: str
    summary_en: str
    next_action: str

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "label": self.label,
            "tone": self.tone,
            "badge_label": self.badge_label,
            "summary_zh_TW": self.summary_zh_TW,
            "summary_en": self.summary_en,
            "next_action": self.next_action,
        }


def local_env_path() -> Path:
    return PROJECT_ROOT / ".env"


def provider_for_id(provider_id: str, provider_catalog_path: str | Path | None = None) -> Provider | None:
    key = provider_id.strip()
    if not key:
        return None
    path = Path(provider_catalog_path) if provider_catalog_path is not None else catalog_file(PROVIDER_CATALOG_NAME)
    for provider in load_provider_catalog(path):
        if provider.provider_id == key:
            return provider
    return None


def crawler_asset_credential_status(
    asset: CrawlerAsset,
    *,
    env_path: str | Path | None = None,
    provider_catalog_path: str | Path | None = None,
) -> dict[str, object]:
    """Return UI-safe local credential status for one crawler asset.

    The payload deliberately never includes raw credential values. Web/Tk/Qt can
    render it as a login-style edit panel while secrets stay in the local
    ignored settings file or current process environment.
    """

    target_env = Path(env_path) if env_path is not None else local_env_path()
    provider = provider_for_id(asset.provider_id, provider_catalog_path)
    env_values = read_env_values(target_env)
    required = asset_requires_credentials(asset)
    env_names = credential_env_vars_for_asset(asset, provider)
    fields = [
        credential_field_status(name, env_values=env_values, required=required)
        for name in env_names
    ]
    configured_count = sum(1 for field in fields if field.configured)
    missing_required = [field.env_var for field in fields if field.required and not field.configured]
    status = credential_status_code(
        requires_credentials=required,
        field_count=len(fields),
        configured_count=configured_count,
        missing_required=missing_required,
    )
    next_action = credential_next_action(status)
    display_profile = credential_display_profile(
        status=status,
        configured_count=configured_count,
        field_count=len(fields),
        missing_required=missing_required,
        next_action=next_action,
    )
    docs_url = first_text(asset.docs_url, provider.docs_url if provider is not None else "")
    signup_url = provider.signup_url if provider is not None else ""
    entry_url = first_text(signup_url, docs_url)
    return {
        "status": status,
        "display_label": display_profile.label,
        "display_tone": display_profile.tone,
        "display_profile": display_profile.to_dict(),
        "display_badge_label": display_profile.badge_label,
        "display_summary_zh_TW": display_profile.summary_zh_TW,
        "display_summary_en": display_profile.summary_en,
        "requires_credentials": required,
        "configured_count": configured_count,
        "field_count": len(fields),
        "missing_required": missing_required,
        "fields": [field.to_dict() for field in fields],
        "credential_profile_id": asset.credential_profile_id,
        "api_key_env_var": asset.api_key_env_var,
        "account_hint": asset.account_hint,
        "provider_id": asset.provider_id,
        "provider_name": provider.name if provider is not None else "",
        "auth_type": provider.auth_type if provider is not None else "",
        "docs_url": docs_url,
        "signup_url": signup_url,
        "credential_entry_url": entry_url,
        "credential_entry_label": credential_entry_label(signup_url=signup_url, docs_url=docs_url),
        "env_path": str(target_env),
        "env_file_exists": target_env.exists(),
        "remember_local_default": True,
        "session_only_supported": True,
        "safety_note_zh_TW": "這是本機登入設定；Web Preview 不會把明文金鑰寫進事件紀錄或 JSON 回應。",
        "next_action": next_action,
    }


def update_crawler_asset_credentials(
    asset: CrawlerAsset,
    payload: Mapping[str, object],
    *,
    env_path: str | Path | None = None,
    provider_catalog_path: str | Path | None = None,
) -> dict[str, object]:
    target_env = Path(env_path) if env_path is not None else local_env_path()
    provider = provider_for_id(asset.provider_id, provider_catalog_path)
    allowed_env_vars = set(credential_env_vars_for_asset(asset, provider))
    values, clear = credential_update_from_payload(payload, allowed_env_vars)
    remember_local = credential_remember_local(payload)
    if remember_local or clear:
        write_env_updates(target_env, values=values if remember_local else {}, clear=clear)
    for key, value in values.items():
        os.environ[key] = value
    for key in clear:
        os.environ.pop(key, None)
    status = crawler_asset_credential_status(
        asset,
        env_path=target_env,
        provider_catalog_path=provider_catalog_path,
    )
    status["remember_local"] = remember_local
    return status


def credential_remember_local(payload: Mapping[str, object]) -> bool:
    raw = payload.get("remember_local", True)
    if isinstance(raw, str):
        return raw.strip().lower() not in {"0", "false", "no", "off"}
    return bool(raw)


def credential_update_from_payload(
    payload: Mapping[str, object],
    allowed_env_vars: set[str],
) -> tuple[dict[str, str], set[str]]:
    raw_values = payload.get("values")
    raw_clear = payload.get("clear")
    values: dict[str, str] = {}
    clear: set[str] = set()
    if isinstance(raw_values, Mapping):
        for raw_key, raw_value in raw_values.items():
            key = normalize_env_name(str(raw_key))
            if not key or key not in allowed_env_vars:
                raise ValueError(f"credential env var is not editable for this asset: {raw_key}")
            value = str(raw_value or "")
            if not value:
                continue
            if "\n" in value or "\r" in value:
                raise ValueError(f"credential value for {key} must be a single line")
            values[key] = value
    if isinstance(raw_clear, list):
        for raw_key in raw_clear:
            key = normalize_env_name(str(raw_key))
            if not key or key not in allowed_env_vars:
                raise ValueError(f"credential env var is not editable for this asset: {raw_key}")
            clear.add(key)
    clear.difference_update(values)
    return values, clear


def credential_env_vars_for_asset(asset: CrawlerAsset, provider: Provider | None = None) -> tuple[str, ...]:
    names: list[str] = []
    for name in (asset.api_key_env_var, *(provider.template_env_vars() if provider is not None else ())):
        normalized = normalize_env_name(name)
        if normalized and normalized not in names:
            names.append(normalized)
    return tuple(names)


def asset_requires_credentials(asset: CrawlerAsset) -> bool:
    if asset.access_requirement == "crawler_managed_auth":
        return True
    for capability in asset.capabilities:
        if capability.credential_mode == "user_credential_required":
            return True
    return False


def credential_field_status(
    env_var: str,
    *,
    env_values: Mapping[str, str],
    required: bool,
) -> CredentialFieldStatus:
    file_value = env_values.get(env_var, "")
    process_value = os.environ.get(env_var, "")
    file_configured = is_configured_secret(file_value)
    process_configured = is_configured_secret(process_value)
    if file_configured:
        configured_source = "env_file"
        value_preview = mask_secret(file_value)
    elif process_configured:
        configured_source = "process_env"
        value_preview = mask_secret(process_value)
    else:
        configured_source = "missing"
        value_preview = ""
    return CredentialFieldStatus(
        env_var=env_var,
        configured=file_configured or process_configured,
        configured_source=configured_source,
        required=required,
        value_preview=value_preview,
        label=credential_field_label(env_var),
        help_text="貼上官方入口提供的 API Key、Token 或帳號密碼；留空代表不變，勾選清除才會移除。",
    )


def credential_status_code(
    *,
    requires_credentials: bool,
    field_count: int,
    configured_count: int,
    missing_required: list[str],
) -> str:
    if not requires_credentials and field_count == 0:
        return "public_no_credentials"
    if not requires_credentials:
        return "optional_credentials_configured" if configured_count else "optional_credentials_available"
    if not field_count:
        return "credential_profile_required"
    if missing_required and configured_count:
        return "partial_credentials"
    if missing_required:
        return "missing_credentials"
    return "configured"


def credential_status_label(status: str) -> str:
    labels = {
        "public_no_credentials": "免登入",
        "optional_credentials_available": "可選登入",
        "optional_credentials_configured": "已設定可選登入",
        "credential_profile_required": "需要登入設定",
        "missing_credentials": "需要登入 / API Key",
        "partial_credentials": "登入資訊未完整",
        "configured": "已設定登入",
    }
    return labels.get(status, status)


def credential_status_tone(status: str) -> str:
    if status in {"public_no_credentials", "configured", "optional_credentials_configured"}:
        return "success"
    if status in {"missing_credentials", "partial_credentials", "credential_profile_required"}:
        return "warning"
    return "neutral"


def credential_next_action(status: str) -> str:
    if status in {"missing_credentials", "partial_credentials", "credential_profile_required"}:
        return "edit_local_credentials_before_live_download"
    if status in {"optional_credentials_available"}:
        return "optional_edit_local_credentials"
    return "continue_to_bounds_or_download_plan"


def credential_display_profile(
    *,
    status: str,
    configured_count: int,
    field_count: int,
    missing_required: list[str] | tuple[str, ...],
    next_action: str,
) -> CredentialDisplayProfile:
    """Build the display profile shared by desktop/web surfaces."""

    label = credential_status_label(status)
    tone = credential_status_tone(status)
    missing_text = ", ".join(str(item) for item in missing_required if str(item).strip())
    if field_count:
        badge_label = f"{label} {configured_count}/{field_count}"
        summary_zh = f"登入：{label}（{configured_count}/{field_count}）"
        summary_en = f"Login: {label} ({configured_count}/{field_count})"
    else:
        badge_label = label
        summary_zh = f"登入：{label}"
        summary_en = f"Login: {label}"
    if missing_text:
        summary_zh = f"{summary_zh}；缺少 {missing_text}"
        summary_en = f"{summary_en}; missing {missing_text}"
    if next_action:
        summary_zh = f"{summary_zh}；下一步：{next_action}"
        summary_en = f"{summary_en}; next: {next_action}"
    return CredentialDisplayProfile(
        status=status,
        label=label,
        tone=tone,
        badge_label=badge_label,
        summary_zh_TW=summary_zh,
        summary_en=summary_en,
        next_action=next_action,
    )


def credential_status_blocks_download(status_or_payload: object) -> bool:
    """Return whether live listing/download should stop before a doomed request.

    The guard is intentionally backend-owned so Tk, Web, and future Qt do not
    each keep a slightly different list of credential-blocking states.
    """

    if isinstance(status_or_payload, Mapping):
        status = str(status_or_payload.get("status") or "")
    else:
        status = str(status_or_payload or "")
    return status in CREDENTIAL_BLOCKING_STATUSES


def credential_entry_label(*, signup_url: str, docs_url: str) -> str:
    if signup_url:
        return "開啟官方登入 / 申請 API Key"
    if docs_url:
        return "開啟官方文件"
    return ""


def credential_field_label(env_var: str) -> str:
    name = normalize_env_name(env_var)
    lowered = name.lower()
    if "username" in lowered or lowered.endswith("_user"):
        return "帳號"
    if "password" in lowered or "passwd" in lowered:
        return "密碼"
    if "client_id" in lowered:
        return "Client ID"
    if "client_secret" in lowered:
        return "Client Secret"
    if "token" in lowered:
        return "Access Token"
    if "api_key" in lowered or lowered.endswith("_key"):
        return "API Key"
    return "登入資訊"


def read_env_values(path: str | Path) -> dict[str, str]:
    target = Path(path)
    if not target.exists():
        return {}
    values: dict[str, str] = {}
    for line in target.read_text(encoding="utf-8-sig").splitlines():
        match = ENV_LINE_RE.match(line)
        if not match:
            continue
        key = normalize_env_name(match.group(1))
        if not key:
            continue
        _, raw_value = line.split("=", 1)
        values[key] = parse_env_value(raw_value.strip())
    return values


def write_env_updates(path: str | Path, *, values: Mapping[str, str], clear: set[str]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    existing_lines = target.read_text(encoding="utf-8-sig").splitlines() if target.exists() else []
    if not existing_lines:
        existing_lines = [
            "# APIkeys_collection local credentials",
            "# Generated by RRKAL Web Preview. This file is ignored by Git.",
            "",
        ]
    handled: set[str] = set()
    output: list[str] = []
    for line in existing_lines:
        match = ENV_LINE_RE.match(line)
        if not match:
            output.append(line)
            continue
        key = normalize_env_name(match.group(1))
        if key in values:
            output.append(f"{key}={format_env_value(values[key])}")
            handled.add(key)
        elif key in clear:
            output.append(f"{key}=")
            handled.add(key)
        else:
            output.append(line)
    for key, value in values.items():
        if key not in handled:
            output.extend(("", f"{key}={format_env_value(value)}"))
    for key in sorted(clear):
        if key not in handled:
            output.extend(("", f"{key}="))
    content = "\n".join(output).rstrip() + "\n"
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temp_name, target)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(temp_name)
        raise
    return target


def normalize_env_name(value: str) -> str:
    text = str(value or "").strip()
    if not text or not ENV_NAME_RE.fullmatch(text):
        return ""
    return text


def parse_env_value(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        text = text[1:-1]
        if value.strip().startswith('"'):
            text = text.replace(r"\"", '"').replace(r"\\", "\\")
    return text


def format_env_value(value: str) -> str:
    text = str(value)
    if not text:
        return ""
    if any(char.isspace() for char in text) or "#" in text or '"' in text or "\\" in text:
        return '"' + text.replace("\\", "\\\\").replace('"', r"\"") + '"'
    return text


def is_configured_secret(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    lowered = text.lower()
    if lowered in {"none", "null", "changeme", "todo"}:
        return False
    return not any(lowered.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES)


def mask_secret(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    suffix = text[-4:] if len(text) >= 4 else text[-1:]
    return "****" + suffix


def first_text(*values: str) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


__all__ = [
    "CREDENTIAL_BLOCKING_STATUSES",
    "CredentialDisplayProfile",
    "crawler_asset_credential_status",
    "credential_display_profile",
    "credential_env_vars_for_asset",
    "credential_status_blocks_download",
    "local_env_path",
    "provider_for_id",
    "read_env_values",
    "update_crawler_asset_credentials",
    "write_env_updates",
]
