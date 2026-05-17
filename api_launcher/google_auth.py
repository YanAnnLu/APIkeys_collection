from __future__ import annotations

import os
import secrets
from dataclasses import dataclass


DEFAULT_GOOGLE_DEVICE_VERIFICATION_URL = "https://www.google.com/device"


@dataclass(frozen=True)
class GoogleDeviceLoginRequest:
    provider: str
    client_id_env: str
    client_id_available: bool
    verification_url: str
    user_code: str
    status: str
    message: str


def build_google_device_login_request(
    client_id_env: str = "GOOGLE_OAUTH_CLIENT_ID",
    verification_url: str = DEFAULT_GOOGLE_DEVICE_VERIFICATION_URL,
) -> GoogleDeviceLoginRequest:
    client_id = os.environ.get(client_id_env, "").strip()
    if not client_id:
        return GoogleDeviceLoginRequest(
            provider="google",
            client_id_env=client_id_env,
            client_id_available=False,
            verification_url=verification_url,
            user_code="",
            status="missing_client_id",
            message=(
                f"Set {client_id_env} to enable Google OAuth device login. "
                "The launcher does not store Google OAuth tokens yet."
            ),
        )
    return GoogleDeviceLoginRequest(
        provider="google",
        client_id_env=client_id_env,
        client_id_available=True,
        verification_url=verification_url,
        user_code=_demo_user_code(),
        status="skeleton_only",
        message=(
            "OAuth device-code exchange is not implemented yet. "
            "This request reserves the QR/device-login UI contract."
        ),
    )


def _demo_user_code() -> str:
    token = secrets.token_hex(4).upper()
    return f"{token[:4]}-{token[4:]}"
