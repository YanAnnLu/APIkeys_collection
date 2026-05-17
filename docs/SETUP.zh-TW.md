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

目前接力用的 macOS 環境已經有 Conda env：

```bash
cd "/Users/yen-an/Library/CloudStorage/CloudMounter-Google#1/APIkeys_collection"
conda run -n metal_trade_312 python -m pip install -r requirements-dev.txt
conda run -n metal_trade_312 python -m unittest discover -s tests
conda run -n metal_trade_312 python APIkeys_collection_ui.py
```

不要把套件裝進 `base` 或 system Python。若之後需要新增套件，優先安裝到 `metal_trade_312`，並同步更新 `requirements.txt` 或 `requirements-dev.txt`。

一般 macOS/Linux 也可用專案 venv：

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

如果使用同步碟或 CloudMounter，請確認目前工作目錄真的在 `APIkeys_collection/` 專案資料夾內，不要在上一層雲端根目錄執行會寫檔的命令。

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
python3 APIkeys_collection.py --verify-downloads-json
```

## 注意事項

- 不要提交 `state/`、`downloads/`、`.env`、`*.private.json`。
- 不要提交 `config/launcher_integrations.local.json`；它保存本機 UI 語言、欄寬、工具路徑與 AI profile 覆寫。
- AI QR/device 登入 token 會放在 `state/private/ai_oauth_tokens/`，這是本機私有狀態，不可提交。
- 提供商 favicon 快取會放在 `state/favicons/`，可刪除重抓，不可提交。
- SQLite 在同步碟上可能被鎖住；大量寫入時最好改成本機 state path。
- Windows 有時會鎖 `.pyc`，建議設定 `PYTHONDONTWRITEBYTECODE=1`。
- Renderer dependencies 放在 `requirements-renderer.txt`，不要混進 launcher core。
- 如果 UI 中文顯示異常，先不要批次轉碼，避免破壞既有檔案；應該另開一次 encoding cleanup。
- macOS 若看到 Windows `K:\...` 路徑，通常代表本機整合設定尚未分平台配置；應改用 `*_by_platform` 或在 Mac 的 local config 指向 macOS 實際路徑。

## 常用 UI 入口

| 入口 | 用途 |
| --- | --- |
| `設定 > 介面語言` | 切換繁中/英文。 |
| `設定 > AI 輔助模型` | 選擇真正要調用的 AI profile；也可登入選取模型或貼本次 API key。 |
| `整合 > Google / Gemini 與 AI 設定` | Google/Gemini token 狀態與 QR 登入入口；不負責切換模型。 |
| `整合 > Google QR 登入` | 直接開啟 Gemini/Google QR 登入；若尚未設定 Client ID，會提供 `設定 QR 登入`。 |
| `工具 > 開發者 CLI` | 在專案根目錄跑單次 CLI 命令。 |
| 左側 `依類型 / 依提供商` | 切換分類方式；依提供商模式會嘗試顯示網站 favicon。 |
