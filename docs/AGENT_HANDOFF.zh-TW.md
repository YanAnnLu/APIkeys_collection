# Agent 接力卡
## 2026-05-31 13:17 Web event context chip labels
- 本輪把 Web Preview 事件紀錄 context chip 加上一層 display adapter：context key 經 `eventContextKeyLabel()` 顯示「資產 ID」「執行紀錄」「下一步」等人類欄位名，`next_action` / `user_next_action` scalar value 缺 label 時顯示「下一步待確認」。
- 保持邊界：event payload、event context summary、JSON/debug、recent-events API、event log storage、crawler/download/import/Tk 流程都沒改；這只是 Web event list visible label hygiene。
- 已驗證：`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest -v tests.test_web_preview` 通過 65 tests；docs mojibake scan OK；`git diff --check` 無 whitespace error（Git 仍提示 `frontends/web/static/app.js` line-ending warning）；完整 smoke `state\logs\pre_push_smoke_20260531_131800.log` 通過，1039 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`。
## 2026-05-31 13:06 Web download/import context chip labels
- 本輪把 Web Preview 下載 / 匯入結果列的 context chip 從 backend trace token 改成人類文案：`crawler_asset_path` 顯示為「爬蟲資產路徑」，`download_import_pipeline` 顯示為「下載 / 匯入管線」。
- 保持邊界：download/import payload、artifacts、route key、event/provenance、plan outcome、callback diagnostics、Tk 顯示、crawler registry 與正式下載 / 匯入流程都沒改；這只是 Web result row visible chip hygiene。
- 已驗證：`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest -v tests.test_web_preview` 通過 65 tests；docs mojibake scan OK；`git diff --check` 無 whitespace error（Git 仍提示 `frontends/web/static/app.js` line-ending warning）；完整 smoke `state\logs\pre_push_smoke_20260531_130753.log` 通過，1039 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`。
## 2026-05-31 12:56 Web seed row title labels
- 本輪把 Web Preview seed row 的主標題收斂到 `seedDisplayText()`：seed row 不再用 `dataset_id` / `uid` 當主標題 fallback；dataset id 仍保留在小字追溯欄，明確標成 `Dataset ID：...`，缺追溯值時顯示「Seed ID 待確認」。
- 保持邊界：favorite key、route key、download uid、seed ownership validation、seed download/import endpoint 與本機 seed catalog 都沒改；這只是 seed row visible title hygiene。
- 已驗證：`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest -v tests.test_web_preview` 通過 65 tests；docs mojibake scan OK；`git diff --check` 無 whitespace error（Git 仍提示 `frontends/web/static/app.js` line-ending warning）；完整 smoke `state\logs\pre_push_smoke_20260531_125801.log` 通過，1039 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`。
## 2026-05-31 12:47 Web downloader/recommended seed title labels
- 本輪把 Web Preview 下載器結果列與推薦 seed 面板標題也接回 display-safe helper：`crawlerAssetDownloadImportRowHtml()` 顯示 `assetDisplayText()`，`seedRecommendedPanelHtml()` 顯示 `seedDisplayText()`，缺 label 時落到中性 fallback，不再把 `payload.asset_id` / `result.asset_id` / `recommended_seed_uid` 當使用者標題。
- 保持邊界：raw ids 仍保留在 API payload、route key、favorite key、writeJson/debug 與 provenance；seed row 本身仍可顯示 catalog-provided dataset id 作為可追溯欄位，這輪只收掉主要標題 fallback。Web API、seed recommendation service、download/import、crawler registry、credential flow、Tk 顯示與 project maturity 都沒改。
- 已驗證：`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest -v tests.test_web_preview` 通過 65 tests；docs mojibake scan OK；`git diff --check` 無 whitespace error（Git 仍提示 `frontends/web/static/app.js` line-ending warning）；完整 smoke `state\logs\pre_push_smoke_20260531_124839.log` 通過，1039 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`。
## 2026-05-31 12:31 Web mission queue display labels
- 本輪把 Web Preview mission queue 裡的資產 / seed 顯示再收斂：asset-level download/import、seed download/import、recommended-seed closure、seed schema probe、seed listing、credential-blocked build-plan 與 credential-save mission 都改用 `assetDisplayText()` / `seedDisplayText()`，缺 label 時顯示中性 fallback，不再把 `assetId`、`datasetUid` 或 `recommended_seed_uid` 當主要互動紀錄文案。
- 保持邊界：raw `asset_id`、`dataset_uid`、`next_action` 仍保留在 route、JSON/debug、writeJson 與 provenance；Web API shape、crawler registry、seed enumeration、schema probe service、download/import service、credential storage、Tk 顯示與 project maturity 都沒改。這只是 Web mission queue visible display hygiene。
- 已驗證：`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest -v tests.test_web_preview` 通過 65 tests；docs mojibake scan OK；`git diff --check` 無 whitespace error（Git 仍提示 `frontends/web/static/app.js` line-ending warning）；完整 smoke `state\logs\pre_push_smoke_20260531_123324.log` 通過，1039 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26703440667` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 12:21 Cross-agent exchange workflow docs
- 本輪把 `L:\AGENT_EXCHANGE` 的 RRKAL 收信規則寫回 repo 入口文件：`AGENT_START_HERE`、`WORKFLOW`、`DOCS_INDEX` 都已明確要求開始新 session / checkpoint close 前檢查 `L:\AGENT_EXCHANGE\inbox\*_RRKAL_project.md`，並在相關 `Status: new` entry 的 `Responses` 區塊回覆 `Decision`、`Response`、`Next`。
- 保持邊界：交換區不上 GitHub，不是 RRKAL source of truth；原始信件不複製進公開 repo。採納建議後才消化成 RRKAL 內部 GTD / handoff / docs / OpenSpec / code slice。
- 已驗證：本輪開始檢查交換區無新的 RRKAL `Status: new` 收信；`docs` mojibake scan 通過；`git diff --check` 通過。這是 workflow/docs 切片，不改產品碼、Web/Tk、crawler、download/import 或 credential flow。
## 2026-05-31 11:56 Web source type display label guard
- 本輪把 Web Preview `sourceTypeDisplayText()` 的最後 raw fallback 拿掉：source type filter、asset card、Passport 與 selected hero 只顯示後端 `source_type_label` / capability profile label，缺 label 時顯示「來源範式待確認」，不再用 `shortPattern(source_type)` 把 raw source id 美化成假人類文案。
- 保持邊界：raw `source_type` 仍保留在 payload、filter key、route key、search haystack、JSON/debug 與 developer diagnostics；crawler registry、source type dispatch、capability profile、download/import、credential flow、Tk 顯示與 project maturity 都沒改。這只是 Web source-type visible display hygiene。
- 已驗證：`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest -v "tests.test_web_preview"` 通過 65 tests；第一次完整 smoke `state\logs\pre_push_smoke_20260531_115255.log` 在 L 槽雲端 transient `Unable to read current working directory` 失敗，立即重跑 `state\logs\pre_push_smoke_20260531_115307.log` 通過，1039 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；程式碼提交：`2878b35 Require Web source type display labels`；GitHub Actions manual run `26702672659` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 11:45 Web label helper raw fallback guard
- 本輪把 Web Preview 三個 label helper 再收斂：登入設定完成 mission 的登入狀態、capability label、bounds field label 都只顯示後端 label、本地已知 label map 或中性 fallback，不再把 `status.status`、`capability_id`、`field_id` 當可見文案候選。
- 保持邊界：`status.status`、`capability_id`、`field_id` raw ids 仍保留在 payload、JSON/debug、路由/表單 key 與追溯資料裡；credential save、capability metadata、bounds form schema、download/import、crawler registry、Tk 顯示與 project maturity 都沒改。這只是 Web visible label fallback hygiene。
- 已驗證：`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest -v "tests.test_web_preview"` 通過 65 tests；完整 smoke `state\logs\pre_push_smoke_20260531_114156.log` 通過，1039 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；程式碼提交：`f498178 Hide Web label helper fallback ids`；GitHub Actions manual run `26702495054` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 11:32 Web content/display raw fallback guard
- 本輪把 Web Preview 另外幾個可見 display helper 收斂：flow step label、event object context、content review bucket、content pipeline lane 與 parser summary 都只消費後端 display label / short label / stage label / status label 或中性 fallback，不再把 `step_id`、`review_bucket`、`pipeline_lane`、`parser_id`、`source_format`、raw `stage/status` 當可見文案候選。
- 保持邊界：raw ids 仍保留在 payload、JSON/debug、event context 與搜尋/追溯資料裡；adapter review、content parser/import 判斷、event log shape、download/import、crawler registry、Tk 顯示與 project maturity 都沒改。這只是 Web visible display fallback hygiene。
- 已驗證：`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest -v "tests.test_web_preview"` 通過 65 tests；完整 smoke `state\logs\pre_push_smoke_20260531_112945.log` 通過，1039 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；程式碼提交：`a081fdb Hide Web content display fallback ids`；GitHub Actions manual run `26702264196` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 11:19 Web next-action raw fallback guard
- 本輪把 Web Preview 使用者可見的 next-action fallback 再收斂：Downloader row、seed 枚舉 mission、Crawler Passport、credential badge、plan preview 狀態 / mission、selected hero、plan passport 與 stale passport 都只吃後端 `*_next_action_label` 或中性 fallback，不再把 raw `next_action` / `stale_next_action` snake_case id 放進畫面文案。
- 保持邊界：raw `next_action` / `stale_next_action` 仍保留在 payload、JSON/debug、search haystack 或控制流程 comparison 給 agent 與程式使用；crawler registry、capability profile、download/import、credential flow、Tk 顯示與 project maturity 都沒改。這只是 Web visible display fallback hygiene。
- 已驗證：`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest -v "tests.test_web_preview"` 通過 65 tests；完整 smoke `state\logs\pre_push_smoke_20260531_111535.log` 通過，1039 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；程式碼提交：`30419dc Hide Web next action fallback ids`；GitHub Actions manual run `26702034041` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 11:00 Crawler capability dimension display labels
- 本輪把 crawler capability profile 的四個矩陣維度補上後端 display label：`source_family_label`、`transport_label`、`auth_mode_label`、`terms_risk_label`、`result_shape_label` 會隨 `CrawlerCapabilityProfile.to_dict()` 輸出。Web capability capsule summary 改吃這些 label，不再把 `catalog_search / json / public_or_review / dataset_list` 這類 raw backend token 放進使用者可見摘要。
- 保持邊界：`source_family`、`transport`、`auth_mode`、`terms_risk`、`result_shape` raw 欄位仍保留在 payload 給 agent/debug/filter；crawler registry、capability address、seed enumeration、download/import、credential flow、Tk 顯示與 project maturity 都沒改。這只是 capability profile display contract 的補強。
- 已驗證：`node --check frontends\web\static\app.js` OK；第一次 `py -3 -B -m unittest tests.test_crawler_assets tests.test_web_preview -v` 只在已知 Windows localhost short-response 測試遇到 transient `WinError 10053`，單測立即重跑通過；`py -3 -B -m unittest -v "tests.test_crawler_assets" "tests.test_web_preview"` 通過 112 tests；完整 smoke `state\logs\pre_push_smoke_20260531_105851.log` 通過，1039 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；程式碼提交：`47b779c Label crawler capability dimensions`；GitHub Actions manual run `26701734284` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 10:42 Tk seed scope raw fallback guard
- 本輪把 Tk crawler asset `crawler_asset_seed_scope_label()` 收斂到後端 `seed_scope_display_label()`：dict / object profile 都能讀 `seed_scope_label`，缺 label 且遇到未知 `seed_scope` / `current_seed_scope` 時顯示「Seed 範式待確認」，不再把 `new_seed_scope` 類 raw backend token 放進表格或 Passport。
- 保持邊界：`capability_profile.seed_scope` 與 `current_seed_scope` raw 欄位仍保留在 payload / asset object 給 agent/debug；crawler registry、seed enumeration、Web 顯示、download/import、credential flow 與 project maturity 都沒改。這只是 Tk display fallback hygiene。
- 已驗證：`py -3 -B -m unittest tests.test_tk_ui_helpers tests.test_tk_dialogs tests.test_crawler_assets -v` 通過 221 tests；同時執行的 `py_compile` 在 L 槽 `__pycache__` rename 遇到已知 `WinError 5` 雲端鎖，後續完整 smoke `state\logs\pre_push_smoke_20260531_104000.log` 通過，1039 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；程式碼提交：`d81ee45 Hide Tk seed scope fallback ids` / docs 提交 `649ee6f Log Tk seed scope fallback checkpoint`；GitHub Actions manual run `26701397722` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 10:28 Web seed scope raw fallback guard
- 本輪把 Web Preview 的 Crawler Passport 與 capability capsule summary 再收斂一層：`Seed 範式` 只消費後端 `capability_profile.seed_scope_label`，缺 label 時顯示「Seed 範式待確認」，不再把 raw `seed_scope` 作為使用者文案候選。
- 保持邊界：`capability_profile.seed_scope` raw 欄位仍保留在 payload 給 agent/debug；crawler registry、seed enumeration、Tk 顯示、download/import、credential flow 與 project maturity 都沒改。這只是 Web display fallback hygiene。
- 已驗證：`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest tests.test_web_preview -v` 通過 65 tests；完整 smoke `state\logs\pre_push_smoke_20260531_102546.log` 通過，1038 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；程式碼提交：`5e20250 Hide Web seed scope fallback ids` / docs 提交 `26ee617 Log Web seed scope fallback checkpoint`；GitHub Actions manual run `26701162075` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 10:16 Project maturity row fallback labels
- 本輪把 project maturity 的 row fallback 再收斂一層：Web maturity card 缺 `area_label` 時顯示「成熟度面向待確認」，不再以 `row.area_id` 當使用者標題；Markdown render 缺 `area_label` / `maturity_label_zh_TW` / `display_label` 時也會顯示「成熟度面向待確認」與 maturity display profile 的「未分類」，不再把 `new_backend_area` / `new_backend_level` 類 raw id 當人類文案。
- 保持邊界：`area_id`、`maturity_level`、display profile 與 metrics 仍保留在 payload 給 agent/debug；project maturity matrix 計算、Web route、Tk dialog、download/import/crawler 行為都沒改。這只是 Web/Markdown fallback display hygiene。
- 已驗證：`py -3 -B -m unittest tests.test_project_maturity tests.test_web_preview -v` 通過 71 tests；完整 smoke `state\logs\pre_push_smoke_20260531_100946.log` 通過，1038 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；程式碼提交：`ec03262 Hide maturity fallback ids` / docs 提交 `a09845d Log maturity fallback checkpoint`；GitHub Actions manual run `26700904557` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 10:01 Project maturity delivery status label
- 本輪把 project maturity 的 canonical delivery scope 補上後端 `status_label`，`ready_for_mvp_demo` 會顯示「可展示小閉環」；Tk 成熟度矩陣 dialog 改吃這個 label，缺 label 時顯示「交付狀態待確認」，不再把 raw delivery status id 當主要使用者文案。Markdown render 也輸出 `status_label`，Web 既有 `displayTextOrFallback()` 會自動消費同一欄位。
- 保持邊界：`canonical_delivery_scope.status` raw 欄位仍保留給 agent/debug；maturity row 計算、MVP readiness 判斷、Web route、Tk dialog 開啟流程、crawler/download/import 都沒改。這只是 maturity payload 的 display-contract 補強。
- 已驗證：`py -3 -B -m unittest tests.test_project_maturity tests.test_tk_dialogs tests.test_web_preview -v` 通過 214 tests；完整 smoke `state\logs\pre_push_smoke_20260531_095829.log` 通過，1037 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；程式碼提交：`63e231a Label project maturity delivery status` / docs 提交 `7df9f23 Log maturity status label checkpoint`；GitHub Actions manual run `26700613871` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 09:49 Crawler capability status display fallback
- 本輪把 crawler asset 能力狀態顯示收斂到 `status_label_or_fallback()`：後端 `CrawlerAsset.capability_summary`、Tk crawler asset 表格三個能力欄、右側 Passport 能力清單遇到未知 `item.status` / `asset.capability_status(...)` 時會顯示「需檢查能力狀態」，不再把 `new_capability_status` 類 raw backend token 當人類文案。
- 保持邊界：`CrawlerAssetCapability.status` raw 欄位、`capability_status()`、能力判斷、crawler health、registry、download/import、Web route 與 credential flow 都沒改；這只是能力狀態的 display-contract fallback 收斂。
- 已驗證：`py -3 -B -m unittest tests.test_tk_ui_helpers tests.test_crawler_assets -v` 通過 76 tests；`py -3 -B -m unittest tests.test_tk_ui_helpers tests.test_tk_dialogs tests.test_crawler_assets -v` 通過 220 tests；完整 smoke `state\logs\pre_push_smoke_20260531_094645.log` 通過，1037 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；程式碼提交：`aced815 Hide crawler capability status fallbacks` / docs 提交 `d18aa1b Log capability status fallback checkpoint`；GitHub Actions manual run `26700405770` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 09:30 Tk crawler asset health state label fallback
- 本輪把 Tk crawler asset 表格 / Passport 的 compact state label 改成共用後端 `health_status_label_or_fallback()`；未知 `asset.health.status_code` 會顯示「未知」，不再把 `new_backend_health` 類 raw status token 直接露到 UI。
- 保持邊界：`asset.health.status_code` raw 欄位、`status_tone`、`status_gate`、crawler health evaluation、Web asset card 與 download/import/crawler 行為都沒改；這只是 Tk compact state label 的 display-contract 收斂。
- 已驗證：第一次 `py_compile` 在 L 槽 `__pycache__` rename 遇到雲端碟 `WinError 5`，同檔案後續用 `PYTHONDONTWRITEBYTECODE=1` / `-B` 路線驗證；`py -3 -B -m unittest tests.test_tk_ui_helpers -v` 通過 28 tests；`py -3 -B -m unittest tests.test_tk_ui_helpers tests.test_tk_dialogs -v` 通過 172 tests；完整 smoke `state\logs\pre_push_smoke_20260531_093004.log` 通過，1036 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；程式碼提交：`54cb206 Reuse crawler health labels in Tk` / docs 提交 `ad268a7 Log Tk health label checkpoint`；GitHub Actions manual run `26700154616` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 06:50 Backend seed scope label fallback
- 本輪把 `seed_scope_display_label()` 的未知 seed scope fallback 改成「Seed 範式待確認」；已知 `entry_listing` / `paginated_catalog` / `unknown` 仍顯示「入口列表」「分頁 catalog」「未知」，避免未來 registry 新增 seed scope token 時直接露出 raw backend id。
- 保持邊界：`seed_scope` raw 欄位仍保留在 payload 給 agent/debug 追溯；crawler registry、handler dispatch、seed enumeration、Web/Tk 讀取 `capability_profile.seed_scope_label` 的方式都沒改。這只是後端 capability profile 的 display-safe label fallback。
- 已驗證：`py -3 -B -m unittest tests.test_web_preview.WebPreviewApiTest.test_server_rejects_oversized_discard_body_before_diagnostic_handler -v` 單測通過，確認前一次 Windows localhost short-response 問題是 transient；`py -3 -B -m unittest tests.test_crawler_assets -v` 通過 47 tests；`py -3 -B -m unittest tests.test_crawler_assets tests.test_web_preview tests.test_tk_dialogs -v` 通過 256 tests；完整 smoke `state\logs\pre_push_smoke_20260531_065021.log` 通過，1035 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；程式碼提交：`7b85048 Hide unknown seed scope labels` / docs 提交 `72979c4 Log seed scope label checkpoint`；GitHub Actions manual run `26697139842` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 06:40 Tk crawler audit next-action fallback
- 本輪把 Tk crawler audit 的未知 `next_action` fallback 改成「查看 crawler 審核結果。」；已知 `repair_crawler_query_or_parser` 等 action 仍顯示原本的人類指引，未知 action 不再把 raw backend id 直接露到 discovery/audit 訊息。
- 保持邊界：crawler audit payload、source audit result、promotion/upsert、warning code、problem source grouping、CLI/JSON 與 Web route 都沒改；這只是 Tk audit next-step display fallback。
- 已驗證：`py_compile` for `frontends\tk\ui_labels.py` / `tests\test_tk_ui_labels.py` OK；`py -3 -B -m unittest tests.test_tk_ui_labels tests.test_launcher_ui tests.test_tk_dialogs -v` 通過 182 tests；完整 smoke `state\logs\pre_push_smoke_20260531_063741.log` 通過，1034 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；程式碼提交：`d6210f1 Hide Tk crawler action fallback ids` / docs 提交 `c8703e9 Log Tk crawler action fallback checkpoint`；GitHub Actions manual run `26696880389` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 06:28 Tk provider status fallback labels
- 本輪把 `ProviderRow.update_label` / `local_label` 收斂到 `provider_update_status_label()` / `provider_local_status_label()`；已知狀態仍顯示「有更新」「未納管」，未知 backend status 改顯示「更新狀態待確認」「本地狀態待確認」，避免新 provider status token 直接露到 Tk 主表格欄位。
- 保持邊界：ProviderCatalogEntry、download eligibility、repository row、search haystack、download/import/crawler/credential flow 都沒改；這只是 Tk provider view-model 的 display-safe fallback。
- 已驗證：`py_compile` for `frontends\tk\provider_models.py` / `tests\test_tk_provider_models.py` OK；`py -3 -B -m unittest tests.test_tk_provider_models tests.test_tk_dialogs -v` 通過 147 tests；完整 smoke `state\logs\pre_push_smoke_20260531_062818.log` 通過，1034 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；程式碼提交：`b07a5e6 Label Tk provider status fallbacks` / docs 提交 `cb45246 Log Tk provider status checkpoint`；GitHub Actions manual run `26696686112` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 06:14 Tk import plan status labels
- 本輪把 Tk 匯入狀態 fallback 收斂到 `import_plan_status_label()`；已知 `manual_review_required` 顯示「需內容 Parser review」，未知 `import_plan.status` 顯示「匯入狀態待確認」，避免新 backend status 直接露到下載器匯入欄。
- 保持邊界：CSV/JSON importer、download-plan runner、manual-review payload、content parser review payload、SQLite write gate、manifest 與 Web route 都沒改；這只是 Tk 匯入欄位的 display-safe fallback。
- 已驗證：`py_compile` for `frontends\tk\import_workflows.py` / `tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 通過 144 tests；完整 smoke `state\logs\pre_push_smoke_20260531_061218.log` 通過，1032 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；程式碼提交：`72af949 Label Tk import plan statuses` / docs 提交 `8876ead Log Tk import status checkpoint`；GitHub Actions manual run `26696368474` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 06:03 Tk download skip bucket labels
- 本輪把 Tk 下載器略過摘要的 bucket 顯示收斂到 `download_skip_bucket_label()`；已知 bucket 顯示「需 Adapter」「缺下載 URL」等文案，未知 bucket 只顯示「其他待處理」，避免未登錄 backend bucket 直接洩漏成 raw id。
- 保持邊界：`download_entry_skip_bucket()`、`download_skip_summary()`、download plan runner、CLI JSON、queue、manifest/import 行為都沒改；這只是 Tk 下載略過摘要的人類文案 fallback。
- 已驗證：`py_compile` for `frontends\tk\download_workflows.py` / `tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 通過 142 tests；完整 smoke `state\logs\pre_push_smoke_20260531_060120.log` 通過，1030 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；程式碼提交：`3962d96 Label Tk download skip buckets` / docs 提交 `74e88c5 Log Tk download skip checkpoint`；GitHub Actions manual run `26696145938` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 05:52 Tk downloader status labels
- 本輪把 Tk 下載器 runtime status 顯示收斂到 `download_job_status_label()`；下載器表格與失敗/取消狀態列顯示「已規劃」「下載中」「失敗」等人類文案，不再把 raw `planned` / `failed` 直接當主要使用者文字。
- 保持邊界：download queue 的 stable `JobStatus`、`download_status_by_provider` tuple、plan key、provider id lookup、manifest/register/import 與 `download_job_problem` event context 都沒改；raw status/id 仍保留給 agent/debug 追溯。
- 已驗證：`py_compile` for `frontends\tk\download_workflows.py` / `tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 通過 141 tests；完整 smoke `state\logs\pre_push_smoke_20260531_055004.log` 通過，1029 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；程式碼提交：`5766f6c Label Tk download job statuses` / docs 提交 `78b2266 Log Tk download status checkpoint`；GitHub Actions manual run `26695927338` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 05:36 Tk repair provider labels
- 本輪把 Tk 修復/驗證面板的 provider 欄位與多個修復提示標題接到 `repair_provider_label()` / `repair_asset_title()`；表格與 messagebox 顯示 `Provider ID：...`，避免 raw `provider_id` 被當成人類資料源名稱。
- 保持邊界：下載 manifest scan、database self-check、requeue、SQLite reimport、dry-run SQL、connection metadata、unmanage、event context 與 detail pane 的 `provider_id:` trace key/value 都沒改；這只是修復 UI 的 provider provenance label 收斂。
- 已驗證：`py_compile` for `frontends\tk\repair_workflows.py` / `tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 通過 139 tests；完整 smoke `state\logs\pre_push_smoke_20260531_053625.log` 通過，1027 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；程式碼提交：`40dae91 Label Tk repair provider ids` / docs 提交 `18f676c Log Tk repair provider checkpoint`；GitHub Actions manual run `26695645884` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 05:25 Tk adapter review provider labels
- 本輪把 Adapter Review dialog 表格的 provider 欄接到 `provider_display_label(None, provider_id)`；表格顯示 `Provider ID：...`，避免 raw `nyc_open_data` 被當成人類資料源名稱。detail pane 的 `provider_id:` key/value 仍保留 raw id，因為那裡是 agent / 人類可複製的追溯區。
- 保持邊界：adapter review display payload、detail key/value shape、resolver entry、open URL、resolve-from-UI、download/import/crawler flow 都沒改；這只是表格欄位的 provider provenance label 收斂。
- 已驗證：`py_compile` for `frontends\tk\adapter_review_dialog.py` / `tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 通過 138 tests；完整 smoke `state\logs\pre_push_smoke_20260531_052210.log` 通過，1026 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；程式碼提交：`afd20d3 Label Tk adapter review providers` / docs 提交 `4e70a9e Log Tk adapter review provider checkpoint`；GitHub Actions manual run `26695394542` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 05:12 Tk dataset candidate provider labels
- 本輪把 Dataset Candidate Review dialog 的 Provider 欄與 detail provider line 也接到 `provider_display_label(None, provider_id)`；候選資料只知道 provider id 時，UI 會顯示 `Provider ID：...`，不再把裸 `example_provider` 放在「提供商」欄位裡像人類名稱。
- 保持邊界：candidate status mapping、evidence JSON、source URL、approve/reject/add-to-plan、repository candidate schema、download/import/crawler flow 都沒改；這只是 review UI 的 provider provenance label 收斂。
- 已驗證：`py_compile` for `frontends\tk\dataset_candidate_review_dialog.py` / `tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 通過 138 tests；完整 smoke `state\logs\pre_push_smoke_20260531_050944.log` 通過，1026 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；程式碼提交：`ce27d37 Label Tk candidate review providers` / docs 提交 `ce3caf4 Log Tk candidate review provider checkpoint`；GitHub Actions manual run `26695103614` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 05:01 Tk provider table/detail display labels
- 本輪把 Tk 主表格 row title 與 detail panel title/description 也接到 `provider_display_label()`；若 `ProviderRow.name` 空白，畫面會顯示 `Provider ID：...`，不再出現空白表格標題或以空白 provider name 組出不完整描述。
- 保持邊界：provider repository row、search haystack、dataset count、detail owner/category/auth/website、download/import/crawler/credential flow 都沒改；這只是 Tk 使用者可見 provider display fallback ownership 的第三段收斂。
- 已驗證：`py_compile` for `frontends\tk\table_data_workflows.py` / `detail_panel_workflows.py` / `tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 通過 138 tests；完整 smoke `state\logs\pre_push_smoke_20260531_045819.log` 通過，1026 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；程式碼提交：`88d126b Use Tk provider display labels in details` / docs 提交 `a36a992 Log Tk provider detail display checkpoint`；GitHub Actions manual run `26694878725` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 04:42 Reuse Tk provider display labels
- 本輪延續上一個 provider display helper consolidation：AI summary 產生/寫入狀態與下載完成狀態也改用 `provider_display_label()`，避免 `row.name=""` 時出現空白 provider 名稱或 raw provider id 被當成主要使用者文案。
- 保持邊界：AI profile/token flow、download queue、manifest/register/import、repository key、plan key 與 worker job key 都沒改；這只是 Tk 使用者可見 label fallback ownership 收斂。
- 已驗證：`py_compile` for `frontends\tk\ai_summary_workflows.py` / `download_workflows.py` / `tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 通過 136 tests；完整 smoke `state\logs\pre_push_smoke_20260531_044010.log` 通過，1024 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；程式碼提交：`0f39122 Reuse Tk provider display labels` / docs 提交 `3c88df0 Log Tk provider display reuse checkpoint`；GitHub Actions manual run `26694502805` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 04:28 Tk provider display label helper
- 本輪做 Tk display-contract consolidation：新增 `frontends/tk/provider_display.py::provider_display_label()`，讓 source action 與 download-plan workflow 共用「有 provider name 顯示名稱、空白則顯示 `Provider ID：...`、完全缺值則顯示 `Provider 待確認`」的 fallback 規則。
- `source_action_workflows.py` 保留 `source_action_provider_label()` 相容 wrapper；`plan_workflows.py` 的 provider toggle、加入下載計畫、dataset version plan 與 cart item label 已改吃同一份 helper。stable provider id 仍用於 repository call、plan key 與 background job key，這輪只調整使用者可見文案 fallback ownership。
- 已驗證：`py_compile` for `frontends\tk\provider_display.py` / `source_action_workflows.py` / `plan_workflows.py` / `tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 通過 135 tests；完整 smoke `state\logs\pre_push_smoke_20260531_042609.log` 通過，1023 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；程式碼提交：`b1e15b6 Share Tk provider display labels` / docs 提交 `50f1d13 Log Tk provider display helper checkpoint`；GitHub Actions manual run `26694215394` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 04:14 Tk blank provider name fallbacks
- 本輪延續 Tk source action display-contract：已有 `ProviderRow` 但 `row.name` 為空白時，選取、metadata row action、解除納管、標記移除與開官方文件頁都改用 `source_action_provider_label()`，顯示 `Provider ID：...` 或既有 provider name，不再出現空白 provider 名稱。
- 已驗證：`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m py_compile frontends\tk\source_action_workflows.py tests\test_tk_dialogs.py` OK；`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m unittest tests.test_tk_dialogs -v` 通過 134 tests；完整 smoke 第一次 `state\logs\pre_push_smoke_20260531_041138.log` 在 early `git diff --check staged` 遇到雲端碟 transient `Unable to read current working directory`；同一工作區立即確認 `pwd` / `git status` / `git diff --check` 正常，第二次完整 smoke `state\logs\pre_push_smoke_20260531_041156.log` 通過，1022 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；已推送 `2198b22 Guard Tk blank provider labels` / `8ccfd35 Log Tk blank provider label checkpoint`，GitHub Actions manual run `26693884337` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 04:03 Tk source action provider id fallback labels
- 本輪做 Tk display-contract 小切片：source action workflow 的置頂、metadata 檢查、本地資產驗證與納管狀態，若找不到 `ProviderRow.name`，會明確顯示 `Provider ID：...`，不再把 raw provider id 偽裝成 provider 顯示名稱。
- 已驗證：`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m py_compile frontends\tk\source_action_workflows.py tests\test_tk_dialogs.py` OK；`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m unittest tests.test_tk_dialogs -v` 通過 133 tests；完整 smoke `state\logs\pre_push_smoke_20260531_040016.log` 通過，1021 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；已推送 `d0c715a Label Tk source action provider ids` / `0c63b39 Log Tk source action provider checkpoint`，GitHub Actions manual run `26693645745` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 03:49 Tk credential subtitle provenance labels
- 本輪做 Tk display-contract 小切片：Crawler Asset credential/login dialog 的副標改由 `crawler_asset_credential_subtitle()` 產生，Provider、Source、Provider ID、Asset ID 都有明確標籤，不再把 `provider / source_type / asset_id` 裸串成主要使用者文案。
- 已驗證：`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m py_compile frontends\tk\crawler_asset_credential_dialog.py tests\test_tk_dialogs.py` OK；`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m unittest tests.test_tk_dialogs -v` 通過 131 tests；完整 smoke `state\logs\pre_push_smoke_20260531_034638.log` 通過，1019 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；已推送 `60a5b09 Label Tk credential subtitle ids` / `8bf0e6c Log Tk credential subtitle checkpoint`，GitHub Actions manual run `26693340352` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 03:36 Tk listing status display label
- 本輪做 Tk display-contract 小切片：`run_selected_crawler_asset_listing()` 仍用 raw `asset.asset_id` 作為 single-flight key 與 listing worker 參數，但狀態列與 duplicate guard 改顯示 `asset.display_name`，不再把 `demo_index` 這類 asset id 當主要使用者文字。
- 已驗證：`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m py_compile frontends\tk\crawler_asset_workflows.py tests\test_tk_dialogs.py` OK；`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m unittest tests.test_tk_dialogs -v` 通過 130 tests；完整 smoke `state\logs\pre_push_smoke_20260531_033255.log` 通過，1018 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；已推送 `1b60382 Label Tk listing status names` / `909cb26 Log Tk listing status checkpoint`，GitHub Actions manual run `26693093030` 通過 Ubuntu、Windows 與 real DB smoke。
- 交換區：已回覆 `L:\AGENT_EXCHANGE\inbox\c_3_RRKAL_project.md` 的 territory / EEZ / maritime-boundary manifest 建議，決策為 `backlogged`；這是未來 geospatial governance / OpenSpec 題，不打斷目前 Tk display-contract checkpoint。
## 2026-05-31 03:21 Tk metadata crawl status label
- 本輪做 Tk display-contract 小切片：`run_selected_crawler_asset_metadata()` 仍用 raw `provider_id` 設定 `active_provider_id` 給既有 metadata crawl 流程，但狀態列改顯示 `asset.display_name`，不再把 provider id 當主要使用者文字。
- 已驗證：`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m py_compile frontends\tk\crawler_asset_workflows.py tests\test_tk_dialogs.py` OK；`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m unittest tests.test_tk_dialogs -v` 通過 129 tests；第一次完整 smoke `state\logs\pre_push_smoke_20260531_031658.log` 在 `unittest discover` 起點遇到雲端碟 transient `Start directory is not importable: 'tests'`；同一環境立即確認 `tests\__init__.py` 存在且手動 `py -3 -B -m unittest discover -s tests -p "test*.py" -v` 通過 1017 tests / 4 skipped；第二次完整 smoke `state\logs\pre_push_smoke_20260531_031911.log` 通過，1017 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；已推送 `aa92271 Label Tk metadata crawl status` / `a8c97ab Log Tk metadata status checkpoint`，GitHub Actions manual run `26692761185` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 03:05 Tk crawler asset profile provenance labels
- 本輪做 Tk display-contract 小切片：Crawler Asset profile editor 的副標不再用裸 `provider_id / source_type_label / asset_id` 串接；新增 `crawler_asset_profile_subtitle()`，把來源範式、人類可讀 label 與追溯用 Provider ID / Asset ID 明確標示，避免 raw id 看起來像主要 UI 文案。
- 已驗證：`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m py_compile frontends\tk\crawler_asset_profile_dialog.py tests\test_tk_dialogs.py` OK；`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m unittest tests.test_tk_dialogs -v` 通過 128 tests；完整 smoke `state\logs\pre_push_smoke_20260531_030524.log` 通過，1016 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；已推送 `bc775da Label Tk profile provenance ids` / `0400e1b Log Tk profile provenance checkpoint`，GitHub Actions manual run `26692492110` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 02:55 Web provider/preset/seed fallback labels
- 本輪延續 Web display-contract 收斂：Crawler Passport provider 文字改吃 `providerDisplayText(card)`，credential editor title 改走 `credentialProviderTitle()`，bounds preset 顯示改走 `boundPresetLabel()`，seed row 空 metadata 改顯示「資料摘要待確認」；Web 不再直接把 `card.provider_id`、`status.provider_id`、`assetId`、`preset_id` 或英文 `metadata pending` 當主要使用者文案。
- 已驗證：`node --check frontends\web\static\app.js` OK；`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m unittest tests.test_web_preview -v` 通過 65 tests；完整 smoke 第一次 `state\logs\pre_push_smoke_20260531_025000.log` 的 unittest 已通過 1015 tests / 4 skipped，但 MVP demo CLI 遇到雲端碟 transient `Permission denied`；同一條 MVP demo CLI 立即重試成功 `download_import_completed` / `row_count=3`；第二次完整 smoke `state\logs\pre_push_smoke_20260531_025242.log` 通過，1015 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；已推送 `3b40128 Label Web provider preset seed fallbacks`，GitHub Actions manual run `26692222235` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 02:40 Web display helper fallback consolidation
- 本輪把 Web Preview 的 Parser Registry chips、後端 flow step label、capability label 與 bounds field label 都收回 `displayTextOrFallback()` 類 helper；缺 label 時顯示「Parser 線索待確認」「流程步驟待確認」「能力待確認」「欄位待確認」，不再直接 fallback 到 `parser_id`、`step_id`、`capability_id` 或 `field_id`。
- 已驗證：`node --check frontends\web\static\app.js` OK；`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m unittest tests.test_web_preview -v` 通過 65 tests；完整 smoke `state\logs\pre_push_smoke_20260531_023814.log` 通過，1015 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；已推送 `7161ab5 Guard Web id label fallbacks`，GitHub Actions manual run `26691886415` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 02:31 Web maturity area display fallback
- 本輪延續 Web display-contract 收斂：成熟度工作區的 row 標題改用 `displayTextOrFallback("成熟度面向待確認", row.area_label, row.area_id)`，不再把英文 `maturity area` 或 snake_case `area_id` 當作使用者可見標題。
- 已驗證：`node --check frontends\web\static\app.js` OK；`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m unittest tests.test_web_preview -v` 通過 65 tests；完整 smoke `state\logs\pre_push_smoke_20260531_022904.log` 通過，1015 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；已推送 `6116d4b Hide Web maturity area ids`，GitHub Actions manual run `26691697057` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 02:17 Web provider display fallback
- 本輪做小型 Web display-contract 收斂：Downloader row 與 selected hero 的 provider 文字改由 `providerDisplayText()` 產生，空值顯示「Provider 待確認」，不再出現英文 fallback `provider unknown`；provider id 仍可作為過渡顯示值，直到後端正式補 `provider_name` / `provider_label`。
- 已驗證：`node --check frontends\web\static\app.js` OK；`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m unittest tests.test_web_preview -v` 通過 65 tests；完整 smoke `state\logs\pre_push_smoke_20260531_021933.log` 通過，1015 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；`git diff --check` OK（僅保留既有 `frontends/web/static/app.js` CRLF warning）；已推送 `1fe48ac Label Web provider fallback`，GitHub Actions manual run `26691488253` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 02:05 Blocked plan reason display labels
- 本輪做一個小型 display-contract 收斂切片：`api_launcher.crawler_plan_outcome_display` 新增 blocked reason display label/fallback，`plan_outcome_display_profile()` 的 blocked summary / short label 不再把 raw `missing_credentials`、`crawler_asset_disabled` 類 backend id 放進使用者文案；Tk 下載計畫 blocked dialog 也改吃同一個 label。
- 已驗證：`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m unittest tests.test_tk_dialogs tests.test_web_preview -v` 通過 192 tests；`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m py_compile api_launcher\crawler_plan_outcome_display.py frontends\tk\crawler_asset_ui_helpers.py tests\test_tk_dialogs.py tests\test_web_preview.py` OK；完整 smoke `state\logs\pre_push_smoke_20260531_020551.log` 通過，1015 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；已推送 `70a9a5f Label blocked plan reasons`，GitHub Actions manual run `26691178190` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 01:49 Tk AI profile OAuth status labels
- 本輪把 Tk AI 摘要 profile login status 的 raw OAuth status 也收回同一個 display helper：`AiSummaryWorkflowMixin.ai_profile_login_status()` 在 OAuth ready 時顯示「OAuth 已登入：已登入」/ `OAuth signed in: Signed in`，不再把 raw `ready` 放進 AI 模型選擇表格或狀態摘要。
- 已驗證：`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m unittest tests.test_tk_dialogs -v` 通過 127 tests；`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m py_compile frontends\tk\ai_summary_workflows.py tests\test_tk_dialogs.py` OK；完整 smoke `state\logs\pre_push_smoke_20260531_014855.log` 通過，1015 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；已推送 `733ff0b Label Tk AI OAuth status`，GitHub Actions manual run `26690911510` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 01:40 Tk plan schema probe status labels
- 本輪把 Tk 下載計畫界域欄位探測失敗訊息也收回後端 display helper：`api_launcher.schema_probe` 新增 `schema_probe_status_label()` / `schema_probe_failure_detail()`；`PlanWorkflowMixin._finish_plan_bounds_probe()` 失敗 dialog 會顯示「缺少可探測資料端點」「欄位探測發生錯誤」等人類文案，必要時附技術細節，不再把 raw `unavailable` / `error` / 未知 `probe.status` 直接放進使用者可見訊息。
- 已驗證：`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m unittest tests.test_source_download tests.test_tk_dialogs -v` 通過 138 tests；`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m py_compile api_launcher\schema_probe.py frontends\tk\plan_workflows.py tests\test_source_download.py tests\test_tk_dialogs.py` OK；完整 smoke `state\logs\pre_push_smoke_20260531_014010.log` 通過，1014 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；已推送 `b1710f0 Label Tk schema probe failures`，GitHub Actions manual run `26690639138` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 01:29 Tk OAuth token status labels
- 本輪把 Tk Google/Gemini 連線與 OAuth device-flow 的 raw token/status id 收回後端 display helper：新增 `oauth_token_status_label()`，Google/Gemini 設定視窗顯示「尚未登入」「已登入」「登入請求失敗」等人類文案；OAuth device polling 未完成時顯示「等待授權」「登入請求失敗」等 label，不再把 raw `missing`、`ready`、`request_failed` 或未知 status id 放進使用者可見 status bar / connection message。
- 已驗證：`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m unittest tests.test_oauth_device tests.test_tk_dialogs -v` 通過 138 tests；`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m py_compile api_launcher\oauth_device.py frontends\tk\ai_settings_dialogs.py frontends\tk\oauth_workflows.py tests\test_oauth_device.py tests\test_tk_dialogs.py` OK；完整 smoke `state\logs\pre_push_smoke_20260531_012951.log` 通過，1012 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；已推送 `1e98417 Label Tk OAuth token statuses`，GitHub Actions manual run `26690438010` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 01:19 Showcase display labels
- 本輪把 Tk 展示模式裡的 raw status/stage token 收回後端 / shared display helper：seed coverage report 會輸出 `showcase_status_label`，Tk showcase seed coverage dialog 顯示「所有入口都有完整 seed 嘗試路徑」等文案；展示下載 dialog / status bar 會用 `download_import_stage_display_label()` 顯示「下載 / 匯入完成」，未知 progress stage 則顯示「展示流程狀態待確認」，不再把 raw `all_sources_have_complete_seed_attempt_path`、`download_import_completed` 或未知 stage id 放進使用者可見文字。
- 已驗證：`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m unittest tests.test_showcase_workflows tests.test_dataset_discovery -v` 通過 65 tests；`$env:PYTHONDONTWRITEBYTECODE='1'; py -3 -B -m unittest tests.test_tk_dialogs tests.test_showcase_workflows -v` 通過 130 tests；完整 smoke `state\logs\pre_push_smoke_20260531_011655.log` 通過，1010 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；已推送 `9e45de2 Label Tk showcase status stages`，GitHub Actions manual run `26690162318` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 01:06 Closure stage display labels
- 本輪補齊 recommended-seed closure / seed download-import 的 stage 顯示契約：`CrawlerAssetRecommendedSeedClosureResult.to_dict()` 現在輸出 `closure_stage_label`；Tk seed download/import 與 recommended closure message 會顯示「下載 / 匯入完成」「下載前需處理」「沒有推薦 seed」等人類文案，不再把 raw `download_import_completed`、`blocked_before_download`、`no_recommended_seed` 放進 message body / status message。
- 已驗證：`PYTHONDONTWRITEBYTECODE=1 py -3 -B -m unittest tests.test_tk_ui_helpers tests.test_crawler_asset_download -v` 通過 33 tests；`PYTHONDONTWRITEBYTECODE=1 py -3 -B -m unittest tests.test_tk_dialogs tests.test_web_preview tests.test_crawler_asset_download -v` 通過 195 tests；docs mojibake scan OK；完整 smoke `state\logs\pre_push_smoke_20260531_010544.log` 通過，1008 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；`git diff --check` OK；已推送 `70f01d7 Label closure stage messages`，GitHub Actions manual run `26689937366` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 00:52 Crawler asset surface/access labels
- 本輪繼續收斂 Crawler Asset 使用者可見文字：後端 `CrawlerAsset.to_dict()` 現在輸出 `source_surface_label` 與 `access_requirement_label`；Tk 右側 Passport 與 Web asset card / Passport / selected hero 會消費後端 label，不再由 UI 自行翻譯 `source_surface`，也不再在 Tk detail 顯示 raw `crawler_managed_auth`。
- 新增/更新 tests 鎖住：Tk detail 顯示「資料目錄」「需登入 / API key」等人類文案，Web 靜態檢查禁止 `file_index` / `map_service` 類本地翻譯表回到 JS。已驗證：`node --check frontends\web\static\app.js` OK；`PYTHONDONTWRITEBYTECODE=1 py -3 -B -m unittest tests.test_web_preview tests.test_crawler_assets tests.test_tk_ui_helpers -v` 通過 138 tests；`PYTHONDONTWRITEBYTECODE=1 py -3 -B -m unittest tests.test_tk_dialogs tests.test_web_preview -v` 通過 189 tests；docs mojibake scan OK；完整 smoke `state\logs\pre_push_smoke_20260531_005312.log` 通過，1007 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；已推送 `aedd95b Label crawler asset surface access`，GitHub Actions manual run `26689631897` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 00:38 Tk crawler asset maturity/risk labels
- 本輪修掉 Tk Crawler Asset 右側 Passport 的 raw token 外洩：`crawler_asset_detail_text()` 原本直接顯示 `asset.maturity` / `asset.risk_tier`，例如 `unbuilt`、`needs_handler`；現在改吃後端 `crawler_asset_maturity_label()` / `crawler_asset_risk_tier_label()`，顯示「待補 handler」「待審核」等人類文案。
- 新增 `test_crawler_asset_detail_text_uses_maturity_and_risk_labels()`，鎖住 Tk detail 不得再顯示 raw maturity/risk id。已驗證：`PYTHONDONTWRITEBYTECODE=1 py -3 -B -m unittest tests.test_tk_ui_helpers tests.test_tk_dialogs -v` 通過 151 tests；docs mojibake scan OK；完整 smoke `state\logs\pre_push_smoke_20260531_003914.log` 通過，1007 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；已推送 `be3f5bd Label Tk crawler asset maturity risk`，GitHub Actions manual run `26689307021` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 00:22 Project maturity mojibake guard
- 本輪沒有改成熟度矩陣產品行為；先針對剛才 PowerShell 顯示假亂碼與成熟度 UI/文件易被誤判的風險補防回歸。實體檔案用 Python UTF-8 / `ascii()` 檢查後確認 `api_launcher/project_maturity.py` 與 `tests/test_project_maturity.py` 是乾淨 UTF-8，先前 `Get-Content` 顯示的亂碼是 console code page 問題。
- 新增 `ProjectMaturityTests.assert_no_mojibake_fragments()` 與 `test_project_maturity_payload_and_markdown_do_not_contain_mojibake()`，會掃 `--project-maturity-json` payload 與 markdown render，禁止 U+FFFD、常見 mojibake 片段與 private-use 亂碼進成熟度矩陣輸出。已驗證：`PYTHONDONTWRITEBYTECODE=1 py -3 -B -m unittest tests.test_project_maturity tests.test_web_preview tests.test_tk_dialogs -v` 通過 194 tests；docs mojibake scan OK；完整 smoke `state\logs\pre_push_smoke_20260531_002749.log` 通過，1006 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；已推送 `751b64c Guard maturity matrix encoding`，GitHub Actions manual run `26689055642` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-31 00:10 Importer shim maturity evidence
- 延續 23:57 的 importer compatibility shim，本輪把 shim profile 接進 `--project-maturity-json` 的 `content_parser_and_import.metrics`。payload 會輸出 `supported_sqlite_importers=("csv_to_sqlite","json_to_sqlite")`、`compatibility_shim_count`、`compatibility_shim_runtime_scope=scoped_importer_boundary`、`global_monkeypatch=false` 與 shim 明細，讓 UI/agent 能從成熟度矩陣看見這層相容能力。
- 新增 `ImporterCompatibilityShimProfile` / `importer_compatibility_shim_report()`；這是 declarative evidence，不是新的全域 monkeypatch，也不改下載或匯入主流程。已驗證：`--project-maturity-json` 實際輸出 `compatibility_shim_count=1`、`runtime_scope=scoped_importer_boundary`、`global_monkeypatch=false`；`PYTHONDONTWRITEBYTECODE=1 py -3 -B -m unittest tests.test_importer_compatibility_shims tests.test_project_maturity tests.test_csv_importer tests.test_json_importer -v` 通過 20 tests；docs mojibake scan OK；完整 smoke `state\logs\pre_push_smoke_20260531_001121.log` 通過，1005 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；已推送 `571d727 Expose importer shim maturity evidence`，GitHub Actions manual run `26688687472` 通過 Ubuntu、Windows 與 real DB smoke。
## 2026-05-30 23:57 Importer compatibility shim
- 本輪把「劫持外部混亂來源」收斂成 importer 邊界的 scoped compatibility shim：新增 `api_launcher.importers.compatibility_shims`，不常駐覆寫 `builtins.print`、`sys.modules` 或 pandas；只在 CSV/JSON 進 SQLite 前正規化欄位與 cell 值。
- CSV importer 現在會攤平 tuple/list/MultiIndex-like 欄位與字串 repr，例如 `("Price", "Adj Close")`、`"('Price', 'Close')"`；`Unnamed:*_level_*` 這類 pandas 匯出殘留會落成安全 fallback 欄名。CSV/JSON importer 也會把 dict/list/tuple cell 穩定 JSON 化，`None` / NaN 仍匯入為空字串。
- 已驗證：`PYTHONDONTWRITEBYTECODE=1 py -3 -B -c "import ..."` OK；`py -3 -B -m unittest tests.test_importer_compatibility_shims tests.test_csv_importer tests.test_json_importer -v` 通過 15 tests；`git diff --check` OK；docs mojibake scan OK；完整 smoke `state\logs\pre_push_smoke_20260530_235939.log` 通過，1004 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；已推送 `db66df6 Add importer compatibility shim`，GitHub Actions manual run `26688452891` 通過 Ubuntu、Windows 與 real DB smoke。`py_compile` 在 L 槽雲端 `__pycache__` replace 時遇到 `WinError 5`，本輪以不寫 pyc 的 import check 與完整 smoke 補驗證，避免把雲端同步鎖誤判成程式錯誤。下一步可把這個 shim 接進更完整的 content parser/import profile diagnostics。
## 2026-05-30 23:41 Tk recommended seed closure
- 本輪把 recommended-seed closure 接進 Tk Seed 清單 dialog：後端 `recommended_seed_uid` 除了「下載推薦 Seed」外，現在也有「驗證閉環」入口。Tk 會重跑 bounded listing、讀本機 seed page，然後呼叫同一個 `run_recommended_seed_closure()` 後端 service；UI 不自行挑 seed、不重寫 Web/CLI 的 closure 規則。
- 新增 Tk helper：`crawler_asset_recommended_seed_closure_target_paths()`、`crawler_asset_recommended_seed_closure_ui_message()`、`crawler_asset_recommended_seed_closure_event_context()`。事件 payload 只記 compact seed page summary，不把整頁 seed list 寫進 event log。
- 已驗證：`py -3 -B -m py_compile frontends\tk\crawler_asset_seed_dialog.py frontends\tk\crawler_asset_ui_helpers.py frontends\tk\crawler_asset_workflows.py tests\test_tk_dialogs.py tests\test_tk_ui_helpers.py` OK；`py -3 -B -m unittest tests.test_tk_ui_helpers tests.test_tk_dialogs tests.test_crawler_asset_download tests.test_crawler_seed_registry -v` 通過 179 tests；`git diff --check` OK；frontends/tk 與 tests mojibake scan OK；完整 smoke `state\logs\pre_push_smoke_20260530_234119.log` 通過，1001 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；已推送 `a3141d9 Wire recommended seed closure into Tk` / `4591bb5 Document Tk recommended seed closure`，GitHub Actions manual run `26688043642` 通過 Ubuntu、Windows 與 real DB smoke。本輪另記錄 compat/shim guardrail：`sys.modules` / monkeypatch 可作測試或 adapter 相容層，但不要成為產品主線的全域常駐覆寫。
## 2026-05-30 23:18 Web recommended seed closure
- 本輪把 22:54 的 recommended-seed closure 後端/CLI artifact 接進 Web Preview：新增 `POST /api/crawler-assets/{asset_id}/recommended-seed-closure`，Web seed 推薦面板新增「驗證閉環」按鈕。按鈕固定走 `listing -> backend recommended_seed_uid -> formal seed download/import`，並把目前 bounds form values 傳給後端 closure service；Web 不自行挑 seed，也不重寫下載/匯入規則。
- 缺憑證時 Web 會先停在 shared credential-blocked payload，`closure_stage=credential_blocked`，不呼叫 live closure service；成功時會合併 shared download/import display payload、更新 plan passport、合併 seed page，並寫 `crawler_asset_recommended_seed_closure_completed` structured event。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawler_asset_closure.py frontends\web\preview_api.py frontends\web\server.py tests\test_web_preview.py` OK；`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest tests.test_web_preview tests.test_crawler_asset_download tests.test_crawler_seed_registry -v` 通過 94 tests；`git diff --check` OK；Browser 實測 `http://127.0.0.1:8765/` 可載入 Web Preview，畫面可見「下載推薦 seed」與「驗證閉環」；完整 smoke `state\logs\pre_push_smoke_20260530_232325.log` 通過，993 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；已推送 `3ccb3ff Wire recommended seed closure into Web`，GitHub Actions manual run `26687624870` 通過 Ubuntu、Windows 與 real DB smoke。下一步可做 Tk 對應入口或小型 Web/preview_api consolidation。
## 2026-05-30 22:54 Recommended seed closure CLI
- 本輪把第二條 live public source 小閉環收成後端/CLI artifact：新增 `api_launcher/crawler_asset_closure.py` 與 CLI `--run-crawler-asset-recommended-seed-closure ASSET_ID --crawler-asset-closure-json`，流程固定為 `crawler asset listing -> 本機 seed page -> 後端 recommended_seed_uid -> formal seed download/import`。這不是新 demo route，也不繞過既有 plan/download/import service。
- 已用 DataSF live public Socrata source 驗證：`sf_open_data_socrata_catalog` 枚舉 4 筆 seed，後端推薦 `ds_c0ebed9866e8c58b72784bff` / `Elect_StAsmbly_Dists`，closure command 回傳純 JSON，`closure_stage=download_import_completed`、`succeeded=true`、`imported=1`，artifact 在 `state\live_closure_probe\sf_command_verify\...`。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawler_asset_closure.py api_launcher\cli_crawler_assets.py` OK；`py -3 -B -m unittest tests.test_crawler_asset_download tests.test_crawler_seed_registry -v` 通過 29 tests；live closure subprocess JSON parse OK；完整 smoke `state\logs\pre_push_smoke_20260530_225806.log` 通過，990 tests / 4 skipped；GitHub Actions manual run `26687064209` 通過 Ubuntu、Windows 與 real DB smoke。下一步可把此 closure result 接進 Web/Tk 的「推薦 seed」狀態，或繼續做 bounded consolidation。
## 2026-05-30 22:30 Codex Cloud handoff / dialogue backup workflow
- 本輪初始化 RRKAL 專屬 Codex Cloud / 新 thread 接手文件：新增 `docs/CODEX_CLOUD_HANDOFF.zh-TW.md` 與 `docs/WORKFLOW.zh-TW.md`。公開 repo 只保存蒸餾後 handoff、workflow、decision、GTD、development log；完整對話或 raw transcript 只應放 private `Kagamihara-Ruruka/dialogue-save`，建議路徑為 `APIkeys_collection/<topic-slug>__YYYY-MM-DD__<thread-short-id>/`。
- 已同步入口：`AGENT_START_HERE` 增加 Cloud/new-thread/對話備份閱讀路線；`DOCS_INDEX` 與 `DOCS_REGISTRY.csv` 已加入兩份 workflow 文件；`PROJECT_GTD` 已記錄本 checkpoint。
- 邊界：這是 workflow/docs 初始化，不改產品碼、不接觸 `RRKAL_displaytools` 或 private transcript 內容，也不把 raw transcript 放進公開 repo。下一位 agent 若接到 Cloud 工作，先讀 `AGENT_START_HERE -> CODEX_CLOUD_HANDOFF -> WORKFLOW -> AGENT_HANDOFF -> PROJECT_GTD`。
## 2026-05-30 19:55 Tk source type display labels
- 本輪把同一份 `source_type_label` 接進 Tk：Crawler Asset 表格、右側 Passport 詳情、flow step、crawler profile dialog 與 credential dialog 都顯示「CKAN package search」「HTML file index」或「來源範式待確認」，不再把 raw `ckan_package_search` / `html_file_index` 當主要使用者文字。
- 已提交實作：`859fc5a Use source type labels in Tk`。
- 已驗證：in-memory compile 相關 Tk/backend/test 檔 OK；`py -3 -B -m unittest tests.test_tk_dialogs tests.test_tk_ui_helpers tests.test_crawler_assets -v` 通過，188 tests OK；完整 smoke `state\logs\pre_push_smoke_20260530_195239.log` 通過，987 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26683225294` 通過 Ubuntu、Windows 與 real DB smoke。`py_compile` 曾被 L 槽雲端 `__pycache__` replace lock 擋住，已用不寫 pyc 的 compile 與完整 smoke 補驗證。
- Docs drift check：已同步 GTD / handoff / Web Preview UIUX contract / development log；本輪只調整 Tk 顯示投影與對話框副標，不改 crawler registry dispatch、source type id、download/import service、credential storage 或 Web 行為。
## 2026-05-30 19:43 Web source type display labels
- 本輪把 crawler `source_type` 的使用者文案往後端 capability profile 收斂：`CrawlerCapabilityProfile` 與 `CrawlerAsset.to_dict()` 會輸出 `source_type_label`，Web source-type filter、Downloader row、Crawler Passport 與 selected hero 改顯示 label 或「來源範式待確認」，不再直接把 `stac_collections` / `html_file_index` 類 raw registry id 當人類文案。
- 已提交實作：`a0d71be Label crawler source types for Web`。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawler_capability_profiles.py api_launcher\crawler_assets.py tests\test_crawler_assets.py tests\test_web_preview.py` OK；`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest tests.test_crawler_assets tests.test_web_preview -v` 通過，108 tests OK；完整 smoke `state\logs\pre_push_smoke_20260530_194021.log` 通過，987 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26682992419` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / Web Preview UIUX contract / development log；本輪只增加 source type display label payload 與 Web 消費方式，不改 crawler registry dispatch、source type id、download/import service、credential storage 或 Tk 操作。
## 2026-05-30 19:24 Web maturity display labels
- 本輪把 Web「成熟度」工作區的 Delivery Scope 摘要與 maturity row label 也接回 display-safe helper：`deliveryClosureText()` 會優先使用後端 `status_zh_TW` / display label，缺值時顯示「狀態待確認」；row label 缺值時顯示「成熟度待確認」，不再把 raw `ready_for_mvp_demo`、`maturity_level` 或 `unknown` 放進使用者可見摘要。
- 已提交實作：`50559e7 Hide raw maturity status in Web`。
- 已驗證：`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest tests.test_web_preview -v` 通過，62 tests OK；完整 smoke `state\logs\pre_push_smoke_20260530_192430.log` 通過，987 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26682740605` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / Web Preview UIUX contract / development log；本輪只調整 Web maturity workspace 顯示 fallback，不改後端 maturity payload、crawler registry、download/import service、credential storage 或 Tk 操作。
## 2026-05-30 19:14 Web download mission stage label
- 本輪把 Web mission queue 的正式下載 / 匯入完成訊息也接回 `downloadImportStageText()`；asset-level 與 seed-level 成功訊息會顯示「下載 / 匯入完成」這類後端 display label，不再把 `download_import_completed` 或 raw stage token 放進互動紀錄。
- 已提交實作：`85f8ecd Use stage labels in Web missions`。
- 已驗證：`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest tests.test_web_preview -v` 通過，62 tests OK；完整 smoke `state\logs\pre_push_smoke_20260530_191232.log` 通過，987 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26682454145` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / Web Preview UIUX contract / development log；本輪只調整 Web mission queue 顯示 fallback，不改後端 payload、download/import service、crawler registry、credential storage 或 Tk 操作。
## 2026-05-30 19:01 Crawler asset maturity/risk labels
- 本輪把 Crawler Asset 的 `maturity` / `risk_tier` 使用者文案收回後端：`CrawlerAsset.to_dict()` 會輸出 `maturity_label` / `risk_tier_label`，Web Passport 改讀 label，缺值時落到「成熟度待確認」「風險層級待確認」，不再顯示 raw `unknown` 或 tier token；能力膠囊缺摘要時也顯示「能力膠囊待確認」。
- 已提交實作：`2c786bf Label crawler asset maturity risk`。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawler_assets.py tests\test_crawler_assets.py tests\test_web_preview.py` OK；`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest tests.test_crawler_assets tests.test_web_preview -v` 通過，108 tests OK；完整 smoke `state\logs\pre_push_smoke_20260530_190104.log` 通過，987 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26682250910` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / Web Preview UIUX contract / development log；本輪只增加 Crawler Asset display labels 與 Web 消費方式，不改 maturity/risk 判斷、crawler registry、download/import service、credential storage 或 Tk 操作。
## 2026-05-30 18:49 Web capability fallback cleanup
- 本輪延續 Web UI display contract：資產卡片的「能力位址」在後端未提供 capability address 時顯示「待確認」，不再 fallback 到 `source_type` 短碼；能力膠囊摘要的 Seed 範式也改走 `displayTextOrFallback()`，避免缺 label 時把 `entry_listing` / `paginated_catalog` raw token 放進使用者可見摘要。
- 已提交實作：`6f20da2 Guard Web capability fallbacks`。
- 已驗證：`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest tests.test_web_preview -v` 通過，62 tests OK；完整 smoke `state\logs\pre_push_smoke_20260530_184921.log` 通過，987 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26682035145` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / Web Preview UIUX contract / development log；本輪只調整 Web 顯示 fallback 與靜態 guard，不改後端 payload、crawler registry、download/import service、credential storage 或 Tk 操作。
## 2026-05-30 18:37 Web stage label ownership cleanup
- 本輪移除 Web `downloadImportStageText()` 內的 download/import stage 翻譯表；Web 只消費後端 `download_import.stage_label` / display label，缺 label 時落到「下載狀態待確認」，避免 stage 文案 ownership 回流到 JS。
- 已提交實作：`c972bdd Remove Web stage label map`。
- 已驗證：`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest tests.test_web_preview -v` 通過，62 tests OK；完整 smoke `state\logs\pre_push_smoke_20260530_183533.log` 通過，987 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26681755877` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / Web Preview UIUX contract / development log；本輪只移除 Web 端重複 stage 翻譯表與補靜態 guard，不改後端 payload、download/import 執行語意、crawler registry、credential storage 或 Tk 操作。
## 2026-05-30 18:28 Download/import stage label payload
- 本輪把上一個 Web fallback 的 stage 文案往後端 display payload 收斂：`crawler_asset_download_import_display_payload()` 會輸出 `download_import.stage_label`，Web download/import credential-blocked payload 也會輸出同一類 label，讓 Web/Tk/未來 Qt 可顯示「下載 / 匯入完成」「下載前需處理」而不必自行翻譯 `download_import_completed` / `blocked_before_download`。
- 已提交實作：`cb94da4 Add download import stage labels`。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawler_asset_display.py frontends\web\preview_payloads.py tests\test_crawler_asset_download.py tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_crawler_asset_download tests.test_web_preview -v` 通過，66 tests OK；完整 smoke `state\logs\pre_push_smoke_20260530_182547.log` 通過，987 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26681570087` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / Web Preview UIUX contract / development log；本輪只增加 shared display payload 欄位與 Web blocked response label，不改 download/import 執行語意、crawler registry、credential storage 或 Tk 操作。
## 2026-05-30 18:12 Web stage/review fallback guard
- 本輪延續 Web UI display contract：下載 / 匯入結果列的 Stage 改用 `downloadImportStageText()`，content review bucket、import lane、credential save mission、event context chips 與 Seed 範式 fallback 都會透過 display-safe helper，避免 label 缺失時把 `download_import_completed`、`content_parser_required`、`content_parser_review`、`entry_listing` 等 raw backend token 當成人類文案。
- 已提交實作：`c319655 Guard Web stage and review fallbacks`。
- 已驗證：`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest tests.test_web_preview -v` 通過，62 tests OK；完整 smoke `state\logs\pre_push_smoke_20260530_181251.log` 通過，987 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26681344585` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / Web Preview UIUX contract / development log；本輪只調整 Web 顯示 fallback 與靜態防回歸測試，不改後端 payload、crawler registry、download/import service、credential storage 或 Tk 操作。
## 2026-05-30 17:55 SQLite import write gate
- 本輪補上第一個後端 DB write gate：新增 `api_launcher.sqlite_write_gate`，以 process-local / per-SQLite-path `RLock` 序列化同一 Python process 內的 SQLite writer；CSV/JSON importer 與 download-plan import policy decision 都已進入 `sqlite_write_gate()`，避免同一 curated SQLite path 被同 process 多個 import worker 同時寫入或同時做 rename/replace 決策。
- 已提交實作：`7eb4e9a Gate SQLite import writes`。
- 已驗證：`py -3 -B -m py_compile api_launcher\sqlite_write_gate.py api_launcher\importers\csv_importer.py api_launcher\importers\json_importer.py api_launcher\downloads\plan_runner.py api_launcher\project_maturity.py tests\test_sqlite_write_gate.py tests\test_project_maturity.py` OK；`py -3 -B -m unittest tests.test_sqlite_write_gate tests.test_csv_importer tests.test_json_importer tests.test_project_maturity -v` 通過，20 tests OK；`py -3 -B -m unittest tests.test_ingestion_pipeline tests.test_crawler_asset_download tests.test_download_jobs tests.test_project_maturity tests.test_sqlite_write_gate -v` 通過，19 tests OK；`py -3 -B APIkeys_collection.py --project-maturity-json` 已顯示 `background_jobs_and_scheduler.metrics.sqlite_write_gate_available=true`；完整 smoke `state\logs\pre_push_smoke_20260530_175518.log` 通過，987 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26681030452` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / project maturity matrix / development log；本輪只增加 process-local SQLite write gate 與成熟度 metrics，不改下載 URL、內容 parser、crawler registry、credential storage、Tk/Web 操作或 user guide。限制：這不是跨 process / 跨 app instance lock，也不是完整 bounded job scheduler。
## 2026-05-30 17:39 Tk next-action fallback guard
- 本輪把 Tk crawler asset helper 裡幾個「label 缺失時退回 raw next_action / stale reason」的訊息收掉：blocked download-plan summary、Plan Passport stale summary、credential guard message、credential summary 都只使用 `_ui_next_action_text()` 產生的人類文案或中性 fallback。
- 已提交實作：`a223c62 Guard Tk next-action fallbacks`。
- 已驗證：`py -3 -B -m unittest tests.test_tk_ui_helpers tests.test_tk_dialogs -v` 通過，142 tests OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_173622.log` 通過，983 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26680645293` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只調整 Tk helper 顯示 fallback，不改 backend payload、crawler registry、download/import service、credential storage 或 Web 操作。
## 2026-05-30 17:32 Web UIUX display contract doc sync
- 本輪是小型 consolidation / docs drift 修補：`docs/WEB_PREVIEW_UIUX.zh-TW.md` 已把 Plan Passport freshness guard 從 `stale_next_action` raw token 校正成 `stale_next_action_label`，並補上 Web 使用者可見文字不得 fallback 到 snake_case / raw backend token 的規則。
- 已提交文檔：本 checkpoint 只更新協作文檔，未改產品碼。
- 已驗證：docs mojibake scan OK；`git diff --check` OK。
- Docs drift check：本輪就是 drift 修補；只更新 Web UIUX contract，不改 Web/Tk/後端行為，也不需要跑 RRKAL 測試。
## 2026-05-30 17:24 Web display fallback guard
- 本輪把 Web Preview 多處「label 缺失時直接顯示 raw backend token」的 fallback 收斂成 `displayTextOrFallback()`：Downloader row、Crawler Passport、Credential badge、Plan Preview mission、Seed import badge、Hero next action、Plan Passport stale/next action 都會拒絕 snake_case / raw token 當人類文案。
- 已提交實作：`64f1fed Guard Web display text fallbacks`。
- 已驗證：`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest tests.test_web_preview -v` 通過，62 tests OK；`git diff --check` 無 whitespace error（Git 仍提示 `frontends/web/static/app.js` line-ending warning）；完整 smoke `state\logs\pre_push_smoke_20260530_172115.log` 通過，983 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26680390399` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只調整 Web 顯示 fallback 與靜態防回歸測試，不改後端 payload、crawler registry、download/import service、credential storage 或 Tk 操作。
## 2026-05-30 17:12 Web download/import action labels
- 本輪把 Web Preview 的正式下載 / 匯入訊息再往後端 display payload 收斂：asset-level 與 seed-level download/import 失敗或 review-required 訊息改用 `downloadImportNextActionText()`，只顯示 `next_action_label` 類人類文案；plan chip 也不再 fallback 到 raw `outcome_bucket`。
- 已提交實作：`2f0586a Hide Web download action ids`。
- 已驗證：`py -3 -B -m unittest tests.test_web_preview -v` 通過，62 tests OK；`git diff --check` 無 whitespace error（Git 仍提示 `frontends/web/static/app.js` line-ending warning）；本切片 UTF-8/mojibake check OK；完整 smoke `state\logs\pre_push_smoke_20260530_170812.log` 通過，983 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26680156433` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只調整 Web download/import 顯示 fallback 與靜態防回歸測試，不改 download/import service、plan resolver、crawler registry、credential storage 或 Tk 操作。
## 2026-05-30 17:01 Crawler asset health labels
- 本輪把 Crawler Asset health payload 補上 `status_label`、`status_tone` 與 `next_action_label`；Web asset passport 與 selected hero 的 state pill 改讀 `card.health.status_label`，未知 status fallback 也不再直接顯示 raw id。
- 已提交實作：`61fb8d1 Add crawler asset health labels`。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawler_asset_health.py tests\test_crawler_assets.py tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_crawler_assets tests.test_web_preview -v` 通過，108 tests OK；`git diff --check` 無 whitespace error（Git 仍提示 `frontends/web/static/app.js` line-ending warning）；health label slice UTF-8/mojibake check OK；完整 smoke `state\logs\pre_push_smoke_20260530_165759.log` 通過，983 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26679912192` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只調整 health display payload 與 Web state pill 消費方式，不改 health evaluation、crawler registry、download/import、credential storage 或 Tk 操作。
## 2026-05-30 16:48 Crawler asset capability row labels
- 本輪是小型 consolidation：`crawler_asset_card_capabilities()` 會輸出 capability `status_label` 與 `next_action_label`，Web asset passport 的 capability row 只顯示人類文案，不再直接組 `capability.status / capability.next_action`。
- 已提交實作：`85485b6 Label crawler asset capability rows`。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawler_asset_capabilities.py api_launcher\crawler_asset_flow_display.py tests\test_crawler_assets.py tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_crawler_assets tests.test_web_preview -v` 通過，108 tests OK；同一組測試前一次遇到 Windows localhost oversized-body socket flake，單測與全組 rerun 均通過；`git diff --check` 無 whitespace error（Git 仍提示 `frontends/web/static/app.js` line-ending warning）；capability label slice UTF-8/mojibake check OK；完整 smoke `state\logs\pre_push_smoke_20260530_164446.log` 通過，983 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26679666184` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只調整 asset card capability display payload 與 Web passport 消費方式，不改 capability status 判斷、crawler registry、download/import、credential storage 或 Tk 操作。
## 2026-05-30 16:33 Web bounds/probe display fallback
- 本輪修掉 Web Preview 兩個 raw status fallback：seed schema probe 完成 mission 不再 fallback 到 `payload.schema_probe.status`，bounds form 狀態 pill 改吃後端 `spec.display_label`，不再直接顯示 `spec.status`。
- 已提交實作：`0255727 Use bound form labels in Web UI`。
- 已驗證：`py -3 -B -m unittest tests.test_web_preview -v` 通過，62 tests OK；`git diff --check` 無 whitespace error（Git 仍提示 `frontends/web/static/app.js` line-ending warning）；Web slice UTF-8/mojibake check OK；完整 smoke `state\logs\pre_push_smoke_20260530_162942.log` 通過，982 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26679378203` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只調整 Web 顯示 fallback，不改 schema probe service、bounds form schema、download/import、credential storage、crawler registry 或 Tk 操作。
## 2026-05-30 16:21 Remote pagination status labels
- 本輪延續 UI display contract：`crawler_remote_pagination_payload()` 會輸出遠端分頁狀態的人類顯示 payload，Tk seed enumeration note 優先顯示「仍有下一頁線索」「已列完」「遠端狀態待確認」等文案，不再把未知 remote status raw id 直接放進使用者可見內容。
- 已提交實作：`c71c830 Label remote pagination statuses`。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawler_seed_display.py api_launcher\crawler_asset_listing_payloads.py frontends\tk\crawler_asset_ui_helpers.py tests\test_crawler_assets.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_crawler_assets tests.test_tk_dialogs tests.test_web_preview -v` 通過，226 tests OK；同一組測試前一次遇到 Windows localhost oversized-body socket flake，單測與全組 rerun 均通過；`git diff --check` OK；`api_launcher` / `frontends` / `tests` mojibake scan OK；完整 smoke `state\logs\pre_push_smoke_20260530_161735.log` 通過，982 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26679162441` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只調整 remote pagination display payload 與 Tk seed enumeration note fallback，不改 crawler pagination 行為、token storage、seed enumeration limits、download/import、Web 操作或 user guide。
## 2026-05-30 16:03 Account provider support status labels
- 本輪延續 UI display contract：`api_launcher.account_links` 新增帳號登入模式與支援狀態 label helper；Tk Google/Gemini 連線視窗的帳號支援表格會顯示「OAuth 登入」「規劃中」「🚧 施工中」等文案，不再把 `oauth` / `planned` / `skeleton` raw contract id 當成使用者文字。
- 已提交實作：`418efa9 Label account provider support status`。
- 已驗證：`py -3 -B -m py_compile api_launcher\account_links.py frontends\tk\ai_settings_dialogs.py tests\test_account_links.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_account_links tests.test_tk_dialogs -v` 通過，123 tests OK；`git diff --check` OK；`api_launcher` / `frontends` / `tests` mojibake scan OK；完整 smoke `state\logs\pre_push_smoke_20260530_160327.log` 通過，981 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26678879682` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只調整帳號支援表格顯示文案，不改 OAuth/API key storage、credential flow、account provider contract、crawler registry、download/import、Web 操作或 user guide。
## 2026-05-30 15:49 Dataset candidate review status labels
- 本輪延續 UI display contract：新增 `api_launcher.dataset_candidate_display`，把 Dataset Candidate Review 的 `needs_review` / `approved` / `planned` / `rejected` / `all` 狀態顯示文案集中到後端 helper；Tk review dialog 的表格、detail 與 filter 下拉只顯示人類文案，送 repository 查詢或更新時才轉回 raw status id。
- 已提交實作：`d567e7d Label dataset candidate review status`。
- 已驗證：`py -3 -B -m py_compile api_launcher\dataset_candidate_display.py frontends\tk\dataset_candidate_review_dialog.py frontends\tk\table_data_workflows.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs tests.test_web_preview -v` 通過，180 tests OK；`git diff --check` OK；`api_launcher` / `frontends` / `tests` mojibake scan OK；完整 smoke `state\logs\pre_push_smoke_20260530_154916.log` 通過，980 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26678612556` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只調整 Dataset Candidate Review 狀態顯示與 Tk filter mapping，不改 candidate repository schema、crawler registry、download/import、Web 操作或 user guide。
## 2026-05-30 15:39 Adapter review item display helper
- 本輪是小型 consolidation：新增 `adapter_review_item_display_payload()`，把 Adapter Review item 的 required action、outcome bucket、content import status、content review bucket、content pipeline lane、content next action label 集中到後端 display helper；Tk dialog 只消費這份 payload，不再自行翻譯多組 enum。
- 已提交實作：`3d179a7 Centralize adapter review item labels`。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawler_asset_review_display.py api_launcher\crawler_asset_display.py frontends\tk\adapter_review_dialog.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs tests.test_web_preview -v` 通過，180 tests OK；`git diff --check` OK；`api_launcher` / `frontends` mojibake scan OK；完整 smoke `state\logs\pre_push_smoke_20260530_153556.log` 通過，980 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26678335312` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只收斂 Adapter Review item 顯示投影 ownership，不改 adapter review item JSON、resolver、download/import、crawler registry、credential storage、Web 操作或 user guide。
## 2026-05-30 15:26 Tk Adapter review detail labels
- 本輪延續 Adapter Review UI contract：detail text 內的 `outcome_bucket`、`content_import_status`、`content_review_bucket`、`content_pipeline_lane` value 也改用共用 display helper，顯示「來源解析待辦」「需內容 Parser review」「內容 Parser 待辦」等文案，不再把 `source_resolution_required` / `content_parser_required` / `content_parser_review` 直接放進使用者可見 detail。
- 已提交實作：`e4e3ca1 Label adapter review detail buckets`。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawler_asset_review_display.py api_launcher\crawler_asset_display.py frontends\tk\adapter_review_dialog.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs tests.test_web_preview -v` 通過，180 tests OK；`git diff --check` OK；`api_launcher` / `frontends` / `tests` mojibake scan OK；完整 smoke `state\logs\pre_push_smoke_20260530_152157.log` 通過，980 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26678102571` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只調整 Adapter Review detail display labels，不改 adapter review item JSON、resolver、download/import、crawler registry、credential storage、Web 操作或 user guide。
## 2026-05-30 15:12 Tk Adapter review action labels
- 本輪修掉 Tk Adapter Review 對話框的 raw action id 顯示：表格與 detail text 會用 shared `next_action_display_label_or_fallback()` 顯示「解析 API，產生可下載 resources」「新增內容 Parser 或保留原始檔」等人類文案，不再把 `resolve_api` / `add_content_parser_or_keep_raw_artifact` 直接放進使用者可見內容。
- 已提交實作：`d5fba12 Label adapter review actions in Tk`。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawler_next_action_display.py frontends\tk\adapter_review_dialog.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_crawler_next_action_display tests.test_tk_dialogs tests.test_web_preview -v` 通過，183 tests OK；`git diff --check` OK；`api_launcher` / `frontends` / `tests` mojibake scan OK；完整 smoke `state\logs\pre_push_smoke_20260530_150912.log` 通過，980 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26677811389` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只調整 Tk Adapter review 顯示文案與共用 action label 表，不改 adapter review resolver、download/import、crawler registry、credential storage、Web 操作或 user guide。
## 2026-05-30 14:54 unknown next_action UI fallback
- 本輪把 user-facing 的 `next_action` fallback 收到共用 display helper：新增 `next_action_display_label_or_fallback()`，讓 Tk/Web/後端 display payload 在遇到尚未登錄的新 snake_case action id 時顯示安全人類提示，不再把 raw backend id 直接丟給使用者。
- 已提交實作：`8e9788c Hide unknown next action ids from UI`。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawler_next_action_display.py api_launcher\crawler_asset_download.py api_launcher\crawler_asset_display.py api_launcher\crawler_plan_outcome_display.py frontends\web\preview_assets.py frontends\web\preview_payloads.py frontends\tk\crawler_asset_ui_helpers.py tests\test_crawler_next_action_display.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_crawler_next_action_display tests.test_tk_dialogs tests.test_crawler_assets tests.test_web_preview tests.test_crawler_asset_download -v` 通過，232 tests OK；`git diff --check` OK；`api_launcher` / `frontends` / `tests` mojibake scan OK；完整 smoke `state\logs\pre_push_smoke_20260530_145227.log` 通過，980 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26677496659` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只調整 UI/display fallback，不改 crawler asset listing、download/import 執行語意、credential storage、crawler registry 或 user guide。
## 2026-05-30 14:35 Tk crawler asset row fallback label
- 本輪修掉 Tk Crawler Asset 表格的另一個 raw id fallback：當資產還沒有最近下載計畫結果時，最後欄位會用 `next_action_display_label(asset.next_action)`，不再把 `run_full_crawl_or_export_candidates` 這類 action id 直接顯示給使用者。
- 已提交實作：`d4f924d Label crawler asset row fallback actions`。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawler_next_action_display.py frontends\tk\crawler_asset_ui_helpers.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 通過，115 tests OK；`py -3 -B -m unittest tests.test_crawler_assets tests.test_tk_dialogs tests.test_web_preview -v` 通過，222 tests OK；`git diff --check` OK；`api_launcher` / `frontends` mojibake scan OK；完整 smoke `state\logs\pre_push_smoke_20260530_143559.log` 通過，974 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26677141154` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只調整 Tk table display fallback，不改 crawler asset profile、listing、download/import、Web 操作、credential storage、crawler registry 或 user guide。
## 2026-05-30 14:24 stale plan passport action labels
- 本輪把 stale Plan Passport 的下一步也補成 UI-neutral display payload：`crawler_asset_plan_passport_for_profile()` 會輸出 `stale_next_action_label`，Tk/Web 顯示優先使用人類文案，不再把 `enable_before_building_download_plan` 這類 raw action id 放進使用者可見摘要。
- 已提交實作：`6a0c27c Label stale plan passport actions`。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawler_asset_profiles.py api_launcher\crawler_next_action_display.py frontends\tk\crawler_asset_ui_helpers.py tests\test_crawler_assets.py tests\test_tk_dialogs.py tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_crawler_assets tests.test_tk_dialogs tests.test_web_preview -v` 通過，221 tests OK；`git diff --check` OK；`api_launcher` / `frontends` mojibake scan OK；完整 smoke `state\logs\pre_push_smoke_20260530_142419.log` 通過，973 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26676890389` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只調整 stale Plan Passport display contract，不改 plan staleness 判斷、profile storage、download/import、Web/Tk 操作流程、credential storage、crawler registry 或 user guide。
## 2026-05-30 14:09 Tk bounds warning text
- 本輪把 Tk Crawler Asset 界域表單的警示預覽改成人類文案：`crawler_asset_bound_warning_text()` 會說明「欄位探測」或「探測結果已套用但仍需人工確認」，不再把 `warning_codes` / `schema_probe_*` raw id 直接顯示給使用者。
- 已提交實作：`55a180d Hide bounds warning codes in Tk`。
- 已驗證：`py -3 -B -m py_compile frontends\tk\crawler_asset_bound_dialog.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs tests.test_crawler_assets tests.test_web_preview -v` 通過，221 tests OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_140930.log` 通過，973 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26676617783` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只調整 Tk warning display contract，不改 schema probe service、bounds payload、download/import、Web 操作、credential storage、crawler registry 或 user guide。
## 2026-05-30 13:55 download bound display labels
- 本輪把 `download_bound_status` 補成 UI-neutral display payload：後端新增 `applied_labels.zh_TW/en`，Tk plan bounds status 優先顯示「樣本上限、時間範圍、下載大小上限」這類人類文案，不再把 `sample_limit` / `max_bytes_enforced` raw code 直接丟給使用者。
- 已提交實作：`4abe249 Show download bound labels in Tk`。
- 已驗證：`py -3 -B -m py_compile api_launcher\source_download.py frontends\tk\plan_workflows.py tests\test_source_download.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_source_download tests.test_tk_dialogs -v` 通過，123 tests OK；`py -3 -B -m unittest tests.test_source_download tests.test_tk_dialogs tests.test_tk_ui_helpers tests.test_crawler_asset_download -v` 通過，150 tests OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_135528.log` 通過，971 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26676323224` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只增加 backend display labels 並讓 Tk plan status 消費它，不改 download/import 行為、Web 操作、credential storage、crawler registry 或 user guide。
## 2026-05-30 13:42 max_bytes bound status contract
- 本輪沒有改 HTTP 下載 enforcement；只把 `download_bound_status.applied` 中的 `max_bytes` 狀態從舊的 `max_bytes_review` 改成 `max_bytes_enforced`，讓 Tk/Web/agent 讀 plan payload 時知道 byte cap 已由 `HTTPDownloadAdapter` 執行，不再把它誤解成 review-only metadata。
- 已提交實作：`3ff00fc Clarify max bytes bound status`。
- 已驗證：`py -3 -B -m py_compile api_launcher\source_download.py tests\test_source_download.py` OK；`py -3 -B -m unittest tests.test_source_download -v` 通過，11 tests OK；`py -3 -B -m unittest tests.test_source_download tests.test_http_downloader tests.test_download_plan_runner tests.test_crawler_asset_download tests.test_tk_ui_helpers -v` 通過，60 tests OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_134217.log` 通過，971 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26676072708` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只修正 backend payload label，不改 Web/Tk 操作流程、實際 download/import 行為、credential storage、crawler registry 或 user guide。
## 2026-05-30 11:44 Metadata probe truncation flag
- 本輪沒有改 metadata crawl 的 bounded excerpt 行為，只補上 agent/UI 可讀的 `truncated` flag：`safe_fetch_metadata()` 讀到超過 `max_bytes` 的成功 response 時，仍只保留 bounded excerpt，但 payload 會明確標示 `truncated=true`，避免把摘要誤認成完整頁面。
- 已提交實作：`3bea35b Expose metadata probe truncation flag`。
- 已驗證：`py -3 -B -m py_compile api_launcher\core.py tests\test_metadata_probe.py` OK；`py -3 -B -m unittest tests.test_metadata_probe -v` 通過，3 tests OK；`api_launcher` mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_114424.log` 通過，971 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26673700933` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 handoff / development log；本輪只新增 metadata probe JSON 欄位，不改 provider discovery、crawler registry、download/import、Web/Tk 操作或 user guide。
## 2026-05-30 11:34 Download max_bytes enforcement
- 本輪把 `SourceDownloadBounds.max_bytes` 從 plan metadata / review 標記接到實際 HTTP adapter：`download_bounds.max_bytes` 為正數時，`HTTPDownloadAdapter` 會用 `Content-Length` / `Content-Range` 提前拒絕超量下載，未知總長度時也會在 chunk 累計超過 budget 前 fail-fast。
- 已提交實作：`a0ee7bc Enforce download max byte bounds`。
- 已驗證：`py -3 -B -m py_compile api_launcher\downloads\http.py tests\test_http_downloader.py` OK；`py -3 -B -m unittest tests.test_http_downloader tests.test_download_plan_runner tests.test_source_download -v` 通過，33 tests OK；`api_launcher` / tests mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_113427.log` 通過，970 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26673503912` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只讓既有 `max_bytes` bounds 在 HTTP download layer 生效，不改 Web/Tk 表單操作、crawler registry、adapter resolver、credential storage 或 user guide。
## 2026-05-30 11:19 Schema probe oversized response guard
- 本輪延續 bounded probe hardening：`fetch_probe_bytes()` 現在會讀 `max_bytes + 1`，若 schema/head probe response 超過 budget 會明確 raise `ValueError`，避免用截斷 CSV/JSON 推論欄位並誤導 Web/Tk 界域表單。
- 已提交實作：`53ac5bd Reject oversized schema probe responses`。
- 已驗證：`py -3 -B -m py_compile api_launcher\schema_probe.py tests\test_source_download.py` OK；`py -3 -B -m unittest tests.test_source_download tests.test_tk_dialogs tests.test_web_preview -v` 通過，185 tests OK；`api_launcher` mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_111958.log` 通過，969 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26673225198` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只加固 schema/head probe response budget，不改 Web/Tk 操作流程、crawler registry、download/import、credential storage 或 user guide。
## 2026-05-30 11:08 Crawler registry maturity metrics
- 本輪沒有重寫 crawler registry；確認 `CrawlerSpec` / `@crawler(...)` / 4-bit capability address / seed scope registry 已落地後，只把成熟度 JSON 的 source handler row 補齊 registry 證據：`registry_matrix_cell_count`、`capability_address_width`、`capability_address_group_count`、`seed_scope_counts`、`dispatch_owner` 與相容 surface。
- 已提交實作：`8ce74e7 Expose crawler registry maturity metrics`。
- 已驗證：`py -3 -B -m py_compile api_launcher\project_maturity.py tests\test_project_maturity.py` OK；`py -3 -B -m unittest tests.test_project_maturity tests.test_dataset_discovery -v` 通過，63 tests OK；`py -3 -B APIkeys_collection.py --project-maturity-json` 可看到 source handler row 的 registry metrics；`api_launcher` mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_110838.log` 通過，968 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26672959016` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只擴充成熟度 JSON 證據，不改 crawler handler、registry dispatch、Web/Tk 操作、download/import、credential storage 或 user guide。

## 2026-05-30 10:58 Web Preview POST body guard
- 本輪替 Web Preview localhost API 加上 request body budget：`DEFAULT_WEB_PREVIEW_POST_BODY_MAX_BYTES=1024 * 1024`，`read_json_body()` 與 `discard_request_body()` 都會先檢查 `Content-Length`，oversized POST body 會回 400，不會進入 crawler asset route handler 或 developer diagnostic handler。
- 已提交實作：`461c749 Bound Web preview POST bodies`。
- 已驗證：`py -3 -B -m py_compile frontends\web\server.py tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 通過，62 tests OK；`frontends\web` / tests mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_105811.log` 通過，968 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26672739923` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / Web Preview UIUX notes / development log；本輪只加固本機 Web Preview POST body budget，不改 Web UI 操作、crawler、download/import、credential storage、Tk 操作或 user guide。

## 2026-05-30 10:46 Favicon oversized response guard
- 本輪把 Tk favicon 快取的 byte budget 從「只 bounded read」加固成「讀 `max_bytes + 1` 並拒絕 oversized response」：`download_favicon_png()` 遇到超過 `DEFAULT_FAVICON_MAX_BYTES` 的 favicon payload 會 fail-fast，不把異常大 response 交給 Pillow 解析。
- 已提交實作：`491b711 Reject oversized favicon responses`。
- 已驗證：`py -3 -B -m py_compile api_launcher\favicons.py tests\test_favicons.py` OK；`py -3 -B -m unittest tests.test_favicons tests.test_tk_dialogs -v` 通過，118 tests OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_104606.log` 通過，965 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26672465125` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只加固 favicon response budget，不改 favicon URL 正規化、cache path、Tk/Web 操作、crawler、download/import、credential 或 user guide。

## 2026-05-30 10:37 Source pattern oversized probe guard
- 本輪把 source pattern detector 的 probe byte budget 從「只 bounded read」加固成「讀 `max_bytes + 1` 並拒絕 oversized response」：`fetch_pattern_probe()` 遇到超過 `DEFAULT_PATTERN_PROBE_MAX_BYTES` 的 payload 會回 `None`，讓 detector 安全降級到 `unknown` / review，而不是用截斷 JSON/HTML 誤判來源範式。
- 已提交實作：`fe6fa58 Reject oversized source pattern probes`。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawlers\source_patterns.py tests\test_source_patterns.py` OK；`py -3 -B -m unittest tests.test_source_patterns tests.test_source_pattern_drafts -v` 通過，41 tests OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_103738.log` 通過，964 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26672279172` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / dataset discovery notes / development log；本輪只加固 detector probe budget，不改 detector registry、source draft review gate、crawler handlers、download/import、credential、Tk/Web 操作或 user guide。

## 2026-05-30 10:28 Tk scheduler guard metrics
- 本輪把 Tk scheduler 測試護欄也接進 `--project-maturity-json`：`background_jobs_and_scheduler.metrics` 現在除了 policy count / max-active table，也輸出 `capacity_policy_call_site_guarded=true`、`direct_thread_spawn_guarded=true`、`direct_thread_spawn_owner=frontends/tk/background_jobs.py` 與對應 guard test 名稱。
- 已提交實作：`a6ee50e Expose Tk scheduler guard metrics`。
- 已驗證：`py -3 -B -m py_compile api_launcher\project_maturity.py tests\test_project_maturity.py` OK；`py -3 -B -m unittest tests.test_project_maturity tests.test_tk_background_jobs -v` 通過，13 tests OK；`py -3 -B APIkeys_collection.py --project-maturity-json` 顯示 scheduler guard metrics；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_102820.log` 通過，963 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26672090649` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / project maturity matrix / development log；本輪只擴充成熟度 JSON 的 metrics，不改 Tk runtime 行為、policy 數量、crawler、download/import、credential、Web 操作或 user guide。

## 2026-05-30 10:19 Tk direct thread guard
- 本輪補第二道 Tk scheduler 測試護欄：`tests/test_tk_background_jobs.py` 會用 AST 掃描 `frontends/tk/*.py`，要求 Tk 模組除了 `frontends/tk/background_jobs.py` 以外不能直接呼叫 `threading.Thread` / `Thread(...)`；未來背景 worker 必須經由共用 helper 與 policy registry。
- 已提交實作：`8eae394 Guard Tk direct thread spawning`。
- 已驗證：`py -3 -B -m py_compile tests\test_tk_background_jobs.py` OK；`py -3 -B -m unittest tests.test_tk_background_jobs -v` 通過，9 tests OK；`py -3 -B -m unittest tests.test_tk_background_jobs tests.test_tk_dialogs -v` 通過，121 tests OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_101939.log` 通過，963 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26671893236` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只新增測試 guardrail，不改 Tk runtime 行為、policy 數量、crawler、download/import、credential、Web 操作或 user guide。

## 2026-05-30 10:10 Tk background capacity policy guard
- 本輪補測試護欄：`tests/test_tk_background_jobs.py` 會用 AST 掃描 `frontends/tk/*.py`，確保所有 `start_single_flight_thread(...)` call site 都明確傳入 `max_active_jobs`，避免未來新增 Tk 背景 worker 時繞過 `frontends/tk/background_job_policies.py`。
- 已提交實作：`57ae939 Guard Tk background job capacity policy`。
- 已驗證：`py -3 -B -m py_compile tests\test_tk_background_jobs.py` OK；`py -3 -B -m unittest tests.test_tk_background_jobs -v` 通過，8 tests OK；`py -3 -B -m unittest tests.test_tk_background_jobs tests.test_tk_dialogs -v` 通過，120 tests OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_101011.log` 通過，962 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26671701107` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只新增測試 guardrail，不改 Tk runtime 行為、policy 數量、crawler、download/import、credential、Web 操作或 user guide。

## 2026-05-30 09:59 Remaining Tk background job caps
- 本輪補齊 Tk policy registry 覆蓋面：developer CLI subprocess、MVP demo smoke、showcase download 也納入 `frontends/tk/background_job_policies.py`，每個 UI instance 同時最多 1 個；`--project-maturity-json` 的 `background_jobs_and_scheduler.metrics.bounded_tk_policy_count` 現在為 11。
- 已提交實作：`66ca52e Cap remaining Tk background jobs`。
- 已驗證：`py -3 -B -m py_compile frontends\tk\background_job_policies.py frontends\tk\developer_cli_dialog.py frontends\tk\mvp_demo_workflows.py frontends\tk\showcase_workflows.py tests\test_tk_background_jobs.py` OK；`py -3 -B -m unittest tests.test_tk_background_jobs tests.test_tk_dialogs tests.test_project_maturity -v` 通過，123 tests OK；`py -3 -B APIkeys_collection.py --project-maturity-json` 顯示 `bounded_tk_policy_count=11` 並包含 `developer_cli` / `mvp_demo_smoke` / `showcase_download`；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_095939.log` 通過，961 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26671489455` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / project maturity matrix / development log；本輪只補 Tk background job caps，不改 subprocess 命令語義、MVP demo/showcase 內容、crawler、download/import、credential、Web 操作或 user guide。

## 2026-05-30 09:49 Tk background policy metrics in maturity JSON
- 本輪修正文檔漂移：`docs/PROJECT_MATURITY_MATRIX.zh-TW.md` 已說 Tk 背景工作上限有 typed policy registry，但 `--project-maturity-json` 的 `background_jobs_and_scheduler` row 仍是舊描述、metrics 空白。現在 `api_launcher.project_maturity` 會輸出 `policy_registry_available=true`、`bounded_tk_policy_count` 與 `max_active_jobs_by_policy`，讓 Web/Tk/agent 讀成熟度矩陣時看得到 scheduler hardening 的已完成部分與剩餘限制；09:59 後目前 count 已是 11。
- 已提交實作：`4ba6576 Expose Tk background policy metrics`。
- 已驗證：`py -3 -B -m py_compile api_launcher\project_maturity.py tests\test_project_maturity.py frontends\tk\background_job_policies.py` OK；`py -3 -B -m unittest tests.test_project_maturity tests.test_tk_background_jobs -v` 通過，11 tests OK；`py -3 -B APIkeys_collection.py --project-maturity-json` 已顯示 `background_jobs_and_scheduler.metrics.max_active_jobs_by_policy.sqlite_import=1`；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_094947.log` 通過，961 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26671260990` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 handoff / development log / project maturity matrix；本輪只修正 machine-readable maturity payload，不改 Tk/Web 操作、crawler、download/import、credential 或 user guide。

## 2026-05-30 09:40 Tk background job policy registry
- 本輪把 Tk 背景工作容量上限收斂成 `frontends/tk/background_job_policies.py` 的 typed policy registry：AI summary、crawler asset、discovery、OAuth、plan bounds probe、sidebar favicon、source action、SQLite import 都從同一張 policy table 匯入 `max_active_jobs` 常數；workflow 仍只負責 UI handoff，沒有引入全域 scheduler 或 asyncio 重寫。
- 已提交實作：`b2bcdf9 Declare Tk background job policies`。
- 已驗證：`py -3 -B -m py_compile frontends\tk\background_job_policies.py frontends\tk\background_jobs.py frontends\tk\crawler_asset_workflows.py frontends\tk\discovery_workflows.py frontends\tk\import_workflows.py frontends\tk\ai_summary_workflows.py frontends\tk\source_action_workflows.py frontends\tk\oauth_workflows.py frontends\tk\plan_workflows.py frontends\tk\sidebar_workflows.py tests\test_tk_background_jobs.py` OK；`py -3 -B -m unittest tests.test_tk_background_jobs -v` 通過，7 tests OK；`py -3 -B -m unittest tests.test_tk_background_jobs tests.test_tk_dialogs tests.test_tk_ui_helpers -v` 通過，142 tests OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_093807.log` 通過，961 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26671011263` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / project maturity matrix / development log；本輪只把已存在的 Tk background job caps 移到 declarative policy registry，不改 worker 行為、UI 操作、crawler、download/import、credential、Web 操作或 user guide。

## 2026-05-30 09:23 Tk OAuth background capacity guard
- 本輪延續 credential/login scheduler hardening：Tk Google browser login 與 device-code polling 仍用同一份 OAuth single-flight helper，但同一 UI 同時最多 2 個 OAuth background worker；queue 滿時走 capacity callback，不再開新的 callback server / token polling worker。
- 已提交實作：`79dea32 Bound Tk OAuth background jobs`。
- 已驗證：`py -3 -B -m py_compile frontends\tk\oauth_workflows.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 通過，112 tests OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_092339.log` 通過，958 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26670676995` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只增加 Tk OAuth 背景工作容量 guard，不改 token exchange/storage、credential UI、crawler、download/import、Web 操作或 user guide。

## 2026-05-30 09:14 Tk sidebar favicon capacity guard
- 本輪延續 bounded scheduler hardening：Tk sidebar favicon 背景下載現在同一 UI 同時最多 4 個 provider favicon worker；重複 owner/favicon 仍維持 single-flight，queue 滿時跳過本輪下載並清掉 loading marker，下一次 sidebar 重繪仍可再試。
- 已提交實作：`20d110c Bound Tk sidebar favicon jobs`。
- 已驗證：`py -3 -B -m py_compile frontends\tk\sidebar_workflows.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 通過，111 tests OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_091441.log` 通過，957 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26670478264` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只增加 Tk sidebar favicon 背景工作容量 guard，不改 favicon URL 推導、cache、下載 byte budget、crawler、download/import、credential、Web 操作或 user guide。

## 2026-05-30 09:04 Tk plan bounds probe capacity guard
- 本輪延續 bounded scheduler hardening：Tk 下載計畫的「界域欄位探測」現在有 capacity guard，同一 UI 同時最多 2 個 plan bounds/schema probe worker；同一 plan item 仍維持 single-flight，queue 滿時只更新狀態，不開新 thread。
- 已提交實作：`fb301fa Bound Tk plan bounds probe jobs`。
- 已驗證：`py -3 -B -m py_compile frontends\tk\plan_workflows.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 通過，110 tests OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_090436.log` 通過，956 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26670244075` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只增加 Tk plan bounds probe 背景工作容量 guard，不改 schema probe service、bounds form contract、download/import、crawler、credential、Web 操作或 user guide。

## 2026-05-30 08:55 Tk seed scope display label
- 本輪把 Tk Crawler Asset 表格與右側 Crawler Passport 也接到後端 `capability_profile.seed_scope_label`：`crawler_asset_row_values()` / `crawler_asset_detail_text()` 現在優先顯示「入口列表」「分頁 catalog」這類後端 label，只有缺 label 時才 fallback 到 raw `seed_scope` / `current_seed_scope`。
- 已提交實作：`96b1850 Show Tk seed scope label from profile`。
- 已驗證：`py -3 -B -m py_compile frontends\tk\crawler_asset_ui_helpers.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs tests.test_tk_ui_helpers -v` 通過，132 tests OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_085350.log` 通過，955 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26670001042` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log / discovery notes / Web Preview UIUX；本輪只改 Tk 顯示投影，不改 crawler handler、seed enumeration service、download/import、credential、Web 操作或 user guide。

## 2026-05-30 08:37 Seed scope display label contract
- 本輪把 `seed_scope` 的使用者可讀文案推回後端 capability profile：`CrawlerCapabilityProfile.to_dict()` 現在輸出 `seed_scope_label`，Web Preview 的 Crawler Passport 與能力膠囊摘要優先顯示這個後端 label，再 fallback 到 raw `seed_scope`。
- 已提交實作：`0dcc809 Add seed scope display label to profiles`。
- 已驗證：`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest tests.test_crawler_assets tests.test_web_preview -v` 通過，104 tests OK；`git diff --check` OK（僅既有 CRLF/LF warning）；完整 smoke `state\logs\pre_push_smoke_20260530_083705.log` 通過，954 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26669557147` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log / discovery notes / Web Preview UIUX；本輪只新增 UI-neutral display label，不改 seed scope registry、crawler handler、seed enumeration service、download/import、credential、Tk 操作或 user guide。

## 2026-05-30 08:26 Web seed scope passport display
- 本輪是 Web Preview thin-display slice：Crawler Passport 現在直接顯示 `capability_profile.seed_scope` 的 raw backend contract，能力膠囊摘要也包含 seed scope，讓使用者/agent 可看出 crawler 是 `entry_listing` 還是 `paginated_catalog`，但 Web 不自行從 `source_type` 推理 seed 枚舉語義。
- 已提交實作：`c3ad3f5 Show seed scope in Web Preview passport`。
- 已驗證：`node --check frontends\web\static\app.js` OK；`py -3 -B -m py_compile tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 通過，59 tests OK；`git diff --check` OK（僅既有 CRLF/LF warning）；完整 smoke `state\logs\pre_push_smoke_20260530_082633.log` 通過，954 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26669287121` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log / discovery notes / Web Preview UIUX；本輪只顯示既有 backend capability profile 欄位，不改 crawler handler、seed enumeration service、download/import、credential、Tk 操作或 user guide。

## 2026-05-30 08:17 Capability profile seed scope payload
- 本輪延續 crawler seed scope registry slice：`CrawlerCapabilityProfile` 新增 `seed_scope`，crawler asset payload 的 `capability_profile` 現在會直接輸出 registry 宣告的 `entry_listing` / `paginated_catalog`，讓 Tk/Web/未來 Qt 不必從 `source_type` 或 `current_seed_scope` 反推 crawler 本身的 seed 枚舉語義。
- 已提交實作：`38b4a8f Expose seed scope in capability profile`。
- 已驗證：in-memory compile `api_launcher\crawler_capability_profiles.py` / `tests\test_crawler_assets.py` OK；`py -3 -B -m unittest tests.test_crawler_assets tests.test_web_preview -v` 通過，104 tests OK；sample `html_file_index` asset payload 輸出 `capability_profile.seed_scope=entry_listing`；`api_launcher` / tests mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_081522.log` 通過，954 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26668930811` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log / discovery notes；本輪只增加 crawler asset capability profile payload 欄位，不改 Web/Tk 既有操作流程、crawler handler、download/import、credential 或 user guide。

## 2026-05-30 08:06 Crawler seed scope registry metadata
- 本輪是 bounded declarative registry slice：`CrawlerSpec` 新增 `seed_scope`，14 個 crawler handler 的 decorator 現在明確宣告 `entry_listing` 或 `paginated_catalog`；`dataset_seed_coverage.py` 改由 registry metadata 產生 entry-listing / paginated-catalog source type set，不再自行維護一份平行硬編碼清單。
- 已提交實作：`4052c5f Declare crawler seed scope metadata`。
- 已驗證：in-memory compile `api_launcher\crawlers\registry.py` / `api_launcher\crawlers\dataset_sources.py` / `api_launcher\dataset_seed_coverage.py` / `api_launcher\crawler_registry_report.py` / 相關 tests OK；`py -3 -B -m unittest tests.test_dataset_discovery tests.test_developer_diagnostics -v` 通過，63 tests OK；`py -3 -B -m unittest tests.test_crawler_assets tests.test_crawler_audit_smoke tests.test_handoff tests.test_heartbeat -v` 通過，81 tests OK；`--crawler-registry-report-json` 已輸出 `dimensions.seed_scope={'entry_listing': 4, 'paginated_catalog': 10}`；`api_launcher` / tests mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_080433.log` 通過，954 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26668632330` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log / discovery notes；本輪只把 seed coverage 的 source-type 分組來源移到 crawler registry metadata，未改 crawler handler、seed enumeration payload、download/import、credential、Tk/Web 操作或 user guide。

## 2026-05-30 07:46 Metadata HTTP error excerpt budget
- 本輪是 bounded consolidation slice：新增 `DEFAULT_HTTP_ERROR_EXCERPT_MAX_BYTES=8192`，讓 `core.safe_fetch_metadata()` 處理 HTTPError 時讀取的 error body excerpt budget 不再藏成裸值；metadata probe 正常 response 的 bounded excerpt 行為不變。
- 已提交實作：`3e690f6 Name metadata error excerpt budget`。
- 已驗證：in-memory compile `api_launcher\core.py` / `tests\test_metadata_probe.py` OK；`py -3 -B -m unittest tests.test_metadata_probe -v` 通過，2 tests OK；`api_launcher` / tests mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_074401.log` 通過，952 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26668021259` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只命名 metadata probe HTTP error excerpt budget，不改 metadata CLI output shape、crawler、download/import、credential、Tk/Web 操作或 user guide。

## 2026-05-30 07:36 Event log tail block budget
- 本輪是 bounded consolidation slice：新增 `DEFAULT_EVENT_LOG_TAIL_BLOCK_BYTES=8192`，讓 `latest_events()` / `_tail_text_lines_seek()` 的 tail block size 不再藏成裸值；雲端碟 binary seek/read 失敗時 fallback 到 streaming tail 的行為不變。
- 已提交實作：`6dbd7ee Name event log tail block budget`。
- 已驗證：in-memory compile `api_launcher\event_log.py` / `tests\test_event_log.py` OK；`py -3 -B -m unittest tests.test_event_log -v` 通過，4 tests OK；`api_launcher` / tests mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_073441.log` 通過，950 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26667734258` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只命名 event log tail block budget，不改 event JSONL shape、handoff output、UI/CLI 操作、crawler、download/import、credential 或 user guide。

## 2026-05-30 07:29 Provider discovery fetch budget CLI
- 本輪延續上一個 provider discovery guard：CLI 新增 `--provider-discovery-max-bytes`，預設讀 `DEFAULT_PROVIDER_DISCOVERY_FETCH_MAX_BYTES=120_000`，並把該值傳給 `discover_provider_candidates()`；大型官方 docs/homepage 可由命令調高 budget，不需要改產品碼。
- 已提交實作：`299a870 Expose provider discovery fetch budget`。
- 已驗證：in-memory compile `api_launcher\cli_discovery.py` / `tests\test_discovery.py` OK；`py -3 -B -m unittest tests.test_discovery -v` 通過，10 tests OK；`api_launcher` / tests mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_072640.log` 通過，950 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26667473612` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只增加 provider discovery CLI budget 參數，不改 Tk/Web 操作、provider promotion、local discovery audit、crawler、download/import、credential 或 user guide。

## 2026-05-30 07:20 Provider discovery fetch size guard
- 本輪延續 provider discovery / network boundary hardening：新增 `DEFAULT_PROVIDER_DISCOVERY_FETCH_MAX_BYTES=120_000`，並讓 `discovery.fetch_text()` 對 homepage/docs response 讀 `max_bytes + 1`；若遠端頁面超過 budget，會 fail-fast 而不是靜默用截斷頁面推斷 metadata、API base 或 auth hints。
- 已提交實作：`7ee46e9 Bound provider discovery fetch size`。
- 已驗證：in-memory compile `api_launcher\discovery.py` / `tests\test_discovery.py` OK；`py -3 -B -m unittest tests.test_discovery -v` 通過，9 tests OK；`api_launcher` / tests mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_071727.log` 通過，949 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26667191598` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只增加 provider discovery metadata fetch size guard，不改 provider promotion、local discovery audit、crawler、download/import、credential 或 user guide。

## 2026-05-30 07:10 AI summary response size guard
- 本輪延續 credential/network boundary hardening：新增 `DEFAULT_AI_SUMMARY_RESPONSE_MAX_BYTES=2 * 1024 * 1024`，並讓 `integrations._post_json()` 接受可覆寫 `max_bytes`；AI summary 相關 OpenAI-compatible / Gemini / Ollama 類 JSON response 會讀 `max_bytes + 1` 並拒絕過大 payload，避免 summary 生成遇到異常 response 時無界讀取。
- 已提交實作：`7c594b4 Bound AI summary response size`。
- 已驗證：in-memory compile `api_launcher\integrations.py` / `tests\test_ai_summary_generation.py` OK；`py -3 -B -m unittest tests.test_ai_summary_generation -v` 通過，12 tests OK；`api_launcher` / tests mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_070812.log` 通過，947 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26666910109` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只增加 AI summary POST JSON response size guard，不改 AI profile selection、credential storage、credential UI、crawler、download/import 或 user guide。

## 2026-05-30 07:00 Google OAuth form response size guard
- 本輪延續 credential/network boundary hardening：新增 `DEFAULT_GOOGLE_OAUTH_FORM_MAX_BYTES=512 * 1024`，並讓 `google_auth._post_form()` 接受可覆寫 `max_bytes`；legacy Google device/token POST response 會讀 `max_bytes + 1` 並拒絕過大 payload，對齊 `oauth_device` 的 bounded guard。
- 已提交實作：`52bae62 Bound Google OAuth form response size`。
- 已驗證：in-memory compile `api_launcher\google_auth.py` / `tests\test_google_auth.py` OK；`py -3 -B -m unittest tests.test_google_auth -v` 通過，6 tests OK；`api_launcher` / tests mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_065755.log` 通過，945 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26666579322` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只增加 legacy Google OAuth POST form response size guard，不改 token storage、credential UI、crawler、download/import 或 user guide。

## 2026-05-30 06:51 OAuth form response size guard
- 本輪延續 credential/network boundary hardening：新增 `DEFAULT_OAUTH_FORM_MAX_BYTES=512 * 1024`，並讓 `oauth_device._post_form()` 接受可覆寫 `max_bytes`；device-code / browser-code token POST response 會讀 `max_bytes + 1` 並拒絕過大 payload。
- 已提交實作：`0eb72a5 Bound OAuth form response size`。
- 已驗證：in-memory compile `api_launcher\oauth_device.py` / `tests\test_oauth_device.py` OK；`py -3 -B -m unittest tests.test_oauth_device -v` 通過，12 tests OK；`api_launcher` / tests mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_064907.log` 通過，943 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26666292682` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只增加 OAuth POST form response size guard，不改 token storage、credential UI、crawler、download/import 或 user guide。

## 2026-05-30 06:42 Adapter metadata fetch size guard
- 本輪延續 adapter resolver bounded policy hardening：新增 `DEFAULT_ADAPTER_JSON_MAX_BYTES=8 * 1024 * 1024`，並讓 `fetch_json()` 接受可覆寫 `max_bytes`；外部 metadata lookup 會讀 `max_bytes + 1` 並拒絕過大 payload，避免 adapter review resolver 無界讀取 CKAN / CMR / DataCite / Dataverse 等 JSON。
- 已提交實作：`66cfa31 Bound adapter metadata fetch size`。
- 已驗證：in-memory compile `api_launcher\adapter_plan_resolver.py` / `tests\test_adapter_plan_resolver.py` OK；`py -3 -B -m unittest tests.test_adapter_plan_resolver -v` 通過，57 tests OK；`api_launcher` / tests mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_063947.log` 通過，941 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26665963070` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只增加 adapter metadata fetch size guard，不改 resolver output shape、download/import、Web/Tk 操作、credential 或 user guide。

## 2026-05-30 06:32 Favicon fetch byte budget contract
- 本輪延續 bounded policy hardening：新增 `DEFAULT_FAVICON_MAX_BYTES=128 * 1024`，並讓 `download_favicon_png()` 接受可覆寫 `max_bytes`，保留 Tk favicon cache 128 KiB 預設讀取上限但不再把 byte budget 藏成裸值。
- 已提交實作：`b5e3e58 Name favicon fetch byte budget`。
- 已驗證：in-memory compile `api_launcher\favicons.py` / `tests\test_favicons.py` OK；`py -3 -B -m unittest tests.test_favicons -v` 通過，5 tests OK；`api_launcher` / tests mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_063016.log` 通過，939 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26665627697` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只命名並外顯 favicon fetch byte budget，不改 favicon URL 正規化、cache path、Tk/Web 操作、crawler、download/import、credential 或 user guide。

## 2026-05-30 06:23 Source pattern probe byte budget contract
- 本輪延續 bounded policy hardening：新增 `DEFAULT_PATTERN_PROBE_MAX_BYTES=128 * 1024`，並讓 `fetch_pattern_probe()` 接受可覆寫 `max_bytes`，保留既有 source pattern detector 128 KiB 預設讀取上限但不再把 byte budget 藏成裸值。
- 已提交實作：`8e0f123 Name source pattern probe byte budget`。
- 已驗證：in-memory compile `api_launcher\crawlers\source_patterns.py` / `tests\test_source_patterns.py` OK；`py -3 -B -m unittest tests.test_source_patterns -v` 通過，26 tests OK；`api_launcher` / tests mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_062054.log` 通過，938 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26665313476` 通過 Ubuntu、Windows 與 real DB smoke。`py_compile` 曾被 L 槽雲端 `__pycache__` replace lock 擋住，已用不寫 pyc 的 compile 驗證語法。
- Docs drift check：已同步 GTD / handoff / development log；本輪只命名並外顯 source pattern detector probe byte budget，不改 detector scoring、crawler dispatch、Web/Tk 操作、download/import、credential 或 user guide。

## 2026-05-30 06:12 Schema probe byte budget contract
- 本輪延續 bounded policy hardening：新增 `DEFAULT_SCHEMA_PROBE_MAX_BYTES=128 * 1024`，並讓 `fetch_probe_bytes()` 接受可覆寫 `max_bytes`，保留既有 128 KiB 預設讀取上限但不再把 byte budget 藏成裸值。
- 已提交實作：`241a3c7 Name schema probe byte budget`。
- 已驗證：`py -3 -B -m py_compile api_launcher\schema_probe.py tests\test_source_download.py` OK；`py -3 -B -m unittest tests.test_source_download -v` 通過，10 tests OK；`api_launcher` / tests mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_060957.log` 通過，937 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26664906622` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只命名並外顯 schema/head probe byte budget，不改 Web/Tk 欄位探測操作、crawler、download/import、credential 或 user guide。

## 2026-05-30 06:02 Adapter resource traversal depth guard
- 本輪依照 bounded recursion guardrail 做後端小型 hardening：`resource_mappings_from_candidate()` 新增 `MAX_RESOURCE_MAPPING_DEPTH=12` 與可覆寫 `max_depth` 參數，避免 JSON-LD/DCAT/Schema.org metadata 異常深巢狀時無限制遞迴；正常 resource 攤平行為與 resolver 輸出形狀不變。
- 已提交實作：`ff56909 Bound resource metadata traversal depth`。
- 已驗證：`py -3 -B -m py_compile api_launcher\adapter_plan_resolver.py tests\test_adapter_plan_resolver.py` OK；`py -3 -B -m unittest tests.test_adapter_plan_resolver -v` 通過，55 tests OK；`api_launcher` / tests mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_055953.log` 通過，936 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26664558279` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只新增 adapter resolver metadata traversal 防護，不改 crawler、download/import service、CLI/Tk/Web 操作或 user guide。

## 2026-05-30 05:50 Adapter direct-resource resolver lane helper
- 本輪轉到後端 bounded consolidation：新增 `direct_resource_entry_from_resource()`，把 `api_launcher/adapter_plan_resolver.py` 中單一 resource summary 是否能 promotion 成 bounded direct file 的判斷抽成獨立 resolver lane helper。
- `direct_resource_entries_for_plan_entry()` 保留原 pipeline 順序：bounded API resolver -> resource summaries -> Socrata/NCEI fallback -> metadata lookup -> ERDDAP sample；本輪只移動 direct-resource lane，不改 resolver policy、大小上限、metadata/API link guard 或輸出形狀。
- 已提交實作：`6460eaa Extract direct resource resolver lane`。
- 已驗證：in-memory compile `api_launcher\adapter_plan_resolver.py` / `tests\test_adapter_plan_resolver.py` OK；`py -3 -B -m unittest tests.test_adapter_plan_resolver -v` 通過，54 tests OK；`api_launcher` mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_054828.log` 通過，935 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26664108955` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只移動 adapter resolver 內部 helper 邊界，不改 crawler、download/import service、CLI/Tk/Web 操作或 user guide。

## 2026-05-30 05:40 Web plan-preview result typed bundle
- 本輪延續 Web Preview consolidation slice：新增 `WebPlanPreviewResultResponse` 與 `web_plan_preview_result_payload()`，讓 plan preview route 取得 response fragment 時，同時取得後續 persist / event log 需要的 compact `plan_outcome` / `plan_passport`。
- `web_plan_preview_result_response()` 保留既有 dict response 相容入口；`frontends/web/preview_api.py` 改用 typed bundle，不再從 generic response dict 反拆 outcome/passport。
- 已提交實作：`7628c7d Bundle Web plan preview result payload`。
- 已驗證：in-memory compile `frontends\web\preview_api.py` / `frontends\web\preview_payloads.py` / `tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 通過，59 tests OK；`frontends\web` / tests mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_053838.log` 通過，935 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26663712241` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只移動 Web plan-preview route 內部 payload handoff，不改 Web 操作流程、crawler、download/import、credential、storage policy 或 user guide。

## 2026-05-30 05:28 Web download/import result response helper
- 本輪延續 Web Preview consolidation slice：新增 `WebDownloadImportResultResponse` 與 `web_download_import_result_response()`，由 `frontends/web/preview_payloads.py` 集中建立 download/import completion response fragment，並一次回傳 route 後續要用的 compact `plan_outcome` / `plan_passport`。
- `frontends/web/preview_api.py` 的 asset-level 與 seed-level download/import route 不再各自呼叫 `crawler_asset_download_import_display_payload()` 後重複拆 `plan_outcome` / `plan_passport`；route 仍保留正式 service call、profile passport persist 與 event logging ownership。
- 已提交實作：`ec6e995 Move Web download import result payload`。
- 已驗證：in-memory compile `frontends\web\preview_api.py` / `frontends\web\preview_payloads.py` / `tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 通過，59 tests OK；`frontends\web` / tests mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_052640.log` 通過，935 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26663264563` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只移動 Web download/import 成功 response fragment 與 route 內部解包邊界，不改 Web 操作流程、crawler、download/import service、credential、storage policy 或 user guide。

## 2026-05-30 05:11 Web plan-preview result response helper
- 本輪延續 Web Preview consolidation slice：新增 `web_plan_preview_result_response()`，由 `frontends/web/preview_payloads.py` 集中建立已執行 plan preview 的 response fragment。
- `frontends/web/preview_api.py` 的 `crawler_asset_plan_preview()` 不再自行組 `plan_result`、`plan_outcome`、`plan_passport`、`adapter_review` 或 plan next-action；route 仍保留 repository session、plan builder call、profile passport persist 與 event logging。
- 已提交實作：`dffb31b Move Web plan preview result response payload`。
- 已驗證：in-memory compile `frontends\web\preview_api.py` / `frontends\web\preview_payloads.py` / `tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 通過，58 tests OK；`frontends\web` / tests / docs mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_051449.log` 通過，934 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26662713557` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只移動 Web plan-preview 成功 response fragment，不改 Web 操作流程、crawler、download/import、credential 或 user guide。

## 2026-05-30 04:58 Web listing result response helper
- 本輪延續 Web Preview consolidation slice：新增 `web_crawler_asset_listing_result_response()`，由 `frontends/web/preview_payloads.py` 集中建立 crawler listing 成功 response fragment。
- `frontends/web/preview_api.py` 的 `crawler_asset_listing()` 不再自行拆 `listing_result`、`audit_summary` 或 listing `next_action`；route 仍保留 repository session、crawler service call、commit 與 event logging。
- 已提交實作：`c0024af Move Web listing result response payload`。
- 已驗證：in-memory compile `frontends\web\preview_api.py` / `frontends\web\preview_payloads.py` / `tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 通過，57 tests OK；`frontends\web` / tests / docs mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_050046.log` 通過，933 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26662122047` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只移動 Web listing 成功 response fragment，不改 Web 操作流程、crawler、download/import、credential 或 user guide。

## 2026-05-30 04:48 Web listing credential block helper
- 本輪延續 Web Preview consolidation slice：新增 `web_crawler_asset_listing_credential_blocked_response()`，由 `frontends/web/preview_payloads.py` 集中建立 crawler listing 缺憑證 blocked response。
- `frontends/web/preview_api.py` 的 `crawler_asset_listing()` 不再直接建立 `CrawlerAssetListingResult` 或自行套 credential next-action；route 只負責 asset/context、credential guard、crawler service call 與 event。
- 已提交實作：`2518c4c Move Web listing credential block payload`。
- 已驗證：in-memory compile `frontends\web\preview_api.py` / `frontends\web\preview_payloads.py` / `tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 通過，56 tests OK；`frontends\web` / tests / docs mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_045032.log` 通過，932 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26661656999` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只移動 Web listing 缺憑證 payload 組裝邊界，不改 credential storage policy、Web 操作流程、crawler、download/import 或 user guide。

## 2026-05-30 04:37 Web plan-preview credential block helper
- 本輪延續 Web Preview consolidation slice：新增 `web_plan_preview_credential_blocked_response()`，由 `frontends/web/preview_payloads.py` 集中建立 Web plan preview 缺憑證 blocked response。
- `frontends/web/preview_api.py` 的 `crawler_asset_plan_preview()` 不再自行組 `plan_outcome` / `plan_passport` / credential next-action；route 只負責 action context、credential guard、service call 與 event。
- 已提交實作：`ef84f38 Move Web plan preview credential block payload`。
- 已驗證：in-memory compile `frontends\web\preview_api.py` / `frontends\web\preview_payloads.py` / `tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 通過，55 tests OK；`frontends\web` / tests / docs mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_044005.log` 通過，931 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26661212407` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只移動 Web plan-preview 缺憑證 payload 組裝邊界，不改 credential storage policy、Web 操作流程、crawler、download/import 或 user guide。

## 2026-05-30 04:25 Web credential event helper
- 本輪轉到 Web Preview consolidation slice：新增 `web_crawler_asset_credentials_event_context()`，由 `frontends/web/preview_payloads.py` 集中建立 Web credential update 的 safe event context。
- `frontends/web/preview_api.py` 的 `save_crawler_asset_credentials()` 不再自行組 event context；event 只記錄 asset/provider、status、configured/field counts、env var 名稱與 next_action，不寫入 token/password 或 value preview。
- 已提交實作：`9660752 Move Web credential event payload`。
- 已驗證：in-memory compile `frontends\web\preview_api.py` / `frontends\web\preview_payloads.py` / `tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 通過，54 tests OK；`frontends\web` / docs mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_042738.log` 通過，930 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26660663183` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只移動 Web credential event payload 組裝邊界，不改 credential storage policy、Web 操作流程、crawler、download/import 或 user guide。

## 2026-05-30 04:14 Crawler plan built event helper
- 本輪延續 Tk consolidation slice：新增 `crawler_asset_download_plan_built_event_context()`，由 `frontends/tk/crawler_asset_ui_helpers.py` 集中建立 `crawler_asset_download_plan_built` compact event context。
- `frontends/tk/crawler_asset_workflows.py` 的 `_crawler_asset_download_plan_worker()` 不再自行組 `asset_id`、direct/review counts 與 resolved plan path；worker 只負責呼叫 backend plan builder、寫 plan artifacts、記錄 event。
- 已提交實作：`0ce2825 Move crawler plan built event payload`。
- 已驗證：in-memory compile `frontends\tk\crawler_asset_workflows.py` / `frontends\tk\crawler_asset_ui_helpers.py` / `tests\test_tk_ui_helpers.py` OK；`py -3 -B -m unittest tests.test_tk_ui_helpers tests.test_tk_dialogs -v` 通過，131 tests OK；`frontends\tk` / docs mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_041635.log` 通過，929 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26660167246` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD / handoff / development log；本輪只移動 Tk crawler plan built event payload 組裝邊界，不改 UI 操作、crawler、download-plan builder、download/import、credential 或 user guide。

## 2026-05-30 04:01 Source pattern draft event helper
- 本輪延續 Tk consolidation slice：新增 `source_pattern_draft_written_event_context()` 與 `source_pattern_draft_blocked_event_context()`，由 `frontends/tk/source_pattern_draft_ui_helpers.py` 集中建立 source URL detector / local source draft 的 compact event context。
- `frontends/tk/crawler_asset_workflows.py` 的 `_source_pattern_draft_worker()` 不再自行組 `source_pattern_source_draft_written` / `source_pattern_source_draft_blocked` event payload；worker 只負責呼叫後端 detector/draft service、寫 event、顯示 review / success 訊息。
- 已提交實作：`ea20633 Move source pattern draft event payload`。
- 已驗證：in-memory compile `frontends\tk\crawler_asset_workflows.py` / `frontends\tk\source_pattern_draft_ui_helpers.py` / `tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 通過，108 tests OK；`frontends\tk` / docs mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_040505.log` 通過，928 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`；GitHub Actions manual run `26659664434` 通過 Ubuntu、Windows 與 real DB smoke。`py_compile` 曾被 L 槽雲端 `__pycache__` replace lock 擋住，已用不寫 pyc 的 compile 驗證語法。
- Docs drift check：已同步 GTD / handoff / development log；本輪只移動 Tk source pattern draft event payload 組裝邊界，不改 source pattern detector、local source draft 行為、UI 操作、crawler、download/import、credential 或 user guide。

## 2026-05-30 03:51 Crawler seed download/import event helper
- 本輪延續 Tk consolidation slice：新增 `crawler_seed_download_import_event_context()`，由 `frontends/tk/crawler_asset_ui_helpers.py` 集中建立 seed download/import 的 compact event context。
- `frontends/tk/crawler_asset_workflows.py` 的 `_crawler_asset_seed_download_import_worker()` 不再自行拆 `result.pipeline.stage`、`result.succeeded`、`pipeline.to_dict()` 與 artifacts；worker 只負責呼叫正式 seed download/import service、寫 event、handoff 到 Tk completion message。
- 已提交實作：`5d7295f Move crawler seed download event payload`。
- 已驗證：`py -3 -B -m py_compile frontends\tk\crawler_asset_workflows.py frontends\tk\crawler_asset_ui_helpers.py tests\test_tk_ui_helpers.py` OK；`py -3 -B -m unittest tests.test_tk_ui_helpers tests.test_tk_dialogs -v` 通過，128 tests OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_035311.log` 通過，926 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`。
- Docs drift check：已同步 GTD / handoff / development log；本輪只移動 Tk seed download/import event payload 組裝邊界，不改 UI 操作、crawler、download/import、credential 或 user guide。

## 2026-05-30 03:44 Crawler seed schema probe event helper
- 本輪延續 Tk consolidation slice：新增 `crawler_seed_schema_probe_event_context()`，由 `frontends/tk/crawler_asset_ui_helpers.py` 集中建立 seed schema probe 的 compact event context。
- `frontends/tk/crawler_asset_workflows.py` 的 `_crawler_asset_seed_schema_probe_worker()` 不再自行組 `probe.to_dict()` / `schema_probe_required_count` / `warning_codes` event payload；worker 只負責呼叫後端 probe service、寫 event、handoff 到 Tk dialog。
- 已提交實作：`97c8ac6 Move crawler seed schema probe event payload`。
- 已驗證：`py -3 -B -m py_compile frontends\tk\crawler_asset_workflows.py frontends\tk\crawler_asset_ui_helpers.py tests\test_tk_ui_helpers.py` OK；`py -3 -B -m unittest tests.test_tk_ui_helpers tests.test_tk_dialogs -v` 通過，127 tests OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_034629.log` 通過，925 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`。
- Docs drift check：已同步 GTD / handoff / development log；本輪只移動 Tk schema probe event payload 組裝邊界，不改 UI 操作、crawler、download/import、credential 或 user guide。

## 2026-05-30 03:37 Crawler asset listing outcome event helper
- 本輪延續 Tk consolidation slice：新增 `crawler_asset_listing_outcome_event_payload()`，由 `frontends/tk/crawler_asset_ui_helpers.py` 集中建立 listing outcome 的 compact event context 與 sidebar preview payload。
- `frontends/tk/crawler_asset_workflows.py` 的 `record_crawler_asset_listing_outcome()` 不再直接呼叫 backend listing event helper 或自行組 preview payload；workflow 只負責寫 event log 與更新 UI cache。
- 已提交實作：`d2aa1b3 Move crawler listing outcome event payload`。
- 已驗證：`py -3 -B -m py_compile frontends\tk\crawler_asset_workflows.py frontends\tk\crawler_asset_ui_helpers.py tests\test_tk_ui_helpers.py` OK；`py -3 -B -m unittest tests.test_tk_ui_helpers tests.test_tk_dialogs -v` 通過，126 tests OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_033933.log` 通過，924 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`。
- Docs drift check：已同步 GTD / handoff / development log；本輪只移動 Tk listing event/preview payload 組裝邊界，不改 UI 操作、crawler、download/import、credential 或 user guide。

## 2026-05-30 03:30 Crawler asset plan outcome event helper
- 本輪延續 Tk consolidation slice：新增 `crawler_asset_plan_outcome_event_payload()`，由 `frontends/tk/crawler_asset_ui_helpers.py` 集中建立 crawler asset plan outcome 的 event context 與 plan passport payload。
- `frontends/tk/crawler_asset_workflows.py` 的 `record_crawler_asset_plan_outcome()` 不再直接呼叫 backend display helpers 組 event context，也不再自行計算 review queue count；workflow 只負責 persist passport 與寫 event log。
- 已提交實作：`39bd423 Move crawler plan outcome event payload`。
- 已驗證：`py -3 -B -m py_compile frontends\tk\crawler_asset_workflows.py frontends\tk\crawler_asset_ui_helpers.py tests\test_tk_ui_helpers.py` OK；`py -3 -B -m unittest tests.test_tk_ui_helpers tests.test_tk_dialogs -v` 通過，125 tests OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_033209.log` 通過，923 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`。
- Docs drift check：已同步 GTD / handoff / development log；本輪只移動 Tk event payload 組裝邊界，不改 UI 操作、crawler、download/import、credential 或 user guide。

## 2026-05-30 02:33 Post-restart smoke checkpoint
- 使用者回報 app 閃退並重啟後，本輪未再開新功能切片，先補跑完整 pre-push smoke。
- 目前 HEAD：`e118bf4 Record crawler plan artifact helper CI pass`，branch `rrkal-32e215c-recovery` 相對 `origin/rrkal-32e215c-recovery` ahead 1。
- 已驗證：`.\scripts\pre_push_smoke_brief.cmd` 通過，完整 log `state\logs\pre_push_smoke_20260530_023314.log`；922 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`。
- Docs drift check：這是重啟後驗證 checkpoint，不改產品行為、UI/CLI 操作、crawler、download/import、credential 或 user guide；GTD 不需更新。

## 2026-05-30 02:20 Crawler asset plan artifact writer helper
- 本輪延續 Tk consolidation slice：新增 `write_crawler_asset_download_plan_artifacts()`，由 `frontends/tk/crawler_asset_ui_helpers.py` 集中寫出 crawler asset original/resolved plan JSON。
- `frontends/tk/crawler_asset_workflows.py` 不再直接 import `json`、`safe_path_part` 或 `state_file`，也不再在 worker 內拼 `state/crawler_asset_plans/{asset}.original/resolved.json`；worker 只呼叫 helper，再寫 event 與完成 UI handoff。
- 已提交實作：`b880bfa Move crawler plan artifact writing`，並已推送到 `origin/rrkal-32e215c-recovery`。
- GitHub Actions manual run `26654793363` 通過 Ubuntu、Windows 與 real DB smoke。
- 已驗證：`py -3 -B -m py_compile frontends\tk\crawler_asset_workflows.py frontends\tk\crawler_asset_ui_helpers.py tests\test_tk_ui_helpers.py` OK；`py -3 -B -m unittest tests.test_tk_ui_helpers tests.test_tk_dialogs -v` 通過，124 tests OK；`frontends\tk` / tests mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_022203.log` 通過，922 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`。
- Docs drift check：已同步 GTD / handoff / development log；本輪只移動 Tk plan artifact path/write ownership，不改 UI 操作、crawler、download/import、credential 或 user guide。

## 2026-05-30 02:08 Crawler asset plan cache helper
- 本輪延續 Tk consolidation slice：新增 `cache_crawler_asset_plan_state()`，由 `frontends/tk/crawler_asset_ui_helpers.py` 集中更新 plan outcome、resolved plan、content review 與 plan passport 的 Tk lookup cache。
- `frontends/tk/crawler_asset_workflows.py` 的 `_finish_crawler_asset_download_plan()` 不再手動初始化 / 更新四組 cache；blocked 與 success 路徑都只委派 helper，再繼續做 record event、refresh row、status/messagebox。
- 已提交實作：`9eac107 Move crawler plan cache updates`，並已推送到 `origin/rrkal-32e215c-recovery`。
- GitHub Actions manual run `26654234638` 通過 Ubuntu、Windows 與 real DB smoke。
- 已驗證：`py -3 -B -m py_compile frontends\tk\crawler_asset_workflows.py frontends\tk\crawler_asset_ui_helpers.py tests\test_tk_ui_helpers.py` OK；`py -3 -B -m unittest tests.test_tk_ui_helpers tests.test_tk_dialogs -v` 通過，122 tests OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_021026.log` 通過，920 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`。
- Docs drift check：已同步 GTD / handoff / development log；本輪只移動 Tk display cache 更新邊界，不改 UI 操作、crawler、download/import、credential 或 user guide。

## 2026-05-30 02:05 Crawler asset bounds payload cache helper
- 本輪延續 Tk consolidation slice：新增 `crawler_asset_bound_payload_from_cache()`，由 `frontends/tk/crawler_asset_ui_helpers.py` 集中把 bounds dialog cache 內的 dict 還原成 `CrawlerAssetBoundPayload`。
- `frontends/tk/crawler_asset_workflows.py` 的 `crawler_asset_bound_payload_for_asset()` 現在只委派 helper，不再在 workflow event handler 內重複解析 `facet_values` / `field_values` / `maps_to_values` / `warning_codes`。
- 已提交實作：`251682c Move crawler bounds payload cache parsing`，並已推送到 `origin/rrkal-32e215c-recovery`。
- GitHub Actions manual run `26653677336` 通過 Ubuntu、Windows 與 real DB smoke。
- 已驗證：`py -3 -B -m py_compile frontends\tk\crawler_asset_workflows.py frontends\tk\crawler_asset_ui_helpers.py tests\test_tk_ui_helpers.py` OK；`py -3 -B -m unittest tests.test_tk_ui_helpers tests.test_tk_dialogs -v` 通過，120 tests OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_015821.log` 通過，918 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`。
- Docs drift check：已同步 GTD / handoff / development log；本輪只移動 Tk cache parsing 邊界，不改 UI 操作、crawler、download/import、credential 或 user guide。

## 2026-05-30 01:51 Recovery branch upstream tracking repaired
- 本輪修正 L 槽 clone 的本機 Git fetchspec：`remote.origin.fetch` 原本只包含 `main`，導致 recovery branch 雖已 `push -u`，但 `@{u}` 仍報 `upstream branch ... not stored as a remote-tracking branch`，pre-push smoke 因而顯示 `no upstream branch found`。
- 已在本機 `.git/config` 加入 `+refs/heads/rrkal-32e215c-recovery:refs/remotes/origin/rrkal-32e215c-recovery`，並重新 fetch；現在 `git rev-parse --abbrev-ref --symbolic-full-name '@{u}'` 回傳 `origin/rrkal-32e215c-recovery`，`git status -sb --ahead-behind` 會顯示 `rrkal-32e215c-recovery...origin/rrkal-32e215c-recovery`。
- 這是 L 槽工作區 Git metadata 修復，不改產品程式、不改 tracked file 行為、不影響 GitHub remote。
- Docs drift check：本輪只補工作區治理紀錄；不改 UI/CLI 操作、crawler、download/import、credential 或 user guide。

## 2026-05-30 01:48 Crawler asset bounds schema helper CI pass
- `d3c1d8c Move crawler bounds schema lookup` / `d653ccb Record bounds schema helper smoke` 已推送到 `origin/rrkal-32e215c-recovery`。
- GitHub Actions manual run `26652940368` 通過 Ubuntu、Windows 與 real DB smoke。
- 本輪 verified behavior：`crawler_asset_download_plan_bounds_schema()` 集中 Tk crawler asset build-download-plan bounds schema lookup；workflow 仍只負責 UI orchestration，不接管 backend bounds、download plan 或 import 規則。
- Docs drift check：本輪只補遠端 CI 證據，不改使用者操作流程、crawler、download/import、credential 或 user guide；user guide 不需更新。

## 2026-05-30 01:45 Crawler asset bounds schema helper smoke pass
- `d3c1d8c Move crawler bounds schema lookup` / `d2f645e Record bounds schema helper checkpoint` 已補完整 smoke。
- 已驗證：`.\scripts\pre_push_smoke_brief.cmd` 通過，完整 log `state\logs\pre_push_smoke_20260530_014250.log`；916 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`。
- 注意：pre-push smoke 腳本仍顯示 `no upstream branch found; skipped pending-push diff check`，但 branch 可用 `git push -u origin rrkal-32e215c-recovery` 明確重設 upstream 後再推。這是 Git/workflow 狀態觀察，不改產品行為。
- Docs drift check：本輪只補 smoke 證據，不改 UI/CLI 操作、crawler、download/import、credential 或 user guide；user guide 不需更新。

## 2026-05-30 01:39 Crawler asset bounds schema lookup helper
- 本輪做一個小型 Tk consolidation slice：新增 `crawler_asset_download_plan_bounds_schema()`，由 `frontends/tk/crawler_asset_ui_helpers.py` 集中讀取 crawler asset 的 `BUILD_DOWNLOAD_PLAN.bounds_schema`。
- `frontends/tk/crawler_asset_workflows.py` 不再重複掃 `asset.capabilities` 找 plan capability；seed schema probe 與 crawler asset 送進下載器前的 bounds dialog 都改為消費同一個 helper。這不改 bounds schema、本機 payload、download plan、seed probe、crawler、download/import 或使用者操作流程。
- 已提交實作：`d3c1d8c Move crawler bounds schema lookup`。
- 已驗證：`py -3 -B -m py_compile frontends\tk\crawler_asset_workflows.py frontends\tk\crawler_asset_ui_helpers.py tests\test_tk_ui_helpers.py` OK；`py -3 -B -m unittest tests.test_tk_ui_helpers tests.test_tk_dialogs -v` 通過，118 tests OK；`frontends\tk` / docs mojibake scan OK；`git diff --check` OK。
- Docs drift check：已同步 GTD；本輪未改使用者可見流程或 user guide，user guide 不需更新。

## 2026-05-30 01:36 Crawler registry focused verification
- 本輪未改產品程式，針對既有 crawler declarative registry 做 focused verification，確認它已落地到 dispatch / diagnostics / handoff surfaces。
- Verified behavior source：`api_launcher/crawlers/registry.py` 有 `CrawlerSpec`、四維 matrix、capability code/mask、duplicate guard 與 handler signature guard；`api_launcher/crawlers/dataset_sources.py` 透過 `crawler_handler()` 正式分派，`SOURCE_CRAWLER_HANDLERS` 僅保留相容 / 診斷用途。
- 已驗證：`py -3 -B -m unittest tests.test_dataset_discovery tests.test_developer_diagnostics tests.test_handoff tests.test_heartbeat -v` 通過，92 tests OK。
- Docs drift check：本輪只補驗證紀錄，不改行為、UI/CLI 操作、crawler handler、download/import 或 user guide；GTD/relationship/workspace docs 已在上一個 docs drift checkpoint 對齊。

## 2026-05-30 01:32 Docs drift correction for dialog and crawler registry ownership
- 本輪只做文檔漂移修補，未改產品程式：`docs/CODE_RELATIONSHIP_MAP.zh-TW.md`、`docs/WORKSPACE_LAYOUT.zh-TW.md`、`docs/PROJECT_GTD.md` 已對齊 verified behavior。
- Verified behavior source：`frontends/tk/dialogs.py` 已是 33 行相容 re-export facade；dialog implementations 已移到 focused owner modules。`api_launcher/crawlers/registry.py` 已提供 `CrawlerSpec`、四維 matrix、capability code/mask 與 `crawler_handler()`，`dataset_sources.py` 只保留相容/診斷 surface。
- 已提交實際文檔修補：`39bf8bb Update docs drift records`。
- 已驗證：docs mojibake scan OK；`git diff --check` OK。本切片未改程式碼，不需跑 RRKAL 單元測試或 full smoke。
- Docs drift check：已修正 `dialogs.py` 與 crawler source registry 相關漂移；未發現需同步 user guide 的使用者操作流程變更。

## 2026-05-30 01:26 Provider candidate review dialog ownership CI pass
- 本輪從 `frontends/tk/dialogs.py` 移出 `ProviderCandidateReviewDialog`，新增 `frontends/tk/provider_candidate_review_dialog.py` 作為 provider/source 候選審核 dialog owner。
- `dialogs.py` 現在降成 33 行相容 re-export facade，只保留各 dialog class 的穩定匯入面；後續不要再把新 dialog 實作塞回 `dialogs.py`。
- 新 owner 仍只負責 review-only 表格、detail pane、開 URL、寫入 ignored local provider seed / dataset source draft 與 event log；正式 catalog promotion 仍必須走 local discovery draft audit / crawler audit，不在 dialog 內直接納管 provider/source。
- 已驗證：in-memory compile `frontends\tk\dialogs.py` / `frontends\tk\provider_candidate_review_dialog.py` / `tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 106 tests OK；`frontends\tk` / docs mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_012128.log` 通過，914 tests / 4 skipped，MVP `download_import_completed` / `row_count=3`。
- 已推送到 `origin/rrkal-32e215c-recovery`；GitHub Actions manual run `26651915573` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 Provider candidate review dialog ownership 與 `dialogs.py` facade，不改使用者操作流程、local draft audit、crawler、download/import、credential、event schema 或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-30 01:15 Dataset candidate review dialog ownership CI pass
- 本輪從 `frontends/tk/dialogs.py` 移出 `DatasetCandidateReviewDialog`，新增 `frontends/tk/dataset_candidate_review_dialog.py` 作為資料集候選審核 dialog owner。
- `dialogs.py` 仍 re-export `DatasetCandidateReviewDialog`，所以 `frontends.tk.dialogs` 舊匯入點與 tests 不需改；新 owner 只負責候選 table、detail pane、source URL 開啟、candidate status 更新與「加入下載計畫」的既有 UI 委派，實際 repository status update 與 plan mutation 仍走既有 backend / 主 UI helpers。
- `dialogs.py` 從約 467 行降到 254 行；這是小型 dataset-candidate review dialog ownership cleanup，不改 crawler audit、candidate schema、download/import、credential、provider catalog 或 UI 操作流程。
- 已驗證：in-memory compile `frontends\tk\dialogs.py` / `frontends\tk\dataset_candidate_review_dialog.py` / `tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 106 tests OK；`frontends\tk` / docs mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_011008.log` 通過，914 tests / 4 skipped，MVP `download_import_completed` / `row_count=3`。`py_compile` 曾被雲端碟 `__pycache__` replace lock 擋住，已用不寫 pyc 的 compile 驗證語法，完整 smoke 也已通過 py_compile core entrypoints。
- 已推送到 `origin/rrkal-32e215c-recovery`；GitHub Actions manual run `26651385342` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 Dataset candidate review dialog ownership，不改使用者操作流程、crawler、download/import、credential、event schema 或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-30 01:02 Adapter review dialog ownership CI pass
- 本輪從 `frontends/tk/dialogs.py` 移出 `AdapterReviewDialog`，新增 `frontends/tk/adapter_review_dialog.py` 作為 Adapter 待辦視窗 owner。
- `dialogs.py` 仍 re-export `AdapterReviewDialog`，所以 `frontends.tk.dialogs` 舊匯入點、crawler asset adapter review 入口與 tests 不需改；新 owner 只負責 review-only 表格、detail pane、開啟 source / landing URL 與委派主 UI 既有 resolver 入口，真正 adapter plan resolution、download/import、content parser review 仍留在後端與既有 workflow。
- `dialogs.py` 從約 589 行降到 467 行；這是小型 adapter-review dialog ownership cleanup，不改 adapter review item shape、resolved plan、download/import、crawler、credential 或 UI 操作流程。
- 已驗證：`py -3 -B -m py_compile frontends\tk\dialogs.py frontends\tk\adapter_review_dialog.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 106 tests OK；`frontends\tk` / docs mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_005628.log` 通過，914 tests / 4 skipped，MVP `download_import_completed` / `row_count=3`。
- 已推送到 `origin/rrkal-32e215c-recovery`；GitHub Actions manual run `26650752400` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 Adapter review dialog ownership，不改使用者操作流程、crawler、download/import、credential、event schema 或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-30 00:47 Data-store connection dialog ownership CI pass
- 本輪從 `frontends/tk/dialogs.py` 移出 `DataStoreConnectionSettingsDialog`，新增 `frontends/tk/data_store_connection_settings_dialog.py` 作為資料儲存連線設定 dialog owner。
- `dialogs.py` 仍 re-export `DataStoreConnectionSettingsDialog`，所以 `frontends.tk.dialogs` 舊匯入點、整合入口與 tests 不需改；新 owner 只負責 data-store profile 表格、測試按鈕、env template 按鈕與 active profile 按鈕的 UI 編排，實際連線測試、env template 產生、active profile 寫入與 event log 仍走既有 backend helpers。
- `dialogs.py` 從約 739 行降到 589 行；這是小型 data-store settings dialog ownership cleanup，不改 profile schema、credential/env storage、資料庫連線測試、active profile 或 UI 操作流程。
- 已驗證：`py -3 -B -m py_compile frontends\tk\dialogs.py frontends\tk\data_store_connection_settings_dialog.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 106 tests OK；`frontends\tk` / docs mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_004216.log` 通過，914 tests / 4 skipped，MVP `download_import_completed` / `row_count=3`。
- 已推送到 `origin/rrkal-32e215c-recovery`；GitHub Actions manual run `26650062525` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 data-store settings dialog ownership，不改使用者操作流程、credential/env storage、crawler、download/import、event schema 或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-30 00:33 AI/Gemini settings dialog ownership CI pass
- 本輪從 `frontends/tk/dialogs.py` 移出 `AiModelSettingsDialog` 與 `GoogleGeminiSettingsDialog`，新增 `frontends/tk/ai_settings_dialogs.py` 作為 AI profile / Google-Gemini connection dialogs 的 owner。
- `dialogs.py` 仍 re-export 兩個 class，所以 `frontends.tk.dialogs` 舊匯入點、整合選單與 tests 不需改；新 owner 只負責 AI/Gemini 設定視窗、說明文案、表格 row projection 與按鈕編排，credential 寫入、OAuth browser/device-code flow、API key storage 與 AI summary generation 仍委派既有 UI/backend 服務。
- `dialogs.py` 從約 998 行降到 739 行；這是小型 AI settings dialog ownership cleanup，不改 AI profile selection、Gemini API key 保存、OAuth config、Google login readiness 或 UI 操作流程。
- 已驗證：`py -3 -B -m py_compile frontends\tk\dialogs.py frontends\tk\ai_settings_dialogs.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 106 tests OK；`frontends\tk` / docs mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_002856.log` 通過，914 tests / 4 skipped，MVP `download_import_completed` / `row_count=3`。
- 已推送到 `origin/rrkal-32e215c-recovery`；GitHub Actions manual run `26649428252` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 AI/Gemini settings dialog ownership，不改使用者操作流程、credential storage、OAuth/API key 行為、crawler、download/import、event schema 或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-30 00:20 Provider/database dialog ownership CI pass
- 本輪從 `frontends/tk/dialogs.py` 移出 `ProviderEditorDialog` 與 `DatabaseClientSettingsDialog`，新增 `frontends/tk/provider_editor_dialog.py` 與 `frontends/tk/database_client_settings_dialog.py` 作為各自 owner。
- `dialogs.py` 仍 re-export 兩個 class，所以 `frontends.tk.dialogs` 舊匯入點、provider 編輯 workflow、database client settings 入口與 tests 不需改；provider dialog 只建立 `core.Provider` result，真正寫入仍由主 UI/repository 決定；database client dialog 只改本機 integration config 與開啟本機 DB 工具，不改資料庫內容。
- `dialogs.py` 從約 1317 行降到 998 行；這是小型 provider/settings dialog ownership cleanup，不改 provider 欄位驗證、local integration config schema、database client profile 行為或 UI 操作流程。
- 已驗證：`py -3 -B -m py_compile frontends\tk\dialogs.py frontends\tk\provider_editor_dialog.py frontends\tk\database_client_settings_dialog.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 106 tests OK；`frontends\tk` / docs mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260530_001456.log` 通過，914 tests / 4 skipped，MVP `download_import_completed` / `row_count=3`。
- 已推送到 `origin/rrkal-32e215c-recovery`；GitHub Actions manual run `26648746037` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 provider/database client settings dialog ownership，不改使用者操作流程、crawler、download/import、credential、event schema 或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-30 00:04 Language/startup diagnostics dialog ownership CI pass
- 本輪從 `frontends/tk/dialogs.py` 移出 `UiLanguageSettingsDialog` 與 `StartupEnvironmentChecksDialog`，新增 `frontends/tk/language_settings_dialog.py` 與 `frontends/tk/startup_environment_checks_dialog.py` 作為各自 owner。
- `dialogs.py` 仍 re-export 兩個 class，所以 `frontends.tk.dialogs` 舊匯入點與 provider settings workflow 不需改；語言 dialog 只寫本機 integration config 並通知主 UI 重建 menu，啟動檢查 dialog 只讀 `core.run_startup_checks(DB_PATH)`。
- `dialogs.py` 從 1416 行降到 1317 行；這是小型 settings/diagnostics dialog ownership cleanup，不改語言設定值、startup check 內容、UI 操作流程或修復行為。
- 已驗證：`py -3 -B -m py_compile frontends\tk\dialogs.py frontends\tk\language_settings_dialog.py frontends\tk\startup_environment_checks_dialog.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 106 tests OK；`frontends\tk` / docs mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260529_235707.log` 通過，914 tests / 4 skipped，MVP `download_import_completed` / `row_count=3`。
- 已推送到 `origin/rrkal-32e215c-recovery`；GitHub Actions manual run `26647816256` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 settings/diagnostics dialog ownership，不改使用者操作流程、crawler、download/import、credential、event schema 或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 23:50 Import policy dialog ownership CI pass
- 本輪從 `frontends/tk/dialogs.py` 移出 `ImportExistingTablePolicyDialog`，新增 `frontends/tk/import_policy_dialog.py` 作為既有資料表處理策略 modal owner。
- `dialogs.py` 仍 re-export `ImportExistingTablePolicyDialog`，所以 `frontends.tk.dialogs` 舊匯入點與 import workflow 不需改；新 owner 只處理 `rename/skip/replace` 的使用者選擇與 replace 確認提示，真正 import/replace/skip guard 仍在 importer/pipeline 層。
- `dialogs.py` 從 1504 行降到 1416 行；這是小型 dialog ownership cleanup，不改匯入策略值、同名表處理行為或 UI 操作流程。
- 已驗證：`py -3 -B -m py_compile frontends\tk\dialogs.py frontends\tk\import_policy_dialog.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 106 tests OK；`frontends\tk` mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260529_234256.log` 通過，914 tests / 4 skipped，MVP `download_import_completed` / `row_count=3`。
- 已推送到 `origin/rrkal-32e215c-recovery`；GitHub Actions manual run `26647086608` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 Import Existing Table policy dialog ownership，不改使用者操作流程、import/replace 行為、crawler、download/import、credential、event schema 或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 23:37 Developer CLI dialog ownership CI pass
- 本輪從 `frontends/tk/dialogs.py` 移出 `DeveloperCliDialog`，新增 `frontends/tk/developer_cli_dialog.py` 作為開發者 CLI 視窗 owner。
- `dialogs.py` 仍 re-export `DeveloperCliDialog`，所以 `frontends.tk.dialogs` 舊匯入點與 `provider_settings_workflows.py` 不需改；新 owner 集中 subprocess、`shlex`、`PROJECT_ROOT` 與 single-flight job helper。
- `dialogs.py` 從 1625 行降到 1504 行；這是小型 dialog ownership cleanup，不改 CLI 命令解析、timeout、background job 或 UI 操作流程。
- 已驗證：`py -3 -B -m py_compile frontends\tk\dialogs.py frontends\tk\developer_cli_dialog.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 106 tests OK；`frontends\tk` mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260529_233050.log` 通過，914 tests / 4 skipped，MVP `download_import_completed` / `row_count=3`。
- 已推送到 `origin/rrkal-32e215c-recovery`；GitHub Actions manual run `26646483112` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 Developer CLI dialog ownership，不改使用者操作流程、crawler、download/import、credential、event schema 或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 23:21 Recent event log dialog ownership CI pass
- 本輪從 `frontends/tk/dialogs.py` 移出 `RecentEventLogsDialog`，新增 `frontends/tk/recent_event_logs_dialog.py` 作為事件紀錄視窗 owner。
- `dialogs.py` 仍 re-export `RecentEventLogsDialog`，所以既有 `frontends.tk.dialogs` import 與測試入口不斷；新 dialog 只讀 `latest_events()` / JSONL，不寫 event log、不改 crawler/download/import/state。
- `dialogs.py` 從 1715 行降到 1625 行；這是小型 dialog ownership cleanup，不是 Tk 對話框大搬家。
- 已驗證：`py -3 -B -m py_compile frontends\tk\dialogs.py frontends\tk\recent_event_logs_dialog.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 106 tests OK；相關 Tk/docs mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260529_231341.log` 通過，914 tests / 4 skipped，MVP `download_import_completed` / `row_count=3`。
- 已推送到 `origin/rrkal-32e215c-recovery`；GitHub Actions manual run `26645636629` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 Tk dialog ownership，不改使用者操作流程、事件 JSONL schema、crawler、download/import、credential 或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 23:02 Tk crawler asset event-state helper ownership CI pass
- 本輪延續 Tk consolidation：新增 `frontends/tk/crawler_asset_event_state.py`，把 crawler asset plan/listing structured event 的狀態恢復邏輯從 `frontends/tk/crawler_asset_workflows.py` 移出。
- `crawler_asset_workflows.py` 現在只呼叫 `crawler_asset_plan_state_from_events()` / `crawler_asset_listing_outcomes_from_events()`，再把回傳 dict 放回 UI cache；helper 不跑 crawler、不重建 plan、不寫 profile，只恢復重開 Tk 後的可視狀態。
- 新 helper 保留舊行為：plan outcome label、content review label、plan passport、resolved plan JSON 與 listing seed enumeration preview 仍從 structured event / saved resolved plan 取得；遺失或壞掉的 resolved plan 只會跳過，不阻斷 UI 啟動。
- 已驗證：`py -3 -B -m py_compile frontends\tk\crawler_asset_workflows.py frontends\tk\crawler_asset_event_state.py frontends\tk\crawler_asset_ui_helpers.py tests\test_tk_ui_helpers.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_ui_helpers tests.test_tk_dialogs -v` 116 tests OK；`frontends\tk` / `api_launcher` / `tests` / `docs` mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260529_225850.log` 通過，914 tests / 4 skipped，MVP `download_import_completed` / `row_count=3`。
- 已推送到 `origin/rrkal-32e215c-recovery`；Tk event-state checkpoint 已包含在 `b38700c Record Tk event state smoke`，GitHub Actions manual run `26644859793` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 Tk event-state helper ownership，不改使用者操作流程、按鈕、crawler、download/import、credential、event schema 或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 22:46 Adapter review fallback resolver pipeline CI pass
- 本輪在 `api_launcher/adapter_plan_resolver.py` 做小型準宣告式收斂：`direct_resource_entries_for_plan_entry()` 內的 bounded resolver、NCEI fallback resolver 與 metadata lookup resolver 改成顯式 resolver pipeline 迴圈。
- 行為順序維持不變：STAC/CMR bounded resolver 先跑，generic resources 之後，Socrata bounded sample、NCEI data-file lookup、NCEI bounded search/access-data fallback，再進 CMR granule asset / CKAN / DataCite / Dataverse metadata lookup，ERDDAP sample 仍可並存。
- 這不是全面拆 `adapter_plan_resolver.py`，只是先把可重複的 resolver 分流收斂成 table-like pipeline，降低後續新增 fallback resolver 時繼續堆 `if` 的風險。
- 已驗證：`py -3 -B -m py_compile api_launcher\adapter_plan_resolver.py tests\test_adapter_plan_resolver.py tests\test_dataset_download_plan.py` OK；`py -3 -B -m unittest tests.test_adapter_plan_resolver tests.test_dataset_download_plan -v` 72 tests OK；`api_launcher` mojibake scan OK；`git diff --check` OK；完整 smoke `state\logs\pre_push_smoke_20260529_224026.log` 通過，912 tests / 4 skipped，MVP `download_import_completed` / `row_count=3`。
- 已推送到 `origin/rrkal-32e215c-recovery`；resolver pipeline checkpoint 已包含在 `8db60fa Record resolver pipeline checkpoint`，GitHub Actions manual run `26643848797` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 resolver 內部分派寫法，不改 adapter review output shape、download/import 行為、UI/CLI 操作或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 22:31 Docs registry PoC
- 本輪收掉 GTD 上的中期文檔治理 PoC 第一版：新增 `docs/DOCS_REGISTRY.csv`，用 diff-friendly CSV 盤點文件路徑、角色、權威層級、last_verified、驗證證據與備註。
- `docs/DOCS_INDEX.zh-TW.md` 已把 `DOCS_REGISTRY.csv` 登記為輔助索引，明確說明它不取代 Markdown source of truth；handoff/GTD/log 仍是人類可讀協作主線。
- `docs/PROJECT_GTD.md` 已把「diff-friendly docs registry PoC」從待辦改成第一版完成；SQLite/DB 型文件治理仍保留為後續 report/cache 方向，不在本輪擴大。
- 已驗證：docs mojibake scan OK；`git diff --check` OK；未改產品程式，不需跑 RRKAL 單元測試。
- Docs drift check：本輪只新增文檔治理 registry 與索引，不改產品行為、UI/CLI 操作流程、crawler、download/import、credential 或 user guide。

## 2026-05-29 22:27 Recovery branch CI pass
- 已將 `96bfc7e` / `0c0f8c8` 推到 `origin/rrkal-32e215c-recovery`，遠端 head 為 `0c0f8c8 Record Tk row detail checkpoint`。
- 推送前本地完整 smoke 通過：912 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_222350.log`。
- 手動 workflow dispatch 已針對 recovery branch 跑完 GitHub Actions：run `26643001651` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本段只補遠端驗證與 branch 狀態，不改產品行為、UI/CLI 操作流程或 user guide。

## 2026-05-29 22:19 Tk crawler asset row/detail helper ownership cleanup
- 本輪延續 Tk consolidation：把 crawler asset table row tuple 與右側 passport detail text 的組裝移到 `frontends/tk/crawler_asset_ui_helpers.py`。
- `frontends/tk/crawler_asset_workflows.py` 從約 1303 行降到約 1246 行；workflow class 仍保留 `crawler_asset_row_values()` wrapper 與 `on_crawler_asset_select()` orchestration，但不再直接組 table row、capability lines、credential summary、plan passport summary 或 bounds schema text。
- 新 helper 只做 Tk read-model projection；它不載入 assets、不查 event log、不跑 crawler、不改 profile / credential / download plan。
- 已驗證：`py -3 -B -m py_compile frontends\tk\crawler_asset_workflows.py frontends\tk\crawler_asset_ui_helpers.py tests\test_tk_dialogs.py tests\test_tk_ui_helpers.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs tests.test_tk_ui_helpers -v` 114 tests OK；`frontends\tk` mojibake scan OK；`git diff --check` OK。
- 已提交本地 checkpoint `96bfc7e Move crawler asset Tk row detail helpers`；目前 recovery branch 尚未推送此 commit。
- Docs drift check：本輪只改 Tk helper ownership，不改使用者操作流程、按鈕、crawler、download/import、credential 或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 22:13 Recovery branch pushed
- 已將 recovery branch 推到 GitHub：`origin/rrkal-32e215c-recovery`，遠端 head 為 `3cf23c9 Record recovery branch smoke`。
- 推送前本地完整 smoke 已在 `3cf23c9` 通過：912 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_221019.log`。
- `gh run list --branch rrkal-32e215c-recovery` 沒列出 run；已檢查 `.github/workflows/ci.yml`，目前 CI 只在 `main` push / PR to `main` / manual `workflow_dispatch` 觸發，所以 recovery branch 沒有 Actions run 是預期狀態。
- 若要取得 GitHub Actions 證據，可開 PR 到 `main` 或手動 dispatch workflow；不要把「沒有 branch run」記成 CI failure。

## 2026-05-29 22:06 Recovery branch post-consolidation smoke
- 在 `40d9c0a` / `86b5974` 兩個 consolidation code checkpoint 與對應 docs checkpoint 後，已補跑完整 smoke：`.\scripts\pre_push_smoke_brief.cmd` 通過。
- Smoke 結果：912 tests / 4 skipped，MVP demo `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_220607.log`。
- `pre_push_smoke` 顯示此 recovery branch 尚無 upstream，pending-push diff check 被略過；若要上 GitHub，請推成 `rrkal-32e215c-recovery` 分支，不要直接覆蓋 `origin/main`。
- Docs drift check：本段只補驗證紀錄，不改產品行為、UI/CLI 操作流程或 user guide。

## 2026-05-29 22:04 Source pattern draft Tk message helper ownership cleanup
- 本輪延續 Tk consolidation：新增 `frontends/tk/source_pattern_draft_ui_helpers.py`，把 source pattern draft 成功 / review-needed message formatting 從 `frontends/tk/crawler_asset_workflows.py` 移出。
- `crawler_asset_workflows.py` 從約 1382 行降到約 1303 行；workflow class 保留 `source_pattern_draft_message()` / `source_pattern_draft_review_message()` wrapper 作相容入口，但實際文案投影由新 helper 擁有。
- 新 owner 只把 backend summary dict 轉成 Tk 可讀訊息，不決定 source draft 是否 promotion、不執行 discovery audit、不下載或匯入資料。
- 已驗證：`py -3 -B -m py_compile frontends\tk\crawler_asset_workflows.py frontends\tk\source_pattern_draft_ui_helpers.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 106 tests OK；`frontends\tk` mojibake scan OK；`git diff --check` OK。
- 已提交本地 checkpoint `86b5974 Move source pattern draft Tk messages`；目前 recovery branch 仍未推送。
- Docs drift check：本輪只改 Tk helper ownership，不改 source pattern draft dialog 操作流程、crawler/source pattern 行為、下載/匯入、credential 或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 21:58 Crawler asset flow display helper ownership cleanup
- 本輪延續 recovery lane 上的 display-contract consolidation：新增 `api_launcher/crawler_asset_flow_display.py`，把 `CrawlerAssetFlowStep`、`crawler_asset_card_capabilities()` 與 `crawler_asset_flow_steps()` 從 `api_launcher/crawler_asset_display.py` 移出。
- `crawler_asset_display.py` 從 542 行降到 459 行；它仍 re-export flow display helpers 作相容 surface，但 `frontends/web/preview_assets.py` 已改讀新 owner。
- 新 owner 只負責 crawler asset card capability rows 與 `seed -> source_pattern -> bounds -> download_plan -> review_gate` 流程條的 UI-neutral read model，不執行 crawler、不建立下載計畫、不決定 credential / review policy。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawler_asset_display.py api_launcher\crawler_asset_flow_display.py frontends\web\preview_assets.py tests\test_crawler_assets.py tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_crawler_assets tests.test_web_preview -v` 98 tests OK；`api_launcher` mojibake scan OK；`git diff --check` OK。
- 已提交本地 checkpoint `40d9c0a Move crawler asset flow display helpers`；目前 recovery branch 仍未推送。
- Docs drift check：本輪只改 backend display helper ownership 與 Web import owner，不改 Web/Tk/CLI 操作流程、crawler、download/import、credential 或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 21:50 Recovery workspace and GitHub owner alignment
- 本輪依使用者要求完成 RRKAL recovery lane：`L:\RRKAL_project` 現在是主工作區與提交來源，舊 `K:\APIkeys_collection` 在本 session 只作唯讀參考，`L:` 其他專案資料夾也視為唯讀。
- repo 已從 `c91ed79` 的上一個提交 `32e215c` 建立乾淨救援基底，並完成完整 smoke：`.\scripts\pre_push_smoke_brief.cmd` 通過，912 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_210703.log`。
- Git metadata 已遷回 `L:\RRKAL_project\.git`，不再依賴本機 worktree 指標；本機臨時 clone `C:\Users\lyn59\Documents\Codex\RRKAL_project_seed_32e215c` 已刪除。
- GitHub owner 已改為 `Kagamihara-Ruruka`，`origin` 已更新為 `https://github.com/Kagamihara-Ruruka/APIkeys_collection.git`；active CI / heartbeat / manual import docs URL / workflow docs / repo skill 指令已改用 `Kagamihara-Ruruka/APIkeys_collection`，歷史 development log 保留舊 owner 以維持時間線。
- 已提交本地 checkpoint `8c4b214 Align GitHub owner and workspace references`；目前 branch 是 `rrkal-32e215c-recovery`，尚未推送。若要推 GitHub，應推成 recovery branch，不要直接覆蓋 `origin/main`。
- 已驗證：`py_compile api_launcher\heartbeat.py api_launcher\manual_import.py` OK；`tests.test_heartbeat tests.test_manual_import` 19 tests OK；`git ls-remote origin HEAD` 可讀；`git diff --check` OK；變更 `.md` / repo skill mojibake scan OK。
- Docs drift check：本輪改變工作區與 GitHub owner 工作流，已同步 AGENT_START_HERE、AGENT_HANDOFF、PROJECT_GTD、GIT_HANDOFF、HEARTBEAT_AUTOMATION、SETUP、OpenSpec workflow doc、failure modes、repo skill 與 active code URL/slug。

## 2026-05-29 19:21 Next-action display helper ownership cleanup
- 本輪延續 display-contract consolidation：新增 `api_launcher/crawler_next_action_display.py`，把 `NEXT_ACTION_DISPLAY_LABELS` 與 `next_action_display_label()` 從 `api_launcher/crawler_asset_display.py` 移出。
- `crawler_asset_display.py` 從約 715 行降到約 676 行；它仍 re-export next-action display helpers 作相容 surface，但 download service、schema probe、developer diagnostics、Web payload/assets 與 Tk UI helper 已改讀新 owner。
- 新 owner `crawler_next_action_display.py` 是純 machine `next_action` id 到人類 label 的穩定表格，不 import Web/Tk、crawler service 或 download/import，讓 Tk/Web/未來 Qt 可共用同一份後端顯示契約。
- 已驗證：in-memory compile `api_launcher\crawler_asset_display.py`、`api_launcher\crawler_next_action_display.py`、`api_launcher\crawler_asset_download.py`、`api_launcher\crawler_asset_schema_probe.py`、`api_launcher\developer_diagnostics.py`、`frontends\web\preview_assets.py`、`frontends\web\preview_payloads.py`、`frontends\tk\crawler_asset_ui_helpers.py`、`frontends\tk\ui_helpers.py` OK；`tests.test_crawler_assets` 45 tests OK；`tests.test_web_preview` 53 tests OK；`tests.test_tk_dialogs tests.test_tk_ui_helpers tests.test_crawler_asset_download` 118 tests OK；`api_launcher` mojibake scan OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，912 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_191322.log`。
- 已推送 `8191751 Move next action display labels`；GitHub Actions run `26634236072` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 backend display helper ownership 與 import owner，不改 Web/Tk/CLI 操作流程、crawler、download/import、credential 或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 19:05 Seed enumeration display helper ownership cleanup
- 本輪延續 display-contract consolidation：新增 `api_launcher/crawler_seed_display.py`，把 seed enumeration 的 `SeedEnumerationDisplayProfile`、status display table 與 `seed_enumeration_display_payload()` 從 `api_launcher/crawler_asset_display.py` 移出。
- `crawler_asset_display.py` 從約 835 行降到約 715 行；它仍 re-export seed enumeration display helpers 作相容 surface，但 `api_launcher/crawler_asset_listing_payloads.py` 與 `tests/test_crawler_assets.py` 已改讀新 owner。
- 新 owner `crawler_seed_display.py` 是純 seed enumeration 狀態文案 / tone / next-action contract，不 import Web/Tk、crawler service 或 download/import，讓「枚舉完成度 / local limit / warning / blocked」顯示規則可以獨立維護。
- 已驗證：in-memory compile `api_launcher\crawler_asset_display.py`、`api_launcher\crawler_seed_display.py`、`api_launcher\crawler_asset_listing_payloads.py`、`tests\test_crawler_assets.py`、`tests\test_web_preview.py`、`tests\test_tk_dialogs.py` OK；`tests.test_crawler_assets` 45 tests OK；`tests.test_web_preview` 53 tests OK；`tests.test_tk_dialogs` 106 tests OK；`api_launcher` mojibake scan OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，912 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_185833.log`。
- 已推送 `8b2fc8e Move seed enumeration display helpers`；GitHub Actions run `26633608060` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 backend display helper ownership 與 import owner，不改 Web/Tk/CLI 操作流程、crawler、download/import、credential 或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 18:50 Crawler asset bounds display helper ownership cleanup
- 本輪延續 display-contract consolidation：新增 `api_launcher/crawler_asset_bound_display.py`，把 crawler asset capability label、bounds field label/help、bounds group display text 與 `crawler_asset_bound_form_payload()` 從 `api_launcher/crawler_asset_display.py` 移出。
- `crawler_asset_display.py` 從約 893 行降到約 809 行；它仍保留 plan outcome、download/import、flow steps 與其他 UI-neutral display contract，並 re-export bounds display helpers，避免 Tk/Web/tests 舊 import 立即斷裂。
- 新 owner `crawler_asset_bound_display.py` 只依賴 bounds form dataclass 與 capability dataclass，不回頭 import Web/Tk；這讓界域表單文案 / capability badge 後續可單獨測試、同步 Tk/Web/Qt，不讓 display 巨石繼續吸收所有表單文字。
- 已驗證：in-memory compile `api_launcher\crawler_asset_display.py`、`api_launcher\crawler_asset_bound_display.py`、`tests\test_crawler_assets.py`、`tests\test_web_preview.py`、`tests\test_tk_dialogs.py` OK；`tests.test_crawler_assets` 45 tests OK；`tests.test_web_preview` 53 tests OK；`tests.test_tk_dialogs` 106 tests OK；`api_launcher` mojibake scan OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，912 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_184346.log`。
- 已推送 `99d634e Move crawler asset bounds display helpers`；GitHub Actions run `26632957820` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 backend display helper ownership，不改 Web/Tk/CLI 操作流程、crawler、download/import、credential 或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 18:34 Adapter review display helper ownership cleanup
- 本輪延續 display-contract consolidation：新增 `api_launcher/crawler_asset_review_display.py`，把 adapter-review summary、content parser/import status、content review bucket label/tone、pipeline lane label/tone 等純 display helper 從 `api_launcher/crawler_asset_display.py` 移出。
- `crawler_asset_display.py` 從約 1124 行降到約 893 行；它仍保留 crawler asset / plan outcome / download-import display contract，並 re-export adapter-review display helpers，避免 Tk/Web/tests 的舊 import 立即斷裂。
- 新 owner `crawler_asset_review_display.py` 只依賴 `adapter_review_agent_payload()` 與自己的 display table，不回頭 import Web/Tk；這讓 adapter review / content parser UI 合約可以後續獨立測試與擴充。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawler_asset_display.py api_launcher\crawler_asset_review_display.py frontends\web\preview_api.py frontends\tk\crawler_asset_workflows.py frontends\tk\dialogs.py frontends\tk\import_workflows.py tests\test_web_preview.py tests\test_tk_dialogs.py` OK；`tests.test_web_preview` 53 tests OK；`tests.test_tk_dialogs` 106 tests OK；`tests.test_crawler_asset_download tests.test_crawler_assets` 49 tests OK；`api_launcher` mojibake scan OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，912 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_182918.log`。
- 已推送 `a67f4e7 Move adapter review display helpers`；GitHub Actions run `26632346463` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 backend display helper ownership，不改 Web/Tk/CLI 操作流程、crawler、download/import、credential 或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 18:19 Crawler asset listing payload ownership cleanup
- 本輪延續 backend consolidation：新增 `api_launcher/crawler_asset_listing_payloads.py`，把 listing result 的 `seed_enumeration`、remote pagination 與 compact listing event context helper 從 `api_launcher/crawler_asset_service.py` 移出。
- `crawler_asset_service.py` 從約 753 行降到約 630 行；service 保留 source lookup、crawler execution、candidate upsert、download-plan orchestration，不再持有 listing result UI/event projection 規則。
- `frontends/web/preview_api.py`、`frontends/tk/crawler_asset_workflows.py`、`api_launcher/cli_crawler_assets.py` 與 `tests/test_crawler_assets.py` 已改讀新 owner；`crawler_asset_service.py` 仍 re-export helper 名稱作相容 surface。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawler_asset_service.py api_launcher\crawler_asset_listing_payloads.py api_launcher\cli_crawler_assets.py frontends\tk\crawler_asset_workflows.py frontends\web\preview_api.py tests\test_crawler_assets.py` OK；`tests.test_crawler_assets` 45 tests OK；`tests.test_web_preview` 53 tests OK；`tests.test_tk_dialogs` 106 tests OK；`api_launcher` mojibake scan OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，912 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_181330.log`。
- 已推送 `6806a58 Move crawler asset listing payload helpers`；GitHub Actions run `26631709497` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 helper ownership 與 import owner，不改 Web/Tk/CLI 操作流程、crawler、download/import、credential 或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 18:05 Crawler asset payload adapter ownership cleanup
- 本輪延續 backend consolidation：新增 `api_launcher/crawler_asset_payloads.py`，把 crawler asset bounds payload 轉成 `SourceDownloadOptions` / `SourceDownloadBounds` 的 adapter helper 從 `api_launcher/crawler_asset_service.py` 移出。
- `crawler_asset_service.py` 從約 968 行降到約 828 行；service 仍保留 listing、seed plan、candidate upsert 與 orchestration，不再同時擁有 UI-neutral bounds payload parsing、version selector、bbox / tuple / int / bool coercion 等 adapter 細節。
- `api_launcher.crawler_asset_service` 仍保留同名 import surface，舊呼叫 `source_download_options_from_crawler_asset_payload` 不會斷；`tests/test_crawler_assets.py` 已改讀新 owner。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawler_asset_service.py api_launcher\crawler_asset_payloads.py tests\test_crawler_assets.py` OK；`py -3 -B -m unittest tests.test_crawler_assets -v` 45 tests OK；compat import smoke OK；`api_launcher` mojibake scan OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，912 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_175921.log`。
- 已推送 `9f44aa5 Move crawler asset payload adapters`；GitHub Actions run `26631096034` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 helper ownership 與測試 import，不改 Web/Tk/CLI 操作流程、crawler、download/import、credential 或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 17:50 Tk credential dialog next-action label
- 本輪完成 GTD 上的 Tk credential UX 小項：`frontends/tk/crawler_asset_credential_dialog.py` 新增 `crawler_asset_credential_next_action_text()`，credential dialog 會優先顯示後端 `next_action_label_zh_TW` / display profile label，不把 raw `next_action` id 顯示給一般使用者。
- Dialog 仍只是薄 UI：不判斷哪個 crawler 需要 credential、不保存明文到事件、不改 `api_launcher.local_credentials` 的 credential guard / storage policy。
- 新增 regression：`tests.test_tk_dialogs.TkDialogModuleTest.test_credential_dialog_next_action_uses_display_label_not_raw_id`。
- 已驗證：`py -3 -B -m py_compile frontends\tk\crawler_asset_credential_dialog.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 106 tests OK；`frontends\tk` mojibake scan OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，912 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_174501.log`。
- 已推送 `98b2805 Show credential next action in Tk dialog`；GitHub Actions run `26630439903` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 Tk credential dialog 顯示文案與測試，不改登入欄位、credential storage、下載/匯入、Web route 或 user guide；已同步 GTD、handoff 與 development log。

## 2026-05-29 17:39 Web Preview diagnostics helper ownership cleanup
- 本輪延續 Web Preview consolidation：新增 `frontends/web/preview_diagnostics.py`，把 `web_preview_status()`、`web_project_maturity()`、`crawler_handler_smoke_diagnostics()`、`web_real_download_demo()` 與 `developer_real_download_demo()` 從 `frontends/web/preview_api.py` 移出。
- `frontends/web/preview_api.py` 從約 497 行降到約 428 行；它仍保留 crawler asset listing、credential update、plan preview、asset download/import 與 seed download/import endpoint orchestration，不再同時持有 health / maturity / developer diagnostics / demo proof helper。
- `frontends/web/server.py` 已改由 `frontends.web.preview_diagnostics` 匯入 health、maturity、crawler smoke 與 developer demo helpers；`tests/test_web_preview.py` 的 mock target 也對齊新 owner。
- 已驗證：`py -3 -B -m py_compile frontends\web\preview_api.py frontends\web\preview_assets.py frontends\web\preview_diagnostics.py frontends\web\server.py tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 53 tests OK；`frontends\web` mojibake scan OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，911 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_173302.log`。
- 已推送 `8018b38 Move Web preview diagnostics helpers`；GitHub Actions run `26629906445` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 Web diagnostics/status helper ownership 與 import/mock 路徑，不改 Web API route、JS 操作、crawler/download/import/credential 行為或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 17:24 Web Preview asset read-model helper ownership cleanup
- 本輪延續 Web Preview consolidation：新增 `frontends/web/preview_assets.py`，把 `crawler_asset_cards()`、`crawler_asset_card()`、`crawler_asset_detail()`、`crawler_asset_seed_page()`、`crawler_asset_seed_row()`、`save_crawler_asset_seed_favorite()` 與 `crawler_asset_credential_detail()` 從 `frontends/web/preview_api.py` 移出。
- `frontends/web/preview_api.py` 從約 703 行降到約 497 行；它仍保留 status / project maturity / developer diagnostics / listing / credential update / plan preview / download-import endpoint orchestration，不再持有 asset card/detail/seed read-model projection。
- `frontends/web/server.py` 已改由 `frontends.web.preview_assets` 匯入 asset cards/detail/credential/seed/favorite helpers；`tests/test_web_preview.py` 也改讀新 owner。`preview_api.py` 暫時保留同名 import 作為相容 surface，避免其他內部呼叫立即斷裂。
- 已驗證：`py -3 -B -m py_compile frontends\web\preview_api.py frontends\web\preview_assets.py frontends\web\server.py tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 53 tests OK；`frontends\web` mojibake scan OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，911 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_171844.log`。
- 已推送 `173f057 Move Web preview asset helpers`；GitHub Actions run `26629273947` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 Web asset read-model helper ownership 與 import/test 路徑，不改 Web API route、JS 操作、crawler/download/import/credential 行為或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 17:00 Web Preview event helper ownership cleanup
- 本輪延續 Web Preview consolidation：新增 `frontends/web/preview_events.py`，把 `recent_crawler_asset_listing_outcomes()`、`compact_listing_outcome()`、`recent_crawler_asset_plan_outcomes()`、`recent_crawler_asset_plan_passports()`、`web_preview_recent_events()` 與 event payload summary 從 `frontends/web/preview_api.py` 移出。
- `frontends/web/preview_api.py` 從約 798 行降到約 703 行；它仍保留 asset cards/detail、credential update、listing、plan preview、download/import 等 endpoint orchestration，不再持有事件摘要壓縮規則。
- `frontends/web/server.py` 已改由 `frontends.web.preview_events` 匯入 `web_preview_recent_events()`；`tests/test_web_preview.py` 的 event helper 與 `latest_events` patch target 也對齊新 owner。
- 已驗證：`py -3 -B -m py_compile frontends\web\preview_api.py frontends\web\preview_context.py frontends\web\preview_payloads.py frontends\web\preview_events.py frontends\web\server.py tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 53 tests OK；`frontends\web` / `docs` mojibake scan OK；`git diff --check` OK（僅 `PROJECT_GTD.md` CRLF/LF 提醒）；`.\scripts\pre_push_smoke_brief.cmd` 通過，911 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_170131.log`。
- 已推送 `0dffffc Move Web preview event helpers`；GitHub Actions run `26628565727` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 Web event summary helper ownership 與 import/mock 路徑，不改 Web API route、JS 操作、crawler/download/import/credential 行為或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 16:41 Web Preview context helper ownership cleanup
- 本輪延續 Web Preview consolidation：新增 `frontends/web/preview_context.py`，把 `WebPreviewRepositorySession`、`WebCrawlerAssetActionContext`、`web_preview_repository_context()`、`web_crawler_asset_action_context()`、`crawler_asset_bound_form()`、`crawler_asset_payload_from_web_values()` 與 crawler asset lookup 從 `frontends/web/preview_api.py` 移出。
- `frontends/web/preview_api.py` 從約 889 行降到約 798 行；它仍保留 Web endpoint orchestration、route-specific credential blocking、plan build、download/import、event logging 與 passport update，不把 commit/download/import 決策藏進 context helper。
- `frontends/web/server.py` 已改由 `frontends.web.preview_context` 匯入 `crawler_asset_payload_from_web_values()`，避免 server route 繼續依賴 `preview_api.py` 的舊 helper ownership；`tests/test_web_preview.py` 的 action-context helper import 也對齊新 owner。
- 已驗證：`py -3 -B -m py_compile frontends\web\preview_api.py frontends\web\preview_context.py frontends\web\preview_payloads.py frontends\web\server.py tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 53 tests OK；`frontends\web` / `docs` mojibake scan OK；`git diff --check` OK（僅 `PROJECT_GTD.md` CRLF/LF 提醒）；`.\scripts\pre_push_smoke_brief.cmd` 通過，911 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_164536.log`。
- 已推送 `61018b6 Move Web preview context helpers`；GitHub Actions run `26627862336` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 Web context/setup helper ownership 與 import 路徑，不改 Web API route、JS 操作、crawler/download/import/credential 行為或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 15:25 Web Preview payload helper ownership cleanup
- 本輪延續 Web Preview consolidation：新增 `frontends/web/preview_payloads.py`，把 `web_next_action_payload()`、`apply_web_next_action()`、`web_crawler_asset_listing_payload()`、`crawler_asset_listing_options()`、`web_download_import_target_paths()`、`web_download_import_event_context()`、`web_download_import_credential_blocked_response()` 與相關 path dataclass 從 `frontends/web/preview_api.py` 移出。
- `frontends/web/preview_api.py` 從約 1053 行降到約 889 行，保留 route/API-facing orchestration、repository session、asset lookup、credential guard、plan/download/import service 呼叫；純 Web response/path helper 改由 `preview_payloads.py` 擁有，避免 API route 檔繼續吸收 display/payload 細節。
- `tests/test_web_preview.py` 已改由 `frontends.web.preview_payloads` 匯入這批 helper；搬移後修正 `default_local_downloads_root` patch target，避免測試仍 patch 舊 owner。
- 已驗證：`py -3 -B -m py_compile frontends\web\preview_api.py frontends\web\preview_payloads.py tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 53 tests OK；`frontends\web` / `docs` mojibake scan OK；`git diff --check` OK（僅 `PROJECT_GTD.md` CRLF/LF 提醒）；`.\scripts\pre_push_smoke_brief.cmd` 通過，911 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_162409.log`。
- 已推送 `14a9d61 Move Web preview payload helpers`；GitHub Actions run `26627022320` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 Web helper ownership 與測試 patch target，不改 Web API route、JS 操作、crawler/download/import/credential 行為或 user guide；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 15:10 Tk crawler asset helper ownership cleanup
- 本輪延續 Tk consolidation：把先前暫放在 generic `frontends/tk/ui_helpers.py` 的 crawler asset / seed download-import helper 全部移到 `frontends/tk/crawler_asset_ui_helpers.py`。`ui_helpers.py` 現在回到 yfinance、data-store、MVP smoke 等較通用的 Tk helper owner，不再同時承擔 crawler asset 專屬文案、plan summary、credential guard 與 seed target path。
- `frontends/tk/crawler_asset_workflows.py` 現在只從 `frontends.tk.crawler_asset_ui_helpers` 匯入 crawler asset UI projection；`tests/test_tk_dialogs.py` / `tests/test_tk_ui_helpers.py` 的 patch target 也已對齊新 owner，避免測試仍 patch 舊模組但實際依賴已搬走。
- 已驗證：`py -3 -B -m py_compile frontends\tk\ui_helpers.py frontends\tk\crawler_asset_ui_helpers.py frontends\tk\crawler_asset_workflows.py tests\test_tk_ui_helpers.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_ui_helpers tests.test_tk_dialogs -v` 113 tests OK；`git diff --check` OK；`frontends\tk` / `tests` / `docs` mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，911 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_150355.log`。
- 已推送 `c4a108b Move crawler asset helpers to dedicated module`；GitHub Actions run `26623612788` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 helper ownership 與測試 patch target，不改使用者操作流程、按鈕、crawler/download/import 行為或 UI 文案 contract；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 14:39 Tk crawler asset display helper module
- 本輪延續 Tk 大檔 consolidation：新增 `frontends/tk/crawler_asset_ui_helpers.py`，把 seed page status / preview、seed enumeration note、credential badge / summary、credential event context、listing event preview、state label、review count 等純 Tk 投影 helper 從 `frontends/tk/crawler_asset_workflows.py` 移出。
- `crawler_asset_workflows.py` 行數從約 1601 行降到約 1384 行；它仍保留 workflow、background job handoff、service 呼叫與 dialog routing，不再承擔這批 table/sidebar/status text helper ownership。
- `tests/test_tk_dialogs.py` 已改由 `frontends.tk.crawler_asset_ui_helpers` 匯入這批 helper，避免測試繼續把大型 workflow 檔當成 display helper owner。
- 已驗證：`py -3 -B -m py_compile frontends\tk\crawler_asset_workflows.py frontends\tk\crawler_asset_ui_helpers.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 105 tests OK；`frontends\tk` / `tests` mojibake scan OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，911 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_144106.log`。
- 已推送 `6822095 Extract Tk crawler asset display helpers`；GitHub Actions run `26622638928` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 Tk helper ownership，不改使用者操作流程、按鈕、後端 service 或 UI 文案 contract；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 14:19 Tk crawler asset UI helper consolidation
- 本輪做 Tk crawler asset workflow 的小型 consolidation：把下載計畫摘要、listing blocked status、plan outcome 短標籤、plan passport 摘要與 credential guard prompt helper 從 `frontends/tk/crawler_asset_workflows.py` 移到 `frontends/tk/ui_helpers.py`。
- `crawler_asset_workflows.py` 現在只消費這些 Tk UI helper，不再同時承擔 crawler asset workflow 與 message/summary helper ownership；後端 crawler、download/import、credential guard、plan outcome、plan passport 行為不變。
- `tests/test_tk_dialogs.py` 已改由 `frontends.tk.ui_helpers` 匯入這些 helper，避免測試繼續把大型 workflow 檔當成 helper owner。
- 已驗證：`py -3 -B -m py_compile frontends\tk\crawler_asset_workflows.py frontends\tk\ui_helpers.py tests\test_tk_dialogs.py tests\test_tk_ui_helpers.py` OK；`py -3 -B -m unittest tests.test_tk_ui_helpers -v` 8 tests OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 105 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，911 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_142011.log`。
- 已推送 `7f13bcf Move Tk crawler asset UI helpers`；GitHub Actions run `26621919504` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只改 Tk helper ownership，不改使用者操作流程或 UI 文案 contract；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 14:00 GitHub adjacent project scan / docs governance
- 依使用者要求用 GitHub read-only 盤點其他 repo：`RRKAL_displaytools` 今天仍活躍，最新 `08a6eab Acknowledge boundary highlight renderer input`，最近 smoke runs success；`CODE_KM` 最新 `bc78f85 Record next action checkpoint` 且 CI success；`rrkal-visual-compressor` 最新 `03d7232 Add one-command MVP pipeline`；`rrkal-renderer` 最新 `a1351c3 feat: allow disabling auto-open preview in photo sample runner`。
- 新增 `docs/EXTERNAL_PROJECT_CONTEXT.zh-TW.md`，把這些 repo 的可借鑑方向與 read-only 邊界寫清楚：可抽 display contract、renderer input acknowledgement、one-command pipeline、provenance surfaced output、governed ingestion workflow；不要直接搬碼或把外部 repo 當 RRKAL runtime dependency。
- `DOCS_INDEX.zh-TW.md` 已加入「參考其他 GitHub 專案進度」閱讀路線與新文件角色。
- 已推送 `beb42d8 Document adjacent project context`；GitHub Actions run `26621082393` 已通過 Ubuntu、Windows 與 real DB smoke。
- RRKAL 最近程式 checkpoint `c3f53d6 Move recent plan event display helpers` 已推送，GitHub Actions run `26620918050` 通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪新增外部專案上下文文件與索引；它是參考地圖，不改產品能力、不改使用者操作流程。User guide 不需更新。

## 2026-05-29 07:46 Recent plan event extraction display contract
- 本輪把「從 structured event log 萃取最近 plan outcome / plan passport」的規則從 `frontends/web/preview_api.py` 收回 `api_launcher/crawler_asset_display.py`：新增 `crawler_asset_recent_plan_outcomes_from_events()` 與 `crawler_asset_recent_plan_passports_from_events()`。
- Web Preview 的 `recent_crawler_asset_plan_outcomes()` / `recent_crawler_asset_plan_passports()` 現在只負責讀 `latest_events()`，再交給 backend display helper 篩選 `crawler_asset_plan_outcome_recorded`、壓縮 badge / passport payload；Web 不再持有 event context 的壓縮規則或 thin `compact_web_plan_passport_payload()` wrapper。
- 新增 regression：`tests.test_web_preview.WebPreviewApiTest.test_recent_plan_event_helpers_keep_ui_payloads_compact`，鎖住 helper 會忽略非 plan event，且不讓 `providers` / `resolved_plan` 這類大 payload 進 UI status surface。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawler_asset_display.py frontends\web\preview_api.py tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 53 tests OK；docs/source mojibake scan OK；`git diff --check` OK（僅 `PROJECT_GTD.md` CRLF/LF 提醒）；`.\scripts\pre_push_smoke_brief.cmd` 通過，911 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_074816.log`。
- 已推送 `c3f53d6 Move recent plan event display helpers`；GitHub Actions run `26620918050` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪改 Web recent plan event helper ownership；已同步 GTD、handoff 與 development log。使用者操作入口未改，user guide 不需更新。

## 2026-05-29 07:29 Tk plan event context reuse
- 本輪把 Tk 的 `record_crawler_asset_plan_outcome()` 也接到 backend `crawler_asset_plan_event_context()`：Tk 不再手寫 asset id、outcome counts、content review、run record 與 plan passport event keys。
- Tk 仍保留本地 resolved plan path 作為事件中的 `resolved_plan`，並保留 `review_queue_count` 使用 resolved plan adapter review count；這兩個是 Tk 寫檔 / 顯示 queue 的本地 artifact，不移回 Web。
- 移除 `frontends/tk/crawler_asset_workflows.py` 對 `crawler_run_record_from_result` 的直接 import；run record 由 backend display helper 產生。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawler_asset_display.py frontends\tk\crawler_asset_workflows.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 105 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，910 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_073145.log`。
- 已推送 `49c3040 Reuse plan event context in Tk`；GitHub Actions run `26608663640` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪改 Tk plan event context helper ownership；已同步 GTD、handoff 與 development log。使用者操作入口未改，user guide 不需更新。

## 2026-05-29 07:16 Plan event context display contract
- 本輪繼續 Web Preview bounded consolidation：`crawler_asset_plan_event_context()` 從 `frontends/web/preview_api.py` 移到 `api_launcher/crawler_asset_display.py`，與 plan badge / plan outcome display helpers 放在同一個 UI-neutral display contract module。
- Web Preview 仍負責在 plan preview 與 download/import completion 時寫 structured event，但 compact event shape、run record 與 plan passport 壓縮規則改由後端 helper 擁有，避免未來 Tk/Web/Qt 各自發明 event keys。
- 既有 regression `tests.test_web_preview.WebPreviewApiTest.test_web_plan_event_context_keeps_badge_payload_compact` 改為直接測 backend helper；Web endpoint 行為不變。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawler_asset_display.py frontends\web\preview_api.py tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 52 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，910 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_071718.log`。
- 已推送 `66fd82b Move plan event context display payload`；GitHub Actions run `26608126362` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪改 plan event context helper ownership；已同步 GTD、handoff 與 development log。使用者操作入口未改，user guide 不需更新。

## 2026-05-29 06:56 Credential-blocked plan display payload
- 本輪繼續 Web Preview bounded consolidation：`api_launcher/crawler_asset_display.py` 新增 `credential_blocked_plan_outcome_payload()` 與 `credential_blocked_plan_passport_payload()`，把缺登入 / API Key 時的 plan outcome 與 plan passport 從 Web route 移回 backend display contract。
- `frontends/web/preview_api.py` 的 plan preview、asset download/import、seed download/import credential-blocked 分支改為消費這兩個 helper；Web 仍負責 endpoint-level next action 與 credential guard，不再自己組 `credential_setup_required` 形狀。
- 新增 regression：`tests.test_web_preview.WebPreviewApiTest.test_credential_blocked_plan_payloads_are_backend_display_contract`。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawler_asset_display.py frontends\web\preview_api.py tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 52 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，910 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_065819.log`。
- 已推送 `deeb96b Move credential-blocked plan display payloads`；GitHub Actions run `26607436050` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪改 Web credential-blocked 內部 display helper ownership；已同步 GTD、handoff 與 development log。使用者操作入口未改，user guide 不需更新。

## 2026-05-29 06:38 Web listing payload helper
- 本輪繼續 Web Preview bounded consolidation：`frontends/web/preview_api.py` 新增 `web_crawler_asset_listing_payload()`，讓 listing blocked 分支與 live listing 成功分支都先使用 `CrawlerAssetListingResult.to_dict()` 的同一份 service-owned 結構，再由 Web 附加 `next_action_label`。
- `crawler_asset_listing()` 的 credential-blocked 分支不再手寫 candidate counts、seed enumeration、search scope 等 listing payload；這些欄位由 `CrawlerAssetListingResult` dataclass 保持一致。Web 仍明確處理 credential guard 與 endpoint-level next action。
- 移除 `preview_api.py` 對 `crawler_seed_enumeration_payload` 的直接 import，避免 Web endpoint 自己重建 seed enumeration。
- 新增 regression：`tests.test_web_preview.WebPreviewApiTest.test_web_crawler_asset_listing_payload_adds_label_without_rebuilding_shape`，並補強 listing endpoint 測試確認 nested `listing_result.next_action_label` 也存在。
- 已驗證：`py -3 -B -m py_compile frontends\web\preview_api.py tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 51 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，909 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_064048.log`。
- 已推送 `a54a931 Normalize web listing payloads`；GitHub Actions run `26606736921` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪改 Web listing endpoint 內部 payload helper；已同步 GTD、handoff 與 development log。使用者操作入口未改，user guide 不需更新。

## 2026-05-29 06:23 Web crawler action context helper
- 本輪繼續 Web Preview bounded consolidation：`frontends/web/preview_api.py` 新增 `WebCrawlerAssetActionContext` 與 `web_crawler_asset_action_context()`，集中 plan preview、asset download/import、seed download/import 三條 endpoint 共用的 asset lookup、credential guard 與 bounds payload 解析。
- Endpoint 仍明確保留各自的 credential blocking、plan build、download/import、passport update 與 event logging；helper 只收斂重複 setup，不隱藏交易或業務決策。
- 新增 regression：`tests.test_web_preview.WebPreviewApiTest.test_web_crawler_asset_action_context_resolves_asset_credentials_and_bounds`。
- 驗證過程中先寫錯測試假設：credential demo asset 的 limit facet 是 `granule_limit`，不是通用 `limit`。已改成檢查後端 facet key，避免測試用 UI 欄位名稱猜 backend contract。
- 已驗證：`py -3 -B -m py_compile frontends\web\preview_api.py tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 50 tests OK；`frontends\web` 與 docs mojibake scan OK；`git diff --check` OK（僅 `PROJECT_GTD.md` CRLF/LF 提醒）；`.\scripts\pre_push_smoke_brief.cmd` 通過，908 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_062631.log`。
- 已推送 `87d7f7b Extract web crawler action context`；GitHub Actions run `26606124857` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪改 Web endpoint 內部 setup helper；已同步 GTD、handoff 與 development log。使用者操作入口未改，user guide 不需更新。

## 2026-05-29 06:07 Web next-action payload helper
- 本輪做 Web Preview endpoint 狀態 payload 的小型 consolidation：`frontends/web/preview_api.py` 新增 `web_next_action_payload()` 與 `apply_web_next_action()`，集中產生 `next_action` + `next_action_label`。
- `crawler_asset_listing()`、`crawler_asset_plan_preview()`、asset-level download/import、seed-level download/import 與 credential-blocked download/import payload 改用同一個 helper，避免 Web endpoint 各自呼叫 `next_action_display_label()` 或手動組 action/label。
- 這不改 crawler、download/import、credential guard、plan outcome、plan passport、Web route 或 JavaScript 操作流程；只是讓 Web Preview 更像 thin UI adapter，後續 Tk/Qt parity 檢查可直接比對同一種 action-label contract。
- 新增 regression：`tests.test_web_preview.WebPreviewApiTest.test_web_next_action_payload_pairs_backend_id_with_display_label`。
- 已驗證：`py -3 -B -m py_compile frontends\web\preview_api.py tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 49 tests OK；`frontends\web` 與 docs mojibake scan OK；`git diff --check` OK（僅 `PROJECT_GTD.md` CRLF/LF 提醒）；`.\scripts\pre_push_smoke_brief.cmd` 通過，907 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_060852.log`。
- 已推送 `e8e50d4 Consolidate web next-action payloads`；GitHub Actions run `26605399831` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪改 Web endpoint 內部 payload 組裝；已同步 GTD、handoff 與 development log。使用者操作入口未改，user guide 不需更新。

## 2026-05-29 05:51 Tk metadata / AI background capacity guard
- 本輪把 provider metadata crawl 與 AI summary 兩類外部工作量入口也補上 capacity guard：`frontends/tk/source_action_workflows.py` 新增 `MAX_TK_SOURCE_ACTION_BACKGROUND_JOBS = 2`，`frontends/tk/ai_summary_workflows.py` 新增 `MAX_TK_AI_SUMMARY_BACKGROUND_JOBS = 2`。
- `SourceActionWorkflowMixin.crawl_provider_ids()` 仍保留 provider scope single-flight key；不同 provider scope 已有 2 個 metadata crawl worker 時，第三個入口只更新 status，不再開新 worker。
- `AiSummaryWorkflowMixin.generate_active_summary()` 仍保留 provider/profile single-flight key；已有 2 個 AI summary worker 時，第三個入口只更新 status，不再開新 worker。這降低雲端 / 本機 AI 呼叫與 repository notes 回寫併發壓力。
- 這不改 metadata crawler、provider row action、AI profile、credential 檢查、summary generation 或 repository upsert 行為。
- 新增 regression：`test_source_action_metadata_crawl_blocks_when_queue_full` 與 `test_ai_summary_blocks_when_queue_full`。
- 已驗證：`py -3 -B -m py_compile frontends\tk\source_action_workflows.py frontends\tk\ai_summary_workflows.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_background_jobs tests.test_tk_dialogs -v` 109 tests OK；`frontends\tk` 與 docs mojibake scan OK；`git diff --check` OK（僅 `PROJECT_GTD.md` / `frontends/tk/ai_summary_workflows.py` CRLF/LF 提醒）；`.\scripts\pre_push_smoke_brief.cmd` 通過，906 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_055235.log`。
- 已推送 `c5965d5 Cap Tk metadata and AI summary jobs`；GitHub Actions run `26604680441` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪改 Tk metadata crawl / AI summary 背景工作 capacity guard；已同步 GTD、handoff 與 development log。使用者操作入口未改，user guide 不需更新。

## 2026-05-29 05:39 Tk discovery background capacity guard
- 本輪把 Tk discovery / crawler-audit 類背景工作再加一層 capacity guard：`frontends/tk/discovery_workflows.py` 新增 `MAX_TK_DISCOVERY_BACKGROUND_JOBS = 2` 與 `notify_discovery_queue_full()`。
- Provider candidate discovery、dataset candidate discovery、local discovery dry-run audit 仍保留各自 single-flight key；現在同一 UI 已有 2 個 discovery/audit worker 時，第三個入口只更新 status「Discovery 背景工作已達上限」，不再開新 daemon thread。
- 這不改 provider discovery、dataset crawler audit、local promotion dry-run、repository upsert 或 review dialog；只是降低連點 / 低算力設備下的 discovery worker 併發壓力。
- 新增 regression：`test_provider_discovery_blocks_when_discovery_queue_full`、`test_dataset_candidate_discovery_blocks_when_discovery_queue_full`、`test_local_discovery_audit_blocks_when_discovery_queue_full`。
- 已驗證：`py -3 -B -m py_compile frontends\tk\discovery_workflows.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_background_jobs tests.test_tk_dialogs -v` 107 tests OK；`frontends\tk` 與 docs mojibake scan OK；`git diff --check` OK（僅 `PROJECT_GTD.md` / `frontends/tk/discovery_workflows.py` CRLF/LF 提醒）；`.\scripts\pre_push_smoke_brief.cmd` 通過，904 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_054019.log`。
- 已推送 `a8580b2 Cap Tk discovery background jobs`；GitHub Actions run `26604123009` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪改 Tk discovery 背景工作 capacity guard；已同步 GTD、handoff 與 development log。使用者操作入口未改，user guide 不需更新。

## 2026-05-29 05:25 Tk SQLite import capacity guard
- 本輪把 Tk 匯入入口從「同一路徑 duplicate guard」再補成「同一 UI 同時最多一個 SQLite import worker」：`ImportWorkflowMixin` 新增 `MAX_TK_SQLITE_IMPORT_JOBS = 1`、`sqlite_import_queue_is_full()` 與共用 busy status helper。
- `import_supported_plan_results_from_ui()` 與 `import_local_file_from_ui()` 會在開 policy dialog / file picker 前先檢查整體 import queue；已有其他 SQLite import worker 時只更新 status，不彈使用者流程，也不開新 worker。
- `start_single_flight_thread()` 呼叫同步帶 `max_active_jobs=1` / `on_capacity`，作為前置 guard 之外的保險。這不改 manifest、existing-table policy、local file provenance review、importer 或 ingestion pipeline 規則。
- 新增 regression：`test_import_supported_plan_results_blocks_when_sqlite_import_queue_full` 與 `test_import_local_file_blocks_when_sqlite_import_queue_full_before_file_picker`。
- 已驗證：`py -3 -B -m py_compile frontends\tk\import_workflows.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_background_jobs tests.test_tk_dialogs -v` 104 tests OK；`frontends\tk` 與 docs mojibake scan OK；`git diff --check` OK（僅 `PROJECT_GTD.md` CRLF/LF 提醒）；`.\scripts\pre_push_smoke_brief.cmd` 通過，901 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_052631.log`。
- 已推送 `ac59e6f Cap Tk SQLite import jobs`；GitHub Actions run `26603488680` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪改 Tk 匯入背景工作 capacity guard；已同步 GTD、handoff 與 development log。使用者操作入口未改，user guide 不需更新。

## 2026-05-29 05:10 Tk crawler asset background capacity guard
- 本輪在 `frontends/tk/background_jobs.py` 的 `start_single_flight_thread()` 補 `max_active_jobs` / `on_capacity`，讓同一 owner 不只擋同 key duplicate，也能在不同 key 背景工作太多時拒絕開新 daemon thread。
- `CrawlerAssetWorkflowMixin._start_crawler_asset_background_job()` 先把 crawler asset 分頁的並行背景工作上限設為 `MAX_CRAWLER_ASSET_BACKGROUND_JOBS = 4`；超過時只更新 status「爬蟲資產背景工作已達上限，請等目前工作完成」，不再開新 worker。
- 這是 bounded scheduler consolidation 的小步：不改 crawler/listing/schema probe/seed download/import service，不導入 asyncio，只先降低連點或多 seed 操作造成的無限制 thread / SQLite path 競爭風險。
- 新增 `tests/test_tk_background_jobs.py::test_start_single_flight_thread_rejects_capacity_before_spawning_thread`。
- 已驗證：in-memory compile `frontends\tk\background_jobs.py` / `frontends\tk\crawler_asset_workflows.py` / `tests\test_tk_background_jobs.py` OK；`py -3 -B -m unittest tests.test_tk_background_jobs tests.test_tk_dialogs -v` 102 tests OK；`frontends\tk` 與 docs mojibake scan OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，899 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_051203.log`。
- 已推送 `2a657bc Cap Tk crawler asset background jobs`；GitHub Actions run `26602836368` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪改 Tk crawler asset 背景工作 capacity guard；已同步 GTD、handoff 與 development log，user guide 不需更新，因操作入口未改。

## 2026-05-29 04:57 Web/Tk callback diagnostics visible surface
- 本輪把上一個 checkpoint 的 backend `callback_diagnostics` 顯示契約接到 Web / Tk：Web download/import result row 會顯示 `進度回報有警告` chip、下一步與前兩筆 callback error preview，並在 mission list 補一筆 callback diagnostics mission；Tk seed download/import completion message 也會把 callback warning 與「檢查事件紀錄或 UI 進度回報」寫進 message body。
- 前端不重新判斷 callback error 是否代表下載失敗，只消費 backend `callback_diagnostics.display_label` / `next_action_label` / `errors`；成功 download/import 仍維持成功，callback diagnostics 只是 observer/UI progress warning。
- 已補 `tests/test_tk_ui_helpers.py::test_crawler_seed_download_import_ui_message_surfaces_callback_diagnostics`，並在 Web static contract 測試鎖住 `downloadImportCallbackDiagnostics()` / `callbackDiagnosticsHtml()` / `addCallbackDiagnosticsMission()` 與使用者可讀 warning 文案。
- 已驗證：`node --check frontends\web\static\app.js` OK；in-memory compile `frontends\tk\ui_helpers.py` / tests OK；`py -3 -B -m unittest tests.test_tk_ui_helpers tests.test_web_preview tests.test_tk_dialogs -v` 154 tests OK；Web/Tk touched files mojibake scan OK；`git diff --check` OK（僅 CRLF 提醒）；`.\scripts\pre_push_smoke_brief.cmd` 通過，898 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_045827.log`。
- 已推送 `9dbe3d2 Show callback diagnostics in Web and Tk`；GitHub Actions run `26602160525` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪改 Web/Tk 顯示 callback diagnostics 的文字 surface，不改按鈕或操作流程；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 04:42 Crawler asset callback diagnostics display payload
- 本輪把 `DownloadPlanRunResult.callback_errors` 再往 UI-neutral crawler asset 顯示 payload 接一層：`crawler_asset_download_import_display_payload()` 現在會輸出 top-level `callback_diagnostics`，並在 nested `download_import` 內提供 `callback_error_count`、`callback_errors` 與 `callback_diagnostics`。
- `callback_diagnostics` 會把無錯誤狀態標成「進度回報正常」，有錯誤時標成 warning，並給 `inspect_event_logs_or_ui_callback` / 「檢查事件紀錄或 UI 進度回報」下一步；這仍是 observer/UI progress diagnostics，不把成功 download/import 重新分類成 failed。
- 已補 `tests/test_crawler_asset_download.py::test_download_import_display_payload_packages_shared_ui_state` regression，鎖住 display payload 會保留 callback warning 與 next-action label。
- 已驗證：in-memory compile `api_launcher\crawler_asset_display.py` / `tests\test_crawler_asset_download.py` OK（K 槽 `__pycache__` lock 曾讓 `py_compile` 寫 pyc 失敗，非語法錯誤）；`py -3 -B -m unittest tests.test_crawler_asset_download -v` 4 tests OK；`py -3 -B -m unittest tests.test_web_preview -v` 48 tests OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 98 tests OK；`api_launcher\crawler_asset_display.py` 與 docs mojibake scan OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，897 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_044415.log`。
- 已推送 `d8b7f54 Surface callback diagnostics in display payload`；GitHub Actions run `26601404592` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪改 shared backend display payload，讓 UI 可呈現 callback diagnostics；已同步 GTD、handoff 與 development log，user guide 不需更新，因使用者操作流程未改。

## 2026-05-29 04:26 Download plan callback diagnostics surface
- 本輪把 `DownloadPlanRunResult.callback_errors` 往外接到 CLI/event surface：`download_plan_executed` structured event 現在會記錄 `callback_error_count` 與前 5 筆 `callback_errors` 預覽。
- `render_download_import_cli_lines()` 現在會在 callback diagnostics 存在時輸出 `[download-plan] callback_errors=N` 與逐筆 callback diagnostic；這仍是 observer/UI diagnostics，不把成功下載改成 failed。
- 新增 `tests/test_download_plan_runner.py::test_cli_render_lines_include_callback_diagnostics`，並在 `test_cli_emits_download_plan_json_summary` 鎖住 event context 的 callback diagnostics 欄位。
- 已驗證：`PYTHONDONTWRITEBYTECODE=1 py -3 -B -m py_compile api_launcher\cli_download_plan.py api_launcher\ingestion_pipeline.py tests\test_download_plan_runner.py` OK；`py -3 -B -m unittest tests.test_download_plan_runner -v` 13 tests OK；`py -3 -B -m unittest tests.test_download_jobs tests.test_download_plan_runner -v` 16 tests OK；`py -3 -B -m unittest tests.test_handoff -v` 21 tests OK；`git diff --check` OK；相關 source/docs mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，897 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_042759.log`。
- 已推送 `adcec1c Surface download callback diagnostics in CLI event`；GitHub Actions run `26600577586` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪改 CLI/event diagnostics payload 與 CLI 摘要，不改使用者操作流程；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 04:12 Download plan callback diagnostics
- 本輪把 queue callback isolation 的診斷出口接到 `api_launcher/downloads/plan_runner.py`：`DownloadPlanRunResult` 新增 `callback_errors`，`to_dict()` 也會輸出同欄位。
- `run_download_plan_payload()` 會在 queue shutdown 前讀取 `queue.callback_error_snapshot()`；progress callback 失敗會進入 diagnostics，但不會增加 `failed`，也不會把已完成下載改成失敗。
- 新增 `tests/test_download_plan_runner.py::test_runner_reports_progress_callback_errors_without_failing_download`，驗證 UI/progress callback 壞掉時下載仍完成，且 JSON result 可看到 callback error。
- 已驗證：`PYTHONDONTWRITEBYTECODE=1 py -3 -B -m py_compile api_launcher\downloads\plan_runner.py tests\test_download_plan_runner.py` OK；`py -3 -B -m unittest tests.test_download_plan_runner tests.test_download_jobs -v` 15 tests OK。
- 已推送 `aaeb8a2 Surface download callback diagnostics in plan results`；GitHub Actions run `26599799798` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪改 agent-readable download plan result payload，多出 diagnostics 欄位但不改使用者操作流程；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 04:00 Crawler registry handler signature guard
- 本輪補上 `api_launcher/crawlers/registry.py` 的 handler signature fail-fast：`@crawler(...)` 註冊時會用共用六參數 signature `(source, timeout, limit, search_terms, full_crawl, max_pages)` 檢查 handler。
- 這補齊宣告式 registry 任務單裡「handler 簽章不符要在 import/registration 階段報錯」的 contract，避免未來新增 crawler 時到 UI 或下載流程才出錯。
- 新增 `tests/test_dataset_discovery.py::test_crawler_registry_rejects_handler_signature_mismatch`，確認錯誤 handler 會被 registry 拒絕；既有 14 個 handler 行為不變。
- 已驗證：`PYTHONDONTWRITEBYTECODE=1 py -3 -B -m py_compile api_launcher\crawlers\registry.py tests\test_dataset_discovery.py` OK；`py -3 -B -m unittest tests.test_dataset_discovery -v` 57 tests OK；`api_launcher/crawlers` mojibake scan OK。
- 已推送 `fb03440 Guard crawler registry handler signatures`；GitHub Actions run `26599208635` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只硬化 crawler registry contract，不改使用者操作流程；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 03:45 Download queue callback isolation
- 本輪把 `api_launcher/downloads/jobs.py` 的 progress callback 從下載 worker 狀態中隔離：callback 例外會記錄成 `DownloadCallbackError`，但不會把實際下載 job 標記為 `failed`。
- `NonBlockingDownloadQueue.add_callback()` 現在在 lock 內註冊 callback，`_publish()` 會先 snapshot callback list 再逐一呼叫，避免 callback list 在 publish 期間被修改。
- 新增 `callback_error_snapshot()`，讓 UI/agent/test 可讀取 callback 失敗紀錄；這是 observer/UI diagnostics，不改 downloader、HTTP adapter、manifest 或 import 行為。
- 已驗證：`PYTHONDONTWRITEBYTECODE=1 py -3 -B -m py_compile api_launcher\downloads\jobs.py tests\test_download_jobs.py` OK；`py -3 -B -m unittest tests.test_download_jobs -v` 3 tests OK；`py -3 -B -m unittest tests.test_http_downloader tests.test_download_plan_runner tests.test_download_jobs -v` 22 tests OK；`git diff --check` OK；`api_launcher/downloads` mojibake scan OK。
- 已推送 `fb8e0d6 Isolate download progress callback failures`；GitHub Actions run `26598592970` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪改下載 queue 的 observer/callback hardening，不改使用者操作流程；已同步 GTD、handoff 與 development log，user guide 不需更新。

## 2026-05-29 03:26 Crawler decorators own registry metadata
- 本輪把 14 個 crawler 的 `@crawler(...)` 註冊移到各自 handler 模組附近；`dataset_sources.py` 不再持有中心宣告式 mapping，只保留匯入觸發、相容常數與 matrix/query facade。
- ERDDAP 與 HTML file index 因 handler signature 與共用六參數 crawler signature 不同，已在各自模組新增薄 wrapper：`erddap_source_crawler()` 與 `html_file_index_source_crawler()`；正式抓取/解析邏輯仍留在原有 `erddap_candidates_for_source()` / `html_file_index_candidates_for_source()`。
- 這不改 14 個 source type、capability bits、crawler output、download/import 或 UI payload；只是把 source_type metadata ownership 從中心檔移到 handler 檔，讓新增 crawler 更接近「加 handler + 裝飾器」的準宣告式流程。
- 已驗證：crawler 模組與 `tests/test_dataset_discovery.py` py_compile OK；`py -3 -B -m unittest tests.test_dataset_discovery tests.test_crawler_assets tests.test_web_preview -v` 149 tests OK；`py -3 -B -m unittest tests.test_crawler_audit_smoke tests.test_developer_diagnostics tests.test_source_patterns tests.test_discovery_drafts -v` 51 tests OK；`api_launcher/crawlers` mojibake scan OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，893 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_032740.log`。
- 已推送 `54a8538 Move crawler registry metadata to handlers`；GitHub Actions run `26597565703` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪改 crawler registry ownership 與 source metadata contract；已同步 GTD、handoff 與 development log，不改使用者操作文件。

## 2026-05-29 03:05 Tk crawler asset thread mock cleanup
- 本輪完成 Tk scheduler guard consolidation 的小尾巴：`frontends/tk/crawler_asset_workflows.py` 移除已不再使用的 `threading` import，測試也改 patch 真正的共用背景工作入口 `frontends.tk.background_jobs.threading.Thread`。
- 這不改 crawler asset listing、source pattern draft、seed schema probe、seed download/import、download plan build 或 credential guard 行為；只讓產品碼與測試都指向同一個 single-flight helper 邊界，避免舊 UI workflow 模組被誤認為 thread owner。
- 已驗證：`py -3 -B -m py_compile frontends\tk\crawler_asset_workflows.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_background_jobs tests.test_tk_dialogs -v` 101 tests OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，893 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_030649.log`。
- 已推送 `5adecdc Clean crawler asset thread mock boundary`；GitHub Actions run `26596461917` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只修正 Tk crawler asset workflow 的測試邊界與 unused import；已同步 GTD、handoff 與 development log，不改使用者操作文件。

## 2026-05-29 02:52 Tk Developer CLI single-flight guard
- 本輪完成 Tk raw thread consolidation 的最後一個產品 UI 入口：`DeveloperCliDialog.run_command()` 不再直接建立裸 `threading.Thread`，改走 `frontends.tk.background_jobs.start_single_flight_thread()`。
- Developer CLI 使用 `("developer_cli", "command", "")` job key；同一 dialog 仍有 CLI command 執行中時，Tk 不再清空輸出或開第二個 subprocess worker。
- 這不改 command parsing、working directory、subprocess timeout、stdout/stderr capture 或 status/output 顯示語意；只把 developer-only CLI runner 的背景 thread 收斂到共用 helper。
- 已驗證：`py -3 -B -m py_compile frontends\tk\dialogs.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_background_jobs tests.test_tk_dialogs -v` 101 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，893 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_025254.log`。
- 已推送 `dbdb0d4 Guard Tk developer CLI background job`；GitHub Actions run `26595758705` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只收斂 Tk developer CLI dialog 的背景 job guard；已同步 GTD、handoff 與 development log。

## 2026-05-29 02:37 Tk sidebar favicon single-flight guard
- 本輪繼續 Tk scheduler guard consolidation：`SidebarWorkflowMixin.fetch_provider_icon_async()` 不再直接建立裸 `threading.Thread`，改走 `frontends.tk.background_jobs.start_single_flight_thread()`。
- Provider favicon fetch 使用 `("provider_favicon", owner, favicon_url)` job key；同一 provider/favicon 下載已在執行時，Tk 不再開第二個 worker。
- 這不改 favicon URL 推導、cache path、PNG 下載、`PhotoImage` 建立或 sidebar provider filter 顯示語意；只把 favicon 下載入口的背景 thread 收斂到共用 helper。
- 已驗證：`py -3 -B -m py_compile frontends\tk\sidebar_workflows.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_background_jobs tests.test_tk_dialogs -v` 99 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，891 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_023718.log`。
- 已推送 `e586cf3 Guard Tk sidebar favicon background job`；GitHub Actions run `26594978569` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只收斂 Tk sidebar favicon 入口的背景 job guard；已同步 GTD、handoff 與 development log。

## 2026-05-29 02:26 Tk OAuth login single-flight guard
- 本輪繼續 Tk scheduler guard consolidation：`OAuthWorkflowMixin` 新增 `_start_oauth_background_job()`，把 OAuth/login 對話中的背景 worker 收斂到 `frontends.tk.background_jobs.start_single_flight_thread()`。
- Google browser login 使用 `("oauth_browser_login", profile_id, "")` job key；同一 profile 登入流程已在執行時，Tk 不再開第二個 callback server / browser login worker。
- Device-code polling 使用 `("oauth_device_poll", profile_id, device_code)` job key；使用者重複按「重新檢查登入」時只更新狀態，不再重疊發出 token polling request。
- 這不改 OAuth authorization URL、PKCE、callback server、device-code polling、token exchange、token 保存或本機 credential storage；只把登入入口的背景 thread 收斂到共用 helper。
- 已驗證：`py -3 -B -m py_compile frontends\tk\oauth_workflows.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_background_jobs tests.test_oauth_device tests.test_tk_dialogs -v` 107 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，889 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_022611.log`。
- 已推送 `0278a93 Guard Tk OAuth login background jobs`；GitHub Actions run `26594347795` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只收斂 Tk OAuth/login 入口的背景 job guard；已同步 GTD、handoff 與 development log。

## 2026-05-29 02:11 Tk showcase download single-flight guard
- 本輪繼續 Tk scheduler guard consolidation：`ShowcaseWorkflowMixin.run_showcase_download_from_ui()` 保留既有 `showcase_download_running` 使用者提示，同時把 bounded showcase download worker 改走 `frontends.tk.background_jobs.start_single_flight_thread()`。
- Showcase download 使用 `("showcase_download", "bounded_public", "")` job key；同一展示下載工作已在執行時，Tk 不再開第二個 worker，避免展示連點造成重複公開資料下載、manifest 寫入與展示 `.db` 匯入。
- 這不改 showcase download 的有界 demo source、sample limit、progress dialog、download/import service 或 resumable showcase download queue；只把 bounded showcase 入口的背景 thread 收斂到共用 helper。
- 已驗證：`py -3 -B -m py_compile frontends\tk\showcase_workflows.py tests\test_tk_dialogs.py` OK；targeted 2 tests OK；`py -3 -B -m unittest tests.test_tk_background_jobs tests.test_tk_dialogs tests.test_showcase_workflows -v` 99 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，887 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_021213.log`。
- 已推送 `d972c7c Guard Tk showcase download job`；GitHub Actions run `26593575008` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只收斂 Tk showcase bounded download 入口的背景 job guard；已同步 GTD、handoff 與 development log。

## 2026-05-29 01:58 Tk import SQLite single-flight gate
- 本輪繼續 Tk scheduler guard consolidation：`ImportWorkflowMixin.import_supported_plan_results_from_ui()` 與 `import_local_file_from_ui()` 不再直接建立裸 `threading.Thread`，改走 `frontends.tk.background_jobs.start_single_flight_thread()`。
- 兩條匯入入口共用 `("sqlite_import", sqlite_path, "")` job key；同一 curated SQLite 正在匯入時，Tk 只更新 status，不再開啟第二個匯入 worker，也不會在本機檔案匯入時先彈出檔案選擇器。
- 這不改 importer、manifest、existing-table policy、local file provenance review 或 ingestion pipeline 規則；只在 Tk 入口加一層同 SQLite path 的背景工作 gate，降低連點造成的 DB lock / 重複匯入風險。
- 已驗證：`py -3 -B -m py_compile frontends\tk\import_workflows.py tests\test_tk_dialogs.py` OK；targeted 4 tests OK；`py -3 -B -m unittest tests.test_tk_background_jobs tests.test_tk_dialogs tests.test_launcher_ui -v` 125 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，885 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_015909.log`。
- 已推送 `24f1a1a Guard Tk import SQLite jobs`；GitHub Actions run `26592898718` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只收斂 Tk 匯入入口的背景 job / SQLite write gate；已同步 GTD、handoff 與 development log。

## 2026-05-29 01:44 Tk AI summary single-flight guard
- 本輪繼續 Tk scheduler guard consolidation：`AiSummaryWorkflowMixin.generate_active_summary()` 不再直接建立裸 `threading.Thread`，改走 `frontends.tk.background_jobs.start_single_flight_thread()`。
- AI 摘要的 job key 使用 provider id 與 AI profile id，例如 `("ai_summary", "provider_a", "local_ollama")`；同一 provider/profile 的摘要工作已在執行時，Tk 只更新 status，不再重複開 worker。
- 這不改 AI 摘要 profile 選擇、credential 檢查、summary 生成、repository upsert 或 detail panel 顯示語意；只把產生說明入口的背景工作排程收斂到共用 single-flight helper。
- 已驗證：`py -3 -B -m py_compile frontends\tk\ai_summary_workflows.py tests\test_tk_dialogs.py` OK；targeted 2 tests OK；`py -3 -B -m unittest tests.test_tk_background_jobs tests.test_tk_dialogs -v` 89 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，881 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_014547.log`。
- 已推送 `32bf476 Guard Tk AI summary background job`；GitHub Actions run `26592201477` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只收斂 Tk AI summary 內部背景 job guard；已同步 GTD、handoff 與 development log。

## 2026-05-29 01:33 Tk source action metadata crawl single-flight guard
- 本輪繼續 Tk scheduler guard consolidation：`SourceActionWorkflowMixin.crawl_provider_ids()` 不再直接建立裸 `threading.Thread`，改走 `frontends.tk.background_jobs.start_single_flight_thread()`。
- Metadata crawl 的 job key 以排序後 provider scope 建立，例如 `("metadata_crawl", "provider_a,provider_b", "")`；同一批 provider metadata crawl 已在執行時，Tk 只更新 status，不再重複開 worker。
- 這不改 provider metadata crawler、repair/self-check、row action、repository update 或 UI menu 語意；只把 row action 入口的背景工作排程收斂到共用 single-flight helper。
- 已驗證：`py -3 -B -m py_compile frontends\tk\source_action_workflows.py tests\test_tk_dialogs.py` OK；targeted 2 tests OK；`py -3 -B -m unittest tests.test_tk_background_jobs tests.test_tk_dialogs -v` 87 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，879 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_012947.log`。
- 已推送 `1dac898 Guard Tk metadata crawl background job`；GitHub Actions run `26591378222` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只收斂 Tk source action metadata crawl 內部背景 job guard；已同步 GTD、handoff 與 development log。

## 2026-05-29 01:20 Tk discovery workflow single-flight guard
- 本輪繼續 bounded scheduler consolidation：`DiscoveryWorkflowMixin` 的 provider candidate discovery、dataset candidate discovery 與 local discovery dry-run audit 不再直接建立裸 `threading.Thread`，改走 `frontends.tk.background_jobs.start_single_flight_thread()`。
- 新增 discovery 專用 active job set / lock。Provider discovery 用 `("provider_discovery", "all", "")`，dataset candidate discovery 用選取 provider scope，local discovery audit 用 `("local_discovery_audit", "dry_run", "")`；同一邏輯任務重複觸發時只更新 status，不再重複開 worker。
- 這不改 provider discovery、dataset crawler audit、local promotion dry-run、repository upsert 或 dialog 顯示語意；只是先把 Tk discovery 入口的背景工作排程收斂到共用 single-flight helper。
- 已驗證：`py -3 -B -m py_compile frontends\tk\discovery_workflows.py tests\test_tk_dialogs.py` OK；targeted 3 tests OK；`py -3 -B -m unittest tests.test_tk_background_jobs tests.test_tk_dialogs -v` 85 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，877 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_011717.log`。
- 已推送 `e183ae0 Guard Tk discovery background jobs`；GitHub Actions run `26590713282` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只收斂 Tk discovery 內部背景 job guard；已同步 GTD、handoff 與 development log。

## 2026-05-29 01:00 Web Preview POST body drain hardening
- 本輪回應 docs-only checkpoint `505ecbf` 的 GitHub Actions Windows failure：`tests.test_web_preview.WebPreviewApiTest.test_real_download_demo_route_is_developer_diagnostic_only` 看到 developer diagnostic POST 被測試 retry helper 重送，導致 `developer_real_download_demo()` mock 被呼叫兩次。
- 根因是 local Web Preview server 對不需要 request body 的 POST（developer diagnostic 與 unknown endpoint）會直接回短 JSON，沒有先 drain `Content-Length` body；Windows localhost runner 偶爾會 abort 這種短連線，測試 helper 因重試而重跑有副作用 endpoint。
- `frontends/web/server.py` 新增 `discard_request_body()`，developer diagnostic 與 unknown POST route 會先讀掉 unused body 再回 JSON；`tests/test_web_preview.py` 的 `post_json_to_preview_server()` 改成預設不重試 POST，只有 legacy 404 route 顯式 opt-in retry，避免重複執行真 workflow / diagnostics。
- 已驗證：`py -3 -B -m py_compile frontends\web\server.py tests\test_web_preview.py` OK；targeted route tests OK；`py -3 -B -m unittest tests.test_web_preview -v` 48 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，874 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_010020.log`。
- 已推送 `8883f1f Harden Web preview POST body drain`；GitHub Actions run `26589864084` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪是 Web Preview local server / test hardening，不改使用者主操作流程；已同步 GTD、handoff 與 development log。

## 2026-05-29 00:44 Tk MVP demo smoke single-flight guard
- 本輪繼續做 Tk scheduler guard 小切片：`MvpDemoWorkflowMixin.run_mvp_demo_smoke_from_ui()` 不再直接建立裸 `threading.Thread`，改走 `frontends.tk.background_jobs.start_single_flight_thread()`。
- 這保留既有 `mvp_demo_smoke_running` 使用者提示，同時讓 canonical MVP demo smoke 也使用統一 single-flight active job set / lock / release 機制；避免展示或驗收時連點造成重複 demo DB / flow artifacts / event log 寫入。MVP demo smoke 的下載、匯入與 closure 判斷本身沒有改。
- 已驗證：`py -3 -B -m py_compile frontends\tk\mvp_demo_workflows.py tests\test_launcher_ui.py` OK；`py -3 -B -m unittest tests.test_launcher_ui -v` 32 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，874 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_004114.log`。
- 已推送 `320abad Guard MVP demo smoke background job`；GitHub Actions run `26588777239` 已通過 Ubuntu、Windows 與 real DB smoke。後續 docs-only checkpoint `a6f776e` 的 run `26588937925` 也已通過。
- Docs drift check：本輪只收斂 Tk MVP demo smoke 內部背景 job guard；已同步 GTD、handoff 與 development log。

## 2026-05-29 00:33 Tk plan bounds probe single-flight guard
- 本輪繼續做 Tk scheduler guard 小切片：`PlanWorkflowMixin.configure_selected_plan_bounds_from_ui()` 的下載計畫界域欄位探測不再直接建立裸 `threading.Thread`，改走 `frontends.tk.background_jobs.start_single_flight_thread()`。
- 這讓同一個 plan item 的 schema/bounds probe 同時只能跑一個，避免連點造成多個欄位探測、重複界域 dialog 或 `download_plan_entries_by_provider` 競爭。Tk 仍只負責選取 plan item、排背景 worker 與顯示界域表單；欄位探測與 bounds 套用規則不移進 UI。
- 已驗證：`py -3 -B -m py_compile frontends\tk\plan_workflows.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 79 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，872 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_002957.log`。
- 已推送 `8cfa0ae Guard plan bounds probe background job`；GitHub Actions run `26588169356` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只收斂 Tk plan bounds probe 內部背景 job guard；已同步 GTD、handoff 與 development log。

## 2026-05-29 00:16 Tk source pattern draft single-flight guard
- 本輪做 Tk scheduler guard 小切片：`open_source_pattern_draft_dialog()` 不再直接建立裸 `threading.Thread`，改走既有 `_start_crawler_asset_background_job()` / `frontends.tk.background_jobs` single-flight helper。
- 這讓同一個 source URL 的 detector / local source draft worker 只能同時跑一個，避免連點造成重複寫入 local discovery source draft、重複 dialog/status 更新或後續 SQLite / event log 競爭。Tk 仍只負責收 URL、排背景 worker 與顯示結果；STAC/CKAN/ERDDAP 等 detector 規則仍在後端 source-pattern service。
- 已驗證：`py -3 -B -m py_compile frontends\tk\crawler_asset_workflows.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 77 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，870 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260529_001201.log`。
- 已推送 `a8ba8cb Guard source draft background job`；GitHub Actions run `26587355365` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只收斂 Tk source-pattern draft 內部背景 job guard；已同步 GTD、handoff 與 development log。

## 2026-05-28 23:37 Tk seed download/import target path helper
- 本輪做 Tk 對應 bounded consolidation：新增 `frontends.tk.ui_helpers.CrawlerSeedDownloadImportTargetPaths` 與 `crawler_seed_download_import_target_paths()`，把 seed download/import worker 的 downloads root、curated SQLite 與 resolved plan path 組裝從 `crawler_asset_workflows.py` 抽出。
- 這不改 Tk 操作流程、正式 seed download/import service 或事件 payload；Tk workflow 仍只負責 thread wrapper、repository handoff、status 與 dialog，路徑 sanitize / target layout 改由 helper 測試鎖住。
- 已驗證：`py -3 -B -m py_compile frontends\tk\ui_helpers.py frontends\tk\crawler_asset_workflows.py tests\test_tk_ui_helpers.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_ui_helpers tests.test_tk_dialogs -v` 82 tests OK；docs mojibake scan OK；時間佔位掃描無結果；`git diff --check` OK（僅既有 CRLF/LF warning）；`.\scripts\pre_push_smoke_brief.cmd` 通過，868 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_233856.log`。
- 已推送 `54c2dbd Extract Tk seed target path helper`；GitHub Actions run `26585404548` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只收斂 Tk seed worker 內部 path helper；已同步 GTD、handoff 與 development log。

## 2026-05-28 23:17 Web repository bootstrap helper
- 本輪繼續做 Web Preview bounded consolidation：新增 `frontends.web.preview_api.WebPreviewRepositorySession` 與 `web_preview_repository_context()`，集中 Web endpoint 重複的 SQLite connection、`ApiCatalogRepository`、schema init 與 optional builtin provider bootstrap。
- 這不改 Web API response、crawler/listing/plan/download/import service 或交易邊界；endpoint 仍明確決定何時 `commit()`，helper 只負責開 session 與初始化 repository。
- 已驗證：`py -3 -B -m py_compile frontends\web\preview_api.py tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 48 tests OK；docs mojibake scan OK；時間佔位掃描無結果；`git diff --check` OK（僅既有 CRLF/LF warning）；`.\scripts\pre_push_smoke_brief.cmd` 通過，867 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_231815.log`。
- 已推送 `71d498c Extract Web repository bootstrap helper`；GitHub Actions run `26584181347` 已通過 Ubuntu、Windows 與 real DB smoke。後續 docs-only checkpoint `851ea44` 的 run `26584356568` 也已通過。
- Docs drift check：本輪只收斂 Web endpoint 內部 repository bootstrap；已同步 GTD、handoff 與 development log。

## 2026-05-28 23:02 Web download/import target path helper
- 本輪繼續做 Web Preview bounded consolidation：新增 `frontends.web.preview_api.WebDownloadImportTargetPaths` 與 `web_download_import_target_paths()`，asset-level 與 seed-level download/import endpoint 共用 DB、downloads root、curated SQLite 與 resolved plan path 組裝。
- 這不改 Web API response、正式下載/匯入 service、目錄語意或使用者操作流程；seed-level run 仍只在預設 Web downloads root 下自動加 seed 子目錄，測試/呼叫端傳入 `downloads_root` 時保留精確路徑控制。
- 已驗證：`py -3 -B -m py_compile frontends\web\preview_api.py tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 48 tests OK；docs mojibake scan OK；時間佔位掃描無結果；`git diff --check` OK（僅既有 CRLF/LF warning）；`.\scripts\pre_push_smoke_brief.cmd` 通過，867 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_230350.log`。
- 已推送 `266dbcd Extract Web download import target path helper`；GitHub Actions run `26583382254` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪只收斂 Web endpoint 內部 target path helper；已同步 GTD、handoff 與 development log。

## 2026-05-28 22:47 Web download/import event context helper
- 本輪繼續做 Web Preview bounded consolidation：新增 `frontends.web.preview_api.web_download_import_event_context()`，asset-level 與 seed-level download/import 完成事件共用同一份 event context builder。
- 這不改 Web API response、正式下載/匯入 service 或 event 欄位；只是移除兩段重複的 stage、success、download_import、artifacts event context 組裝，讓 endpoint 更薄。
- 已驗證：`py -3 -B -m py_compile frontends\web\preview_api.py tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 46 tests OK；docs/Web mojibake scan OK；時間佔位掃描無結果；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，865 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_224847.log`。
- 已推送 `b8e32ed Extract Web download import event context helper`；GitHub Actions run `26582485477` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪不改使用者操作流程，只收斂 Web endpoint 內部 event payload helper；已同步 GTD、handoff 與 development log。

## 2026-05-28 22:34 Web download/import credential block helper
- 本輪做 Web Preview bounded consolidation：新增 `frontends.web.preview_api.web_download_import_credential_blocked_response()`，asset-level 與 seed-level download/import endpoint 遇到缺憑證時共用同一份 blocked payload。
- 這不改 credential guard、正式下載/匯入 service 或 response shape；只是移除兩段重複的 `blocked_before_download` / `edit_local_credentials_before_live_download` 組裝，避免 Web endpoint 後續分叉。
- 已驗證：`py -3 -B -m py_compile frontends\web\preview_api.py tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 46 tests OK，新增 asset/seed download-import 缺憑證時不呼叫正式 service 的 regression；docs/Web mojibake scan OK；時間佔位掃描無結果；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，865 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_223514.log`。
- 已推送 `ab9cf83 Extract Web download import credential block helper`；GitHub Actions run `26581728210` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪不改使用者操作流程，只收斂 Web endpoint 內部重複 blocked payload；已同步 GTD、handoff 與 development log。

## 2026-05-28 22:19 Tk seed download/import UI message helper
- 本輪繼續做 bounded consolidation：新增 `frontends.tk.ui_helpers.crawler_seed_download_import_ui_message()` 與 `CrawlerSeedDownloadImportUiMessage`，把 Tk seed download/import completion message 的 stage、success、artifact 與 next-action label 組裝從 `crawler_asset_workflows.py` 抽出。
- `CrawlerAssetWorkflowMixin._finish_crawler_asset_seed_download_import()` 現在只呼叫 helper、設定 status，然後依 `succeeded` 選擇 info/warning dialog；workflow adapter 不再直接重組 backend display payload。
- 已驗證：`py -3 -B -m py_compile frontends\tk\ui_helpers.py frontends\tk\crawler_asset_workflows.py tests\test_tk_ui_helpers.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_ui_helpers tests.test_tk_dialogs -v` 81 tests OK；`py -3 -B -m unittest tests.test_launcher_ui tests.test_tk_ui_helpers tests.test_tk_dialogs -v` 111 tests OK；docs/Tk mojibake scan OK；時間佔位掃描無結果；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，863 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_222110.log`。
- 已推送 `8876439 Extract Tk seed download import message helper`；GitHub Actions run `26580910210` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪不改使用者操作流程，只把 Tk message 組裝收斂到 helper，讓 `crawler_asset_workflows.py` 少吸收顯示細節；已同步 GTD、handoff 與 development log。

## 2026-05-28 22:02 Tk download/import display payload alignment
- 本輪把 Tk seed download/import 完成訊息也接到 `api_launcher.crawler_asset_display.crawler_asset_download_import_display_payload()`。Tk 不再直接從 raw `result.to_dict()` 自行重組 stage、success 與 next-action label，而是讀同一份 backend display payload。
- `crawler_asset_download_import_display_payload()` 同步補上無 `pipeline` 物件時的 fallback：若 helper 收到 legacy / test result dict，會從 `download_result.stage`、`succeeded`、`next_action` 補回 `download_import` 摘要，避免 UI 測試假物件崩掉。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawler_asset_display.py frontends\tk\crawler_asset_workflows.py tests\test_tk_dialogs.py tests\test_crawler_asset_download.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs tests.test_crawler_asset_download tests.test_web_preview -v` 123 tests OK；docs mojibake scan OK；時間佔位掃描無結果；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，862 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_220333.log`。
- 已推送 `ea3186a Align Tk download import display payload`；GitHub Actions run `26579978458` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪不改使用者操作流程，只把 Tk 顯示層改成消費共用 payload；已同步 GTD、handoff 與 development log。

## 2026-05-28 21:48 Download/import display payload consolidation
- 本輪做小型 consolidation：新增 `api_launcher.crawler_asset_display.crawler_asset_download_import_display_payload()`，集中包裝 formal asset-level / seed-level download-import run 的 `download_result`、`plan_result`、`plan_outcome`、`plan_passport`、`adapter_review`、`download_import` 與 `next_action_label`。
- `frontends/web/preview_api.py` 的 `crawler_asset_download_import()` / `crawler_seed_download_import()` 改用這個後端 display helper，Web endpoint 只保留 endpoint-specific input、destination、profile passport update 與 event logging。這不改 crawler、plan、download、import 或 response shape。
- 已驗證：`py -3 -B -m py_compile api_launcher\crawler_asset_display.py frontends\web\preview_api.py tests\test_crawler_asset_download.py tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_crawler_asset_download tests.test_web_preview -v` 48 tests OK；docs mojibake scan OK；時間佔位掃描無結果；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，862 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_214932.log`。
- 已推送 `3e3d7af Consolidate download import display payload`；GitHub Actions run `26579114791` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪改的是 Web endpoint / backend display contract 邊界，已同步 GTD、handoff 與 development log；使用者操作流程與主要按鈕沒有改。

## 2026-05-28 21:29 Tk project maturity matrix
- 本輪把既有 `api_launcher.project_maturity` 後端成熟度矩陣接回 Tk 控制台：新增 `frontends/tk/project_maturity_workflows.py`，由 `project_maturity_payload()` 開 DB / repository 並回傳 `build_project_maturity_payload()`；Tk 不重新判斷成熟度、不計算單一專案百分比。
- Tk 工具選單新增「專案成熟度矩陣」，顯示 canonical delivery scope、各成熟度 row、`🚧` 施工中 / 規劃中圖示、限制數與後端回答口徑。這是 Web 成熟度工作區的 Tk 對應入口，不改 crawler、download、import 或 maturity 判斷。
- 已驗證：`py -3 -B -m py_compile frontends\tk\project_maturity_workflows.py frontends\tk\launcher_ui.py frontends\tk\window_layout_workflows.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs tests.test_launcher_ui tests.test_project_maturity -v` 109 tests OK；實跑 temp DB payload 確認 renderer / Qt rows 帶 `status_icon=🚧` 且 Tk message 含施工中圖示；docs mojibake scan OK；時間佔位掃描無結果；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，861 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_213112.log`。
- 已推送 `e19d8e3 Add Tk project maturity matrix action`；GitHub Actions run `26578190695` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：本輪改了 Tk 操作入口，已同步 GTD、handoff 與 development log；未改使用者正式手冊，因為此入口是治理 / diagnostics 類工具，不改主要資料下載操作流程。

## 2026-05-28 20:47 Web project maturity workspace
- 本輪把既有 `api_launcher.project_maturity` 後端成熟度矩陣接到 Web Preview：新增 `GET /api/project-maturity`，由 `frontends/web/preview_api.py::web_project_maturity()` 只負責開 DB / repository 並回傳 `build_project_maturity_payload()`，Web 不重新判斷成熟度。
- Web Preview 新增「成熟度」工作區與 `maturityGrid` 卡片牆，顯示 canonical delivery scope、各成熟度 row、`🚧` 施工中圖示、display tone、限制與下一步。這是 UI contract 顯示層，不改 crawler、download、import 或 maturity 判斷。
- 已驗證：`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest tests.test_web_preview tests.test_project_maturity -v` 48 tests OK；docs mojibake scan OK；時間佔位掃描無結果；`.\scripts\pre_push_smoke_brief.cmd` 通過，859 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_204151.log`。
- 已推送 `6e51329 Add Web project maturity workspace`；GitHub Actions run `26575702230` 已通過 Ubuntu、Windows 與 real DB smoke。
- Docs drift check：已同步 GTD、Web Preview UIUX 文件與 development log，並以本段回填 commit / CI 狀態。

## 2026-05-28 19:42 Project maturity construction display profile
- 本輪做小型 UI-neutral contract 修補：`api_launcher/project_maturity.py` 的 `MaturityMatrixRow.to_dict()` 現在輸出 `status_icon`、`display_tone`、`display_label` 與 `display_profile`。
- `contract_only` 與 `planned_not_started` 會輸出 `🚧`，讓 Tk/Web/未來 Qt 可以直接顯示施工中/規劃中狀態，不需要 UI 自行判斷 renderer/simulation/Qt 是否已完成。
- Markdown renderer 也會用 `maturity_level` fallback 補上 icon，保留舊 payload 相容性。這不改 maturity row 判斷、不改 crawler/download/import，只補顯示 contract。
- 已驗證：`py -3 -B -m py_compile api_launcher\project_maturity.py tests\test_project_maturity.py` OK；`py -3 -B -m unittest tests.test_project_maturity -v` 4 tests OK；`py -3 -B -m unittest tests.test_project_maturity tests.test_handoff -v` 25 tests OK；CLI write/read smoke 確認 renderer/simulation row 輸出 `status_icon=\U0001f6a7`、`display_tone=review`；`.\scripts\pre_push_smoke_brief.cmd` 通過，857 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_194439.log`。
- 已推送 `ce6bac3 Add maturity construction display profile`；GitHub Actions run `26572843583` 已通過 Ubuntu、Windows 與 real DB smoke。

## 2026-05-28 19:31 Web base bounds form delegation
- 本輪延續 schema probe service consolidation：`frontends/web/preview_api.py::crawler_asset_bound_form()` 現在直接委託 `api_launcher.crawler_asset_schema_probe.crawler_asset_bound_form_spec()`，Web 不再自己讀 `BUILD_DOWNLOAD_PLAN` capability、載入 source、組 base form spec。
- 這不改 Web route、payload shape、bounds form 欄位或 schema probe 行為；只是把 base bounds form 組裝邏輯一併收回 backend service module，讓 Web Preview 繼續保持薄 adapter。
- 已驗證：`py -3 -B -m py_compile frontends\web\preview_api.py api_launcher\crawler_asset_schema_probe.py` OK；focused Web bounds/schema tests OK；`py -3 -B -m unittest tests.test_web_preview tests.test_crawler_assets -v` 87 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，856 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_192824.log`。
- 已推送 `7d63f1c Delegate Web bounds form to backend service`；GitHub Actions run `26572118977` 已通過 Ubuntu、Windows 與 real DB smoke。

## 2026-05-28 19:18 Schema probe service consolidation
- 本輪做 bounded consolidation：新增 `api_launcher/crawler_asset_schema_probe.py`，把 seed/resource URL 正規化、schema probe、bounds form spec 建立、probe enrichment、`next_action_label` payload 打包成 UI-neutral backend service。這讓 Web Preview / Tk / 未來 Qt 都能吃同一份 schema-probe contract。
- `frontends/web/preview_api.py` 仍重新匯出 `crawler_asset_bound_form_schema_probe()`，所以現有 server route 與測試 import 不需要改；但 Web 不再保存 probe runner、timeout/row-limit bounded parsing、entry normalization、form enrichment 這些後端邏輯。
- `frontends/tk/crawler_asset_workflows.py` 的 seed schema probe worker 改呼叫 `crawler_asset_bound_form_schema_probe_result()`，只負責開 Tk dialog 與保存 bounds payload；欄位推論與 form enrichment 不再散在 Tk worker 內。
- 已推送 `fd43435 Extract crawler asset schema probe service`；GitHub Actions run `26571568872` 已通過 Ubuntu、Windows 與 real DB smoke。先前本地驗證：`py -3 -B -m py_compile api_launcher\crawler_asset_schema_probe.py frontends\web\preview_api.py frontends\tk\crawler_asset_workflows.py tests\test_tk_dialogs.py tests\test_web_preview.py` OK；focused schema probe tests OK；`py -3 -B -m unittest tests.test_tk_dialogs tests.test_web_preview tests.test_crawler_assets -v` 160 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，856 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_191340.log`。

## 2026-05-28 18:54 Log timestamp correction
- 本輪修正文檔治理漂移：`docs/DEVELOPMENT_LOG.zh-TW.md` 與本 handoff 先前把尚未完成的 checkpoint 寫成「小時精確、分鐘佔位」格式，後續 commit / CI 完成後沒有回填實際分鐘。這不是 GitHub 或系統自動改寫，而是 agent 在 checkpoint 尚未收束時留下佔位值。
- 已將近期 checkpoint 時間改為可追溯的實際本地時間：18:42、18:29、18:07、17:52、17:40、17:25、17:06、16:51、16:09。後續正式 log 不應再提交分鐘佔位；若 checkpoint 尚未完成，應先不寫正式 log，或寫明 `pending` 並在 commit 前回填精確 `HH:mm`。
- 已推送 `55f357e Fix exact checkpoint times in docs`；GitHub Actions run `26570514520` 已通過 Ubuntu、Windows 與 real DB smoke。先前本地驗證：時間佔位掃描無結果；`git diff --check` OK；docs mojibake scan OK。

## 2026-05-28 18:42 Tk background job helper extraction
- 本輪做小型 consolidation：新增 `frontends/tk/background_jobs.py`，把 single-flight active job set、lock、duplicate guard、release 的共通邏輯從 `crawler_asset_workflows.py` 抽出。`CrawlerAssetWorkflowMixin` 仍保留 crawler asset 專用薄包裝與 UI 狀態文案，但不再直接維護 active job set 細節。
- 這不改 crawler/listing/plan/download/import 行為，也不把 Tk 全面改成 async；只是先建立可測 helper，讓後續其他 Tk workflow 若需要 bounded scheduler / single-flight guard 時，不必再複製 thread/lock 模式。
- 已驗證：`py -3 -B -m py_compile frontends\tk\background_jobs.py frontends\tk\crawler_asset_workflows.py tests\test_tk_background_jobs.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_background_jobs -v` 3 tests OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 73 tests OK；`py -3 -B -m unittest tests.test_tk_background_jobs tests.test_tk_dialogs tests.test_web_preview -v` 118 tests OK；`git diff --check` OK（僅 CRLF/LF warning）；docs/frontends/tk/tests mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，856 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_183726.log`; pushed `f8c0aed Extract Tk background job helper`; GitHub Actions run `26569870367` passed Ubuntu, Windows, and real DB smoke.

## 2026-05-28 18:29 Tk crawler asset job guard expansion
- 本輪延伸上一個 single-flight guard：`run_selected_crawler_asset_listing()` 與 `prepare_selected_crawler_asset_download()` 也改用 `_start_crawler_asset_background_job()`。同一 crawler asset 的清單擷取或下載計畫建立正在執行時，Tk 不再開第二個 worker；下載計畫會在打開 bounds dialog 前先檢查 active job，避免連點時重複彈表單。
- 仍然沒有改後端 crawler/listing/plan/download/import 語意，也沒有引入全面 async；這只是 Tk control panel 的 bounded job guard，先降低 repeated-click 對 repository、plan 檔案與使用者對話框狀態的競爭。
- 本地 pre-push 第一次暴露兩個環境韌性缺口，已一併修補：`event_log.latest_events()` 在雲端碟 binary seek/read 被拒時會退回 bounded streaming tail；Web Preview port scan 遇到 Windows 保留或安全阻擋整段候選 port 時，會退回 OS-assigned local port，而不是讓本地 smoke 直接失敗。這些修補只影響 handoff/report 與 local preview startup resilience，不改資料下載或匯入語意。
- 已推送 `c075581 Harden crawler asset job guards`；GitHub Actions run `26569271791` 已通過 Ubuntu、Windows 與 real DB smoke。先前本地驗證：`py -3 -B -m py_compile frontends\tk\crawler_asset_workflows.py tests\test_tk_dialogs.py` OK；targeted 4 tests OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 73 tests OK；`py -3 -B -m unittest tests.test_tk_dialogs tests.test_web_preview tests.test_crawler_assets -v` 159 tests OK；robustness targeted tests OK；`py -3 -B -m unittest tests.test_web_preview tests.test_event_log tests.test_tk_dialogs -v` 119 tests OK；`git diff --check` OK（僅 CRLF/LF warning）；docs/api_launcher/frontends/tests mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，853 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_182328.log`。

## 2026-05-28 18:07 Tk seed job single-flight guard
- 本輪做 bounded scheduler/consolidation 小切片：`frontends/tk/crawler_asset_workflows.py` 新增 `_start_crawler_asset_background_job()` / `_release_crawler_asset_background_job()`，用 `(job_type, asset_id, dataset_uid)` 登記 active Tk 背景任務。同一 seed 的欄位探測或 seed download/import 已在執行時，Tk 不再重複開 `threading.Thread`，而是回報「already running」狀態。
- 這不是全面改 async/await，也不改後端 `api_launcher` 下載、匯入、schema probe 或 crawler 行為；只是先在 Tk 薄殼上加 single-flight guard，降低連點造成的重複 worker、SQLite path / download path 競爭與對話框狀態混亂風險。
- 已推送 `ee702cd Add Tk seed job single-flight guard`；GitHub Actions run `26568299155` 已通過 Ubuntu、Windows 與 real DB smoke。先前本地驗證：`py -3 -B -m py_compile frontends\tk\crawler_asset_workflows.py tests\test_tk_dialogs.py` OK；targeted 3 tests OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 71 tests OK；`py -3 -B -m unittest tests.test_tk_dialogs tests.test_web_preview tests.test_crawler_assets -v` 157 tests OK；docs/Tk mojibake scan OK；`git diff --check` OK（僅 CRLF/LF warning）；`.\scripts\pre_push_smoke_brief.cmd` 通過，849 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_180047.log`。

## 2026-05-28 17:52 Web Preview Windows socket hardening
- `a862a7c Move seed enumeration display into profile` 已推送，但 GitHub Actions run `26567064570` 的 Windows job 在 `tests.test_web_preview.WebPreviewApiTest.test_real_download_demo_route_is_developer_diagnostic_only` 發生 localhost 404 短 JSON 回應讀取中斷：`ConnectionAbortedError: [WinError 10053]`。Ubuntu 與 real DB smoke 已通過，失敗點集中在 Web Preview 測試/HTTP close contract，不是 seed enumeration display refactor 本身。
- 本輪後續修補 Web Preview JSON response close semantics：`frontends/web/server.py` 的 `write_json()` 現在對 JSON/錯誤回應明確送出 `Connection: close`、flush body，並設定 `close_connection = True`；`tests/test_web_preview.py` 的 preview POST helper 也送出 `Connection: close` 並使用 bounded retry，避免 Windows runner 的 localhost/host security software 在短 404 body 上造成 flaky failure。
- 已推送 `1e5e7d0 Harden Web preview JSON connection close`；GitHub Actions run `26567621356` 已通過 Ubuntu、Windows 與 real DB smoke。先前本地驗證：`py -3 -B -m py_compile frontends\web\server.py tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview.WebPreviewApiTest.test_real_download_demo_route_is_developer_diagnostic_only -v` OK；`py -3 -B -m unittest tests.test_web_preview tests.test_crawler_assets -v` 86 tests OK；`py -3 -B -m unittest tests.test_tk_dialogs tests.test_developer_diagnostics -v` 73 tests OK；docs/frontends-web mojibake scan OK；`git diff --check` OK（僅 CRLF/LF warning）；`.\scripts\pre_push_smoke_brief.cmd` 通過，847 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_174707.log`。

## 2026-05-28 17:40 Seed enumeration display contract
- 本輪做 bounded consolidation：`crawler_seed_enumeration_payload()` 仍在 service 層決定 blocked/error/empty/local-limit/warning/within-limits/sample 狀態，但顯示文案、tone、default next_action 與 completion confidence 的預設值已抽到 `api_launcher/crawler_asset_display.py` 的 `SeedEnumerationDisplayProfile` / `seed_enumeration_display_payload()`。
- 這讓 Web/Tk/未來 Qt 繼續消費同一份 `seed_enumeration` payload，同時避免 `crawler_asset_service.py` 繼續吸收 UI 顯示字串。沒有改 crawler、download/import、seed page window 或 remote pagination 行為。
- 已推送 `a862a7c`；本地驗證：`py -3 -B -m py_compile api_launcher\crawler_asset_display.py api_launcher\crawler_asset_service.py tests\test_crawler_assets.py` OK；`py -3 -B -m unittest tests.test_crawler_assets tests.test_web_preview tests.test_tk_dialogs -v` 155 tests OK；docs/api_launcher mojibake scan OK；`git diff --check` OK（僅 CRLF/LF warning）；`.\scripts\pre_push_smoke_brief.cmd` 通過，847 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_173534.log`。GitHub Actions run `26567064570` 在 Windows Web Preview 404 短回應讀取處失敗，已在上一節記錄後續修補。

## 2026-05-28 17:25 Crawler registry CLI JSON
- 本輪把 `api_launcher/crawler_registry_report.py` 接成正式 CLI JSON 入口：`py -3 -B APIkeys_collection.py --crawler-registry-report-json` 會輸出 source type count、dimension counters、matrix cells、capability groups 與 spec payload，供 agent / CI / diagnostics 直接讀取，不必解析 Web/Tk 或人類文字。
- `api_launcher/cli_flags.py` 維持 lazy import，並將原本已壞掉的註解重寫成乾淨 ASCII 維護註解；`core.py` 只新增薄入口 `show_crawler_registry_report()`，不在 core 內重建 registry 邏輯。
- 已推送 `f002ff1` Add crawler registry report CLI JSON；GitHub Actions run `26566344259` 已通過 Ubuntu、Windows 與 real DB smoke。先前本地驗證：`py -3 -B -m py_compile api_launcher\cli_flags.py api_launcher\core.py api_launcher\crawler_registry_report.py tests\test_developer_diagnostics.py` OK；`py -3 -B -m unittest tests.test_developer_diagnostics tests.test_cli_flags tests.test_project_maturity -v` 8 tests OK；實跑 `py -3 -B APIkeys_collection.py --db state\tmp\crawler_registry_report.sqlite --init-db --seed --crawler-registry-report-json` 只輸出 JSON，無 `[db]` / `[seed]` 人類訊息；docs/api_launcher mojibake scan OK；`git diff --check` OK（僅 CRLF/LF warning）；`.\scripts\pre_push_smoke_brief.cmd` 通過，846 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_171845.log`。

## 2026-05-28 17:06 Crawler registry report diagnostics
- 本輪新增 `api_launcher/crawler_registry_report.py`，把 `CrawlerSpec` registry 轉成 UI-neutral report / summary：包含 source type count、dimension counters、matrix cells、capability groups 與 spec payload。這不打 live source，也不做 crawler smoke，只描述目前正式 dispatch 已使用的 registry。
- `api_launcher/developer_diagnostics.py` 的 `crawler_handler_smoke_diagnostics_payload()` 現在會帶 `registry_summary`，因此 Tk/Web/未來 Qt 的 developer-only diagnostics 可讀同一份 registry 維度摘要，不需要各自掃 globals 或重建 source_type 分組。
- 已推送 `628b6bf` Add crawler registry diagnostics report；GitHub Actions run `26565469450` 已通過 Ubuntu、Windows 與 real DB smoke。先前本地驗證：`py -3 -B -m py_compile api_launcher\crawler_registry_report.py api_launcher\developer_diagnostics.py tests\test_developer_diagnostics.py` OK；`py -3 -B -m unittest tests.test_developer_diagnostics tests.test_tk_dialogs tests.test_web_preview -v` 113 tests OK；docs/api_launcher mojibake scan OK；`git diff --check` OK（僅 CRLF/LF warning）；`.\scripts\pre_push_smoke_brief.cmd` 通過，845 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_165956.log`。

## 2026-05-28 16:51 Crawler registry dispatch consolidation
- 本輪把 crawler dispatch 往宣告式 registry 再收一刀：`discover_dataset_candidate_output_for_source()` 與 `discover_dataset_candidates_for_source()` 現在直接透過 `crawler_handler(source.source_type)` 讀 `CrawlerSpec` registry；`SOURCE_CRAWLER_HANDLERS` 保留為相容/診斷 surface，但不再承載正式分派責任。
- `api_launcher/crawlers/registry.py` 新增 `iter_crawler_specs_by_dims()` / `crawler_specs_by_dims()`，`dataset_sources.py` 新增 `list_registered_crawlers()` / `list_crawlers_by_dims()`，讓 CLI/UI/debug 可以按 `source_family`、`transport`、`auth_profile`、`result_shape` 做 partial matrix query，不必回到散落的 `source_type` 分支。
- 這是 registry/gateway 邊界收斂，不改 14 個 crawler handler、pagination、download/import 或 UI 行為。已驗證：`py -3 -B -m py_compile api_launcher\crawlers\registry.py api_launcher\crawlers\dataset_sources.py tests\test_dataset_discovery.py` OK；`py -3 -B -m unittest tests.test_dataset_discovery tests.test_crawler_assets tests.test_web_preview -v` 141 tests OK；docs/crawlers mojibake scan OK；`git diff --check` OK（僅 CRLF/LF warning）；`.\scripts\pre_push_smoke_brief.cmd` 通過，844 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_164315.log`。已推送 `b1091b2 Route crawler dispatch through registry`；GitHub Actions run `26564776648` 已通過 Ubuntu、Windows 與 real DB smoke。

## 2026-05-28 16:09 Tk seed schema probe action
- 本輪把 Web 已有的 seed-level schema/head probe 心流補到 Tk：`CrawlerAssetSeedDialog` 新增「探測欄位」動作，只把選中 seed 的 `api_url` / `download_url` / `landing_url` 包成 entry，不在 dialog 內推斷欄位或 source type。
- `CrawlerAssetWorkflowMixin` 新增 `run_crawler_asset_seed_schema_probe_from_ui()`：背景呼叫既有 `probe_plan_entry_schema()`，再用 `apply_schema_probe_to_crawler_asset_bound_form_spec()` 產生 enriched bounds form，最後開同一個 `CrawlerAssetBoundDialog` 讓使用者套用界域。套用後的 bounds payload 會暫存在 `crawler_asset_bound_payloads[asset_id]`，後續「下載此 Seed」仍走 formal seed download/import service。
- 這是 Tk/Web 對齊切片，不改 schema probe 後端、不改 crawler/download/import，也不把 source-specific schema 規則塞進 Tk。已補 regression：seed row URL helper、seed dialog action routing、schema probe worker enrichment / bounds payload storage。已驗證：`py -3 -B -m py_compile frontends\tk\crawler_asset_seed_dialog.py frontends\tk\crawler_asset_workflows.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 69 tests OK；`py -3 -B -m unittest tests.test_tk_dialogs tests.test_web_preview tests.test_crawler_assets -v` 154 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，843 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_160421.log`。已推送 `430d278 Add Tk seed schema probe action`；GitHub Actions run `26562872018` 已通過 Ubuntu、Windows 與 real DB smoke。

## 2026-05-28 15:43 Web seed schema probe action
- 本輪先在 Web Preview 接上 seed-level schema/head probe 動作：推薦 seed 面板與每筆 seed row 現在都有「探測欄位」按鈕，會把可見 seed 的 `api_url` / `download_url` / `landing_url` 包成 entry，呼叫既有 `POST /api/crawler-assets/{asset_id}/bounds-form/schema-probe`。
- 這是 UI 防盲填接線，不改 schema probe 後端、不改 crawler/download/import。Web 只負責選取使用者已看見的 seed URL；欄位推論、`time_field` / `columns` selector enrichment 仍由後端 `crawler_asset_bound_form_schema_probe()` 與 `apply_schema_probe_to_crawler_asset_bound_form_spec()` 負責。
- 已補 `tests.test_web_preview` static regression，鎖住 `runSeedSchemaProbeById`、`schemaProbeEntryForSeed`、`/bounds-form/schema-probe` 與「探測欄位」文案存在。驗證：`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest tests.test_web_preview -v` 41 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，840 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_154516.log`。已推送 `6f3e2de Add Web seed schema probe action`；GitHub Actions run `26561993780` 已通過 Ubuntu、Windows 與 real DB smoke。

## 2026-05-28 15:31 Web capability address display
- 本輪把 `CrawlerCapabilityProfile` 的 capability address 接到 Web Preview：`frontends/web/preview_api.py` 的 crawler asset card payload 現在包含 `capability_profile`，Web 卡片與 Passport 會顯示「能力 0000」、「能力位址」與「能力膠囊」摘要。
- 這是 UI 顯示層接線，不改 crawler handler、download/import、source registry 或 capability 編碼規則。Web 只消費後端 payload，不自行用 `source_type` 推算能力分組。
- 已補 `tests.test_web_preview` regression：鎖住 cards API 會輸出 `capability_profile.capability_binary` / `capability_bits` / `source_family`，並鎖住靜態 UI 文字與 `.capability-address-badge` 樣式存在。
- 本地驗證已通過：`node --check frontends\web\static\app.js` OK；`py -3 -B -m py_compile frontends\web\preview_api.py tests\test_web_preview.py` OK；`py -3 -B -m unittest tests.test_web_preview -v` 41 tests OK；`py -3 -B -m unittest tests.test_web_preview tests.test_crawler_assets tests.test_dataset_discovery -v` 140 tests OK；臨時 Web server `127.0.0.1:8795` 驗證 `/api/health`、`/api/crawler-assets`、`/app.js`、`/styles.css` 均帶有 capability profile / badge 內容；`.\scripts\pre_push_smoke_brief.cmd` 通過，840 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_152601.log`。已推送 `6d2cf77 Show crawler capability address in Web Preview`；GitHub Actions run `26561194976` 已通過 Ubuntu、Windows 與 real DB smoke。

## 2026-05-28 15:08 Capability address surfaced in capability profile
- 本輪把 `api_launcher/crawlers/registry.py` 的 4-bit `CrawlerCapabilityCode` 繼續往 `api_launcher/crawler_capability_profiles.py` 推進：`CrawlerCapabilityProfile` 現在會保存 `capability_code`，並在 `to_dict()` 中輸出 `capability_code`、`capability_bits`、`capability_binary`。
- 這是 UI/agent 可讀的「能力膠囊地址」接線，不是 crawler 重寫、不改 14 個 handler、不改 download/import 行為。Web/Tk/未來 Qt 可以從同一個 `asset.to_dict()["capability_profile"]` 讀 capability address，而不是各自重建 source_type 分支。
- 未註冊或未實作的 source type 仍回空地址：`capability_code={}`、`capability_bits=None`、`capability_binary=""`，避免 backlog handler 被誤標成已分類能力。
- 已補 `tests.test_crawler_assets` regression，鎖住 CKAN profile 的 `0000` address 與 unknown source 的空地址 fallback。已推送 `7d319e2 Surface crawler capability address in profiles`；GitHub Actions run `26560284599` 已通過 Ubuntu、Windows 與 real DB smoke。本地驗證：`py -3 -B -m unittest tests.test_crawler_assets -v` 44 tests OK；`py -3 -B -m unittest tests.test_crawler_assets tests.test_dataset_discovery tests.test_web_preview -v` 140 tests OK；`py -3 -B -m py_compile api_launcher\crawler_capability_profiles.py tests\test_crawler_assets.py` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，840 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_150514.log`。

## 2026-05-28 14:40 Crawler capability address / mask index
- 本輪開始把使用者提出的 IPv4/CIDR 類比落成小型 PoC：在 `api_launcher/crawlers/registry.py` 內新增 4-bit `CrawlerCapabilityCode` 與 `CrawlerCapabilityMask`，用固定維度描述 crawler 分流能力，而不是把 source type 分支散回 UI 或 importer。
- 目前 4 個位元的維度是：來源表面（catalog vs index/capabilities）、transport（JSON vs text/markup）、auth（none vs credential-aware）、輸出形狀（dataset list vs resource/layer links）。這是輔助索引，不取代 `CrawlerSpec`，也不改現有 14 個 handler 的行為。
- 目前分組結果：`0000` 是一般 JSON catalog dataset list（NCEI/CKAN/CMR/STAC/GBIF/Dataverse/Zenodo/DataCite/OGC Records/OpenAlex）；`0010` 是 credential-aware JSON catalog（Socrata）；`1000` 是 JSON index scan（ERDDAP）；`1101` 是 text/XML index 或 capabilities 產生 resource/layer links（HTML file index、OGC WMS）。
- 已補 focused tests：`tests.test_dataset_discovery` 驗證 4-bit 分組、prefix mask 查詢、credential mask 查詢、未知維度 fail-fast 與重複 source_type fail-fast。已推送 `32d2325 Add crawler capability address mask index`；GitHub Actions run `26559567014` 已通過 Ubuntu、Windows 與 real DB smoke。本地驗證：`py -3 -B -m unittest tests.test_dataset_discovery -v` 55 tests OK；`py -3 -B -m unittest tests.test_dataset_discovery tests.test_crawler_assets tests.test_web_preview -v` 140 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，840 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_144419.log`。

## 2026-05-28 14:09 Branch threshold / decorator dispatch / profile storage guard
- 使用者補充準宣告式架構的三個邊界，本輪先收進文檔，不改產品程式碼。第一，`if/else` 適合 2 到 3 條人類可一眼讀懂的簡單分支；到 4 條路時已接近 `2 x 2` matrix，若再疊 source type、auth、pagination、content format、bounds facet 等維度，就應改用 table / registry / gateway 收束。
- 第二，decorator 不只是語義標籤；在大量條件分支下，它可以是避免中心 `if/elif` 膨脹的註冊/分派寫法。`@crawler(...)` 應讓 handler 主動掛到 registry / matrix，再由 gateway 選路；但 decorator 不負責改寫 handler 回傳值，payload 包裝與狀態正規化仍在 normalizer 出口。
- 第三，外部 YAML / JSON / TOML / `.env` 適合放有人類語意、需要使用者或維護者打開填寫的 source/provider/credential/rate-limit profile；純邏輯高維分支若不需要人類直接填寫，優先用 typed Python table / dataclass / tuple index / dict registry，不為了「宣告式」把機器分派矩陣硬塞進 YAML。
- 已更新 `DECLARATIVE_ARCHITECTURE_DECISION.zh-TW.md` 與 `DATASET_DISCOVERY_NOTES.zh-TW.md`。下一輪實作 crawler dispatch/gateway 時，先用 typed table / registry 做機器分派；只有 source/profile/credential 類人類可填設定才考慮外部檔案。
- 已推送 `c4970e2 Document branch threshold profile storage guardrails`；GitHub Actions run `26558075686` 已通過 Ubuntu、Windows 與 real DB smoke。本地檢查：`git diff --check` OK（僅 CRLF/LF warning）；docs mojibake scan OK。此輪是 docs-only checkpoint，因此沒有跑產品單元測試。

## 2026-05-28 13:46 Loop sentinel / range / slice / decorator return guard
- 本輪補充 loop / ordered collection / decorator 設計規則，不改產品程式碼。結論：range、slice、array/list/page window 是避免硬編碼的重要工具；迴圈停止條件優先來自 protocol response、source profile、使用者 bounds、job budget、schema size、remote pagination metadata 或 runtime policy。
- 硬寫哨兵值或 magic page size 不是完全禁止，但必須先被審查；若不可避免，應命名成常數或 profile 欄位、可覆寫、可測，並在 payload 回報 `limit_reached` / `sentinel_stop` 類 structured warning。UI 顯示 seed/candidate preview 時應呈現 `shown_start`、`shown_end`、`page_size`、`has_more`、`remaining`，不要把 `[0:49]` / `[0:99]` 的窗口硬編成假全集。
- 裝飾器方向採納為「註冊與標註」：`@crawler(...)` 可以把 handler 與 `CrawlerSpec` 登記到 registry / matrix，但 handler 原本的 `DatasetCandidate[]` / `DatasetCrawlerOutput` 回傳值與 warning / pagination metadata 不應被 decorator 吞掉。decorator 讓 dispatch 更優雅，核心資料流仍要可追蹤、可測。
- 使用者進一步釐清：目標不是上帝 YAML，而是混合式準宣告式架構。允許 pipeline / array / registry / profile / decorator 搭配少量條件分支、迴圈與受控淺遞迴；判斷要集中在 gateway / policy / adapter 邊界，不要散落到 UI，也不要為了消滅所有 `if` 創造更難 debug 的自製 DSL。
- 分支膠囊的設計要點：主管道進入膠囊前先正規化 input；膠囊內的條件分支只負責選路，不負責 in-box-return、payload 包裝、UI 文案或狀態回填；膠囊出口 / gateway / normalizer 再把 handler 回傳收斂回主管道 contract。
- 已更新 `DECLARATIVE_ARCHITECTURE_DECISION.zh-TW.md`、`DATASET_DISCOVERY_NOTES.zh-TW.md`、`CODE_HEALTH_AUDIT.zh-TW.md` 與 `PROJECT_GTD.md`。下一輪若碰到 seed page / candidate preview / schema preview / queue 顯示，優先用 range/slice/islice 與後端 page contract，不要把數字散落在 Tk/Web。

## 2026-05-28 13:45 Recursion and pipeline/declarative architecture guard
- 本輪補充架構決策，不改產品程式碼。結論：宣告式與管道式不是二選一；RRKAL 應採「profile 宣告能力/政策/budget，pipeline 負責按順序安全執行」。不要偏向萬能 YAML，也不要回到散落手寫流程。
- 遞迴不是禁用，但遠端 crawler、網站探索、HTML index traversal、pagination、下載/匯入主路徑預設不用 recursive call stack，改用 queue / stack / `deque` + `seen` + `max_depth` + `max_pages` + `max_nodes` + timeout/rate-limit。互動式遠端探索以 Raspberry Pi-class 裝置為基準，預設 `max_depth=2`；沒有明確 source profile、測試與使用者確認時，不得超過 `max_depth=4`。
- 已更新 `DECLARATIVE_ARCHITECTURE_DECISION.zh-TW.md`、`DATASET_DISCOVERY_NOTES.zh-TW.md`、`CODE_HEALTH_AUDIT.zh-TW.md` 與 `PROJECT_GTD.md`。下一個實作若碰到 crawler/link traversal，必須把 depth/page/node budget 放進 source profile / request policy，不要寫死在 UI 或單一 handler。
- 已推送 `f1b38b8 Document recursion and pipeline guardrails`；GitHub Actions run `26557008628` 已通過 Ubuntu、Windows 與 real DB smoke。本地檢查：`git diff --check` OK（僅 CRLF/LF warning）；docs mojibake scan OK。此輪是 docs-only checkpoint，因此沒有跑產品單元測試。

## 2026-05-28 13:29 Governance intake before next implementation
- 本輪是文檔治理 checkpoint，不改產品程式碼、crawler、download、import、Tk/Web 行為，也不寫入 `K:\CODE_KM` 或其他 K 槽專案。工作樹接手時乾淨，HEAD 為 `b89202d Record crawler capability profile CI checkpoint`。
- 已消化並落入協作文件的規則：大檔解耦要排進固定 consolidation slice；後端邏輯邊界先於資料夾搬家；文檔可作為資料資產治理，先用 CSV/JSON registry，後續再評估 SQLite catalog；註釋要說明 ownership、guard 與不變量，行為改變時同步更新或刪除；未完整實作的 UI surface 要顯示 `🚧` / construction / `contract_only` / `planned`，避免使用者或驗收把空殼當交付。
- K 槽其他工作區仍只作 read-only 概念參考：`CODE_KM` 的 manifest / run state / review gate / next_action label 可借鏡；`video_downloader` 的 config matrix / queue scheduler 可借鏡；`rrkal-renderer` 的 artifact schema 與 render report 可借鏡；`auto_trading` 的 domain split 可借鏡。不得直接搬程式碼，也不得寫入那些專案。
- 已推送 `835d673 Record governance intake before implementation`；GitHub Actions run `26556736959` 已通過 Ubuntu、Windows 與 real DB smoke。本地檢查：`git diff --check` OK（僅 CRLF/LF warning）；docs mojibake scan OK。此輪是 docs-only checkpoint，因此沒有跑產品單元測試。
- 下一個產品實作切片建議二選一：第一，延伸 crawler registry，讓 dispatch/gateway 真正讀 `CrawlerSpec` 並補 partial matrix query / duplicate guard 測試；第二，把 schema/head probe 觸發接到 Web/Tk seed 選取流程，讓 bounds 表單更少盲填。兩者都應保持小切片、先測 service，再接 UI。

## 2026-05-28 12:45 Crawler capability profile consumes registry metadata
- 本輪把上一個 `CrawlerSpec` registry metadata 接進既有 `CrawlerCapabilityProfile`，讓 asset payload 直接帶 `source_family`、`transport`、`result_shape` 與 `supports_full_crawl`。這讓 Web/Tk/agent 不必再從 source type 或 handler 名稱猜來源能力。
- 實作仍是 read/describe contract，不改 crawler、download、import 或 UI 行為；若 registry 尚未有該 source type，capability profile 會保守回 `unknown` / `False`，避免未支援來源被誤宣稱有完整能力。
- 已推送 `c0cbc6f Surface crawler spec metadata in capability profile`；GitHub Actions run `26555497364` 已通過 Ubuntu、Windows 與 real DB smoke。本地驗證：`py -3 -B -m unittest tests.test_crawler_assets tests.test_dataset_discovery tests.test_web_preview -v`，136 tests OK；`crawler_capability_profiles.py` / `test_crawler_assets.py` in-memory compile OK；docs / source mojibake scan OK；`git diff --check` OK（僅 CRLF/LF warning）；`.\scripts\pre_push_smoke_brief.cmd` 通過，836 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_124725.log`。

## 2026-05-28 12:31 Crawler registry compatibility handoff
- 本輪採納「CrawlerSpec + Registry + decorator」方向，但只做第一版相容層，不搬 14 個 crawler handler。新增 `api_launcher/crawlers/registry.py`，提供 `CrawlerSpec`、`@crawler(...)`、`crawler_specs_by_source_type()` 與 `crawler_matrix()`；`dataset_sources.py` 目前仍保留 `SOURCE_CRAWLER_HANDLERS` 給舊呼叫與測試，但這張表已由 registry specs 生成。
- 目前 14 個 supported source type 都已有宣告式 metadata：`source_family`、`transport`、`auth_profile`、`result_shape`、`supports_full_crawl`。這是往 `Matrix Cell -> Validated Profile -> Capability Gateway -> Middleware Pipeline` 推進的薄層，還不是 universal YAML / decorator pipeline 重寫。
- 已推送 `bc80e96 Add crawler spec registry compatibility layer`；GitHub Actions run `26555005114` 已通過 Ubuntu、Windows 與 real DB smoke。本地驗證：`py -3 -B -m unittest tests.test_dataset_discovery tests.test_crawler_audit_smoke tests.test_crawler_assets tests.test_source_patterns tests.test_discovery_drafts -v`，142 tests OK；`registry.py` / `dataset_sources.py` / `test_dataset_discovery.py` in-memory compile OK；docs / crawler mojibake scan OK；`git diff --check` OK（僅 CRLF/LF warning）；`.\scripts\pre_push_smoke_brief.cmd` 通過，836 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_123315.log`。

## 2026-05-28 12:13 Schema/head probe bounds form handoff
- 本輪把 crawler asset 界域表單的 schema/head probe enrichment 收成後端契約：新增 `apply_schema_probe_to_crawler_asset_bound_form_spec()`，當 `SchemaProbeResult` 有欄位時，`time_field` 會轉成 `select_or_text` selector，`columns` 會帶出可選欄位，`start_date` / `end_date` 不再被誤標成仍需 schema probe；probe 失敗則保留 review/warning 狀態，不假裝可選。
- Web Preview 新增薄 route：`POST /api/crawler-assets/{asset_id}/bounds-form/schema-probe`，只接受候選 entry URL、呼叫既有 `probe_plan_entry_schema()`，再回傳同一份 `bound_form` display payload。前端仍不自行推斷欄位或 source type；真正把此 route 接到 seed 選取 / UI 按鈕是下一個切片。payload 正規化已涵蓋 top-level `url` 與 nested `entry.url`。
- 已推送 `1f1cd71 Add schema probe bounds form enrichment`；GitHub Actions run `26554444984` 已通過 Ubuntu、Windows 與 real DB smoke。本地驗證：`py -3 -B -m unittest tests.test_crawler_assets tests.test_web_preview tests.test_tk_dialogs -v`，151 tests OK；docs mojibake scan OK；`git diff --check` OK（僅 CRLF/LF warning）；`.\scripts\pre_push_smoke_brief.cmd` 通過，835 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_121359.log`。

## 2026-05-28 11:48 Tk bounds quick values handoff
- 本輪先確認另一 agent 的 `api_launcher/cli_flags.py` lazy import 變更已安全落地：HEAD `055a9fc`，`cli_flags.py` 目前無未提交 diff；`py -3 -B -m unittest tests.test_cli_flags tests.test_handoff -v`，22 tests OK，所以不需回退或修補該檔。
- 同輪把 Tk 界域表單接上既有後端 `CrawlerAssetBoundFormSpec.recommended_values` 與 `presets`。Dialog 現在會顯示「快速界域 / Quick bounds」、「套用推薦值」與最多 4 個後端區域預設按鈕；按下後只複製後端明確提供的值，不在 Tk 內自行猜 collection、time field、bbox 或版本。
- 已補 headless regression：`apply_recommended_values()` 會套用安全 limit，但不會把 STAC search term 誤填成 collection；`apply_preset("taiwan")` 會套用台灣 bbox，找不到 preset 時回 `False`。已驗證：`py -3 -B -m unittest tests.test_tk_dialogs -v`，66 tests OK；`py -3 -B -m unittest tests.test_crawler_assets tests.test_tk_dialogs -v`，108 tests OK。下一步仍是 schema/head probe，讓版本、時間欄位與欄位選擇從「推薦值」進一步變成遠端可選清單。

## 2026-05-28 11:27 CLI lazy import hardening handoff
- 工作樹接回時有 `api_launcher/cli_flags.py` 的延遲導入變更。本輪將它收成正式 hardening：`command_requested()` 內才導入各 CLI 子命令活性判斷函式，避免 import `api_launcher.cli_flags` 或普通啟動路徑預先載入所有 CLI workflow 依賴。
- 新增 `tests/test_cli_flags.py`，用 fresh subprocess 驗證 import `api_launcher.cli_flags` 時不會連帶載入其他 `api_launcher.cli_*` command module。已驗證：不寫 pyc 的 compile OK；`py -3 -B -m unittest tests.test_cli_flags tests.test_handoff -v`，22 tests OK。
- 本輪也修正 development log 漂移：`806b6cd Narrow active focus to crawler closure` 與 `22ccefa Add recommended seed action to Tk dialog` 均已改標成 `PUSHED / CI PASS`，對應 GitHub Actions run `26549667153` / `26552672553`。

## 2026-05-28 11:18 Tk recommended seed handoff
- 本輪把 Tk Seed 清單 dialog 接上後端 `recommended_seed_uid`：dialog 現在會顯示「推薦 seed」摘要、自動選中推薦列，並提供「下載推薦 Seed」按鈕。推薦仍完全來自 `crawler_seed_page()` payload；Tk 不自行挑第一列、收藏列或依 source type 推斷可下載性。
- 新增純 helper regression：`crawler_seed_dialog_recommended_text()` / `crawler_seed_dialog_recommended_uid()` 會呈現後端推薦 seed，並保留既有 `下載此 Seed` / 收藏 / formal seed download service flow。已驗證：`py -3 -B -m py_compile frontends\tk\crawler_asset_seed_dialog.py tests\test_tk_dialogs.py` OK；`py -3 -B -m unittest tests.test_tk_dialogs -v`，64 tests OK；`py -3 -B -m unittest tests.test_tk_dialogs tests.test_crawler_seed_registry tests.test_handoff -v`，107 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，827 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_111749.log`。
- 下一步仍是小閉環：挑第二條 live public source 做 bounded closure readiness artifact，或優先補 schema/head probe，讓界域表單欄位從盲填逐步變成下拉/預設值。

## 2026-05-28 10:41 Web recommended seed UX handoff
- 本輪把 Web Preview seed 清單接上後端 `recommended_seed_uid`：seed 面板現在會顯示「推薦 seed」區塊與「下載推薦 seed」按鈕，直接呼叫既有正式 `POST /api/crawler-assets/{asset_id}/seed-download-import`。前端只呈現 `crawler_seed_page()` 給的推薦，不自行挑 seed 或推斷 import policy。
- 已補 regression：seed page API 測試確認第一頁會回傳 `recommended_seed_uid` / `recommended_seed_next_action`；靜態 Web asset 測試確認 `seedRecommendedPanelHtml`、`下載推薦 seed` 與 `recommended_seed_uid` 存在。完整 Web / seed / handoff focused suite 已通過：`py -3 -B -m unittest tests.test_web_preview tests.test_crawler_seed_registry tests.test_handoff -v`，81 tests OK。過程中也把 legacy demo route 的 localhost POST 測試補上一次 Windows socket retry，避免本機 `WinError 10053` flake 汙染 route-removal regression。瀏覽器驗證時選到 NOAA NCEI seed list，畫面可見「下載推薦 seed」，且沒有把 raw `download_recommended_seed` 顯示給使用者。`.\scripts\pre_push_smoke_brief.cmd` 也已通過，826 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_105848.log`。已推送 `46601f2 Surface recommended seed in web preview`，GitHub Actions run `26552151790` 已通過 Ubuntu、Windows 與 real DB smoke。
- 下一步可把同一份推薦 seed UX 接回 Tk seed dialog / Crawler Passport，或挑第二條 live public source 做 bounded closure readiness artifact。若繼續 Web 驗收，請在本地 clone 或本機路徑啟動 Web Preview，避免 K/RaiDrive 影響 server / SQLite。

## 2026-05-28 09:45 Focus narrowing handoff
- 使用者更新目前目標：完成手邊任務後，近期主線收斂到 crawler / data asset 的小閉環，暫時略過資料渲染與 Unreal 5 對接。後續不要把 `simulation_bridge.py`、`unreal_bridge.py`、renderer contracts 當作近期交付焦點；它們維持 maturity matrix 內的 `contract_only` / planned work。
- 下一個有效切片應優先服務「入口 -> 枚舉 seed -> 推薦 seed -> 有界下載 / 匯入 -> 可驗收 JSON/UI」這條線，例如 live public source readiness artifact、Web/Tk 使用 recommended seed 的一鍵操作、或將 bounds/defaults contract 接進 UI。

## 2026-05-28 09:37 Seed page recommended default handoff
- 本輪在 seed page payload 補上推薦預設 seed：`crawler_seed_page()` 現在會從目前可見頁面挑第一筆可直接進 `sqlite_curated_import` 且不需 review 的 seed，輸出 `recommended_seed`、`recommended_seed_uid` 與 `recommended_seed_next_action=download_recommended_seed`。這是 Web/Tk 後續做「懶人一鍵推薦下載」的後端契約，不讓前端自行猜哪筆 seed 最安全。
- 已用 live Socrata temp catalog 驗證：`nyc_open_data_socrata_catalog` 第一頁會推薦 `ds_5dce200fd403246bca0031d5` / `Civil Service List (Active)`，且 `recommended_seed.content_display_label=可有界匯入 SQLite`。PowerShell 文字管線可能把中文顯示成 `?`，本輪用 Python `subprocess.run(..., encoding='utf-8')` 捕捉 stdout 驗證檔案/JSON 本身沒有 mojibake。
- 已推送：`8083578 Add recommended crawler seed payload`；GitHub Actions run `26549445961` 已通過 Ubuntu、Windows 與 real DB smoke。本輪驗證：in-memory syntax compile OK；`py -3 -B -m unittest tests.test_crawler_seed_registry tests.test_handoff -v` 43 tests OK；docs / source / tests mojibake scan 0 hits；`git diff --check` OK（僅 CRLF/LF warning）；`.\scripts\pre_push_smoke_brief.cmd` 通過，826 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_093628.log`。

## 2026-05-28 09:19 Socrata seed importability display handoff
- 本輪修正 seed 清單的內容能力契約：`socrata_resource` 不再被 `content_registry` 標成「未知內容格式 / adapter_review」，而是標成 resolver-backed API resource。它會由 `socrata_bounded_sample_query_resolver` 先轉成有界 JSON sample，再走既有 JSON -> SQLite 匯入。
- 已驗證 live public Socrata probe：用本地 temp DB 枚舉 `nyc_open_data_socrata_catalog` 得到 5 筆 seed；第一筆 `Civil Service List (Active)` 的 seed page JSON 現在顯示 `content_display_label=可有界匯入 SQLite`、`review_required=false`、`parser_id=socrata_bounded_sample_query_resolver`。同一 seed 先前已實跑 formal seed download/import，結果為 `download_import_completed`、`submitted=1`、`completed=1`、`imported=1`。
- 已推送：`4dc573b Mark Socrata seeds as bounded importable`；GitHub Actions run `26548948298` 已通過 Ubuntu、Windows 與 real DB smoke。本輪驗證：in-memory syntax compile OK；`py -3 -B -m unittest tests.test_content_registry tests.test_crawler_seed_registry tests.test_handoff -v` 55 tests OK；docs / source / tests mojibake scan 0 hits；`git diff --check` OK（僅 CRLF/LF warning）；`.\scripts\pre_push_smoke_brief.cmd` 通過，825 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_092121.log`。

## 2026-05-28 08:54 Crawler seed download/import CLI handoff
- 本輪把 seed-level formal download/import 補到 CLI，新增 `--run-crawler-seed-download-import ASSET_ID DATASET_UID` 與 `--crawler-seed-download-import-json`。這條命令重用 `api_launcher.crawler_asset_download.run_crawler_seed_download_import()`，不在 CLI 重寫 plan、download 或 import 規則。
- CLI 會從本機 catalog seed 建立 resolved seed plan，預設把 seed download artifact 寫到 `--downloads-root` 底下的 `crawler_seed_downloads/<asset>__<seed>/resolved_seed_download_plan.json`，並可沿用既有 `--import-sqlite-db`、`--download-timeout`、`--plan-import-existing-table-policy`。這讓「選入口 -> 枚舉 seed -> 選 seed -> 下載 / 匯入」可由 Web/Tk/CLI 三端共用同一條 service。
- 已推送：`d667f65 Add crawler seed download import CLI`；GitHub Actions run `26548277425` 已通過 Ubuntu、Windows 與 real DB smoke。已驗證：in-memory syntax compile OK；CLI help 會列出新參數；docs / source mojibake scan 0 hits；`git diff --check` OK（僅 CRLF/LF warning）；`py -3 -B -m unittest tests.test_crawler_seed_registry tests.test_handoff tests.test_project_maturity -v` 44 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，823 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_085742.log`。第一次用 `py_compile` 在 K/RaiDrive 上遇到 `WinError 5` 寫入 `__pycache__`，後續用不寫 pyc 的 `compile()` 檢查；這屬於雲端工作區 pycache/lock 問題，不是語法錯誤。

## 2026-05-28 07:55 Project maturity matrix handoff
- 本輪延續「小閉環 100% 但整體不能用單一百分比」的交付口徑，新增 `api_launcher/project_maturity.py` 與 CLI `--project-maturity-json` / `--write-project-maturity-json` / `--project-maturity-markdown`。後續使用者問整體進度時，應回 mature matrix，不要回 `94%` 這類單一數字。
- 新增 `docs/PROJECT_MATURITY_MATRIX.zh-TW.md`，正式定義 `deliverable_100`、`implemented_bounded`、`partial_bounded`、`contract_only`、`planned_not_started`、`hardening_needed`。`canonical_mvp_demo_closure` 仍可說 100%，但 renderer/simulation 是 `contract_only`，Qt 是 `planned_not_started`，provider-specific deep adapters 仍是 `partial_bounded`。
- 已推送：`aff46b9 Add project maturity matrix`；GitHub Actions run `26546301932` 已通過 Ubuntu、Windows 與 real DB smoke。本地驗證：`py -3 -B -m py_compile api_launcher\project_maturity.py api_launcher\core.py api_launcher\cli_flags.py tests\test_project_maturity.py` OK；`py -3 -B -m unittest tests.test_project_maturity tests.test_handoff -v` 24 tests OK；實跑 `--project-maturity-json` 寫出 `state\reports\project_maturity_smoke.json`，確認 `canonical_delivery_scope.closure_percent=100` 且 rows 包含 `partial_bounded` / `contract_only`；docs mojibake scan OK；`git diff --check` 只有 CRLF/LF warning；`.\scripts\pre_push_smoke_brief.cmd` 通過，818 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_080033.log`。

## 2026-05-28 06:25 Canonical MVP closure readiness handoff
- 本輪回應「有目標、有推進進度，但永遠不到 100%，如何交付客戶」的問題，將 canonical MVP demo 小閉環正式做成可查詢的 readiness artifact。新增 `api_launcher/mvp_readiness.py`，CLI 新增 `--mvp-readiness-json` / `--write-mvp-readiness-json`。
- 已驗證小閉環 100% 只限 bounded scope：`seed -> candidate -> plan -> download -> manifest -> SQLite import -> JSON handoff`。實跑 `--run-mvp-demo-smoke-json state\mvp_demo\flow.json` 得到 `download_import_completed`、`row_count=3`；再跑 `--mvp-readiness-json` 得到 `status=ready_for_mvp_demo`、`closure_percent=100`、`blockers=[]`、`warnings=[]`。這不是全產品成熟度百分比。
- 同輪測試暴露環境探測魯棒性問題：`latest_events()` 原本會整份讀大型 JSONL，`log_event()`、renderer profile、startup environment checks 與 integration profile parsing 會呼叫可能卡住的 `platform.*`。本輪已改為檔尾 bounded 讀取；event log 平台欄位改用 `os.name` / `sys.version`；`rendering_profiles.py` / `platform_paths.py` / `environment.py` / `integrations.py` 改用 `sys.platform` 與環境變數做保守推斷。
- `scripts/pre_push_smoke.ps1` 也補上 K/RaiDrive upstream 探測 guard：`git rev-parse @{u}` 偶發讀不到 cwd 時只跳過 optional pending-push diff，不讓整個 smoke 直接失敗。
- 已推送：`bae2f19 Add MVP readiness closure report`；GitHub Actions run `26544580172` 已通過 Ubuntu、Windows 與 real DB smoke。本地驗證：`py -3 -B -m unittest tests.test_environment tests.test_cli_renderer_contracts tests.test_event_log tests.test_handoff tests.test_mvp_demo_flow -v` 35 tests OK；`py_compile` 相關 entrypoints / modified modules OK；`git diff --check` 只有 CRLF/LF warning；docs mojibake scan OK；實跑 MVP smoke + readiness JSON OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，815 tests / 4 skipped，MVP smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_071419.log`。下一位 agent 若要回答整體專案進度，必須回「成熟度矩陣」，不要把 `closure_percent=100` 擴張成全產品完成度。

## 2026-05-28 05:52 Source-code maturity audit handoff
- 本輪回應「為什麼昨天文檔審計後仍會把 contract / planned / implemented 混在一起」的問題，補上能力成熟度邊界。已查證：`simulation_bridge.py` 是 `contract_only`，`unreal_bridge.py` 只產生 `planned` target 並不做 real I/O，`dataset_adapters.py` 目前只有 GEBCO、HYG、yfinance 三條 provider-specific adapter。
- 這不代表 source crawler 只支援三種來源。`SOURCE_CRAWLER_HANDLERS` / `SUPPORTED_DATASET_SOURCE_TYPES` 說的是 source-level crawler handler / offline audit contract；`dataset_adapters.py`、`adapter_plan_resolver.py`、`content_registry.py`、renderer bridge 是不同層。後續文件不可只寫「支援某來源」，必須說明支援到 discovery、bounded plan、download、import、renderer bridge 或 contract-only 哪一層。
- 已推送：`f753e94 Clarify source capability maturity`；GitHub Actions run `26541108253` 已通過 Ubuntu、Windows 與 real DB smoke。這是 docs drift guard 的補洞，不改產品程式碼。本地 docs mojibake scan OK，`git diff --check` OK（僅 CRLF/LF warning）。

## 2026-05-28 05:43 Developer diagnostics next-action label handoff
- 本輪把 developer-only crawler handler smoke diagnostics payload 也補上 `next_action_label`。`api_launcher/developer_diagnostics.py` 現在會把 `run_dataset_discovery_handler_smoke_json_if_summary_fails` 轉成「摘要失敗時，執行 handler smoke JSON 診斷」，Tk diagnostics message 也優先顯示這個 label，不再把 raw action id 當主文案。
- 這是 UI-neutral display contract 的小切片，不改 handler smoke、crawler audit 或 Web/Tk diagnostics 執行邏輯；developer-only surface 仍明確標示它只是 offline contract smoke，不證明 live NASA/NOAA/CKAN endpoint 可連。
- 已推送：`eaae796 Add diagnostics next action label`；GitHub Actions run `26540644756` 已通過 Ubuntu、Windows 與 real DB smoke。本地驗證已通過：in-memory Python syntax check OK；`py -3 -B -m unittest tests.test_developer_diagnostics tests.test_tk_dialogs tests.test_web_preview -v` 103 tests OK；docs mojibake scan OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，812 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_054131.log`。

## 2026-05-28 05:34 Tk MVP smoke next-action label handoff
- 本輪把 Tk MVP Demo Smoke 失敗摘要也接到共用 `next_action_display_label()`。`frontends/tk/ui_helpers.py` 現在會把 `inspect_manifest` 轉成「檢查 manifest 與最近事件紀錄」，避免使用者在 Tk messagebox 看到 raw machine action；machine-readable `next_action` 仍保留在 CLI JSON / agent payload。
- 這是 UI 顯示層切片，不改 MVP demo smoke、download、manifest、SQLite import 或 repair 行為。新增 / 更新 regression：`tests.test_launcher_ui.DownloadPlanPanelUiTests.test_mvp_demo_smoke_result_message_guides_failed_closure` 會確認使用者訊息包含人類 label，且不含 raw `inspect_manifest`。
- 已推送：`c044d3e Use labels for Tk MVP smoke next action`；GitHub Actions run `26540081387` 已通過 Ubuntu、Windows 與 real DB smoke。本地驗證已通過：in-memory Python syntax check OK；`py -3 -B -m unittest tests.test_launcher_ui -v` 30 tests OK；`py -3 -B -m unittest tests.test_tk_ui_helpers tests.test_launcher_ui -v` 35 tests OK；docs mojibake scan OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，812 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_052930.log`。

## 2026-05-28 05:16 Web plan/listing next-action label handoff
- 本輪把 Web Preview 非缺憑證的 listing 與 plan-preview response 也補上 top-level `next_action_label`。`crawler_asset_listing()` 現在會把 `review_or_upsert_dataset_candidates` 轉成「審核或寫入候選資料」；`crawler_asset_plan_preview()` 的 dry-run / execute 路徑會分別輸出「建立下載計畫並交給後端判斷」或 plan outcome 的人類下一步。
- `frontends/web/static/app.js` 的 seed 枚舉 mission、plan form state 與 plan mission 也改成優先讀 `payload.next_action_label`，避免成功路徑仍用 raw `next_action`。這仍是顯示層切片，不改 crawler、download、import 或 adapter review 行為。
- 已推送：`4ffc618 Add labels to Web plan next actions`；GitHub Actions run `26539515284` 已通過 Ubuntu、Windows 與 real DB smoke。本地驗證已通過：in-memory Python syntax check OK；`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest tests.test_web_preview -v` 38 tests OK；docs mojibake scan OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，812 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_051719.log`。

## 2026-05-28 05:04 Tk listing blocked next-action label handoff
- 本輪把 Tk 爬蟲資產「清單擷取被阻擋」status bar 訊息也接到共用 next-action label。`frontends/tk/crawler_asset_workflows.py` 新增 `crawler_asset_listing_blocked_status_text()`，由 `api_launcher.crawler_asset_display.next_action_display_label()` 將 `enable_before_crawl` 等 machine action 轉成人類可讀「先啟用爬蟲資產，再枚舉 seed」。
- 這是 UI 顯示層切片，不改 crawler、repository、download 或 import 行為；目標是讓 Tk/Web/未來 Qt 都消費後端 display contract，不在使用者畫面露出 raw `next_action`。
- 已推送：`27a2072 Use labels for blocked Tk listing action`；GitHub Actions run `26538937815` 已通過 Ubuntu、Windows 與 real DB smoke。本地驗證已通過：in-memory Python syntax check OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 63 tests OK；docs mojibake scan OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，812 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_050459.log`。

## 2026-05-28 04:50 Web crawler asset next-action label handoff
- 本輪把 Web Preview 的 crawler asset card、Crawler Passport、下載器清單與缺憑證 blocked payload 都接到同一份 `next_action_label` contract。`api_launcher.crawler_asset_display` 現在提供 `next_action_display_label()`，讓 Web API 不必把 `probe_schema_then_define_bounds`、`edit_local_credentials_before_live_download` 等 raw machine action 直接交給前端顯示。
- `frontends/web/preview_api.py` 會在 asset card、credential-blocked listing、plan preview、asset download/import、seed download/import 與 blocked plan passport 回傳人類可讀 `next_action_label`；`frontends/web/static/app.js` 的 hero、passport、下載器 row 與搜尋 haystack 也優先使用 label。這是 UI-neutral display contract 對齊，不改 crawler、download 或 import 執行行為。
- 已推送：`b0a182f Add labels to crawler asset next actions`；GitHub Actions run `26538299583` 已通過 Ubuntu、Windows 與 real DB smoke。本地驗證已通過：in-memory Python syntax check OK；`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest tests.test_web_preview -v` 38 tests OK；docs mojibake scan OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，811 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_045134.log`。第一次跑 `tests.test_web_preview` 時 Windows ephemeral port 遇到一次 `WinError 10013`，重跑單條 server test 與完整 suite 均通過，判定為環境性 port flake。

## 2026-05-28 04:30 Download/import next-action label handoff
- 本輪把 formal crawler asset / seed 下載匯入結果也接到 UI-neutral next-action label contract。`CrawlerAssetDownloadImportResult.to_dict()` 現在會輸出 `next_action_label`，先使用 `api_launcher.crawler_asset_display.NEXT_ACTION_DISPLAY_LABELS` 將 `run_adapter_review_or_resolve_adapter_plan_before_downloading` 轉成「先處理 Adapter 審核或解析計畫，再下載」。
- Tk seed 下載 / 匯入完成或未完成提示改為優先顯示 `next_action_label`，避免 messagebox 把 raw machine `next_action` 丟給使用者。Web Preview 的 formal asset download/import 與 seed download/import endpoint 也會把 `next_action_label` 回傳到 top-level 與 `download_import` payload；下載器 mission 與結果列優先顯示人類可讀下一步。
- 已推送：`b504544 Add labels to download import next actions`；GitHub Actions run `26537337144` 已通過 Ubuntu、Windows 與 real DB smoke。本地驗證已通過：in-memory Python syntax check OK；`node --check frontends\web\static\app.js` OK；`py -3 -B -m unittest tests.test_crawler_asset_download tests.test_tk_dialogs tests.test_web_preview -v` 103 tests OK；docs mojibake scan OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，811 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_043200.log`。

## 2026-05-28 04:09 Tk blocked plan next-action label handoff
- 本輪把 Tk「爬蟲資產無法建立下載計畫」警告也接到後端 display payload。`frontends/tk/crawler_asset_workflows.py` 的 `crawler_asset_download_plan_summary_text()` 現在先讀 `crawler_asset_plan_outcome_payload(...).next_action_label`，避免 blocked path 把 `enable_before_building_download_plan` 這類 machine `next_action` 直接顯示給使用者。
- 新增 `tests/test_tk_dialogs.py::test_crawler_asset_download_plan_summary_blocked_uses_human_next_action_label`，鎖住 blocked summary 要顯示「先啟用爬蟲資產」，且 raw `enable_before_building_download_plan` 不得出現在使用者訊息中。
- 已推送：`ff0f283 Use labels for blocked Tk plan next action`；GitHub Actions run `26536339890` 已通過 Ubuntu、Windows 與 real DB smoke。本地驗證已通過：不寫 pyc 的 in-memory Python syntax check OK；`py -3 -B -m unittest tests.test_tk_dialogs -v` 61 tests OK；docs mojibake scan OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，809 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_041048.log`。

## 2026-05-28 03:53 Source draft next-action label handoff
- 本輪把 source pattern draft 的 next-action 顯示也收斂成 UI-neutral label。`api_launcher/source_pattern_drafts.py` 現在會在成功與 blocked review payload 中輸出 `next_action_label`、`next_action_label_zh_TW`、`next_action_label_en`；machine-readable `next_action` 保留給 JSON / agent。
- `frontends/tk/crawler_asset_workflows.py` 的 source draft 成功與保留審核訊息改成優先顯示人類下一步；成功路徑的 audit command 仍保留在「可重跑命令 / Command」行，不再把 `run_local_discovery_audit_before_catalog_promotion` 或 `review_source_profile_or_add_detector` 當主文案。
- 已推送：`032dc53 Add source draft next action labels`；GitHub Actions run `26535420927` 已通過 Ubuntu、Windows 與 real DB smoke。本地驗證已通過：不寫 pyc 的 in-memory Python syntax check OK；`py -3 -B -m unittest tests.test_source_pattern_drafts tests.test_tk_dialogs -v` 74 tests OK；`git diff --check` OK；docs mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，808 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_035402.log`。

## 2026-05-28 03:36 Tk credential next-action label handoff
- 本輪把 credential next-action label 的 UI-neutral contract 補回 Tk guard prompt。`frontends/tk/crawler_asset_workflows.py` 的 `crawler_asset_credential_summary_text()` 與 `crawler_asset_credential_guard_message()` 現在會優先讀 `display_profile.next_action_label_zh_TW/en` 或 top-level `next_action_label_zh_TW/en`，讓 Tk 顯示「先完成登入設定，再下載資料」，而不是把 `edit_local_credentials_before_live_download` 這種機器碼直接丟給使用者。
- 新增 / 更新 `tests/test_tk_dialogs.py` regression：credential summary fallback 與 guard message 都要使用人類可讀 next-action label，並確認 raw machine `next_action` 不出現在使用者訊息裡。raw `next_action` 仍保留給 JSON / event / agent debug。
- 已推送 `6403836 Use credential next action labels in Tk`；GitHub Actions run `26534494911` 的 Ubuntu、Windows 與 real DB smoke 全部 success。本地驗證已通過：不寫 pyc 的 in-memory Python syntax check OK；`py -3 -B -m unittest tests.test_tk_dialogs tests.test_local_credentials -v` 61 tests OK；`git diff --check` OK；docs mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，807 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_033736.log`。

## 2026-05-28 03:29 Credential next-action label handoff
- 本輪延續 `CredentialDisplayProfile`，把 credential `next_action` 的機器碼補成 UI-neutral 人類可讀 label。`api_launcher/local_credentials.py` 新增 `credential_next_action_label()`，`CredentialDisplayProfile.to_dict()` 現在帶 `next_action_label`、`next_action_label_zh_TW` 與 `next_action_label_en`；summary 也改用 label，不再把 `edit_local_credentials_before_live_download` 直接丟到使用者畫面。
- Web Preview 的 credential badge、credential panel 與 blocked guard banner 已改成優先讀 `display_profile` / `display_badge_label` / `display_summary_zh_TW`。這讓 Web/Tk/未來 Qt 仍保留 machine-readable `next_action` 給 agent，但 UI 呈現使用「先完成登入設定，再下載資料」這種人類可讀文案。
- 已推送 `26f7d84 Add credential next action labels`；GitHub Actions run `26533611438` 的 Ubuntu、Windows 與 real DB smoke 全部 success。本地驗證已通過：不寫 pyc 的 in-memory Python syntax check OK；`node --check frontends\web\static\app.js` OK；`py -B -m unittest tests.test_local_credentials tests.test_web_preview tests.test_tk_dialogs -v` 98 tests OK；`git diff --check` OK（僅 CRLF/LF warning）；docs mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，806 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_031946.log`。

## 2026-05-28 03:11 Credential display profile handoff
- 本輪把 credential 顯示文案從 Tk helper 再往後端收斂。`api_launcher/local_credentials.py` 新增 `CredentialDisplayProfile` 與 `credential_display_profile()`，`crawler_asset_credential_status()` 現在會輸出 `display_profile`、`display_badge_label`、`display_summary_zh_TW` 與 `display_summary_en`，讓 Tk/Web/未來 Qt 不必各自組登入徽章與摘要。
- `frontends/tk/crawler_asset_workflows.py` 的 `crawler_asset_credential_badge_label()` / `crawler_asset_credential_summary_text()` 已改為優先讀後端 payload，舊欄位只作相容 fallback。Web detail payload 測試也鎖住 credential `display_profile`，避免 Web 端日後回到自行推斷登入狀態。
- 已推送 `71ee4c8 Add credential display profile`；GitHub Actions run `26532840227` 的 Ubuntu、Windows 與 real DB smoke 全部 success。本地驗證已通過：`git diff --check` OK（僅 CRLF/LF warning）；docs mojibake scan OK；targeted syntax check 使用不寫 pyc 的 in-memory `compile()` OK（K 槽雲端 `__pycache__` 曾出現 WinError 5）；`py -B -m unittest tests.test_local_credentials tests.test_tk_dialogs tests.test_web_preview -v` 98 tests OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，806 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_030413.log`。

## 2026-05-28 02:41 Tk credential status badge handoff
- 本輪延續 Tk credential editor，把本機登入狀態前移成可掃描 UI。`frontends/tk/crawler_asset_workflows.py` 的 crawler asset 表格新增「登入」欄，取自後端 `crawler_asset_credential_status()` 的 UI-safe display payload；右側 Crawler Passport 也會顯示登入 label、已設定/總欄位數、缺少欄位與 next action。
- 儲存「登入設定 / 記住我的帳號」後，Tk 只刷新目前 asset row 與 Passport，不重新載入整張表；仍不預填、不顯示、不寫入 event log 任何明文 secret 或 masked preview。新增 helper `crawler_asset_credential_badge_label()` / `crawler_asset_credential_summary_text()`，只負責把後端 payload 轉成 Tk 文案，不複製 credential blocking policy。
- 已推送 `79a4d8d Surface Tk credential status badge`；GitHub Actions run `26531730322` 的 Ubuntu、Windows 與 real DB smoke 全部 success。本地驗證已通過：`py -B -m py_compile frontends\tk\crawler_asset_workflows.py tests\test_tk_dialogs.py` OK；`py -B -m unittest tests.test_tk_dialogs -v` 58 tests OK；`py -B -m unittest tests.test_local_credentials tests.test_tk_dialogs tests.test_launcher_ui -v` 89 tests OK；`git diff --check` OK；docs mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，805 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_024335.log`。

## 2026-05-28 02:22 Tk credential editor handoff
- 本輪把 Web Preview 的本機登入設定心流補回 Tk。新增 `frontends/tk/crawler_asset_credential_dialog.py`，以「登入設定 / 記住我的帳號」dialog 顯示後端 `crawler_asset_credential_status()` 提供的欄位、官方登入 / 申請 API Key 入口、清除已保存值與「記住我的帳號」勾選；dialog 不預填或回傳已保存明文 secret。
- `frontends/tk/crawler_asset_workflows.py` 右側 Crawler Passport 新增「登入設定 / 記住我的帳號」入口。缺登入 / API Key 時，seed 下載 guard 會先開這個本機 credential editor，不再只丟 warning 或讓使用者自己猜 `.env`；保存仍呼叫 `api_launcher.local_credentials.update_crawler_asset_credentials()`，Tk 只收集 payload。structured event 只記錄 status、counts、field names 與 next action，不記錄明文 token 或 masked preview。
- 已推送 `b1e4380 Add Tk crawler credential editor`；GitHub Actions run `26530735262` 的 Ubuntu、Windows 與 real DB smoke 全部 success。本地 targeted 驗證已通過：`py -B -m py_compile frontends\tk\crawler_asset_credential_dialog.py frontends\tk\crawler_asset_workflows.py tests\test_tk_dialogs.py` OK；`py -B -m unittest tests.test_tk_dialogs -v` 57 tests OK；`py -B -m unittest tests.test_local_credentials tests.test_tk_dialogs tests.test_web_preview -v` 96 tests OK；`py -B -m unittest tests.test_launcher_ui tests.test_tk_dialogs -v` 87 tests OK；`git diff --check` OK（僅 CRLF/LF warning）；docs mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，804 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_022421.log`。

## 2026-05-28 02:03 Tk credential guard handoff
- 本輪把 Web Preview 已有的 credential-blocking 判斷抽回 `api_launcher.local_credentials.credential_status_blocks_download()`，讓 Web/Tk/未來 Qt 不再各自維護 missing/partial/profile-required 狀態清單。Web Preview 的 `credential_status_blocks_plan()` 現在呼叫這個共用 helper。
- Tk seed 下載路徑現在會在啟動背景 worker 前呼叫 `crawler_asset_credential_status()`。若來源缺登入 / API Key，`run_crawler_asset_seed_download_import_from_ui()` 會先顯示「需要登入 / API Key」、缺少欄位、next action 與官方入口；若有官方登入 / 申請 API Key URL，會詢問是否開啟瀏覽器。這避免 Tk seed download 先送出必然失敗的 live request。
- 已推送 `2ef082d Add Tk seed credential guard`；GitHub Actions run `26529714810` 的 Ubuntu、Windows 與 real DB smoke 全部 success。本地 targeted 驗證已通過：`py -B -m py_compile api_launcher\local_credentials.py frontends\web\preview_api.py frontends\tk\crawler_asset_workflows.py tests\test_tk_dialogs.py tests\test_web_preview.py` OK；`py -B -m unittest tests.test_tk_dialogs -v` 54 tests OK；`py -B -m unittest tests.test_web_preview -v` 38 tests OK；`py -B -m unittest tests.test_local_credentials tests.test_tk_dialogs tests.test_web_preview -v` 93 tests OK；`git diff --check` OK（僅 CRLF/LF warning）；docs mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，801 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_020439.log`。

## 2026-05-28 01:44 Tk seed import path handoff
- 本輪把上一個 Web seed import badge 切片同步到 Tk。`frontends/tk/crawler_asset_seed_dialog.py` 現在會從 seed row 的 `content_display_label` / `content_import_profile.display_label` / `content_pipeline_lane` 取得後端 import path label，並在 Seed 表格新增「匯入路徑」欄；Tk 不自行推斷 CSV/ZIP/GeoTIFF 規則。
- 右側 Crawler Passport 的 seed preview 也會顯示同一個 import label，讓使用者不用打開完整表格，也能看到可匯入 SQLite、需解壓轉換、內容 Parser 待辦或 Adapter review 等處理路徑。這是 Tk/Web 顯示同步，不改 crawler、resolver、downloader 或 importer 執行行為。
- 已推送 `df10e7d Surface seed import path in Tk`；GitHub Actions run `26528721624` 的 Ubuntu、Windows 與 real DB smoke 全部 success。本地 targeted 驗證：`py -B -m py_compile frontends\tk\crawler_asset_seed_dialog.py frontends\tk\crawler_asset_workflows.py tests\test_tk_dialogs.py` OK；`py -B -m unittest tests.test_tk_dialogs -v` 52 tests OK；`py -B -m unittest tests.test_crawler_seed_registry tests.test_web_preview tests.test_tk_dialogs -v` 105 tests OK；`git diff --check` OK（僅 CRLF/LF warning）；docs mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，799 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_014549.log`。

## 2026-05-28 01:27 Seed import badge handoff
- 本輪把 `ContentImportProfile` 再前移到 seed 分頁 payload。`api_launcher.crawler_seed_registry.crawler_seed_row()` 現在會輸出 `content_import_profile`、`content_importability`、`content_pipeline_lane`、`content_next_action`、display label/tone 與 `content_review_required`，讓 Web/Tk/CLI/未來 Qt 在使用者按「下載此 seed」前就能看到可匯入 SQLite、需解壓轉換、內容 Parser 待辦或 Adapter review。
- Web Preview 的 seed row 目前會把 `content_display_label` 畫成匯入路徑 badge；規則仍在後端 `api_launcher.content_registry`，JavaScript 只 render badge。若 candidate metadata 已有 `content_import_profile` / `content_detection.import_profile`，seed row 會優先使用；否則依 `native_format`，再退到 URL suffix 做弱偵測。
- 本地 targeted 驗證已通過：`py -B -m py_compile api_launcher\crawler_seed_registry.py tests\test_crawler_seed_registry.py tests\test_web_preview.py` OK；`node --check frontends\web\static\app.js` OK；`py -B -m unittest tests.test_crawler_seed_registry tests.test_web_preview -v` 53 tests OK；`py -B -m unittest tests.test_crawler_asset_download tests.test_dataset_download_plan tests.test_adapter_plan_resolver tests.test_content_registry -v` 86 tests OK；`git diff --check` OK（僅 CRLF/LF warning）；docs mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，799 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_012837.log`。已推送 `e9b39ab Surface seed import profile badges`；GitHub Actions run `26527820441` 的 Ubuntu、Windows 與 real DB smoke 全部 success。

## 2026-05-28 01:08 Content import display handoff
- 本輪把前一輪 `ContentImportProfile` contract 接到 Adapter review / Web / Tk 顯示層，但不改 downloader/importer 執行行為。`AdapterReviewItem` 現在會帶 `content_import_profile`、`content_importability`、`content_pipeline_lane`、`content_next_action`、display label/tone 與 `content_review_required`；`adapter_review_agent_payload()` 也會統計 `by_content_pipeline_lane` 與 `by_content_importability`。
- `api_launcher.crawler_asset_display.adapter_review_display_payload()` 現在會輸出 `content_pipeline_lanes`，Web Review Workspace 新增 Import Lane 卡片，Web mission log 也會顯示匯入路徑摘要。Tk Adapter detail 會顯示 `content_pipeline_lane` 與 `content_next_action`。`plan_entry_content_status_payload()` 會優先讀 `content_import_profile` 的 label/tone/next_action，讓 Web/Tk/未來 Qt 不必各自從 raw import status 推斷。
- 本地 targeted 驗證已通過：`py -B -m py_compile api_launcher\adapter_review.py api_launcher\crawler_asset_display.py frontends\tk\dialogs.py tests\test_web_preview.py tests\test_tk_dialogs.py` OK；`node --check frontends\web\static\app.js` OK；`py -B -m unittest tests.test_web_preview -v` 38 tests OK；`py -B -m unittest tests.test_tk_dialogs tests.test_dataset_download_plan tests.test_adapter_plan_resolver tests.test_content_registry -v` 136 tests OK；`git diff --check` OK（僅 CRLF/LF warning）；docs mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，797 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_011007.log`。已推送 `53307c2 Surface content import profile in UI`；GitHub Actions run `26526948071` 的 Ubuntu、Windows 與 real DB smoke 全部 success。

## 2026-05-28 00:36 Content import profile handoff
- 本輪往宣告式 profile 架構推進，但沒有重寫 downloader/importer。新增 `api_launcher.content_registry.ContentImportProfile` 與 `content_import_profile()`，把下載物格式的 import 能力集中成 UI-neutral contract。
- 新 payload 會出現在 `ContentParserCapability.to_dict()["import_profile"]`、`ContentDetection.to_dict()["import_profile"]` 與 dataset `import_plan["content_import_profile"]`。CSV/JSON/GeoJSON 會標成 `pipeline_lane=sqlite_curated_import`、`review_required=false`；ZIP/壓縮檔會標成 `downloaded_payload_transform`；NetCDF/HDF/Zarr/GRIB、GeoTIFF/COG/GeoPackage/tiles、Parquet/Arrow、SQLite snapshot、document/unknown 會標成 content parser / adapter review。這讓 Web/Tk/未來 Qt 讀同一份 next_action，不再各自推斷內容格式。
- 本輪不改實際下載、匯入、adapter resolver 執行行為，只增加可序列化 contract。已推送 `dd360dc Add content import profile contract`；GitHub Actions run `26525140539` 的 Ubuntu、Windows 與 real DB smoke 全部 success。已驗證：`py -B -m py_compile api_launcher\content_registry.py api_launcher\plans.py tests\test_content_registry.py` OK；`tests.test_content_registry` 12 tests OK；`tests.test_adapter_plan_resolver` 54 tests OK；`tests.test_web_preview tests.test_crawler_asset_download tests.test_crawler_assets` 81 tests OK；`git diff --check` OK（僅 docs CRLF/LF warning）；docs mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，796 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_003747.log`。

## 2026-05-28 00:17 Flow comment pass handoff
- 本輪延續 2026-05-27 23:41 的註釋密度工作，做第二批不改行為的可讀性切片。已在 `api_launcher/crawler_asset_service.py`、`frontends/tk/crawler_asset_workflows.py` 與 `frontends/web/static/app.js` 補上模組 docstring、流程邊界註解與 service/UI/Web adapter 的責任說明。
- 註解重點是讓接手者看懂現有資料流：crawler asset listing 如何把 source listing 轉成 catalog candidates、seed download/import 為何先從本機 catalog 建 plan、source download options/bounds 如何轉換 UI payload、Tk workflow 為何只能呼叫 service，以及 Web Preview 為何只保存畫面 state 而不持有業務真相。
- 本輪不改函式簽名、不改 UI 行為、不改 crawler / resolver / downloader / importer 邏輯。已推送 `1a85a3f Add crawler asset flow comments`；GitHub Actions run `26524137769` 的 Ubuntu、Windows 與 real DB smoke 全部 success。已驗證：`py -B -m py_compile api_launcher\crawler_asset_service.py frontends\tk\crawler_asset_workflows.py` OK；`node --check frontends\web\static\app.js` OK；`tests.test_crawler_assets` 42 tests OK；`tests.test_crawler_asset_download` 2 tests OK；`tests.test_crawler_seed_registry` 13 tests OK；`tests.test_tk_dialogs tests.test_launcher_ui` 82 tests OK；`tests.test_web_preview` 37 tests OK；`git diff --check` OK（僅 `frontends/web/static/app.js` CRLF/LF warning）；docs mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，795 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260528_001723.log`。

## 2026-05-27 23:41 Architecture comment pass handoff
- 本輪依使用者要求提高現有檔案註釋密度，先做不改行為的可讀性切片。已在 `api_launcher/crawler_asset_bound_forms.py`、`api_launcher/crawler_capability_profiles.py`、`api_launcher/crawler_asset_display.py`、`api_launcher/crawler_asset_download.py`、`api_launcher/crawler_seed_registry.py` 與 `frontends/web/preview_api.py` 補上模組 docstring 與架構邊界註解。
- 註解重點是讓接手者看懂資料流與責任邊界：bounds facets 如何變成 form spec / payload、capability profile 為何不是 universal interpreter、display profile 為何要讓後端持有 UI 文案、formal download/import service 的邊界、seed page 為何只讀本機 catalog，以及 Web Preview 為何只能做 thin frontend。
- 本輪不改函式簽名、不改 UI 行為、不改 crawler / resolver / downloader / importer 邏輯。已推送 `5155323 Add crawler asset architecture comments`；GitHub Actions run `26522281618` 的 Ubuntu、Windows 與 real DB smoke 全部 success。已驗證：`py -B -m py_compile api_launcher\crawler_asset_bound_forms.py api_launcher\crawler_capability_profiles.py api_launcher\crawler_asset_display.py api_launcher\crawler_asset_download.py api_launcher\crawler_seed_registry.py frontends\web\preview_api.py` OK；`py -B -m unittest tests.test_crawler_assets` 42 tests OK；`py -B -m unittest tests.test_web_preview` 37 tests OK；`py -B -m unittest tests.test_tk_dialogs` 52 tests OK；`git diff --check` OK；docs mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，795 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260527_234318.log`。

## 2026-05-27 22:55 Bounds form profile handoff
- 依宣告式架構方向，將 crawler asset bounds form 的狀態收斂成 typed `CrawlerAssetBoundFormProfile`。`api_launcher/crawler_asset_bound_forms.py` 現在提供 `CrawlerAssetBoundFormProfile` 與 `crawler_asset_bound_form_profile()`，並讓 `CrawlerAssetBoundFormSpec.to_dict()` 輸出 `form_profile`。
- 這層只做 compact profile：欄位數、required/optional 欄位、facet、groups、control types、schema probe 欄位、preset ids、recommended value keys、warning codes 與 next action。完整欄位細節仍保留在既有 `fields` / `presets` / `recommended_values`，所以 Web/Tk 相容 payload 不破壞。
- 已推送 `8933534 Add crawler bounds form profile`；GitHub Actions run `26519665320` 的 Ubuntu、Windows 與 real DB smoke 全部 success。本地驗證已通過：`py -B -m py_compile api_launcher\crawler_asset_bound_forms.py api_launcher\crawler_asset_display.py tests\test_crawler_assets.py tests\test_web_preview.py` OK；`py -B -m unittest tests.test_crawler_assets -v` 42 tests OK；`py -B -m unittest tests.test_web_preview -v` 37 tests OK；`py -B -m unittest tests.test_crawler_assets tests.test_web_preview tests.test_tk_dialogs -v` 131 tests OK；`git diff --check` OK（僅 CRLF/LF warning）；docs mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，795 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260527_225749.log`。下一步可把 Web/Tk 表單狀態條逐步改讀 `form_profile`，但不需要在本切片強迫前端重寫。

## 2026-05-27 22:44 Web demo cleanup docs drift handoff
- 本輪依 Documentation Drift Guard 複查 Web demo route cleanup，修正 `PROJECT_GTD.md` 與 `DOCS_DRIFT_AUDIT.zh-TW.md` 中仍把舊 `執行真下載示範` 寫成一般使用者主流程的敘述。
- 已對齊目前 verified behavior：Web 下載器主 CTA 是正式 `下載 / 匯入目前資產`；舊 public CSV helper 只保留在 developer diagnostics `POST /api/diagnostics/real-download-demo`；舊 `/api/demo/real-download` 不再是一般 API。
- 已推送 `f251d8c Align web demo cleanup docs`；GitHub Actions run `26518617851` 的 Ubuntu、Windows 與 real DB smoke 全部 success。本地檢查：`git diff --check` OK（僅 CRLF/LF warning）；docs mojibake scan OK。此切片是文檔漂移修補，不改產品碼、不改 Web/Tk 行為。下一步可回到宣告式主線，優先做 `BoundsFormProfile` 小切片，避免 UI/Tk/Web 各自猜界域表單狀態。

## 2026-05-27 22:32 UI display profile handoff
- 依宣告式架構方向，將 plan outcome 的顯示狀態再收斂成 typed `DisplayProfile`。`api_launcher/crawler_asset_display.py` 現在提供 `DisplayProfile` 與 `plan_outcome_display_profile()`，並讓 `crawler_asset_plan_outcome_payload()` 輸出 `display_profile`，同時保留原本 `display_label` / `display_tone` / `short_label` / `summary` 欄位以免前端破壞。
- 這是 UI 狀態 contract 的第一步：後端負責 `outcome_bucket -> label/tone/summary/next_action_label`，Tk/Web/未來 Qt 只負責呈現。它不是重新設計 Web/Tk，也不碰 download/import/crawler handler。
- 已推送 `246d333 Add plan outcome display profile`；GitHub Actions run `26517816388` 的 Ubuntu、Windows 與 real DB smoke 全部 success。本地驗證已通過：`py -B -m py_compile api_launcher\crawler_asset_display.py tests\test_web_preview.py` OK；`py -B -m unittest tests.test_web_preview -v` 37 tests OK；`py -B -m unittest tests.test_tk_dialogs -v` 52 tests OK；`git diff --check` OK（僅 CRLF/LF warning）；docs mojibake scan OK。

## 2026-05-27 22:00 Crawler capability profile handoff
- 依使用者要求繼續往宣告式架構推進，但沒有重寫 crawler handler。本輪新增 `api_launcher/crawler_capability_profiles.py`，提供 `CrawlerCapabilityProfile`：把 source type、auth mode、terms risk、pagination mode、content format hints、bounds facets、middleware ids、failure policy 與 `SourceRequestPolicy` 包成可序列化 profile。
- `crawler_asset_from_source()` 現在會把這份 profile 掛到 `CrawlerAsset.capability_profile` 與 `asset.to_dict()["capability_profile"]`。這讓 Web/Tk/Qt/agent 後續可讀同一份 capability contract，不必散落 `if source_type == ...` 來猜 pagination、內容格式或缺憑證時下一步。
- 這是 `Matrix Cell -> Validated Profile -> Capability Gateway -> Middleware Pipeline` 的第一個資料契約切片，不是 universal interpreter。既有 handler、download/import、seed row UI 行為不變。
- 本輪同時修補 `scripts/pre_push_smoke.ps1`：PowerShell native command 失敗不會自動被 `$ErrorActionPreference` 擋住，所以現在 `git diff --check`、`py_compile`、`unittest discover`、CLI summary 後都檢查 `$LASTEXITCODE`。這避免 pre-push smoke 在測試失敗時繼續跑 summary/smoke 造成假綠燈。
- 已推送 `d125a3d Add crawler capability profile contract`；GitHub Actions run `26517164906` 的 Ubuntu、Windows 與 real DB smoke 全部 success。本地驗證已通過：`py -B -m py_compile api_launcher\crawler_capability_profiles.py api_launcher\crawler_assets.py api_launcher\crawlers\request_policy.py tests\test_crawler_assets.py` OK；`py -B -m unittest tests.test_crawler_assets -v` 40 tests OK；`py -B -m unittest tests.test_dataset_discovery -v` 50 tests OK；`py -B -m unittest tests.test_crawler_assets tests.test_dataset_discovery tests.test_web_preview -v` 126 tests OK；`git diff --check` OK（僅 CRLF/LF warning）；docs mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，792 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260527_221311.log`。

## 2026-05-27 21:38 Tk seed row action handoff
- 本輪把 Tk「爬蟲資產」分頁從側欄 seed 摘要推進到可操作 seed row：右側 Crawler Passport 新增「開 Seed 表格 / 下載」，會開 `frontends/tk/crawler_asset_seed_dialog.py` 的表格 dialog。Dialog 只顯示目前已載入的本機 catalog seed page，回傳 `favorite` / `download` action，不直接改 profile、下載檔案或匯入資料。
- 收藏動作走共用 `api_launcher.crawler_seed_registry.save_crawler_seed_favorite()`，下載動作走正式 `api_launcher.crawler_asset_download.run_crawler_seed_download_import()`。Tk worker 會把輸出放到 OS Downloads 底下的 `RuRuKa Asset Launcher/downloads/crawler_assets/<asset>/<seed>`，並寫出 seed resolved plan / `curated_sources.db`；避免把 live SQLite import 預設壓在 K 槽雲端同步路徑。
- 已推送 `d0b42f8 Add Tk crawler seed row actions`；GitHub Actions run `26515224421` 的 Ubuntu、Windows 與 real DB smoke 全部 success。
- 本地驗證已通過：read/compile（不寫 pyc）OK；`py -B -m unittest tests.test_tk_dialogs -v` 52 tests OK；`py -B -m unittest tests.test_tk_dialogs tests.test_crawler_seed_registry tests.test_crawler_asset_download tests.test_web_preview -v` 103 tests OK；`git diff --check` OK（僅 CRLF/LF warning）；docs mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd` 通過，792 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260527_214126.log`。

## 2026-05-27 21:05 Tk/Web seed enumeration confidence handoff
- 本輪把 listing event 內的 `seed_enumeration` / `remote_pagination` 也接到 Tk「爬蟲資產」分頁。Tk 開啟時會從 `crawler_asset_listing_recorded` structured event 恢復最近一次 seed 枚舉狀態；選取 crawler asset 時，右側「Seed 清單」會在本機 seed page 摘要之外，顯示「遠端還有下一頁線索 / 遠端已列完 / handler 尚未回報遠端完整度」這類可讀提示，且不暴露 raw pagination token。
- Web Preview 的 recent listing compact payload 也補回 `seed_enumeration` 與 `remote_pagination`，避免頁面重載後 seed bar 只剩 counts、失去後端完整度提示。這是 UI contract 修補，不重新 live crawl，也不改 download/import 行為。
- 本地驗證已通過：read/compile（不寫 pyc）OK；`py -B -m unittest tests.test_tk_dialogs -v` 48 tests OK；`py -B -m unittest tests.test_tk_dialogs tests.test_web_preview tests.test_crawler_assets tests.test_crawler_seed_registry -v` 137 tests OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 已通過，788 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260527_211759.log`。已推送 `441517f Surface seed enumeration confidence in UI`，GitHub Actions run `26513855548` 的 Ubuntu、Windows 與 real DB smoke 全部 success。`py_compile` 仍會在 K 槽 `frontends\tk\__pycache__` 遇到已知 `WinError 5` 雲端碟 cache lock，故本輪語法驗證使用 read/compile。

## 2026-05-27 20:54 Tk crawler seed page handoff
- 本輪把同一份 seed page contract 接到 Tk「爬蟲資產」分頁右側 Crawler Passport：新增「Seed 清單」區塊與「查看 Seed 清單 / 顯示更多 Seed」動作。Tk 會重用 `api_launcher.crawler_seed_registry.crawler_seed_page()`，只讀本機 catalog 已枚舉 seed，不重新 live crawl；分頁摘要、收藏星號與下一頁狀態都吃後端 payload。
- `frontends/tk/crawler_asset_workflows.py` 只負責取得選中 asset、建立 `ApiCatalogRepository`、讀取 source provider id 與顯示摘要；page clamp、favorite row、`shown_start/shown_end/remaining/next_action` 仍由後端 seed registry 決定，避免 Tk/Web/CLI/未來 Qt 各自重算。
- 本地驗證已通過：`py -B -m py_compile frontends\tk\crawler_asset_workflows.py tests\test_tk_dialogs.py` OK；`py -B -m unittest tests.test_tk_dialogs -v` 45 tests OK；`py -B -m unittest tests.test_crawler_seed_registry tests.test_launcher_ui -v` 43 tests OK；`py -B -m unittest tests.test_tk_dialogs tests.test_crawler_seed_registry tests.test_launcher_ui tests.test_crawler_assets -v` 128 tests OK。.\scripts\pre_push_smoke_brief.cmd 已通過，784 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`，log：`state\logs\pre_push_smoke_20260527_205728.log`；已推送 `d582c63 Add Tk crawler seed page preview`，GitHub Actions run `26512757129` 的 Ubuntu、Windows 與 real DB smoke 全部 success。
## 2026-05-27 20:28 Crawler seed page CLI handoff
- 本輪把 Web 已有的 seed 分頁 contract 接到 CLI：新增 `--crawler-asset-seeds ASSET_ID`、`--crawler-asset-seeds-json`、`--crawler-asset-seed-page`、`--crawler-asset-seed-page-size`、`--crawler-asset-seeds-provider-id` 與 `--crawler-asset-profile-path`。CLI 會重用 `api_launcher.crawler_seed_registry.crawler_seed_page()`，只讀本機 catalog 已枚舉 seed，不重新 live crawl。
- 若 CLI 能從 crawler asset source profile 找到 provider，使用者只需給 asset id；若找不到 source，可用 `--crawler-asset-seeds-provider-id` 明確指定 provider。阻擋狀態會回 JSON：`blocked_reason=crawler_asset_source_not_found_or_provider_id_required`、`next_action=provide_crawler_asset_provider_id_or_fix_source_profile`。
- 本地驗證已通過：`py -B -m py_compile api_launcher\cli_crawler_assets.py api_launcher\core.py api_launcher\cli_flags.py tests\test_crawler_seed_registry.py` OK；`py -B -m unittest tests.test_crawler_seed_registry -v` 13 tests OK；`py -B -m unittest tests.test_crawler_seed_registry tests.test_crawler_assets tests.test_web_preview -v` 88 tests OK；實際 CLI smoke `--crawler-asset-seeds noaa_ncei_dataset_search --crawler-asset-seeds-json --crawler-asset-seed-page-size 3` 回傳 JSON，provider id 正確解析為 `noaa_ncei_access_data`。`.\scripts\pre_push_smoke_brief.cmd` 通過，781 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`；已推送 `407525e Add crawler asset seed page CLI`，GitHub Actions run `26511610643` 的 Ubuntu、Windows 與 real DB smoke 全部 success。
## 2026-05-27 20:02 Remaining handler remote pagination metadata
- 本輪把 `DatasetCrawlerOutput` 遠端 pagination metadata 繼續延伸到 NCEI、GBIF、Dataverse、OGC API Records、STAC full-crawl handler。NCEI / GBIF / Dataverse 在本機 `max_pages` 先截斷但當前頁仍是滿頁時，現在會回報 `remote_pagination_status=has_more`、`remote_exhausted=false` 與下一個 offset/start token；OGC / STAC 在 `rel=next` 尚存在但 page cap 停止時也會回報 token-present 狀態。
- 已保留相容 API：既有 `paginated_*_candidates()` 仍回傳 list；新增 `paginated_*_output()` 與 `*_candidates_for_source()` 的 richer output 只讓 orchestrator / crawler asset listing 取得遠端分頁 metadata。這不是 live endpoint 全量成功證明，而是讓 Web/Tk/Qt 不再只靠本機 `max_results` 猜 seed 枚舉完整度。
- 已推送 `e070beb Expand remaining crawler pagination metadata`；GitHub Actions run `26510356684` 的 Ubuntu、Windows 與 real DB smoke 全部 success。本地驗證也已通過：讀檔 compile（不寫 pyc，避開 K 槽 pycache 權限問題）OK；`py -B -m unittest tests.test_dataset_discovery` 50 tests OK；`py -B -m unittest tests.test_dataset_discovery tests.test_crawler_assets tests.test_crawler_seed_registry tests.test_web_preview -v` 134 tests OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 777 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`。`py_compile` 曾因 K 槽檔案/pycache 權限回 `Permission denied`，但同檔以 read/compile 方式與測試匯入均通過。

## 2026-05-27 19:36 Remote pagination metadata expansion
- 本輪把 `DatasetCrawlerOutput` 遠端 pagination metadata 從 Socrata / CKAN 延伸到 OpenAlex、DataCite、Zenodo、CMR full-crawl handler。這些 handler 在本機 `max_pages` 先截斷但遠端明確有下一頁線索時，現在會回報 `remote_pagination_status=has_more`、`remote_exhausted=false` 與 token-present 狀態，讓 seed 枚舉 UI 不再只靠本機上限猜完整度。
- 已推送 `193f244 Expand crawler remote pagination metadata`；GitHub Actions run `26509127789` 的 Ubuntu、Windows 與 real DB smoke 全部 success。已補 regression：OpenAlex cursor、DataCite `links.next`、Zenodo `links.next`、CMR page number 都有 page-cap `has_more` 測試。已驗證：`py -B -m unittest tests.test_dataset_discovery` 45 tests OK；`py -B -m unittest tests.test_dataset_discovery tests.test_crawler_assets tests.test_crawler_seed_registry tests.test_web_preview` 129 tests OK；相關 crawler 檔案 py_compile OK；docs mojibake scan OK；`git diff --check` OK；`.\scripts\pre_push_smoke_brief.cmd` 772 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`。

## 2026-05-27 18:52 Web demo route developer-only cleanup
- 本輪把舊 Web real-download demo 從一般路由 `/api/demo/real-download` 移到 developer diagnostics 路由 `POST /api/diagnostics/real-download-demo`。舊路由現在回 404，避免使用者或 agent 把過渡 demo endpoint 誤當成正式 crawler 下載入口。
- `developer_real_download_demo()` 仍會執行同一條 public CSV regression helper，但 payload 會明確帶 `developer_only=true`、`scope=developer_diagnostic_public_csv_not_main_download_flow`，並標出正式主流程 `POST /api/crawler-assets/{asset_id}/download-import` 與 seed 流程 `POST /api/crawler-assets/{asset_id}/seed-download-import`。
- 已推送 `4796f4b Move web real download demo to diagnostics`；GitHub Actions run `26508314088` 的 Ubuntu、Windows 與 real DB smoke 全部 success。已驗證：`py -B -m unittest tests.test_web_preview tests.test_crawler_asset_download tests.test_crawler_assets tests.test_crawler_seed_registry` 86 tests OK；`py -B -m py_compile frontends\web\preview_api.py frontends\web\server.py tests\test_web_preview.py api_launcher\crawler_asset_download.py` OK；`node --check frontends\web\static\app.js` OK；docs mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd` 768 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`。

## 2026-05-27 17:44 Seed-level Web download/import path
- 本輪在已完成的 crawler asset formal download/import 基礎上，補上 seed row 層級的正式下載 / 匯入路徑。Web seed 清單現在會在每筆 seed 顯示「下載此 seed」，呼叫 `POST /api/crawler-assets/{asset_id}/seed-download-import`，把目前動態界域表單值與 `dataset_uid` 交給後端。
- 後端新增 `build_crawler_seed_download_plan()` 與 `run_crawler_seed_download_import()`：它會驗證 seed 是否屬於該 crawler asset，從 catalog seed 直接建立 formal resolved plan，套用同一份 credential gate、bounds、adapter review、download/import pipeline，且不重新打遠端 crawler。這讓使用者可以從已枚舉的可見 seed 直接進入正式下載 / 匯入。
- Web Preview 預設輸出路徑會落在本機下載資料夾的 `RuRuKa Asset Launcher Web Preview\<asset_id>\<seed>`，並寫出 `resolved_seed_download_plan.json` 與 `curated_sources.db`；這延續 K/RaiDrive live SQLite import 可能 lock 的教訓，不把展示或驗收用 SQLite 預設壓在 K 槽雲端同步路徑。
- 已推送 `7dd4570 Add seed-level web download import path`；GitHub Actions run `26504382256` 的 Ubuntu、Windows 與 real DB smoke 全部 success。已驗證：`py -B -m unittest tests.test_crawler_asset_download tests.test_web_preview`，35 tests OK；`py -B -m unittest tests.test_crawler_asset_download tests.test_web_preview tests.test_crawler_assets tests.test_crawler_seed_registry`，84 tests OK；`py -B -m py_compile api_launcher\crawler_asset_service.py api_launcher\crawler_asset_download.py frontends\web\preview_api.py frontends\web\server.py` OK；`node --check frontends\web\static\app.js` OK；docs mojibake scan OK；`git diff --check` 無 whitespace error（僅 CRLF/LF warning）；`.\scripts\pre_push_smoke_brief.cmd` 766 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`。

## 2026-05-27 16:25 Formal crawler asset download/import Web path
- 本輪把 Web Preview 下載器主 CTA 從過渡用「執行真下載示範」改成正式的「下載 / 匯入目前資產」，路由為 `POST /api/crawler-assets/{asset_id}/download-import`。它會從選取的 crawler asset 與動態界域表單建立 resolved plan，執行 direct download/import pipeline，並把 `plan_outcome`、`plan_passport`、`adapter_review`、`download_import` 與 artifacts 回傳給 Web。
- 新增 `api_launcher/crawler_asset_download.py` 作為正式 service：`asset + bounds -> resolved plan -> direct downloads -> import`。Web 只呼叫這個 service，不再把 demo CSV 當作主下載心流。舊 `/api/demo/real-download` 與 `api_launcher/web_real_download_demo.py` 暫時保留給 regression / developer demo，後續全 crawler source 更穩後再移到 developer-only 或刪除。
- Live smoke 教訓：同一條正式路徑在 K/RaiDrive 上匯入 SQLite 曾遇到 `database is locked`；改用本地 temp/downloads 路徑後成功，`download_import_completed`、`submitted=1`、`completed=1`、`imported=1`。後續 GUI/smoke/展示下載匯入仍應使用本地 clone 或本機 Downloads/Temp，不要把 live import 壓在 K 槽雲端同步路徑。
- 已推送 `87cfa21 Add crawler asset web download import path`；GitHub Actions run `26500493354` 的 Ubuntu、Windows 與 real DB smoke 全部 success。已驗證：formal endpoint live smoke 在本機 temp 路徑完成 `download_import_completed` / `submitted=1` / `completed=1` / `imported=1`；`py -B -m unittest tests.test_crawler_asset_download tests.test_web_preview -v`，33 tests OK；`py -B -m unittest tests.test_crawler_asset_download tests.test_web_preview tests.test_crawler_assets tests.test_crawler_seed_registry -v`，82 tests OK；`py -B -m unittest tests.test_dataset_discovery tests.test_source_download tests.test_ingestion_pipeline -v`，54 tests OK；`node --check frontends\web\static\app.js` OK；`py -B -m py_compile api_launcher\crawler_asset_download.py frontends\web\preview_api.py frontends\web\server.py` OK；docs mojibake scan OK；`git diff --check` OK（僅 CRLF/LF warning）；`.\scripts\pre_push_smoke_brief.cmd`，764 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`。

## 2026-05-27 15:55 Matrix/profile gateway architecture note
- 使用者補充的架構概念已收斂進 `docs/DECLARATIVE_ARCHITECTURE_DECISION.zh-TW.md`：正式命名採 `Matrix Cell -> Validated Profile -> Capability Gateway -> Middleware Pipeline`。
- 判斷：這是第二階段宣告式架構的收斂工具，不是第一階段重寫命令。第一階段仍保持 `seed -> crawler -> candidate -> plan -> download -> import -> UI`，既有 handler 保留。PoC 應先選 Socrata 或 HTML file index，輸出仍是既有 `DatasetCandidate`。
- 後續實作優先順序：UI display profile、Bounds form profile、Content parser/import profile，最後才做 crawler capability profile PoC。避免 raw matrix row、過度 `@decorator` 魔法或一次消滅所有 crawler。

## 2026-05-27 15:48 Source request policy consolidation checkpoint
- 本輪把 source profile 的 timeout / max pages / page size / rate-limit / credential mode / terms risk 收斂到 `api_launcher.crawlers.request_policy.SourceRequestPolicy` 與 `source_request_policy()`。`dataset_sources.py` 現在只消費有效 policy，再呼叫既有 handler；這是為未來 middleware / decorator pipeline 鋪 typed contract，不是改寫 crawler handler。
- 已保留既有行為：source-level max pages 仍是安全上限、page size 仍會壓低過大的 UI/CLI override、access policy 仍走白名單 normalization。已推送 `0863357 Extract source request policy helper`；GitHub Actions run `26498010323` 的 Ubuntu、Windows 與 real DB smoke 全部 success。已驗證：`py -B -m unittest tests.test_dataset_discovery tests.test_crawler_assets -v`，81 tests OK；`py -B -m unittest tests.test_dataset_discovery tests.test_crawler_assets tests.test_web_preview -v`，112 tests OK；`py -B -m py_compile api_launcher\crawlers\request_policy.py api_launcher\crawlers\dataset_sources.py tests\test_dataset_discovery.py` OK；docs mojibake scan OK；`git diff --check` OK（僅 CRLF/LF warning）；`.\scripts\pre_push_smoke_brief.cmd`，762 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`。

## 2026-05-27 15:27 Source profile access policy validation checkpoint
- 本輪在 `credential_mode` / `terms_risk` 明示欄位上補白名單 normalization：`DatasetDiscoverySource` loader 只接受 `public_or_review`、`user_credential_required`、`terms_review_required` 這類已知治理值，未知字串會被清空，`source_to_dict()` 也不會把未知 access policy 寫回 source JSON。
- `crawler_asset_capabilities.credential_mode_for_source()` / `terms_risk_for_source()` 也改吃同一組 normalizer；因此本機 source profile 若誤填 `raw-secret`、`maybe` 這類值，不會漏到 Web/Tk/Qt capability contract，而是回到既有 public/review fallback heuristic。
- 這是 source profile access policy 的防呆補強，不是新的 crawler 功能，也不改使用者 UI 操作流程。已推送 `217231a Normalize source access policy values`；GitHub Actions run `26497125509` 的 Ubuntu、Windows 與 real DB smoke 全部 success。已驗證：`py -B -m unittest tests.test_dataset_discovery tests.test_crawler_assets -v`，80 tests OK；`py -B -m unittest tests.test_dataset_discovery tests.test_crawler_assets tests.test_web_preview -v`，111 tests OK；docs mojibake scan OK；`git diff --check` OK（僅 CRLF/LF warning）；`.\scripts\pre_push_smoke_brief.cmd`，761 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`。

## 2026-05-27 15:04 Source profile access policy checkpoint
- 本輪新增 `DatasetDiscoverySource.credential_mode` 與 `terms_risk`；source JSON 會載入與寫回這兩個欄位。`crawler_asset_capabilities.credential_mode_for_source()` / `terms_risk_for_source()` 會優先讀明示 source profile 欄位，再退回既有文字 heuristic。
- 這代表登入/API key 與條款風險屬於 crawler/source profile，而不是資料集本身或 UI 猜測。`crawler_asset_source_signature()` 已納入這兩個欄位，讓保存過的 plan passport 在治理設定改變後變 stale。
- 已推送 `e98213f Add source profile access policy overrides`；GitHub Actions run `26496327588` 的 Ubuntu、Windows 與 real DB smoke 全部 success。已驗證：`py -B -m unittest tests.test_dataset_discovery tests.test_crawler_assets -v`，78 tests OK；`py -B -m unittest tests.test_dataset_discovery tests.test_crawler_assets tests.test_web_preview -v`，109 tests OK；`git diff --check` OK；docs mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd`，759 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`。

## 2026-05-27 14:54 Source profile rate-limit politeness checkpoint
- 本輪在已完成的 `crawl_timeout_seconds` / `crawl_max_pages` / `crawl_page_size` 基礎上，新增 `crawl_rate_limit_seconds`；`DatasetDiscoverySource` / source JSON 會載入與寫回此欄位，各 paginated crawler handler 會透過 `api_launcher.crawlers.pagination.polite_crawl_delay()` 在下一頁 request 前套用 source-level 延遲。
- `crawler_asset_source_signature()` 已納入 timeout、max pages、page size 與 rate-limit 欄位，避免 UI/Web/Tk 保存過的 plan passport 在來源 politeness profile 改變後仍被視為 fresh。
- 這仍是第一階段 MVP hardening，不是改成 universal interpreter。使用者提出的「數據驅動裝飾器爬蟲架構」可作為第二階段 PoC 候選；本輪實作只把可重複的 request policy guard 收斂到 source profile 與共用 helper。
- 已推送 `8962dd9 Add source profile rate limit guard`；GitHub Actions run `26495740693` 的 Ubuntu、Windows 與 real DB smoke 全部 success。已驗證：`py -B -m unittest tests.test_dataset_discovery -v`，39 tests OK；`py -B -m unittest tests.test_dataset_discovery tests.test_crawler_assets tests.test_crawler_audit_smoke tests.test_web_preview -v`，113 tests OK；`git diff --check` OK；docs mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd`，758 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`。

## 2026-05-27 14:31 Source profile page-size politeness checkpoint
- 本輪在已完成的 `crawl_timeout_seconds` / `crawl_max_pages` 基礎上，已推送 `8fec58f Add source profile page size guard`；GitHub Actions run `26494877172` 的 Ubuntu、Windows 與 real DB smoke 全部 success。修補內容：`DatasetDiscoverySource` / source JSON 現在可宣告 `crawl_page_size`，讓 Web/Tk/CLI 即使給出較大的 `max_results_override`，source profile 仍可把 per-request page size 壓低。
- 已驗證：`py -B -m unittest tests.test_dataset_discovery -v`，38 tests OK；`py -B -m unittest tests.test_dataset_discovery tests.test_crawler_assets tests.test_crawler_audit_smoke -v`，81 tests OK；docs mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd`，757 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`；GitHub Actions run `26494877172` 全部 success。

## 2026-05-27 14:15 Source profile politeness defaults checkpoint
- 本輪接續 code health audit 的 P2 hardening，已推送 `88698ad Add source profile politeness defaults`；GitHub Actions run `26494263728` 的 Ubuntu、Windows 與 real DB smoke 全部 success。修補內容：`DatasetDiscoverySource` 新增 `crawl_timeout_seconds` 與 `crawl_max_pages`，`dataset_discovery_sources*.json` 載入 / 寫回會保留這兩個欄位。
- Crawler 執行時會使用 source-level timeout；`crawl_max_pages` 視為來源層安全上限，若 CLI/UI 執行期 `max_pages` 更低，會採更低值，避免展示或完整枚舉把特定入口的 politeness boundary 放大。這是 source-profile 收斂，不是把 crawler 改成 universal interpreter。
- 已驗證：`py -B -m unittest tests.test_dataset_discovery -v`，38 tests OK；`py -B -m unittest tests.test_dataset_discovery tests.test_crawler_assets tests.test_crawler_audit_smoke -v`，81 tests OK；docs mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd`，757 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`；GitHub Actions run `26494263728` 全部 success。

## 2026-05-27 13:45 HTML file index partial warning checkpoint
- 延續 code health audit，已推送 `0294621 Keep HTML index candidates on partial crawl warnings`；GitHub Actions run `26493410406` 的 Ubuntu、Windows 與 real DB smoke 全部 success。修補內容：`api_launcher/crawlers/html_index.py` full crawl 追同網域 linked index page 時，若某個 linked page fetch 失敗，現在輸出 `index_page_fetch_failed` warning 並保留已找到的 file-shard candidates，不再讓單頁失敗吃掉整個入口的 seed 枚舉成果。
- `DatasetCrawlerOutput` 新增 `warnings` 欄位；`api_launcher/crawlers/orchestrator.py` 會把 handler-level warnings 併入 source audit，因此 UI/agent 可在 `source_results.warning_codes` 看到 partial failure，而不是只能看到 generic error。
- 已驗證：`py -B -m unittest tests.test_dataset_discovery tests.test_crawler_assets tests.test_crawler_audit_smoke -v`，79 tests OK；`git diff --check` 無 whitespace error；docs mojibake scan OK；`scripts\pre_push_smoke_brief.cmd` 755 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`；GitHub Actions run `26493410406` 全部 success。

## 2026-05-27 13:22 Code health audit / P1 hardening checkpoint
- 本輪從 `05d6b67 Record GUI audit CI checkpoint` 繼續，已推送 `9e63f6c Harden import fetch and credential writes`；GitHub Actions run `26492936566` 的 Ubuntu、Windows 與 real DB smoke 全部 success。
- 已修 P1-1：`api_launcher/importers/csv_importer.py` 的 `replace=True` 匯入不再先 drop target table；新資料先寫唯一暫存表，成功後才 swap target，失敗時保留舊 curated table。測試：`tests.test_csv_importer` 新增失敗保留舊表與成功替換 regression。
- 已修 P1-2：`api_launcher/crawlers/fetch.py` 的 crawler metadata fetch 加入 `DEFAULT_MAX_CRAWLER_RESPONSE_BYTES = 8MB`，避免 metadata probe 誤讀大型檔案或惡意 payload。測試：`tests.test_crawler_fetch` 新增超限拒絕 regression。
- 已修 P1-3：`api_launcher/local_credentials.py` 的本機 `.env` 寫入改成同目錄 UTF-8 temp file + `os.replace()`；替換失敗時清理 temp 並保留舊檔。測試：`tests.test_local_credentials` 新增 replace failure 不破壞既有檔案 regression。
- 已新增 `docs/CODE_HEALTH_AUDIT.zh-TW.md`，並更新 GTD、Docs Index、本 handoff 與 development log。此文件列出 P2 剩餘風險：HTML file index partial failure、source-profile politeness defaults、Web `真下載示範` 退場。
- 針對使用者提出的「數據驅動裝飾器爬蟲架構」：採納為宣告式架構第二階段的候選 PoC，不直接重寫現有 crawler。實作時應避免 raw list row，優先用 dataclass / profile schema；並注意裝飾器順序，若 credential 必須每頁刷新，pagination wrapper 應呼叫 credential wrapper，而不是只在整個 pagination 外層注入一次。
- 驗證已通過：targeted `py -B -m unittest tests.test_csv_importer tests.test_json_importer tests.test_ingestion_pipeline tests.test_crawler_fetch tests.test_local_credentials tests.test_web_preview -v` 共 52 tests OK；`git diff --check` 無 whitespace error；docs mojibake scan OK；`scripts\pre_push_smoke_brief.cmd` 754 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`；GitHub Actions run `26492936566` 全部 success。

## 2026-05-27 13:01 GUI-level documentation drift audit complete
- 文件漂移審計已補完 Web/Tk 實際行為對照。Verified Git state：`1e08e21 Complete documentation drift audit`，working tree 在本輪修補前為 clean / `main...origin/main`；該 commit 的 GitHub Actions run `26491482241` 已 success。
- Web Preview 實證：HTTP/API smoke 與 in-app browser 均通過。`/api/crawler-assets` 回 23 張資產卡；`/api/crawler-assets/noaa_ncei_dataset_search/seeds?page=1&page_size=50` 回 49 筆本機 seed 視窗；NASA CMR 資產 detail 回 `missing_credentials` / `需要登入 / API Key` / 3 個 credential 欄位。瀏覽器 DOM 可見四個工作區「爬蟲資產 / 下載器 / 匯入審核 / 事件紀錄」、下載器的「執行真下載示範」、NASA credential guard、官方登入入口與「記住我的帳號」流程。
- Tk 實證：`frontends/tk/window_layout_workflows.py` 顯示主分頁順序為「爬蟲資產」第一、「下載器」第二；工具選單仍有三個展示模式入口與「開發者：Crawler handler diagnostics」。Targeted headless tests 已覆蓋下載器雙擊、開始/暫停主按鈕、爬蟲資產送進下載器、developer diagnostics 與 dialog 文案。
- 驗證：`node --check frontends\web\static\app.js` OK；`py -B -m unittest tests.test_web_preview tests.test_crawler_seed_registry tests.test_tk_dialogs tests.test_launcher_ui -v` 112 tests OK；`py -B APIkeys_collection.py --handoff-report-json` 成功且 canonical MVP demo 仍為 `download_import_completed` / `row_count=3`。
- 文檔處置：`DOCS_DRIFT_AUDIT.zh-TW.md`、`PROJECT_GTD.md`、本 handoff、`DEVELOPMENT_LOG.zh-TW.md` 已補 GUI-level audit 結論；`DEVELOPMENT_LOG.zh-TW.md` 也把 12:55 文檔審計列從本地 `WORKING` 對齊到已推送 checkpoint。下一輪可回到產品主線，不需要再中斷做大規模文件審計；但每個 checkpoint 仍要做小型 docs drift check。

## 2026-05-27 12:55 Deep documentation drift audit / UTF-8 guard
- 第二輪文檔漂移審計從 `f580450 Align docs with verified drift audit` 開始，目標是把使用者文件、Web/Tk 文件、架構文件與 encoding 風險補到可交接狀態。最終 commit 請以 `git log -1` 驗證，不要把本段的起點 commit 誤讀成最新 HEAD。
- Verified behavior：`--handoff-report-json` 成功，canonical MVP demo 仍為 `download_import_completed`、`row_count=3`；`--crawler-run-summary-json` 目前是 `missing_listing`，所以若要展示某入口 seed 清單，請先重新枚舉該入口；`--dataset-discovery-handler-smoke-json` 仍顯示 14 個 supported source type 的離線 handler contract pass。
- Web Preview smoke：用 in-process HTTP server 驗證 `/api/health`、`/api/crawler-assets`、`/api/diagnostics/crawler-handler-smoke`、`/api/events/recent` 均能回應，crawler asset card 數 23，diagnostics `supported_source_type_count=14`、`candidate_case_status=pass`。這不是 live endpoint 全成功證明。
- Encoding incident：`AGENT_START_HERE.zh-TW.md` 以 Python strict UTF-8 與 `Get-Content -Encoding UTF8` 讀取正常；PowerShell 預設輸出曾顯示 mojibake，判定為 console/codepage 顯示問題。後續讀寫中文文件必須明確指定 UTF-8，不要只看預設 console 輸出就修檔。
- 本輪修補文件：`USER_GUIDE.zh-TW.md`、`WEB_PREVIEW_UIUX.zh-TW.md`、`USER_MANUAL.zh-TW.md`、`MVP_FLOW_AUDIT.zh-TW.md`、`TECHNICAL_OVERVIEW.zh-TW.md`、`ARCHITECTURE.zh-TW.md`、`DOCS_DRIFT_AUDIT.zh-TW.md`、`PROJECT_GTD.md`、本 handoff。`真下載示範` 已標成 transitional/demo-only surface，不能當作所有 crawler source 均已正式打通的證明。

## 2026-05-27 12:22 Documentation drift audit / current verified status
- Read-only drift audit confirmed an obvious stale handoff claim: this file still said latest pushed HEAD was `3ca9a37`, while verified Git state is now `170b236 Log CKAN pagination output checkpoint` on `main...origin/main`.
- Verified GitHub Actions state: `gh run list --repo Kagamihara-Ruruka/APIkeys_collection --limit 5` reports latest run `26489024004` for `170b236` completed with `success`.
- Current docs alignment patch updates `AGENT_START_HERE.zh-TW.md`, this handoff, `PROJECT_GTD.md`, `DOCS_INDEX.zh-TW.md`, `DEVELOPMENT_LOG.zh-TW.md`, and adds `DOCS_DRIFT_AUDIT.zh-TW.md`.
- Rule for next agents: do not treat older sections in this file as current truth merely because they are near the top. Prefer verified behavior plus this newest handoff section; older entries are evidence/history unless restated in the latest section.
- Known remaining drift risk: user-facing docs and older architecture/user manual files were not line-by-line validated against live Tk/Web behavior in this checkpoint. Before a showcase or UI acceptance pass, verify the actual UI and then patch user-facing docs minimally.

## 2026-05-27 Declarative architecture decision
- 已新增 `docs/DECLARATIVE_ARCHITECTURE_DECISION.zh-TW.md`。結論是採納宣告式架構作為第二階段收斂方向，但第一階段不重寫成萬能 YAML / universal interpreter。
- 目前優先順序仍是 MVP 閉環：`seed -> crawler -> candidate -> plan -> download -> import -> UI`。現有 Python adapter / service / registry 先保持可測、可用、可交付。
- 後續只在規則已穩定且重複出現時，逐步抽成 UI state contract、dynamic bounds form contract、content parser/importer capability contract、adapter review/download plan contract、feature flags、source profile metadata。Socrata 或 HTML file index 可作第一個 PoC，但必須有 fixture、blocked/unknown、zero-candidate 測試。

## 2026-05-27 Crawler handler pagination output contract
- 新增 `DatasetCrawlerOutput` 作為 handler 的相容 richer return contract。舊 handler 仍可只回傳 `list[DatasetCandidate]`；新 handler 可額外回報 `remote_pagination_status`、`remote_exhausted` 與 `remote_next_page_token`。
- `crawl_dataset_sources()` / orchestrator 會把 richer output 保留到 `DatasetSourceCrawlResult`，`run_crawler_asset_listing()` 再把第一個 source result 的遠端 pagination metadata 帶入 `CrawlerAssetListingResult` 與 `seed_enumeration` payload。
- Socrata full crawl 是第一個真 handler PoC：若 `max_pages` 安全上限截斷 catalog 枚舉，後端會回報 `remote_pagination.status=has_more`、`remote_exhausted=false`，並只向 UI 暴露 `next_page_token_present=true`，不暴露 raw token。
- CKAN full crawl 是第二個真 handler：它會用 `result.count` / `start` 判斷遠端 exhausted 或 `has_more`，讓政府開放資料入口不再只回報本機 limit 狀態。
- 本切片已用 targeted tests 驗證：orchestrator 保留 pagination metadata、Socrata / CKAN page cap 會回報 has-more、crawler asset listing payload 不洩漏 raw token。下一步是把 OpenAlex / DataCite / Zenodo / CMR 等已有 cursor、next link 或 result-count 的 handler 逐一接上，而不是在 UI 加猜測。

## 2026-05-27 Seed remote pagination contract
- `CrawlerAssetListingResult` 現在帶 `remote_pagination_status`、`remote_exhausted` 與 `remote_next_page_token`。輸出的 `remote_pagination` payload 只暴露 status、exhausted 與 `next_page_token_present`，不把 raw token 交給 UI。
- `seed_enumeration` 現在帶 `completion_confidence`。`local_limit_only` 表示達到本機安全上限但遠端未明確回報 exhausted；`remote_reported_exhausted` 表示 handler 已明確知道遠端列完。Web/Tk/Qt 不應再把 `candidate_count >= max_results` 解讀為「遠端完整」。
- 目前多數 handler 尚未實際回填遠端 pagination token / exhausted；下一步是逐一把有分頁能力的 handler 接上這個 contract，而不是在前端補 heuristic。

## 2026-05-27 Git / CI status
- 最新已推送 HEAD：`170b236 Log CKAN pagination output checkpoint`，GitHub Actions run `26489024004` 的 Ubuntu、`windows-2025-vs2026` 與 real DB smoke 全部 success。上一個功能 commit `3ca9a37 Add CKAN remote pagination output` / run `26488915209` 也成功，但已不是 latest HEAD。
- `b8b45f9 Add crawler asset web seed UX` 曾在 CI 失敗，原因是 Tk crawler listing event logging 的語法錯誤。這已由 `6be2061` 修復；後續改 Web crawler asset 時仍要至少跑 Tk import / `tests.test_launcher_ui tests.test_tk_dialogs`，避免只驗 Web targeted tests 漏掉 Tk import path。
- K 槽雲端工作區偶發 PowerShell current working directory handle 失效時，Git repo 本身不一定壞。若看到 `fatal: Unable to read current working directory`，先用 `git -C K:\APIkeys_collection status` 驗證，不要 reset、restore 或刪 lock。這次用 `git -C` 完成 add / commit / push。

## 2026-05-27 Handoff crawler handler contract summary
- `api_launcher/handoff.py` 會在 `HandoffSnapshot` 中輸出 `crawler_handler_smoke_summary`。這是 compact 摘要，不包含每個 source type 的完整 `source_results`，只列 supported source type 數、零候選 warning count、正常候選 pass count、next action 與可重跑命令。
- `--handoff-report-json` 現在能讓 heartbeat 或下一位 agent 直接看到 handler audit contract 是否仍完整；若摘要不符，先跑 `python APIkeys_collection.py --dataset-discovery-handler-smoke-json` 看完整 per-source report，再修 handler / audit / warning contract。
- 這仍是離線 contract smoke，不代表 live endpoint 可用，也不取代 `tests.test_source_patterns`、各 crawler fixture、實際 source discovery 與下載計畫驗證。

## 2026-05-27 Heartbeat crawler handler contract summary
- `api_launcher/heartbeat.py` 現在同樣輸出 `crawler_handler_smoke_summary`，並在 heartbeat Markdown report 與 agent prompt 中列出可重跑命令、supported source type 數、零候選 warning count、正常候選 pass count 與 next action。
- `python APIkeys_collection.py --heartbeat-plan-json --heartbeat-skip-ci` 可在離線 / 長工時接力時直接看到這份摘要。若 working tree 有 tracked changes，`safe_to_progress=false` 仍是正確安全行為；不要把它誤判成 crawler contract 壞掉。

## 2026-05-27 Web Preview developer diagnostics
- `api_launcher/crawler_audit_smoke.py` 現在提供共用 `crawler_handler_audit_smoke_summary()`；handoff / heartbeat / Web Preview 讀同一份 compact summary，不再各自重算。
- Web Preview 新增 `GET /api/diagnostics/crawler-handler-smoke`。這是 developer-only endpoint，只回傳 `developer_only=true`、`scope=offline_contract_smoke_no_live_network` 與 compact summary；不包含 per-source `source_results`，也不代表 live endpoint 可用。
- 已用 local HTTP smoke 確認 endpoint 回傳 `supported_source_type_count=14`、`candidate_case_status=pass`。若前端要呈現這個資訊，請放在開發者診斷區，不要混到正式使用者的 seed 枚舉 / 建立下載計畫流程。

## 2026-05-27 Tk developer diagnostics
- Tk 工具選單新增「開發者：Crawler handler diagnostics」，實作集中在 `frontends/tk/developer_diagnostics_workflows.py`，不把 diagnostics 邏輯塞回 `launcher_ui.py` 或 `dialogs.py`。
- Tk 入口讀同一份 `crawler_handler_audit_smoke_summary()`，只顯示 compact counts、next action 與可重跑 command，並寫入 `tk_crawler_handler_smoke_diagnostics_opened` structured event；不包含 per-source `source_results`。
- 這是 developer-only / offline contract smoke。若要確認 live crawler 是否能連 NASA/NOAA/CKAN 等遠端來源，仍要跑正式 crawler listing / source discovery / download plan，不要把這個 diagnostics 當成 live endpoint 成功證明。

## 2026-05-27 Developer diagnostics service
- `api_launcher/developer_diagnostics.py` 現在是 Tk / Web / 未來 Qt 的 diagnostics surface payload 共用入口。`crawler_handler_smoke_diagnostics_payload(surface)` 會套同一組 `purpose`、`diagnostic_id`、`developer_only`、`scope`、compact summary 與 next action。
- Web Preview 的 `/api/diagnostics/crawler-handler-smoke` 與 Tk 工具選單都只負責傳入自己的 `surface`；不要在前端再複製 `diagnostic_id`、scope 或 next-action 字串。

## 2026-05-27 Crawler audit contract smoke
- `api_launcher/crawler_audit_smoke.py` 新增離線 handler audit contract smoke。它用 fixture source 覆蓋所有 `SUPPORTED_DATASET_SOURCE_TYPES`，並透過注入式 crawler runner 驗證兩件事：零候選要產生 `zero_candidates` / `repair_crawler_query_or_parser`；正常候選要通過 audit summary。這不打 live endpoint，也不取代每個 handler 的 payload fixture 測試。
- CLI 新增 `--dataset-discovery-handler-smoke-json`，輸出 agent-readable JSON。若後續新增 crawler handler，這條 smoke 應立刻能指出 source type 是否漏掉 audit status、warning code 或 next_action 交接。
- `crawl_dataset_sources()` 現在支援可選 `source_crawler` 注入。正式流程仍走 `default_source_crawler()`；測試與 contract smoke 才使用替身，避免為了驗 audit layer 而連外。

## 2026-05-27 Source Pattern / Crawler Asset registry coverage
- `api_launcher/crawlers/source_patterns.py` 已補上 NCEI、GBIF、Dataverse、Zenodo、DataCite、OpenAlex 的 URL shape detector。這些 detector 只做入口類型辨識與 source type hint，不下載資料，也不取代 crawler audit。
- `SOURCE_TYPE_HINTS` 現在由測試鎖成完全覆蓋 `SUPPORTED_DATASET_SOURCE_TYPES`。新增 crawler handler 時，必須同步補 detector hint、source draft 正規化、bounds facet、surface label 與測試；不要讓「handler 有了但貼 URL 建來源草稿仍 unknown」再發生。
- `tests.test_source_pattern_drafts` 已確認 vendor/science API URL 在 fake fetcher / no live network 下可建立 supported local source draft，並正規化到對應 crawler endpoint。這是 URL -> source draft -> crawler audit 的第一段閉環，不代表正式 catalog promotion 或下載。
- `api_launcher/crawler_assets.py::SOURCE_SURFACE_LABELS` 與 `api_launcher/crawler_asset_bounds.py::SOURCE_BOUND_FACETS` 現在也由測試鎖成覆蓋所有 supported source type。後續若 UI 出現 raw `source_surface` 或弱表單，先查這兩個 registry。
- Web Preview 修正了無動態界域欄位時 build-plan 按鈕被反向停用的 bug；`surfaceLabel()` 也補上 `file_index`、`map_service`、`catalog`。如果前端看起來「點不了建立計畫」，先檢查 credential guard 與 `selectedAssetId`，不要再回到舊的反向 disabled 判斷。
- Web Preview 的爬蟲資產選取現在預設觸發 seed 枚舉，而不是要求使用者先按「更新」。後端以 `complete_seed=true`、`full_crawl=true`、`max_results=1000` 嘗試列出入口 seed，並將候選 upsert 到本機 catalog。
- Web 新增 `/api/crawler-assets/{asset_id}/seeds?page=&page_size=50`，右側 seed 清單只讀本機已枚舉候選並以 50 筆為一個視窗展開。這個 endpoint 不重新打遠端 crawler；「顯示更多 seed」只是顯示下一批已枚舉結果。
- Seed 清單分頁已抽到 `api_launcher/crawler_seed_registry.py`。`frontends/web/preview_api.py` 只負責解析 asset / DB / profile，真正的 asset filter、page clamp、row payload、favorite 判斷都由後端 service 產生。後續 Tk/Qt 若要顯示 seed 清單，請直接用這個 module，不要複製 Web endpoint 內部邏輯。
- Seed page payload 現在包含 `page_summary`：`shown_start`、`shown_end`、`remaining`、`page_count`、`next_page`、`next_action`。前端做展開清單或動態 bar 時應吃這份後端摘要，不要自己用 `page * page_size` 重算。
- 收藏對象已改為 seed。Web 目前透過 `/api/crawler-assets/{asset_id}/seed-favorites` 進入 `save_crawler_seed_favorite()`，再寫入 crawler asset profile 的 `favorite_seed_uids`；UI 不應直接呼叫 profile helper 或自行知道 profile 欄位名稱。後續若要產品化，應延伸 seed registry 查詢 / 狀態 payload，而不是收藏 crawler asset 入口。
- `CrawlerAssetListingResult.to_dict()` 與 listing event context 現在包含 `seed_enumeration`：`status`、`display_tone`、`label`、`help`、`limited_by_max_results`、`candidate_count`、`max_results`。Web/Tk/Qt 應呈現這份後端 payload，不要用 `candidate_count >= max_results` 之類的前端 heuristic 自行推論。
- 當 `seed_enumeration.status=local_limit_reached` 時，意思是「達到本機安全枚舉上限，遠端可能還有更多」，不是錯誤，也不是入口失效。下一步應是縮小界域、提高上限，或等 handler 層補遠端 pagination / exhausted 狀態。
- UI 文案請避免回到「更新資料清單」作為主流程。入口卡片可以保留「重新枚舉 seed」作為次要刷新，但使用者選入口時就應能看到已枚舉的 seed 清單。

## 2026-05-26 Crawler run record handoff payload
- `api_launcher/crawler_run_records.py` 現在提供 compact `crawler_run_record()`，用同一份 payload 描述 crawler listing 與 download-plan build 的 stage、status、outcome bucket、候選/下載/review/error/warning/duplicate counts、signature、`next_action` 與穩定 `record_key`。
- `CrawlerAssetListingResult.to_dict()` 與 `CrawlerAssetDownloadPlanResult.to_dict()` 都已輸出 `run_record`。下一位 agent / Tk / Web / Qt 應優先讀 `payload["run_record"]` 做狀態交接，不要各自從 `candidate_count`、`warning_count`、`outcome_bucket` 等分散欄位重新推理。
- Tk 與 Web Preview 的 `crawler_asset_plan_outcome_recorded` structured event context 現在也會帶 `run_record`。外部 agent 若從 event log 或 `/api/events/recent` 接手，應先讀 `context.run_record` / `context_summary.run_record`，再決定是否需要重建 plan 或補正式 run registry。
- Tk 清單擷取完成後也會寫入 `crawler_asset_listing_recorded` structured event，保存 bounded counts、`next_action` 與 `run_record.stage=crawler_listing`。接手時若要理解「剛剛 crawler 找到多少候選」，先讀這個 event，不要只看 status bar 或重新跑遠端 crawler。
- Web Preview `/api/events/recent` 現在也會保留 listing event 的候選/upsert/skip/duplicate/warning/error counts 與 compact `run_record` counts。接手 agent 若沒有 Tk 畫面，可直接讀 Web 事件摘要或完整 JSONL；不要因為缺 UI 狀態就重跑遠端 crawler。
- `--handoff-report` / `--handoff-report-json` 現在會在 `crawler_run_summary` 列出最新 listing 與 download-plan build 的 bounded counts、compact `run_record`、`next_action` 與 `resolved_plan_available`。接手優先順序是 handoff JSON -> Web `/api/events/recent` -> 完整 JSONL；不要為了找上一輪 crawler 狀態先重跑遠端來源。
- `api_launcher/crawler_run_records.py` 現在集中提供 `crawler_run_context_summary()` 與 `crawler_run_event_summary()`；Web Preview 與 handoff 已共用這組白名單摘要。後續 Qt/Tk/agent 不要再自行複製 `run_record` / `content_review` / counts 壓縮規則。
- `--crawler-run-summary-json` 是更輕的狀態查詢入口，只讀 structured event log 並輸出最新 listing / download-plan build summary；預設掃描最近 5000 筆事件，避免被 CI/smoke/log-only 事件淹沒。若任務只需要 crawler run counts / next_action，先用這個；若還需要 catalog、GTD、MVP readiness，再讀完整 `--handoff-report-json`。
- `crawler_run_summary.summary_scope` 會標示這次讀了多少 structured events、是否找到 latest listing / latest plan build、各自 event timestamp、`status`、`missing_event_names` 與 `next_action`。這是交接視窗證據，不是 freshness 判斷；若要判斷是否過期，後續應另做 stale policy。
- `crawler_run_record_from_result()` 是降級式 helper：result 沒有 `to_dict()`、`to_dict()` 拋錯、或 payload 不含 dict 型 `run_record` 時會回傳 `{}`。UI/event logging 不應因 run-record handoff 缺失而中止主要 plan outcome 記錄。
- 這仍是 handoff / structured event 層，不是永久 DB migration。`storage_lane=structured_event_log` 與 `future_sqlite_table=crawler_run_registry` 是後續 run registry 表設計的對齊提示；目前不要新增 SQLite 表或把它當成已完成 registry persistence。

## 2026-05-26 Source Pattern Draft review payload
- `api_launcher.source_pattern_drafts.SourcePatternDraftError` 現在是 URL -> source draft 擋板的結構化例外。遇到 unknown、低信心、缺 `source_type_hint` 或 unsupported crawler source type 時，不會寫 local source draft；例外的 `to_dict()` 會輸出 `review_reason`、`minimum_confidence`、`source_pattern_detection`、`skipped` 與 `next_action=review_source_profile_or_add_detector`。
- CLI `--write-source-draft-from-url ... --write-source-draft-json PATH` 在上述 blocked review 情況會先寫出 blocked summary JSON，再保留失敗狀態。下一位 agent 應讀 JSON 判斷要補 source profile、調整 detector，或新增 pattern/adapter，不要只從 traceback 推理。
- UI/Tk/Web/Qt 若接這個路徑，應呈現 `review_reason` 與 `next_action`，並把 `source_pattern_detection.evidence` 作為診斷細節；不要把 unknown/low-confidence URL 硬寫進 catalog 或下載器。
- Tk 爬蟲資產分頁已接上這個 structured review：`SourcePatternDraftError` 會顯示 warning dialog 與 status，並寫 `source_pattern_source_draft_blocked` warning event；只有真正未預期例外才走 `showerror` / `log_exception`。

## 2026-05-26 Crawler Asset status gates
- `api_launcher.crawler_asset_health.CrawlerAssetHealth` 現在帶 `status_gate`，把 crawler asset 狀態收斂成 UI-neutral gate：archived -> `restricted`、disabled/unknown -> `staged`、missing handler -> `adapter_review`、needs bounds/review-needed -> `review`、healthy -> `completed`。
- Tk/Web/Qt/agent 後續應讀 `asset.health.status_gate` 做任務分流，不要各自從 `status_code`、`risk_tier`、`maturity` 或 capability status 重建 gate。`status_code` 仍保留給細節與 debug。

## 2026-05-26 Plan Passport stale guard
- 本輪新增 profile-backed plan passport stale 判斷：`update_crawler_asset_plan_passport()` 會保存 `saved_at`、`profile_state`、`stale=false`，`crawler_asset_plan_passport_for_profile()` 會在 asset 停用、封存或 profile state 改變時輸出 `stale=true` 與 `stale_reason`。
- `load_crawler_assets()` 現在回傳 display-safe passport；Web/Tk 只呈現 stale 狀態，不自行判斷規則。這是之後 Qt 換皮時可共用的 payload。
- stale 判斷已延伸到 `source_signature` 與 `bounds_signature`：來源 endpoint/source type/file regex 等欄位改變會輸出 `source_changed`，界域 facets 改變會輸出 `bounds_schema_changed`。這些簽名由後端生成，UI 不應自行重算。
- stale payload 已補 `stale_label` 與 `stale_next_action`，讓 Web/Tk/未來 Qt 顯示「資產已停用 / 來源設定已改變 / 界域表單已改變」這類可讀提示，而不是把 raw `source_changed` 丟給使用者。
- Tk Crawler Passport 摘要已改成優先呈現同一份 `stale_label` / `stale_next_action`；若後續改 Qt 或 Web，不要直接顯示 raw `stale_reason`，它只保留給 agent/debug 對照。
- Web Preview 的下載器列與 Plan Passport 面板也已加上 `stalePassportLabel()` / `stalePassportNextAction()` fallback；缺 display-safe label 時只顯示中性重建提示，不再把 raw `stale_reason` 串進主要 UI。後續 Web/Qt 新元件應沿用 display-safe helper，不要重開前端翻譯表。
- `SourceDownloadPlanBuild` 現在會在每次建立 plan 時保存候選清單 snapshot digest：`candidate_snapshot_signature` / `candidate_snapshot_count` 會進入 compact `plan_passport`，用來追溯本次計畫由哪一批 candidate metadata / version / source URL 形成。
- 重要邊界：候選 digest 只代表「當次 crawl 的快照」。`load_crawler_assets()` 不會重爬遠端；`candidate_snapshot_changed` 只會在使用者 explicit fresh crawl / rebuild plan 時，由 `build_crawler_asset_download_plan()` 比較上一版 profile 護照與本次 digest 後輸出。
- Web Preview 下載器列與 Plan Passport 面板、Tk Crawler Passport 摘要已接上 `candidate_snapshot_changed` 顯示。後續 Qt 只需要呈現這個 compact passport 欄位，不要在 Qt 端重跑 crawl 或自行比較 digest。
- 已補 regression 鎖住「相同候選快照不算變更」：同一批 candidate metadata/version/source URL 重新建 plan 時，`candidate_snapshot_changed=false`。未來若改 candidate digest、resolver 或 profile 寫回流程，請保留這條防線，避免 UI 把所有 rebuild 都誤導成候選清單變更。
- 已補測試：profile compact persistence、disabled asset stale、source_changed stale、bounds_schema_changed stale、candidate snapshot digest stability、Web persisted signature payload、Tk summary stale text、Web stale display label。

最後更新：2026-05-26

接手時先讀 `docs/AGENT_START_HERE.zh-TW.md`，再讀本文件與 `PROJECT_GTD.md`。這份文件是跨 Windows、macOS、不同 Agent 接力時的固定接力卡；每次切換機器或切換 Agent 前，請優先更新這份文件。

## 2026-05-26 Web Preview / 後端流程視覺化

- Web Preview 目前已從 `tem/ui-aseat-ui` 只吸收構圖與互動節奏，產品語彙已收斂回 RRKAL：爬蟲資產、資產護照、界域輸入、下載計畫、本機互動紀錄、後端 JSON。
- `api_launcher/crawler_asset_display.py` 現在負責 crawler asset 的 UI 共用顯示 schema：`flow_steps`、capability `display_label`、bound field `display_label` / `display_help`、`plan_outcome` 與 Adapter review `by_outcome` 顯示摘要都由後端產生；Web/Tk/Qt 只負責呈現，不自行推測 readiness。
- Web Preview 動態界域表單現在會依同一份 `group_display` 分組渲染，後端提供「版本控制、資料集選擇、時間界域、空間界域、擷取上限」等群組文案；這是未來 Qt/QSS 表單語彙的前導，不要在 JS 或 Tk 中另寫 bounds group 規則。
- Web Preview `/api/health` 現在會回報實際綁定的 `host`、`port`、`url`、原請求 port、`port_scan` 與 `port_scanned`。前端總覽與本機互動紀錄會顯示實際 `host:port`；如果 8765 被其他 agent / IDE Live Preview / clone 占用，請用這個欄位確認實際服務，不要終止不明程序。
- Web Preview 中寬度版面已修正：側欄不再以 `font-size: 0` 隱藏中文標籤，980px 以下會把側欄轉成頁首控制區，來源篩選改成多欄且有高度上限。後續改 CSS 時要維持「第一屏看得到主工作區、nav 文字可讀」這個 guard。
- Web Preview 卡片牆現在會在本次 session 建立下載計畫後顯示 `plan_outcome` 徽章：文字吃 `short_label`，色調吃 `display_tone`，若 `content_review.has_review` 也會顯示內容格式待辦徽章。頁面重載後，`frontends/web/preview_api.py` 會讀近期 `crawler_asset_plan_outcome_recorded` structured event，轉成 `latest_plan_outcome` 放回卡片 payload；本頁 session 內的新結果仍優先於 event log。Web Preview 自己執行 `execute=true` 也會寫同一種 compact event，但只記 badge/context 與 `resolved_plan_available`，不把完整 resolved plan 放進 JSONL。不要把跨 session 狀態塞進 JS localStorage；更正式的持久狀態應回到 asset profile / backend service。
- 選中資產的 hero 與右側資產護照也會呈現 `latest_plan_outcome` 摘要；JS 只渲染後端的 label/tone/counts/content-review badge，不依 outcome bucket 寫前端業務分支。
- Web Preview 已補 `planOutcomeLabel()`、`planPassportLabel()` 與 `reviewOutcomeLabel()` fallback；缺後端 display label 時只能顯示中性文案，不要把 raw `outcome_bucket` 當作 UI 主文案。raw bucket 應留在 JSON / detail / agent debug。
- `frontends/web/preview_api.py` 的 `execute=true` plan preview 現在會回傳 compact `plan_passport`，由 `api_launcher/crawler_asset_display.py::crawler_asset_plan_passport_payload()` 產生。它整理 resolved-plan presence、candidate/direct/review/content-review counts、credential/missing-provider counts、bounds 與 next action，但刻意不包含完整 `providers` / resolved plan body。下一步若要更正式，應把這份 passport 視覺化到 Web/Tk/Qt 卡片護照，或評估回寫 asset profile；不要在 Web session 裡累積完整 plan 狀態。
- Web Preview 右側資產護照已顯示 session-local `plan_passport` 面板。瀏覽器驗證時 8765 被占用，server 透過 `--port-scan` 自動使用 `http://127.0.0.1:8766/`；建立 NOAA NCEI plan 後，護照面板顯示 `PLAN PASSPORT`、Candidates 49、Direct 69、Review 0、Adapter 39、內容待辦 39，JSON inspector 也含 `plan_passport`。測試時只停止本次啟動的 PID，不要終止未知 port 使用者。
- Web Preview crawler asset card/detail 現在會優先從 asset profile 讀回 compact `latest_plan_passport`，再退回近期 `crawler_asset_plan_outcome_recorded` event。`frontends/web/preview_api.py` 只允許白名單欄位進入前端 payload，完整 `providers` / resolved plan body 不會從 profile 或 event log 回灌到 UI；因此頁面重載後的「下載器」分頁可顯示真實計畫護照摘要。
- Tk Crawler Passport 也已接上同一份 compact `plan_passport`：送進下載器後會寫入 asset profile 的 `latest_plan_passport`，並同步記在 `crawler_asset_plan_passports` 與 `crawler_asset_plan_outcome_recorded` event context。重開 UI 可從 profile / 最近事件還原，右側 passport 顯示候選、可下載、待 Adapter、內容待辦、憑證阻擋與缺 Provider 摘要。完整 resolved plan 仍只留在 review/download path；下一步要處理 stale 判斷，不要擴大保存內容。
- Web Preview 側欄目前四個工作區都已啟用：`爬蟲資產` 是原本的界域/資產護照主流程；`下載器` 只視覺化已建立的 `plan_outcome` / `plan_passport`；`匯入審核` 只視覺化最近 plan build 回傳的 Adapter review / content parser 待辦；`事件紀錄` 讀 `/api/events/recent` 的 bounded structured event 摘要。這是 UIUX 前導層，不是正式 Web downloader；不要在 `app.js` 內新增下載、匯入或 adapter 判斷規則。
- 事件紀錄分頁的 chip 會優先顯示 `run_record` 與 crawler/download 核心 counts；前端只負責排序摘要，不自行推導 run 狀態。
- `frontends/web/static/app.js` 已改成優先使用後端 `display_label` / `display_help` / `display_tone` / `summary`，只把本地對照表留作 fallback，避免 mojibake label 或平台差異直接污染 UI。
- Web Preview 現在有登入式本機登入設定流程：右側資產護照以「登入設定 / 記住我的帳號」作為主語言，顯示已設定、尚未記住帳號、官方文件與註冊連結；`.env` 只保留在技術層與後端說明，不作為主按鈕文案。`/api/crawler-assets/{asset_id}/credentials` 可讀遮蔽狀態並寫入本機 ignored credential file。缺登入 / API Key 時，`/plan-preview?execute=true` 會先回傳 `credential_setup_required`，不呼叫 live crawler；前端按「建立下載計畫」會改成開登入設定表單。表單提供官方登入/申請入口、三步驟登入說明與「記住我的帳號」勾選；勾選時保存到這台電腦，取消勾選時只寫入目前 process env。後端界線在 `api_launcher/local_credentials.py`；UI 只送 env var values / clear list / remember flag，event log 與 API response 不保存明文。這是早期本機開發便利入口，不是遠端 OAuth 或多使用者 credential vault。
- 已驗證：`node --check frontends\web\static\app.js`、`py -B -m unittest tests.test_web_preview tests.test_source_patterns tests.test_source_pattern_drafts tests.test_dataset_discovery tests.test_crawler_assets`、臨時 pycache `py_compile`、Web Preview HTTP smoke。
- Tk 的爬蟲資產分頁已開始使用同一份 display schema：表格短狀態改取 `plan_outcome.short_label`，避免 Tk/Web/Qt 各自維護 outcome bucket 文案。下一位 agent 若繼續 Web/Tk/Qt 對齊，優先把 Adapter resolving 結果回寫成卡片 badge / 待辦徽章；不要把外部參考命名搬回 UI。
- Tk Adapter 待辦表格也已開始使用共用 display schema：表格 outcome 欄顯示 `adapter_review_outcome_label()` 的人類可讀短標籤，detail 仍保留 raw `outcome_bucket`，所以 UI 不再把 `source_resolution_required` 直接丟給使用者，但 agent 仍可複製細節比對 JSON。
- Adapter Review 現在也帶出 content parser 摘要：`adapter_review_agent_payload()` 的 item 與 summary 會包含 `content_source_format`、`content_parser_id`、`content_review_bucket` / `by_content_review_bucket` / `by_content_parser`，Tk detail 也會顯示內容格式、parser id 與 parser review bucket；Web Preview 的 Adapter review display payload 也會輸出 `content_review_buckets` / `content_parsers`，JS 任務列會顯示「內容格式待辦」。下載器面板 import 欄位也已改用 `plan_entry_content_status_payload()`，避免把 `manual_review_required` 這種 raw 狀態丟給使用者。爬蟲資產表格、Passport 與建立下載計畫後的 popup 摘要也會顯示 resolved plan 的 `content_review_label`；`crawler_asset_plan_outcome_payload()` 另外提供 `content_review` badge payload（label / tone / count / has_review），後續 Tk/Web/Qt 不需要各自推理待辦徽章。Tk `crawler_asset_plan_outcome_recorded` structured event 也會寫入這個 badge payload；事件恢復時可優先讀 badge label，舊事件仍可從 resolved plan 回推內容格式待辦。Web Preview 的界域表單狀態列也已直接吃 `plan_outcome.content_review`，建立下載計畫後會顯示同一份內容格式待辦 badge。下一步再把同一組欄位整理成正式 card badge / resolved-plan passport 元件。

## 2026-05-25 Web Preview / UIUX 對照層

- 本輪新增 `frontends/web/`，作為 HTML/CSS UIUX 對照層。它不是第二套 Web 版後端，也不是要取代 Tk；目前只用 stdlib HTTP server 暴露 crawler asset JSON endpoints，讓瀏覽器能呈現來源清單、Crawler Passport、動態界域表單與後端 JSON 結果。
- 啟動方式：`scripts\run_web_preview.cmd`，或手動執行 `py -B -m frontends.web.server --host 127.0.0.1 --port 8765 --open`，然後開 `http://127.0.0.1:8765/`。
- 業務邏輯仍屬於 `api_launcher`。Web Preview 只經過 `frontends/web/preview_api.py` 呼叫 `load_crawler_assets()`、`build_crawler_asset_bound_form_spec()` 與 `build_crawler_asset_download_plan()` 等既有 service；不要在 `app.js` 裡重寫 crawler、resolver、downloader 或 importer 規則。
- `execute=false` 的 plan preview 只驗證界域 payload，不觸發 live crawler；`execute=true` 才會呼叫後端建立下載計畫，結果仍會依 direct download / adapter review 規則處理。
- 相關文件已新增 `docs/WEB_PREVIEW_UIUX.zh-TW.md`，並在 GTD / Docs Index 記錄這條開發路線。後續若同步 Tk 與 Web Preview，請先確認 service contract，再分別接 UI 外殼。Tk 可以維持穩定樸素的控制台語言；Web Preview 可以更自由地實驗視覺、卡片、Passport、任務佇列與未來 QSS token，但不得分叉後端規則。
- Web Preview 靜態 UI 只保留 `tem/ui-aseat-ui` 的布局節奏：左側來源範式、中央爬蟲資產卡片牆、右側資產護照 / 界域表單、下方本機互動紀錄 / 後端 JSON。外部參考詞彙不再作為 RRKAL 可見語言；若後續要加互動，仍要先接 `frontends/web/preview_api.py` 或共享 service，不要在 `app.js` 重寫 crawler 規則。
- Web Preview server 現在支援 port fallback：預設 `8765`，若被其他前端 agent、IDE Live Preview 或另一份 clone 占用，會依 `--port-scan` 往後找可用 port 並印出實際 URL。不要終止不明程序；不同專案資料夾用不同 port 即可並行。

## 2026-05-25 爬蟲資產 UI 狀態收斂

- 本輪在 `api_launcher/crawler_asset_service.py` 補上 `CrawlerAssetDownloadPlanResult.outcome_bucket` 與 `user_next_action`，把爬蟲資產送進下載器的結果固定成後端狀態桶：`ready_to_download`、`partial_review_required`、`review_required`、`zero_candidates`、`empty_plan`、`blocked`。
- `frontends/tk/crawler_asset_workflows.py` 現在只顯示後端狀態，不再用 Tk 自己解析 resolved plan。可直接下載時會提示去下載器用開始 / 暫停；仍需 Adapter 待辦時會提示開 Adapter review 或調整界域；零候選會提示放寬時間 / 空間 / 筆數條件。
- Tk 爬蟲資產表格的「下一步」欄與右側 passport 現在會保留同一輪送進下載器的短狀態，例如 `已加入`、`待 Adapter`、`零候選` 或 blocked reason；compact `plan_passport` 也會寫入 asset profile 與 structured event，重開 UI 後可從 profile / event-log 還原顯示。長期跨 session 的正式保存只允許 compact 狀態欄位，不保存完整 plan。
- Crawler Passport 右側新增「開本次 Adapter 待辦」入口；它讀取同一輪爬蟲資產建立的 resolved plan 並交給既有 `AdapterReviewDialog`，不從 Tk 重新解析 plan，也不要求使用者先去全域 Adapter menu 找剛才那一批待辦。
- Tk 會寫入 `crawler_asset_plan_outcome_recorded` structured event，內容含 `asset_id`、`outcome_bucket`、`outcome_label`、`review_queue_count`、`content_review`、compact `plan_passport`、`resolved_plan` 與 `user_next_action`；重開 UI 後 crawler asset 分頁會從最近事件恢復短狀態、passport 摘要與 resolved plan，這是後續卡片 badge / event-log persistence 的基礎。
- 新增 headless 測試鎖住 review-required 與 ready-to-download 的使用者提示，也補上 service outcome bucket 的 regression。下一輪若做 Qt 或卡片牆 badge，請沿用 `outcome_bucket`，不要重新寫一套 UI 判斷。

## 2026-05-25 Crawler asset / download plan registry 收斂

- 歷史穩定 checkpoint：`734deb1`（`Preserve fragments in crawler query URLs`），GitHub Actions run `26400477554` 已成功；這不是目前 latest HEAD。目前 latest HEAD 以本文件最上方的 current verified status 為準。
- `api_launcher/crawlers/fetch.py::search_endpoint_url()` 現在用 URL parser 寫回 query，會把新增查詢參數放在 `#fragment` 前面，並在沒有有效參數時原樣返回。後續 crawler URL 組裝應走共用 helper 或範式專屬 normalizer，不要用手寫字串相加。
- CLI `--source-draft-detector-min-confidence` 現在也引用後端 `DEFAULT_PATTERN_MINIMUM_CONFIDENCE`。命令列、Tk 表單與 detector service 共用同一個人工 review 門檻；後續不要在 CLI/UI 入口各自硬寫 detector threshold。
- Tk source draft dialog 與 crawler asset workflow 現在引用後端 `DEFAULT_PATTERN_MINIMUM_CONFIDENCE`，不再在 UI 端硬寫 `0.35`。後續若調整 detector threshold，先改 `api_launcher.crawlers.source_patterns` 的契約與測試，UI 只吃服務層預設。
- `api_launcher/source_pattern_drafts.py` 會在寫 local source draft 前二次檢查 detector confidence；即使 detector 回傳非 unknown 且帶 `source_type_hint`，低於 `DEFAULT_PATTERN_MINIMUM_CONFIDENCE` 仍停在 review。這條防線避免測試替身、外部 detector 或 plugin adapter 繞過 unknown fallback。
- `api_launcher/crawlers/source_patterns.py` 現在集中 unknown fallback 與最低信心門檻為 `UNKNOWN_PATTERN_ID` / `DEFAULT_PATTERN_MINIMUM_CONFIDENCE`；`source_pattern_drafts.py` 與 detector regression tests 已共用同一契約，後續不要在 adapter、UI 或 source draft 裡硬寫 `"unknown"` / `0.35`。
- `api_launcher/crawlers/source_patterns.py` 的 detector 入口現在也會 guard 注入式 fetcher 例外；自訂 fetcher、未來 plugin probe 或測試替身若拋錯，會降級成 `unknown` / review，而不是中止整段 discovery。新增測試已覆蓋 fetcher exception 與 malformed JSON。
- Crawler asset bounds 的 `version` 欄位已接到真實版本選擇：`source_download_options_from_crawler_asset_payload()` 會把 source-level version facet 轉成 `selected_versions["*"]`，`selected_version_options()` 會套用到 crawler 回傳的 dataset。`version_limit` 已拆成獨立 facet，預設 `1` 只代表最多取一個版本，不會被 Tk/Web 表單預設值誤當成版本 `"1"`。這是暫時的 source-level selector；未來 dataset-specific UI 可以覆蓋它，不要再把版本文字誤塞成 `version_limit`。
- `api_launcher/crawlers/source_type_registry.py` 現在集中 HTML/file-index 來源類型判斷，提供 `source_type_is_file_index()` 與 `source_uses_file_index()`；bounds facet、crawler asset capability 與 source draft 都應共用這組 helper。
- `api_launcher/plans.py` 已把 CMR collection 與 DataCite/OpenAlex research metadata 的 adapter-review 擋板命名成 `CMR_COLLECTION_*` 與 `RESEARCH_METADATA_*` registry/set；後續不要把 DOI/OpenAlex/NASA CMR 特例直接塞回 UI 或 resolver 分支。
- 驗證紀錄：`tests.test_crawler_fetch tests.test_dataset_discovery` 35 tests OK；完整 `unittest discover -s tests` 632 tests / 4 skipped OK；`scripts\pre_push_smoke_brief.cmd` 632 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`；GitHub Actions Ubuntu、`windows-2025-vs2026`、real DB smoke success。
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

1. `L:\RRKAL_project` 是目前 recovery lane 的雲端主工作區與提交正本。開發者日常在 IDE 看到的 Git 狀態，以這個資料夾為準。
2. 舊 `K:\APIkeys_collection` 在本 session 只作唯讀參考；`L:` 其他專案資料夾也視為唯讀，不在 RRKAL 任務中寫入。
3. 需要 GUI、showcase、完整 smoke 或可能被雲端碟延遲影響的測試時，才從 GitHub 或 `L:\RRKAL_project` 建立本地測試 clone，例如 `C:\Users\lyn59\Documents\Codex\RRKAL_local_test\...`。
4. 本地 clone 只作為測試跑道，不作為長期提交來源。測試中找到的修復，必須回補到 `L:\RRKAL_project`。
5. 回補完成後，先確認 `L:\RRKAL_project` 工作樹，再從 `L:\RRKAL_project` `commit` / `push` 到 GitHub。
6. push 後仍需用 GitHub Actions 驗證。不要把「本地 clone 通過」誤當成「雲端正本已同步」。

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
   gh run list --repo Kagamihara-Ruruka/APIkeys_collection --limit 5
   gh run watch RUN_ID --repo Kagamihara-Ruruka/APIkeys_collection --exit-status
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

- `L:\RRKAL_project` 是主工作區、日常閱讀資料夾、修復回補位置與 commit / push 來源；舊 `K:\APIkeys_collection` 只作唯讀參考。
- GUI、showcase、完整 smoke、壓力測試，優先在本地磁碟 clone 執行：`C:\Users\lyn59\Documents\Codex\RRKAL_local_test\...`。這個 clone 是證明環境，不是隱藏主線。
- 如果本地 clone 測到修復，必須把修復回補到 `L:\RRKAL_project`，再由 `L:\RRKAL_project` commit / push。不要讓本地 clone 與雲端正本長期分岔。
- 需要展示資產時，從 `L:\RRKAL_project` 同步 `state/showcase/` 到本地 clone；DB、log、臨時依賴、runtime SQLite 仍維持忽略，不當成正式原始碼。
- `L:\RRKAL_project` 在雲端同步碟上，適合主工作區與資料潔癖管理，但可能遇到 pycache、SQLite、GUI 冷啟動或檔案鎖延遲。測試時使用本地 clone；若不得不在 `L:\RRKAL_project` 跑測試，優先設定 `PYTHONPYCACHEPREFIX` 到 `%TEMP%`，避免 bytecode 鎖住雲端同步檔案。
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
- 做到一個穩定節點就要 commit/push，並用 `gh run watch` 或 `gh run list` 確認 CI。使用者手機會收到 GitHub Actions 通知，所以不要只說 push 成功。若 push 已抵達 `origin/main` 但數分鐘內沒有對應 SHA 的 Actions run，改用 `gh workflow run CI --repo Kagamihara-Ruruka/APIkeys_collection --ref main` 手動 dispatch，再用 `gh run watch RUN_ID --exit-status` 追結果；這是排隊異常的補證據流程，不代表可以跳過本機 smoke。
- 為了降低 token 用量，長輸出請優先用 repo-owned 簡報入口，例如 `.\scripts\pre_push_smoke_brief.cmd`。完整 log 會寫到 `state/logs/pre_push_smoke_*.log`，對話中只貼關鍵行與失敗尾端。外部 `distill` 只能當可選後處理；不要用它取代 raw log、JSON、SQL、CI、測試證據，也不要把可能含 secrets/env/credential 的輸出送去未知 provider。Windows 上若要用 `distill`，必須先確認 `distill.cmd --version` 成功；2026-05-22 實測 `@samuelfaj/distill@1.5.2` 缺 `@samuelfaj/distill-win32-x64` 平台包，尚不能視為可用。
- `.\scripts\pre_push_smoke_brief.cmd -Help` 或 `--help` 只會列出 brief smoke 用法並立即退出，不會建立 log 或啟動完整 unittest；正式 checkpoint 仍要不加 help 跑完整 `pre_push_smoke_brief`。
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
- macOS 目前已安裝 GitHub CLI (`gh`)；GitHub 帳號已由 `YanAnnLu` 改名為 `kagamihara-rururka`，目前使用 `Kagamihara-Ruruka`，查 CI run/log 時使用 `Kagamihara-Ruruka/APIkeys_collection`。
- 海域法域資料請記住：領海、EEZ、爭議區、公海不是單純座標戳，而是帶法律/行政屬性的 GIS polygon 圖層。MySQL spatial 可做 MVP；較完整 GIS 分析、切 tile、空間索引應優先考慮 PostGIS；原始資料保留 GeoPackage/Shapefile/GeoJSON 與 manifest。
- 團隊開始共同尋找資料庫入口網站時，請先寫入 `docs/DATABASE_PORTAL_INTAKE.zh-TW.md`。這是組員用的入口收集表，不要貼 API key/token/cookie；只記網站、API 文件、授權、入口類型、主題、地理範圍與是否需要登入。CLI 已有 `--portal-intake-report --write-portal-intake-json state/portal_intake.review.json`，會把表格整理成 provider seed 草稿、dataset discovery source 草稿、crawler mapping 待辦、adapter/integration backlog 或 incomplete warning；`--promote-portal-intake-local` 只會把乾淨草稿寫進被 Git 忽略的 `config/provider_discovery_seeds.local.json` 與 `config/dataset_discovery_sources.local.json`，不直接改正式 catalog。草稿要進正式 catalog 時，用 `--promote-local-discovery-catalog --write-local-discovery-audit-json state/local_discovery_audit.json`；這會先跑 crawler audit，只有 error=0/warning=0 的 local dataset source 才會寫入正式 catalog。
- `docs/DATASET_DISCOVERY_NOTES.zh-TW.md` 是重要 discovery 主入口，不是暫存雜檔；crawler-first、爬蟲資產 / Crawler Asset、candidate review、bounded resolver、adapter handoff、dataset-version plan 的新規格都應寫在這裡。`docs/appendices/discovery.zh-TW.md` 只保留 redirect/摘要，避免舊 handoff、skill 或 prompt 引用失效。
- 2026-05-22 已補「爬蟲資產 / Crawler Asset」概念：它是 API 搜集器的概念擴充，代表可治理、可版本化、可審核、可排程、可修復的資料取得能力；它不取代 Provider、Dataset、DatasetDiscoverySource、Adapter 或 Mission，而是把現有 crawler/source/resolver/event-log 流程包成產品層。短期不要為此硬加大型 registry；等 UI/健康檢查/repair mission 需要時，再把它提升成正式資料模型。
- 2026-05-24 已把 crawler asset 三能力槽正式化到 `api_launcher/crawler_asset_capabilities.py`：`fetch_metadata`、`list_datasets`、`build_download_plan`。每槽帶 input/output contract、credential mode、terms risk、error buckets 與 bounds facets；舊 `download_selected` 只是 UI 相容別名。後續 Tk/Qt/CLI 產生界域表單時要讀這份 contract，不要在 UI 內各自猜欄位。
- 2026-05-24 已把 crawler asset profile 與 health 拆成後端契約：`api_launcher/crawler_asset_profiles.py` 保存啟用/封存、credential profile、API key env var、帳號提示、排程、限流、重試、seed scope、Logo/favicon/授權備註；`api_launcher/crawler_asset_health.py` 統一產出 `status_code`、emoji、reason、warning、next_action。Tk/Qt/CLI 都應讀這兩個契約，不要各自重建失效判斷或憑證欄位。
- 2026-05-24 第二個切片新增 `api_launcher/crawler_asset_bounds.py`，將 facets 提升為 bounds schema：每個 facet 有 group/control/value type/maps_to/required/options/help，並對應 TimeBounds、SpatialBounds、ColumnBounds、VersionBounds、LimitBounds、AuthBounds 等概念。請優先重用這份 schema 與既有 `api_launcher.bound_form` / `SourceDownloadBounds`，不要為 crawler card、Qt 或 CLI wizard 重寫另一套界域表單規則。
- 2026-05-24 Tk 已有第一版 crawler asset profile 編輯入口：`frontends/tk/crawler_asset_profile_dialog.py` 只收集 profile reference（credential profile、API key env var、帳號提示、排程、限流、重試、Logo/favicon 等），實際驗證與保存交給 `update_crawler_asset_profile()`。UX 規則：爬蟲分頁用明確「爬蟲設定」按鈕或未來齒輪進設定；下載器清單雙擊才代表把選中項目啟動/送入下載，不要把雙擊拿去開設定。
- 近期 GTD 加入 Notion-backed seed intake：使用者打算開一個 Notion 分頁/資料庫給組員維護入口網站清單。Notion 應視為雲端 intake/staging，不是正式 catalog 權威；未來 sync 指令應把 Notion rows 轉成與 `docs/DATABASE_PORTAL_INTAKE.zh-TW.md` 相同的 review JSON / local seed / local dataset source，再跑 crawler audit，通過後才提升正式 catalog。注意 sync 要記 provenance，避免不清楚 seed 從哪列 Notion 來。
- WMS/OGC URL guard 已再補一輪：`api_launcher/crawlers/source_patterns.py` 與 `api_launcher/crawlers/ogc_wms.py` 現在會用 URL parser 產生 GetCapabilities probe，移除 fragment、替換衝突 `service/request`、保留其他 query；source draft normalization 也會把 `ogc_wms_capabilities` endpoint 正規化成可 audit 的 WMS capabilities URL。STAC `/collections` 誤判也已降低，沒有 STAC-like link relation 的 generic collections payload 會停在 unknown/review。
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

Windows 上 `L:\RRKAL_project` 是目前主工作區與提交來源；GUI、展示、完整 smoke、或任何容易受雲端同步碟影響的測試，應先 clone 到 `C:\Users\lyn59\Documents\Codex\RRKAL_local_test\` 的地端副本，必要時再從 `L:\RRKAL_project` 複製 `state/showcase` 展示資料。測試通過後，把確認過的修復回補 `L:\RRKAL_project` 再提交與推送。

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
## 2026-05-25 爬蟲資產下載計畫閉環

- 本輪把 `api_launcher/crawler_asset_service.py` 往前推到可產生下載計畫：`build_crawler_asset_download_plan()` 會讀取 crawler asset source/profile，擋下 disabled/archived source，將 `CrawlerAssetBoundPayload` 轉成 `SourceDownloadBounds`，再呼叫既有 `build_source_download_plan()`。這保持邊界清楚：UI/Qt 不需要重寫 crawler、candidate、resolver 或 direct-download eligibility 規則。
- Tk `frontends/tk/crawler_asset_workflows.py` 的「送進下載器」已接上背景工作：使用者填完動態界域表單後，會建立 `state/crawler_asset_plans/{asset}.original.json` 與 `{asset}.resolved.json`，把 resolved plan 中可直接下載的項目加入下方下載器；需要 adapter review 的項目仍留在 resolved plan summary，不假裝可下載。
- 驗證已補到 `tests/test_crawler_assets.py` 與 `tests/test_tk_dialogs.py`：覆蓋界域 payload -> source-download options、service 產生 direct download plan、Tk workflow 啟動背景計畫工作。下一步可在 UI 上把 review-required 狀態做成更清楚的徽章/待辦。
