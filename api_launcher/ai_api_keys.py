from __future__ import annotations

import json
import os
import time
from pathlib import Path

from api_launcher.paths import PROJECT_ROOT


# AI key 檔案必須留在 ignored private state；不要把實際 key 寫進 tracked config。
DEFAULT_AI_API_KEY_STORE = "state/private/ai_api_keys.private.json"


def api_key_store_path(store: str | Path | None = None) -> Path:
    # store 參數主要給測試或特殊本機設定；正常情況走 ignored private 預設路徑。
    path = Path(store or DEFAULT_AI_API_KEY_STORE).expanduser()
    if not path.is_absolute():
        # 相對路徑固定落在 repo 底下，避免從不同 cwd 啟動時把 key 寫到不可預期位置。
        path = PROJECT_ROOT / path
    return path


def default_api_key_env(profile: object) -> str:
    # profile 以 object 型別接收，是為了讓此模組可被 dataclass、namedtuple 或測試替身重用。
    configured = str(getattr(profile, "api_key_env", "") or "").strip()
    if configured:
        return configured
    # 舊 profile 可能還沒宣告 env 名稱；用 provider kind 補安全的 MVP 預設。
    kind = str(getattr(profile, "kind", "") or "").strip()
    if kind == "gemini":
        return "GEMINI_API_KEY"
    if kind in {"openai", "openai_compatible"}:
        return "OPENAI_API_KEY"
    return ""


def save_ai_api_key(profile: object, api_key: str, store: str | Path | None = None) -> Path:
    # 保存的是「本機使用者的 credential」，不是 catalog/provider metadata，不能進 Git。
    profile_id = str(getattr(profile, "id", "") or "").strip()
    if not profile_id:
        raise RuntimeError("AI profile has no id.")
    env_name = default_api_key_env(profile)
    if not env_name:
        # 沒有 env 名稱代表 profile 還沒定義 credential 邊界，不能猜一個檔案欄位硬存。
        raise RuntimeError(f"{profile_id} has no API key environment variable.")
    path = api_key_store_path(store)
    data = _load_store(path)
    profiles = data.setdefault("profiles", {})
    # store schema 只放 profile 對應，不放 provider catalog；catalog 仍由公開設定管理。
    # 以 profile_id 當 key，讓同一種 provider 可以有多個模型 profile 各自保存 key。
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
        # POSIX 權限是 best effort；Windows 可能忽略 chmod，所以 ignored private 目錄仍是主要邊界。
        path.chmod(0o600)
    except OSError:
        pass
    return path


def load_saved_ai_api_keys(profiles: list[object], store: str | Path | None = None) -> list[str]:
    # 啟動時只把已保存 key 載入 process env，不把 key 回寫到任何 tracked 設定。
    data = _load_store(api_key_store_path(store))
    saved = data.get("profiles") if isinstance(data.get("profiles"), dict) else {}
    loaded_labels: list[str] = []
    for profile in profiles:
        profile_id = str(getattr(profile, "id", "") or "").strip()
        item = saved.get(profile_id) if isinstance(saved, dict) else None
        if not isinstance(item, dict):
            # 缺少該 profile 的保存項目是正常情況，代表使用者還沒設定。
            continue
        api_key = str(item.get("api_key") or "").strip()
        env_name = str(item.get("api_key_env") or default_api_key_env(profile)).strip()
        if not api_key or not env_name:
            continue
        if not os.environ.get(env_name, "").strip():
            # 不覆蓋已存在的 env，讓使用者臨時注入的 credential 優先於本機保存值。
            os.environ[env_name] = api_key
        loaded_labels.append(str(getattr(profile, "label", "") or profile_id))
    return loaded_labels


def saved_ai_api_key_status(profile: object, store: str | Path | None = None) -> tuple[str, str]:
    # 狀態分成 ready/stored/missing，讓 UI 可以分辨「已載入」與「有保存但尚未載入」。
    profile_id = str(getattr(profile, "id", "") or "").strip()
    env_name = default_api_key_env(profile)
    if env_name and os.environ.get(env_name, "").strip():
        return "ready", f"{env_name} is loaded for this session."
    data = _load_store(api_key_store_path(store))
    saved = data.get("profiles") if isinstance(data.get("profiles"), dict) else {}
    item = saved.get(profile_id) if isinstance(saved, dict) else None
    if isinstance(item, dict) and str(item.get("api_key") or "").strip():
        # stored 代表磁碟有 key 但 process env 尚未載入，UI 可提示重啟或重新載入。
        return "stored", f"{env_name or profile_id} is saved locally but not loaded."
    return "missing", f"No saved API key for {profile_id}."


def _load_store(path: Path) -> dict[str, object]:
    # 回傳固定 schema，呼叫端就不需要到處處理 None 或 malformed JSON。
    if not path.exists():
        return {"schema_version": 1, "profiles": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        # key store 損壞時不要阻擋 UI 啟動；之後由狀態/設定流程提示使用者重存。
        return {"schema_version": 1, "profiles": {}}
    if not isinstance(data, dict):
        return {"schema_version": 1, "profiles": {}}
    data.setdefault("schema_version", 1)
    if not isinstance(data.get("profiles"), dict):
        data["profiles"] = {}
    return data
