from __future__ import annotations

import json
import os
import time
from pathlib import Path

from api_launcher.paths import PROJECT_ROOT


DEFAULT_AI_API_KEY_STORE = "state/private/ai_api_keys.private.json"


def api_key_store_path(store: str | Path | None = None) -> Path:
    path = Path(store or DEFAULT_AI_API_KEY_STORE).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def default_api_key_env(profile: object) -> str:
    configured = str(getattr(profile, "api_key_env", "") or "").strip()
    if configured:
        return configured
    kind = str(getattr(profile, "kind", "") or "").strip()
    if kind == "gemini":
        return "GEMINI_API_KEY"
    if kind in {"openai", "openai_compatible"}:
        return "OPENAI_API_KEY"
    return ""


def save_ai_api_key(profile: object, api_key: str, store: str | Path | None = None) -> Path:
    profile_id = str(getattr(profile, "id", "") or "").strip()
    if not profile_id:
        raise RuntimeError("AI profile has no id.")
    env_name = default_api_key_env(profile)
    if not env_name:
        raise RuntimeError(f"{profile_id} has no API key environment variable.")
    path = api_key_store_path(store)
    data = _load_store(path)
    profiles = data.setdefault("profiles", {})
    profiles[profile_id] = {
        "label": str(getattr(profile, "label", "") or profile_id),
        "kind": str(getattr(profile, "kind", "") or ""),
        "api_key_env": env_name,
        "api_key": api_key,
        "updated_at": int(time.time()),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def load_saved_ai_api_keys(profiles: list[object], store: str | Path | None = None) -> list[str]:
    data = _load_store(api_key_store_path(store))
    saved = data.get("profiles") if isinstance(data.get("profiles"), dict) else {}
    loaded_labels: list[str] = []
    for profile in profiles:
        profile_id = str(getattr(profile, "id", "") or "").strip()
        item = saved.get(profile_id) if isinstance(saved, dict) else None
        if not isinstance(item, dict):
            continue
        api_key = str(item.get("api_key") or "").strip()
        env_name = str(item.get("api_key_env") or default_api_key_env(profile)).strip()
        if not api_key or not env_name:
            continue
        if not os.environ.get(env_name, "").strip():
            os.environ[env_name] = api_key
        loaded_labels.append(str(getattr(profile, "label", "") or profile_id))
    return loaded_labels


def saved_ai_api_key_status(profile: object, store: str | Path | None = None) -> tuple[str, str]:
    profile_id = str(getattr(profile, "id", "") or "").strip()
    env_name = default_api_key_env(profile)
    if env_name and os.environ.get(env_name, "").strip():
        return "ready", f"{env_name} is loaded for this session."
    data = _load_store(api_key_store_path(store))
    saved = data.get("profiles") if isinstance(data.get("profiles"), dict) else {}
    item = saved.get(profile_id) if isinstance(saved, dict) else None
    if isinstance(item, dict) and str(item.get("api_key") or "").strip():
        return "stored", f"{env_name or profile_id} is saved locally but not loaded."
    return "missing", f"No saved API key for {profile_id}."


def _load_store(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"schema_version": 1, "profiles": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": 1, "profiles": {}}
    if not isinstance(data, dict):
        return {"schema_version": 1, "profiles": {}}
    data.setdefault("schema_version", 1)
    if not isinstance(data.get("profiles"), dict):
        data["profiles"] = {}
    return data
