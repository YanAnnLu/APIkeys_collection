"""桌面平台整合 helper。"""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path


def reveal_path_in_file_manager(path: Path) -> None:
    """用目前平台的檔案管理器定位檔案或資料夾。"""

    # 這個 helper 只負責「帶使用者看到檔案」；失敗時不建立、不修改、不刪除任何檔案。
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
        return
    if os.name == "nt":
        subprocess.Popen(["explorer", f"/select,{path}"])
        return
    webbrowser.open(path.parent.as_uri())
