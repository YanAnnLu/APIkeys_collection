# Failure Modes 與意外處理筆記

更新日期：2026-05-17

這份文件給人類開發者與 agent 使用。目的不是把所有錯誤都藏起來，而是讓錯誤可觀測、可重現、可恢復。

## 原則

- 下載續傳只處理「傳輸中斷」，不是完整的意外處理。
- 所有重要錯誤都應寫入 `state/logs/launcher_events.jsonl`。
- 給人看的摘要錯誤寫入 `state/logs/launcher_errors.log`。
- runtime 狀態應可重建；SQLite、download `.part`、cache 都不應被視為唯一真相。
- 在刪除、覆蓋、降版本、更新資料庫前，都要先確認 install ID、dataset UID、版本與 checksum/schema。

## 常見意外

| 場景 | 風險 | 目前處理 | 後續需要 |
| --- | --- | --- | --- |
| 網路中斷 | 下載失敗或檔案不完整 | `.part` 檔與 Range resume | per-provider retry policy 與 manifest 驗證 |
| 使用者重複點 Start | 同一 provider 重複排 job | `prepare_provider_for_download()` 阻擋活躍 job | 以 dataset version 為 key 支援多版本但避免重複同版本 |
| 使用者手動刪下載檔 | registry 指向不存在資產 | asset verifier 可標記 missing | UI 一鍵修復或重新下載缺失資產 |
| 使用者手動刪 SQL database | launcher registry 變成死紀錄 | SQL self-check 已列入 GTD | MySQL/PostgreSQL/SQLite introspection |
| SQLite 被同步碟鎖住 | 寫入失敗或 permission denied | startup checks 與 error log | 建議本機 state path 或 lock retry |
| 切換版本到一半 | 新舊資料混合 | transition planner skeleton | staging area + atomic promote |
| 降版本 | 新 schema 不相容舊資料 | transition planner 可辨識 downgrade | rollback policy 與 schema migration |
| provider 改 URL | seed/adapter 指到舊入口 | freshness/version metadata | scheduled metadata check |
| API rate limit | 429/503 或封鎖 | polite policy/cooldown | provider-specific quota profile |
| 使用者改本機路徑 | 找不到工具或資料 | path resolver + startup checks | UI path repair wizard |
| 文字編碼問題 | 中文或 metadata 亂碼 | UTF-8/LF 規則 | 自動檢查 doc/config encoding |

## Agent 開發時要看哪裡

1. 先讀 `docs/PROJECT_GTD.md` 確認功能狀態。
2. 再讀 `state/logs/launcher_events.jsonl` 最近事件。
3. 若有錯誤，讀 `state/logs/launcher_errors.log`。
4. 修改前確認 `git status --short --branch`。
5. 修改後跑測試與 Docker。

## 之後應該實作的恢復機制

- download staging directory：先下載到 staging，驗證後再 promote。
- manifest table：記錄每個版本的檔案、checksum、大小、schema fingerprint。
- repair command：掃描 missing/stale/broken asset 並提出修復計畫。
- transaction-like update：更新版本失敗時保留舊版可用狀態。
- UI undo/confirm：刪除、解除納管、降版本、覆蓋資料庫都要二次確認。
