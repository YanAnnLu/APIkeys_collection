from __future__ import annotations

import json
import os
import re
import time
import base64
import hashlib
from dataclasses import dataclass
from pathlib import Path
from urllib import error, parse, request

from api_launcher.paths import PROJECT_ROOT


DEVICE_CODE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"
AUTHORIZATION_CODE_GRANT_TYPE = "authorization_code"
GOOGLE_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"


@dataclass(frozen=True)
class OAuthDeviceConfig:
    # OAuth device config 是中期/開發者登入契約；一般 MVP 不應要求使用者提供 client id。
    provider: str
    profile_id: str
    label: str
    enabled: bool
    client_id: str
    client_secret: str
    client_id_env: str
    client_secret_env: str
    authorization_url: str
    device_code_url: str
    token_url: str
    verification_url: str
    scopes: tuple[str, ...]
    token_store: str
    token_env: str


@dataclass(frozen=True)
class OAuthDeviceLoginRequest:
    # login request 是 UI 可顯示的 device-code 狀態，不直接暴露原始 OAuth response。
    provider: str
    profile_id: str
    label: str
    client_id: str
    client_secret: str
    client_id_env: str
    client_secret_env: str
    client_id_available: bool
    verification_url: str
    verification_url_complete: str
    user_code: str
    device_code: str
    expires_in: int
    interval: int
    token_url: str
    token_store: str
    token_env: str
    scopes: tuple[str, ...]
    status: str
    message: str


@dataclass(frozen=True)
class OAuthDeviceTokenResult:
    status: str
    message: str
    access_token: str = ""
    refresh_token: str = ""
    token_type: str = ""
    expires_in: int = 0
    scope: str = ""
    slow_down: bool = False


def oauth_device_config_from_profile(profile: object) -> OAuthDeviceConfig | None:
    # profile 沒有 oauth_device 時才套預設，避免把不支援 OAuth 的模型誤判成可登入。
    raw = getattr(profile, "oauth_device", {}) or {}
    profile_id = str(getattr(profile, "id", "") or "").strip()
    kind = str(getattr(profile, "kind", "") or "").strip()
    if not isinstance(raw, dict) or not raw:
        raw = default_oauth_device_config(profile_id, kind)
    if not raw:
        return None
    provider = str(raw.get("provider") or kind or profile_id).strip()
    token_store = str(raw.get("token_store") or getattr(profile, "token_store", "") or "").strip()
    token_env = str(raw.get("token_env") or getattr(profile, "oauth_token_env", "") or "").strip()
    if not token_store and profile_id:
        token_store = f"state/private/ai_oauth_tokens/{profile_id}.json"
    if not token_env and profile_id:
        token_env = f"AI_OAUTH_ACCESS_TOKEN_{_env_suffix(profile_id)}"
    return OAuthDeviceConfig(
        provider=provider,
        profile_id=profile_id,
        label=str(getattr(profile, "label", "") or profile_id or provider).strip(),
        enabled=bool(raw.get("enabled", True)),
        client_id=str(raw.get("client_id") or "").strip(),
        client_secret=str(raw.get("client_secret") or "").strip(),
        client_id_env=str(raw.get("client_id_env") or "").strip(),
        client_secret_env=str(raw.get("client_secret_env") or "").strip(),
        authorization_url=str(raw.get("authorization_url") or default_authorization_url(provider)).strip(),
        device_code_url=str(raw.get("device_code_url") or "").strip(),
        token_url=str(raw.get("token_url") or "").strip(),
        verification_url=str(raw.get("verification_url") or "").strip(),
        scopes=_scopes_from_raw(raw.get("scopes")),
        token_store=token_store,
        token_env=token_env,
    )


def build_oauth_device_login_request(config: OAuthDeviceConfig, timeout: float = 15.0) -> OAuthDeviceLoginRequest:
    # 建立 device flow 時只檢查必要設定；失敗回傳結構化狀態給 UI，而不是丟出視窗例外。
    if not config.enabled:
        return _empty_request(config, "disabled", f"{config.label} QR/device login is disabled.")
    if not config.device_code_url or not config.token_url:
        return _empty_request(config, "missing_oauth_endpoint", f"{config.label} has no OAuth device-code/token endpoint configured.")
    client_id = config.client_id or (os.environ.get(config.client_id_env, "").strip() if config.client_id_env else "")
    if not client_id:
        target = config.client_id_env or "oauth_device.client_id"
        return _empty_request(config, "missing_client_id", f"Set {target} to enable {config.label} QR/device login.")
    try:
        data = _post_form(
            config.device_code_url,
            {
                "client_id": client_id,
                "scope": " ".join(config.scopes),
            },
            timeout=timeout,
        )
    except Exception as exc:
        return _empty_request(config, "request_failed", f"{config.label} device-code request failed: {exc}", client_id_available=True)
    return OAuthDeviceLoginRequest(
        provider=config.provider,
        profile_id=config.profile_id,
        label=config.label,
        client_id=client_id,
        client_secret=config.client_secret,
        client_id_env=config.client_id_env,
        client_secret_env=config.client_secret_env,
        client_id_available=True,
        verification_url=str(data.get("verification_url") or data.get("verification_uri") or config.verification_url),
        verification_url_complete=str(data.get("verification_url_complete") or data.get("verification_uri_complete") or ""),
        user_code=str(data.get("user_code") or ""),
        device_code=str(data.get("device_code") or ""),
        expires_in=int(data.get("expires_in") or 0),
        interval=max(int(data.get("interval") or 5), 1),
        token_url=config.token_url,
        token_store=config.token_store,
        token_env=config.token_env,
        scopes=config.scopes,
        status="authorization_pending",
        message=f"Scan the QR code or open the device page, then finish {config.label} authorization.",
    )


def poll_oauth_device_token(login_request: OAuthDeviceLoginRequest, timeout: float = 15.0) -> OAuthDeviceTokenResult:
    # poll 一次就返回，讓呼叫端依 interval/slow_down 控制節奏，避免觸犯 OAuth provider 限制。
    client_id = login_request.client_id or (os.environ.get(login_request.client_id_env, "").strip() if login_request.client_id_env else "")
    client_secret = login_request.client_secret or (os.environ.get(login_request.client_secret_env, "").strip() if login_request.client_secret_env else "")
    if not client_id:
        target = login_request.client_id_env or "oauth_device.client_id"
        return OAuthDeviceTokenResult("missing_client_id", f"Missing client id: {target}")
    if not login_request.device_code:
        return OAuthDeviceTokenResult("missing_device_code", f"Missing {login_request.label} device_code; start QR login again.")
    try:
        payload = {
            "client_id": client_id,
            "device_code": login_request.device_code,
            "grant_type": DEVICE_CODE_GRANT_TYPE,
        }
        if client_secret:
            payload["client_secret"] = client_secret
        data = _post_form(login_request.token_url, payload, timeout=timeout)
    except OAuthDevicePending as exc:
        return OAuthDeviceTokenResult(exc.error_code, exc.message, slow_down=exc.error_code == "slow_down")
    except Exception as exc:
        return OAuthDeviceTokenResult("request_failed", f"{login_request.label} token request failed: {exc}")
    access_token = str(data.get("access_token") or "")
    if not access_token:
        return OAuthDeviceTokenResult("empty_token", f"{login_request.label} returned no access_token.")
    return OAuthDeviceTokenResult(
        status="success",
        message=f"{login_request.label} OAuth token received.",
        access_token=access_token,
        refresh_token=str(data.get("refresh_token") or ""),
        token_type=str(data.get("token_type") or ""),
        expires_in=int(data.get("expires_in") or 0),
        scope=str(data.get("scope") or ""),
    )


def oauth_authorization_url(
    config: OAuthDeviceConfig,
    redirect_uri: str,
    state: str,
    code_challenge: str,
) -> str:
    client_id = oauth_client_id(config)
    if not client_id:
        raise RuntimeError(f"Missing OAuth client id: {config.client_id_env or 'oauth_device.client_id'}")
    if not config.authorization_url:
        raise RuntimeError(f"{config.label} has no OAuth authorization URL configured.")
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(config.scopes),
        "state": state,
        "access_type": "offline",
        "prompt": "select_account consent",
        "include_granted_scopes": "true",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return config.authorization_url + "?" + parse.urlencode(params)


def exchange_oauth_authorization_code(
    config: OAuthDeviceConfig,
    code: str,
    redirect_uri: str,
    code_verifier: str,
    timeout: float = 15.0,
) -> OAuthDeviceTokenResult:
    client_id = oauth_client_id(config)
    client_secret = oauth_client_secret(config)
    if not client_id:
        return OAuthDeviceTokenResult("missing_client_id", f"Missing OAuth client id: {config.client_id_env or 'oauth_device.client_id'}")
    payload = {
        "client_id": client_id,
        "code": code,
        "code_verifier": code_verifier,
        "grant_type": AUTHORIZATION_CODE_GRANT_TYPE,
        "redirect_uri": redirect_uri,
    }
    if client_secret:
        payload["client_secret"] = client_secret
    try:
        data = _post_form(config.token_url, payload, timeout=timeout)
    except Exception as exc:
        return OAuthDeviceTokenResult("request_failed", f"{config.label} authorization-code token request failed: {exc}")
    access_token = str(data.get("access_token") or "")
    if not access_token:
        return OAuthDeviceTokenResult("empty_token", f"{config.label} returned no access_token.")
    return OAuthDeviceTokenResult(
        status="success",
        message=f"{config.label} OAuth token received.",
        access_token=access_token,
        refresh_token=str(data.get("refresh_token") or ""),
        token_type=str(data.get("token_type") or ""),
        expires_in=int(data.get("expires_in") or 0),
        scope=str(data.get("scope") or ""),
    )


def pkce_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def oauth_client_id(config: OAuthDeviceConfig) -> str:
    return config.client_id or (os.environ.get(config.client_id_env, "").strip() if config.client_id_env else "")


def looks_like_google_oauth_client_id(client_id: str) -> bool:
    value = client_id.strip()
    return bool(re.fullmatch(r"[0-9A-Za-z._-]+\.apps\.googleusercontent\.com", value))


def oauth_client_secret(config: OAuthDeviceConfig) -> str:
    return config.client_secret or (os.environ.get(config.client_secret_env, "").strip() if config.client_secret_env else "")


def save_oauth_config_token(result: OAuthDeviceTokenResult, config: OAuthDeviceConfig) -> Path:
    path = token_store_path(config.token_store)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "provider": config.provider,
        "profile_id": config.profile_id,
        "created_at": int(time.time()),
        "token_type": result.token_type,
        "access_token": result.access_token,
        "refresh_token": result.refresh_token,
        "expires_in": result.expires_in,
        "scope": result.scope,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def save_oauth_device_token(result: OAuthDeviceTokenResult, login_request: OAuthDeviceLoginRequest) -> Path:
    path = token_store_path(login_request.token_store)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "provider": login_request.provider,
        "profile_id": login_request.profile_id,
        "created_at": int(time.time()),
        "token_type": result.token_type,
        "access_token": result.access_token,
        "refresh_token": result.refresh_token,
        "expires_in": result.expires_in,
        "scope": result.scope,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def load_oauth_token(token_store: str | Path) -> dict[str, object]:
    path = token_store_path(token_store)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def oauth_token_status(token_store: str | Path, label: str = "OAuth") -> tuple[str, str]:
    token = load_oauth_token(token_store)
    if not token:
        return "missing", f"No saved {label} token."
    access_token = str(token.get("access_token") or "")
    if not access_token:
        return "invalid", f"Saved {label} token has no access_token."
    created_at = int(token.get("created_at") or 0)
    expires_in = int(token.get("expires_in") or 0)
    if expires_in and created_at and time.time() >= created_at + expires_in - 60:
        return "expired", f"Saved {label} access token is expired; scan QR again."
    return "ready", f"Saved {label} token is ready for this session."


def activate_saved_oauth_token(token_store: str | Path, token_env: str, label: str = "OAuth") -> tuple[str, str]:
    status, message = oauth_token_status(token_store, label=label)
    if status != "ready":
        return status, message
    token = load_oauth_token(token_store)
    if token_env:
        os.environ[token_env] = str(token.get("access_token") or "")
    return status, message


def token_store_path(token_store: str | Path) -> Path:
    path = Path(token_store).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def default_oauth_device_config(profile_id: str, kind: str) -> dict[str, object]:
    if kind == "gemini":
        return {
            "enabled": True,
            "provider": "google",
            "client_id_env": "GOOGLE_OAUTH_CLIENT_ID",
            "client_secret_env": "GOOGLE_OAUTH_CLIENT_SECRET",
            "authorization_url": GOOGLE_AUTHORIZATION_URL,
            "device_code_url": "https://oauth2.googleapis.com/device/code",
            "token_url": "https://oauth2.googleapis.com/token",
            "verification_url": "https://www.google.com/device",
            "scopes": [
                "https://www.googleapis.com/auth/cloud-platform",
                "https://www.googleapis.com/auth/generative-language.retriever",
            ],
            "token_env": "GOOGLE_OAUTH_ACCESS_TOKEN",
            "token_store": f"state/private/ai_oauth_tokens/{profile_id or 'gemini'}.json",
        }
    if kind in {"openai", "openai_compatible"}:
        suffix = _env_suffix(profile_id or kind)
        return {
            "enabled": True,
            "provider": kind,
            "client_id_env": f"{suffix}_OAUTH_CLIENT_ID",
            "client_secret_env": f"{suffix}_OAUTH_CLIENT_SECRET",
            "authorization_url": "",
            "device_code_url": "",
            "token_url": "",
            "verification_url": "",
            "scopes": [],
            "token_env": f"AI_OAUTH_ACCESS_TOKEN_{suffix}",
            "token_store": f"state/private/ai_oauth_tokens/{profile_id or kind}.json",
        }
    return {}


class OAuthDevicePending(RuntimeError):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


def _empty_request(config: OAuthDeviceConfig, status: str, message: str, client_id_available: bool = False) -> OAuthDeviceLoginRequest:
    return OAuthDeviceLoginRequest(
        provider=config.provider,
        profile_id=config.profile_id,
        label=config.label,
        client_id=config.client_id,
        client_secret=config.client_secret,
        client_id_env=config.client_id_env,
        client_secret_env=config.client_secret_env,
        client_id_available=client_id_available,
        verification_url=config.verification_url,
        verification_url_complete="",
        user_code="",
        device_code="",
        expires_in=0,
        interval=5,
        token_url=config.token_url,
        token_store=config.token_store,
        token_env=config.token_env,
        scopes=config.scopes,
        status=status,
        message=message,
    )


def default_authorization_url(provider: str) -> str:
    return GOOGLE_AUTHORIZATION_URL if provider == "google" else ""


def _post_form(url: str, payload: dict[str, str], timeout: float) -> dict[str, object]:
    body = parse.urlencode(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        try:
            data = json.loads(exc.read().decode("utf-8"))
        except Exception:
            data = {}
        error_code = str(data.get("error") or "")
        message = str(data.get("error_description") or data.get("error_message") or exc)
        if error_code in {"authorization_pending", "slow_down", "access_denied", "expired_token"}:
            raise OAuthDevicePending(error_code, message)
        raise RuntimeError(f"{error_code or exc.code}: {message}") from exc


def _scopes_from_raw(raw: object) -> tuple[str, ...]:
    if isinstance(raw, str):
        return tuple(scope.strip() for scope in raw.split() if scope.strip())
    if isinstance(raw, list):
        return tuple(str(scope).strip() for scope in raw if str(scope).strip())
    return ()


def _env_suffix(value: str) -> str:
    suffix = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").upper()
    return suffix or "PROFILE"
