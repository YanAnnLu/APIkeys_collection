# Agent 接力卡

最後更新：2026-05-17

這份文件是跨 Windows、macOS、不同 Agent 接力時的固定入口。每次切換機器或切換 Agent 前，請優先更新這份文件；下一位 Agent 應該先讀這份，再讀 `PROJECT_GTD.md`。

## 接手順序

1. 同步 Git：

   ```bash
   git pull origin main
   git status --short --branch
   ```

2. 讀文件：

   ```text
   docs/AGENT_HANDOFF.zh-TW.md
   docs/PROJECT_GTD.md
   docs/ARCHITECTURE.md
   docs/TECHNICAL_OVERVIEW.zh-TW.md
   ```

3. 跑基本驗證：

   ```bash
   python3 -m unittest discover -s tests
   python3 -m py_compile APIkeys_collection.py APIkeys_collection_ui.py frontends/tk/launcher_ui.py api_launcher/core.py
   python3 APIkeys_collection.py --summary
   ```

   Windows PowerShell 可改用：

   ```powershell
   py -m unittest discover -s tests
   py -m py_compile APIkeys_collection.py APIkeys_collection_ui.py frontends\tk\launcher_ui.py api_launcher\core.py
   py APIkeys_collection.py --summary
   ```

4. 如果 Docker 可用，跑 smoke test：

   ```bash
   docker compose -f docker-compose.yml run --rm --build launcher
   ```

5. push 後追 GitHub Actions：

   ```bash
   gh run list --repo YanAnnLu/APIkeys_collection --limit 5
   gh run watch RUN_ID --repo YanAnnLu/APIkeys_collection --exit-status
   ```

   注意：`git push` 成功只代表 commit 到遠端，不代表 Windows/Ubuntu CI 成功。手機 GitHub 通知若顯示 `CI failed`，要看 workflow log，不是重試 push。

## 目前專案定位

APIkeys Collection 是一個類 Steam 的科學資料集/資料庫 launcher。它不是單純 API key 管理器，而是要管理：

- 資料源與供應商 discovery seeds
- 下載計畫，也就是資料集購物車
- 非阻塞下載、續傳、暫停、重試、polite rate limit
- 本機資料庫與 data store 連線 profile
- install registry、版本、更新、解除納管/解除安裝安全流程
- API/CSV/JSON/manual SQL 匯入與清洗管線
- Taichi 與 Unreal 虛擬孿生 renderer bridge
- 未來 agent skill / natural-language database management

## 目前 Git 狀態

| 欄位 | 值 |
| --- | --- |
| Branch | `main` |
| 最新已推送 commit | 以 `git log -1 --oneline` 為準；每次接力前更新本文件 |
| 上次驗證 | 2026-05-17：本機 `186 tests OK`、Tk UI smoke OK、GitHub Actions CI Windows/Ubuntu OK |
| UI 入口 | `python3 APIkeys_collection_ui.py` 或 `py APIkeys_collection_ui.py` |
| Tk UI 實作 | `frontends/tk/launcher_ui.py` |
| 使用者指南 | `docs/USER_GUIDE.zh-TW.md` |

## 最近完成

- Tk UI 實作檔已從 `frontends/tk/APIkeys_collection_ui.py` 改名為 `frontends/tk/launcher_ui.py`。
- 根目錄 `APIkeys_collection_ui.py` 保留相容入口，不要刪。
- SQL-only 連線模組已合併進泛用 data store contract。
- `api_launcher/data_store_connections.py` 現在統一管理 MySQL/PostgreSQL/SQLite、MongoDB、S3-compatible object storage、vector DB。
- `config/launcher_integrations.example.json` 使用 `data_store_connection_profiles`，不要重新新增 `sql_connection_profiles`。
- `api_launcher/library_actions.py` 已提供 action map/order/menu-label helpers，Tk 右鍵選單已開始共用這套規則。
- `api_launcher/library_actions.py` 已提供 agent-readable JSON payload；CLI 可用 `--show-library-actions PROVIDER_ID --library-actions-json` 讓未來 skill 重用同一套 action 規則。
- Tk UI 已新增 `Tools > Recent event logs`，可以直接查看 `state/logs/launcher_events.jsonl` 的近期事件。
- Tk UI 的 `工具 > 修復 / 驗證資產` 現在會開啟 repair panel，分成「下載檔案」與「資料庫」兩個分頁；下載檔案分頁列出每個 download manifest 的健康狀態與路徑。
- Repair panel 現在會顯示安全修復建議；對有 HTTP(S) `source_url` 和 `provider_id` 的 missing/size/checksum manifest，可用「重新排下載」透過 staging 重新排下載。
- Tk UI 新增 `設定 > 介面語言`，語言存在 `launcher_integrations.local.json` 的 `ui_language`。預設是 `zh-TW`；新開啟 dialog 會套用，主畫面完整套用需重新啟動。後續碰 UI 時應優先補齊繁中顯示與 `tr(...)` 英文 fallback。
- Tk UI 新增 `設定 > AI 輔助模型`，使用者必須明確選擇要調用哪個 AI profile；目前支援 local Ollama、Gemini、OpenAI-compatible profile。AI 登入/API key 可各自存在 profile/session，但生成描述時以此設定為準。每個 profile 可帶 `oauth_device` 設定；支援 OAuth device-code 的服務會用 QR 登入並把 token 存在 `state/private/ai_oauth_tokens/`。
- Tk UI 資料源詳情改為右側比例抽屜：抽屜寬度依主內容區比例計算，保留表格基本空間，開關時有短距離寬度動畫，內容可捲動，描述/狀態/連結文字會依抽屜寬度換行，避免被擠成窄直欄；抽屜內另有 AI 生成描述 textbox。
- Tk UI 左側欄可在「依類型」與「依提供商」間切換；提供商模式會依目前 catalog owner 動態產生篩選按鈕，並在背景抓取/快取官網 favicon 到 `state/favicons/` 當小圖示。
- Tk UI 新增 `工具 > 開發者 CLI`，提供專案工作目錄下的單次命令輸入/輸出面板，供開發者快速呼叫 CLI。
- Tk UI 主表格支援類 Excel 欄寬調整：拖拉欄位分隔線後，欄寬會寫入 `launcher_integrations.local.json` 的 `ui_table_column_widths`；「更多 > 重設表格欄寬」可清除回預設比例。
- Tk UI 的下載資格與詳情狀態文字已補上繁中顯示，UI 語言切到 `en-US` 時仍保留英文 fallback。
- Data store connection testing 已有骨架：`--test-data-store PROFILE_ID|all` 可測 configured profiles；SQLite 會用 read-only introspection，MySQL/PostgreSQL 先檢查 env vars 與 optional Python driver。
- SQL/database self-check 已擴充到 SQLite database/table assets：`--self-check-databases` 會用 registry asset verifier 檢查 managed database/table assets；SQLite database asset 依 `source_uri`/path 做 read-only 檢查與 database-level fingerprint，SQLite table asset 依 `source_uri` + `asset_name` 檢查單表存在與 table-level fingerprint drift，並回寫 asset/provider 狀態與 missing/error 明細。
- MySQL/PostgreSQL data-store layer 已有 `information_schema` introspection helpers：連線 smoke 可回報 table_count；database/table asset 若登記 `schema_fingerprint`，self-check 會要求 schema summary 並偵測 drift。跨引擎 table asset 會從 `install_location` 解析 database owner，PostgreSQL `asset_name` 可用 `schema.table` 指定 schema，並能標記 missing table。
- `--self-check-databases` 現在人類輸出會包含 `suggestion=...` 修復代號；`--self-check-databases-json` 會輸出純 JSON，包含每個 missing/error database/table asset 的錯誤、去敏感化位置、是否有 schema fingerprint、以及修復建議。這是給 UI、下一位 Agent、或未來自動修復流程讀的入口。
- Tk Repair panel 的「資料庫」分頁會重用同一套 database self-check verifier 與 `database_self_check_issues()`；目前只顯示診斷與下一步，不自動執行 `DROP`、重建 table、或刷新 fingerprint。
- 2026-05-17 已修復 Windows CI：Python `with sqlite3.connect(...)` 不會自動 close connection，Windows temp SQLite 會被檔案鎖住並造成 `WinError 32`；短生命週期 SQLite probe/test 請用 `contextlib.closing(sqlite3.connect(...))`。
- macOS 目前已安裝並登入 GitHub CLI (`gh`) 為 `YanAnnLu`，可直接查 CI run/log。

## 下一步優先事項

1. 擴充 SQL/database self-check：加入 per-asset SQL profile/schema 選擇、真實 driver smoke 覆蓋，並把現有 UI repair suggestion 升級成 adapter-owned guarded action。
2. 擴充 repair 建議到 adapter-specific datasets、agent-readable repair summaries 與更完整事件 log。
3. 擴充 `.codex/skills/apikeys-collection-launcher`，加入 adapter-specific repair/download/database self-check 操作流程。
4. 繼續減少 Tk UI 內的業務邏輯，讓 UI 主要負責呈現與觸發。

## 開發守則

- 每完成一個功能，要更新 `docs/PROJECT_GTD.md`。
- 每次跨機器或跨 Agent 接力，要更新這份 `docs/AGENT_HANDOFF.zh-TW.md`。
- 不要提交 `config/launcher_integrations.local.json`、`state/`、`downloads/`、真實 token、真實 API key。
- 不要把本機絕對路徑寫死在程式碼；路徑要走 `api_launcher/paths.py` 或 config。
- 預留端口不是死碼；但如果兩個模組表達同一件事，要優先合併抽象。
- macOS 要注意 Tk、UTF-8、LF 換行、路徑大小寫與 `python3`/venv。特別注意不要讓 Windows 路徑（例如 `K:\...`）在 Mac startup checks 被當成錯誤；跨平台路徑應先依系統挑 `*_by_platform`，不符合本系統的 generic path 要忽略或降成 warning，不可阻擋 UI 啟動。
- SQLite 短生命週期連線不要裸用 `with sqlite3.connect(...)`；那只處理 transaction，不會 close connection。用 `contextlib.closing(...)` 避免 Windows CI 檔案鎖。
- 每次 push 後，用 `gh run watch --exit-status` 追最新 CI；不要只以 push 成功判斷完成。
- 接力事故紀錄：2026-05-17 曾因把未提交的大型 `APIkeys_collection.py` 誤判為可丟棄內容而覆回 Git wrapper。下一位 Agent 遇到任何未提交、非預期、或看似「不符合文件」的大改動時，必須先備份或輸出 patch，再詢問/確認；不要直接 `git restore`、刪除或覆寫。

## 給下一位 Agent 的提示詞

```text
你正在接手 APIkeys_collection。請先讀 docs/AGENT_HANDOFF.zh-TW.md，再讀 docs/PROJECT_GTD.md。不要依賴上一段聊天紀錄。

先執行 git pull origin main、git status --short --branch、python3 -m unittest discover -s tests。本機 Codex/macOS 環境請優先用 conda env：conda run -n metal_trade_312 python -m unittest discover -s tests；不要把套件裝進 base/system Python。

push 後請用 gh run watch 追 CI。Windows 失敗時優先檢查 SQLite/file handle、路徑與 `.pyc` 鎖。SQLite 短生命週期連線要用 contextlib.closing。

目前優先任務是擴充 SQL/database self-check：加入 per-asset SQL profile/schema 選擇、真實 driver smoke 覆蓋，以及 database drift/missing table 的 repair 建議；接著擴充 repair 建議到 adapter-specific datasets、agent-readable repair summaries 與更完整事件 log。

注意：SQL-only connection layer 已被合併到 api_launcher/data_store_connections.py，不要重新建立 sql_connection_profiles 或 sql_connections.py。

注意：未提交內容一律視為使用者或上一位 Agent 的成果。若檔案看似不符合目前架構，先備份/產生 patch 並說明風險，再決定是否收斂。
```
