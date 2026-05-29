# 文件漂移審計

最後更新：2026-05-28 07:45 Asia/Taipei

本文件記錄 RRKAL 文件是否仍對齊實際專案狀態。它不是 roadmap，也不是產品規格；它是「文件可不可信」的審計紀錄。

## 第五輪補洞：整體進度改用成熟度矩陣（2026-05-28）

這一輪把「之後不能再用單一 94% 回答整體進度」從對話規則落成可驗證 artifact。

已落地的 verified behavior：

- 新增 `api_launcher/project_maturity.py`。
- CLI 新增 `--project-maturity-json`、`--write-project-maturity-json`、`--project-maturity-markdown`。
- 新增 `docs/PROJECT_MATURITY_MATRIX.zh-TW.md`，定義 `deliverable_100`、`implemented_bounded`、`partial_bounded`、`contract_only`、`planned_not_started`、`hardening_needed`。
- 成熟度矩陣會把 canonical MVP demo closure 的 `closure_percent=100` 放在 `canonical_delivery_scope`，並明確保留 `not_product_scope`。

文件口徑：

- 可以寫：可交付小閉環是 100%。
- 可以寫：整體專案要用成熟度矩陣回答。
- 不可以寫：整體 RRKAL 是 94%、100%，或任何未定義邊界的單一百分比。

後續若新增第二條 bounded closure，例如某個 public live source 的完整 `seed -> bounds -> download -> import -> UI` 路徑，應新增自己的 readiness artifact 或矩陣 row，而不是覆蓋 canonical MVP demo 的 100%。

## 第四輪補洞：小閉環 100% 與整體成熟度拆分（2026-05-28）

這一輪處理「為什麼有目標但永遠不到 100%，如何交付客戶」的交付口徑問題。結論是：客戶交付必須以 bounded closure 判定 100%，不能用無邊界的全產品願景百分比。

已落地的 verified behavior：

- 新增 `--mvp-readiness-json` / `--write-mvp-readiness-json`。
- 新增 `api_launcher/mvp_readiness.py`，輸出 `closure_id=canonical_mvp_demo_closure`、`closure_percent`、verified steps、blockers、warnings、rerun commands。
- 實跑 canonical smoke：`download_import_completed`、`row_count=3`。
- 實跑 readiness：`status=ready_for_mvp_demo`、`closure_percent=100`、`blockers=[]`、`warnings=[]`。

文件口徑：

- 可以寫：canonical offline Socrata 311 MVP demo closure 已 100%。
- 不可以寫：RRKAL 全產品、所有 crawler、所有 adapter、renderer / simulation bridge、Qt/Web ecosystem 已 100%。
- 之後使用者問「整體進度多少」時，必須回成熟度矩陣；單一百分比只能用在明確 bounded deliverable。

同輪魯棒性修補：

- `event_log.latest_events()` 已改為檔尾 bounded 讀取，避免大型 JSONL 讓 handoff/readiness MemoryError 或超時。
- `log_event()` 已移除每筆事件的 `platform.*` 阻塞 probe，改用 `os.name` / `sys.version` 提供非阻塞平台欄位。
- `api_launcher/rendering_profiles.py`、`api_launcher/platform_paths.py`、`api_launcher/environment.py`、`api_launcher/integrations.py` 已移除一般啟動 / renderer profile / integration profile 路徑上的 `platform.system()` / `platform.machine()` 阻塞 probe，改用 `sys.platform` / 環境變數做保守推斷。
- `scripts/pre_push_smoke.ps1` 已補 K/RaiDrive upstream 探測 guard；若 optional `git rev-parse @{u}` 偶發讀不到 cwd，會跳過 pending-push diff 而不是直接中斷 smoke。

## 第三輪補洞：源碼成熟度邊界審計（2026-05-28）

這一輪不是重新推翻第二輪文檔審計，而是補上第二輪漏掉的判準：文件不能只寫「已有 crawler / adapter / bridge」，還必須說清楚它落在哪一個成熟度層級。否則 agent 會把「已有 contract」誤讀成「已能真實執行」，或把「source handler 已接」誤讀成「內容 parser / importer / renderer 都已完成」。

已查證的源碼事實：

- `api_launcher/simulation_bridge.py` 目前是 simulation input/backend contract。backend 的 `implementation_status` 仍是 `contract_only`，不能被寫成已實作物理模擬引擎。
- `api_launcher/unreal_bridge.py` 目前只產生 Unreal bridge target plan，狀態是 `planned`，且刻意不在該層複製檔案或改動 Unreal project content。不能被寫成已完成 Unreal Content 實體導入。
- `api_launcher/dataset_adapters.py` 目前集中註冊 provider-specific dataset adapter，實體為 GEBCO、HYG、yfinance 三條。這不等於整個 source pattern / crawler 系統只有三個來源，也不等於 14 個 source type 都有 deep dataset adapter。
- `api_launcher/crawlers/dataset_sources.py` 的 `SUPPORTED_DATASET_SOURCE_TYPES` / `SOURCE_CRAWLER_HANDLERS` 代表 source-level crawler handler contract，可用來做 discovery / candidate enumeration / offline audit smoke；它不是內容格式 parser、curated SQLite importer、renderer bridge 或 full live download coverage 的保證。
- `api_launcher/adapter_plan_resolver.py` 與 `api_launcher/adapter_plan_resolvers/` 是 bounded resolver / adapter-review bridge，目標是把候選 metadata 安全提升成小樣本 direct plan 或 review item；它不代表每個平台的大量資料都已可無界下載。
- `api_launcher/content_registry.py` / import plan contract 目前已能把 CSV/JSON/GeoJSON 等可匯入格式與 NetCDF/GeoTIFF/ZIP/unknown 等 review lane 分開；停在 review lane 的格式不得寫成已可 curated import。

後續文檔一律使用以下成熟度語彙，避免模糊宣稱：

| 成熟度 | 可寫成 | 不可寫成 |
| --- | --- | --- |
| `contract_only` | 已定義資料結構、介面或輸入契約 | 已實作引擎、已可執行 |
| `planned_io` | 已能產生檔案/bridge/export 計畫 | 已完成實體複製、匯入或外部專案修改 |
| `offline_contract_smoke` | fixture / offline smoke 通過 | live endpoint 全部可用 |
| `live_discovery` | 可向指定 live source 枚舉候選 | 可下載或匯入資料本體 |
| `bounded_plan_resolver` | 可把候選提升成小樣本 plan 或 review item | 可全量下載該平台所有資料 |
| `download_ready` | 有 direct download plan 且通過 downloader/manifest | 已 curated import 或 renderer-ready |
| `import_ready` | 可進 SQLite / manifest import | 已有所有 domain parser / renderer bridge |
| `ui_operable` | Tk/Web 已可操作該流程 | 後端所有來源都完成 |
| `ci_verified` | 對應測試 / smoke / CI 通過 | 未覆蓋的 live source 也通過 |

處置：

- `DATASET_DISCOVERY_NOTES.zh-TW.md` 已補上 source crawler、provider-specific dataset adapter、adapter resolver、content parser/importer、renderer/simulation bridge 的分層界線。
- `PROJECT_GTD.md` 與 `AGENT_HANDOFF.zh-TW.md` 已把這次視為 docs drift guard 的補洞 checkpoint。
- 後續若文件說「支援某 source type」，必須同時說明它是 discovery、bounded plan、download、import、renderer bridge 還是哪一層支援。

## 第二輪審計摘要（2026-05-27）

第二輪審計從 commit `f580450 Align docs with verified drift audit` 開始，並在 `1e08e21 Complete documentation drift audit` 完成第一批推送。後續 GUI-level audit 補上 Web/Tk 實際行為對照，目標是把第一輪留下的使用者文件、Web/Tk 文件、架構文件與 encoding 風險補到可交接狀態。

已驗證行為：

- `git status --short --branch`：乾淨，`main...origin/main`。
- `git log -1 --oneline --decorate`：`1e08e21 (HEAD -> main, origin/main, origin/HEAD) Complete documentation drift audit`。
- GitHub Actions：run `26491482241` 對應 `1e08e21`，已 success。
- `py -B APIkeys_collection.py --handoff-report-json`：可成功輸出；provider count 55、dataset count 1、canonical MVP demo `download_import_completed`、table `nyc_open_data_socrata_socrata_311_sample_190`、`row_count=3`。
- `py -B APIkeys_collection.py --crawler-run-summary-json`：目前 `summary_scope.status=missing_listing`，表示本機 event window 沒有最新 crawler asset listing event；這不是 crawler 全壞，而是 freshness 證據不足。
- `py -B APIkeys_collection.py --dataset-discovery-handler-smoke-json`：14 個 supported source type 的離線 handler contract smoke pass；這是 offline contract，不代表 live NASA/NOAA/CKAN endpoint 均可連線。
- Web Preview in-process HTTP smoke：`/api/health`、`/api/crawler-assets`、`/api/diagnostics/crawler-handler-smoke`、`/api/events/recent` 均回應；crawler asset card 數 23，developer diagnostics `supported_source_type_count=14`、`candidate_case_status=pass`。
- Encoding / mojibake：`AGENT_START_HERE.zh-TW.md` 以 Python strict UTF-8 與 `Get-Content -Encoding UTF8` 讀取正常。若 PowerShell 預設輸出顯示亂碼，應視為 console/codepage 顯示風險，不能直接判定檔案損壞。
- GUI-level Web audit：用 in-app browser 開啟本機 Web Preview，確認四個工作區「爬蟲資產 / 下載器 / 匯入審核 / 事件紀錄」可見；後續 demo route cleanup 後，「下載器」主 CTA 已對齊為正式 `下載 / 匯入目前資產`，舊 `執行真下載示範` 不再是一般使用者主流程。選取 NASA Earthdata CMR 後可見「需要登入 / API Key」、官方登入入口與「記住我的帳號」設定流程，且主文案沒有把 `.env` 當成一般使用者操作語言。
- Web API / DOM audit：`/api/crawler-assets` 回傳 23 張資產卡；`/api/crawler-assets/noaa_ncei_dataset_search/seeds?page=1&page_size=50` 回傳 49 筆本機 seed 視窗與 `next_action=seed_page_complete`；`/api/crawler-assets/nasa_earthdata_cmr_collections` 回傳 credential status `missing_credentials`、label `需要登入 / API Key`、3 個 credential 欄位；靜態 HTML/JS 中存在四分頁、正式 `下載 / 匯入目前資產`、`顯示更多 seed`、`記住我的帳號`、`/credentials`、`/seed-favorites`，且不再包含 `realDownloadDemoButton` 或 `執行真下載示範` 作為一般 UI。
- Tk audit：`frontends/tk/window_layout_workflows.py` 確認主分頁順序為「爬蟲資產」第一、「下載器」第二；工具選單仍有三個展示模式入口與「開發者：Crawler handler diagnostics」。`tests.test_tk_dialogs` / `tests.test_launcher_ui` 的 targeted headless tests 已覆蓋下載器雙擊、開始/暫停主按鈕、爬蟲資產送進下載器、developer diagnostics 與 dialog 文案。
- Formal Web download/import audit：本輪 Web 下載器主 CTA 已從「執行真下載示範」改成「下載 / 匯入目前資產」，正式路徑為 `POST /api/crawler-assets/{asset_id}/download-import`。本地 temp/downloads live smoke 已驗證 public Socrata asset 可完成 `download_import_completed`、`submitted=1`、`completed=1`、`imported=1`；K/RaiDrive live import 曾遇到 SQLite `database is locked`，因此文件已補上 GUI/smoke/展示下載匯入要用本地 clone 或本機 Downloads/Temp 的規則。
- 18:52 follow-up：舊一般路由 `POST /api/demo/real-download` 已移除並回 404；同一條 public CSV proof helper 僅保留在 developer diagnostics 路由 `POST /api/diagnostics/real-download-demo`，payload 會標示 `developer_only=true` 與正式主/seed 下載 endpoint。16:25 以前提到「執行真下載示範」的審計文字只作歷史證據，不代表目前使用者主流程。

本輪已修正 / 標註：

- `USER_GUIDE.zh-TW.md`：新增目前校準狀態，明確標示 crawler listing freshness 目前缺最新 listing event；將「真下載示範 / 展示模式」標成過渡與 demo-only surface。
- `WEB_PREVIEW_UIUX.zh-TW.md`：新增 Web API smoke 驗證值，並標示 `/api/demo/real-download` 是 transitional helper，不是正式全 crawler 下載證明。
- `USER_MANUAL.zh-TW.md`、`MVP_FLOW_AUDIT.zh-TW.md`：補上 2026-05-27 校準註記，避免舊 demo 文件被誤讀成最新 Web/Tk 操作總綱。
- `TECHNICAL_OVERVIEW.zh-TW.md`、`ARCHITECTURE.zh-TW.md`：補上校準註記，把它們定位為架構背景與邊界文件；最新能力仍以 verified behavior、GTD、handoff、專題文件為準。
- 全域 skill 已補強 UTF-8 explicit rule 與 Python strict scanner；RRKAL docs 也已用 scanner 驗證無 mojibake 風險。
- `PROJECT_GTD.md`、本文件、`AGENT_HANDOFF.zh-TW.md`、`DEVELOPMENT_LOG.zh-TW.md` 補上 GUI-level audit 完成紀錄，並把 12:55 文檔審計從本地 `WORKING` 對齊到已推送 checkpoint。
- `USER_GUIDE.zh-TW.md`、`WEB_PREVIEW_UIUX.zh-TW.md`、`CODE_HEALTH_AUDIT.zh-TW.md` 已把 Web 主流程從舊 demo CTA 對齊到 formal crawler asset download/import endpoint；舊 `/api/demo/real-download` 已不再暴露為一般 API，developer-only regression helper 改走 `POST /api/diagnostics/real-download-demo`，不能再被寫成正式使用者主流程。

## 本輪審計範圍

本輪是第一輪快速但實質的文檔漂移審計，重點是權威入口與接力文件：

- `docs/AGENT_START_HERE.zh-TW.md`
- `docs/AGENT_HANDOFF.zh-TW.md`
- `docs/PROJECT_GTD.md`
- `docs/DOCS_INDEX.zh-TW.md`
- `docs/DEVELOPMENT_LOG.zh-TW.md`

未做完整逐行驗證的文件：

- `docs/USER_GUIDE.zh-TW.md`
- `docs/USER_MANUAL.zh-TW.md`
- `docs/WEB_PREVIEW_UIUX.zh-TW.md`
- `docs/ARCHITECTURE*.md`
- `docs/TECHNICAL_OVERVIEW.zh-TW.md`
- 較舊 feature docs 與 appendices

## 已驗證現況

驗證命令與結果：

- `git status --short --branch`：`## main...origin/main`
- `git log -1 --oneline --decorate`：`170b236 (HEAD -> main, origin/main, origin/HEAD) Log CKAN pagination output checkpoint`
- `gh run list --repo Kagamihara-Ruruka/APIkeys_collection --limit 5`：最新 run `26489024004` 對應 `170b236`，狀態 `completed success`
- 主要近期文件存在且可讀：`AGENT_HANDOFF`、`PROJECT_GTD`、`DATASET_DISCOVERY_NOTES`、`DOCS_INDEX`、`DEVELOPMENT_LOG`

## 已發現並修補的漂移

### 1. Handoff 最新 HEAD 漂移

`docs/AGENT_HANDOFF.zh-TW.md` 的「Git / CI status」仍寫：

```text
最新已推送 HEAD：3ca9a37 Add CKAN remote pagination output
```

但 verified behavior 顯示目前 HEAD 是：

```text
170b236 Log CKAN pagination output checkpoint
```

處置：

- 已將 handoff 最新 Git / CI status 對齊到 `170b236` / run `26489024004`。
- 已在 handoff 最上方新增本輪 docs drift audit / current verified status，提醒後續 agent 不要把較舊段落當成目前真相。

### 2. 入口文件權威順序過時

`AGENT_START_HERE.zh-TW.md` 原權威順序把本文件排在 verified behavior 前面，容易讓 agent 盲信文件。

處置：

- 已新增「文檔漂移防護」。
- 已把權威順序改為：使用者最新指令 -> 已驗證行為 -> handoff/GTD -> 入口/索引文件 -> specs -> feature docs -> 歷史日誌與參考資料。

### 3. Docs Index 未標出文檔漂移審計入口

`DOCS_INDEX.zh-TW.md` 原本沒有告訴 agent 如何處理文件漂移。

處置：

- 已新增文檔漂移防護原則。
- 已新增「檢查文件是否漂移」閱讀路線。
- 已把本文件加入主文件地圖。

## 已知剩餘漂移風險

這些不是已確認錯誤，而是本輪刻意不納入「文件漂移審計完成」定義的外部風險：

1. Handoff 過長，較舊段落仍含當時的「最新」用語。
   - 最上方最新 section 已修正權威狀態；已把明顯的「最新穩定 checkpoint」舊語句改成歷史 checkpoint。其餘舊段落暫視為歷史證據，不逐段重寫。
2. Live external endpoint coverage 不屬於本輪文件審計。
   - 本輪確認的是 UI/API contract、offline handler smoke、Web/Tk 文件對齊，不代表 NASA/NOAA/CKAN/Socrata 等每個外部入口都已 live network 成功下載。
3. Tk 桌面視覺手動驗收沒有在 K 槽直接開 GUI。
   - 本輪用程式碼入口與 headless tests 驗證 Tk 行為契約；正式展示前仍應依專案規則在本地 clone 啟動 Tk 做速度與畫面驗收。

## 後續建議

大規模文件審計目前可視為結束。下一輪應回到產品主線，但保留以下維護規則：

1. 後續每個功能 checkpoint 都要做 docs drift check，而不是等下一次大審計。
2. 若改 Web/Tk UI 文案或按鈕，至少跑對應 targeted tests，並用 Web API / DOM 或本地 clone GUI 驗證一次。
3. 若改 crawler/source pattern/download/import 行為，優先補 CLI JSON / fixture tests，再更新 user-facing docs。
4. 將 handoff 的超長歷史段逐步瘦身，把穩定歷史移到 `DEVELOPMENT_LOG.zh-TW.md` 或專題文件，只保留最新接力與風險。

## 本輪結論

目前已知文件漂移已做最小修補，Web/Tk 使用者文件與實際可查證行為沒有留下會阻擋下一輪主線開發的矛盾。下一輪開發仍必須先用 verified behavior 建立現況，但不需要再中斷主線做一次大規模文檔審計。
