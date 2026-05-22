# 開發日誌

最後更新：2026-05-22

這份文件從 2026-05-21 起持續記錄開發歷史，並已依 GitHub Actions push run 反推回補 2026-05-17 以後的流水帳。它不是取代 `PROJECT_GTD.md` 或 `AGENT_HANDOFF.zh-TW.md`：GTD 管目前進度與下一步，handoff 管接力狀態，開發日誌管「每個版本怎麼走到現在、哪個點可當 checkpoint、還有什麼風險」。

時間以 GitHub Actions `createdAt` 轉為 Asia/Taipei (UTC+8) 分組。
日期區塊與同日內時間都採倒序排列：最近日期在最上方，同一天內最新 run 也在最上方。

## 標記規則

- `**CHECKPOINT**`：該 push 的 GitHub Actions 結論為 success，可作為回溯穩定點。
- `**CI 失敗**`：該 push 的 GitHub Actions 結論為 failure；保留在流水帳中，用來看見修復脈絡。
- 每筆使用表格欄位：`時間`、`標記`、`SHA`、`Run`、`原始標題`、`中文說明`。
- 日期區塊與同日內時間都倒序，讓最近期 checkpoint 一打開就能看到。

## 2026-05-17 至 2026-05-22 回補流水帳

### 2026-05-22

主線：完成 repo-wide 繁中維護註解工程，把註解規則落到所有 `.py` 檔，同步 GTD 狀態，定義 `tem/` 本機暫存區的 Git 與交接規則，補上可重複 MVP Demo Flow，抽出下載/匯入 pipeline slice，讓 UI 共用 demo 與匯入邊界，把 yfinance 收斂成可選非官方金融資料源、離線時間序列 Demo plan、明確 opt-in live CSV plan、保留天數、查詢視窗、儲存目標 metadata、storage review dry-run、Tk 工具入口與人類/DBA handoff，並讓 Tk 審查流程一次輸出 review JSON / dry-run SQL / handoff Markdown，將語言套件支援庫收斂成 canonical source metadata / access surface 關聯表，把 MySQL/PostgreSQL missing table 的 dry-run SQL 修復引導接到 CLI 與 Tk UI，並把「一輪對話可多個實質 checkpoint」的推進規則固化到 handoff/skill。

| 時間 | 標記 | SHA | Run | 原始標題 | 中文說明 |
| --- | --- | --- | --- | --- | --- |
| 11:26 | **CHECKPOINT** | `ba0b2e1` | `26266674074` | Add yfinance storage handoff to Tk review | 將 yfinance storage review 的 Tk dialog 擴充為一次產出 review JSON、必要時的 `.dry_run.sql` 與人類 / DBA 審查用 handoff Markdown。新增共用路徑 helper `yfinance_project_path_from_ui_text()`，讓 plan/review/handoff 三個輸出欄位都用同一個 project-root 基準，並在 UI 事件紀錄中加入 `handoff_path`、`dry_run=true` 與 `will_write_database=false`。同步 USER_GUIDE、USER_MANUAL、GTD、handoff 與 repo/local skill；本機驗證 `PYTHONPYCACHEPREFIX` 下的 `py_compile`、31 個 yfinance/UI 目標測試、408 個 unittest、`--summary` 與 `git diff --check`；CI Ubuntu、Windows、real DB smoke 全部成功。 |
| 11:15 | **CHECKPOINT** | `996cbce` | `26266329621` | Add yfinance storage handoff report | 新增 `--write-yfinance-storage-handoff ... --yfinance-storage-handoff-review ...`，可把 yfinance storage review JSON 轉成給人類 / DBA 審查的 Markdown。handoff 會列出 review JSON、target、engine、table、CSV 來源、symbols、dry-run SQL、execution guard、審查清單與下一步邊界，並拒絕非 `dry_run=true` 的 review payload；它仍只寫文件，不連線、不建表、不匯入、不代表批准執行。同步 USER_GUIDE、USER_MANUAL、GTD、handoff 與 repo/local skill；本機驗證 `PYTHONPYCACHEPREFIX` 下的 `py_compile`、30 個 yfinance/UI 目標測試、407 個 unittest、CLI handoff smoke、`--summary` 與 `git diff --check`；CI Ubuntu、Windows、real DB smoke 全部成功。 |
| 10:59 | **CHECKPOINT** | `89f637a` | `26265849867` | Add yfinance storage review UI entry | 把 yfinance storage review dry-run 接到 Tk `工具 > 產生 yfinance 儲存審查 dry-run`，UI 可讀取既有 plan 路徑、指定 review 輸出與審查目標，呼叫共用 adapter 產生 review JSON 與必要時的 `.dry_run.sql`。新增 `yfinance_storage_review_paths_from_ui()` helper，固定相對路徑基準並拒絕空路徑；事件紀錄明確寫入 `dry_run=true`、`will_write_database=false`。同步 USER_GUIDE、USER_MANUAL、GTD、handoff 與 repo/local skill，提醒後續 agent 這仍是人工/DBA 審查交接，不會連線、建表、匯入、背景抓取或接 crawler。驗證包含 `PYTHONPYCACHEPREFIX` 下的 `py_compile`、27 個 yfinance/UI 目標測試、404 個 unittest、CLI yfinance review smoke、`--summary` 與 `git diff --check`；CI Ubuntu、Windows、real DB smoke 全部成功。 |
| 10:40 | **CHECKPOINT** | `8d44e94` | `26265281226` | Add yfinance storage review dry-run | 替既有 yfinance plan 增加 `--write-yfinance-storage-review` 審查入口，可讀取 `--yfinance-storage-review-plan`，輸出 storage review JSON，並依 plan 內 storage target 或 `--yfinance-storage-review-target` 產生 MySQL、TimescaleDB/PostgreSQL、ClickHouse、Parquet/DuckDB 的 dry-run SQL/命令草稿。審查檔明確標記 `dry_run=true`、`will_write_database=false`、`requires_user_review=true`，launcher 不會連線、不會建表、不會匯入，也不會把 storage target metadata 當成自動執行。同步 USER_GUIDE、USER_MANUAL、GTD、handoff 與 repo/local skill；本機驗證 `py_compile`、25 個 yfinance/UI 目標測試、402 個 unittest、CLI smoke、`--summary` 與 `git diff --check`；CI Ubuntu、Windows、real DB smoke 全部成功。 |
| 10:12 | **CHECKPOINT** | `0f2e706` | `26264425447` | Document multi-checkpoint development turns | 依使用者要求，把「一輪對話可包含多個實質 checkpoint commit」固化到 handoff 與 repo/local launcher skill。規則改為：同一 MVP 主題下可連續推進多個相鄰小切片，但每個 commit 仍須可審查、可驗證、可由 CI 回溯；開發日誌要記錄每個已推送且驗證成功的實質 feature/fix/workflow/docs checkpoint，但 log-only commit 不再記錄，避免日誌遞迴。本輪為 workflow/docs checkpoint，`git diff --check` 通過；CI Ubuntu、Windows、real DB smoke 全部成功。 |
| 10:07 | **CHECKPOINT** | `83d69a1` | `26264291720` | Add yfinance storage target metadata | 替 yfinance opt-in live CSV plan 加入 metadata-only storage target profiles：CLI 新增 `--yfinance-storage-target`，Tk live dialog 新增「儲存目標」下拉選單，plan/source/dataset/time_series_contract 可記錄 `auto`、`sqlite_mvp_table`、`mysql_timeseries_table`、`parquet_duckdb_archive`、`timescaledb_hypertable`、`clickhouse_ohlcv_table` 等目標建議。這些 target 只作資料護照與後續匯出/匯入規劃，不會自動寫 MySQL、Parquet、TimescaleDB、ClickHouse，不會背景刷新、排程、下載或匯入。同步 USER_GUIDE、USER_MANUAL、GTD、handoff 與 repo/local skill；本機驗證 `py_compile`、22 個 yfinance/UI 目標測試、399 個 unittest、`--summary` 與 `git diff --check`；CI Ubuntu、Windows、real DB smoke 全部成功。 |
| 09:18 | **CHECKPOINT** | `36fa6c2` | `26262760724` | Add yfinance query window presets | 替 yfinance opt-in live CSV plan 加入 chart-friendly query window presets：CLI 新增 `--yfinance-query-window`，Tk live dialog 新增「查詢視窗」下拉選單，可把 `intraday_5d_5m`、`daily_1mo`、`daily_6mo`、`weekly_1y` 轉成 `period`/`interval`、`chart_profile` 與 `storage_hint` metadata。`period`/`interval` 手動覆寫會記為 `manual_override`；query-window 只作 chart/storage metadata，不會自動刷新、下載、匯入、排程或 crawler live call。同步 USER_GUIDE、USER_MANUAL、GTD、handoff 與 repo/local skill；本機驗證 `py_compile`、20 個 yfinance/UI 目標測試、397 個 unittest、`--summary` 與 `git diff --check`；CI Ubuntu、Windows、real DB smoke 全部成功。 |
| 08:15 | **CHECKPOINT** | `f81847a` | `26260743271` | Add yfinance retention metadata controls | 替 yfinance opt-in live CSV plan 加入 `--yfinance-retention-days`，CLI/Tk UI 可把保留天數寫入 plan/source/dataset metadata 與 time-series contract；保留政策只作本機快取治理提示，不會自動刪檔、背景刷新、下載、匯入或 crawler live call。同步 USER_GUIDE、USER_MANUAL、GTD、handoff 與 repo/local skill；本機驗證 `py_compile`、17 個 yfinance/UI 目標測試、394 個 unittest、`--summary` 與 `git diff --check`；CI Ubuntu、Windows、real DB smoke 全部成功。 |
| 04:53 | **CHECKPOINT** | `f31b481` | `26252519723` | Add yfinance plan actions to Tk UI | 把 yfinance 的離線 demo plan 與明確 opt-in live CSV plan 接到 Tk `工具` 選單。UI 只建立 plan 並加入下載計畫，後續仍由使用者按「開始」與「匯入」；live path 會要求 symbol/period/interval 與 unofficial personal/research 確認框，不會自動下載、背景排程、接 crawler 或在 CI 打 Yahoo。同步更新 USER_GUIDE、USER_MANUAL、GTD、handoff 與 repo/local skill；本機驗證包含 `py_compile`、16 個 yfinance/UI 針對性測試、393 個 unittest、`--summary` smoke 與 `git diff --check`，CI 的 Ubuntu、Windows 與 real DB smoke 全數成功。 |
| 04:29 | **CHECKPOINT** | `ecfaa2b` | `26251323191` | Document data source access surfaces | 將 yfinance 延伸出的概念收斂成 `canonical source` metadata 模型：語言套件、REST、CLI、toolbox 與 database driver 不再各自變成 provider/source，而是以 `來源 / 語言或 runtime / 套件或工具名稱` 的關聯表掛到同一個背後資料庫/API。文件明確要求多語言 wrapper 取聯集合併，API key 不因公開套件而公開，adapter 的價值是把 JSON/CSV/DataFrame/SDMX/OData/paged/archive 等輸出轉成 manifest、checksum、schema/provenance、可匯入資料庫與可修復 registry record。同步更新 platform concepts、discovery notes、GTD、handoff 與 repo/local skill；本輪為文件/skill checkpoint，`git diff --check` 通過，CI 的 Ubuntu、Windows 與 real DB smoke 全數成功。 |
| 04:11 | **CHECKPOINT** | `1b11b57` | `26250412357` | Add opt-in yfinance live plan | 新增 `--write-yfinance-live-plan` 與 `--yfinance-acknowledge-unofficial`，讓使用者可明確 opt-in 呼叫本機選用 `yfinance`，把 live OHLCV 結果寫成本機 CSV，再產生 file-backed download/import plan；此路徑保留非官方、personal/research-only 警告，不把 yfinance 做成 hard dependency，不接 crawler/background/CI live call。`api_launcher/adapters/yfinance.py` 補上 period/interval 驗證、time-series contract、CSV 欄位正規化、fake fetcher 測試入口與 plan metadata；CLI、USER_GUIDE、USER_MANUAL、架構/關聯圖、GTD、handoff 與 skill 同步更新。驗證包含 `py_compile`、391 個 unittest、yfinance adapter fixture/mock 測試、`git diff --check`，CI 的 Ubuntu、Windows 與 real DB smoke 全數成功。 |
| 03:41 | **CHECKPOINT** | `10e3ea7` | `26248941703` | Add Tk SQL repair dry-run action | 將 MySQL/PostgreSQL manifest-backed missing table 的 dry-run SQL 產生接到 Tk `工具 > 修復 / 驗證資產` 的資料庫分頁，新增「產生 dry-run SQL」按鈕、輸出路徑顯示、成功事件紀錄與防誤用提示；路徑正規化抽成 `database_repair_sql_path_for_asset()`，讓 CLI/UI 共用同一個檔名 guard。此動作仍只寫 `state/database_repair/*.dry_run.sql`，不連線、不執行 SQL、不修改 registry。同步更新 USER_GUIDE、failure modes、TECH_STACK、GTD、handoff 與 repo/local skill；本機驗證包含 `py_compile`、52 個 database repair/self-check/UI 測試、387 個 unittest、`git diff --check`，CI 的 Ubuntu、Windows 與 real DB smoke 全數成功。 |
| 03:22 | **CHECKPOINT** | `5b81689` | `26248005108` | Add SQL repair dry-run generation | 新增 `--write-database-repair-sql ASSET_ID`，讓 manifest-backed missing MySQL/PostgreSQL table 可產生 `state/database_repair/*.dry_run.sql` 供人工審核；此路徑只寫 SQL 檔，不連線、不執行 DDL/DML、不修改遠端資料庫或 registry。`--self-check-databases-json` 也會在安全條件成立時標示 `sql_dry_run_available=true`。同步更新 USER_GUIDE、failure modes、GTD、handoff 與 repo/local skill；本機驗證包含 `py_compile`、47 個 database repair/self-check 測試、384 個 unittest、`git diff --check`，CI 的 Ubuntu、Windows 與 real DB smoke 全數成功。 |
| 03:03 | **CHECKPOINT** | `e4bd0a6` | `26247067553` | Add optional yfinance demo adapter | 新增 `Yahoo Finance via yfinance` provider seed、`YFinanceMarketDataAdapter` query-template contract，以及 `--write-yfinance-demo-plan` 離線 OHLCV CSV fixture plan。這條金融時間序列 Demo 可用既有 direct downloader 產生 manifest 並匯入 SQLite，保留 `event_time`、`symbol`、`received_at`、`ingest_run_id`、`revision` 等欄位；同時明確不把 `yfinance` 做成 hard dependency、不在 CI 打 Yahoo、不把 Yahoo Finance 資料視為商用可再散布來源。同步更新 catalog、使用手冊、架構/關聯圖、GTD、handoff 與 skill；本機驗證包含 25 個針對性測試、381 個 unittest、adapter discovery smoke、yfinance 離線下載匯入 smoke、`py_compile` 與 `git diff --check`，CI 的 Ubuntu、Windows 與 real DB smoke 全數成功。 |
| 02:38 | **CHECKPOINT** | `40ddb4b` | `26245778018` | Add UI MVP demo flow entry | 讓 Tk UI 新增 `工具 > 產生 MVP Demo Flow` 與上方 `更多 > 產生 MVP Demo Flow`，直接呼叫共用的 `api_launcher.mvp_demo`，寫出 `state/mvp_demo/*` 並把離線 direct plan 加入下方下載計畫；UI 不自動下載或匯入，仍由使用者明確按「開始」與「匯入」。同步更新使用手冊、交接、GTD 與 skill，並把 `Yahoo Finance via yfinance` 記為後續可選、非官方、personal/research 用途的金融 adapter 候選；本機驗證包含 5 個針對性測試、375 個 unittest、`py_compile` 與 `git diff --check`，CI 的 Ubuntu、Windows 與 real DB smoke 全數成功。 |
| 02:22 | **CHECKPOINT** | `da0f4d8` | `26244973496` | Route UI plan imports through pipeline slice | 讓 Tk UI 的 `匯入可支援下載結果` 改走 `api_launcher/ingestion_pipeline.py` 的 `run_existing_download_import_slice()`，把已下載 manifest 驗證、downloaded asset 登錄、SQLite 匯入、逐項狀態與 rename table 規則收進共用 service，不再在 `launcher_ui.py` 內重寫一套匯入 loop；本機驗證包含 15 個針對性測試、375 個 unittest、`py_compile` 與 `git diff --check`，CI 的 Ubuntu、Windows 與 real DB smoke 全數成功。 |
| 01:55 | **CHECKPOINT** | `ffa9f87` | `26243591715` | Add download import pipeline slice | 新增 `api_launcher/ingestion_pipeline.py` 作為 direct plan 的下載/匯入流程切片，讓 `core.py --run-download-plan` 透過同一個 service 執行下載、manifest 登錄、支援格式匯入、blocked next_action、stage 分類與 CLI 摘要渲染；本機驗證包含 15 個針對性測試、374 個 unittest、`py_compile` 與 `git diff --check`，CI 的 Ubuntu、Windows 與 real DB smoke 全數成功。 |
| 01:36 | **CHECKPOINT** | `73c2220` | `26242596720` | Add canonical MVP demo flow | 新增 `--write-mvp-demo-flow` 與 `api_launcher/mvp_demo.py`，可產生固定 flow manifest、Socrata adapter review plan、離線 JSON fixture 與離線 direct plan；本機驗證包含 adapter 解析、離線下載、manifest 驗證、SQLite 匯入、372 個 unittest、`py_compile` 與 `git diff --check`，CI 的 Windows、Ubuntu 與 real DB smoke 全數成功。 |
| 01:05 | **CHECKPOINT** | `7e7387f` | `26240992737` | Guide blocked download plans | 收束下載計畫的失敗閉環：`--run-download-plan` 現在會輸出 `skip_summary` 與 `next_action`，Tk UI 在沒有可直接下載項目時會引導使用者前往 Adapter 待辦或解析 Adapter 計畫。 |
| 00:50 | **CHECKPOINT** | `cacbffe` | `26240183046` | Document crawler asset concept | 將「爬蟲資產 / Crawler Asset」定位寫入平台概念、產品定位、探索筆記與架構文件，明確把它視為受治理的資料取得能力，而不是立刻新增大 registry。 |
| 00:37 | **CHECKPOINT** | `04a4644` | `26239536548` | Document local tem staging folder | 將 `tem/` 的用途寫入 `WORKSPACE_LAYOUT`、`AGENT_HANDOFF` 與 `DOCS_INDEX`：它是本機暫存區、已被 Git 忽略，團隊協作者與 CI 看不到內容；若暫存素材要變成正式資產，必須提升到 canonical docs/source 後再提交。 |
| 00:34 | **CHECKPOINT** | `8b61c2c` | `26239356382` | Ignore local tem staging folder | 將 `/tem/` 加入 `.gitignore`，並同步 repo/local Codex skill，明確禁止未經使用者要求就 `git add`、commit 或 push `tem/` 內容，也禁止讓正式流程依賴 `tem/` 路徑。 |
| 00:07 | **CHECKPOINT** | `1b8f8db` | `26237944941` | Add repo-wide Chinese maintainer comments | 完成全 repo Python 註解工程：正式模組、Tk UI、scripts、renderer helper 與 tests 都補上繁中維護/測試意圖註解；本機驗證包含註解覆蓋檢查、AST 語法解析、`git diff --check` 與 368 個 unittest，CI 的 Ubuntu、Windows 與 real DB smoke 也成功。 |

### 2026-05-21

主線：補 heartbeat automation 與 Codex runner，串 library repair actions，收斂 Tk 啟動可見性，補程式關聯圖、Demo/使用者手冊、Mermaid 繁中規則、README.zh-TW、文件整理規則，並修正 resolver 對壓縮 JSON/GeoJSON 類資源格式的交接。

| 時間 | 標記 | SHA | Run | 原始標題 | 中文說明 |
| --- | --- | --- | --- | --- | --- |
| 22:40 | **CHECKPOINT** | `1c6e2b0` | `26233013484` | Preserve compressed JSON resource formats | 保留壓縮 JSON/GeoJSON/NDJSON 類 resource format，讓 `json.gz`、`jsonl.gz`、`ndjson.gz`、`geojson.gz` 等既有 importer 支援格式能正確進入下載與匯入計畫。 |
| 21:57 | **CHECKPOINT** | `da35451` | `26230599073` | Consolidate docs refactor workflow | 收攏文件整理流程與繁中入口，並同步 repo/local Codex skill 的文件重構規則。 |
| 21:30 | **CHECKPOINT** | `98c1ba0` | `26229130535` | Document Mermaid flow conventions | 把繁中 Mermaid 圖說規則文件化，要求繁中 `.md` 的可見節點與箭頭以中文為主。 |
| 21:27 | **CHECKPOINT** | `a525a33` | `26228924048` | Map program flows and demo documentation | 補上程式關聯圖與 Demo/操作文件，讓模組調度、Demo 閉環與使用路徑更容易接手。 |
| 21:13 | **CHECKPOINT** | `8236fac` | `26228172868` | Polish Tk startup presentation | 收斂 Tk UI 啟動後的顯示、置前與 focus 行為，改善 IDE 或背景 shell 啟動時看不到視窗的問題。 |
| 08:47 | **CHECKPOINT** | `dde1eed` | `26198656901` | Connect library repair actions to suggestions | 把 library repair actions 接到既有修復建議，讓 UI/agent 不必重建修復判斷邏輯。 |
| 08:18 | **CHECKPOINT** | `69dd22e` | `26197671241` | Add scheduled Codex heartbeat runner | 新增可由排程呼叫本機 Codex CLI 的 runner 入口，讓安全檢查通過後能自動推進下一步。 |
| 08:07 | **CHECKPOINT** | `5a6c539` | `26197318657` | Add heartbeat command wrappers | 新增 Windows 友善的 heartbeat `.cmd` wrapper，避免 PowerShell Execution Policy 擋住 `.ps1` 入口。 |
| 00:21 | **CHECKPOINT** | `c2f426a` | `26175532616` | Fix heartbeat planner JSON serialization | 修正 heartbeat planner 產生 JSON 時的循環參照問題，讓 plan payload 可被 CI 與外部工具穩定讀取。 |
| 00:15 | **CI 失敗** | `102994f` | `26175194234` | Add heartbeat automation entrypoints | 新增 heartbeat automation 的 CLI 與接力入口，作為排程推進的第一版實作；這筆當時 CI 失敗，後續修正 planner JSON 序列化。 |

### 2026-05-20

主線：強化 resolver resource metadata 判讀、UI import policy、archive import 格式、database repair UI/CLI、real MySQL/PostgreSQL smoke、event logs、handoff report 與資料資產平台文檔。

| 時間 | 標記 | SHA | Run | 原始標題 | 中文說明 |
| --- | --- | --- | --- | --- | --- |
| 23:30 | **CHECKPOINT** | `86ad74e` | `26172676367` | Log UI repair requeue events | 讓 Tk repair panel 的 requeue 操作寫入 event log，記錄 queued/blocked/failed 等結果。 |
| 23:10 | **CHECKPOINT** | `a929633` | `26171557234` | Log download manifest verification summaries | 讓下載 manifest verification 寫入結構化 event log，方便 handoff 與 UI/agent 追蹤檔案健康。 |
| 23:00 | **CHECKPOINT** | `b961e57` | `26171027033` | Enrich handoff report progress context | 擴充 handoff report 的進度上下文，加入 GTD focus、manifest/asset/verification timestamps 等資訊。 |
| 22:33 | **CHECKPOINT** | `d0e940d` | `26169451239` | Ignore Spectra local artifacts | 把 Spectra/OpenSpec GUI 的本機 artifact 加入忽略規則，避免開發工具產物被誤提交。 |
| 22:17 | **CHECKPOINT** | `dc985fa` | `26168517850` | Add database registry repair CLI | 新增 database registry repair CLI，讓 agent 可執行 stop-tracking 或 guarded reimport 並輸出 JSON。 |
| 21:32 | **CHECKPOINT** | `3fdb7b0` | `26165912750` | Update handoff for agent transfer | 更新 agent handoff，記錄當前驗證、CI 與下一步，支援跨機器/跨 Agent 接力。 |
| 21:21 | **CHECKPOINT** | `12419bb` | `26165313576` | Cover real DB schema drift smoke | 讓 real DB smoke 覆蓋 schema drift，透過受控 ALTER 驗證 fingerprint drift 能被偵測。 |
| 15:39 | **CHECKPOINT** | `cfe6999` | `26148529063` | Cover registry-backed real DB self-check | 讓 real DB smoke 覆蓋 registry-backed table self-check，確認 present/missing 狀態。 |
| 15:27 | **CHECKPOINT** | `908b15a` | `26148007327` | Run real database smoke in CI | 在 GitHub Actions 加入 disposable MySQL/PostgreSQL service containers，讓真實 driver smoke 可在 CI 跑。 |
| 15:18 | **CHECKPOINT** | `ffbd07f` | `26147585557` | Add opt-in real database smoke tests | 新增 opt-in 真實 MySQL/PostgreSQL smoke tests，預設跳過，只有設定 env vars 與 driver 時才連線。 |
| 15:08 | **CHECKPOINT** | `0862d25` | `26147163057` | Mark safe database repair suggestions | 讓 database repair suggestion 精準標記哪些情況可以自動修復，降低誤操作風險。 |
| 14:58 | **CHECKPOINT** | `08c6dc6` | `26146744743` | Cover tar geojson archive imports | 補上 TAR.GZ 內 GeoJSON.GZ 匯入測試，確認 archive transform 能處理 GIS JSON 類資料。 |
| 14:44 | **CHECKPOINT** | `510e2b4` | `26146150793` | Expand archive import member formats | 擴充 ZIP/TAR archive importer 可抽出的 member 格式，讓壓縮包能接既有 SQLite 匯入路徑。 |
| 14:29 | **CHECKPOINT** | `8d6333a` | `26145565066` | Preserve compound source formats | 保存 compound source format，例如 csv.gz、jsonl、geojson.gz、zip、tar.gz，避免 provenance 被簡化成 unknown。 |
| 14:16 | **CHECKPOINT** | `9435894` | `26145046980` | Expand guarded SQLite reimport formats | 擴充 SQLite guarded reimport 支援格式，納入更多 CSV/JSON/JSONL/GeoJSON 變體。 |
| 14:06 | **CHECKPOINT** | `81a26ee` | `26144697993` | Update handoff after import preference CI | 在 UI 匯入偏好測試通過後更新 handoff，保存驗證結果與接手狀態。 |
| 14:04 | **CHECKPOINT** | `c903db4` | `26144606542` | Remember UI import policy preference | 讓 UI 記住匯入策略偏好，減少使用者每次重選的摩擦。 |
| 13:50 | **CHECKPOINT** | `65cb251` | `26144124360` | Update handoff after import policy CI | 在 import policy CI 通過後更新 handoff，讓下一位 Agent 知道該切片已驗證。 |
| 13:48 | **CHECKPOINT** | `aca3de5` | `26144029986` | Add UI import policy selection | 讓 UI 可選擇匯入策略，為 keep/rename/replace 類操作提供明確入口。 |
| 08:49 | **CHECKPOINT** | `27dbce9` | `26134376662` | Add safe rename policy for plan imports | 新增 plan import 的安全改名策略，遇到既有 table 時建立新表而不是覆蓋。 |
| 08:19 | **CHECKPOINT** | `b9167a3` | `26133399043` | Install numpy for dev test coverage | 在開發測試環境補上 numpy，讓 renderer-light 或相關測試覆蓋可執行。 |
| 08:01 | **CHECKPOINT** | `9a79a6f` | `26132764678` | Read JSON-LD graph resource metadata | 讓 resolver 能讀取 JSON-LD `@graph` 包裝中的 resource metadata，避免漏掉嵌套下載線索。 |
| 07:47 | **CHECKPOINT** | `1231457` | `26132254701` | Support namespaced DCAT resource metadata | 支援帶 namespace 的 DCAT/schema.org resource metadata，例如 `dcat:downloadURL` 與 `schema:contentUrl`。 |
| 04:24 | **CHECKPOINT** | `077989c` | `26123107780` | Read distribution metadata in adapter resolver | 讓 adapter resolver 讀取 distribution 類 metadata，以便從資料目錄中找出可審核下載資源。 |
| 02:12 | **CHECKPOINT** | `d8c6b18` | `26116211720` | Update CI actions for Node 24 | 更新 GitHub Actions 官方 action 版本，消除 Node 24 相關相容性風險。 |
| 02:06 | **CHECKPOINT** | `91cd635` | `26115924978` | Add APIkeys collection Codex skills | 新增 APIkeys_collection 專案 Codex skills，讓開發與操作工作有固定接手規則。 |
| 01:41 | **CHECKPOINT** | `1f6f90d` | `26114595344` | Recognize common resource download metadata keys | 擴充 resolver 對常見下載 metadata 欄位的辨識，例如 downloadURL、contentUrl、fileUrl 等。 |
| 01:30 | **CHECKPOINT** | `672bfa4` | `26114036790` | Skip existing tables on plan import reruns | 讓 plan-driven import 重跑時預設跳過已存在 table，避免把重跑視為失敗或覆蓋資料。 |
| 01:13 | **CHECKPOINT** | `79cd466` | `26113102560` | Document data asset platform concepts | 補充資料資產平台概念，記錄 Discovery Tool、lakehouse/K8S、Render Studio、ML asset 與 connector 路線。 |
| 00:43 | **CHECKPOINT** | `8a0d422` | `26111524365` | Reimport missing SQLite tables from manifests | 讓缺失的 SQLite table 可從健康 manifest 重新匯入，並維持不覆蓋既有表的安全 guard。 |
| 00:28 | **CHECKPOINT** | `a7f19a9` | `26110723509` | Let repair UI stop tracking database assets | 讓修復 UI 可 registry-only 停止追蹤指定 database/table asset，不執行 SQL 或刪檔。 |
| 00:12 | **CHECKPOINT** | `b3363e0` | `26109863663` | Let repair UI adjust database asset profiles | 讓修復 UI 可調整 database/table asset 的 profile/schema metadata，為多資料庫自檢做準備。 |
| 00:01 | **CHECKPOINT** | `4f2aafe` | `26109254273` | Resolve DataCite DOI content URLs narrowly | 讓 DataCite DOI 只在明確 `contentUrl` 且格式/大小安全時轉成 direct plan，避免把 DOI landing page 當檔案下載。 |

### 2026-05-19

主線：重構 crawler 模組，補 pagination/fetch/query helper，擴充 DataCite、OGC API Records、Socrata、OpenAlex、STAC、CMR、NCEI、Dataverse 等 crawler/resolver，並導入 OpenSpec workflow。

| 時間 | 標記 | SHA | Run | 原始標題 | 中文說明 |
| --- | --- | --- | --- | --- | --- |
| 23:43 | **CHECKPOINT** | `c5954c1` | `26108195045` | Resolve bounded NCEI search data files | 讓 NCEI Search data file 只在 dataset 加站點/空間條件且小於上限時提升為 direct file。 |
| 23:28 | **CHECKPOINT** | `13972f9` | `26107326025` | Resolve CMR granule data links narrowly | 讓 CMR granule data/download/enclosure links 只在格式與大小安全時提升為 direct asset。 |
| 23:06 | **CHECKPOINT** | `3f1eed7` | `26106052749` | Handle DataCite contentUrl resources | 讓 DataCite crawler 交出的 `contentUrl` resources 可被 generic resolver 安全判讀。 |
| 22:48 | **CHECKPOINT** | `7e30ff0` | `26104948281` | Guard CMR metadata links in adapter resolver | 在 CMR resolver 中保護 metadata/service/browse/opendap links，避免誤當 direct asset。 |
| 16:41 | **CHECKPOINT** | `d342677` | `26086226444` | Keep OGC metadata links in adapter review | 讓 OGC metadata/navigation links 留在 adapter review，只有明確 data/download link 才可能提升。 |
| 16:23 | **CHECKPOINT** | `005edd2` | `26085383980` | Keep OGC broker links out of primary API URLs | 避免把 OGC/WIS2 broker 或 notification link 當成 primary HTTP API URL。 |
| 16:07 | **CHECKPOINT** | `a455e47` | `26084647609` | Add WMO WIS2 OGC records source | 新增 WMO WIS2 Global Discovery Catalogue 作為 OGC API Records 真實 smoke source。 |
| 15:45 | **CHECKPOINT** | `95fd110` | `26083601605` | Support CMR feed entry JSON imports | 讓 JSON importer 支援 NASA CMR `feed.entry` 結構，能把 granule metadata 匯入 SQLite。 |
| 15:10 | **CHECKPOINT** | `478a261` | `26082086854` | Add bounded CMR granule sample resolver | 新增 CMR collection -> `page_size=1` granule metadata sample resolver。 |
| 14:32 | **CHECKPOINT** | `20e0d79` | `26080506526` | Adopt OpenSpec workflow tooling | 導入 OpenSpec workflow tooling，為中大型變更建立 proposal/tasks/acceptance 的工作流。 |
| 13:25 | **CHECKPOINT** | `b164194` | `26078095042` | Add Dataverse candidate file resolver | 新增 Dataverse candidate file resolver，對 persistent id 做單次 latest-version lookup 並挑安全小檔。 |
| 12:14 | **CHECKPOINT** | `cfcecd8` | `26075781921` | Add OpenAlex dataset discovery crawler | 新增 OpenAlex Works dataset crawler，從研究 metadata 產生 dataset candidates。 |
| 11:36 | **CHECKPOINT** | `7a33062` | `26074628076` | Add bounded NCEI access data resolver | 新增 NCEI Access Data 有界查詢 resolver，要求 dataset/date/spatial 等條件才產生小樣本。 |
| 11:08 | **CHECKPOINT** | `e22740d` | `26073749709` | Cover Socrata candidate plan resolution | 補上 Socrata candidate -> bounded plan 的測試/覆蓋，確認不會做 unsafe full-table download。 |
| 10:55 | **CHECKPOINT** | `b54534d` | `26073331125` | Add Socrata catalog dataset crawler | 新增 Socrata catalog crawler，從城市/open data portal 找出 resource candidates。 |
| 09:59 | **CHECKPOINT** | `2da6882` | `26071556561` | Add OGC API Records dataset crawler | 新增 OGC API Records crawler，支援 WIS2 等 records catalog 的 metadata candidates。 |
| 09:30 | **CHECKPOINT** | `854af3f` | `26070617504` | Clarify handoff checkpoint reference | 釐清 handoff checkpoint 引用方式，避免下一位 Agent 依賴過期聊天紀錄。 |
| 09:27 | **CHECKPOINT** | `919f24b` | `26070538931` | Update handoff checkpoint | 更新 handoff checkpoint，記錄當前 crawler/resolver 進度與驗證狀態。 |
| 08:34 | **CHECKPOINT** | `d0b3ca8` | `26068790700` | Add NCEI bounded search resolver | 新增 NOAA/NCEI Search bounded resolver，把 search candidate 轉成小型 metadata sample。 |
| 08:17 | **CHECKPOINT** | `199b94e` | `26068208282` | Add Socrata bounded sample resolver | 新增 Socrata/SODA bounded sample resolver，把 resource/API metadata 轉成 `$limit=25` 小樣本。 |
| 07:40 | **CHECKPOINT** | `c1b1719` | `26066899140` | Add CKAN bounded package resolver | 新增 CKAN package_show bounded resolver，只做單次 metadata lookup 並提升安全 direct resources。 |
| 07:27 | **CHECKPOINT** | `01f6ae0` | `26066406408` | Centralize crawler source registry | 集中 crawler source registry，讓 supported source types 與 dispatcher 對齊。 |
| 07:11 | **CHECKPOINT** | `ece3043` | `26065821569` | Add DataCite dataset crawler | 新增 DataCite DOI search crawler，產生 metadata-first dataset candidates。 |
| 06:56 | **CHECKPOINT** | `0d0120a` | `26065239194` | Move crawler source fetch flows | 把 source-level fetch/parse flows 移出 dispatcher，讓 `dataset_sources.py` 更接近純註冊表。 |
| 06:44 | **CHECKPOINT** | `c7dd6c6` | `26064775791` | Extract crawler query URL helpers | 拆出 crawler query URL builder helper，讓 source-specific 查詢 URL 組裝集中管理。 |
| 04:21 | **CHECKPOINT** | `81285fd` | `26058221654` | Update crawler pagination docs | 更新 crawler pagination 文件，記錄各 source crawler 的分頁責任與安全邊界。 |
| 04:18 | **CHECKPOINT** | `4fae862` | `26058098589` | Extract NCEI pagination flow | 把 NOAA/NCEI pagination flow 拆出，讓 Search API full crawl 有清楚上限與去重規則。 |
| 04:11 | **CHECKPOINT** | `7244209` | `26057753176` | Extract Zenodo pagination flow | 把 Zenodo records pagination flow 拆出，讓 Zenodo crawler 的分頁與解析分工清楚。 |
| 04:05 | **CHECKPOINT** | `3b05a2b` | `26057447812` | Extract Dataverse pagination flow | 把 Dataverse pagination flow 拆出，讓 Dataverse search crawler 可獨立演進。 |
| 04:00 | **CHECKPOINT** | `509025e` | `26057191504` | Extract GBIF pagination flow | 把 GBIF dataset search pagination flow 拆出，降低 GBIF crawler 與 dispatcher 耦合。 |
| 03:54 | **CHECKPOINT** | `eedbcb6` | `26056912411` | Extract CKAN pagination flow | 把 CKAN pagination flow 拆出，統一 package_search 類 source 的分頁處理。 |
| 03:49 | **CHECKPOINT** | `8beb6d6` | `26056658366` | Extract CMR pagination flow | 把 NASA CMR pagination flow 拆出，讓 CMR collection/granule 抓取更容易維護。 |
| 03:43 | **CHECKPOINT** | `e77f873` | `26056377268` | Extract STAC pagination flow | 把 STAC pagination flow 拆出，讓 STAC crawler 的多頁抓取邏輯獨立可測。 |
| 03:34 | **CHECKPOINT** | `23ce25a` | `26055903367` | Extract crawler pagination helpers | 把 full-crawl page cap 與候選去重 append helper 拆出，統一各 crawler 的分頁邊界。 |
| 03:28 | **CHECKPOINT** | `92d41e0` | `26055610460` | Extract crawler fetch helpers | 把 crawler 共用 HTTP fetch、JSON validation 與 URL helper 拆出，降低 source crawler 重複碼。 |

### 2026-05-18

主線：把下載結果推進到 CSV/JSON SQLite 匯入，記錄 resident/mobile/P2P/Hadoop/K8S 路線，建立 crawler-first dataset discovery、candidate review、plan import、adapter review queue 與 bounded resolver。

| 時間 | 標記 | SHA | Run | 原始標題 | 中文說明 |
| --- | --- | --- | --- | --- | --- |
| 20:33 | **CHECKPOINT** | `545a2f0` | `26033730560` | Extract NCEI crawler parser | 拆出 NCEI crawler parser，讓 NOAA/NCEI Search payload parsing 可獨立測試。 |
| 20:23 | **CHECKPOINT** | `8e758fc` | `26033258410` | Extract HTML index crawler parser | 拆出 HTML index crawler parser，讓檔案索引頁解析與其他 crawler 分離。 |
| 20:17 | **CHECKPOINT** | `928d730` | `26032973671` | Extract Zenodo crawler parser | 拆出 Zenodo crawler parser，讓 Zenodo records payload parsing 可獨立維護。 |
| 20:11 | **CHECKPOINT** | `46dd25f` | `26032682072` | Extract Dataverse crawler parser | 拆出 Dataverse crawler parser，讓 Dataverse search payload parsing 可獨立維護。 |
| 20:05 | **CHECKPOINT** | `133782c` | `26032390536` | Extract GBIF crawler parser | 拆出 GBIF crawler parser，讓 GBIF dataset payload parsing 可獨立維護。 |
| 19:57 | **CHECKPOINT** | `a55eb32` | `26032040223` | Extract CMR crawler parser | 拆出 CMR crawler parser，讓 NASA CMR collection payload parsing 可獨立測試。 |
| 19:51 | **CHECKPOINT** | `b5cbfe4` | `26031746771` | Extract ERDDAP crawler parser | 拆出 ERDDAP crawler parser，讓 allDatasets payload parsing 可獨立維護。 |
| 19:45 | **CHECKPOINT** | `b3a1e21` | `26031476832` | Extract CKAN crawler parser | 拆出 CKAN crawler parser，讓 package_search payload parsing 可獨立測試。 |
| 19:38 | **CHECKPOINT** | `3b619ec` | `26031151955` | Extract STAC crawler parser | 拆出 STAC crawler parser，讓 STAC payload parsing 可獨立測試。 |
| 19:28 | **CHECKPOINT** | `0689340` | `26030671026` | Split crawler shared types | 拆出 crawler shared types，讓 DatasetDiscoverySource/DatasetCandidate 從 dispatcher 分離。 |
| 19:10 | **CHECKPOINT** | `f693923` | `26029840457` | Organize documentation handoff map | 整理 documentation handoff map，建立文件索引與接手閱讀順序。 |
| 18:58 | **CHECKPOINT** | `ff540bd` | `26029319639` | Add bounded STAC item resolver | 新增 STAC collection -> `limit=1` item-search GeoJSON sample resolver。 |
| 18:30 | **CHECKPOINT** | `4554612` | `26027998403` | Add workspace inventory and handoff summaries | 新增 workspace inventory 與 handoff summaries，幫助整理檔案與跨 Agent 接力。 |
| 16:51 | **CHECKPOINT** | `6b2a745` | `26023315124` | Promote audited local discovery sources to catalog | 把 crawler audit 通過且無 warning 的 local discovery sources 提升到正式 catalog。 |
| 16:20 | **CHECKPOINT** | `741de74` | `26021879309` | Promote portal intake drafts to local discovery config | 把通過基本檢查的 portal intake drafts 提升到 ignored local discovery config。 |
| 15:27 | **CHECKPOINT** | `dd65a2b` | `26019610366` | Parse portal intake sheet into review payloads | 把 portal intake Markdown 表解析成 review JSON，分出 provider seed、dataset source 與 adapter backlog。 |
| 15:05 | **CHECKPOINT** | `16354f6` | `26018721608` | Add portal intake sheet and bounded repository resources | 新增 portal intake 表與 bounded repository resource 記錄，讓團隊可提交候選入口。 |
| 14:17 | **CHECKPOINT** | `afd3df5` | `26016912397` | Expand dataset discovery sources and repository crawlers | 擴充 dataset discovery sources 與 repository crawlers，增加正式 catalog 中可爬入口。 |
| 13:49 | **CHECKPOINT** | `c181974` | `26015980242` | Resolve ERDDAP candidates to bounded sample plans | 讓 ERDDAP candidates 可解析成 bounded sample CSV plan，用小樣本測試下載/匯入閉環。 |
| 13:19 | **CHECKPOINT** | `38c44ea` | `26015031497` | Improve launcher drawer and dataset discovery visibility | 改善 launcher detail drawer 與 dataset discovery 可見性，讓 crawler-imported dataset rows 更容易被看見。 |
| 12:38 | **CHECKPOINT** | `09d9098` | `26013846029` | Resolve direct links from adapter plans | 讓 adapter plan resolver 處理更多 direct link 欄位與 metadata 包裝。 |
| 12:31 | **CHECKPOINT** | `a4cfd18` | `26013618401` | Expose adapter plan resolver in Tk UI | 把 adapter plan resolver 暴露到 Tk UI，讓使用者可從介面解析待辦計畫。 |
| 12:18 | **CHECKPOINT** | `92880f9` | `26013242152` | Resolve direct resources from adapter plans | 讓 adapter plan resolver 從 resources metadata 中找出安全 direct resources。 |
| 11:55 | **CHECKPOINT** | `909c5f5` | `26012625890` | Import supported files from archives | 新增 bounded archive transform，可從 ZIP/TAR 抽第一個支援檔案再接 SQLite importer。 |
| 11:43 | **CHECKPOINT** | `234f237` | `26012296875` | Add adapter review queue for plans | 新增 Adapter review queue，讓 CLI/Tk 可列出需要 adapter 的 plan items。 |
| 11:26 | **CHECKPOINT** | `517b10f` | `26011837192` | Add adapter review hints to dataset plans | 在 non-direct 或需轉換的 plan entries 加入 adapter_review handoff hints。 |
| 11:15 | **CHECKPOINT** | `355722a` | `26011548780` | Avoid UI import table overwrite | 避免 UI 匯入覆蓋既有 table，預設以安全改名建立新表。 |
| 11:05 | **CHECKPOINT** | `1345e9b` | `26011302588` | Show UI import readiness for plan items | 在 UI cart/job table 顯示 import readiness、狀態與 target table hints。 |
| 10:28 | **CHECKPOINT** | `83e98a5` | `26010301302` | Add guided UI import for plan results | 新增 UI guided import，讓使用者從下載 job/table 狀態進行驗證後匯入。 |
| 10:12 | **CHECKPOINT** | `913ca95` | `26009883696` | Support dataset-version UI plan items | 讓 Tk cart 支援 dataset/version plan items，避免同一 provider 多 dataset 互相覆蓋。 |
| 09:52 | **CHECKPOINT** | `2dadf51` | `26009360013` | Import supported download plan results | 讓 `--run-download-plan` 可在驗證後匯入支援的 CSV/JSON/GeoJSON 結果。 |
| 09:39 | **CHECKPOINT** | `e189b0c` | `26008990109` | Export crawler candidates as dataset plans | 讓 crawler candidates 可輸出為 dataset-version download/import plan。 |
| 09:05 | **CHECKPOINT** | `eb91ec4` | `26008124730` | Add concurrent dataset crawler auditing | 新增並行 dataset crawler auditing，並對 0 筆/過低/metadata 不完整結果產生 warning。 |
| 08:12 | **CHECKPOINT** | `68fe616` | `26006798788` | Organize launcher modules and docs | 整理 launcher 模組與文件，讓 API launcher core、UI 與 docs 分工更清楚。 |
| 07:53 | **CHECKPOINT** | `863ed0a` | `26006389536` | Add dataset candidate review workflow | 新增 dataset candidate review workflow，讓 crawler candidates 可被批准、拒絕或加入計畫。 |
| 06:47 | **CHECKPOINT** | `1418445` | `26004971266` | Close Gemini description integration loop | 打通 Gemini provider description integration loop，讓保存的 API key 可供摘要生成使用。 |
| 06:06 | **CHECKPOINT** | `2d9a155` | `26004061132` | Reject invalid Google OAuth client IDs | 拒絕格式不合法的 Google OAuth client id，避免重複觸發 invalid_client。 |
| 05:55 | **CHECKPOINT** | `e1cfbaa` | `26003811483` | Clarify Google OAuth setup flow | 釐清 Google OAuth setup flow，避免一般使用者被要求貼 developer client id。 |
| 05:48 | **CHECKPOINT** | `6e353bd` | `26003673538` | Add browser-based Google OAuth login | 新增 browser-based Google OAuth login 草案，後續因正式 OAuth app 需求而收斂。 |
| 05:19 | **CHECKPOINT** | `1b86544` | `26003014490` | Add user-facing Google QR login setup | 新增使用者面向的 Google QR login setup 草案，後續收斂為中期/開發者路線。 |
| 05:07 | **CHECKPOINT** | `aaf0ab1` | `26002746161` | Expand crawler-driven dataset sources | 擴充 dataset discovery sources，增加更多 metadata catalog 入口。 |
| 01:20 | **CHECKPOINT** | `d7bfef5` | `25997562969` | Add crawler-driven dataset discovery | 新增 crawler-driven dataset discovery 主線，讓 provider/source 能產生 reviewable dataset candidates。 |
| 00:43 | **CHECKPOINT** | `79707ba` | `25996713812` | Reserve Hadoop and Kubernetes pipeline ports | 預留 Hadoop/HDFS/Hive/Spark 與 K8S orchestration 對接契約，不納入當前 MVP 依賴。 |
| 00:31 | **CHECKPOINT** | `a844fd0` | `25996450926` | Import verified JSON manifests to SQLite | 新增從健康 JSON/JSONL/GeoJSON manifest 匯入 curated SQLite table 的路徑。 |
| 00:23 | **CHECKPOINT** | `b14b458` | `25996247479` | Record P2P dataset node concept | 記錄 P2P dataset node 概念，限定 public dataset 且需授權與 checksum guard。 |
| 00:17 | **CHECKPOINT** | `7b4e8c0` | `25996119286` | Record mobile companion app direction | 記錄 mobile companion app 方向，未來手機只做安全遠端控制與狀態查看。 |
| 00:13 | **CHECKPOINT** | `05dc758` | `25996017684` | Record resident desktop app roadmap | 記錄 resident desktop app 路線，規劃未來 system tray/menu bar 與長駐 worker。 |
| 00:08 | **CHECKPOINT** | `5d78925` | `25995903858` | Batch import verified CSV manifests | 新增批次匯入健康 CSV manifests 的 CLI，預設跳過不支援、不健康或已匯入項目。 |
| 00:02 | **CHECKPOINT** | `3ef4269` | `25995759465` | Import verified CSV manifests to SQLite | 新增從健康 CSV/CSV.GZ manifest 匯入 curated SQLite table 的路徑。 |

### 2026-05-17

主線：建立跨平台 CI 與 SQLite/Windows 修復守則，補上 manifest/repair/data-store 自檢、Tk repair panel、AI/Gemini 入口、下載 manifest 與直接下載計畫執行。

| 時間 | 標記 | SHA | Run | 原始標題 | 中文說明 |
| --- | --- | --- | --- | --- | --- |
| 23:54 | **CHECKPOINT** | `a9c0117` | `25995569527` | Run direct download plan entries | 讓 CLI 可執行 direct download plan entries，驗證 sidecar manifest 並註冊健康 payload。 |
| 23:44 | **CHECKPOINT** | `75a9d54` | `25995328804` | Export adapter dataset download plans | 讓 adapter-discovered dataset versions 可輸出為 dataset download plans。 |
| 23:24 | **CHECKPOINT** | `12dd16b` | `25994869232` | Register verified downloads as file assets | 把健康下載 manifest 註冊為 managed file assets，閉合 direct download -> registry ownership 路徑。 |
| 23:15 | **CHECKPOINT** | `370cd98` | `25994644779` | Classify realtime dataset updates | 分類 realtime/append-only dataset update 策略，避免把時間序列資料當靜態版本跳過。 |
| 23:07 | **CHECKPOINT** | `6ccbb68` | `25994470084` | Add per-asset data store profiles | 新增 per-asset data store profile 欄位，讓不同 database/table asset 可指定不同連線設定。 |
| 22:44 | **CHECKPOINT** | `915dd44` | `25993937240` | Add JSON download repair report | 新增 JSON download repair report，讓 agent/UI 可讀取 manifest issues 與 requeue plan。 |
| 22:37 | **CHECKPOINT** | `6d9aee1` | `25993760759` | Reuse verified HTTP downloads | 讓 HTTP downloader 在 target file 與 sidecar manifest 已驗證時重用檔案，避免重複下載。 |
| 22:16 | **CHECKPOINT** | `f33bd6e` | `25993288423` | Refresh user-facing launcher docs | 更新使用者面向 launcher 文件，讓 UI/操作流程說明更貼近現況。 |
| 22:11 | **CHECKPOINT** | `61a4478` | `25993177475` | Add AI profile QR login and provider icons | 新增 AI profile QR login 草案與 provider icons，後續收斂為更清楚的 AI/profile UX。 |
| 21:19 | **CHECKPOINT** | `34e1556` | `25992000198` | Show resize cursor for Tk table columns | 在 Tk table columns hover 時顯示 resize cursor，讓手動調欄寬更直覺。 |
| 21:12 | **CHECKPOINT** | `b3dd868` | `25991847511` | Improve Tk detail drawer layout | 改善 Tk detail drawer layout，讓詳細資訊區更可讀且不壓縮主列表。 |
| 20:58 | **CHECKPOINT** | `3267287` | `25991520833` | Handle cross-platform Unreal paths on macOS | 處理 macOS 上看到 Windows Unreal path 時的跨平台警告/忽略邏輯，避免 startup 阻塞。 |
| 20:47 | **CHECKPOINT** | `8f96316` | `25991283090` | Localize repair UI and show database issues | 本地化 repair UI，並在 UI 顯示 database issues 與修復建議。 |
| 20:31 | **CHECKPOINT** | `ffbfb7c` | `25990910893` | Add database self-check repair suggestions | 新增 database self-check repair suggestions，讓問題有穩定 suggestion IDs 與修復方向。 |
| 20:21 | **CHECKPOINT** | `c690b27` | `25990701428` | Document CI and SQLite handoff safeguards | 補充 CI 與 SQLite handoff safeguards，提醒後續使用 contextlib.closing 等安全做法。 |
| 20:18 | **CHECKPOINT** | `6d9612f` | `25990628206` | Close SQLite probes for Windows CI | 修正短生命週期 SQLite probes，確實關閉 connection，解掉 Windows CI 檔案鎖。 |
| 20:07 | **CI 失敗** | `4bb5b18` | `25990396833` | Verify SQL table assets from install ownership | 嘗試依 install ownership 驗證 SQL table assets；這筆當時 CI 失敗，後續由 SQLite probe 修正收斂。 |
| 19:59 | **CI 失敗** | `3fea8d4` | `25990224293` | Add SQL information schema introspection helpers | 嘗試新增 SQL information_schema helpers；這筆當時 CI 失敗，後續修復 Windows SQLite 檔案鎖問題。 |
| 19:53 | **CI 失敗** | `179d1e4` | `25990089504` | Add SQLite table asset self-checks | 嘗試新增 SQLite table asset self-checks；這筆當時 CI 失敗，後續由 connection close 修復。 |
| 19:45 | **CI 失敗** | `39722f3` | `25989914834` | Detect SQLite database schema drift | 嘗試偵測 SQLite database schema drift；這筆當時 CI 失敗，後續修正 SQLite probe 關閉方式。 |
| 19:39 | **CI 失敗** | `73e7e98` | `25989799370` | Add repair and data-store self-check workflows | 嘗試新增 repair 與 data-store self-check workflows；這筆當時 CI 失敗，後續集中修復 SQLite 連線/Windows 檔案鎖。 |
| 17:29 | **CHECKPOINT** | `625a910` | `25987126632` | Add Tk manifest repair panel | 新增 Tk manifest repair panel，讓使用者可在 UI 檢查 manifest 與重新排下載。 |
| 17:25 | **CHECKPOINT** | `e439210` | `25987046110` | Share library action helpers with Tk UI logs | 讓 Tk UI logs 共用 library action helpers，避免 UI 另寫 action policy。 |
| 17:18 | **CHECKPOINT** | `b18fa87` | `25986903749` | Add cross-agent handoff card | 新增跨 Agent handoff card，固定接手時要讀的狀態、雷點與驗證流程。 |
| 17:12 | **CHECKPOINT** | `0d51022` | `25986787195` | Consolidate data store connection structure | 收攏 data store connection 結構，建立 profile/test-result/env-var mapping 的單一契約。 |
| 16:55 | **CHECKPOINT** | `e063ff3` | `25986434233` | Enable Gemini summary invocation path | 打開 Gemini summary invocation path，讓 AI provider description 能被實際呼叫。 |
| 16:48 | **CHECKPOINT** | `ffb20c3` | `25986286696` | Add account link and AI prompt contracts | 新增 account link 與 AI prompt contracts，定義摘要生成與帳號/credential 邊界。 |
| 16:43 | **CHECKPOINT** | `139a712` | `25986179526` | Refine Tk launcher and Gemini login skeleton | 調整 Tk launcher 與 Gemini login skeleton，改善 UI 結構與 AI 摘要入口。 |
| 16:29 | **CHECKPOINT** | `01b5d81` | `25985891413` | Add Steam-like library action skeleton | 新增 Steam-like library action skeleton，定義 install/update/repair/open/render 等 action 方向。 |
| 16:24 | **CHECKPOINT** | `12f63aa` | `25985796665` | Add frontend contract inspection hooks | 新增 frontend contract inspection hooks，讓前端/renderer contract 可被檢查。 |
| 16:17 | **CHECKPOINT** | `c880ae5` | `25985640519` | Add renderer frontend pipeline skeleton | 新增 renderer frontend pipeline skeleton，建立 Taichi/Unreal/Cesium 類 renderer bridge 概念。 |
| 15:33 | **CHECKPOINT** | `5a06622` | `25984763083` | Add Unreal bridge planning skeleton | 新增 Unreal bridge planning skeleton，記錄未來虛擬地球/frontend 對接方向。 |
| 15:21 | **CHECKPOINT** | `54de4ec` | `25984516437` | Add manifest listing CLI | 新增 manifest listing CLI，讓下載/manifest 狀態可由命令列檢視。 |
| 15:19 | **CHECKPOINT** | `304af0e` | `25984470572` | Update project state after manifest and CI work | 在 manifest 與 CI 工作後更新 project state，保存當時進度與驗證結果。 |
| 15:16 | **CHECKPOINT** | `b2e0a2f` | `25984424650` | Make path tests independent of local SQLite state | 讓 path tests 不依賴本機 SQLite 狀態，修復跨平台 CI 不穩定因素。 |
| 15:15 | **CI 失敗** | `ec4dcd2` | `25984393356` | Add Chinese cross-platform setup notes | 新增中文跨平台 setup notes；這筆當時 CI 失敗，後續與 CI/path 修復一起收斂。 |
| 15:13 | **CI 失敗** | `a6669f5` | `25984353375` | Add cross-platform CI workflow | 嘗試新增跨平台 CI workflow；這筆當時 CI 失敗，後續由路徑測試與 SQLite 連線關閉修復。 |

## 目前已知風險

- 本機 `git log` 在 2026-05-20 附近仍會碰到缺失 object `aca3de5bb67649e291223106e927a144fe403a9a`，這與先前 handoff 記錄的雲端同步損傷吻合；本次回補改以 GitHub Actions push run list 作為時間線來源。
- 先前未追蹤的 `APIkeys_collection (1).py` 重複副本已移除；目前不再列為待處理風險。
- `docs/PROJECT_STATE.md` 是長篇歷史狀態快照；最新狀態應以本開發日誌、`PROJECT_GTD.md`、`AGENT_HANDOFF.zh-TW.md`、`git log` 可讀範圍與 GitHub Actions 為準。
