# Agent 接力卡

最後更新：2026-05-25

接手時先讀 `docs/AGENT_START_HERE.zh-TW.md`，再讀本文件與 `PROJECT_GTD.md`。這份文件是跨 Windows、macOS、不同 Agent 接力時的固定接力卡；每次切換機器或切換 Agent 前，請優先更新這份文件。

## 2026-05-25 Crawler asset / download plan registry 收斂

- 最新穩定 checkpoint：`dcbee41`（`Centralize file index source type checks`），GitHub Actions run `26397913391` 已成功。
- `api_launcher/crawlers/source_type_registry.py` 現在集中 HTML/file-index 來源類型判斷，提供 `source_type_is_file_index()` 與 `source_uses_file_index()`；bounds facet、crawler asset capability 與 source draft 都應共用這組 helper。
- `api_launcher/plans.py` 已把 CMR collection 與 DataCite/OpenAlex research metadata 的 adapter-review 擋板命名成 `CMR_COLLECTION_*` 與 `RESEARCH_METADATA_*` registry/set；後續不要把 DOI/OpenAlex/NASA CMR 特例直接塞回 UI 或 resolver 分支。
- 驗證紀錄：`tests.test_source_pattern_drafts tests.test_crawler_assets` 26 tests OK；完整 `unittest discover -s tests` 627 tests / 4 skipped OK；`scripts\pre_push_smoke_brief.cmd` 627 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`；GitHub Actions Ubuntu、`windows-2025-vs2026`、real DB smoke success。
- 接下來仍維持 crawler 後端收斂主線：優先找 source_type 分支、URL/format 硬編碼與 UI 自行猜測的地方，轉成 registry/helper + regression test。每個 substantive checkpoint 必須先推送並確認 CI，再更新 `docs/DEVELOPMENT_LOG.zh-TW.md`。

## 2026-05-25 Content parser registry 骨架

- Checkpoint 規則補強：每完成一個 commit / push / CI success 的功能切片，都要同步更新 `docs/DEVELOPMENT_LOG.zh-TW.md`。未推送或測試未綠的工作只能寫成 GTD/handoff 的「進行中/風險」，不能寫成 `**CHECKPOINT**`。
- 新增 `api_launcher/content_registry.py`，把下載物內容格式與 STAC/CKAN/ERDDAP 等來源入口範式分開。它目前能回報 `source_format`、`content_family`、`import_status`、`parser_id`、`review_bucket` 與 evidence。
- `api_launcher/plans.py::dataset_import_plan_entry()` 已改用 content registry：CSV/CSV.GZ 與 JSON/JSONL/NDJSON/GeoJSON 仍是 `supported_after_download`，ZIP/TAR/ZST 等封包停在 transform review，NetCDF/HDF/Zarr/GeoTIFF/Shapefile ZIP/FlatGeobuf/PMTiles/MBTiles/Parquet/PDF/XML/unknown 停在 content parser review。
- `api_launcher/adapter_plan_resolver.py` 產生 direct entry 時已補上 `content_detection` 與 `content_parser` 摘要，包含 parser id、import status 與 review bucket。下一步可把這些欄位接到 adapter review / download plan 的 UI 顯示層。
- Content format 正規化已補 geospatial/scientific MIME：`image/tiff; application=geotiff` 與 GeoPackage 會進入 `geospatial_asset_review`，HDF / GRIB 類型也會進入 scientific/grid review，而不是掉到 unknown。
- Adapter resolver 已允許 GeoTIFF / COG / GeoPackage 這類 geospatial direct asset 先形成下載計畫，再停在 content parser review；extensionless GeoTIFF 會得到 `.tif` 目標檔名。
- Generic resource resolver 的 URL suffix 推論已改用 format 正規化；即使 metadata 沒有 mediaType/format hint，`.nc`、`.cdf`、`.h5`、`.hdf5`、`.gpkg`、`.shp.zip`、`.fgb`、`.pmtiles`、`.mbtiles` 與 `.sqlite3` 這類清楚檔案 URL 也可進 direct plan，再由 content parser review 擋住 curated import。
- GRIB/GRIB2 已補齊 detector/source draft/direct eligibility/content registry/resolver/target extension 合約；`.grib2` 可以形成 direct plan，但仍會停在 `scientific_grid_review`，不會假裝可 curated import。
- Direct download eligibility 已補 `.gpkg`、`.cdf`、`.fgb`、`.pmtiles`、`.mbtiles`、`.sqlite` / `.sqlite3` / `.db`，所以 GeoPackage、FlatGeobuf、tile package、舊式 NetCDF 與 raw database snapshot 檔案型 URL 不會在舊 provider/direct URL 判斷路徑被誤導成 adapter required。
- 新增 `tests/test_content_registry.py`，並已跑 `tests.test_content_registry`、`tests.test_dataset_download_plan`、`tests.test_adapter_plan_resolver`。測試也覆蓋 extensionless CSV 與 NetCDF direct asset 的 content parser 摘要。
- Source pattern detector 測試已補 CKAN、Socrata、OGC 正例與 ambiguous collections payload 的 `unknown` fallback，避免通用蟲看起來支援多範式但缺少合約防線。
- `api_launcher/source_pattern_drafts.py` 已在 detector 前拒絕非 HTTP(S) URL 與內嵌帳密 URL；測試確認 invalid URL 不會觸發 detector，也不會寫入 local source draft。
- OGC detector 已把 WMS `GetCapabilities` XML 分流成 `ogc_wms` / `ogc_wms_capabilities`，並新增 `api_launcher/crawlers/ogc_wms.py` 從 capabilities layer 抽 dataset candidate。不要把 WMS 誤接到 `ogc_api_records`。
- WMS parser 會優先使用 `Request/GetMap` 底下的 `OnlineResource` 作為 `api_url`，避免拿到 Service metadata 的介紹頁 URL。
- WMS parser 也已補 `<Service><Title>` metadata 與 layer search-term 過濾測試，候選 passport 不再只依賴 source name 當服務標題。
- Source pattern 的 WMS detector 也已接受大寫 `SERVICE` / `REQUEST` capabilities URL，不會在 detector probe 時重複追加小寫參數。
- HTML file index detector 產生的 source draft 現在會帶保守資料檔副檔名 regex；測試確認草稿能直接交給 `html_file_index_candidates_from_text()` 抽出 CSV shard，而不是在 crawler audit 才因缺 `file_url_regex` 失敗。
- HTML file index detector 本身也已同步辨識複合壓縮與地理/氣象資料檔連結，例如 `.geojson.gz`、`.cdf`、`.hdf5`、`.gpkg`、`.shp.zip`、`.fgb`、`.pmtiles`、`.mbtiles`、`.sqlite3`、`.zarr`、`.grib2`、`.tar.gz`、`.csv.zst`；只有這類檔案的入口頁不應再因舊副檔名清單而掉到低信心 `unknown`。
- HTML file index 預設 regex 已覆蓋 `.csv.gz`、`.csv.zst`、`.geojson.gz`、`.cdf`、`.hdf5`、`.gpkg`、`.shp.zip`、`.fgb`、`.pmtiles`、`.mbtiles`、`.sqlite3`、`.zarr`、`.grib2`、`.tar.gz` 等常見資料檔，避免 source draft 後續 audit 只因壓縮副檔名回傳零候選。
- HTML file index detector 與 source draft 已共用同一份資料檔副檔名 vocabulary；後續新增格式時先改 `source_patterns.py` 的 vocabulary，再用 detector 與 source-draft 測試一起鎖住。
- HTML file index crawler 現在支援 bounded same-origin full crawl：`full_crawl=True` 時會在 `max_pages` 內追同網域索引頁，但不追資料檔或跨網域頁。
- CKAN / Socrata detector 已補深層 URL fallback：若使用者貼 dataset/resource 頁，會再 probe 同 origin 的 canonical API endpoint，避免把可辨識來源誤判為 `unknown`。
- STAC detector 已補 `/collections` endpoint 正例：使用者貼 STAC collections URL 時可直接判成 `stac_collections`，不必一定貼 root catalog。
- ERDDAP source draft normalization 已修正深層 dataset URL：`/erddap/griddap/...` 或 `/erddap/tabledap/...` 會正規化回 allDatasets endpoint，避免 detector 正確、audit endpoint 錯誤的斷線。
- ERDDAP detector 的 info/index probe 也已回到站台根 `/erddap/info/index.json`，可處理 `/ERDDAP/griddap/...` 這類深層或大小寫不同的 dataset URL。

## 2026-05-24 Tk 來源草稿入口與治理機制收斂

- 已把 `--write-source-draft-from-url` 接到 Tk crawler asset 分頁的「貼 URL 建立來源草稿」入口。Tk 只收集 URL / provider / 類別 / 期望候選數等輸入；偵測、source draft 寫入、unsupported/unknown 擋下仍由 `api_launcher.source_pattern_drafts` 後端服務負責。
- 新增 `frontends/tk/source_pattern_draft_dialog.py`，用動態表單收斂輸入，並在成功訊息中顯示 detector pattern、confidence、evidence、ignored local draft 路徑與下一步 discovery audit 指令。這不是 catalog promotion，也不會下載或匯入。
- 新增/補強測試：`tests/test_source_pattern_drafts.py` 覆蓋 detected / unknown / unsupported；`tests/test_tk_dialogs.py` 覆蓋 headless form values 與 Tk workflow 成功訊息。已跑 `scripts/pre_push_smoke_brief.cmd`，574 tests 通過，MVP demo smoke `download_import_completed`、`row_count=3`。
- `docs/AGENT_START_HERE.zh-TW.md` 已補上固定治理機制：小切片開始先看 git 狀態；中大型改動先寫 scope / acceptance / risks；卡住可跑 heartbeat dry-run；agent-readable 狀態優先用 JSON；push 前跑 pre-push smoke，push 後看 GitHub Actions。

## 2026-05-24 來源介面 detector 與界域表單交接

- 本輪新增 `api_launcher/crawlers/source_patterns.py`，正式把 crawler 設計切成「來源介面類型」而不是機構名稱。Detector 只辨識 STAC / CKAN / ERDDAP / Socrata / OGC / CMR / HTML file index / unknown，輸出 confidence、evidence、`source_type_hint`，不下載資料。
- 後續已新增 `api_launcher/source_pattern_drafts.py` 與 CLI `--write-source-draft-from-url URL`，可把 detector 結果寫成 ignored local dataset discovery source draft。這不是 catalog promotion；summary 會帶 `source_pattern_detection`、`audit_source_ids`、`next_action=run_local_discovery_audit_before_catalog_promotion`，下一步仍要跑 crawler audit。
- 文件已在 `docs/DATASET_DISCOVERY_NOTES.zh-TW.md` 補上分層：`source detector -> source adapter -> fetcher -> content detector -> content parser -> normalizer/importer`。後續不要讓 STAC/CKAN/ERDDAP adapter 直接承擔 GeoTIFF/NetCDF/CSV/ZIP 的內容解析。
- 本輪新增 `api_launcher/crawler_asset_bound_forms.py` 與 `frontends/tk/crawler_asset_bound_dialog.py`；Tk crawler asset 的「送進下載器 / 界域」會先依 `bounds_schema` 產生動態表單與 payload，再切到下載器。這還不是完整下載閉環，下一步是把 payload 正式交給 `build_download_plan()`。
- 測試重點：`tests.test_source_patterns` 鎖定 detector 行為，`tests.test_crawler_assets` 鎖定 bounds schema/form payload，`tests.test_tk_dialogs` 鎖定 Tk dialog 與 workflow 儲存 payload。

### K 槽爬蟲教材使用提醒

`K:\` 裡的爬蟲教材不要當成「可直接搬進專案的站點爬蟲」。它們是技術參考，目標是幫 RRKAL 把 `seed -> crawler -> candidate -> plan -> download -> import -> UI` 這條線補得更穩。

- HTTP/header/timeout/HTML/JSON 判斷技巧：優先抽到 `api_launcher/crawlers/source_patterns.py`，用來辨識 STAC / CKAN / Socrata / OGC / CMR / ERDDAP / HTML file index / unknown，而不是判斷是不是 NASA/NOAA。
- HTML 連結解析、相對 URL 合併、副檔名過濾：可強化 `html_file_index`，但要有 `max_pages`、allowed domain、URL 去重、zero candidate warning。
- Scrapy 的 `Spider -> Item -> Pipeline -> Middleware` 是分層思想，可映射成 detector/crawler、`DatasetCandidate`、adapter review/download plan、manifest/import、rate-limit/auth/retry policy；先不要直接引入 Scrapy 依賴。
- CSV/SQLite 清洗教材可用來強化 CSV/JSON manifest import：header 清理、type inference、日期解析、bad row warning、schema fingerprint、SQLite table import；crawler 仍不得直接寫 DB，必須維持 `download -> manifest -> import` 邊界。
- rate limit / politeness 應轉成 source profile 的 `rate_limit_policy`、`timeout`、`max_pages`、`credential_mode`、`terms_risk`，不要在 parser 裡硬塞 `time.sleep()`。
- 錯誤處理要升級成 machine-readable：`warning_codes`、`next_action`、`audit_summary`、`problem_sources`，例如 `zero_candidates`、`below_min_candidates`、`duplicate_heavy_output`、`candidate_metadata_issue`、`unsupported_payload_format`。
- 內容格式 parser registry 要和 source detector 分開：CSV/JSON/GeoJSON 可 import；ZIP/TAR/NetCDF/HDF/GeoTIFF 先 manifest + adapter review；unknown 保留 raw artifact，不假裝可解析。
- Sciverse / OpenDataLab 暫時不要放進 STAC / CKAN / Socrata / OGC / CMR / ERDDAP 這條通用 geospatial source pattern 主線。它比較像低優先級的 `literature_discovery_api` / `vendor_science_api`：可用來找論文、DOI、資料集線索與 provenance，再把真正資料入口交給 STAC/OGC/CMR/ERDDAP/CKAN 等下載器處理。
- 測試使用 fake fetcher / fixture payload，不讓 CI 依賴 live NASA/NOAA/Socrata 網路結果。每新增 detector 至少要有正例 fixture、unknown fallback、不誤判其他範式的測試。

### K 槽概念樣本庫與 CODE_KM 心法

K 槽其他教材與 CODE_KM 不要當成可直接搬進 RRKAL 的程式碼來源，而要當成「概念樣本庫」：先判斷它補強的是 RRKAL 哪個 service boundary、哪個狀態閘門、哪個測試，再抽成小型、fixture-tested 的專案模組。

- 金融與風控教材：補 time-series asset、OHLCV/tick/kbar、交易日曆、補資料策略、風險摘要與 storage review；對應 yfinance / financial provider / time-series import。
- GIS、星圖、3D 與 antigravity_space：補 raster/tile/cache、bbox、projection、renderer-ready manifest、preview 與重型依賴 lazy import；對應 GEBCO/HYG、tile manifest、Taichi/Unreal bridge。
- 數學與機械工程教材：補 bounds/geometry/affine transform、polygon/intersection、tile overlap 與 renderer coordinate conversion；對應 `bounds_schema` 與 GIS/renderer bridge。
- Pandas / 資料清理教材：補 header normalize、missing value、type inference、schema fingerprint、bad row warning；對應 manual import 與 manifest importer。
- Fluent Python / PyMOTW / 架構教材：補 ABC/protocol、streaming iterator、context manager、argparse subcommand、concurrent futures；對應 crawler registry、content parser registry、CLI split、download/import pipeline。
- CODE_KM：最重要的是治理模型。`book/source provenance` 可映射為 dataset/source/file provenance；`OCR run` 可映射為 crawl/download/import run；`Notion staging/review/completed/restricted` 可映射為 candidate review、adapter review、curated asset promotion gate 與 rights/provenance gate；`local MySQL metadata` 可映射為 install registry / run registry / event log；`cleaner/reference skill` 可映射為 developer/client skill 分工。
- 權利邊界要前置：外部教材、站點、API 或 wrapper 只能當 metadata clue 或合法來源的處理參考；任何內容 ingest / redistribution / training suitability 都要先有 provenance 與 rights status。

## Git 維護路線

固定維護順序如下：

1. `K:\APIkeys_collection` 是雲端主工作區與提交正本。開發者日常在 IDE 看到的 Git 狀態，以這個資料夾為準。
2. 需要 GUI、showcase、完整 smoke 或可能被雲端碟延遲影響的測試時，才從 GitHub 或 K 槽建立本地測試 clone，例如 `C:\Users\lyn59\Documents\Codex\RRKAL_local_test\...`。
3. 本地 clone 只作為測試跑道，不作為長期提交來源。測試中找到的修復，必須回補到 `K:\APIkeys_collection`。
4. 回補完成後，先確認 K 槽工作樹，再從 K 槽 `commit` / `push` 到 GitHub。
5. push 後仍需用 GitHub Actions 驗證。不要把「本地 clone 通過」誤當成「雲端正本已同步」。

這條路線的目的，是讓 IDE / Git 面板永遠追蹤雲端正本，同時保留本地 clone 的高速、低鎖檔風險測試能力。

## 接手順序

1. 同步 Git：

   ```bash
   git pull origin main
   git status --short --branch
   ```

2. 讀文件：

   ```text
   docs/AGENT_START_HERE.zh-TW.md
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
   gh run list --repo kagamihara-rururka/APIkeys_collection --limit 5
   gh run watch RUN_ID --repo kagamihara-rururka/APIkeys_collection --exit-status
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

K 槽、本地 clone 與 GitHub 同步規則：

- `K:\APIkeys_collection` 是主工作區、日常閱讀資料夾、修復回補位置與 commit / push 來源。
- GUI、showcase、完整 smoke、壓力測試，優先在本地磁碟 clone 執行：`C:\Users\lyn59\Documents\Codex\RRKAL_local_test\...`。這個 clone 是證明環境，不是隱藏主線。
- 如果本地 clone 測到修復，必須把修復回補到 K 槽，再由 K 槽 commit / push。不要讓本地 clone 與 K 槽長期分岔。
- 需要展示資產時，從 K 槽同步 `state/showcase/` 到本地 clone；DB、log、臨時依賴、runtime SQLite 仍維持忽略，不當成正式原始碼。
- K 槽在雲端同步碟上，適合主工作區與資料潔癖管理，但可能遇到 pycache、SQLite、GUI 冷啟動或檔案鎖延遲。測試時使用本地 clone；若不得不在 K 槽跑測試，優先設定 `PYTHONPYCACHEPREFIX` 到 `%TEMP%`，避免 bytecode 鎖住雲端同步檔案。
- GitHub 是跨機器同步與 CI 證據來源。push 後仍要追 `gh run watch --exit-status`；通過後再把 handoff/GTD/展示資產狀態視為可交接。

切換平台或交給下一位 Agent 前，至少確認：測試通過、語法檢查通過、CLI smoke 通過、文件已更新、已 commit/push，並用 `gh run watch --exit-status` 確認 CI。

## 目前專案定位

RuRuKa Asset Launcher 是一個類 Steam 的科學資料集/資料庫 launcher。它不是單純 API key 管理器，而是要管理：

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
| 最新已驗證 checkpoint | 2026-05-25 Windows/K：`6994a61 Centralize crawler asset surface labels` 已推送，GitHub Actions run `26396895131` 成功。這是 Crawler Asset UX Contract 小切片：`source_surface_label()` 已改用 `SOURCE_SURFACE_LABELS` registry，WMS capabilities 在 UI card/passport 可標示為 `map_service`，file index 標示為 `file_index`，未知 API-like endpoint 仍有 shape fallback。前一個實質 checkpoint `2623dc4` 把 WMS capabilities 納入 entry-listing seed coverage。 |
| 最新本機驗證 | 2026-05-25 Windows/K：crawler asset surface label registry 已驗證。`6994a61` 本機驗證：crawler asset targeted tests 16 tests OK；`py_compile` OK；`git diff --check` OK；完整 `py -B -m unittest discover -s tests` 626 tests OK、skipped=4；`scripts\pre_push_smoke_brief.cmd` 通過：626 tests OK、skipped=4，MVP demo smoke `stage=download_import_completed`、`row_count=3`。完整本機 log 在 `state/logs/pre_push_smoke_20260525_185215.log`，不提交。 |
| 最新已推送 commit | 接力前請以 `git pull --ff-only origin main`、`git status --short --branch`、`git log -1 --oneline` 為準。最新實質功能 checkpoint 是 `6994a61 Centralize crawler asset surface labels`，CI run `26396895131` 成功；後續若只有 log / handoff 同步 commit，請視為文件狀態更新，不代表新的功能切片。 |
| 上次本機驗證 | 2026-05-20 macOS/Antigravity/CloudMounter：IDE 權限按鈕恢復後，這個 session 已不再輸出 `CODEX_SANDBOX=seatbelt` / `CODEX_SANDBOX_NETWORK_DISABLED=1`；`curl -I --max-time 5 https://github.com` 回 HTTP 200，`test -w /Users/yen-an/.codex` 回 `writable`，`git add` / `git commit` / `git push` / `gh run watch` 都不再需要升權。早前餘波修復：`APIkeys_collection.py` 曾被工作樹刪除，已用 HEAD 可讀內容補回；缺失 Git blob `a60de8185d6ad444079a35ede668b19b1e70c5fa` 經確認等於 `frontends/unreal/README.zh-TW.md` 工作樹 hash 後，用 `git hash-object -w` 補回。本輪驗證：real-driver smoke test `py_compile` OK；`tests.test_data_store_real_drivers` 4 tests skipped as intended；`tests.test_data_store_connections tests.test_data_store_real_drivers tests.test_database_self_check` 62 tests OK、skipped=4；`PYTHONPYCACHEPREFIX=/tmp/apikeys_collection_pycache python3 -m unittest discover -s tests -v`，346 tests OK、skipped=5（4 個 opt-in real DB smoke、1 個 optional numpy renderer dependency）；`git diff --check` OK；GitHub Actions run `26165313576` Windows/Ubuntu/real-db-smoke 全部 success。 |
| 本輪本機驗證 | 2026-05-24 Windows/K：Backend/Core hardening checkpoint `48bdbfb` 已驗證。temp `PYTHONPYCACHEPREFIX` `py_compile` 通過；`py -3 -m unittest tests.test_adapter_plan_resolver tests.test_dataset_download_plan -v` 共 63 tests OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過：510 tests OK、skipped=4，MVP demo smoke `stage=download_import_completed`、`row_count=3`；CI run `26346575874` Ubuntu、`windows-2025-vs2026`、real DB smoke 全部 success。完整本機 log 在 `state/logs/pre_push_smoke_20260524_073726.log`，不提交。 |
| Mac 接力準備 | Mac 端先 `git pull --ff-only origin main`，再用 `PYTHONPYCACHEPREFIX=/tmp/apikeys_collection_pycache conda run -n metal_trade_312 python -m unittest discover -s tests` 或至少先跑 `PYTHONPYCACHEPREFIX=/tmp/apikeys_collection_pycache conda run -n metal_trade_312 python -m unittest tests.test_discovery_drafts tests.test_launcher_ui tests.test_discovery tests.test_discovery_promotion -v`。不要把 Windows `K:\...`、`state/`、`downloads/`、`tem/` 或 ignored local config 當成 Mac 必備狀態；若 Mac 缺本機 local seeds/source drafts，可用 `--write-provider-candidate-source-drafts --provider-candidate-source-drafts-input state/provider_candidates.review.json` 從 review JSON 重建本機 source 草稿。 |
| 最近新增重點 | Heartbeat automation 已有 repo-owned 第一階段實作：`api_launcher/heartbeat.py` 會讀 handoff/GTD、Git status、最新 commit 與可選 CI 狀態，產生 `--heartbeat-report`、`--heartbeat-plan-json`、`--write-heartbeat-plan-json`、`--heartbeat-agent-prompt`；`scripts/heartbeat_check.ps1` 是原始 PowerShell 檢查入口，`scripts/heartbeat_agent.ps1` 可 dry-run 產生 prompt，或在 `safe_to_progress=true` 且明確傳入 `-RunAgent -AgentExecutable ...` 時呼叫外部 agent runner。Windows 使用者可改跑 `.cmd` wrappers，避免 Execution Policy 擋 `.ps1`；其中 `scripts\heartbeat_codex.cmd` 才是真正接本機 Codex CLI 的定時推進入口，會在安全檢查通過時把 prompt 餵給 `codex exec`。這不是聊天 thread 自己喚醒自己，而是讓 Windows Task Scheduler/其他外部排程每 45 分鐘呼叫 repo 內腳本。Archive bounded transform 現在支援 ZIP/TAR 內的 `csv.gz`、`json.gz`、`jsonl.gz`、`ndjson`、`ndjson.gz`、`geojson.gz`，會寫衍生 manifest 並接既有 CSV/JSON importer；regression 已覆蓋 ZIP 內 `sample.ndjson.gz` 與 TAR.GZ 內 `sample.geojson.gz` 匯入 SQLite。Registry/source provenance 也正式接受並保存 compound source format，例如 `csv.gz`、`jsonl`、`ndjson`、`geojson`、`geojson.gz`、`zip`、`tar.gz`；下載檔案 asset 與 CSV/JSON/GeoJSON 匯入後的 curated table asset 會記錄實際 payload format。Guarded SQLite table reimport 也會用同一組支援格式，且錯誤/UI 文案會列出支援清單；現在 CLI/agent 可用 `--reimport-missing-sqlite-table ASSET_ID --database-repair-json` 走同一個安全 guard，也可用 `--unmanage-database-asset ASSET_ID --database-repair-json` 做 registry-only 停止追蹤；兩者成功後都會寫入 `database_repair_completed` structured event log。下載 manifest verification 現在會透過共用 helper 寫 `download_manifest_verification_completed`，Tk repair panel 的 requeue button 會寫 `download_repair_requeue_requested`，讓 handoff report / `--show-logs` 能看到檔案健康掃描與重新排下載結果。本輪讓 opt-in real MySQL/PostgreSQL smoke tests 進一步覆蓋 registry-backed table self-check：`APIKEYS_REAL_DB_SMOKE_ALLOW_WRITE=1` 時才會建立/清掉 `apikeys_ci_registry_smoke_*` 測試表，確認 managed table asset 的 present/missing 狀態，並 ALTER 同一張 generated table 觸發 schema fingerprint drift error。`docs/SETUP.zh-TW.md` 已補本機 disposable Docker/env-var 指南；一般本機/Windows/Ubuntu 全量測試仍預設不連線、不 DROP、不覆蓋既有 table、也不猜測未記錄來源。文件面新增 `docs/DEVELOPMENT_LOG.zh-TW.md` 作為已推送 checkpoint 日誌；`PROJECT_STATE.md` 降級為長篇歷史狀態快照，避免它和 live handoff/GTD 互相搶權威。 |
| MVP 剩餘估算 | canonical MVP Demo closure 的剩餘量已收斂到 0%；`--run-mvp-demo-smoke-json` 可重寫 artifacts、跑完 `download -> manifest -> SQLite import`、回傳純 JSON 並驗出 `row_count=3`，且 `--handoff-report` / `--handoff-report-json` 現在會用 `MVP Readiness` / `mvp_readiness` 明確判斷最後一次 smoke 是否達到 `download_import_completed`、`succeeded=true`、`row_count > 0`。離線 MVP smoke 已納入本地 pre-push 與 GitHub Actions CLI smoke，Windows cp1252 stdout 也已用 UTF-8 guard 修復。download/import、handoff JSON、adapter review/resolver JSON、manual import、database self-check/repair dry-run、yfinance fixture/live guarded plan、Tk 引導與 structured events 都已有可回溯 checkpoint。GTD 裡剩下的 crawler/UI/database/renderer/lakehouse 待辦應視為 post-MVP hardening 或下一階段 checkpoint，不再把它們誤算成 canonical demo 的 MVP blocker。 |
| UI 入口 | `python3 APIkeys_collection_ui.py` 或 `py APIkeys_collection_ui.py` |
| Tk UI 實作 | `frontends/tk/launcher_ui.py`；可獨立封裝的 dialog class/workflow：`frontends/tk/dialogs.py`（provider edit、database client、data-store connection、developer CLI、language、startup checks、event logs、AI model settings、Google/Gemini connection settings、import existing-table policy settings、dataset candidate review、provider candidate review、Adapter review queue）；UI 設定/常數：`frontends/tk/ui_config.py`；狀態/修復文案：`frontends/tk/ui_labels.py`；純 helper 邊界：`frontends/tk/ui_helpers.py`；Provider table view-model：`frontends/tk/provider_models.py`；啟動/Tcl helper：`frontends/tk/startup_helpers.py`；桌面檔案管理器 helper：`frontends/tk/desktop_integration.py`；啟動 / 關閉 / 本機 DB lifecycle workflow：`frontends/tk/app_lifecycle_workflows.py`；AI summary/profile workflow：`frontends/tk/ai_summary_workflows.py`；provider edit/settings workflow：`frontends/tk/provider_settings_workflows.py`；側欄 / provider favicon workflow：`frontends/tk/sidebar_workflows.py`；細節抽屜 / responsive layout workflow：`frontends/tk/responsive_layout_workflows.py`；右側細節面板 workflow：`frontends/tk/detail_panel_workflows.py`；下載計畫面板 workflow：`frontends/tk/download_plan_panel_workflows.py`；provider/dataset 表格資料生命週期 workflow：`frontends/tk/table_data_workflows.py`；Treeview 欄寬 / 搜尋分類事件 workflow：`frontends/tk/table_interaction_workflows.py`；主視窗樣式 / 選單 / 第一層 layout workflow：`frontends/tk/window_layout_workflows.py`；yfinance guarded UI workflow：`frontends/tk/yfinance_workflows.py`；MVP Demo UI smoke workflow：`frontends/tk/mvp_demo_workflows.py`；repair / verify asset workflow：`frontends/tk/repair_workflows.py`；OAuth/login workflow：`frontends/tk/oauth_workflows.py`；download plan/job workflow：`frontends/tk/download_workflows.py`；import workflow：`frontends/tk/import_workflows.py`；download-plan composition / Adapter plan workflow：`frontends/tk/plan_workflows.py`；discovery/crawler audit workflow：`frontends/tk/discovery_workflows.py`；row action / library action / crawler dispatch workflow：`frontends/tk/source_action_workflows.py`。主檔 `frontends/tk/launcher_ui.py` 目前是 202 行 thin shell，後續不要把新業務流程塞回主檔。 |
| 使用者指南 | `docs/USER_GUIDE.zh-TW.md` |

## 使用者合作偏好與雷點

這一段是給下一位 Agent 的人類協作提示，不是產品規格。使用者很願意討論概念層，也能接受快速推進，但對「看起來做了、其實沒有閉環」很敏感。

- 2026-05-20 Antigravity IDE 更新後一度沒有吃到 `~/.codex/config.toml` 的 `danger-full-access` 設定，舊 session 顯示 `CODEX_SANDBOX=seatbelt`、`CODEX_SANDBOX_NETWORK_DISABLED=1`，因此早上曾採用偏保守的應急開發策略。使用者已確認 IDE 提供方妥善處理，這個危機目前已不復存在；後續應恢復穩健的正常流程：完成一個可驗證切片後本機測試、commit、push，並用 `gh run watch` 確認 CI。接力前仍可跑例行檢查：`env | sort | rg 'CODEX_SANDBOX|CODEX_SANDBOX_NETWORK_DISABLED'`、`curl -I --max-time 5 https://github.com`、確認 `.codex` 可寫；若未來又出現 sandbox/network disabled，視為新的環境異常再診斷，不要把早上的應急策略當成目前狀態。
- 開發策略已正式往 OpenSpec-aligned workflow 過渡。下一位 Agent 不要只把 OpenSpec 當成可選工具，而要把它視為新的協作規範方向與「專案習慣記憶」：凡是中大型、跨模組、會影響架構/資料模型/UI/外部整合的改動，先寫清楚「變更目的、範圍、任務、驗收標準、風險」再實作；反覆出現的開發習慣也應整理成 OpenSpec requirement / change / task，再讓 skill 指向它。小修、測試補強、窄範圍 bugfix 可以維持快速小步，但完成後要回補 GTD / handoff / 相關設計文件。正式 `openspec/` 目錄已建立，第一個 capability 是 `openspec/specs/development-workflow/spec.md`；這套模式已整理成可移植工作流骨架，未來搬到其他 repo 時只複製 GTD、handoff、development log、docs index、OpenSpec、project skill、smoke check、checkpoint report 這些治理形狀，不直接搬 APIkeys_collection 的 crawler/provider/database/renderer 專用規則。Spectra 是 OpenSpec 可視化工作台，不只服務 Qt 搬遷。macOS 可用 `~/Applications/Spectra.app`；這台 Windows 可用 `C:\Users\lyn59\AppData\Local\Spectra\spectra.exe`。Qt/Conda 工具跨平台分流，先用 `scripts\check_ui_tooling.cmd` 查本機事實。
- 匯報要面向初學者：少用抽象工程術語，多用白話說明「這一步解決什麼、還差什麼、為什麼重要」。每次中途或最後匯報，順手說明距離 MVP 還剩哪些大塊。
- 做到一個穩定節點就要 commit/push，並用 `gh run watch` 或 `gh run list` 確認 CI。使用者手機會收到 GitHub Actions 通知，所以不要只說 push 成功。
- 為了降低 token 用量，長輸出請優先用 repo-owned 簡報入口，例如 `.\scripts\pre_push_smoke_brief.cmd`。完整 log 會寫到 `state/logs/pre_push_smoke_*.log`，對話中只貼關鍵行與失敗尾端。外部 `distill` 只能當可選後處理；不要用它取代 raw log、JSON、SQL、CI、測試證據，也不要把可能含 secrets/env/credential 的輸出送去未知 provider。Windows 上若要用 `distill`，必須先確認 `distill.cmd --version` 成功；2026-05-22 實測 `@samuelfaj/distill@1.5.2` 缺 `@samuelfaj/distill-win32-x64` 平台包，尚不能視為可用。
- 不要在 base/system Python 裝套件；目前 macOS 主要使用 `conda run -n metal_trade_312 ...`。
- 遇到環境差異先配置，不要假設 Windows 路徑可在 Mac 用。尤其 Mac 啟動時要依系統選路徑分隔符與平台路徑，不要讓 Windows `K:\...` 類路徑阻擋 UI。
- 不要硬編碼代表資料集。使用者反覆強調 crawler-first：先找供應商/目錄，解析目錄，再產生候選；adapter 只處理 bounded query、auth、轉換、匯入等必要邏輯。
- Provider/source discovery UI 入口也要保持 metadata-only。`資料庫 > 發現 provider 候選` 只寫 `state/provider_candidates.ui.json` 供 review，不正式納管、不安裝、不抓 API key；`資料庫 > 審核 provider 候選` 只讀同一份 JSON、顯示 evidence 並開 source/docs。若使用者按「寫入本機 seed」，只會寫 ignored local provider discovery seed；若按「寫入 source 草稿」，也只會在候選已有明確或可保守推導的 supported crawler type/endpoint 時寫 ignored local dataset discovery source。兩者都不會寫正式 catalog；正式 catalog 仍應經 local config / crawler audit / promotion guard。
- Crawler 不能只看「程式沒報錯」。如果抓到 0 筆、低於預期、全是重複、重複候選異常偏高、payload shape 不符，都要明確 warning/error；使用者特別在意這種假成功。新 crawler audit 應盡量提供 `warning_codes` 與 `next_action`，並在 discover/local-promotion JSON 頂層保留 `audit_summary`，讓 UI/agent 能先看 `by_warning_code`、`by_next_action`、`problem_sources`，再判斷要修搜尋詞、修 parser、檢查去重/id mapping，或進入候選審核。Tk `資料庫 > 發現資料集候選` 與 `資料庫 > 審核本機 discovery 草稿` 已會把常見 `next_action` 翻成繁中下一步，warning dialog 也會先顯示整體 audit summary 再列逐 source 明細；後續不要退回只顯示 warning 文字。
- 未提交檔案或大改動不要擅自刪除、覆蓋、`git restore`。2026-05-17 曾發生誤還原事故，讓使用者很不安；任何看似奇怪的檔案都先備份/看 diff/產生 patch。
- UI 預設要繁中；如果新增 UI，放到合適的選單或設定，不要到處新增零散入口。使用者覺得 Tk UI 目前只是過渡，PySide/Qt 是中期路線，MVP 前不要重寫。
- 使用者喜歡產品概念層被記錄下來，例如 Steam-like library/install/workspace、renderer bridge、Hadoop/K8S、GIS/時間序列/多媒體資料類型。但實作時仍要先收束 MVP。
- 使用者老師提到 OpenSpec；使用者希望未來開發模式逐步往 spec-driven/changes/tasks/spec delta 靠攏。短期把它當成「中大型變更要有迷你規格與驗收標準」的流程方向，不要讓規格流程阻塞 backend MVP。OpenSpec CLI 透過 `npx -y @fission-ai/openspec@latest ...` 使用；Spectra 是 GUI 輔助，Git 裡的 `openspec/` 才是權威來源；skill 是執行時操作手冊，OpenSpec 是版本化專案契約。OpenSpec 不限英文：capability id、change id、CLI flag、路徑、`Requirement:`/`Scenario:` 等工具標記維持英文/ASCII；意圖、驗收標準、風險、交接提醒可用繁中或雙語。不要把任何 Python 套件裝進 base/system Python；macOS 可用 `metal_trade_312`，Windows 不可假設同名 env 存在。
- 使用者認為所有文件都重要；不要把任何 `.md` 當成可忽略雜檔。每次功能改動後，至少回頭檢查 `PROJECT_GTD.md`、`AGENT_HANDOFF.zh-TW.md`；跨平台或接力流程改變時，直接更新本文件的「跨平台接力檢查」段落，必要時再更新 `DOCS_INDEX.zh-TW.md`、`WORKSPACE_LAYOUT.zh-TW.md`、使用者指南或相關附錄，讓下一位 Agent 容易接力。
- 未來新增英文文件時，必須同時準備繁中版本，或至少在同一輪提交提供繁中摘要與清楚入口。若大幅更新現有英文文件，例如 `ARCHITECTURE.md`、`TECH_STACK.md`、`PROJECT_STATE.md`、`GIT_HANDOFF.md`，也要同步更新繁中閱讀路線；使用者不希望重要接力脈絡只留英文。
- 使用者明確提醒目前有過度編程風險。新增程式碼前先回答三問：它服務 MVP 哪一段（主線是 `seed -> crawler -> candidate -> plan -> download -> import -> UI`）、目前被哪個 CLI/UI/測試/文件流程入口使用、移除後 MVP 會不會受影響。Hadoop、K8S、P2P、mobile、完整 Google OAuth、多 AI profile、Qt migration、Spectra/OpenSpec GUI 等保留在文檔或 stub，不要搶 MVP 主線；不要為單一場景建立大型 base class / registry / strategy pattern。
- 使用者會提出發散想法；可以記錄到文檔/中期目標，但當前開發要常提醒「這次實際推進的是哪個 MVP 環節」。
- 使用者說「繼續推進」或暫離時，通常期待 Agent 自主完成下一個合理小階段：實作、驗證、更新文檔、git commit/push、查 CI。不要每個小選擇都停下來問，但遇到會破壞資料、刪檔、改秘密資訊、或安裝環境不明時要先保守處理。
- Heartbeat automation 的正確理解：repo 現在能產生檢查報告、JSON plan、外部 agent prompt，也有 PowerShell 腳本可被外部排程器呼叫；Codex 聊天本身不會無中生有定時喚醒。正式接上自動 agent 前，先用 `.\scripts\heartbeat_codex.cmd -DryRun` 做 dry-run，確認 `state/heartbeat/heartbeat_plan.json` 和 `state/heartbeat/agent_prompt.md` 符合預期；確認後才把 Task Scheduler 指到 `heartbeat_codex.cmd`。

## 最近完成

- Tk UI 實作檔已從 `frontends/tk/APIkeys_collection_ui.py` 改名為 `frontends/tk/launcher_ui.py`。
- Tk UI 從 IDE 或背景 shell 啟動後會自動浮出、短暫置前並印出 `RuRuKa Asset Launcher (RRKAL) UI ready ...`；相關 TclError suppressor 已收窄成只吞 Tk/Tcl 視窗生命週期錯誤，不再靜默吞掉非預期例外。
- Tk root 建立失敗時，`frontends/tk/launcher_ui.py` 的 `main()` 會攔截 `TclError`、寫入 `ui_tk_startup_failed` event、在 stderr 印出繁中修復建議並回傳 `2`。若錯誤提到 `init.tcl`、Tcl/Tk runtime 或 display，先用系統 Python 執行 `py -B APIkeys_collection_ui.py`；若要用 `.venv`，請以含 Tcl/Tk 的 Python 重建，不要混用 base/system Python 套件。
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
- `api_launcher/library_actions.py` 已提供 action map/order/menu-label helpers，Tk 右鍵選單已開始共用這套規則，並會把 `status_badge` 轉成繁中/英文短標籤顯示在選單項目後方。
- `api_launcher/library_actions.py` 已提供 agent-readable JSON payload；CLI 可用 `--show-library-actions PROVIDER_ID --library-actions-json` 讓未來 skill 重用同一套 action 規則。
- Tk UI 已新增 `Tools > Recent event logs`，可以直接查看 `state/logs/launcher_events.jsonl` 的近期事件。
- Tk UI 的 `工具 > 修復 / 驗證資產` 現在會開啟 repair panel，分成「下載檔案」與「資料庫」兩個分頁；下載檔案分頁列出每個 download manifest 的健康狀態與路徑，並會在驗證與重新排下載時寫入 structured event log。
- Repair panel 現在會顯示安全修復建議；對有 HTTP(S) `source_url` 和 `provider_id` 的 missing/size/checksum manifest，可用「重新排下載」透過 staging 重新排下載。
- HTTP downloader 已新增「已驗證下載重用」：如果目標檔案和 sidecar manifest 都正常，且 provider/dataset/version/source/path 符合目前下載請求，就不重新連網下載。Tk UI 也會記住實際送進下載器的 plan entry，版本下載完成時 registry 的 `source_uri` 不會誤寫成原 provider URL。
- 健康的下載 manifest 現在可登錄為 install registry 裡的 managed `file` asset；CLI `--verify-downloads` 與 Tk 下載完成流程會共用 `register_downloaded_manifest_asset()`。Database self-check 已限定只驗 `database` / `table` asset，避免把已下載檔案誤判成資料庫錯誤。
- Adapter 發現的 dataset version 現在可用 CLI `--export-dataset-plan PATH` 匯出成下載計畫。直接檔案 URL 會有 `download_url`/`target_path`/`use_staging`；入口頁或 selector 會標記成 `adapter_required` 並放在 `adapter_review_url`，不要直接交給 HTTP downloader。
- CLI `--run-download-plan PATH` 現在可執行 plan 裡的 direct entries，跳過 `adapter_required`，下載完成後驗 sidecar manifest 並登錄 managed filesystem `file` asset。可用 `--download-plan-limit N` 做小量 smoke test；若 agent/heartbeat 需要穩定讀取 stage、skip_summary、next_action、import 統計與 errors，請加 `--run-download-plan-json`，不要解析人類輸出字串。每次執行也會寫入 `download_plan_executed` structured event，`--handoff-report` 會列出最近一次 input plan、stage、counts、skip_summary 與 next_action。
- CLI `--write-mvp-demo-flow state/mvp_demo/flow.json` 現在可產生固定 MVP Demo Flow：會寫出 flow manifest、Socrata adapter review plan、agent-readable adapter review JSON、離線 JSON fixture、離線 direct plan 與下一步指令。CLI `--run-mvp-demo-smoke-json state/mvp_demo/flow.json` 則會重寫同一組 artifacts，直接跑離線 `download -> manifest -> SQLite import`，並輸出單一 JSON，包含 `stage`、`succeeded`、`table_name`、`row_count` 與 download/import 統計。它使用 `state/mvp_demo/launcher.sqlite` 隔離 demo registry；離線 plan 可穩定驗證核心閉環，Socrata `$limit=25` resolved plan 則用來驗證真實 adapter resolver。Tk UI 也已新增 `工具 > 產生 MVP Demo Flow`、上方 `更多 > 產生 MVP Demo Flow`、`工具/更多 > 一鍵驗證 MVP Demo Flow`。產生入口只寫出 `state/mvp_demo/*` 並把離線 direct plan 加到下方下載計畫；一鍵驗證入口則在背景用隔離 demo DB 直接跑 canonical 離線 smoke，完成後顯示 stage、table、row_count、artifact 路徑與失敗修復指引。後續不要把 demo 業務邏輯寫死在 Tk 裡。
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
- 2026-05-22 本地預檢：`scripts/pre_push_smoke.cmd` / `.ps1` 可在 push 前檢查 working tree、staged diff、有 upstream 時的 `upstream..HEAD` 待推送 diff，並跑核心 `py_compile`、完整 `unittest discover -s tests`、`--summary` 與離線 MVP demo smoke，同時用 temp pycache 避免 Windows/RaiDrive 鎖檔。`scripts/install_pre_push_hook.cmd` / `.ps1` 可把這條 smoke 安裝成該 clone 的 `.git/hooks/pre-push`；hook 是本機設定，不會進 Git。它負責把錯誤盡量擋在 push 前；push 後仍要跑 `gh run watch --exit-status`，讓遠端 checkpoint 留下可回溯 CI 紀錄。若真的需要繞過，使用 `git push --no-verify` 前要先確認風險。
- Tk UI 已把 plan-driven import 接成 guided action：下載計畫區有 `匯入` 按鈕，`資料庫 > 匯入可支援下載結果` 與「更多」選單也有入口。它會取目前 plan item / 實際下載 plan entry，交給 `api_launcher/ingestion_pipeline.py` 檢查 sidecar manifest、登錄 downloaded manifest asset，再對 `import_plan.status=supported_after_download` 的 CSV/JSON/GeoJSON 項目匯入 `state/curated_imports.sqlite`。下載計畫與下載工作表會顯示匯入狀態/table hint，例如待下載/驗證、可匯入、已匯入、需 adapter、需解壓/adapter。匯入確認框若同時有可匯入與略過項目，會列出略過原因預覽，並指向 Adapter 待辦、解析 Adapter 計畫、下載或 manifest 健康狀態，避免只顯示 skipped 數量。目前不做 destructive replace；若 table 已存在，UI 會自動改名成下一個可用 table，例如 `table_2`，避免覆蓋使用者資料；若共用 helper 回傳 `skipped_existing_table` 這類狀態，UI 會顯示為「略過」，不顯示成失敗。
- `--verify-downloads-json` 已提供下載檔驗證的 agent-readable JSON：包含 summary、issues、repair suggestion、以及 HTTP(S) manifest 可安全重排下載的 plan entry。repair suggestion 現在也帶 `outcome_bucket`、`next_action`、`adapter_id`、`review_hint`，可分辨 `requeue_ready`、`manifest_parse_error`、`source_url_missing`、`adapter_source_missing`、`adapter_source_not_requeueable`、`provider_id_missing` 等狀態；有 adapter metadata 時，下一步會指向 adapter review / resolver，而不是假裝可以自動重排。若要指定掃描資料夾，可搭配 `--downloads-root PATH`。每次 CLI/Tk manifest 掃描後都會寫入 `download_manifest_verification_completed` structured event，記錄 checked/issue/requeue counts 與最多 20 筆 issue preview；Tk requeue button 也會寫 `download_repair_requeue_requested`，記錄 queued / already_active / not_requeueable / failed 與 job/error context，方便 `--show-logs` 和 handoff report 回溯最近一次檔案健康檢查。
- Library action agent payload 現在可接同一條下載 repair suggestion stream：`--show-library-actions PROVIDER --library-local-status imported --library-install-id INSTALL --library-repair-manifest PATH --library-actions-json` 會驗 sidecar manifest，把 `manifest_health` 與 `related_repair_suggestion` 掛在 `repair` action 上；每個 action 也帶 `status_badge`（例如 `ready_to_plan`、`repair_requeue_ready`、`guarded_uninstall_ready`），供 UI/agent 顯示或 routing。Tk 右鍵選單會用 `library_action_menu_label(..., include_status_badge=True)` 顯示「可加入計畫」、「可重排修復」、「可受控移除」等短標籤，但實際執行仍要看 `enabled`、`risk` 與 guarded CLI 參數。Tk 右鍵 repair action 也改為開共享 `修復 / 驗證資產` panel，避免 UI 另走一套 repair policy。
- Tk UI 新增 `設定 > 介面語言`，語言存在 `launcher_integrations.local.json` 的 `ui_language`。預設是 `zh-TW`；新開啟 dialog 會套用，主畫面完整套用需重新啟動。後續碰 UI 時應優先補齊繁中顯示與 `tr(...)` 英文 fallback。
- Tk UI 的登入/串接入口已集中到上方 `整合` 選單：`AI / Gemini 串接中心`、`保存 Gemini API key`、`AI 輔助模型選擇`、`Google OAuth（中期 / 開發者）`、資料儲存連線與資料庫工具都在這裡。主工具列和右側抽屜不要再新增登入/API key/資料庫工具設定入口；抽屜只保留目前資料源的動作。
- AI 生成描述目前以功能閉環為優先：Gemini API key 是 MVP 雲端路線，`api_launcher/ai_api_keys.py` 會把 key 存在 ignored `state/private/ai_api_keys.private.json`，UI 啟動時只會自動載入 saved API key；不要在啟動時 activate Google/OAuth token、打開瀏覽器、打開本機設定檔或叫出 OAuth 設定。`generate_provider_summary()` 也會嘗試載入 saved key。使用者只應在缺 credential 時被要求保存 key，不要每次重貼。
- Google OAuth / QR 是中期正式目標，不是不做；只是現在 MVP 尚未閉環，先不要讓它阻塞 AI 描述生成。一般使用者不該被要求貼 Desktop OAuth Client ID；若沒有專案官方 OAuth App，就顯示尚未開通。開發者仍可透過 `整合 > Google OAuth（中期 / 開發者） > 開發者 OAuth 設定` 測試，格式不像 `*.apps.googleusercontent.com` 的值會被拒絕保存，避免重複觸發 Google `invalid_client`。
- PySide6 / Qt 已列為中期 UI 升級路線：不要現在重寫 UI；先完成 backend/MVP 閉環。後續若啟動 Qt，應新增 `frontends/qt/` 並重用 `api_launcher`、library actions、event logs、download queue、integration contracts，不要把業務邏輯複製進 UI。Windows Qt Creator / PySide6 環境目前仍是準備項，先跑 `scripts\check_ui_tooling.cmd`；截至 2026-05-22，這台 Windows 有 Spectra 2.3.1 與 `py3_12_13`，但沒有 Qt Creator、沒有 PySide6、也沒有 macOS 的 `metal_trade_312`。Provider icon/favicons 的中期方向是 SVG/vector-first；Tk 可保留可重建 bitmap cache 作顯示相容層，但不要把 PNG 當成 canonical icon asset。
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
- macOS 目前已安裝 GitHub CLI (`gh`)；GitHub 帳號已由 `YanAnnLu` 改名為 `kagamihara-rururka`，查 CI run/log 時使用 `kagamihara-rururka/APIkeys_collection`。
- 海域法域資料請記住：領海、EEZ、爭議區、公海不是單純座標戳，而是帶法律/行政屬性的 GIS polygon 圖層。MySQL spatial 可做 MVP；較完整 GIS 分析、切 tile、空間索引應優先考慮 PostGIS；原始資料保留 GeoPackage/Shapefile/GeoJSON 與 manifest。
- 團隊開始共同尋找資料庫入口網站時，請先寫入 `docs/DATABASE_PORTAL_INTAKE.zh-TW.md`。這是組員用的入口收集表，不要貼 API key/token/cookie；只記網站、API 文件、授權、入口類型、主題、地理範圍與是否需要登入。CLI 已有 `--portal-intake-report --write-portal-intake-json state/portal_intake.review.json`，會把表格整理成 provider seed 草稿、dataset discovery source 草稿、crawler mapping 待辦、adapter/integration backlog 或 incomplete warning；`--promote-portal-intake-local` 只會把乾淨草稿寫進被 Git 忽略的 `config/provider_discovery_seeds.local.json` 與 `config/dataset_discovery_sources.local.json`，不直接改正式 catalog。草稿要進正式 catalog 時，用 `--promote-local-discovery-catalog --write-local-discovery-audit-json state/local_discovery_audit.json`；這會先跑 crawler audit，只有 error=0/warning=0 的 local dataset source 才會寫入正式 catalog。
- `docs/DATASET_DISCOVERY_NOTES.zh-TW.md` 是重要 discovery 主入口，不是暫存雜檔；crawler-first、爬蟲資產 / Crawler Asset、candidate review、bounded resolver、adapter handoff、dataset-version plan 的新規格都應寫在這裡。`docs/appendices/discovery.zh-TW.md` 只保留 redirect/摘要，避免舊 handoff、skill 或 prompt 引用失效。
- 2026-05-22 已補「爬蟲資產 / Crawler Asset」概念：它是 API 搜集器的概念擴充，代表可治理、可版本化、可審核、可排程、可修復的資料取得能力；它不取代 Provider、Dataset、DatasetDiscoverySource、Adapter 或 Mission，而是把現有 crawler/source/resolver/event-log 流程包成產品層。短期不要為此硬加大型 registry；等 UI/健康檢查/repair mission 需要時，再把它提升成正式資料模型。
- 2026-05-24 已把 crawler asset 三能力槽正式化到 `api_launcher/crawler_asset_capabilities.py`：`fetch_metadata`、`list_datasets`、`build_download_plan`。每槽帶 input/output contract、credential mode、terms risk、error buckets 與 bounds facets；舊 `download_selected` 只是 UI 相容別名。後續 Tk/Qt/CLI 產生界域表單時要讀這份 contract，不要在 UI 內各自猜欄位。
- 2026-05-24 已把 crawler asset profile 與 health 拆成後端契約：`api_launcher/crawler_asset_profiles.py` 保存啟用/封存、credential profile、API key env var、帳號提示、排程、限流、重試、seed scope、Logo/favicon/授權備註；`api_launcher/crawler_asset_health.py` 統一產出 `status_code`、emoji、reason、warning、next_action。Tk/Qt/CLI 都應讀這兩個契約，不要各自重建失效判斷或憑證欄位。
- 2026-05-24 第二個切片新增 `api_launcher/crawler_asset_bounds.py`，將 facets 提升為 bounds schema：每個 facet 有 group/control/value type/maps_to/required/options/help，並對應 TimeBounds、SpatialBounds、ColumnBounds、VersionBounds、LimitBounds、AuthBounds 等概念。請優先重用這份 schema 與既有 `api_launcher.bound_form` / `SourceDownloadBounds`，不要為 crawler card、Qt 或 CLI wizard 重寫另一套界域表單規則。
- 2026-05-24 Tk 已有第一版 crawler asset profile 編輯入口：`frontends/tk/crawler_asset_profile_dialog.py` 只收集 profile reference（credential profile、API key env var、帳號提示、排程、限流、重試、Logo/favicon 等），實際驗證與保存交給 `update_crawler_asset_profile()`。UX 規則：爬蟲分頁用明確「爬蟲設定」按鈕或未來齒輪進設定；下載器清單雙擊才代表把選中項目啟動/送入下載，不要把雙擊拿去開設定。
- 近期 GTD 加入 Notion-backed seed intake：使用者打算開一個 Notion 分頁/資料庫給組員維護入口網站清單。Notion 應視為雲端 intake/staging，不是正式 catalog 權威；未來 sync 指令應把 Notion rows 轉成與 `docs/DATABASE_PORTAL_INTAKE.zh-TW.md` 相同的 review JSON / local seed / local dataset source，再跑 crawler audit，通過後才提升正式 catalog。注意 sync 要記 provenance，避免不清楚 seed 從哪列 Notion 來。
- 工作區分類已新增 `docs/WORKSPACE_LAYOUT.zh-TW.md`，並提供 CLI `--workspace-inventory --write-workspace-inventory-json state/workspace_inventory.json`。這是盤點工具，不會自動搬檔或刪檔；下一位 Agent 整理 `.py` 前請先用它看大檔案、分類與 root runtime files。`api_launcher/cli_flags.py` 已先把 CLI command-detection 從 `core.py` 拆出來，後續 core 瘦身要沿用這種小步、可測、保守拆分方式。
- `tem/` 已正式定義成本機暫存資料夾，並由 `.gitignore` 排除。它可以保存外部 agent 交接包或概念素材，但不是 canonical source of truth；團隊協作者與 CI 都不會看到本機 `tem/` 內容。下一位 Agent 若從 `tem/` 讀到有用資料，應把摘要或正式檔案搬進文件/原始碼後再提交。
- Crawler 共用資料結構已從 `api_launcher/crawlers/dataset_sources.py` 拆到 `api_launcher/crawlers/types.py`。舊的 `dataset_sources.py` 匯入路徑仍可用，這是為了相容既有 CLI/UI/測試；新程式若只需要 `DatasetDiscoverySource` 或 `DatasetCandidate`，優先從 `api_launcher.crawlers.types` 匯入。
- Crawler 共用 metadata helper 已拆到 `api_launcher/crawlers/metadata.py`，HTTP fetch/JSON/URL helper 已拆到 `api_launcher/crawlers/fetch.py`，共用 full-crawl page cap 與候選去重 append helper 已拆到 `api_launcher/crawlers/pagination.py`，STAC collection payload parser、source-level fetch/parse flow 與 STAC pagination flow 已拆到 `api_launcher/crawlers/stac.py`，CKAN package query URL builder/payload parser/source-level fetch/parse flow/pagination flow 已拆到 `api_launcher/crawlers/ckan.py`，ERDDAP `allDatasets` source-level fetch/parse flow 已拆到 `api_launcher/crawlers/erddap.py`，NASA CMR collection query URL builder/payload parser/source-level fetch/parse flow/pagination flow 已拆到 `api_launcher/crawlers/cmr.py`，GBIF dataset search query URL builder/payload parser/source-level fetch/parse flow/pagination flow 已拆到 `api_launcher/crawlers/gbif.py`，Dataverse search query URL builder/payload parser/source-level fetch/parse flow/pagination flow 已拆到 `api_launcher/crawlers/dataverse.py`，Zenodo records query URL builder/payload parser/source-level fetch/parse flow/pagination flow 已拆到 `api_launcher/crawlers/zenodo.py`，DataCite `/dois` query URL builder/payload parser/source-level fetch/parse flow/pagination flow 已拆到 `api_launcher/crawlers/datacite.py`，OGC API Records query URL builder/FeatureCollection parser/source-level fetch/parse flow/pagination flow 已拆到 `api_launcher/crawlers/ogc_records.py`，Socrata catalog query URL builder/payload parser/source-level fetch/parse flow/pagination flow 已拆到 `api_launcher/crawlers/socrata.py`，OpenAlex Works query URL builder/payload parser/source-level fetch/parse flow/cursor pagination flow 已拆到 `api_launcher/crawlers/openalex.py`，HTML file index source-level fetch/parse flow 已拆到 `api_launcher/crawlers/html_index.py`，NCEI search query URL builder/payload parser/source-level fetch/parse flow/pagination flow 已拆到 `api_launcher/crawlers/ncei.py`。`dataset_sources.py` 目前主要保留 `SOURCE_CRAWLER_HANDLERS` dispatcher mapping、limit/search_terms 正規化與舊匯入相容；`SUPPORTED_DATASET_SOURCE_TYPES` 會給 portal intake 共用，避免同一份 crawler type 清單在不同地方手抄漂移。
- CLI handoff report 已補 portal intake / local discovery 摘要與進度焦點：`--handoff-report PATH` 現在會列出 generated time、MVP Readiness、manifest/asset/verification event 的最近驗證時間、最近 Adapter review / resolver / download plan 執行摘要、最近 MVP demo smoke 的 stage/succeeded/table/row-count 摘要、從 `PROJECT_GTD.md` 解析出的 open GTD focus、portal intake rows/actionable/warnings/local provider seeds/local dataset sources，以及從 Markdown/Notion staging 進 local config，再經 crawler audit promote 到 catalog 的指令流。Suggested Resume Checks 也包含 `--run-mvp-demo-smoke-json`，讓下一位 agent 可直接重跑 canonical 離線 MVP 閉環。若 heartbeat 或外部 agent 需要直接解析同一份 snapshot，可用 `--handoff-report-json` 輸出純 JSON stdout；JSON 內的 `mvp_readiness` 是判斷 canonical MVP demo 是否已可交付的穩定欄位，post-MVP hardening 不應被算成 demo closure blocker。
- 第 1 項目前已調整為「善用 crawler 發現 provider/source 與 dataset candidates」，不要把每個代表資料集都硬寫成 Python adapter。`catalog/APIkeys_collection_catalog.json` 目前有 55 個 provider seed，新增方向包含 NOAA GOES-R on AWS、NOAA NOMADS、Marine Regions、GADM、OpenStreetMap Overpass、U.S. Census TIGERweb、EMODnet ERDDAP、Harvard Dataverse、Zenodo、DataCite、OpenAlex、WMO WIS2 Global Discovery Catalogue、Canada/UK/Australia/HDX CKAN、NYC/DataSF/Chicago Socrata portals，以及 optional/unofficial 的 `Yahoo Finance via yfinance`。`catalog/dataset_discovery_sources.json` 描述可爬的資料目錄，目前 23 個 source；`api_launcher/crawlers/orchestrator.py` 統一調度 source crawlers，並行執行、去重、收斂 per-source error/warning、`warning_codes` 與 `next_action`；`api_launcher/crawlers/fetch.py` 已放共用 HTTP fetch/JSON/URL helper；`api_launcher/crawlers/pagination.py` 已放共用 full-crawl page cap 與候選去重 append helper；各 source 模組已接手 query URL builder、payload parser、source-level fetch/parse flow 與 full-crawl pagination flow；DataCite DOI search 會用 public `/dois` API 與 `resource-type-id=dataset` 產生 metadata-first 候選，並只把明確 `contentUrl` 留作可審核 resource 線索；OpenAlex Works search 會用 `type:dataset` 產生研究資料 metadata 候選；WMO WIS2 source 會用 OGC API Records 產生天氣/觀測 metadata 候選；Socrata catalog crawler 會從 Catalog API 產生 resource 候選，刻意保留 `/api/views/{id}` metadata URL 與 bounded resolver 可用的 `/resource/{id}.json` metadata，不把整張表直接當 direct file。`api_launcher/crawlers/dataset_sources.py` 目前主要保留 dispatcher、limit/search_terms 正規化與舊匯入相容。Crawler 審核不能只看「沒報錯」：0 筆候選、低於 `min_expected_candidates`、只抓到全域重複候選、重複候選異常偏高、payload shape 不符、候選缺少 evidence/source url 都要提示或失敗。CLI `--discover-dataset-candidates --write-dataset-candidates ...` 與 local discovery promotion audit JSON 都會帶 `next_action`；Tk 發現完成提示會把常見 `next_action` 轉成繁中修復方向；常見值包含 `repair_crawler_query_or_parser`、`review_source_overlap_or_dedupe`、`repair_candidate_metadata_mapping`。未來新增供應商時，優先新增/配置 crawler，由 orchestrator 調度；不要讓特殊網頁邏輯散進 UI 或 core。AIS 與衛星雲圖是代表測試案例：AIS 應由 MarineCadastre index 發現 shards，衛星雲圖應由 NOAA/NCEI/GOES-R/Earth Engine/STAC 類 catalog 發現 raster/grid 候選。
- Dataset candidates 現在有初步 review loop：repository 可列出/標記 candidate status，CLI 可用 `--list-dataset-candidates`、`--dataset-candidates-json`、`--review-dataset-candidate UID --dataset-candidate-decision approved|planned|rejected`，Tk UI 在 `資料庫 > 審核資料集候選` 可查看、開來源、標記可用/拒絕或加入目前下載計畫。主列表也會把 crawler 匯入的 dataset 顯示成 provider 底下的縮排列；`資料庫 > 在列表顯示 crawler 資料集` 可切換。這仍是 metadata-only registry 狀態，不會下載或改動資料本體。
- Crawler candidates 現在可以進一步輸出成後端 plan：CLI `--export-candidate-plan PATH --candidate-plan-status approved|needs_review|planned|all` 會把候選 dataset/version 轉成與 adapter 共用的 dataset-version plan schema。每個 entry 都有 `download_eligibility`、direct 檔案的 `target_path`、`dataset_version`、`candidate_review`，以及保守的 `import_plan`。CSV/JSON 類標成可在下載驗證後進 SQLite MVP importer；CSV.ZST/ZIP/TAR 類標成需要解壓或 adapter；API/landing page 保持 adapter review。UI 的候選加入下載計畫也改走 `provider_dataset_version_plan_entry()`，避免把入口頁當成 direct download。
- Socrata candidate-plan path 現在有明確 regression：crawler-style candidate -> `--export-candidate-plan` -> `resolve_adapter_review_plan_payload()` 會產生 bounded `$limit=25` direct sample，且 `tests/test_dataset_download_plan.py` 會檢查 import plan 是 `supported_after_download`。這保護的是「會列出資料集」到「能安全下載/匯入小樣本」的中間接縫。
- Tk UI 下載計畫已從 provider_id-only 購物車升級成 plan item key：provider-level row 還能用，但 candidate review 或 dataset version action 加入的是 `provider::dataset::dataset_uid::version` 這類 key。這代表同一資料商底下可以同時排多個資料集/版本，不會互相覆蓋。注意內部仍有一些 legacy dict 名稱叫 `*_by_provider`，短期其實是用 plan_key 當 key；後續若整理 UI state，先看 `selected_plan_items()` / `provider_id_for_plan_key()`。
- Tk UI 下方下載計畫面板現在可用「收合下載計畫 / 展開下載計畫」切換；收合只隱藏 cart/job table body，標題列、計畫名稱、項目數與開始/匯入/暫停/重試/移除/匯出等主要動作仍保留。這個切換不會取消背景下載 queue，也不改變 plan item state；後續 UI polish 不要把它誤寫成停止下載或清空計畫。
- Dataset-version plan entries 現在對 non-direct 或需解壓/轉換的項目會帶 `adapter_review` 區塊：`adapter_id`、`source_url`、`required_action`、`expected_output`、`reason`。Adapter 待辦 payload / CLI / Tk panel 也會補 `outcome_bucket`，例如 `source_resolution_required`、`downloaded_payload_transform`、`import_adapter_required`，summary 會有 `by_outcome`。這是後續 adapter-specific repair / non-direct adapter 的接手契約；不要再只靠 UI 字串「需 adapter」判斷下一步。
- `api_launcher/adapter_review.py` 會把 plan 裡的 `adapter_review` / adapter-required / unpack-needed entries 整理成 agent-readable queue。CLI 可用 `--adapter-review-plan PATH`、加 `--adapter-review-json` 印出 JSON，或用 `--write-adapter-review-json PATH` 寫出同一份 agent-readable payload；寫檔時會記錄 `adapter_review_json_written` structured event。Tk UI 在 `資料庫 > Adapter 待辦` 與「更多 > Adapter 待辦」可查看目前下載計畫裡的待辦、來源 URL 與 required action。
- `api_launcher/adapter_plan_resolver.py` 是第一個 non-direct plan resolver：CLI `--resolve-adapter-plan INPUT --write-resolved-adapter-plan OUTPUT` 會掃描 CKAN/Data.gov/NCEI/CMR/STAC/Zenodo 類候選常見的 `dataset_version.metadata.resources` / `distribution` / `distributions` / `links` / JSON-LD `@graph`，也認得 `dcat:distribution` 這類 JSON-LD compact key，只把看起來已經是 direct file URL、或 resource metadata 明確標成 CSV/JSON/ZIP 等支援格式的 URL 提升成 direct download plan entry，並重建 `target_path`、`download_eligibility`、`import_plan`；成功寫出 resolved plan 時會記錄 `adapter_plan_resolved` structured event，`--handoff-report` 也會固定列出最近一次 resolved plan 的輸出路徑與 direct/resolved/unresolved/warning 統計。若 heartbeat/agent 需要機器可讀摘要，加 `--resolve-adapter-plan-json` 可讓 stdout 只輸出 resolver summary JSON。泛用 resource reader 現在認得 `download_url`、`downloadURL`、`contentUrl`、`fileUrl`、`url`、`href` 等 direct-link 欄位，以及 `dcat:downloadURL`、`schema:contentUrl` 等命名空間欄位；欄位值可為字串、list 或 `{"@id": "..."}` 物件；格式提示可用 `mediaType`、`contentType`、`encodingFormat`、`dct:format`、`dcat:mediaType`，大小提示可用 `byteSize`、`contentSize`、`dcat:byteSize` 或 `{"@value": "..."}`；只有 `{"label": "CSV download"}` 這類純標籤物件不會被誤當成 direct URL。宣告超過 100 MB 的 resource 會留在 review，不自動下載。若 CKAN/Data.gov plan 只有 `package_show` URL，或只有 `package_search` URL 加 dataset id，resolver 也能只查一次單一 package metadata，再挑安全 direct resource；它不掃整個 CKAN catalog。ERDDAP candidate 若帶 `erddap_protocols`，會讀官方 `info/{dataset}/index.json`，產生最多 25 列/最小維度切片的 sample CSV plan entry，讓下載與 SQLite 匯入流程能先閉環；不要把這當成完整大量下載。Tk UI 已有 `資料庫 > 解析 Adapter 計畫`、上方 `更多 > 解析 Adapter 計畫`、以及 `Adapter 待辦 > 解析可下載 resources`。HTML、API selector、登入頁、`accessURL` 或未知格式仍留在 adapter review；這是 bounded plan rewrite，不是無頭亂爬整站。
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
8. 維護 `docs/AGENT_START_HERE.zh-TW.md` 作為最短入口，`docs/AGENT_HANDOFF.zh-TW.md` 作為最新接力卡；未來若要做 `.codex/skills/apikeys-collection-launcher`，應等 MVP 閉環穩定後再產品化成消費端/操作端技能。
9. Tk UI 主檔解耦已收束到 thin shell；後續若要 UI polish 或 Qt/PySide6 前置工作，新增 workflow/view-model 邊界，不要把 row action、crawler dispatch、repair/install/uninstall 流程搬回 `launcher_ui.py`。
10. Backend/Core Hardening 已完成 yfinance CLI compatibility slice、database-repair CLI slice、download-plan CLI slice 與 manual/local-file import CLI slice；下一刀仍只選一個可測邊界：CSV/JSON manifest import CLI 群組，或 `adapter_plan_resolver.py` 的 source-specific resolver 拆分。DB migration runner、真實 subcommands、crawler dynamic discovery、credential catalog 化、simulation/Unreal feature gating 或 experimental 目錄搬遷仍需 OpenSpec 先定義相容、rollback 與 CI gate。
11. 繼續依 `docs/WORKSPACE_LAYOUT.zh-TW.md` 拆分大型 `.py`：短期 `dataset_sources.py` 已接近純 dispatcher；下一批若碰 `core.py`，先做 compatibility wrapper 或 migration ledger 這種可測小切片。
12. 下一個中大型 crawler/adapter/UI/Hadoop/K8S/Backend-Core 改動請開始走 OpenSpec change 流程，或至少在 `openspec/changes/` 留 proposal/tasks/acceptance criteria；小修不必硬開厚規格，但要保持 GTD/handoff 同步。

## 開發守則

- 每完成一個功能，要更新 `docs/PROJECT_GTD.md`。
- 每次跨機器或跨 Agent 接力，要更新這份 `docs/AGENT_HANDOFF.zh-TW.md`。
- 一輪對話可以包含多個實質 checkpoint commit；合理時可以把同一 MVP 主題下的相鄰小切片連續推進，但每個 commit 仍要可審查、可驗證、可由 CI 回溯。每次完成並推送實質 checkpoint 後，要追加 `docs/DEVELOPMENT_LOG.zh-TW.md`，記錄開發階段、commit、變更範圍、驗證、CI 與剩餘風險；但如果某個 commit 唯一目的只是同步開發日誌，不要再為該 log-sync commit 追加下一筆日誌，避免「更新日誌 -> push -> 再更新日誌」的遞迴。
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
你正在接手 APIkeys_collection。請先讀 docs/AGENT_START_HERE.zh-TW.md，再讀 docs/AGENT_HANDOFF.zh-TW.md 與 docs/PROJECT_GTD.md。不要依賴上一段聊天紀錄。

先執行 git pull origin main、git status --short --branch、python3 -m unittest discover -s tests。本機 Codex/macOS 環境請優先用 conda env：conda run -n metal_trade_312 python -m unittest discover -s tests；不要把套件裝進 base/system Python。

push 後請用 gh run watch 追 CI。Windows 失敗時優先檢查 SQLite/file handle、路徑與 `.pyc` 鎖。SQLite 短生命週期連線要用 contextlib.closing。

目前第 1 項已經改成 crawler-first：provider/source discovery 找供應商與入口，dataset discovery sources 找資料集候選，adapter 只在 crawler 候選需要 bounded query/auth/transform/import 時才寫。請優先看 `catalog/dataset_discovery_sources.json`、`api_launcher/crawlers/types.py`、`api_launcher/crawlers/metadata.py`、`api_launcher/crawlers/fetch.py`、`api_launcher/crawlers/pagination.py`、`api_launcher/crawlers/ncei.py`、`api_launcher/crawlers/stac.py`、`api_launcher/crawlers/ckan.py`、`api_launcher/crawlers/erddap.py`、`api_launcher/crawlers/cmr.py`、`api_launcher/crawlers/gbif.py`、`api_launcher/crawlers/dataverse.py`、`api_launcher/crawlers/zenodo.py`、`api_launcher/crawlers/datacite.py`、`api_launcher/crawlers/ogc_records.py`、`api_launcher/crawlers/socrata.py`、`api_launcher/crawlers/openalex.py`、`api_launcher/crawlers/html_index.py`、`api_launcher/crawlers/orchestrator.py`、`api_launcher/crawlers/dataset_sources.py`、`api_launcher/cli_dataset_discovery.py`、`api_launcher/plans.py`、`api_launcher/adapter_review.py`、`api_launcher/adapter_plan_resolver.py`、`api_launcher/importers/archive_importer.py`。Crawler candidates 已能用 `--export-candidate-plan` 轉成 dataset-version download/import plan；Tk UI cart 也已從 provider_id 級別提升到 dataset_uid/version plan item；`import_plan` 也已接成下載後 guided import，並能在 cart/job table 顯示匯入狀態與 table hint；table 衝突會安全自動改名；non-direct/transform-needed plan entry 已帶 `adapter_review` handoff，CLI/UI 都能列出 Adapter 待辦；`--resolve-adapter-plan` 與 UI `解析 Adapter 計畫` 可先把 CKAN-like resources 裡的 direct file URL 提升成 direct entries，或在缺 resources 摘要時對 CKAN `package_show` 做單一 metadata lookup；也可把 Dataverse latest-version metadata 轉成未受限小檔 direct entries、把 ERDDAP metadata 轉成 bounded sample CSV entry、把 STAC collection 轉成 `limit=1` item metadata、把 CMR collection 轉成 `page_size=1` granule metadata，且 CMR granule links 會區分 metadata/service rel 與 explicit data/download/enclosure asset link、把 Socrata/SODA v2-style resource 轉成 `$limit=25` 小樣本、把 NOAA/NCEI Search entry 轉成 `limit=25&offset=0` metadata sample，並在有 dataset 加站點/空間條件時只查 1 筆 NCEI data metadata、把小於 100MB 的 `/data/...` CSV direct file 提升成下載項目，也能把已具備 dataset/date/spatial 邊界的 NOAA/NCEI Access Data query 轉成 CSV/JSON 小樣本；DataCite DOI/OpenAlex DOI 可只查一次 DataCite metadata 並把明確 `contentUrl` direct file 提升成下載項目；ZIP/TAR 壓縮包已有 bounded transform adapter。Database self-check UI 現在可針對單一 database/table asset 調整 `data_store_profile_id` / `schema_name`；UI/CLI 可停止追蹤該 asset，或對 manifest-backed missing SQLite table 做不覆蓋既有 table 的 guarded reimport。下一步重點是 import policy polish、擴大 guarded repair 覆蓋、或少量 crawler source 類型。AIS 與衛星雲圖是代表測試案例，但不要再把每個資料集硬寫成 Python 類別。使用者也希望未來往 OpenSpec-like workflow 靠攏：中大型變更先有簡短 proposal/tasks/acceptance，再實作與驗證，但目前不要因此拖慢 MVP。

若要整理工作區或拆大型 `.py`，先讀 `docs/WORKSPACE_LAYOUT.zh-TW.md`，再跑 `conda run -n metal_trade_312 python APIkeys_collection.py --workspace-inventory --write-workspace-inventory-json state/workspace_inventory.json`。這只產生盤點，不會搬檔；任何搬移/刪除前都要看 `git status --short` 並保護使用者/上一位 Agent 的未提交成果。

注意：SQL-only connection layer 已被合併到 api_launcher/data_store_connections.py，不要重新建立 sql_connection_profiles 或 sql_connections.py。

注意：未提交內容一律視為使用者或上一位 Agent 的成果。若檔案看似不符合目前架構，先備份/產生 patch 並說明風險，再決定是否收斂。

注意：專案開發策略已改往 OpenSpec-aligned workflow。中大型改動請先建立或更新規格/變更說明，再實作；若 GUI/CLI OpenSpec 工具尚未完成配置，至少先在 handoff/GTD/相關 docs 留下 proposal、tasks、acceptance criteria。不要回到純聊天記憶式開發。
```
## 展示模式交接備註

中午展示與後續進度說明可重跑以下命令，產生被 `.gitignore` 排除的本機展示材料：

```powershell
py -3 -B APIkeys_collection.py --write-dataset-seed-coverage state/showcase/dataset_seed_coverage.json --write-dataset-seed-coverage-md state/showcase/dataset_seed_coverage.md --dataset-discovery-max-pages 3
```

GUI 可用 `scripts\run_showcase_ui.cmd` 啟動；開發者仍可用 `py -3 -B APIkeys_collection_ui.py`。展示者不需要修改程式碼或打 CLI。穩定展示入口包含：

- `工具 > 展示模式：產生 seed 覆蓋報告` 或主畫面 `更多 > 展示模式：產生 seed 覆蓋報告`：只讀 source catalog metadata，不做網路爬蟲、下載或資料庫寫入。
- `工具 > 展示模式：下載資料到本機資料夾`：讓展示者選資料夾與樣本筆數上限，從公開 Socrata demo source 實際下載 payload/manifest，並在選定資料夾內建立 `RuRuKa Asset Launcher Showcase\curated_showcase.db`。
- `工具 > 展示模式：大型 CSV 續傳下載`：把完整 CSV 匯出排入既有下載面板，展示者可用 `暫停` / `繼續` 演示 .part 續傳；這條線只寫 CSV/manifest 到本機資料夾，刻意短路 SQL 匯入。

資料夾選擇預設導向系統 Downloads；若使用者手動選雲端同步資料夾，不要排除或阻擋，只要保留重試、manifest 與 .part 續傳行為。雲端資料夾可能比較慢或偶發鎖檔，因此展示/文件要說明它可用但不是速度假設。不穩定或仍在實驗中的完整 seed / 全來源下載 / SQL 匯入流程應留在開發或審核分流，不要混入穩定展示入口。

`state/showcase/` 現在是可追蹤的展示資產資料夾，用來保存小組展示稿、PPT、樣本資料、截圖與壓力測試回顧；`pptx_deps/`、本機驗證下載輸出、SQLite、log 仍維持忽略。一般使用者預設下載位置已改到系統 Downloads 下的 `RuRuKa Asset Launcher/downloads`，預設 curated SQLite DB 是 `Downloads/RuRuKa Asset Launcher/curated_imports.db`；開發/CI 可以繼續用 `--downloads-root` 與 `--import-sqlite-db` 覆寫。

Windows 上 `K:\APIkeys_collection` 是主工作區與提交來源；GUI、展示、完整 smoke、或任何容易受雲端同步碟影響的測試，應先 clone 到 `C:\Users\lyn59\Documents\Codex\RRKAL_local_test\` 的地端副本，必要時再從 K 槽複製 `state/showcase` 展示資料。測試通過後，把確認過的修復回補 K 槽再提交與推送。

若要粗顆粒展示「完整 seed 嘗試」而不是安全抽樣 `search_terms`，可加 `--dataset-discovery-complete-seed`，並用 `--dataset-discovery-max-pages` 控制頁數上限。這是 seed / candidate 探索，不是無限制下載。
## 急改 / 壓力測試交付規則

展示切片可以粗顆粒、短路到本機資料夾、先避開尚未穩定的 SQL/MySQL/PostgreSQL 或長期轉接器細節，但不能降低真實性。GUI 需要接實際 backend 狀態，不要用假的百分比或裝飾性進度條；簡報、講稿與輸出檔需要被程式讀回或人工打開驗證，不能只確認檔案存在。

壓力測試結束後，需要把可重複的教訓回收進 skill / GTD / OpenSpec。這次展示急改的結論是：未來 Agent 要預期「現場快速交付」會發生，平常就要保持模組化與可組合的 service boundary，讓實驗性功能可以被包成可驗證的展示流程，而不是臨時塞進主程式。

後續接力時請先分清兩條線：防禦性編程線負責穩健實現正式產品功能，包含完整 guard、測試、契約、文件與可維護邊界；快速交付線負責用最短且安全的 GUI 路徑重現已存在或可驗證的產品能力，服務現場說明、組員展示與壓力測試。快速交付可以降低功能顆粒度，但不能降低真實性；其產出應回頭變成防禦性編程的骨架與補強方向。

未來 Agent 開工前要先判斷目前模式。日常開發模式以小切片、防禦性測試、文件一致性與低風險重構為主；快速交付 / 展示模式以穩定 GUI、真輸出、真進度、可操作流程、備援路徑與講稿/簡報可重產為主。使用者不一定會明說完整場景，因此若提到「中午展示、給組員看、現場操作、快速交付、只剩 X 分鐘」等語境，預設進入快速交付 / 展示模式。

Agent 自我改進規則：每次壓力測試、壞假設、突發 timeout、簡報亂碼、UI 啟動失敗或使用者糾正後，都要在收尾前提取一條可重用教訓。格式是：明確命名漏掉的假設、把它轉成下次可觸發的 guardrail、更新最小耐久 artifact（測試、GTD、handoff、OpenSpec 或 skill）、能驗證就驗證，最後回報剩餘風險。這是 agent 執行品質的一部分，不算額外產品 scope。

### 2026-05-24 壓力測試辯證摘要

命題：快速交付容易污染主線。它會誘惑 Agent 把短路徑、展示文案、臨時 fallback、未完成的 UI 控制塞回正式程式，導致後續維護者分不清哪些是產品能力、哪些只是展示補丁。

反命題：沒有快速交付壓力測試，主線會低估真實交付情境。這次展示前才暴露出 PPT 亂碼、GUI 實際啟動、真百分比、資料夾選擇、Socrata timeout、fallback 說明與「展示者不能改程式碼」等需求；這些不是枝節，而是正式產品遲早會遇到的使用者場景。

合題：快速交付應被視為受控壓力測試，而不是例外流程。它的任務是在最短時間內重現已存在或可驗證的產品能力，並用真資料、真狀態、真輸出保住可信度；壓力測試後再把成功的短路徑拆回防禦性編程線，補上契約、測試、錯誤處理、文件、OpenSpec 與可維護邊界。

未來 Agent 需要主動做的判斷：使用者在 vibe coding 時不一定會提供完整場景，因此只要出現展示、會議、組員、現場操作、PPT、GUI、時間倒數、快速交付等訊號，就先切換到「人類可操作交付」思維。此時最重要的問題不是「架構是否最漂亮」，而是「使用者能否在不改程式碼的情況下穩定演示真實能力」。

這次得到的硬規則：

- 展示模式可以縮小範圍，但不能造假；若遠端 API timeout，fallback 必須明示來源與原因。
- 進度條必須接 backend 事件；無 `Content-Length` 時只能顯示已收 bytes 或流程階段，不能捏造下載百分比。
- 簡報、講稿、GUI 啟動腳本與輸出檔都是交付物；產生後要能讀回或打開驗證。
- 快速交付的服務函式要放在可回收的位置，避免藏在巨大 UI 檔或一次性腳本裡。
- 壓力測試後要列出「要回收成正式功能」與「仍是展示分流」的邊界，讓下個 Agent 不會誤判進度。
## UI/UX 開發提醒

UI/UX 需求不得只靠聊天比喻直接實作。若使用者提到 Foxy、Steam、tem 或其他軟體，先萃取互動精神與心流，不自動沿用其命名。中大型 UI 變更先查 `docs/UI_UX_DEVELOPMENT_CONTRACT.zh-TW.md`，把操作對象、入口、觸發方式、狀態變化、後端服務、錯誤狀態與驗收方式整理清楚，再進入 Tk / Qt 程式碼。當前雙擊語意保留給下載器清單項目啟動；爬蟲設定使用明確齒輪或「爬蟲設定」按鈕。
