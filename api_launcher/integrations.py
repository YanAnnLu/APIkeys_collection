from __future__ import annotations

import json
import os
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib import request

from api_launcher.download_policy import PoliteDownloadPolicy
from api_launcher.models import Provider
from api_launcher.paths import config_file, local_config_file


LOCAL_INTEGRATIONS_NAME = "launcher_integrations.local.json"
EXAMPLE_INTEGRATIONS_NAME = "launcher_integrations.example.json"


@dataclass(frozen=True)
class DatabaseClientProfile:
    id: str
    label: str
    kind: str
    enabled: bool
    command: tuple[str, ...]
    notes: str = ""


@dataclass(frozen=True)
class AiSummaryProfile:
    id: str
    label: str
    kind: str
    enabled: bool
    model: str
    endpoint: str
    api_key_env: str = ""
    notes: str = ""


@dataclass(frozen=True)
class DownloadToolProfile:
    id: str
    label: str
    kind: str
    enabled: bool
    command: tuple[str, ...]
    supports_resume: bool
    supports_parallel: bool
    notes: str = ""


@dataclass(frozen=True)
class UnrealProjectProfile:
    id: str
    label: str
    enabled: bool
    engine_root: str
    editor_command: tuple[str, ...]
    project_path: str = ""
    content_root: str = ""
    bridge_subdir: str = "APIkeysCollection"
    notes: str = ""


def integrations_path() -> Path:
    local_path = local_integrations_path()
    if local_path.exists():
        return local_path
    return example_integrations_path()


def local_integrations_path() -> Path:
    return local_config_file(LOCAL_INTEGRATIONS_NAME)


def example_integrations_path() -> Path:
    return config_file(EXAMPLE_INTEGRATIONS_NAME)


def load_integration_config() -> dict[str, object]:
    path = integrations_path()
    if not path.exists():
        return {"database_clients": []}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def ensure_local_integration_config() -> dict[str, object]:
    local_path = local_integrations_path()
    if local_path.exists():
        return json.loads(local_path.read_text(encoding="utf-8-sig"))
    config = load_integration_config()
    save_integration_config(config)
    return config


def save_integration_config(config: dict[str, object]) -> Path:
    path = local_integrations_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def set_active_database_client(profile_id: str) -> DatabaseClientProfile:
    config = ensure_local_integration_config()
    profiles = database_client_profiles_from_config(config)
    if not any(profile.id == profile_id for profile in profiles):
        raise RuntimeError(f"Unknown database client profile: {profile_id}")
    config["active_database_client"] = profile_id
    save_integration_config(config)
    profile = next((item for item in database_client_profiles() if item.id == profile_id), None)
    if profile is None:
        raise RuntimeError(f"Database client profile is not available on this platform: {profile_id}")
    return profile


def database_client_profiles() -> list[DatabaseClientProfile]:
    return database_client_profiles_from_config(load_integration_config())


def database_client_profiles_from_config(config: dict[str, object]) -> list[DatabaseClientProfile]:
    system = platform.system()
    profiles = []
    for item in config.get("database_clients", []):
        command_by_platform = item.get("command_by_platform") or {}
        command = command_by_platform.get(system) or item.get("command") or ()
        if isinstance(command, str):
            command = (command,)
        profiles.append(
            DatabaseClientProfile(
                id=str(item.get("id") or "").strip(),
                label=str(item.get("label") or "").strip(),
                kind=str(item.get("kind") or "").strip(),
                enabled=bool(item.get("enabled", True)),
                command=tuple(str(value) for value in command),
                notes=str(item.get("notes") or "").strip(),
            )
        )
    return [profile for profile in profiles if profile.id and profile.label and profile.command]


def active_database_client() -> DatabaseClientProfile | None:
    config = load_integration_config()
    active_id = str(config.get("active_database_client") or "").strip()
    profiles = database_client_profiles()
    if active_id:
        for profile in profiles:
            if profile.id == active_id and profile.enabled:
                return profile
    return next((profile for profile in profiles if profile.enabled), None)


def open_database_client(profile_id: str | None = None) -> DatabaseClientProfile:
    profiles = database_client_profiles()
    profile = None
    if profile_id:
        profile = next((item for item in profiles if item.id == profile_id), None)
    else:
        profile = active_database_client()
    if profile is None:
        raise RuntimeError("No enabled database client profile is configured.")
    if not profile.command:
        raise RuntimeError(f"Database client profile has no command: {profile.id}")
    subprocess.Popen(profile.command)
    return profile


def download_tool_profiles() -> list[DownloadToolProfile]:
    return download_tool_profiles_from_config(load_integration_config())


def download_tool_profiles_from_config(config: dict[str, object]) -> list[DownloadToolProfile]:
    system = platform.system()
    profiles = []
    for item in config.get("download_tools", []):
        command_by_platform = item.get("command_by_platform") or {}
        command = command_by_platform.get(system) or item.get("command") or ()
        if isinstance(command, str):
            command = (command,)
        profiles.append(
            DownloadToolProfile(
                id=str(item.get("id") or "").strip(),
                label=str(item.get("label") or "").strip(),
                kind=str(item.get("kind") or "").strip(),
                enabled=bool(item.get("enabled", True)),
                command=tuple(str(value) for value in command),
                supports_resume=bool(item.get("supports_resume", False)),
                supports_parallel=bool(item.get("supports_parallel", False)),
                notes=str(item.get("notes") or "").strip(),
            )
        )
    return [profile for profile in profiles if profile.id and profile.label and profile.kind]


def active_download_tool() -> DownloadToolProfile | None:
    config = load_integration_config()
    active_id = str(config.get("active_download_tool") or "").strip()
    profiles = download_tool_profiles()
    if active_id:
        for profile in profiles:
            if profile.id == active_id and profile.enabled:
                return profile
    return next((profile for profile in profiles if profile.enabled), None)


def active_download_policy() -> PoliteDownloadPolicy:
    return download_policy_from_config(load_integration_config())


def unreal_project_profiles() -> list[UnrealProjectProfile]:
    return unreal_project_profiles_from_config(load_integration_config())


def unreal_project_profiles_from_config(config: dict[str, object]) -> list[UnrealProjectProfile]:
    system = platform.system()
    profiles = []
    for item in config.get("unreal_projects", []):
        editor_by_platform = item.get("editor_command_by_platform") or {}
        editor_command = editor_by_platform.get(system) or item.get("editor_command") or ()
        if isinstance(editor_command, str):
            editor_command = (editor_command,)
        engine_root_by_platform = item.get("engine_root_by_platform") or {}
        engine_root = engine_root_by_platform.get(system) or item.get("engine_root") or ""
        profiles.append(
            UnrealProjectProfile(
                id=str(item.get("id") or "").strip(),
                label=str(item.get("label") or "").strip(),
                enabled=bool(item.get("enabled", True)),
                engine_root=str(engine_root or "").strip(),
                editor_command=tuple(str(value) for value in editor_command),
                project_path=str(item.get("project_path") or "").strip(),
                content_root=str(item.get("content_root") or "").strip(),
                bridge_subdir=str(item.get("bridge_subdir") or "APIkeysCollection").strip() or "APIkeysCollection",
                notes=str(item.get("notes") or "").strip(),
            )
        )
    return [profile for profile in profiles if profile.id and profile.label]


def active_unreal_project() -> UnrealProjectProfile | None:
    config = load_integration_config()
    active_id = str(config.get("active_unreal_project") or "").strip()
    profiles = unreal_project_profiles()
    if active_id:
        for profile in profiles:
            if profile.id == active_id and profile.enabled:
                return profile
    return next((profile for profile in profiles if profile.enabled), None)


def download_policy_from_config(config: dict[str, object]) -> PoliteDownloadPolicy:
    policy = config.get("download_policy") or {}
    if not isinstance(policy, dict):
        policy = {}
    cooldown_codes = policy.get("cooldown_status_codes", (429, 503))
    if isinstance(cooldown_codes, list):
        cooldown_codes = tuple(int(value) for value in cooldown_codes)
    elif not isinstance(cooldown_codes, tuple):
        cooldown_codes = (429, 503)
    return PoliteDownloadPolicy(
        max_parallel_jobs=max(1, int(policy.get("max_parallel_jobs", 3))),
        max_parallel_per_host=max(1, int(policy.get("max_parallel_per_host", 1))),
        min_delay_per_host_seconds=max(0.0, float(policy.get("min_delay_per_host_seconds", 1.0))),
        max_retries=max(1, int(policy.get("max_retries", 5))),
        retry_base_delay_seconds=max(0.0, float(policy.get("retry_base_delay_seconds", 2.0))),
        retry_max_delay_seconds=max(0.0, float(policy.get("retry_max_delay_seconds", 120.0))),
        cooldown_status_codes=tuple(cooldown_codes),
        user_agent=str(policy.get("user_agent") or PoliteDownloadPolicy().user_agent),
    )


def ai_summary_profiles() -> list[AiSummaryProfile]:
    config = load_integration_config()
    profiles = []
    for item in config.get("ai_summary_profiles", []):
        profiles.append(
            AiSummaryProfile(
                id=str(item.get("id") or "").strip(),
                label=str(item.get("label") or "").strip(),
                kind=str(item.get("kind") or "").strip(),
                enabled=bool(item.get("enabled", True)),
                model=str(item.get("model") or "").strip(),
                endpoint=str(item.get("endpoint") or "").strip(),
                api_key_env=str(item.get("api_key_env") or "").strip(),
                notes=str(item.get("notes") or "").strip(),
            )
        )
    return [
        profile
        for profile in profiles
        if profile.id and profile.label and profile.kind and profile.model and profile.endpoint
    ]


def active_ai_profile() -> AiSummaryProfile | None:
    config = load_integration_config()
    active_id = str(config.get("active_ai_summary_profile") or "").strip()
    profiles = ai_summary_profiles()
    if active_id:
        for profile in profiles:
            if profile.id == active_id and profile.enabled:
                return profile
    return next((profile for profile in profiles if profile.enabled), None)


def generate_provider_summary(provider: Provider, profile_id: str | None = None, timeout: float = 30.0) -> str:
    profile = _find_ai_profile(profile_id)
    prompt = _provider_summary_prompt(provider)
    if profile.kind == "ollama":
        return _generate_with_ollama(profile, prompt, timeout)
    if profile.kind == "gemini":
        return _generate_with_gemini(profile, prompt, timeout)
    raise RuntimeError(f"Unsupported AI summary profile kind: {profile.kind}")


def _find_ai_profile(profile_id: str | None) -> AiSummaryProfile:
    profiles = ai_summary_profiles()
    if profile_id:
        profile = next((item for item in profiles if item.id == profile_id and item.enabled), None)
    else:
        profile = active_ai_profile()
    if profile is None:
        raise RuntimeError("No enabled AI summary profile is configured.")
    return profile


def _provider_summary_prompt(provider: Provider) -> str:
    return "\n".join(
        [
            "請用繁體中文為這個資料庫/API 來源寫一段 launcher 內使用的簡短說明。",
            "請聚焦：它提供什麼資料、適合什麼研究/工程用途、使用前需要注意什麼認證或限制。",
            "輸出 3 到 5 句，不要寫行銷文，不要編造不存在的功能。",
            f"名稱: {provider.name}",
            f"Owner: {provider.owner}",
            f"Categories: {', '.join(provider.categories)}",
            f"Scope: {provider.geographic_scope}",
            f"Auth: {provider.auth_type}",
            f"Key env var: {provider.key_env_var or 'none'}",
            f"Docs URL: {provider.docs_url}",
            f"API URL: {provider.api_base_url or 'none'}",
            f"Signup URL: {provider.signup_url or 'none'}",
            f"Existing notes: {provider.notes or 'none'}",
        ]
    )


def _post_json(url: str, payload: dict[str, object], headers: dict[str, str] | None, timeout: float) -> dict[str, object]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _generate_with_ollama(profile: AiSummaryProfile, prompt: str, timeout: float) -> str:
    data = _post_json(
        profile.endpoint,
        {"model": profile.model, "prompt": prompt, "stream": False},
        headers=None,
        timeout=timeout,
    )
    text = str(data.get("response") or "").strip()
    if not text:
        raise RuntimeError("Ollama returned an empty summary.")
    return text


def _generate_with_gemini(profile: AiSummaryProfile, prompt: str, timeout: float) -> str:
    api_key = os.environ.get(profile.api_key_env or "GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(f"Missing API key environment variable: {profile.api_key_env or 'GEMINI_API_KEY'}")
    endpoint = profile.endpoint.format(model=profile.model)
    data = _post_json(
        endpoint,
        {"contents": [{"parts": [{"text": prompt}]}]},
        headers={"x-goog-api-key": api_key},
        timeout=timeout,
    )
    candidates = data.get("candidates") or []
    parts = ((candidates[0] or {}).get("content") or {}).get("parts") if candidates else []
    text = "\n".join(str(part.get("text") or "") for part in parts or []).strip()
    if not text:
        raise RuntimeError("Gemini returned an empty summary.")
    return text
