# APIkeys_collection 跨平台開發設定

更新日期：2026-05-17

## 專案定位

這個專案是科學資料集 launcher / downloader，不是單純 API key 清單。開發環境要能支援：

- Python launcher core
- Tk UI
- SQLite state
- Docker smoke test
- Git/GitHub handoff
- 未來 renderer optional dependencies

## Windows PowerShell

```powershell
cd K:\APIkeys_collection
$env:PYTHONDONTWRITEBYTECODE='1'
py -m pip install -r requirements-dev.txt
py -m unittest discover -s tests
py APIkeys_collection.py --init-db --seed --manifest-health --summary
docker compose -f docker-compose.yml run --rm --build launcher
```

啟動 UI：

```powershell
py APIkeys_collection_ui.py
```

若 PowerShell script execution policy 阻擋 `.ps1`：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_ui.ps1
```

## macOS / Linux

```bash
cd APIkeys_collection
export PYTHONDONTWRITEBYTECODE=1
python3 -m pip install -r requirements-dev.txt
python3 -m unittest discover -s tests
python3 APIkeys_collection.py --init-db --seed --manifest-health --summary
docker compose -f docker-compose.yml run --rm --build launcher
```

啟動 UI：

```bash
python3 APIkeys_collection_ui.py
```

## 接力前檢查

```bash
git status --short --branch
python3 APIkeys_collection.py --handoff-report state/handoff.md --manifest-health --show-logs 20
git add .
git commit -m "Describe the launcher change"
git push
```

Windows 可把 `python3` 換成 `py`。

## 接力後檢查

```bash
git pull
git status --short --branch
python3 -m unittest discover -s tests
python3 APIkeys_collection.py --verify-downloads --manifest-health --show-logs 20
```

## 注意事項

- 不要提交 `state/`、`downloads/`、`.env`、`*.private.json`。
- SQLite 在同步碟上可能被鎖住；大量寫入時最好改成本機 state path。
- Windows 有時會鎖 `.pyc`，建議設定 `PYTHONDONTWRITEBYTECODE=1`。
- Renderer dependencies 放在 `requirements-renderer.txt`，不要混進 launcher core。
- 如果 UI 中文顯示異常，先不要批次轉碼，避免破壞既有檔案；應該另開一次 encoding cleanup。
