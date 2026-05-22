# Agent 接力卡

最後更新：2026-05-22

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
   docs/DEVELOPMENT_LOG.zh-TW.md
   docs/ARCHITECTURE.md
   docs/TECHNICAL_OVERVIEW.zh-TW.md
   docs/DATA_ASSET_PLATFORM_CONCEPTS.zh-TW.md
   docs/DATASET_TYPE_MAP.zh-TW.md
   docs/DATASET_DISCOVERY_NOTES.zh-TW.md
   docs/DEVELOPMENT_WORKFLOW_OPEN_SPEC.zh-TW.md
   docs/HEARTBEAT_AUTOMATION.zh-TW.md
   docs/WORKSPACE_LAYOUT.zh-TW.md
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

## 跨平台接力檢查

這一段把 Windows、macOS、Linux 的接力注意事項集中在同一份接力卡。白話說，跨平台問題常常不是「程式邏輯錯」，而是「本機環境假設偷偷寫進程式」。

每次接手先確認：

```bash
git pull origin main
git status --short --branch
git log -1 --oneline
```

如果 `git status` 看到未提交檔案，不要急著刪除、還原或覆蓋。先看 `git diff`，確認那是不是上一位 Agent 或使用者留下的成果。

Windows PowerShell 建議這樣跑：

```powershell
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP 'apikeys_collection_pycache'
py -m unittest discover -s tests
py -m py_compile APIkeys_collection.py APIkeys_collection_ui.py frontends\tk\launcher_ui.py api_launcher\core.py
py APIkeys_collection.py --init-db --seed --manifest-health --db state\ci.sqlite --summary
.\scripts\heartbeat_check.cmd -SkipCi
```

macOS / Linux / Conda 建議這樣跑：

```bash
PYTHONPYCACHEPREFIX=/tmp/apikeys_collection_pycache conda run -n metal_trade_312 python -m unittest discover -s tests
conda run -n metal_trade_312 python -m py_compile APIkeys_collection.py APIkeys_collection_ui.py frontends/tk/launcher_ui.py api_launcher/core.py
conda run -n metal_trade_312 python APIkeys_collection.py --init-db --seed --manifest-health --db state/ci.sqlite --summary
```

沒有 conda 時，可先用本機虛擬環境或 `python3`，但不要把依賴裝進 base/system Python。`PYTHONPYCACHEPREFIX` 是把 Python 暫存 bytecode 放到系統暫存目錄，避免雲端同步碟或跨平台檔案鎖干擾測試。

路徑與本機狀態規則：

- 程式裡不要寫死 `K:\...`、`/Users/...` 或任何本機絕對路徑。
- 新程式優先用 `pathlib.Path`，專案內路徑優先走 `api_launcher/paths.py` 或既有 config resolver。
- 對外輸出的跨平台路徑可用 `.as_posix()`，真的呼叫本機命令時再轉成本機字串。
- `.gitignore` 裡的 runtime 目錄要寫成 `/state/`、`/downloads/`，避免誤忽略 `api_launcher/downloads/` 原始碼。
- 不要提交 `state/`、`downloads/`、`tem/`、`config/*.local.json`、真實 API key/token/cookie/OAuth secret、本機 SQLite runtime 檔。
- `tem/` 是本機暫存資料夾，只用來放外部 agent 產物、概念 prototype、截圖、logs 與待評估素材。它已被 Git 忽略，其他團隊協作者從 GitHub clone 時看不到內容；若要交接其中資訊，請把重點寫進正式 docs/source，不要引用 `tem/` 路徑當成專案事實。

切換平台或交給下一位 Agent 前，至少確認：測試通過、語法檢查通過、CLI smoke 通過、文件已更新、已 commit/push，並用 `gh run watch --exit-status` 確認 CI。

## 目前專案定位

APIkeys Collection 是一個類 Steam 的科學資料集/資料庫 launcher。它不是單純 API key 管理器，而是要管理：

- 資料源與供應商 discovery seeds
- 下載計畫，也就是資料集購物車
- 非阻塞下載、續傳、暫停、重試、polite rate limit
- 本機資料庫與 data store 連線 profile
- install registry、版本、更新、解除納管/解除安裝安全流程
- API/CSV/JSON/manual SQL 匯入與清洗管線
- Taichi 與 Unreal 虛擬孿生 renderer bridge
- 未來 natural-language database management；Agent skill 屬於消費端包裝，接力仍以本文件為準

產品語言請更新成「資料工程版 Steam」：Steam 把找遊戲、裝依賴、更新 runtime、同步存檔、檔案驗證與本機安裝狀態懶人化；本專案要把找資料源、看官方文件、審核資料集、下載、匯入、manifest/checksum、repair、資料庫連線、渲染/分析橋接平台化。不要把它縮回 API key list。

請記住 Library / Install / Workspace 三層模型：Library/entitlement 表示使用者/profile 擁有或收藏哪些資料集；local install 表示這台機器實際安裝、匯入或快取了什麼；workspace/save 表示使用者標註、patch、查詢、分析筆記、下載計畫與偏好。原始資料集應像遊戲本體一樣盡量唯讀；使用者改動放 overlay/workspace，curated/cache/renderer bridge 是可重建的 derived asset。

Renderer bridge 也應被視為可管理資產，不只是程式碼。Tile manifest、cache file、mesh、texture atlas、chart index、shader/material preset 之後都可能需要 source dataset version、checksum、相容性、重建 recipe 與健康狀態。這類 bridge 類似資料世界的 DX12/OpenGL/Metal/Vulkan 橋接概念：資料本體先接 renderer bridge，再接 Taichi/Unreal/Cesium/chart frontend，最後才到圖形 backend。

中期產品形態請記住：Steam-like 也代表常駐本機資料管理器，不只是一次性視窗。Windows 目標是收進右下角系統匣，macOS 目標是收進功能列 / menu bar；後續架構應避免把下載、匯入、修復、更新提醒寫成只能跟 Tk 視窗生命週期綁死的流程。更長期可能有移動端 companion app，但手機端應是配對後的遙控器，只下達安全 action 與查看狀態；raw datasets、data-store credentials、API/AI tokens 與重型處理仍留在桌面端/服務端。

遠期也可能把常駐 launcher 做成 P2P / BitTorrent-like 資料節點，用來加速大型公開資料集下載。這個方向已有 Academic Torrents 等前例；本專案的差異是要把 P2P 放進 launcher 的資料治理流程。只能 opt-in，且只能用於授權允許再散布、版本與 checksum 明確的 public datasets；需要個人 token、私有資料、授權不明或禁止轉載的來源，不能被自動分享或做種。

中期需要預留 Hadoop 與 K8S 對接：Hadoop/HDFS/Hive/Spark 是另一個小組可能負責的分散式資料湖/批次運算後端；Kubernetes/K8S 則是另一個小組可能使用的 worker/job/service 調度層。放在「資料工程版 Steam」的產品語境裡，Hadoop 不突兀，因為它正是在處理 HDFS path、Hive/Metastore table、Spark job、partition、批次輸出與大型 raw/curated storage 這些使用者不想手動管理的雜事。Launcher 應保留 dataset ID、manifest、checksum、license/provenance、partition、job spec、job status、output manifest 作為交接契約。`data_store_connections.py` 已預留 `hadoop_default` profile；`launcher_integrations.example.json` 已預留 `runtime_orchestration_profiles` 的 Docker Compose/Kubernetes profiles。

## 目前 Git 狀態

| 欄位 | 值 |
| --- | --- |
| Branch | `main` |
| 最新已推送 commit | 接力前請以 `git log -1 --oneline` 為準。2026-05-21 目前已確認的遠端 checkpoint 是 `da35451 Consolidate docs refactor workflow`；GitHub Actions run `26230599073` 成功。這個 checkpoint 完成 README 繁中入口、discovery 文件收攏、文件整理規則、繁中 Mermaid 規則、開發者 CLI 索引收攏，以及 repo/local Codex skill 同步。下一輪接手仍要重跑 `git status --short --branch`、`git log -1 --oneline` 與 `gh run list --limit 5`。 |
| 上次本機驗證 | 2026-05-20 macOS/Antigravity/CloudMounter：IDE 權限按鈕恢復後，這個 session 已不再輸出 `CODEX_SANDBOX=seatbelt` / `CODEX_SANDBOX_NETWORK_DISABLED=1`；`curl -I --max-time 5 https://github.com` 回 HTTP 200，`test -w /Users/yen-an/.codex` 回 `writable`，`git add` / `git commit` / `git push` / `gh run watch` 都不再需要升權。早前餘波修復：`APIkeys_collection.py` 曾被工作樹刪除，已用 HEAD 可讀內容補回；缺失 Git blob `a60de8185d6ad444079a35ede668b19b1e70c5fa` 經確認等於 `frontends/unreal/README.zh-TW.md` 工作樹 hash 後，用 `git hash-object -w` 補回。本輪驗證：real-driver smoke test `py_compile` OK；`tests.test_data_store_real_drivers` 4 tests skipped as intended；`tests.test_data_store_connections tests.test_data_store_real_drivers tests.test_database_self_check` 62 tests OK、skipped=4；`PYTHONPYCACHEPREFIX=/tmp/apikeys_collection_pycache python3 -m unittest discover -s tests -v`，346 tests OK、skipped=5（4 個 opt-in real DB smoke、1 個 optional numpy renderer dependency）；`git diff --check` OK；GitHub Actions run `26165313576` Windows/Ubuntu/real-db-smoke 全部 success。 |
| 本輪本機驗證 | 2026-05-21 Windows/K: PowerShell Execution Policy 會擋直接執行 `.ps1` 的機器，已新增 `scripts\heartbeat_check.cmd` / `scripts\heartbeat_agent.cmd` wrapper；wrapper 用單次 `-ExecutionPolicy Bypass` 呼叫原本 `.ps1`，不改系統設定。另新增 `scripts\heartbeat_codex.cmd` / `.ps1` 作為真正呼叫本機 `codex exec` 的定時推進入口。`cmd /c scripts\heartbeat_check.cmd -SkipCi`、`cmd /c scripts\heartbeat_agent.cmd -SkipCi`、`cmd /c scripts\heartbeat_codex.cmd -SkipCi -DryRun` 是本輪 smoke 入口。上一輪 heartbeat automation 驗證：`tests.test_heartbeat -v` 共 10 tests OK；`tests.test_heartbeat tests.test_handoff tests.test_event_log -v` 共 13 tests OK；`py_compile` OK；CLI smoke `--heartbeat-report --write-heartbeat-plan-json --heartbeat-agent-prompt --heartbeat-skip-ci` 可產出 report/JSON/prompt；CI 首輪暴露 clean-worktree planner JSON circular reference，已改成 preview copy 並補 `test_clean_planner_payload_is_json_serializable`；`py -B -m unittest discover -s tests` 共 362 tests OK、skipped=4；`git diff --check` OK。本次 UI 啟動可見性收斂驗證：`py -B -m py_compile APIkeys_collection.py APIkeys_collection_ui.py frontends\tk\launcher_ui.py api_launcher\core.py` OK；`py -B -m unittest tests.test_launcher_ui -v` 2 tests OK；`py -B -m unittest discover -s tests` 366 tests OK、skipped=4；`py -B APIkeys_collection.py --summary` OK；`git diff --check` OK。文件一致性復查：`py -B APIkeys_collection.py --summary` 當時回報 `providers=54`、`key_placeholders=22`、`crawl_results=8`；2026-05-22 加入 optional yfinance provider 後，臨時 DB smoke 已回報 `providers=55`、`key_placeholders=22`。`docs/PROJECT_STATE.md` 已標成長篇歷史快照並更新舊計數，最新 checkpoint 由 `DEVELOPMENT_LOG`、`PROJECT_GTD`、handoff、`git log` 與 CI 共同確認。 |
| 最近新增重點 | Heartbeat automation 已有 repo-owned 第一階段實作：`api_launcher/heartbeat.py` 會讀 handoff/GTD、Git status、最新 commit 與可選 CI 狀態，產生 `--heartbeat-report`、`--heartbeat-plan-json`、`--write-heartbeat-plan-json`、`--heartbeat-agent-prompt`；`scripts/heartbeat_check.ps1` 是原始 PowerShell 檢查入口，`scripts/heartbeat_agent.ps1` 可 dry-run 產生 prompt，或在 `safe_to_progress=true` 且明確傳入 `-RunAgent -AgentExecutable ...` 時呼叫外部 agent runner。Windows 使用者可改跑 `.cmd` wrappers，避免 Execution Policy 擋 `.ps1`；其中 `scripts\heartbeat_codex.cmd` 才是真正接本機 Codex CLI 的定時推進入口，會在安全檢查通過時把 prompt 餵給 `codex exec`。這不是聊天 thread 自己喚醒自己，而是讓 Windows Task Scheduler/其他外部排程每 45 分鐘呼叫 repo 內腳本。Archive bounded transform 現在支援 ZIP/TAR 內的 `csv.gz`、`json.gz`、`jsonl.gz`、`ndjson`、`ndjson.gz`、`geojson.gz`，會寫衍生 manifest 並接既有 CSV/JSON importer；regression 已覆蓋 ZIP 內 `sample.ndjson.gz` 與 TAR.GZ 內 `sample.geojson.gz` 匯入 SQLite。Registry/source provenance 也正式接受並保存 compound source format，例如 `csv.gz`、`jsonl`、`ndjson`、`geojson`、`geojson.gz`、`zip`、`tar.gz`；下載檔案 asset 與 CSV/JSON/GeoJSON 匯入後的 curated table asset 會記錄實際 payload format。Guarded SQLite table reimport 也會用同一組支援格式，且錯誤/UI 文案會列出支援清單；現在 CLI/agent 可用 `--reimport-missing-sqlite-table ASSET_ID --database-repair-json` 走同一個安全 guard，也可用 `--unmanage-database-asset ASSET_ID --database-repair-json` 做 registry-only 停止追蹤；兩者成功後都會寫入 `database_repair_completed` structured event log。下載 manifest verification 現在會透過共用 helper 寫 `download_manifest_verification_completed`，Tk repair panel 的 requeue button 會寫 `download_repair_requeue_requested`，讓 handoff report / `--show-logs` 能看到檔案健康掃描與重新排下載結果。本輪讓 opt-in real MySQL/PostgreSQL smoke tests 進一步覆蓋 registry-backed table self-check：`APIKEYS_REAL_DB_SMOKE_ALLOW_WRITE=1` 時才會建立/清掉 `apikeys_ci_registry_smoke_*` 測試表，確認 managed table asset 的 present/missing 狀態，並 ALTER 同一張 generated table 觸發 schema fingerprint drift error。`docs/SETUP.zh-TW.md` 已補本機 disposable Docker/env-var 指南；一般本機/Windows/Ubuntu 全量測試仍預設不連線、不 DROP、不覆蓋既有 table、也不猜測未記錄來源。文件面新增 `docs/DEVELOPMENT_LOG.zh-TW.md` 作為已推送 checkpoint 日誌；`PROJECT_STATE.md` 降級為長篇歷史狀態快照，避免它和 live handoff/GTD 互相搶權威。 |
| MVP 剩餘估算 | 約 5.8% 到 6.2%；bounded adapter 的 DOI/DataCite、NOAA/NCEI data-file、CMR granule data-link、常見 resource 欄位命名與 JSON-LD `@graph` 包裝風險各收掉一塊，archive transform 已可處理 ZIP/TAR 內常見 CSV/JSON/GeoJSON 變體，database self-check UI 已有 profile/schema 修正、停止追蹤單一壞資產、manifest-backed missing SQLite table reimport、以及 MySQL/PostgreSQL dry-run SQL 產生，且 guarded reimport 已支援 CSV/JSON/JSONL/GeoJSON 類匯入來源；database repair、download manifest verification、Tk repair requeue 現在都會寫 structured event log；real MySQL/PostgreSQL smoke tests 已接進受控 CI service containers 並覆蓋 registry-backed present/missing/schema drift table self-check；plan-driven import 重跑現在有預設略過、CLI/UI safe-rename、明確 replace 三種路徑；Tk UI 啟動可見性已收斂；剩下主要是擴大更多明確擁有權 repair 範圍、crawler source 類型收束、少量 UI polish / docs sync |
| UI 入口 | `python3 APIkeys_collection_ui.py` 或 `py APIkeys_collection_ui.py` |
| Tk UI 實作 | `frontends/tk/launcher_ui.py` |
| 使用者指南 | `docs/USER_GUIDE.zh-TW.md` |

## 使用者合作偏好與雷點

這一段是給下一位 Agent 的人類協作提示，不是產品規格。使用者很願意討論概念層，也能接受快速推進，但對「看起來做了、其實沒有閉環」很敏感。

- 2026-05-20 Antigravity IDE 更新後一度沒有吃到 `~/.codex/config.toml` 的 `danger-full-access` 設定，舊 session 顯示 `CODEX_SANDBOX=seatbelt`、`CODEX_SANDBOX_NETWORK_DISABLED=1`，因此早上曾採用偏保守的應急開發策略。使用者已確認 IDE 提供方妥善處理，這個危機目前已不復存在；後續應恢復穩健的正常流程：完成一個可驗證切片後本機測試、commit、push，並用 `gh run watch` 確認 CI。接力前仍可跑例行檢查：`env | sort | rg 'CODEX_SANDBOX|CODEX_SANDBOX_NETWORK_DISABLED'`、`curl -I --max-time 5 https://github.com`、確認 `.codex` 可寫；若未來又出現 sandbox/network disabled，視為新的環境異常再診斷，不要把早上的應急策略當成目前狀態。
- 開發策略已正式往 OpenSpec-aligned workflow 過渡。下一位 Agent 不要只把 OpenSpec 當成可選工具，而要把它視為新的協作規範方向：凡是中大型、跨模組、會影響架構/資料模型/UI/外部整合的改動，先寫清楚「變更目的、範圍、任務、驗收標準、風險」再實作；小修、測試補強、窄範圍 bugfix 可以維持快速小步，但完成後要回補 GTD / handoff / 相關設計文件。正式 `openspec/` 目錄已建立，第一個 capability 是 `openspec/specs/development-workflow/spec.md`；Spectra GUI 已裝在 `~/Applications/Spectra.app`；Qt Designer 以 `conda run -n metal_trade_312 pyside6-designer` 啟動。
- 匯報要面向初學者：少用抽象工程術語，多用白話說明「這一步解決什麼、還差什麼、為什麼重要」。每次中途或最後匯報，順手說明距離 MVP 還剩哪些大塊。
- 做到一個穩定節點就要 commit/push，並用 `gh run watch` 或 `gh run list` 確認 CI。使用者手機會收到 GitHub Actions 通知，所以不要只說 push 成功。
- 不要在 base/system Python 裝套件；目前 macOS 主要使用 `conda run -n metal_trade_312 ...`。
- 遇到環境差異先配置，不要假設 Windows 路徑可在 Mac 用。尤其 Mac 啟動時要依系統選路徑分隔符與平台路徑，不要讓 Windows `K:\...` 類路徑阻擋 UI。
- 不要硬編碼代表資料集。使用者反覆強調 crawler-first：先找供應商/目錄，解析目錄，再產生候選；adapter 只處理 bounded query、auth、轉換、匯入等必要邏輯。
- Crawler 不能只看「程式沒報錯」。如果抓到 0 筆、低於預期、全是重複、payload shape 不符，都要明確 warning/error；使用者特別在意這種假成功。
- 未提交檔案或大改動不要擅自刪除、覆蓋、`git restore`。2026-05-17 曾發生誤還原事故，讓使用者很不安；任何看似奇怪的檔案都先備份/看 diff/產生 patch。
- UI 預設要繁中；如果新增 UI，放到合適的選單或設定，不要到處新增零散入口。使用者覺得 Tk UI 目前只是過渡，PySide/Qt 是中期路線，MVP 前不要重寫。
- 使用者喜歡產品概念層被記錄下來，例如 Steam-like library/install/workspace、renderer bridge、Hadoop/K8S、GIS/時間序列/多媒體資料類型。但實作時仍要先收束 MVP。
- 使用者老師提到 OpenSpec；使用者希望未來開發模式逐步往 spec-driven/changes/tasks/spec delta 靠攏。短期把它當成「中大型變更要有迷你規格與驗收標準」的流程方向，不要讓規格流程阻塞 backend MVP。OpenSpec CLI 透過 `npx -y @fission-ai/openspec@latest ...` 使用；Spectra 是 GUI 輔助，Git 裡的 `openspec/` 才是權威來源；不要把任何 Python 套件裝進 base/system Python，Python/Qt 相關工具優先放 `metal_trade_312`。
- 使用者認為所有文件都重要；不要把任何 `.md` 當成可忽略雜檔。每次功能改動後，至少回頭檢查 `PROJECT_GTD.md`、`AGENT_HANDOFF.zh-TW.md`；跨平台或接力流程改變時，直接更新本文件的「跨平台接力檢查」段落，必要時再更新 `DOCS_INDEX.zh-TW.md`、`WORKSPACE_LAYOUT.zh-TW.md`、使用者指南或相關附錄，讓下一位 Agent 容易接力。
- 未來新增英文文件時，必須同時準備繁中版本，或至少在同一輪提交提供繁中摘要與清楚入口。若大幅更新現有英文文件，例如 `ARCHITECTURE.md`、`TECH_STACK.md`、`PROJECT_STATE.md`、`GIT_HANDOFF.md`，也要同步更新繁中閱讀路線；使用者不希望重要接力脈絡只留英文。
- 使用者明確提醒目前有過度編程風險。新增程式碼前先回答三問：它服務 MVP 哪一段（主線是 `seed -> crawler -> candidate -> plan -> download -> import -> UI`）、目前被哪個 CLI/UI/測試/文件流程入口使用、移除後 MVP 會不會受影響。Hadoop、K8S、P2P、mobile、完整 Google OAuth、多 AI profile、Qt migration、Spectra/OpenSpec GUI 等保留在文檔或 stub，不要搶 MVP 主線；不要為單一場景建立大型 base class / registry / strategy pattern。
- 使用者會提出發散想法；可以記錄到文檔/中期目標，但當前開發要常提醒「這次實際推進的是哪個 MVP 環節」。
- 使用者說「繼續推進」或暫離時，通常期待 Agent 自主完成下一個合理小階段：實作、驗證、更新文檔、git commit/push、查 CI。不要每個小選擇都停下來問，但遇到會破壞資料、刪檔、改秘密資訊、或安裝環境不明時要先保守處理。
- Heartbeat automation 的正確理解：repo 現在能產生檢查報告、JSON plan、外部 agent prompt，也有 PowerShell 腳本可被外部排程器呼叫；Codex 聊天本身不會無中生有定時喚醒。正式接上自動 agent 前，先用 `.\scripts\heartbeat_codex.cmd -DryRun` 做 dry-run，確認 `state/heartbeat/heartbeat_plan.json` 和 `state/heartbeat/agent_prompt.md` 符合預期；確認後才把 Task Scheduler 指到 `heartbeat_codex.cmd`。

## 最近完成

- Tk UI 實作檔已從 `frontends/tk/APIkeys_collection_ui.py` 改名為 `frontends/tk/launcher_ui.py`。
- Tk UI 從 IDE 或背景 shell 啟動後會自動浮出、短暫置前並印出 `APIkeys_collection UI ready ...`；相關 TclError suppressor 已收窄成只吞 Tk/Tcl 視窗生命週期錯誤，不再靜默吞掉非預期例外。
- 新增 `docs/CODE_RELATIONSHIP_MAP.zh-TW.md`、`docs/MVP_FLOW_AUDIT.zh-TW.md`、`docs/USER_MANUAL.zh-TW.md`：分別補上程式關聯地圖、Demo 閉環稽核、帶圖說的使用者操作手冊。之後整理資料夾或新增功能時，先同步這三份文件，避免調度關係只留在聊天紀錄。
- 文件與 skill 的優先順序已明確：`.md` 是 source of truth，skill/prompt/script 是消費層。整理好 `.md` 後要回頭改 skill 引用，而不是讓舊 skill 路徑反過來決定文件不能整理。
- 調度流程文件應優先用 Mermaid。新增跨模組流程、Demo route、資料流或調度關係時，先更新 `ARCHITECTURE.zh-TW.md`、`CODE_RELATIONSHIP_MAP.zh-TW.md`、`MVP_FLOW_AUDIT.zh-TW.md` 或 `USER_MANUAL.zh-TW.md` 的 Mermaid 圖，再補文字。
- 文件整理規則已固化：使用者要求整理或重構 `.md` 時，先盤點檔名/heading 與引用路徑，每次只整理一組文件，保留舊路徑 redirect/summary，再同步 `DOCS_INDEX.zh-TW.md`、本 handoff、`PROJECT_GTD.md` 與 repo skill。繁中 `.md` 的 Mermaid 可見文字要優先使用繁體中文，只有檔名、CLI flag、模組路徑、產品名或標準名保留原文。
- Discovery 文件已收攏：`docs/DATASET_DISCOVERY_NOTES.zh-TW.md` 現在是 crawler / candidate review / bounded resolver / adapter handoff 的主入口；`docs/appendices/discovery.zh-TW.md` 只保留為舊引用 redirect，不再新增新規格。repo 內 `.codex/skills/apikeys-collection-launcher` 的路由也已跟著改。
- 開發者 CLI 指令索引先收攏在 `docs/USER_GUIDE.zh-TW.md` 的「開發者 CLI」章節，不新增獨立 CLI 文件；等指令規模真的讓使用指南過長，再拆成獨立文件並保留入口連結。
- 根目錄新增 `README.zh-TW.md` 作為繁中 README 入口；英文 `README.md` 只補連結，避免新使用者第一入口只有英文。
- 新增 `docs/ARCHITECTURE.zh-TW.md` 作為中文架構入口；英文 `docs/ARCHITECTURE.md` 保留，但未來架構大改要同步更新中文版本。
- Heartbeat automation 第一階段已加入 CLI 與 Windows entrypoints：`--heartbeat-report`、`--heartbeat-plan-json`、`--write-heartbeat-plan-json`、`--heartbeat-agent-prompt`、`scripts/heartbeat_check.ps1`、`scripts/heartbeat_agent.ps1`、`scripts/heartbeat_check.cmd`、`scripts/heartbeat_agent.cmd`、`scripts/heartbeat_codex.ps1`、`scripts/heartbeat_codex.cmd`。
- 根目錄 `APIkeys_collection_ui.py` 保留相容入口，不要刪。
- SQL-only 連線模組已合併進泛用 data store contract。
- `api_launcher/data_store_connections.py` 現在統一管理 MySQL/PostgreSQL/SQLite、MongoDB、S3-compatible object storage、vector DB。
- `config/launcher_integrations.example.json` 使用 `data_store_connection_profiles`，不要重新新增 `sql_connection_profiles`。
- `api_launcher/library_actions.py` 已提供 action map/order/menu-label helpers，Tk 右鍵選單已開始共用這套規則。
- `api_launcher/library_actions.py` 已提供 agent-readable JSON payload；CLI 可用 `--show-library-actions PROVIDER_ID --library-actions-json` 讓未來 skill 重用同一套 action 規則。
- Tk UI 已新增 `Tools > Recent event logs`，可以直接查看 `state/logs/launcher_events.jsonl` 的近期事件。
- Tk UI 的 `工具 > 修復 / 驗證資產` 現在會開啟 repair panel，分成「下載檔案」與「資料庫」兩個分頁；下載檔案分頁列出每個 download manifest 的健康狀態與路徑，並會在驗證與重新排下載時寫入 structured event log。
- Repair panel 現在會顯示安全修復建議；對有 HTTP(S) `source_url` 和 `provider_id` 的 missing/size/checksum manifest，可用「重新排下載」透過 staging 重新排下載。
- HTTP downloader 已新增「已驗證下載重用」：如果目標檔案和 sidecar manifest 都正常，且 provider/dataset/version/source/path 符合目前下載請求，就不重新連網下載。Tk UI 也會記住實際送進下載器的 plan entry，版本下載完成時 registry 的 `source_uri` 不會誤寫成原 provider URL。
- 健康的下載 manifest 現在可登錄為 install registry 裡的 managed `file` asset；CLI `--verify-downloads` 與 Tk 下載完成流程會共用 `register_downloaded_manifest_asset()`。Database self-check 已限定只驗 `database` / `table` asset，避免把已下載檔案誤判成資料庫錯誤。
- Adapter 發現的 dataset version 現在可用 CLI `--export-dataset-plan PATH` 匯出成下載計畫。直接檔案 URL 會有 `download_url`/`target_path`/`use_staging`；入口頁或 selector 會標記成 `adapter_required` 並放在 `adapter_review_url`，不要直接交給 HTTP downloader。
- CLI `--run-download-plan PATH` 現在可執行 plan 裡的 direct entries，跳過 `adapter_required`，下載完成後驗 sidecar manifest 並登錄 managed filesystem `file` asset。可用 `--download-plan-limit N` 做小量 smoke test。
- CLI `--write-mvp-demo-flow state/mvp_demo/flow.json` 現在可產生固定 MVP Demo Flow：會寫出 flow manifest、Socrata adapter review plan、離線 JSON fixture、離線 direct plan 與下一步指令。它使用 `state/mvp_demo/launcher.sqlite` 隔離 demo registry；離線 plan 可穩定驗證 `download -> manifest -> SQLite import`，Socrata `$limit=25` resolved plan 則用來驗證真實 adapter resolver。Tk UI 也已新增 `工具 > 產生 MVP Demo Flow` 與上方 `更多 > 產生 MVP Demo Flow`，會呼叫同一個 `api_launcher.mvp_demo`，寫出 `state/mvp_demo/*` 並把離線 direct plan 加到下方下載計畫；UI 不會自動下載或自動匯入，使用者仍需明確按「開始」與「匯入」。後續不要把 demo 業務邏輯寫死在 Tk 裡。
- CLI `--import-csv-manifest MANIFEST --import-sqlite-db PATH --import-table TABLE` 現在可把健康 CSV/CSV.GZ manifest payload 匯入 curated SQLite table，欄位名稱會正規化成安全 SQL identifier，並登錄 `asset_role=curated` 的 table asset 與 schema fingerprint。若要覆蓋既有 table，必須明確加 `--import-replace-table`。
- CLI `--import-verified-csv-manifests --import-sqlite-db PATH` 可批次匯入 registry 裡的健康 CSV/CSV.GZ manifests；預設跳過非 CSV、不健康 manifest、已存在 table。可搭配 `--provider ID` 限定資料商。
- CLI `--import-json-manifest MANIFEST --import-sqlite-db PATH --import-table TABLE` 現在可把健康 JSON/JSONL/NDJSON/GeoJSON manifest payload 匯入 curated SQLite table。支援物件陣列、JSON Lines、`records/items/results/data` 包起來的陣列、NASA CMR 常見的 `feed.entry` 巢狀陣列，以及基本 GeoJSON FeatureCollection；欄位先以 `TEXT` 存入並登錄 `asset_role=curated`、實際 `source_format`（例如 `jsonl` 或 `geojson`）與 schema fingerprint。
- CLI `--import-verified-json-manifests --import-sqlite-db PATH` 可批次匯入 registry 裡的健康 JSON/JSONL/GeoJSON manifests；預設跳過非 JSON、不健康 manifest、已存在 table。這是 CSV 後的第二條 raw -> curated MVP 路徑。
- CLI `--run-download-plan PATH --import-supported-plan-results --import-sqlite-db PATH` 現在可在 direct entries 下載並驗證 manifest 後，依 plan entry 的 `import_plan` 自動匯入支援的 CSV/JSON/GeoJSON 類 payload。匯入成功、跳過、不支援、匯入失敗會和 download/manifest 結果分開統計；同一份 plan 重跑時，如果目標 table 已存在，預設會記為 `skipped_existing_table`，不當成失敗，也不覆蓋資料。若要保留舊表但匯入新結果，可加 `--plan-import-existing-table-policy rename`，產生 `table_2` 這類新表；明確覆蓋仍需 `--import-replace-table` 或 `--plan-import-existing-table-policy replace`。
- 2026-05-22 收束：`api_launcher/ingestion_pipeline.py` 是第一個 download/import pipeline slice。`core.py --run-download-plan` 現在透過 `run_download_import_slice()` 執行 direct plan，並由同一個 service 產生 CLI 摘要、blocked `next_action`、匯入統計與 agent/UI 可讀的 stage；Tk UI 的 `匯入可支援下載結果` 也改用 `run_existing_download_import_slice()` 做已下載 manifest 的重新匯入，不再在 `launcher_ui.py` 內重寫 manifest/register/import loop。後續 UI 或 subcommand 若要跑同一段流程，應呼叫 `ingestion_pipeline.py`，不要再直接組 `run_download_plan_payload()` 參數或重寫輸出格式。
- 2026-05-22 手動匯入 CLI：`api_launcher/manual_import.py` 補上使用者自備本機 CSV/JSON 類檔案的 manifest/provenance 入口。`--write-local-file-manifest OUTPUT --local-file FILE` 只寫 sidecar manifest 並顯示下一步匯入指令；`--import-local-file FILE` 會把 manifest 寫到 `state/manual_imports/`、登記 raw file asset 到 synthetic provider `manual_local_files`，再重用既有 CSV/JSON importer 寫入 SQLite。這條路不掃資料夾、不移動/刪除來源檔、不把 `file://` 視為可重排網路下載，也不覆蓋既有 table，除非使用者明確傳 replace。
- 2026-05-22 手動匯入 UI：Tk `資料庫 > 匯入本機 CSV/JSON 檔` 與「更多 > 匯入本機 CSV/JSON 檔」會走同一套 `api_launcher/manual_import.py`。UI 只讓使用者選一個本機檔，可留空 table 名稱由檔名推導；若目標 table 已存在，會用 `unique_table_name()` 自動改名，不覆蓋既有資料。完成後寫 `ui_import_local_file_completed` event，列出 input、manifest、SQLite、table 與 rows/columns。
- 2026-05-22 手動匯入 JSON：CLI `--write-local-file-manifest ... --manual-import-json` 與 `--import-local-file ... --manual-import-json` 會輸出單一 JSON payload，供 heartbeat / agent / 外部工具解析。payload 會包含 manifest、raw asset id、匯入結果、schema fingerprint 與下一步 database self-check 建議；`--manual-import-json` 不應單獨使用。
- 2026-05-22 手動匯入 provenance review：手動匯入 manifest 的 `metadata.provenance_review` 會固定記錄中文來源審查摘要，包含「使用者自備本機檔案」、格式標籤、trust boundary、safe operations、blocked operations、授權/再散布 caveat 與下一步資料庫自檢建議。這是給初學使用者、團隊協作者與 agent 的風險提示，不代表檔案來源或授權已被驗證。Tk 手動匯入完成對話框也會顯示短版來源審查，避免使用者必須打開 manifest JSON 才看得到風險邊界。
- 2026-05-22 手動匯入不支援格式引導：若使用者選到 SQL、Excel、Parquet、Shapefile、NetCDF、HDF、ZIP/TAR 原始包或其他非 CSV/JSON 類格式，`api_launcher.manual_import` 會拒絕並提示先轉成支援格式，或留給 adapter/manual review。不要為了閉環而把未知格式硬塞進 SQLite。
- 2026-05-22 收束：`--run-download-plan` 現在會把未送出的項目拆成 `skip_summary`，例如 `adapter_required`、`metadata_only`、`unavailable`、`missing_download_url`、`not_direct`。只要 plan 有 skipped，pipeline 就保留 `next_action=run_adapter_review_or_resolve_adapter_plan_before_downloading`，避免「部分 direct download 成功」被誤判成整份 plan 完成；Tk UI 在沒有 direct download，或有部分 direct download 已啟動但另有項目被略過時，都會用對話框提示使用者先開 Adapter 待辦或解析 Adapter 計畫。後續維護時請保持這種「不能下載 -> 顯示原因 -> 指向修復/解析入口」的閉環，不要退回只顯示 skipped。
- 2026-05-22 本地預檢：`scripts/pre_push_smoke.cmd` / `.ps1` 可在 push 前跑 `git diff --check`、核心 `py_compile`、完整 `unittest discover -s tests` 與 `--summary`，並用 temp pycache 避免 Windows/RaiDrive 鎖檔。`scripts/install_pre_push_hook.cmd` / `.ps1` 可把這條 smoke 安裝成該 clone 的 `.git/hooks/pre-push`；hook 是本機設定，不會進 Git。它負責把錯誤盡量擋在 push 前；push 後仍要跑 `gh run watch --exit-status`，讓遠端 checkpoint 留下可回溯 CI 紀錄。若真的需要繞過，使用 `git push --no-verify` 前要先確認風險。
- Tk UI 已把 plan-driven import 接成 guided action：下載計畫區有 `匯入` 按鈕，`資料庫 > 匯入可支援下載結果` 與「更多」選單也有入口。它會取目前 plan item / 實際下載 plan entry，交給 `api_launcher/ingestion_pipeline.py` 檢查 sidecar manifest、登錄 downloaded manifest asset，再對 `import_plan.status=supported_after_download` 的 CSV/JSON/GeoJSON 項目匯入 `state/curated_imports.sqlite`。下載計畫與下載工作表會顯示匯入狀態/table hint，例如待下載/驗證、可匯入、已匯入、需 adapter、需解壓/adapter。目前不做 destructive replace；若 table 已存在，UI 會自動改名成下一個可用 table，例如 `table_2`，避免覆蓋使用者資料；若共用 helper 回傳 `skipped_existing_table` 這類狀態，UI 會顯示為「略過」，不顯示成失敗。
- `--verify-downloads-json` 已提供下載檔驗證的 agent-readable JSON：包含 summary、issues、repair suggestion、以及 HTTP(S) manifest 可安全重排下載的 plan entry。若要指定掃描資料夾，可搭配 `--downloads-root PATH`。每次 CLI/Tk manifest 掃描後都會寫入 `download_manifest_verification_completed` structured event，記錄 checked/issue/requeue counts 與最多 20 筆 issue preview；Tk requeue button 也會寫 `download_repair_requeue_requested`，記錄 queued / already_active / not_requeueable / failed 與 job/error context，方便 `--show-logs` 和 handoff report 回溯最近一次檔案健康檢查。
- Library action agent payload 現在可接同一條下載 repair suggestion stream：`--show-library-actions PROVIDER --library-local-status imported --library-install-id INSTALL --library-repair-manifest PATH --library-actions-json` 會驗 sidecar manifest，把 `manifest_health` 與 `related_repair_suggestion` 掛在 `repair` action 上；Tk 右鍵 repair action 也改為開共享 `修復 / 驗證資產` panel，避免 UI 另走一套 repair policy。
- Tk UI 新增 `設定 > 介面語言`，語言存在 `launcher_integrations.local.json` 的 `ui_language`。預設是 `zh-TW`；新開啟 dialog 會套用，主畫面完整套用需重新啟動。後續碰 UI 時應優先補齊繁中顯示與 `tr(...)` 英文 fallback。
- Tk UI 的登入/串接入口已集中到上方 `整合` 選單：`AI / Gemini 串接中心`、`保存 Gemini API key`、`AI 輔助模型選擇`、`Google OAuth（中期 / 開發者）`、資料儲存連線與資料庫工具都在這裡。主工具列和右側抽屜不要再新增登入/API key/資料庫工具設定入口；抽屜只保留目前資料源的動作。
- AI 生成描述目前以功能閉環為優先：Gemini API key 是 MVP 雲端路線，`api_launcher/ai_api_keys.py` 會把 key 存在 ignored `state/private/ai_api_keys.private.json`，UI 啟動時只會自動載入 saved API key；不要在啟動時 activate Google/OAuth token、打開瀏覽器、打開本機設定檔或叫出 OAuth 設定。`generate_provider_summary()` 也會嘗試載入 saved key。使用者只應在缺 credential 時被要求保存 key，不要每次重貼。
- Google OAuth / QR 是中期正式目標，不是不做；只是現在 MVP 尚未閉環，先不要讓它阻塞 AI 描述生成。一般使用者不該被要求貼 Desktop OAuth Client ID；若沒有專案官方 OAuth App，就顯示尚未開通。開發者仍可透過 `整合 > Google OAuth（中期 / 開發者） > 開發者 OAuth 設定` 測試，格式不像 `*.apps.googleusercontent.com` 的值會被拒絕保存，避免重複觸發 Google `invalid_client`。
- PySide6 / Qt 已列為中期 UI 升級路線：不要現在重寫 UI；先完成 backend/MVP 閉環。後續若啟動 Qt，應新增 `frontends/qt/` 並重用 `api_launcher`、library actions、event logs、download queue、integration contracts，不要把業務邏輯複製進 UI。Provider icon/favicons 的中期方向是 SVG/vector-first；Tk 可保留可重建 bitmap cache 作顯示相容層，但不要把 PNG 當成 canonical icon asset。
- Tk UI 資料源詳情改為右側比例抽屜：抽屜寬度依主內容區比例計算，保留表格基本空間，開關時有短距離寬度動畫；標題列與關閉按鈕固定在上方、動作按鈕固定在底部，中間內容才捲動，避免關閉按鈕被捲軸遮住或按鈕隨長文字漂移。描述/狀態/連結文字會依抽屜寬度換行；抽屜內另有 AI 生成描述 textbox。
- Tk UI 左側欄可在「依類型」與「依提供商」間切換；提供商模式會依目前 catalog owner 動態產生篩選按鈕，並在背景抓取/快取官網 favicon 到 `state/favicons/` 當小圖示。現階段 Tk 顯示可能需要 raster cache；未來要改成 SVG/vector canonical asset，再由 Tk 或 Qt 顯示層產生必要的衍生快取。
- Tk UI 新增 `工具 > 開發者 CLI`，提供專案工作目錄下的單次命令輸入/輸出面板，供開發者快速呼叫 CLI。
- Tk UI 主表格支援類 Excel 欄寬調整：拖拉欄位分隔線後，欄寬會寫入 `launcher_integrations.local.json` 的 `ui_table_column_widths`；「更多 > 重設表格欄寬」可清除回預設比例。
- Tk UI 的下載資格與詳情狀態文字已補上繁中顯示，UI 語言切到 `en-US` 時仍保留英文 fallback。
- Data store connection testing 已有骨架：`--test-data-store PROFILE_ID|all` 可測 configured profiles；`--test-data-store-json` 可輸出 agent-readable status/details/next_action；`--set-active-data-store-profile PROFILE_ID` 可把本機作用中 data-store profile id 寫進 ignored local config；`--write-data-store-env-template PATH --data-store-env-template-profile PROFILE_ID` 可寫出空值 `.env` 範本，Tk `整合 > 資料儲存連線` 可設作用中 profile、測試連線、寫出 env 範本。SQLite 會用 read-only introspection，MySQL/PostgreSQL 先檢查 env vars 與 optional Python driver；範本與 active profile 都不保存密碼。
- Data store profiles 支援 `env_var_map`，可把 host/database/user/password/port/path 對應到自訂環境變數名稱；密碼仍不寫進 Git config。
- SQL/database self-check 已擴充到 SQLite database/table assets：`--self-check-databases` 會用 registry asset verifier 檢查 managed database/table assets；SQLite database asset 依 `source_uri`/path 做 read-only 檢查與 database-level fingerprint，SQLite table asset 依 `source_uri` + `asset_name` 檢查單表存在與 table-level fingerprint drift，並回寫 asset/provider 狀態與 missing/error 明細。
- MySQL/PostgreSQL data-store layer 已有 `information_schema` introspection helpers：連線 smoke 可回報 table_count；database/table asset 若登記 `schema_fingerprint`，self-check 會要求 schema summary 並偵測 drift。`tests/test_data_store_real_drivers.py` 是 opt-in 真實 driver smoke：只有設定 `APIKEYS_RUN_REAL_DB_SMOKE=1`、對應 DB env vars、以及 optional Python driver 時才會真的連線；預設 skip，且只做 read-only connection/schema introspection。若額外設定 `APIKEYS_REAL_DB_SMOKE_ALLOW_WRITE=1`，才會在 disposable DB 建立/清理 generated smoke tables，並跑 registry-backed table self-check；write-enabled path 會覆蓋 present、missing、以及對 generated table 執行 `ALTER TABLE` 後的 schema drift error。CI 已有獨立 Ubuntu `real-db-smoke` job，會用 disposable MySQL/PostgreSQL service containers 和 `requirements-db-smoke.txt` 跑完整測試；一般 test matrix 不需要 DB driver。跨引擎 table asset 會從 `install_location` 解析 database owner，PostgreSQL `asset_name` 可用 `schema.table` 指定 schema，並能標記 missing table。
- Database/table asset 現在可記錄 `data_store_profile_id` 與明確 `schema_name`；self-check verifier 會吃 local integration config 裡的 configured profiles。白話說，之後 UI 可以讓使用者替某個資料庫資產指定「用哪個連線設定、查哪個 schema」，不必永遠靠預設 MySQL/PostgreSQL env vars。
- `--self-check-databases` 現在人類輸出會包含 `suggestion=...` 修復代號；`--self-check-databases-json` 會輸出純 JSON，包含每個 missing/error database/table asset 的錯誤、去敏感化位置、是否有 schema fingerprint、profile/schema metadata、以及修復建議。MySQL/PostgreSQL 缺表若有健康 CSV/JSON/GeoJSON 類 manifest，JSON details 會標 `sql_dry_run_available=true`，下一步可用 Tk「產生 dry-run SQL」或 CLI `--write-database-repair-sql ASSET_ID` 產生人工審核用 SQL；這仍不是自動修復。Database repair CLI/UI 成功時也會寫 `database_repair_completed` 到 `state/logs/launcher_events.jsonl`，可用 `--show-logs 20` 查。
- Tk Repair panel 的「資料庫」分頁會重用同一套 database self-check verifier 與 `database_self_check_issues()`；現在可用「調整資料庫連線」修改單一 database/table asset 的 `data_store_profile_id` 與 `schema_name`，儲存後清掉舊 error 並重新自檢；也可用「停止追蹤」把單一 database/table asset 標成 `unmanaged`，讓它退出後續自檢；若是由 CSV/CSV.GZ/JSON/JSONL/NDJSON/GeoJSON manifest 匯入過、現在 table missing 的 SQLite table，可用「重新匯入資料表」從記錄的健康 sidecar manifest 重建缺失 table。非 SQLite 的 MySQL/PostgreSQL 缺表若標有 `sql_dry_run_available=true`，可用「產生 dry-run SQL」寫出 `state/database_repair/*.dry_run.sql` 供審核，不連線、不執行 DDL/DML、不修改 registry。CLI/agent 可用 `--unmanage-database-asset ASSET_ID --database-repair-json` 做同一個 registry-only 停止追蹤，也可用 `--reimport-missing-sqlite-table ASSET_ID --database-repair-json` 呼叫同一個 reimport guard，或用 `--write-database-repair-sql ASSET_ID --database-repair-json` 呼叫同一個 dry-run SQL guard。`database_self_check_issues()` / `--self-check-databases-json` 只在 SQLite manifest-backed 缺表條件成立時標 `can_auto_repair=true`，UI/CLI 都會擋下不符合條件的重新匯入列。停止追蹤只改 registry metadata；重新匯入只在 table 不存在時建立 table，不自動 `DROP`、覆蓋既有 table、或移動檔案。
- 2026-05-17 已修復 Windows CI：Python `with sqlite3.connect(...)` 不會自動 close connection，Windows temp SQLite 會被檔案鎖住並造成 `WinError 32`；短生命週期 SQLite probe/test 請用 `contextlib.closing(sqlite3.connect(...))`。
- macOS 目前已安裝並登入 GitHub CLI (`gh`) 為 `YanAnnLu`，可直接查 CI run/log。
- 海域法域資料請記住：領海、EEZ、爭議區、公海不是單純座標戳，而是帶法律/行政屬性的 GIS polygon 圖層。MySQL spatial 可做 MVP；較完整 GIS 分析、切 tile、空間索引應優先考慮 PostGIS；原始資料保留 GeoPackage/Shapefile/GeoJSON 與 manifest。
- 團隊開始共同尋找資料庫入口網站時，請先寫入 `docs/DATABASE_PORTAL_INTAKE.zh-TW.md`。這是組員用的入口收集表，不要貼 API key/token/cookie；只記網站、API 文件、授權、入口類型、主題、地理範圍與是否需要登入。CLI 已有 `--portal-intake-report --write-portal-intake-json state/portal_intake.review.json`，會把表格整理成 provider seed 草稿、dataset discovery source 草稿、crawler mapping 待辦、adapter/integration backlog 或 incomplete warning；`--promote-portal-intake-local` 只會把乾淨草稿寫進被 Git 忽略的 `config/provider_discovery_seeds.local.json` 與 `config/dataset_discovery_sources.local.json`，不直接改正式 catalog。草稿要進正式 catalog 時，用 `--promote-local-discovery-catalog --write-local-discovery-audit-json state/local_discovery_audit.json`；這會先跑 crawler audit，只有 error=0/warning=0 的 local dataset source 才會寫入正式 catalog。
- `docs/DATASET_DISCOVERY_NOTES.zh-TW.md` 是重要 discovery 主入口，不是暫存雜檔；crawler-first、爬蟲資產 / Aseat、candidate review、bounded resolver、adapter handoff、dataset-version plan 的新規格都應寫在這裡。`docs/appendices/discovery.zh-TW.md` 只保留 redirect/摘要，避免舊 handoff、skill 或 prompt 引用失效。
- 2026-05-22 已補「爬蟲資產 / Crawler Asset / Aseat」概念：它是 API 搜集器的概念擴充，代表可治理、可版本化、可審核、可排程、可修復的資料取得能力；它不取代 Provider、Dataset、DatasetDiscoverySource、Adapter 或 Mission，而是把現有 crawler/source/resolver/event-log 流程包成產品層。短期不要為此硬加大型 registry；等 UI/健康檢查/repair mission 需要時，再把它提升成正式資料模型。
- 近期 GTD 加入 Notion-backed seed intake：使用者打算開一個 Notion 分頁/資料庫給組員維護入口網站清單。Notion 應視為雲端 intake/staging，不是正式 catalog 權威；未來 sync 指令應把 Notion rows 轉成與 `docs/DATABASE_PORTAL_INTAKE.zh-TW.md` 相同的 review JSON / local seed / local dataset source，再跑 crawler audit，通過後才提升正式 catalog。注意 sync 要記 provenance，避免不清楚 seed 從哪列 Notion 來。
- 工作區分類已新增 `docs/WORKSPACE_LAYOUT.zh-TW.md`，並提供 CLI `--workspace-inventory --write-workspace-inventory-json state/workspace_inventory.json`。這是盤點工具，不會自動搬檔或刪檔；下一位 Agent 整理 `.py` 前請先用它看大檔案、分類與 root runtime files。`api_launcher/cli_flags.py` 已先把 CLI command-detection 從 `core.py` 拆出來，後續 core 瘦身要沿用這種小步、可測、保守拆分方式。
- `tem/` 已正式定義成本機暫存資料夾，並由 `.gitignore` 排除。它可以保存外部 agent 交接包或概念素材，但不是 canonical source of truth；團隊協作者與 CI 都不會看到本機 `tem/` 內容。下一位 Agent 若從 `tem/` 讀到有用資料，應把摘要或正式檔案搬進文件/原始碼後再提交。
- Crawler 共用資料結構已從 `api_launcher/crawlers/dataset_sources.py` 拆到 `api_launcher/crawlers/types.py`。舊的 `dataset_sources.py` 匯入路徑仍可用，這是為了相容既有 CLI/UI/測試；新程式若只需要 `DatasetDiscoverySource` 或 `DatasetCandidate`，優先從 `api_launcher.crawlers.types` 匯入。
- Crawler 共用 metadata helper 已拆到 `api_launcher/crawlers/metadata.py`，HTTP fetch/JSON/URL helper 已拆到 `api_launcher/crawlers/fetch.py`，共用 full-crawl page cap 與候選去重 append helper 已拆到 `api_launcher/crawlers/pagination.py`，STAC collection payload parser、source-level fetch/parse flow 與 STAC pagination flow 已拆到 `api_launcher/crawlers/stac.py`，CKAN package query URL builder/payload parser/source-level fetch/parse flow/pagination flow 已拆到 `api_launcher/crawlers/ckan.py`，ERDDAP `allDatasets` source-level fetch/parse flow 已拆到 `api_launcher/crawlers/erddap.py`，NASA CMR collection query URL builder/payload parser/source-level fetch/parse flow/pagination flow 已拆到 `api_launcher/crawlers/cmr.py`，GBIF dataset search query URL builder/payload parser/source-level fetch/parse flow/pagination flow 已拆到 `api_launcher/crawlers/gbif.py`，Dataverse search query URL builder/payload parser/source-level fetch/parse flow/pagination flow 已拆到 `api_launcher/crawlers/dataverse.py`，Zenodo records query URL builder/payload parser/source-level fetch/parse flow/pagination flow 已拆到 `api_launcher/crawlers/zenodo.py`，DataCite `/dois` query URL builder/payload parser/source-level fetch/parse flow/pagination flow 已拆到 `api_launcher/crawlers/datacite.py`，OGC API Records query URL builder/FeatureCollection parser/source-level fetch/parse flow/pagination flow 已拆到 `api_launcher/crawlers/ogc_records.py`，Socrata catalog query URL builder/payload parser/source-level fetch/parse flow/pagination flow 已拆到 `api_launcher/crawlers/socrata.py`，OpenAlex Works query URL builder/payload parser/source-level fetch/parse flow/cursor pagination flow 已拆到 `api_launcher/crawlers/openalex.py`，HTML file index source-level fetch/parse flow 已拆到 `api_launcher/crawlers/html_index.py`，NCEI search query URL builder/payload parser/source-level fetch/parse flow/pagination flow 已拆到 `api_launcher/crawlers/ncei.py`。`dataset_sources.py` 目前主要保留 `SOURCE_CRAWLER_HANDLERS` dispatcher mapping、limit/search_terms 正規化與舊匯入相容；`SUPPORTED_DATASET_SOURCE_TYPES` 會給 portal intake 共用，避免同一份 crawler type 清單在不同地方手抄漂移。
- CLI handoff report 已補 portal intake / local discovery 摘要與進度焦點：`--handoff-report PATH` 現在會列出 generated time、manifest/asset/verification event 的最近驗證時間、從 `PROJECT_GTD.md` 解析出的 open GTD focus、portal intake rows/actionable/warnings/local provider seeds/local dataset sources，以及從 Markdown/Notion staging 進 local config，再經 crawler audit promote 到 catalog 的指令流。
- 第 1 項目前已調整為「善用 crawler 發現 provider/source 與 dataset candidates」，不要把每個代表資料集都硬寫成 Python adapter。`catalog/APIkeys_collection_catalog.json` 目前有 55 個 provider seed，新增方向包含 NOAA GOES-R on AWS、NOAA NOMADS、Marine Regions、GADM、OpenStreetMap Overpass、U.S. Census TIGERweb、EMODnet ERDDAP、Harvard Dataverse、Zenodo、DataCite、OpenAlex、WMO WIS2 Global Discovery Catalogue、Canada/UK/Australia/HDX CKAN、NYC/DataSF/Chicago Socrata portals，以及 optional/unofficial 的 `Yahoo Finance via yfinance`。`catalog/dataset_discovery_sources.json` 描述可爬的資料目錄，目前 23 個 source；`api_launcher/crawlers/orchestrator.py` 統一調度 source crawlers，並行執行、去重、收斂 per-source error/warning；`api_launcher/crawlers/fetch.py` 已放共用 HTTP fetch/JSON/URL helper；`api_launcher/crawlers/pagination.py` 已放共用 full-crawl page cap 與候選去重 append helper；各 source 模組已接手 query URL builder、payload parser、source-level fetch/parse flow 與 full-crawl pagination flow；DataCite DOI search 會用 public `/dois` API 與 `resource-type-id=dataset` 產生 metadata-first 候選，並只把明確 `contentUrl` 留作可審核 resource 線索；OpenAlex Works search 會用 `type:dataset` 產生研究資料 metadata 候選；WMO WIS2 source 會用 OGC API Records 產生天氣/觀測 metadata 候選；Socrata catalog crawler 會從 Catalog API 產生 resource 候選，刻意保留 `/api/views/{id}` metadata URL 與 bounded resolver 可用的 `/resource/{id}.json` metadata，不把整張表直接當 direct file。`api_launcher/crawlers/dataset_sources.py` 目前主要保留 dispatcher、limit/search_terms 正規化與舊匯入相容。Crawler 審核不能只看「沒報錯」：0 筆候選、低於 `min_expected_candidates`、只抓到全域重複候選、payload shape 不符、候選缺少 evidence/source url 都要提示或失敗。未來新增供應商時，優先新增/配置 crawler，由 orchestrator 調度；不要讓特殊網頁邏輯散進 UI 或 core。AIS 與衛星雲圖是代表測試案例：AIS 應由 MarineCadastre index 發現 shards，衛星雲圖應由 NOAA/NCEI/GOES-R/Earth Engine/STAC 類 catalog 發現 raster/grid 候選。
- Dataset candidates 現在有初步 review loop：repository 可列出/標記 candidate status，CLI 可用 `--list-dataset-candidates`、`--dataset-candidates-json`、`--review-dataset-candidate UID --dataset-candidate-decision approved|planned|rejected`，Tk UI 在 `資料庫 > 審核資料集候選` 可查看、開來源、標記可用/拒絕或加入目前下載計畫。主列表也會把 crawler 匯入的 dataset 顯示成 provider 底下的縮排列；`資料庫 > 在列表顯示 crawler 資料集` 可切換。這仍是 metadata-only registry 狀態，不會下載或改動資料本體。
- Crawler candidates 現在可以進一步輸出成後端 plan：CLI `--export-candidate-plan PATH --candidate-plan-status approved|needs_review|planned|all` 會把候選 dataset/version 轉成與 adapter 共用的 dataset-version plan schema。每個 entry 都有 `download_eligibility`、direct 檔案的 `target_path`、`dataset_version`、`candidate_review`，以及保守的 `import_plan`。CSV/JSON 類標成可在下載驗證後進 SQLite MVP importer；CSV.ZST/ZIP/TAR 類標成需要解壓或 adapter；API/landing page 保持 adapter review。UI 的候選加入下載計畫也改走 `provider_dataset_version_plan_entry()`，避免把入口頁當成 direct download。
- Socrata candidate-plan path 現在有明確 regression：crawler-style candidate -> `--export-candidate-plan` -> `resolve_adapter_review_plan_payload()` 會產生 bounded `$limit=25` direct sample，且 `tests/test_dataset_download_plan.py` 會檢查 import plan 是 `supported_after_download`。這保護的是「會列出資料集」到「能安全下載/匯入小樣本」的中間接縫。
- Tk UI 下載計畫已從 provider_id-only 購物車升級成 plan item key：provider-level row 還能用，但 candidate review 或 dataset version action 加入的是 `provider::dataset::dataset_uid::version` 這類 key。這代表同一資料商底下可以同時排多個資料集/版本，不會互相覆蓋。注意內部仍有一些 legacy dict 名稱叫 `*_by_provider`，短期其實是用 plan_key 當 key；後續若整理 UI state，先看 `selected_plan_items()` / `provider_id_for_plan_key()`。
- Tk UI 下方下載計畫面板現在可用「收合下載計畫 / 展開下載計畫」切換；收合只隱藏 cart/job table body，標題列、計畫名稱、項目數與開始/匯入/暫停/重試/移除/匯出等主要動作仍保留。這個切換不會取消背景下載 queue，也不改變 plan item state；後續 UI polish 不要把它誤寫成停止下載或清空計畫。
- Dataset-version plan entries 現在對 non-direct 或需解壓/轉換的項目會帶 `adapter_review` 區塊：`adapter_id`、`source_url`、`required_action`、`expected_output`、`reason`。這是後續 adapter-specific repair / non-direct adapter 的接手契約；不要再只靠 UI 字串「需 adapter」判斷下一步。
- `api_launcher/adapter_review.py` 會把 plan 裡的 `adapter_review` / adapter-required / unpack-needed entries 整理成 agent-readable queue。CLI 可用 `--adapter-review-plan PATH` 或加 `--adapter-review-json`；Tk UI 在 `資料庫 > Adapter 待辦` 與「更多 > Adapter 待辦」可查看目前下載計畫裡的待辦、來源 URL 與 required action。
- `api_launcher/adapter_plan_resolver.py` 是第一個 non-direct plan resolver：CLI `--resolve-adapter-plan INPUT --write-resolved-adapter-plan OUTPUT` 會掃描 CKAN/Data.gov/NCEI/CMR/STAC/Zenodo 類候選常見的 `dataset_version.metadata.resources` / `distribution` / `distributions` / `links` / JSON-LD `@graph`，也認得 `dcat:distribution` 這類 JSON-LD compact key，只把看起來已經是 direct file URL、或 resource metadata 明確標成 CSV/JSON/ZIP 等支援格式的 URL 提升成 direct download plan entry，並重建 `target_path`、`download_eligibility`、`import_plan`。泛用 resource reader 現在認得 `download_url`、`downloadURL`、`contentUrl`、`fileUrl`、`url`、`href` 等 direct-link 欄位，以及 `dcat:downloadURL`、`schema:contentUrl` 等命名空間欄位；欄位值可為字串、list 或 `{"@id": "..."}` 物件；格式提示可用 `mediaType`、`contentType`、`encodingFormat`、`dct:format`、`dcat:mediaType`，大小提示可用 `byteSize`、`contentSize`、`dcat:byteSize` 或 `{"@value": "..."}`；只有 `{"label": "CSV download"}` 這類純標籤物件不會被誤當成 direct URL。宣告超過 100 MB 的 resource 會留在 review，不自動下載。若 CKAN/Data.gov plan 只有 `package_show` URL，或只有 `package_search` URL 加 dataset id，resolver 也能只查一次單一 package metadata，再挑安全 direct resource；它不掃整個 CKAN catalog。ERDDAP candidate 若帶 `erddap_protocols`，會讀官方 `info/{dataset}/index.json`，產生最多 25 列/最小維度切片的 sample CSV plan entry，讓下載與 SQLite 匯入流程能先閉環；不要把這當成完整大量下載。Tk UI 已有 `資料庫 > 解析 Adapter 計畫`、上方 `更多 > 解析 Adapter 計畫`、以及 `Adapter 待辦 > 解析可下載 resources`。HTML、API selector、登入頁、`accessURL` 或未知格式仍留在 adapter review；這是 bounded plan rewrite，不是無頭亂爬整站。
- Resolver 與 download/import plan 現在會保留壓縮 JSON/GeoJSON 類 source format：`json.gz`、`jsonl.gz`、`ndjson`、`ndjson.gz`、`geojson.gz` 不再被簡化成 `gz` 或人工審查；若 resource metadata 或 URL 已明確提供格式，plan 會直接標成 `json_to_sqlite` 的 supported-after-download 路徑。這補上的是既有 JSON importer 已支援、但 resolver 先前沒有正確交接的格式缺口。
- `api_launcher/adapter_plan_resolver.py` 現在也能把 STAC collection candidate 轉成 bounded `limit=1` item-search GeoJSON plan entry。這只下載一小包 STAC item metadata，讓 `下載 -> manifest -> JSON/GeoJSON 匯入 SQLite` 先閉環；不會直接下載 Sentinel/Landsat/GOES 影像資產。為避免假安全，generic resource resolver 也會跳過 STAC `rel=items` 連結，不把未加 limit 的 items endpoint 當成 direct file。
- `api_launcher/adapter_plan_resolver.py` 現在也能把 NASA CMR collection candidate 轉成 bounded `page_size=1` granule metadata JSON plan entry。這只下載一筆 granule metadata，讓衛星/地球觀測來源先走通 JSON manifest/import 小閉環；不會把 `granules.json` 這類 API metadata 當成普通 direct file。若 plan 已經是單筆 CMR granule metadata，`cmr_granule_asset_link_resolver` 只查一次 CMR concept/granules JSON，從 JSON Feed `links` 裡挑明確 `data` / `download` / `enclosure` rel、格式可辨識、未宣告超過 100MB 的 direct asset link；NetCDF/HDF/GeoTIFF/GRIB 這類科學檔即使可下載，匯入 SQLite 仍會是 manual review。`metadata`、`documentation`、`browse`、`service`、`opendap`、`self` 等 rel 留在 review。這個 selector 目前只服務既有 `--resolve-adapter-plan` / Tk `解析 Adapter 計畫` 入口，不是新框架。
- `plans.py` 現在也會把 DataCite DOI / OpenAlex work 視為 research metadata landing/API record，先標成 `adapter_required`。白話說：DOI 像門牌，不是檔案；OpenAlex work 像研究記錄。DataCite crawler 若看到明確 `contentUrl`，會把它整理成 `resources`，讓既有 generic resolver 可以把清楚的 `.nc`、CSV、JSON 等檔案線索提升成 direct entry；若 plan 只有 DataCite DOI metadata，或 OpenAlex work 只有 DOI，`datacite_doi_content_url_resolver` 也可以只查一次 DataCite DOI API，再從 `contentUrl` 挑支援格式、未宣告超過 100MB 的 direct file。DOI landing page 或 repository HTML 頁仍留在 adapter review，不做網頁爬取。
- `api_launcher/adapter_plan_resolver.py` 現在也能把 Socrata/SODA v2-style resource 入口轉成 bounded `$limit=25` 樣本。支援 `/resource/abcd-1234.json`、`/resource/abcd-1234.csv`、`/resource/abcd-1234.geojson` 與 `/api/views/abcd-1234`；若原 URL 已有 `$select` 會保留，再補 `$limit=25`。泛用 direct-file resolver 會跳過 Socrata resource URL，避免 `.json` API 被誤當成完整可下載檔。SODA v3 token/query POST 形狀目前仍留在 adapter review。
- `api_launcher/adapter_plan_resolver.py` 現在也能把 NOAA/NCEI Common Access Search entry 轉成 bounded JSON metadata sample。若 plan 有 `/search/v1/datasets` 且 metadata 裡有 NCEI dataset id，會改成 `/search/v1/data?dataset=...&limit=25&offset=0`；若 plan 本來就是 `/search/v1/data`，會把 limit/offset 壓到 25/0。當 `/search/v1/data` query 已經有 dataset 加站點/框選/位置條件時，`ncei_search_data_file_resolver` 會先做一次 `limit=1&offset=0` metadata lookup；若第一筆結果提供 `/data/...` direct file path、CSV/JSON 等格式可辨識、且 `fileSize` 未超過 100MB，就提升成 direct file plan entry。若沒有站點/空間條件或檔案過大，仍只保存 Search JSON metadata sample，不下載 NOAA 原始資料檔。若 plan 已是 `/access/services/data/v1` Access Data query，只有同時具備 dataset、startDate、endDate、站點/框選/位置條件，且日期跨度不超過 7 天時，才會提升成 CSV/JSON 小樣本 direct entry；無邊界查詢會留在 adapter review。
- `api_launcher/adapter_plan_resolver.py` 現在也能把 Dataverse search candidate 轉成最新版本檔案 plan：若 candidate metadata 有 Dataverse persistent id / global id，resolver 只查一次 `/api/datasets/:persistentId/versions/:latest?persistentId=...`，從回傳 files 裡挑未 restricted、格式可支援、宣告大小不超過 100 MB 的檔案，產生 `/api/access/datafile/{id}` direct entries。這仍是 bounded metadata lookup + small direct file selection，不是掃整個 Dataverse，也不碰受限檔案。
- `api_launcher/importers/archive_importer.py` 是第一個 bounded transform adapter：`--run-download-plan ... --import-supported-plan-results` 遇到 `import_plan.status=requires_unpack_or_adapter` 的 ZIP/TAR，會在 manifest 健康後抽出第一個 CSV/CSV.GZ/JSON/JSON.GZ/JSONL/NDJSON/GeoJSON member，寫衍生 manifest 到 `state/extracted/`，再接既有 CSV/JSON SQLite importer。這不是任意猜測所有壓縮包語意，只是 MVP 安全通路。
- 金融/即時市場資料請記住：這不是一般「同版本就跳過」的靜態資料。`dataset_updates.py` 現在有 append-only / revisable / realtime time-series contract；金融 adapter 應保留 `event_time`、`received_at`、`ingest_run_id`，必要時保留 `revision`/`source_sequence`。MySQL 可做 MVP，重度 tick/回測資料優先考慮 TimescaleDB、ClickHouse、Parquet/DuckDB。時間序列的視覺化對標是 TradingView-like chart：K 線、成交量、指標、縮放拖曳、十字游標與即時更新，而不是只想 Taichi/Unreal 地球渲染。`Yahoo Finance via yfinance` 已加入 catalog 與 `YFinanceMarketDataAdapter`，但它必須維持非官方、optional、personal/research use，不能當商用授權資料源或 hard dependency。CLI `--write-yfinance-demo-plan state/yfinance_demo/plan.json --yfinance-symbol AAPL` 只寫離線 OHLCV CSV fixture plan，可用 `--run-download-plan ... --import-supported-plan-results` 驗證 manifest/import；`--write-yfinance-live-plan state/yfinance_live/plan.json --yfinance-symbol AAPL --yfinance-query-window daily_1mo --yfinance-storage-target auto --yfinance-retention-days 365 --yfinance-acknowledge-unofficial` 才會明確 opt-in 呼叫本機 optional `yfinance`，寫出 live CSV 與 file-backed import plan。`--yfinance-query-window` 只代表 chart-friendly period/interval 與 storage hint metadata，`--yfinance-storage-target` 只代表 SQLite/MySQL/Parquet-DuckDB/TimescaleDB/ClickHouse 等後續儲存目標 metadata，`--yfinance-retention-days` 只代表本機快取治理 metadata；三者都不會觸發自動刪檔、背景刷新、排程或資料庫寫入。若要審查儲存目標，用 `--write-yfinance-storage-review state/yfinance_live/storage_review.json --yfinance-storage-review-plan state/yfinance_live/plan.json`，它只寫 review JSON 與可選 dry-run SQL/Parquet-DuckDB 草稿，不連線、不建表、不匯入；若要把 review 轉成人類 / DBA 簽核材料，用 `--write-yfinance-storage-handoff state/yfinance_live/storage_handoff.md --yfinance-storage-handoff-review state/yfinance_live/storage_review.json`，它只寫 Markdown execution guard/checklist。Tk UI 目前在 `工具` 選單有離線 demo plan、live plan（需確認）與 `產生 yfinance 儲存審查 dry-run` 入口；前兩者只建立 plan 並加入下載計畫，storage review 入口只讀既有 plan 並寫 review JSON / handoff Markdown / dry-run SQL，不會自動下載、匯入、連線寫庫、背景排程或 crawler live call。CI 與測試不要直接打 Yahoo，後續也不要把它接成背景 crawler。同樣原則也適用 R 套件型來源、MATLAB toolbox/REST 入口，以及 Julia/Node/Java/.NET/Go/Rust 等其他語言生態：先把 PyPI、CRAN、Bioconductor、MATLAB Add-On、npm、Maven、NuGet、Go modules、crates.io 等解析成 canonical source 的 metadata evidence；同一資料庫/API 的 wrappers 取聯集合併到 `language_clients` / `access_surfaces`，不要因為 wrapper 或工具箱存在就新增 provider/source、引入新 runtime、商業授權依賴或背景 live call。
- 高能粒子對撞機等大型科學實驗資料請記住：這類是 event/array data，不是普通 SQL row store。SQL 可管 run ID、檔案索引、校準版本、provenance、manifest 與權限；raw data 優先保留 ROOT/HDF5/Parquet/Zarr/FITS/NetCDF 或物件儲存，再用 ROOT/uproot、DuckDB/Parquet、Dask/Spark、ClickHouse 等工具分析。
- 歷史建築/文化資產/多媒體資料請記住：這類常是 asset bundle，可能含照片、影片、音訊、3D mesh、點雲、BIM/IFC、材質貼圖與地理/年代/授權 metadata。SQL 管目錄與索引；raw asset 放檔案/物件儲存並用 manifest 記 checksum、LOD、座標系與依賴；viewer/render target 可是 Three.js、Cesium、Unreal、Blender 或 GLTF pipeline。

## 下一步優先事項

1. 收束 bounded API-query adapters 到 MVP 主線：CKAN package metadata lookup、Dataverse latest-version file lookup、ERDDAP sample resolver、STAC `limit=1` item metadata GeoJSON sample、NASA CMR `page_size=1` granule metadata sample、CMR granule explicit data-link selector、Socrata/SODA `$limit=25` sample、NOAA/NCEI Search `limit=25&offset=0` metadata sample、NOAA/NCEI Search data-file selector、NOAA/NCEI Access Data 有界小查詢、DataCite DOI `contentUrl` lookup 已先打通；DOI/OpenAlex landing/API record 若沒有 `contentUrl` 仍明確留在 adapter review。plan-driven import 重跑已先採「既有 table 預設略過、可選 rename 新表、明確 replace 才覆蓋」策略，且 UI 已有 keep/rename/replace 選擇；下一步優先做少量 crawler source 類型、擴大 guarded database repair 到更多明確擁有權案例，或做少量 UI polish，但每次都先通過「服務哪段 MVP、入口在哪、移除是否影響 MVP」三問。
2. 擴充 SQL/database self-check：per-asset SQL profile/schema 選擇、registry-only stop-tracking、manifest-backed missing SQLite table reimport、MySQL/PostgreSQL missing table dry-run SQL、精準 `can_auto_repair` 標記、以及 opt-in real MySQL/PostgreSQL driver smoke tests 已進 UI/JSON/測試；CI 也已有受控 service-container smoke，並覆蓋 registry-backed present/missing/schema drift table self-check。下一步只在 ownership、DBA review 與 rollback 邊界明確後，才實作 explicit opt-in SQL 執行流程；不要碰非測試表。
3. 繼續擴充 crawler source 類型，但要維持設定檔驅動；Dataverse/Zenodo/DataCite/OGC API Records/Socrata/OpenAlex 已有 metadata parser 與 pagination flow，下一批可評估更細的 NOAA/NCEI file/asset selector 或 DOI/repository resource resolver。
4. 新增 financial/time-series adapter contract，處理 live market data、append windows、revision/backfill、retention policy。
5. 新增 Marine Regions/VLIZ maritime boundaries adapter，支援領海、EEZ、爭議區、公海圖層。
6. Import policy UI 已有第一版：Tk guided import 現在可選 keep/rename/replace，預設仍是安全 rename，不覆蓋原資料；UI 會記住上一回策略並顯示在下載計畫面板。後續 polish 可改善文案或做 per-plan policy 顯示，但不要改掉 beginner-safe 預設。
7. 用 SQLite `dataset_asset_manifests` 做更廣義的 update/dedupe 決策；目前只完成同一 target 檔案的 manifest 重用。
8. 維護 `docs/AGENT_HANDOFF.zh-TW.md` 作為開發接力主入口；未來若要做 `.codex/skills/apikeys-collection-launcher`，應等 MVP 閉環穩定後再產品化成消費端/操作端技能。
9. 繼續減少 Tk UI 內的業務邏輯，讓 UI 主要負責呈現與觸發。
10. 繼續依 `docs/WORKSPACE_LAYOUT.zh-TW.md` 拆分大型 `.py`：短期 `dataset_sources.py` 已接近純 dispatcher；下一批可繼續拆 `core.py` 或在 crawler 端新增明確 dispatcher mapping，Tk UI 等 backend MVP 更穩後再重構。
11. 下一個中大型 crawler/adapter/UI/Hadoop/K8S 改動請開始走 OpenSpec change 流程，或至少在 `openspec/changes/` 留 proposal/tasks/acceptance criteria；小修不必硬開厚規格，但要保持 GTD/handoff 同步。

## 開發守則

- 每完成一個功能，要更新 `docs/PROJECT_GTD.md`。
- 每次跨機器或跨 Agent 接力，要更新這份 `docs/AGENT_HANDOFF.zh-TW.md`。
- 一輪對話可以包含多個實質 checkpoint commit；合理時可以把同一 MVP 主題下的相鄰小切片連續推進，但每個 commit 仍要可審查、可驗證、可由 CI 回溯。每次完成並推送實質 checkpoint 後，要追加 `docs/DEVELOPMENT_LOG.zh-TW.md`，記錄 commit、變更範圍、驗證、CI 與剩餘風險；但如果某個 commit 唯一目的只是同步開發日誌，不要再為該 log-sync commit 追加下一筆日誌，避免「更新日誌 -> push -> 再更新日誌」的遞迴。
- 新增、移動或重新定位文件時，要更新 `docs/DOCS_INDEX.zh-TW.md`；整理工作區或調整檔案責任時，要更新 `docs/WORKSPACE_LAYOUT.zh-TW.md`。
- 新增或修改非直覺程式邏輯時，要在相鄰位置留下維護註解，且本專案註解密度可以比一般專案略高，因為團隊成員不一定熟悉整個 codebase。維護註解預設使用繁體中文；檔名、CLI flag、API 名稱、標準與產品名可保留原文以免失準。註解尤其要補在函式目的、調度流程、安全 guard、schema/provenance 不變量、adapter 假設、外部 API 特例、跨模組 ownership 與資料轉換；註解要說明「為什麼」與「邊界」，不要只是重述程式碼。
- 新增英文文件或大幅更新英文文件時，要同步準備繁中版本、繁中摘要或繁中閱讀路線。
- 不要提交 `config/launcher_integrations.local.json`、`state/`、`downloads/`、`tem/`、真實 token、真實 API key。
- 不要把本機絕對路徑寫死在程式碼；路徑要走 `api_launcher/paths.py` 或 config。
- 預留端口不是死碼；但如果兩個模組表達同一件事，要優先合併抽象。
- 目錄整理規則：`api_launcher/downloads/` 放下載資格、queue、HTTP、staging、repair、transfer tools；`api_launcher/importers/` 放 CSV/JSON 匯入與 curation；根目錄只保留相容啟動入口。
- macOS 要注意 Tk、UTF-8、LF 換行、路徑大小寫與 `python3`/venv。特別注意不要讓 Windows 路徑（例如 `K:\...`）在 Mac startup checks 被當成錯誤；跨平台路徑應先依系統挑 `*_by_platform`，不符合本系統的 generic path 要忽略或降成 warning，不可阻擋 UI 啟動。
- `.gitignore` 裡 root runtime/暫存資料夾要寫成 `/state/`、`/downloads/`、`/tem/`，不要寫成 `downloads/` 這種會誤傷 `api_launcher/downloads/` 原始碼套件的規則。
- 專案在 macOS CloudMounter / 雲端同步碟上時，Python 讀寫預設 `__pycache__` 可能卡住；跑測試建議加 `PYTHONPYCACHEPREFIX=/tmp/apikeys_collection_pycache`。這次 full test 就是靠這個本機 pycache prefix 正常完成。
- 2026-05-20 Windows/RaiDrive：repo 內 `.venv` 的 pip 出現 `pip._vendor.rich` import error，`ensurepip` 與 `py -m pip --python .\.venv\Scripts\python.exe ...` 修復都會長時間卡住；不要在接力時硬重試。這輪改用本機磁碟 `C:\Users\lyn59\AppData\Local\APIkeys_collection\venv-py313` 安裝 `requirements-dev.txt`，已確認 full test 無 skipped。後續若要整理，建議重建 repo 內 `.venv` 或固定使用本機磁碟 venv，不要把大量 site-packages 寫在同步碟。
- Git object store 不適合長期放在 CloudMounter/雲端同步層；若 `git fsck` 出現 missing object 或 invalid reflog，先 `git fetch origin main` 嘗試補回。若仍壞，優先把 repo 重新 clone 到本機磁碟，再把工作區 patch 搬過去。
- 2026-05-19 macOS CloudMounter 曾把 `.git/refs/heads/main` 同步成 `.git/refs/heads/main 1`，導致 `git status` 顯示像是新 repo、`git pull` 報 `bad object refs/heads/main 1`。處理方式是先備份錯位 ref 到 `.git/ref-backups/`，用同一個 SHA 重建 `.git/refs/heads/main`，再把 `main 1` 移出 `refs/heads/`。這是 Git metadata 修復，不是源碼還原；修完後要跑 `git status --short --branch` 與 `git pull --ff-only origin main`。
- SQLite 短生命週期連線不要裸用 `with sqlite3.connect(...)`；那只處理 transaction，不會 close connection。用 `contextlib.closing(...)` 避免 Windows CI 檔案鎖。
- 每次 push 後，用 `gh run watch --exit-status` 追最新 CI；不要只以 push 成功判斷完成。
- 接力事故紀錄：2026-05-17 曾因把未提交的大型 `APIkeys_collection.py` 誤判為可丟棄內容而覆回 Git wrapper。下一位 Agent 遇到任何未提交、非預期、或看似「不符合文件」的大改動時，必須先備份或輸出 patch，再詢問/確認；不要直接 `git restore`、刪除或覆寫。

## 給下一位 Agent 的提示詞

```text
你正在接手 APIkeys_collection。請先讀 docs/AGENT_HANDOFF.zh-TW.md，再讀 docs/PROJECT_GTD.md。不要依賴上一段聊天紀錄。

先執行 git pull origin main、git status --short --branch、python3 -m unittest discover -s tests。本機 Codex/macOS 環境請優先用 conda env：conda run -n metal_trade_312 python -m unittest discover -s tests；不要把套件裝進 base/system Python。

push 後請用 gh run watch 追 CI。Windows 失敗時優先檢查 SQLite/file handle、路徑與 `.pyc` 鎖。SQLite 短生命週期連線要用 contextlib.closing。

目前第 1 項已經改成 crawler-first：provider/source discovery 找供應商與入口，dataset discovery sources 找資料集候選，adapter 只在 crawler 候選需要 bounded query/auth/transform/import 時才寫。請優先看 `catalog/dataset_discovery_sources.json`、`api_launcher/crawlers/types.py`、`api_launcher/crawlers/metadata.py`、`api_launcher/crawlers/fetch.py`、`api_launcher/crawlers/pagination.py`、`api_launcher/crawlers/ncei.py`、`api_launcher/crawlers/stac.py`、`api_launcher/crawlers/ckan.py`、`api_launcher/crawlers/erddap.py`、`api_launcher/crawlers/cmr.py`、`api_launcher/crawlers/gbif.py`、`api_launcher/crawlers/dataverse.py`、`api_launcher/crawlers/zenodo.py`、`api_launcher/crawlers/datacite.py`、`api_launcher/crawlers/ogc_records.py`、`api_launcher/crawlers/socrata.py`、`api_launcher/crawlers/openalex.py`、`api_launcher/crawlers/html_index.py`、`api_launcher/crawlers/orchestrator.py`、`api_launcher/crawlers/dataset_sources.py`、`api_launcher/cli_dataset_discovery.py`、`api_launcher/plans.py`、`api_launcher/adapter_review.py`、`api_launcher/adapter_plan_resolver.py`、`api_launcher/importers/archive_importer.py`。Crawler candidates 已能用 `--export-candidate-plan` 轉成 dataset-version download/import plan；Tk UI cart 也已從 provider_id 級別提升到 dataset_uid/version plan item；`import_plan` 也已接成下載後 guided import，並能在 cart/job table 顯示匯入狀態與 table hint；table 衝突會安全自動改名；non-direct/transform-needed plan entry 已帶 `adapter_review` handoff，CLI/UI 都能列出 Adapter 待辦；`--resolve-adapter-plan` 與 UI `解析 Adapter 計畫` 可先把 CKAN-like resources 裡的 direct file URL 提升成 direct entries，或在缺 resources 摘要時對 CKAN `package_show` 做單一 metadata lookup；也可把 Dataverse latest-version metadata 轉成未受限小檔 direct entries、把 ERDDAP metadata 轉成 bounded sample CSV entry、把 STAC collection 轉成 `limit=1` item metadata、把 CMR collection 轉成 `page_size=1` granule metadata，且 CMR granule links 會區分 metadata/service rel 與 explicit data/download/enclosure asset link、把 Socrata/SODA v2-style resource 轉成 `$limit=25` 小樣本、把 NOAA/NCEI Search entry 轉成 `limit=25&offset=0` metadata sample，並在有 dataset 加站點/空間條件時只查 1 筆 NCEI data metadata、把小於 100MB 的 `/data/...` CSV direct file 提升成下載項目，也能把已具備 dataset/date/spatial 邊界的 NOAA/NCEI Access Data query 轉成 CSV/JSON 小樣本；DataCite DOI/OpenAlex DOI 可只查一次 DataCite metadata 並把明確 `contentUrl` direct file 提升成下載項目；ZIP/TAR 壓縮包已有 bounded transform adapter。Database self-check UI 現在可針對單一 database/table asset 調整 `data_store_profile_id` / `schema_name`；UI/CLI 可停止追蹤該 asset，或對 manifest-backed missing SQLite table 做不覆蓋既有 table 的 guarded reimport。下一步重點是 import policy polish、擴大 guarded repair 覆蓋、或少量 crawler source 類型。AIS 與衛星雲圖是代表測試案例，但不要再把每個資料集硬寫成 Python 類別。使用者也希望未來往 OpenSpec-like workflow 靠攏：中大型變更先有簡短 proposal/tasks/acceptance，再實作與驗證，但目前不要因此拖慢 MVP。

若要整理工作區或拆大型 `.py`，先讀 `docs/WORKSPACE_LAYOUT.zh-TW.md`，再跑 `conda run -n metal_trade_312 python APIkeys_collection.py --workspace-inventory --write-workspace-inventory-json state/workspace_inventory.json`。這只產生盤點，不會搬檔；任何搬移/刪除前都要看 `git status --short` 並保護使用者/上一位 Agent 的未提交成果。

注意：SQL-only connection layer 已被合併到 api_launcher/data_store_connections.py，不要重新建立 sql_connection_profiles 或 sql_connections.py。

注意：未提交內容一律視為使用者或上一位 Agent 的成果。若檔案看似不符合目前架構，先備份/產生 patch 並說明風險，再決定是否收斂。

注意：專案開發策略已改往 OpenSpec-aligned workflow。中大型改動請先建立或更新規格/變更說明，再實作；若 GUI/CLI OpenSpec 工具尚未完成配置，至少先在 handoff/GTD/相關 docs 留下 proposal、tasks、acceptance criteria。不要回到純聊天記憶式開發。
```
