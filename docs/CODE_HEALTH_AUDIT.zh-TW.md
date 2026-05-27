# 程式健康審計

最後更新：2026-05-27 15:04 Asia/Taipei

本文件記錄 2026-05-27 文檔漂移審計後的程式健康審計結果。它不是風格清單，而是把已驗證的行為風險、已修補項目、剩餘風險與下一步可測切片整理給下一位 agent。

## 審計範圍

- 起點狀態：`05d6b67 Record GUI audit CI checkpoint`，工作樹在本輪程式修補前只含本輪 agent 修改。
- 不寫入 `K:\CODE_KM`。
- 不做 live 全來源網路審計。
- 不做 Tk 桌面視覺驗收；本輪以 service、CLI JSON 與測試驗證為主。

## 已執行檢查

- `git status --short --branch`
- `git log -1 --oneline --decorate`
- 高風險模式掃描：`sqlite3.connect`、`requests.get/post`、`source_type`、`provider_id`、寬泛 `except`、刪除 / drop 類操作。
- 大檔案掃描：目前仍以 `frontends/tk/dialogs.py`、`api_launcher/core.py`、`frontends/web/static/app.js`、`api_launcher/repository.py`、`api_launcher/adapter_plan_resolver.py` 等為主要重構訊號。
- `py -B APIkeys_collection.py --dataset-discovery-handler-smoke-json`
- `py -B APIkeys_collection.py --crawler-run-summary-json`
- `py -B APIkeys_collection.py --handoff-report-json`
- `node --check frontends\web\static\app.js`
- `py -B -m unittest tests.test_csv_importer tests.test_json_importer tests.test_ingestion_pipeline tests.test_crawler_fetch tests.test_local_credentials tests.test_web_preview -v`
- `scripts\pre_push_smoke_brief.cmd`，754 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`
- GitHub Actions run `26492936566`：Ubuntu、Windows、Real DB smoke 全部 success
- 後續 HTML index partial warning 切片：`py -B -m unittest tests.test_dataset_discovery tests.test_crawler_assets tests.test_crawler_audit_smoke -v`，79 tests OK；`scripts\pre_push_smoke_brief.cmd` 755 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`；GitHub Actions run `26493410406` 全部 success
- 後續 source-profile politeness 切片：`py -B -m unittest tests.test_dataset_discovery -v`，38 tests OK；`py -B -m unittest tests.test_dataset_discovery tests.test_crawler_assets tests.test_crawler_audit_smoke -v`，81 tests OK；docs mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd`，757 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`；GitHub Actions run `26494263728` 全部 success。
- 後續 source-profile rate-limit 切片：`py -B -m unittest tests.test_dataset_discovery -v`，39 tests OK；`py -B -m unittest tests.test_dataset_discovery tests.test_crawler_assets tests.test_crawler_audit_smoke tests.test_web_preview -v`，113 tests OK；`git diff --check` OK；docs mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd`，758 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`；GitHub Actions run `26495740693` 全部 success。
- 後續 source-profile access-policy 切片：`py -B -m unittest tests.test_dataset_discovery tests.test_crawler_assets -v`，78 tests OK；`py -B -m unittest tests.test_dataset_discovery tests.test_crawler_assets tests.test_web_preview -v`，109 tests OK；`git diff --check` OK；docs mojibake scan OK；`.\scripts\pre_push_smoke_brief.cmd`，759 tests / 4 skipped，MVP demo smoke `download_import_completed` / `row_count=3`；GitHub Actions run `26496327588` 全部 success。

## P0 Findings

目前審計範圍內沒有發現需要立刻停止開發或可能直接造成不可逆資料毀損的 P0。仍需注意：本輪沒有 live 全來源下載審計，因此不能把「所有遠端來源可下載」當成已驗證事實。

## P1 Findings / 已修補

### P1-1 CSV / JSON replace import 失敗時可能丟失既有表

- 檔案：`api_launcher/importers/csv_importer.py`
- 問題：`import_rows_to_sqlite(..., replace=True)` 先 `DROP TABLE IF EXISTS`，再建立新表與寫入。JSON importer 也共用這段 row import service。
- 風險：若新 CSV/JSON 匯入途中因壞列、程式中斷或 SQLite 錯誤失敗，既有 curated table 可能已被刪除。
- 修法：replace 模式先寫入同一 SQLite DB 內的唯一暫存表；只有新資料全部寫入成功後才 drop target 並 rename temp table。失敗時 rollback 並清理 temp table，既有 target table 保留。
- 測試：`tests.test_csv_importer.CsvImporterTests.test_replace_import_preserves_existing_table_when_new_rows_fail` 與 `test_replace_import_swaps_table_after_successful_new_rows`。

### P1-2 Crawler metadata fetch 無大小上限

- 檔案：`api_launcher/crawlers/fetch.py`
- 問題：`fetch_text()` 對 metadata / catalog endpoint 使用 `response.read()` 無上限。
- 風險：若來源 URL 被設定到大型檔案、錯誤 API 或惡意頁面，metadata crawler 可能把大型 payload 一次載入記憶體。
- 修法：新增 `DEFAULT_MAX_CRAWLER_RESPONSE_BYTES = 8 * 1024 * 1024`，`fetch_text()` 只讀 `max_bytes + 1`，超限即拒絕；`fetch_json()` 同步傳入上限。
- 測試：`tests.test_crawler_fetch.CrawlerFetchTests.test_fetch_text_rejects_metadata_response_over_byte_limit`。

### P1-3 本機 credential `.env` 直接覆寫

- 檔案：`api_launcher/local_credentials.py`
- 問題：`write_env_updates()` 原本直接 `write_text()` 覆寫 `.env`。
- 風險：使用者在 Web Preview / 未來 Tk 設定「記住我的帳號」時，若程序中斷或替換失敗，可能留下半截 `.env`，造成所有 credential 狀態失真。
- 修法：同目錄建立 UTF-8 暫存檔，完整寫入後用 `os.replace()` 替換；替換失敗時清理暫存檔並保留舊 `.env`。
- 測試：`tests.test_local_credentials.LocalCredentialsTest.test_write_env_updates_keeps_existing_file_if_replace_fails`。

## P2 Findings / 尚未處理

### P2-1 Seed 完整枚舉仍需 source-profile politeness（timeout / page cap / page size / rate limit 已修補）

- 現況：Web Preview 可用 `complete_seed=true`、`max_results=1000` 與 handler pagination contract 表達本機上限與遠端 has-more。
- 風險：不同來源的合理頁數、延遲、timeout 與 rate limit 不同；如果全部依同一上限執行，仍可能對某些入口太積極。
- 修法：`DatasetDiscoverySource` 新增 `crawl_timeout_seconds`、`crawl_max_pages`、`crawl_page_size` 與 `crawl_rate_limit_seconds`；catalog/local source JSON 會載入與寫回這些欄位。Crawler 執行時會套用 source-level timeout，並把 `crawl_max_pages` 視為來源層安全上限；若執行期 `max_pages` 更低，會採更低值，避免 UI/CLI accidental override 把特定來源的 politeness boundary 放大。`crawl_page_size` 會限制單次請求的 page size；若 UI/CLI 給較大的 `max_results_override`，source profile 可把 per-request page size 壓低。`crawl_rate_limit_seconds` 由 paginated crawler handler 透過共用 `polite_crawl_delay()` 在下一頁 request 前套用。
- 測試：`tests.test_dataset_discovery.DatasetDiscoveryTests.test_source_loader_preserves_politeness_defaults`、`test_source_profile_politeness_defaults_reach_default_crawler` 與 `test_paginated_crawler_honors_source_rate_limit_between_pages`。
- 後續補強：`credential_mode` 與 `terms_risk` 已可由 source profile 明示；crawler asset capability 會先讀 source profile，再退回文字 heuristic。未來可再把 timeout/page/rate-limit/access policy 合併成正式 request policy object。

### P2-2 HTML file index full crawl 單頁失敗策略仍偏硬（已於後續切片修補）

- 現況：HTML file index 已有 same-origin、seen set 與 `max_pages` 安全邊界。
- 風險：若 full crawl 中某個索引頁失敗，後續可能直接中止，而不是保留已找到候選並附 warning。
- 修法：`DatasetCrawlerOutput` 新增 `warnings`；HTML file index full crawl 會把 linked page fetch failure 轉成 `index_page_fetch_failed` warning 並保留已找到候選，orchestrator 會把 handler warning 合併到 source audit。
- 測試：`tests.test_dataset_discovery.DatasetDiscoveryTests.test_html_file_index_full_crawl_keeps_candidates_when_linked_page_fails`。

### P2-3 Web `真下載示範` 仍是過渡功能

- 現況：`web_real_download_demo` 已被文件標記為 transitional / demo-only。
- 風險：若長期保留在主要 UI，容易讓使用者誤以為它代表所有 crawler source 都已完成正式下載 / 匯入。
- 建議：在正式 crawler asset 下載 / import 路徑完全打通後，將它移到 developer/demo diagnostics 或移除。
- 需要測試：UI 不再把 demo CTA 當成主要正式下載入口；正式 downloader path 可完成至少一個 public source。

## P3 Findings / 架構債

- 大檔仍是重構訊號：`frontends/tk/dialogs.py`、`api_launcher/core.py`、`frontends/web/static/app.js`、`api_launcher/repository.py`、`api_launcher/adapter_plan_resolver.py`、`frontends/tk/crawler_asset_workflows.py`。
- 不建議現在一次搬家或大重寫。比較安全的節奏是每 2-3 個功能切片安排一次 consolidation slice：拆 service、補測試、保留相容 wrapper、更新 `CODE_RELATIONSHIP_MAP.zh-TW.md` / `WORKSPACE_LAYOUT.zh-TW.md`。
- `source_type` 分支目前大多集中在 registry / capability / bounds 之類合理位置，沒有看到需要立刻全面改寫的擴散失控。但新增 handler 時仍要優先走 registry / adapter，不要散到 UI。

## 本輪不建議現在重構的項目

- 不建議把所有 crawler 改成單一宣告式 universal interpreter。宣告式架構仍是第二階段收斂方向。
- 不建議在同一輪拆 `core.py`、`repository.py`、`adapter_plan_resolver.py` 與 Tk dialogs。這會干擾目前 crawler asset / Web / import hardening 主線。
- 不建議把 Web Preview demo download 直接刪掉；先讓正式 crawler asset download/import 路徑有可操作替代品，再移走 demo。

## 下一步建議

1. 先把本輪三個 P1 修補跑完整 pre-push smoke，推送後看 GitHub Actions。
2. 下一個 hardening slice 可處理 source-profile rate-limit metadata / middleware，或挑一個 public-source 正式 crawler asset download/import path 取代 Web real demo。
3. 接著回到產品主線：正式 crawler asset 的 public-source download/import path，而不是繼續依賴 Web real demo。

## Docs drift check

- 已更新：本文件、`DOCS_INDEX.zh-TW.md`、`PROJECT_GTD.md`、`AGENT_HANDOFF.zh-TW.md`、`DEVELOPMENT_LOG.zh-TW.md`。
- 未更新：使用者指南與 Web Preview UIUX。理由是本輪沒有改使用者操作流程，只改後端安全性與審計紀錄。
- 已知剩餘漂移：若未來使用者指南仍把 `真下載示範` 表述得像正式 feature，需在正式下載入口完成後再次修補。
