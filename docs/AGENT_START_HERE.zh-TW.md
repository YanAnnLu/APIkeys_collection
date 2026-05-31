# Agent Start Here

最後更新：2026-05-31

這份文件是給接手 RRKAL / `APIkeys_collection` 的 agent 的最短入口地圖。它不取代詳細規格，只負責降低啟動時的判斷成本。

## 文檔漂移防護

不要假設文件永遠反映現況。文件是契約，但契約可能漂移。接手時先用 `git status --short --branch`、`git log -1 --oneline --decorate`、必要的 CLI JSON、smoke/test 或實際 UI 操作建立 verified behavior，再回頭讀文件。

若文件和已驗證行為衝突，以已驗證行為為準，並把漂移寫進 handoff / GTD / development log 或做最小必要文件修補。歷史日誌是證據，不是目前真相。

## 目前主線

1. 先穩住地理與科學資料資產的 `seed -> crawler -> candidate -> plan -> download -> import -> UI` 閉環。
2. Crawler 主線優先處理來源介面類型：STAC、CKAN、Socrata、OGC、CMR、ERDDAP、HTML file index、unknown fallback。
3. 來源介面類型只回答「資料在哪裡、怎麼列資源」；CSV、JSON、NetCDF、GeoTIFF、ZIP 等內容格式要由 content detector / parser registry 另行處理。
4. Tk 仍是目前可用 UI；未來 Qt 只是換皮，後端服務、crawler asset、bounds schema、capability contract 必須保持可重用。
5. 本 session 的主工作區是 `L:\RRKAL_project`，也是提交來源；舊 `K:\APIkeys_collection` 只作唯讀參考。`L:` 是多專案共用雲端碟，除 `L:\RRKAL_project` 外其他資料夾都視為唯讀。GUI/showcase/full smoke 可 clone 到本地磁碟測試，通過後回補 `L:\RRKAL_project` 再 commit/push。
6. 若使用者問「整體進度多少」，不要回單一百分比；先讀 `docs/PROJECT_MATURITY_MATRIX.zh-TW.md` 或跑 `--project-maturity-json`，用成熟度矩陣回答。

## 不要做什麼

- 不要把 NASA、NOAA、World Bank 這種機構名稱寫成 crawler 類別；先判斷來源介面類型。
- 不要把 K 槽教材、CODE_KM、Sciverse 或其他參考範例直接搬成產品碼；先抽概念，做成小型、可測、可審核的 RRKAL module。
- 不要把 source detector 判斷成功當成可直接下載或可正式 promotion；必須先產生 local source draft，再跑 crawler audit。
- 不要讓 crawler 直接寫資料庫；維持 `download -> manifest -> import` 邊界。
- 不要新增巨型 UI 檔案或把後端邏輯塞回 Tk；UI 應消費 service / form spec / capability contract。

## 權威順序

若文件彼此衝突，依序採信：

1. 使用者最新明確指令。
2. 已驗證行為：tests、CLI JSON、smoke result、實際 UI 行為、`git diff`、GitHub Actions。
3. `docs/AGENT_HANDOFF.zh-TW.md` 與 `docs/PROJECT_GTD.md`：最新接力、目前進度、下一步與已知風險。
4. 本文件與 `docs/DOCS_INDEX.zh-TW.md`：入口地圖、閱讀路徑與文件分層。
5. `openspec/specs/` 與 `docs/DEVELOPMENT_WORKFLOW_OPEN_SPEC.zh-TW.md`：中大型變更的規格與流程。
6. 任務對應文件，例如 crawler 看 `docs/DATASET_DISCOVERY_NOTES.zh-TW.md`，UI 看 `docs/UI_UX_DEVELOPMENT_CONTRACT.zh-TW.md` / `docs/WEB_PREVIEW_UIUX.zh-TW.md`。
7. `docs/DEVELOPMENT_LOG.zh-TW.md`、歷史日誌、K 槽教材、外部討論與概念筆記。它們可當證據與脈絡，但不能直接覆蓋已驗證現況。

## 任務閱讀路徑

- 接手任何開發：先讀本文件、`docs/AGENT_HANDOFF.zh-TW.md`、`docs/PROJECT_GTD.md`。
- 開始新 session / checkpoint 收尾前：快速檢查 `L:\AGENT_EXCHANGE\inbox\*_RRKAL_project.md`。若有相關 `Status: new` entry，必須在同一則 entry 的 `Responses` 區塊回覆 `Decision`、`Response`、`Next`，再把採納後的決策消化進本 repo 的 GTD / handoff / docs / OpenSpec / code slice。
- 改 crawler / source pattern / adapter：再讀 `docs/DATASET_DISCOVERY_NOTES.zh-TW.md`。
- 改 UI/UX：再讀 `docs/UI_UX_DEVELOPMENT_CONTRACT.zh-TW.md`。
- 改下載、匯入、repair：再讀 `docs/TECHNICAL_OVERVIEW.zh-TW.md` 與 `docs/ARCHITECTURE.md`。
- 改工作流、OpenSpec、Spectra、跨 agent 規則：再讀 `docs/DEVELOPMENT_WORKFLOW_OPEN_SPEC.zh-TW.md`。
- 轉交 Codex Cloud、新本機 thread、或整理本地對話備份：再讀 `docs/CODEX_CLOUD_HANDOFF.zh-TW.md` 與 `docs/WORKFLOW.zh-TW.md`。公開 repo 只放蒸餾後 handoff/workflow/decision/log；raw transcript 只放 private `dialogue-save`。
- 想看完整文檔地圖：讀 `docs/DOCS_INDEX.zh-TW.md`。

## 每輪固定治理機制

這些機制是防止 agent 悶頭推進、誤判狀態或把快速交付變成一次性程式碼的最低成本護欄。

- 開始前先跑 `git status --short --branch`，確認是否有其他 agent 或使用者的未提交改動；若有 dirty worktree，先保護現況，不要改同一批檔案。
- 開始前與 checkpoint close 前都要看 `L:\AGENT_EXCHANGE\inbox\*_RRKAL_project.md`；交換區不上 GitHub，不是 source of truth，但未回覆的相關 `Status: new` 建議不能默默忽略。
- 中大型跨 crawler、resolver、download plan、import、UI、database 的改動，先用 OpenSpec 或至少寫清 scope、tasks、acceptance criteria、risks；小修不必硬開厚規格。
- 推進中卡住、工作時間拉長或需要外部 agent 接力時，先跑 `.\scripts\heartbeat_codex.cmd -DryRun`，讀 `state/heartbeat/heartbeat_plan.json` 與 `state/heartbeat/agent_prompt.md`，不要直接啟動自動 runner。
- 需要 agent-readable 狀態時，優先用 JSON 入口，例如 `--handoff-report-json`、`--run-mvp-demo-smoke-json`、`--adapter-review-json`、`--run-download-plan-json`，不要解析人類文字輸出。
- push 前先跑 `.\scripts\pre_push_smoke_brief.cmd`；等流程穩定後才考慮用 `.\scripts\install_pre_push_hook.cmd` 安裝本機 hook。
- push 後必須看 GitHub Actions：`gh run list --repo Kagamihara-Ruruka/APIkeys_collection --limit 5`，再用 `gh run watch RUN_ID --repo Kagamihara-Ruruka/APIkeys_collection --exit-status` 等遠端 checkpoint 確認。
- 每個 checkpoint 結束前做 docs drift check：本輪是否改了 UI/Web/Tk/CLI、crawler/source pattern/download/import/adapter review、功能定位、展示/experimental surface、K 槽/本地 clone/GitHub/CI 工作流，或讓 handoff/GTD/log/index/user docs 任一敘述變成錯誤。

## K 槽參考邊界

K 槽教材與 CODE_KM 是概念樣本庫，不是產品碼來源。

- 爬蟲教材：抽 HTTP 探測、HTML 連結解析、Scrapy 分層、rate limit、錯誤分類、fixture 測試。
- CODE_KM：抽 provenance、checksum、pipeline run state、rights/review gate、local metadata index。
- 金融教材：抽 time-series、append/backfill、交易日曆、storage review。
- GIS / 3D / 數學教材：抽 bounds、projection、tile/cache、renderer-ready manifest、geometry transform。
- Sciverse / OpenDataLab：暫時只當 `literature_discovery_api` / provenance 輔助層，不放進第一階段 geospatial downloader 主線。

## 快速交付與日常開發

- 日常開發：小切片、測試、docs/GTD/handoff 同步、避免一口氣改大面積。
- 快速交付：可以降低功能顆粒度，但不能降低真實性。GUI 要真的可操作，進度要來自後端，PPT/腳本要可開可驗證。
- 快速交付後：把急改經驗收斂成測試、文檔、GTD、OpenSpec 或 skill guardrail，不留下只為展示存在的一次性邏輯。

## 功能切片完成前的文檔檢查

功能沒有同步留下必要的 GTD、handoff 或專題文件痕跡，就不算真正完成。但不要為每個小改動大改文件；只在文檔會失真時更新。

完成一個功能切片後，先跑測試，再檢查：

- 是否影響目前進度或下一步？更新 `docs/PROJECT_GTD.md`。
- 是否影響下一位 agent 接手、跨機器同步、風險或工作流？更新 `docs/AGENT_HANDOFF.zh-TW.md`。
- 是否影響 crawler、source pattern、adapter、candidate、resolver 或 discovery audit？更新 `docs/DATASET_DISCOVERY_NOTES.zh-TW.md`。
- 是否影響 UI/CLI 操作、按鈕、選單或展示流程？更新 `docs/USER_GUIDE.zh-TW.md` 或 `docs/USER_MANUAL.zh-TW.md`。
- 是否新增、移動或重新定位文件入口？更新 `docs/DOCS_INDEX.zh-TW.md`。
- 是否改了架構邊界、服務分層或資料流？更新 `docs/TECHNICAL_OVERVIEW.zh-TW.md` 或 `docs/ARCHITECTURE.md`。
- 是否已做到可驗證 checkpoint，即使 GitHub push / CI 因帳號、網路或平台問題失敗，也要更新 `docs/DEVELOPMENT_LOG.zh-TW.md`，明確標成 `WORKING / 未推送`、`LOCAL PASS / CI 未完成` 或 `CI 失敗`，並寫出本地驗證與剩餘風險。

如果都沒有影響，回報時明確說「本切片不需更新文檔」。這不是行政負擔，而是防止下次 agent 從錯誤地圖開始工作。
