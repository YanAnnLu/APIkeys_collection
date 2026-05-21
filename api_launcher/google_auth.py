from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from urllib import error, parse, request

from api_launcher.integrations import load_integration_config
from api_launcher.paths import PROJECT_ROOT


DEFAULT_GOOGLE_DEVICE_CODE_URL = "https://oauth2.googleapis.com/device/code"
DEFAULT_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
DEFAULT_GOOGLE_DEVICE_VERIFICATION_URL = "https://www.google.com/device"
DEFAULT_GOOGLE_OAUTH_SCOPES = (
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/generative-language.retriever",
)
# token 必須留在被 Git 忽略的 private state；不要把預設路徑移進 tracked config。
DEFAULT_GOOGLE_TOKEN_STORE = "state/private/google_oauth_tokens.json"


@dataclass(frozen=True)
class GoogleDeviceLoginRequest:
    # UI/CLI 只讀這個資料物件來顯示 QR/device code 狀態，不直接依賴 Google 原始 payload。
    provider: str
    client_id_env: str
    client_id_available: bool
    verification_url: str
    verification_url_complete: str
    user_code: str
    device_code: str
    expires_in: int
    interval: int
    token_url: str
    scopes: tuple[str, ...]
    status: str
    message: str


@dataclass(frozen=True)
class GoogleDeviceTokenResult:
    # token poll 的結果分成狀態與 credential；呼叫端可依 status 決定是否重試或保存。
    status: str
    message: str
    access_token: str = ""
    refresh_token: str = ""
    token_type: str = ""
    expires_in: int = 0
    scope: str = ""
    slow_down: bool = False


def google_oauth_config() -> dict[str, object]:
    # Google OAuth 是可選整合；缺設定時回傳空 dict，避免一般啟動流程報錯。
    config = load_integration_config().get("google_oauth")
    return config if isinstance(config, dict) else {}


def google_oauth_scopes(config: dict[str, object] | None = None) -> tuple[str, ...]:
    oauth_config = config if config is not None else google_oauth_config()
    raw_scopes = oauth_config.get("scopes")
    # 同時接受 JSON 陣列與空白分隔字串，讓本機 config 容易手動編輯。
    if isinstance(raw_scopes, str):
        scopes = tuple(scope.strip() for scope in raw_scopes.split() if scope.strip())
    elif isinstance(raw_scopes, list):
        scopes = tuple(str(scope).strip() for scope in raw_scopes if str(scope).strip())
    else:
        scopes = DEFAULT_GOOGLE_OAUTH_SCOPES
    return scopes or DEFAULT_GOOGLE_OAUTH_SCOPES


def google_token_store_path(config: dict[str, object] | None = None) -> Path:
    oauth_config = config if config is not None else google_oauth_config()
    raw_path = str(oauth_config.get("token_store") or DEFAULT_GOOGLE_TOKEN_STORE).strip()
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        # 相對路徑固定落在 repo 底下，避免 Windows/macOS 從不同 cwd 啟動時把 token 寫到別處。
        path = PROJECT_ROOT / path
    return path


def build_google_device_login_request(
    client_id_env: str | None = None,
    verification_url: str = DEFAULT_GOOGLE_DEVICE_VERIFICATION_URL,
    device_code_url: str = DEFAULT_GOOGLE_DEVICE_CODE_URL,
    token_url: str = DEFAULT_GOOGLE_TOKEN_URL,
    timeout: float = 15.0,
) -> GoogleDeviceLoginRequest:
    oauth_config = google_oauth_config()
    env_name = client_id_env or str(oauth_config.get("client_id_env") or "GOOGLE_OAUTH_CLIENT_ID")
    client_id = os.environ.get(env_name, "").strip()
    scopes = google_oauth_scopes(oauth_config)
    if not client_id:
        # device login 仍屬開發者/中期路徑；缺 OAuth client 時不能阻擋一般 launcher 啟動。
        return GoogleDeviceLoginRequest(
            provider="google",
            client_id_env=env_name,
            client_id_available=False,
            verification_url=verification_url,
            verification_url_complete="",
            user_code="",
            device_code="",
            expires_in=0,
            interval=5,
            token_url=token_url,
            scopes=scopes,
            status="missing_client_id",
            message=f"Set {env_name} to enable Google OAuth device login.",
        )

    try:
        data = _post_form(
            device_code_url,
            {
                "client_id": client_id,
                "scope": " ".join(scopes),
            },
            timeout=timeout,
        )
    except Exception as exc:
        # device-code request 失敗時仍回傳可顯示狀態，讓 UI 顯示錯誤而不是整個視窗崩潰。
        return GoogleDeviceLoginRequest(
            provider="google",
            client_id_env=env_name,
            client_id_available=True,
            verification_url=verification_url,
            verification_url_complete="",
            user_code="",
            device_code="",
            expires_in=0,
            interval=5,
            token_url=token_url,
            scopes=scopes,
            status="request_failed",
            message=f"Google device-code request failed: {exc}",
        )

    return GoogleDeviceLoginRequest(
        provider="google",
        client_id_env=env_name,
        client_id_available=True,
        verification_url=str(data.get("verification_url") or data.get("verification_uri") or verification_url),
        verification_url_complete=str(data.get("verification_url_complete") or data.get("verification_uri_complete") or ""),
        user_code=str(data.get("user_code") or ""),
        device_code=str(data.get("device_code") or ""),
        expires_in=int(data.get("expires_in") or 0),
        interval=max(int(data.get("interval") or 5), 1),
        token_url=token_url,
        scopes=scopes,
        status="authorization_pending",
        message="Scan the QR code or open the device page, then finish Google authorization.",
    )


def poll_google_device_token(login_request: GoogleDeviceLoginRequest, timeout: float = 15.0) -> GoogleDeviceTokenResult:
    client_id = os.environ.get(login_request.client_id_env, "").strip()
    oauth_config = google_oauth_config()
    client_secret_env = str(oauth_config.get("client_secret_env") or "GOOGLE_OAUTH_CLIENT_SECRET")
    client_secret = os.environ.get(client_secret_env, "").strip()
    if not client_id:
        return GoogleDeviceTokenResult("missing_client_id", f"Missing client id environment variable: {login_request.client_id_env}")
    if not login_request.device_code:
        return GoogleDeviceTokenResult("missing_device_code", "Missing Google device_code; start QR login again.")
    try:
        # 這個函式只 poll 一次；重試節奏由呼叫端控制，才能遵守 Google 回傳的 interval。
        payload = {
            "client_id": client_id,
            "device_code": login_request.device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        }
        if client_secret:
            payload["client_secret"] = client_secret
        data = _post_form(
            login_request.token_url,
            payload,
            timeout=timeout,
        )
    except GoogleOAuthPending as exc:
        return GoogleDeviceTokenResult(exc.error_code, exc.message, slow_down=exc.error_code == "slow_down")
    except Exception as exc:
        return GoogleDeviceTokenResult("request_failed", f"Google token request failed: {exc}")

    access_token = str(data.get("access_token") or "")
    if not access_token:
        return GoogleDeviceTokenResult("empty_token", "Google returned no access_token.")
    return GoogleDeviceTokenResult(
        status="success",
        message="Google OAuth token received.",
        access_token=access_token,
        refresh_token=str(data.get("refresh_token") or ""),
        token_type=str(data.get("token_type") or ""),
        expires_in=int(data.get("expires_in") or 0),
        scope=str(data.get("scope") or ""),
    )


def save_google_oauth_token(result: GoogleDeviceTokenResult, config: dict[str, object] | None = None) -> Path:
    # 這是開發者/中期 OAuth token 儲存路徑；一般 AI summary MVP 不依賴它。
    path = google_token_store_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "provider": "google",
        "created_at": int(time.time()),
        "token_type": result.token_type,
        "access_token": result.access_token,
        "refresh_token": result.refresh_token,
        "expires_in": result.expires_in,
        "scope": result.scope,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        # POSIX 權限是 best effort；Windows 可能忽略 chmod，所以真正邊界仍是 ignored private 目錄。
        path.chmod(0o600)
    except OSError:
        pass
    return path


def load_google_oauth_token(config: dict[str, object] | None = None) -> dict[str, object]:
    # 讀取 token 時容忍缺檔與壞 JSON，避免 private state 損壞時阻斷 launcher。
    path = google_token_store_path(config)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def google_oauth_token_status(config: dict[str, object] | None = None) -> tuple[str, str]:
    # 狀態檢查只看本機 access token 是否可用；目前沒有自動 refresh token 流程。
    token = load_google_oauth_token(config)
    if not token:
        return "missing", "No saved Google OAuth token."
    access_token = str(token.get("access_token") or "")
    if not access_token:
        return "invalid", "Saved Google OAuth token has no access_token."
    created_at = int(token.get("created_at") or 0)
    expires_in = int(token.get("expires_in") or 0)
    if expires_in and created_at and time.time() >= created_at + expires_in - 60:
        return "expired", "Saved Google OAuth access token is expired; scan QR again."
    return "ready", "Saved Google OAuth token is ready for this session."


def activate_saved_google_oauth_token(config: dict[str, object] | None = None) -> tuple[str, str]:
    status, message = google_oauth_token_status(config)
    if status != "ready":
        return status, message
    token = load_google_oauth_token(config)
    # 啟用只作用於目前 process；不修改 shell profile，也不碰全域 Google credential。
    os.environ["GOOGLE_OAUTH_ACCESS_TOKEN"] = str(token.get("access_token") or "")
    return status, message


class GoogleOAuthPending(RuntimeError):
    # 用例外承載 OAuth pending 狀態，讓 _post_form 仍能對真正 HTTP 錯誤使用 RuntimeError。
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


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
        # 這些是 device flow 的正常狀態，不是傳輸失敗；用結構化狀態交回呼叫端。
        if error_code in {"authorization_pending", "slow_down", "access_denied", "expired_token"}:
            raise GoogleOAuthPending(error_code, message)
        raise RuntimeError(f"{error_code or exc.code}: {message}") from exc
