from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from api_launcher.google_auth import build_google_device_login_request


class GoogleAuthTests(unittest.TestCase):
    def test_device_login_request_reports_missing_client_id(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            request = build_google_device_login_request()

        self.assertEqual("missing_client_id", request.status)
        self.assertFalse(request.client_id_available)
        self.assertIn("GOOGLE_OAUTH_CLIENT_ID", request.message)

    def test_device_login_request_is_skeleton_when_client_id_exists(self) -> None:
        with patch.dict(os.environ, {"GOOGLE_OAUTH_CLIENT_ID": "client-id"}):
            request = build_google_device_login_request()

        self.assertEqual("skeleton_only", request.status)
        self.assertTrue(request.client_id_available)
        self.assertRegex(request.user_code, r"^[A-F0-9]{4}-[A-F0-9]{4}$")


if __name__ == "__main__":
    unittest.main()
