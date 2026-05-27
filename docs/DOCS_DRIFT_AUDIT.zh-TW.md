# 文件漂移審計

最後更新：2026-05-27 18:52 Asia/Taipei

本文件記錄 RRKAL 文件是否仍對齊實際專案狀態。它不是 roadmap，也不是產品規格；它是「文件可不可信」的審計紀錄。

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
- GUI-level Web audit：用 in-app browser 開啟本機 Web Preview，確認四個工作區「爬蟲資產 / 下載器 / 匯入審核 / 事件紀錄」可見；切到「下載器」後可見「執行真下載示範」且文字仍定位為 transitional demo helper；選取 NASA Earthdata CMR 後可見「需要登入 / API Key」、官方登入入口與「記住我的帳號」設定流程，且主文案沒有把 `.env` 當成一般使用者操作語言。
- Web API / DOM audit：`/api/crawler-assets` 回傳 23 張資產卡；`/api/crawler-assets/noaa_ncei_dataset_search/seeds?page=1&page_size=50` 回傳 49 筆本機 seed 視窗與 `next_action=seed_page_complete`；`/api/crawler-assets/nasa_earthdata_cmr_collections` 回傳 credential status `missing_credentials`、label `需要登入 / API Key`、3 個 credential 欄位；靜態 HTML/JS 中存在四分頁、`執行真下載示範`、`顯示更多 seed`、`記住我的帳號`、`/credentials`、`/seed-favorites`。
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
- `gh run list --repo kagamihara-rururka/APIkeys_collection --limit 5`：最新 run `26489024004` 對應 `170b236`，狀態 `completed success`
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
