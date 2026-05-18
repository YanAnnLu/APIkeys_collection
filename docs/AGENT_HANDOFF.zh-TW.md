# Agent 接力卡

最後更新：2026-05-18

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
   docs/DATASET_TYPE_MAP.zh-TW.md
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
| 最新已推送 commit | 以 `git log -1 --oneline` 為準；每次接力前更新本文件 |
| 上次驗證 | 2026-05-17：本機測試與 GitHub Actions 狀態以最新 commit 為準；接力前請重跑 |
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
- HTTP downloader 已新增「已驗證下載重用」：如果目標檔案和 sidecar manifest 都正常，且 provider/dataset/version/source/path 符合目前下載請求，就不重新連網下載。Tk UI 也會記住實際送進下載器的 plan entry，版本下載完成時 registry 的 `source_uri` 不會誤寫成原 provider URL。
- 健康的下載 manifest 現在可登錄為 install registry 裡的 managed `file` asset；CLI `--verify-downloads` 與 Tk 下載完成流程會共用 `register_downloaded_manifest_asset()`。Database self-check 已限定只驗 `database` / `table` asset，避免把已下載檔案誤判成資料庫錯誤。
- Adapter 發現的 dataset version 現在可用 CLI `--export-dataset-plan PATH` 匯出成下載計畫。直接檔案 URL 會有 `download_url`/`target_path`/`use_staging`；入口頁或 selector 會標記成 `adapter_required` 並放在 `adapter_review_url`，不要直接交給 HTTP downloader。
- CLI `--run-download-plan PATH` 現在可執行 plan 裡的 direct entries，跳過 `adapter_required`，下載完成後驗 sidecar manifest 並登錄 managed filesystem `file` asset。可用 `--download-plan-limit N` 做小量 smoke test。
- CLI `--import-csv-manifest MANIFEST --import-sqlite-db PATH --import-table TABLE` 現在可把健康 CSV/CSV.GZ manifest payload 匯入 curated SQLite table，欄位名稱會正規化成安全 SQL identifier，並登錄 `asset_role=curated` 的 table asset 與 schema fingerprint。若要覆蓋既有 table，必須明確加 `--import-replace-table`。
- CLI `--import-verified-csv-manifests --import-sqlite-db PATH` 可批次匯入 registry 裡的健康 CSV/CSV.GZ manifests；預設跳過非 CSV、不健康 manifest、已存在 table。可搭配 `--provider ID` 限定資料商。
- CLI `--import-json-manifest MANIFEST --import-sqlite-db PATH --import-table TABLE` 現在可把健康 JSON/JSONL/GeoJSON manifest payload 匯入 curated SQLite table。支援物件陣列、JSON Lines、`records/items/results/data` 包起來的陣列，以及基本 GeoJSON FeatureCollection；欄位先以 `TEXT` 存入並登錄 `asset_role=curated`、`source_format=json` 與 schema fingerprint。
- CLI `--import-verified-json-manifests --import-sqlite-db PATH` 可批次匯入 registry 裡的健康 JSON/JSONL/GeoJSON manifests；預設跳過非 JSON、不健康 manifest、已存在 table。這是 CSV 後的第二條 raw -> curated MVP 路徑。
- `--verify-downloads-json` 已提供下載檔驗證的 agent-readable JSON：包含 summary、issues、repair suggestion、以及 HTTP(S) manifest 可安全重排下載的 plan entry。若要指定掃描資料夾，可搭配 `--downloads-root PATH`。
- Tk UI 新增 `設定 > 介面語言`，語言存在 `launcher_integrations.local.json` 的 `ui_language`。預設是 `zh-TW`；新開啟 dialog 會套用，主畫面完整套用需重新啟動。後續碰 UI 時應優先補齊繁中顯示與 `tr(...)` 英文 fallback。
- Tk UI 的登入/串接入口已集中到上方 `整合` 選單：`AI / Gemini 串接中心`、`保存 Gemini API key`、`AI 輔助模型選擇`、`Google OAuth（中期 / 開發者）`、資料儲存連線與資料庫工具都在這裡。主工具列和右側抽屜不要再新增登入/API key/資料庫工具設定入口；抽屜只保留目前資料源的動作。
- AI 生成描述目前以功能閉環為優先：Gemini API key 是 MVP 雲端路線，`api_launcher/ai_api_keys.py` 會把 key 存在 ignored `state/private/ai_api_keys.private.json`，UI 啟動時自動載入，`generate_provider_summary()` 也會嘗試載入 saved key。使用者只應在缺 credential 時被要求保存 key，不要每次重貼。
- Google OAuth / QR 是中期正式目標，不是不做；只是現在 MVP 尚未閉環，先不要讓它阻塞 AI 描述生成。一般使用者不該被要求貼 Desktop OAuth Client ID；若沒有專案官方 OAuth App，就顯示尚未開通。開發者仍可透過 `整合 > Google OAuth（中期 / 開發者） > 開發者 OAuth 設定` 測試，格式不像 `*.apps.googleusercontent.com` 的值會被拒絕保存，避免重複觸發 Google `invalid_client`。
- PySide6 / Qt 已列為中期 UI 升級路線：不要現在重寫 UI；先完成 backend/MVP 閉環。後續若啟動 Qt，應新增 `frontends/qt/` 並重用 `api_launcher`、library actions、event logs、download queue、integration contracts，不要把業務邏輯複製進 UI。
- Tk UI 資料源詳情改為右側比例抽屜：抽屜寬度依主內容區比例計算，保留表格基本空間，開關時有短距離寬度動畫，內容可捲動，描述/狀態/連結文字會依抽屜寬度換行，避免被擠成窄直欄；抽屜內另有 AI 生成描述 textbox。
- Tk UI 左側欄可在「依類型」與「依提供商」間切換；提供商模式會依目前 catalog owner 動態產生篩選按鈕，並在背景抓取/快取官網 favicon 到 `state/favicons/` 當小圖示。
- Tk UI 新增 `工具 > 開發者 CLI`，提供專案工作目錄下的單次命令輸入/輸出面板，供開發者快速呼叫 CLI。
- Tk UI 主表格支援類 Excel 欄寬調整：拖拉欄位分隔線後，欄寬會寫入 `launcher_integrations.local.json` 的 `ui_table_column_widths`；「更多 > 重設表格欄寬」可清除回預設比例。
- Tk UI 的下載資格與詳情狀態文字已補上繁中顯示，UI 語言切到 `en-US` 時仍保留英文 fallback。
- Data store connection testing 已有骨架：`--test-data-store PROFILE_ID|all` 可測 configured profiles；SQLite 會用 read-only introspection，MySQL/PostgreSQL 先檢查 env vars 與 optional Python driver。
- Data store profiles 支援 `env_var_map`，可把 host/database/user/password/port/path 對應到自訂環境變數名稱；密碼仍不寫進 Git config。
- SQL/database self-check 已擴充到 SQLite database/table assets：`--self-check-databases` 會用 registry asset verifier 檢查 managed database/table assets；SQLite database asset 依 `source_uri`/path 做 read-only 檢查與 database-level fingerprint，SQLite table asset 依 `source_uri` + `asset_name` 檢查單表存在與 table-level fingerprint drift，並回寫 asset/provider 狀態與 missing/error 明細。
- MySQL/PostgreSQL data-store layer 已有 `information_schema` introspection helpers：連線 smoke 可回報 table_count；database/table asset 若登記 `schema_fingerprint`，self-check 會要求 schema summary 並偵測 drift。跨引擎 table asset 會從 `install_location` 解析 database owner，PostgreSQL `asset_name` 可用 `schema.table` 指定 schema，並能標記 missing table。
- Database/table asset 現在可記錄 `data_store_profile_id` 與明確 `schema_name`；self-check verifier 會吃 local integration config 裡的 configured profiles。白話說，之後 UI 可以讓使用者替某個資料庫資產指定「用哪個連線設定、查哪個 schema」，不必永遠靠預設 MySQL/PostgreSQL env vars。
- `--self-check-databases` 現在人類輸出會包含 `suggestion=...` 修復代號；`--self-check-databases-json` 會輸出純 JSON，包含每個 missing/error database/table asset 的錯誤、去敏感化位置、是否有 schema fingerprint、profile/schema metadata、以及修復建議。這是給 UI、下一位 Agent、或未來自動修復流程讀的入口。
- Tk Repair panel 的「資料庫」分頁會重用同一套 database self-check verifier 與 `database_self_check_issues()`；目前只顯示診斷與下一步，不自動執行 `DROP`、重建 table、或刷新 fingerprint。
- 2026-05-17 已修復 Windows CI：Python `with sqlite3.connect(...)` 不會自動 close connection，Windows temp SQLite 會被檔案鎖住並造成 `WinError 32`；短生命週期 SQLite probe/test 請用 `contextlib.closing(sqlite3.connect(...))`。
- macOS 目前已安裝並登入 GitHub CLI (`gh`) 為 `YanAnnLu`，可直接查 CI run/log。
- 海域法域資料請記住：領海、EEZ、爭議區、公海不是單純座標戳，而是帶法律/行政屬性的 GIS polygon 圖層。MySQL spatial 可做 MVP；較完整 GIS 分析、切 tile、空間索引應優先考慮 PostGIS；原始資料保留 GeoPackage/Shapefile/GeoJSON 與 manifest。
- 第 1 項目前已調整為「善用 crawler 發現 provider/source 與 dataset candidates」，不要把每個代表資料集都硬寫成 Python adapter。`catalog/dataset_discovery_sources.json` 描述可爬的資料目錄；`api_launcher/dataset_discovery.py` 可從 NOAA/NCEI Search、ERDDAP `allDatasets`、HTML file index、NASA CMR collection search、STAC collections、GBIF dataset search、CKAN `package_search` 產生 reviewable dataset candidates。AIS 與衛星雲圖是代表測試案例：AIS 應由 MarineCadastre index 發現 shards，衛星雲圖應由 NOAA/NCEI/GOES-R/Earth Engine/STAC 類 catalog 發現 raster/grid 候選。
- Dataset candidates 現在有初步 review loop：repository 可列出/標記 candidate status，CLI 可用 `--list-dataset-candidates`、`--dataset-candidates-json`、`--review-dataset-candidate UID --dataset-candidate-decision approved|planned|rejected`，Tk UI 在 `資料庫 > 審核資料集候選` 可查看、開來源、標記可用/拒絕或加入目前下載計畫。這仍是 metadata-only registry 狀態，不會下載或改動資料本體。
- 金融/即時市場資料請記住：這不是一般「同版本就跳過」的靜態資料。`dataset_updates.py` 現在有 append-only / revisable / realtime time-series contract；金融 adapter 應保留 `event_time`、`received_at`、`ingest_run_id`，必要時保留 `revision`/`source_sequence`。MySQL 可做 MVP，重度 tick/回測資料優先考慮 TimescaleDB、ClickHouse、Parquet/DuckDB。時間序列的視覺化對標是 TradingView-like chart：K 線、成交量、指標、縮放拖曳、十字游標與即時更新，而不是只想 Taichi/Unreal 地球渲染。
- 高能粒子對撞機等大型科學實驗資料請記住：這類是 event/array data，不是普通 SQL row store。SQL 可管 run ID、檔案索引、校準版本、provenance、manifest 與權限；raw data 優先保留 ROOT/HDF5/Parquet/Zarr/FITS/NetCDF 或物件儲存，再用 ROOT/uproot、DuckDB/Parquet、Dask/Spark、ClickHouse 等工具分析。
- 歷史建築/文化資產/多媒體資料請記住：這類常是 asset bundle，可能含照片、影片、音訊、3D mesh、點雲、BIM/IFC、材質貼圖與地理/年代/授權 metadata。SQL 管目錄與索引；raw asset 放檔案/物件儲存並用 manifest 記 checksum、LOD、座標系與依賴；viewer/render target 可是 Three.js、Cesium、Unreal、Blender 或 GLTF pipeline。

## 下一步優先事項

1. Tighten dataset candidate -> download plan behavior：同 provider 多 dataset/version 的 plan 選擇要更準，避免只用 provider_id 當唯一 cart key。
2. 把下載後 CSV/JSON manifest 匯入做成更像一般使用者流程的 UI / guided action。
3. 擴充 repair 建議到 adapter-specific datasets，並把 download/database JSON repair payload 接到更完整事件 log 與 UI guided repair flows。
4. 擴充 SQL/database self-check：把 per-asset SQL profile/schema 選擇做進 UI，加入真實 driver smoke 覆蓋，並把現有 UI repair suggestion 升級成 adapter-owned guarded action。
5. 繼續擴充 crawler source 類型，但要維持設定檔驅動；下一批可評估 OGC API Records、Dataverse、Socrata、OpenAlex/DataCite 類 metadata 來源。
6. 新增 financial/time-series adapter contract，處理 live market data、append windows、revision/backfill、retention policy。
7. 新增 Marine Regions/VLIZ maritime boundaries adapter，支援領海、EEZ、爭議區、公海圖層。
8. 用 SQLite `dataset_asset_manifests` 做更廣義的 update/dedupe 決策；目前只完成同一 target 檔案的 manifest 重用。
9. 維護 `docs/AGENT_HANDOFF.zh-TW.md` 作為開發接力主入口；未來若要做 `.codex/skills/apikeys-collection-launcher`，應等 MVP 閉環穩定後再產品化成消費端/操作端技能。
10. 繼續減少 Tk UI 內的業務邏輯，讓 UI 主要負責呈現與觸發。

## 開發守則

- 每完成一個功能，要更新 `docs/PROJECT_GTD.md`。
- 每次跨機器或跨 Agent 接力，要更新這份 `docs/AGENT_HANDOFF.zh-TW.md`。
- 不要提交 `config/launcher_integrations.local.json`、`state/`、`downloads/`、真實 token、真實 API key。
- 不要把本機絕對路徑寫死在程式碼；路徑要走 `api_launcher/paths.py` 或 config。
- 預留端口不是死碼；但如果兩個模組表達同一件事，要優先合併抽象。
- 目錄整理規則：`api_launcher/downloads/` 放下載資格、queue、HTTP、staging、repair、transfer tools；`api_launcher/importers/` 放 CSV/JSON 匯入與 curation；根目錄只保留相容啟動入口。
- macOS 要注意 Tk、UTF-8、LF 換行、路徑大小寫與 `python3`/venv。特別注意不要讓 Windows 路徑（例如 `K:\...`）在 Mac startup checks 被當成錯誤；跨平台路徑應先依系統挑 `*_by_platform`，不符合本系統的 generic path 要忽略或降成 warning，不可阻擋 UI 啟動。
- `.gitignore` 裡 root runtime 資料夾要寫成 `/state/`、`/downloads/`，不要寫成 `downloads/` 這種會誤傷 `api_launcher/downloads/` 原始碼套件的規則。
- 專案在 macOS CloudMounter / 雲端同步碟上時，Python 讀寫預設 `__pycache__` 可能卡住；跑測試建議加 `PYTHONPYCACHEPREFIX=/tmp/apikeys_collection_pycache`。這次 full test 就是靠這個本機 pycache prefix 正常完成。
- Git object store 不適合長期放在 CloudMounter/雲端同步層；若 `git fsck` 出現 missing object 或 invalid reflog，先 `git fetch origin main` 嘗試補回。若仍壞，優先把 repo 重新 clone 到本機磁碟，再把工作區 patch 搬過去。
- SQLite 短生命週期連線不要裸用 `with sqlite3.connect(...)`；那只處理 transaction，不會 close connection。用 `contextlib.closing(...)` 避免 Windows CI 檔案鎖。
- 每次 push 後，用 `gh run watch --exit-status` 追最新 CI；不要只以 push 成功判斷完成。
- 接力事故紀錄：2026-05-17 曾因把未提交的大型 `APIkeys_collection.py` 誤判為可丟棄內容而覆回 Git wrapper。下一位 Agent 遇到任何未提交、非預期、或看似「不符合文件」的大改動時，必須先備份或輸出 patch，再詢問/確認；不要直接 `git restore`、刪除或覆寫。

## 給下一位 Agent 的提示詞

```text
你正在接手 APIkeys_collection。請先讀 docs/AGENT_HANDOFF.zh-TW.md，再讀 docs/PROJECT_GTD.md。不要依賴上一段聊天紀錄。

先執行 git pull origin main、git status --short --branch、python3 -m unittest discover -s tests。本機 Codex/macOS 環境請優先用 conda env：conda run -n metal_trade_312 python -m unittest discover -s tests；不要把套件裝進 base/system Python。

push 後請用 gh run watch 追 CI。Windows 失敗時優先檢查 SQLite/file handle、路徑與 `.pyc` 鎖。SQLite 短生命週期連線要用 contextlib.closing。

目前第 1 項已經改成 crawler-first：provider/source discovery 找供應商與入口，dataset discovery sources 找資料集候選，adapter 只在 crawler 候選需要 bounded query/auth/transform/import 時才寫。請優先看 `catalog/dataset_discovery_sources.json`、`api_launcher/dataset_discovery.py`、`api_launcher/cli_dataset_discovery.py`。下一步重點是 dataset candidate review/import UI，讓使用者能審核 crawler 找到的資料集，再排入下載或匯入計畫。AIS 與衛星雲圖是代表測試案例，但不要再把每個資料集硬寫成 Python 類別。

注意：SQL-only connection layer 已被合併到 api_launcher/data_store_connections.py，不要重新建立 sql_connection_profiles 或 sql_connections.py。

注意：未提交內容一律視為使用者或上一位 Agent 的成果。若檔案看似不符合目前架構，先備份/產生 patch 並說明風險，再決定是否收斂。
```
