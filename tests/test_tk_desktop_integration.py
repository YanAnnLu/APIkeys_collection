import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from frontends.tk.desktop_integration import reveal_path_in_file_manager


class DesktopIntegrationTests(unittest.TestCase):
    def test_reveal_path_uses_windows_explorer_selection(self) -> None:
        # Windows 要定位到檔案本身，不只是打開父資料夾；這會影響使用者找設定檔的速度。
        target = Path("C:/project/config/local.json")

        with (
            patch("frontends.tk.desktop_integration.sys.platform", "win32"),
            patch("frontends.tk.desktop_integration.os.name", "nt"),
            patch("frontends.tk.desktop_integration.subprocess.Popen") as popen,
        ):
            reveal_path_in_file_manager(target)

        popen.assert_called_once_with(["explorer", f"/select,{target}"])

    def test_reveal_path_uses_macos_open_reveal(self) -> None:
        # macOS 的 `open -R` 是 Finder reveal；比直接 open 父資料夾更符合 UI 的「顯示檔案」語意。
        target = Path("/tmp/project/config/local.json")

        with (
            patch("frontends.tk.desktop_integration.sys.platform", "darwin"),
            patch("frontends.tk.desktop_integration.subprocess.Popen") as popen,
        ):
            reveal_path_in_file_manager(target)

        popen.assert_called_once_with(["open", "-R", str(target)])

    def test_reveal_path_falls_back_to_parent_uri_on_linux(self) -> None:
        # Linux 桌面環境差異太大；fallback 只開父資料夾 URI，不猜特定 file manager。
        target = SimpleNamespace(parent=SimpleNamespace(as_uri=lambda: "file:///tmp/project/config"))

        with (
            patch("frontends.tk.desktop_integration.sys.platform", "linux"),
            patch("frontends.tk.desktop_integration.os.name", "posix"),
            patch("frontends.tk.desktop_integration.webbrowser.open") as open_url,
        ):
            reveal_path_in_file_manager(target)

        open_url.assert_called_once_with(target.parent.as_uri())


if __name__ == "__main__":
    unittest.main()
