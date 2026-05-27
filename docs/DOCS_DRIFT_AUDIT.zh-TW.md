# 文件漂移審計

最後更新：2026-05-27 12:55 Asia/Taipei

本文件記錄 RRKAL 文件是否仍對齊實際專案狀態。它不是 roadmap，也不是產品規格；它是「文件可不可信」的審計紀錄。

## 第二輪審計摘要（2026-05-27）

第二輪審計從 commit `f580450 Align docs with verified drift audit` 開始，目標是把第一輪留下的使用者文件、Web/Tk 文件、架構文件與 encoding 風險補到可交接狀態。

已驗證行為：

- `git status --short --branch`：乾淨，`main...origin/main`。
- `git log -1 --oneline --decorate`：`f580450 (HEAD -> main, origin/main, origin/HEAD) Align docs with verified drift audit`。
- GitHub Actions：run `26490857279` 對應 `f580450`，已 success。
- `py -B APIkeys_collection.py --handoff-report-json`：可成功輸出；provider count 55、dataset count 1、canonical MVP demo `download_import_completed`、table `nyc_open_data_socrata_socrata_311_sample_190`、`row_count=3`。
- `py -B APIkeys_collection.py --crawler-run-summary-json`：目前 `summary_scope.status=missing_listing`，表示本機 event window 沒有最新 crawler asset listing event；這不是 crawler 全壞，而是 freshness 證據不足。
- `py -B APIkeys_collection.py --dataset-discovery-handler-smoke-json`：14 個 supported source type 的離線 handler contract smoke pass；這是 offline contract，不代表 live NASA/NOAA/CKAN endpoint 均可連線。
- Web Preview in-process HTTP smoke：`/api/health`、`/api/crawler-assets`、`/api/diagnostics/crawler-handler-smoke`、`/api/events/recent` 均回應；crawler asset card 數 23，developer diagnostics `supported_source_type_count=14`、`candidate_case_status=pass`。
- Encoding / mojibake：`AGENT_START_HERE.zh-TW.md` 以 Python strict UTF-8 與 `Get-Content -Encoding UTF8` 讀取正常。若 PowerShell 預設輸出顯示亂碼，應視為 console/codepage 顯示風險，不能直接判定檔案損壞。

本輪已修正 / 標註：

- `USER_GUIDE.zh-TW.md`：新增目前校準狀態，明確標示 crawler listing freshness 目前缺最新 listing event；將「真下載示範 / 展示模式」標成過渡與 demo-only surface。
- `WEB_PREVIEW_UIUX.zh-TW.md`：新增 Web API smoke 驗證值，並標示 `/api/demo/real-download` 是 transitional helper，不是正式全 crawler 下載證明。
- `USER_MANUAL.zh-TW.md`、`MVP_FLOW_AUDIT.zh-TW.md`：補上 2026-05-27 校準註記，避免舊 demo 文件被誤讀成最新 Web/Tk 操作總綱。
- `TECHNICAL_OVERVIEW.zh-TW.md`、`ARCHITECTURE.zh-TW.md`：補上校準註記，把它們定位為架構背景與邊界文件；最新能力仍以 verified behavior、GTD、handoff、專題文件為準。
- 全域 skill 已補強 UTF-8 explicit rule 與 Python strict scanner；RRKAL docs 也已用 scanner 驗證無 mojibake 風險。

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

這些不是已確認錯誤，而是尚未逐一驗證的高風險區：

1. 使用者操作文件可能落後於實際 UI。
   - 需對 `USER_GUIDE.zh-TW.md`、`USER_MANUAL.zh-TW.md`、`WEB_PREVIEW_UIUX.zh-TW.md` 做 Tk/Web 實際操作對照。
2. Handoff 過長，較舊段落仍含當時的「最新」用語。
   - 最上方最新 section 已修正權威狀態；已把明顯的「最新穩定 checkpoint」舊語句改成歷史 checkpoint。其餘舊段落暫視為歷史證據，不逐段重寫。
3. 架構與技術總覽文件較舊。
   - `ARCHITECTURE*.md`、`TECHNICAL_OVERVIEW.zh-TW.md`、`WORKSPACE_LAYOUT.zh-TW.md` 可能未完整反映 Web Preview、crawler seed registry、developer diagnostics、remote pagination contract。
4. Showcase / demo 字眼需要下輪審查。
   - 凡是「真下載示範」「展示模式」相關文字，要確認是否清楚標示 transitional/demo，避免被寫成 stable mainline feature。

## 後續建議

下一輪若要繼續大規模對齊，建議順序：

1. 實際啟動 Web Preview，對照 `WEB_PREVIEW_UIUX.zh-TW.md` 與 `USER_GUIDE.zh-TW.md`。
2. 實際啟動 Tk 或至少跑 headless UI/import tests，對照 `USER_MANUAL.zh-TW.md`。
3. 用 `rg` 搜尋「最新」「完成」「穩定」「0%」「真下載示範」「8765/8766」等易漂移語句，逐段分類成 current / historical / roadmap / demo。
4. 將 handoff 的超長歷史段逐步瘦身，把穩定歷史移到 `DEVELOPMENT_LOG.zh-TW.md` 或專題文件，只保留最新接力與風險。

## 本輪結論

目前文件存在明確漂移，但最危險的入口漂移已做最小修補。下一輪開發前，agent 應先讀本文件，再用實際測試/CLI/UI 證據確認要採信哪些文件段落。
