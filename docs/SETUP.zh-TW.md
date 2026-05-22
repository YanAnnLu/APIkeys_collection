# APIkeys_collection 跨平台開發設定

更新日期：2026-05-20

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

不要把套件裝進 `base` 或 system Python。若之後需要新增套件，優先安裝到 `metal_trade_312`，並同步更新 `requirements.txt`、`requirements-dev.txt`，或明確的 optional requirements 檔。

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

## 選用：真實資料庫 smoke test

一般測試不需要安裝 MySQL/PostgreSQL driver，也不會連線到真實資料庫。若要在一次性測試資料庫上跑真實 driver smoke，才安裝：

```bash
python3 -m pip install -r requirements-dev.txt -r requirements-db-smoke.txt
```

本機建議只指向一次性 database 或 disposable container。不要把 `APIKEYS_REAL_DB_SMOKE_ALLOW_WRITE=1` 指到共用、正式、或不可重建的資料庫。

如果要用 Docker 建一次性資料庫，可以先開兩個容器：

```bash
docker run --rm --name apikeys-mysql-smoke \
  -e MYSQL_ROOT_PASSWORD=rootpass \
  -e MYSQL_DATABASE=apikeys_ci \
  -e MYSQL_USER=apikeys_ci \
  -e MYSQL_PASSWORD=apikeys_ci \
  -p 3307:3306 -d mysql:8.4

docker run --rm --name apikeys-postgres-smoke \
  -e POSTGRES_DB=apikeys_ci \
  -e POSTGRES_USER=apikeys_ci \
  -e POSTGRES_PASSWORD=apikeys_ci \
  -p 5433:5432 -d postgres:17
```

等容器 ready 後，在 bash/zsh 設定：

```bash
export APIKEYS_RUN_REAL_DB_SMOKE=1
export APIKEYS_REAL_DB_SMOKE_ALLOW_WRITE=1
export APIKEYS_MYSQL_HOST=127.0.0.1
export APIKEYS_MYSQL_PORT=3307
export APIKEYS_MYSQL_DATABASE=apikeys_ci
export APIKEYS_MYSQL_USER=apikeys_ci
export APIKEYS_MYSQL_PASSWORD=apikeys_ci
export APIKEYS_POSTGRES_HOST=127.0.0.1
export APIKEYS_POSTGRES_PORT=5433
export APIKEYS_POSTGRES_DATABASE=apikeys_ci
export APIKEYS_POSTGRES_USER=apikeys_ci
export APIKEYS_POSTGRES_PASSWORD=apikeys_ci
export APIKEYS_POSTGRES_SCHEMA=public

python3 -m unittest tests.test_data_store_real_drivers -v
```

Windows PowerShell 對應設定：

```powershell
$env:APIKEYS_RUN_REAL_DB_SMOKE='1'
$env:APIKEYS_REAL_DB_SMOKE_ALLOW_WRITE='1'
$env:APIKEYS_MYSQL_HOST='127.0.0.1'
$env:APIKEYS_MYSQL_PORT='3307'
$env:APIKEYS_MYSQL_DATABASE='apikeys_ci'
$env:APIKEYS_MYSQL_USER='apikeys_ci'
$env:APIKEYS_MYSQL_PASSWORD='apikeys_ci'
$env:APIKEYS_POSTGRES_HOST='127.0.0.1'
$env:APIKEYS_POSTGRES_PORT='5433'
$env:APIKEYS_POSTGRES_DATABASE='apikeys_ci'
$env:APIKEYS_POSTGRES_USER='apikeys_ci'
$env:APIKEYS_POSTGRES_PASSWORD='apikeys_ci'
$env:APIKEYS_POSTGRES_SCHEMA='public'

py -m unittest tests.test_data_store_real_drivers -v
```

如果只想做 read-only driver/introspection smoke，不要設定 `APIKEYS_REAL_DB_SMOKE_ALLOW_WRITE`。只設定 `APIKEYS_RUN_REAL_DB_SMOKE=1` 與對應 `APIKEYS_MYSQL_*`、`APIKEYS_POSTGRES_*` 即可。

測完後停止 disposable containers：

```bash
docker stop apikeys-mysql-smoke apikeys-postgres-smoke
```

預設只做 read-only connection/schema introspection。若要連同 registry-backed database/table self-check 一起測，必須額外設定 `APIKEYS_REAL_DB_SMOKE_ALLOW_WRITE=1`，而且只應指向一次性測試資料庫；這會建立、ALTER、清掉 `apikeys_ci_registry_smoke_*` 測試表，用來驗 present、missing、schema drift 三種狀態。

GitHub Actions 的 `real-db-smoke` job 會自動啟動 MySQL/PostgreSQL service containers，並在 disposable 資料庫裡設定 `APIKEYS_REAL_DB_SMOKE_ALLOW_WRITE=1` 跑完整 real DB smoke。

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
- AI OAuth / QR-device 登入 token 會放在 `state/private/ai_oauth_tokens/`，這是本機私有狀態，不可提交。
- 提供商 favicon 快取會放在 `state/favicons/`，可刪除重抓，不可提交。
- SQLite 在同步碟上可能被鎖住；大量寫入時最好改成本機 state path。
- Windows 有時會鎖 `.pyc`，建議設定 `PYTHONDONTWRITEBYTECODE=1`。
- macOS 若專案放在 CloudMounter / 雲端同步碟，Python 讀寫 `__pycache__` 可能卡住；跑測試可加 `PYTHONPYCACHEPREFIX=/tmp/apikeys_collection_pycache`，把 bytecode 快取放到本機暫存。
- `requirements-dev.txt` 會安裝 `numpy`，讓 Unreal preview export 測試不被跳過；`requirements-db-smoke.txt` 只給真實 MySQL/PostgreSQL smoke test；完整 renderer dependencies 仍放在 `requirements-renderer.txt`，不要混進 launcher core。
- 如果 UI 中文顯示異常，先不要批次轉碼，避免破壞既有檔案；應該另開一次 encoding cleanup。
- macOS 若看到 Windows `K:\...` 路徑，通常代表本機整合設定尚未分平台配置；應改用 `*_by_platform` 或在 Mac 的 local config 指向 macOS 實際路徑。

## 常用 UI 入口

| 入口 | 用途 |
| --- | --- |
| `設定 > 介面語言` | 切換繁中/英文。 |
| `整合 > AI / Gemini 串接中心` | Gemini 描述生成入口；現階段主路線是保存 Gemini API key 到本機 private state。 |
| `整合 > 保存 Gemini API key` | 直接保存 Gemini API key 並啟用 `gemini_flash` profile；下次啟動自動載入。 |
| `整合 > AI 輔助模型選擇` | 選擇真正要調用的 AI profile。 |
| `整合 > Google OAuth（中期 / 開發者）` | 保留中期正式 Google 帳號登入、QR/device-code，以及開發者 OAuth 設定；一般使用者不需要貼 OAuth Client ID。 |
| `整合 > 資料儲存連線` | 檢查 MySQL/PostgreSQL/SQLite/NoSQL/object store 等連線設定，也可把選取 profile 寫成本機 env 範本；不保存密碼。 |
| `工具 > 開發者 CLI` | 在專案根目錄跑單次 CLI 命令。 |
| 左側 `依類型 / 依提供商` | 切換分類方式；依提供商模式會嘗試顯示網站 favicon。 |

## OpenSpec / Spectra / Qt Designer

這三個工具是給「開發流程」用的，不是一般使用者每天操作資料庫的入口。

OpenSpec CLI 已可透過 `npx` 使用，不需要全域安裝：

```bash
npx -y @fission-ai/openspec@latest list --specs
npx -y @fission-ai/openspec@latest validate --all --no-interactive
```

本 repo 已初始化 OpenSpec 工作區：

```text
openspec/specs/
openspec/changes/
openspec/changes/archive/
```

Spectra GUI 已安裝在使用者自己的 Applications 目錄：

```bash
open "$HOME/Applications/Spectra.app"
```

打開後選本 repo 根目錄。Spectra 是 OpenSpec 的可視化輔助工具；真正要接力與提交的狀態仍在 Git 裡的 `openspec/` 與文件。

Qt Designer 已在 `metal_trade_312` 裡可用：

```bash
conda run -n metal_trade_312 pyside6-designer
```

也可直接打開：

```bash
open "/opt/homebrew/anaconda3/envs/metal_trade_312/lib/qt6/bin/Designer.app"
```

目前 PySide6/Qt 是中期 UI 路線，不要在 backend MVP 尚未閉環前重寫整個 Tk UI。若未來新增 `frontends/qt/`，應重用 `api_launcher/` 的 crawler、download、import、event log 與 integration contracts。
