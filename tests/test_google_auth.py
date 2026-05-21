# 這份測試鎖定 Google token 本機狀態處理，避免 startup 觸發不必要登入流程。
from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from api_launcher.google_auth import (
    build_google_device_login_request,
    google_oauth_token_status,
    poll_google_device_token,
    save_google_oauth_token,
    GoogleDeviceTokenResult,
)


class GoogleAuthTests(unittest.TestCase):
    def test_device_login_request_reports_missing_client_id(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            request = build_google_device_login_request()

        self.assertEqual("missing_client_id", request.status)
        self.assertFalse(request.client_id_available)
        self.assertIn("GOOGLE_OAUTH_CLIENT_ID", request.message)

    def test_device_login_request_calls_google_when_client_id_exists(self) -> None:
        response = {
            "device_code": "device-code",
            "user_code": "ABCD-EFGH",
            "verification_url": "https://www.google.com/device",
            "expires_in": 1800,
            "interval": 5,
        }
        with patch.dict(os.environ, {"GOOGLE_OAUTH_CLIENT_ID": "client-id"}), patch(
            "api_launcher.google_auth._post_form", return_value=response
        ) as post_form:
            request = build_google_device_login_request()

        self.assertEqual("authorization_pending", request.status)
        self.assertTrue(request.client_id_available)
        self.assertEqual("ABCD-EFGH", request.user_code)
        self.assertEqual("device-code", request.device_code)
        self.assertEqual("client-id", post_form.call_args.args[1]["client_id"])

    def test_poll_device_token_returns_success(self) -> None:
        login = build_google_device_login_request()
        login = login.__class__(
            provider="google",
            client_id_env="GOOGLE_OAUTH_CLIENT_ID",
            client_id_available=True,
            verification_url="https://www.google.com/device",
            verification_url_complete="",
            user_code="ABCD-EFGH",
            device_code="device-code",
            expires_in=1800,
            interval=5,
            token_url="https://oauth2.googleapis.com/token",
            scopes=("email",),
            status="authorization_pending",
            message="pending",
        )
        response = {"access_token": "access", "refresh_token": "refresh", "expires_in": 3600, "token_type": "Bearer"}
        with patch.dict(os.environ, {"GOOGLE_OAUTH_CLIENT_ID": "client-id"}), patch(
            "api_launcher.google_auth._post_form", return_value=response
        ):
            result = poll_google_device_token(login)

        self.assertEqual("success", result.status)
        self.assertEqual("access", result.access_token)

    def test_saved_token_status_reports_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {"token_store": str(os.path.join(tmp, "token.json"))}
            save_google_oauth_token(
                GoogleDeviceTokenResult(
                    status="success",
                    message="ok",
                    access_token="access",
                    refresh_token="refresh",
                    token_type="Bearer",
                    expires_in=3600,
                ),
                config=config,
            )

            status, _message = google_oauth_token_status(config=config)

        self.assertEqual("ready", status)


if __name__ == "__main__":
    unittest.main()
