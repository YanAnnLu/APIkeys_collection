# Failure Modes 與意外處理筆記

更新日期：2026-05-20

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
| 使用者手動刪 SQL database/table | launcher registry 變成死紀錄 | SQL self-check 會標記 missing/error，並輸出 `suggestion=...` 或 JSON repair suggestion；UI 可調整單一 asset 的 profile/schema metadata；UI/CLI 可用 `--unmanage-database-asset ASSET_ID --database-repair-json` 把單一 database/table asset 標成 `unmanaged` 後重新自檢，或對 manifest-backed missing SQLite table 從健康 CSV/JSON sidecar manifest 重新匯入；reimport 不會 DROP 或覆蓋既有 table。MySQL/PostgreSQL manifest-backed missing table 可在 UI 用「產生 dry-run SQL」或 CLI `--write-database-repair-sql ASSET_ID` 產生 dry-run SQL 供人工審核，不會連線或執行 DDL/DML | 擴大 guarded repair 到更多 adapter 明確擁有的資料庫輸出，並保留無法證明擁有權時的人工指引 |
| SQLite 被同步碟鎖住 | 寫入失敗或 permission denied | startup checks 與 error log | 建議本機 state path 或 lock retry |
| SQLite connection 未明確 close | Windows 刪除 temp SQLite 時 `WinError 32`，CI 只在 windows-latest 失敗 | 2026-05-17 已將短生命週期 `sqlite3.connect()` 改用 `contextlib.closing(...)` | 對 SQLite helper/測試避免裸用 `with sqlite3.connect(...)`，必要時加靜態檢查 |
| Windows 絕對路徑在 Mac 啟動 | Tk startup checks 把 `K:\...` 當成 Mac 相對路徑並跳錯誤 | `environment.py` 會辨識 foreign platform path，Mac 上只列 warning 不阻擋 UI | config 支援 per-platform project/content paths，UI path repair wizard |
| 只看 `git push` 成功 | 手機收到 GitHub Actions failure，誤以為 push 失敗 | macOS 已安裝並登入 `gh`，可查/追 CI | 每次 push 後用 `gh run list` / `gh run watch --exit-status` 確認 Windows/Ubuntu 都綠 |
| 切換版本到一半 | 新舊資料混合 | staging area、sidecar manifest、atomic promote、transition planner skeleton | SQLite manifest registry + rollback command |
| 降版本 | 新 schema 不相容舊資料 | transition planner 可辨識 downgrade | rollback policy 與 schema migration |
| provider 改 URL | seed/adapter 指到舊入口 | freshness/version metadata | scheduled metadata check |
| API rate limit | 429/503 或封鎖 | polite policy/cooldown | provider-specific quota profile |
| 使用者改本機路徑 | 找不到工具或資料 | path resolver + startup checks | UI path repair wizard |
| 文字編碼問題 | 中文或 metadata 亂碼 | UTF-8/LF 規則 | 自動檢查 doc/config encoding |
| Agent 誤覆未提交檔案 | 上一位 Agent 或使用者成果遺失 | 2026-05-17 已恢復到 Git 快照；殘留 bytecode 曾另存到 `state/recovery/` | 接力前強制備份/patch 未提交 diff；遇到非預期大檔先詢問，不直接 restore/delete |

## Agent 開發時要看哪裡

1. 先讀 `docs/PROJECT_GTD.md` 確認功能狀態。
2. 執行 `py APIkeys_collection.py --show-logs 20` 或直接讀 `state/logs/launcher_events.jsonl` 最近事件。
3. 若有錯誤，讀 `state/logs/launcher_errors.log`。
4. 修改前確認 `git status --short --branch`。
5. 若有未提交 diff，先用 `git diff > state/recovery/<timestamp>.patch` 或複製檔案到 ignored recovery 位置；不要把「看起來不符合文件」當成可丟棄內容。
6. 若懷疑下載檔壞掉，執行 `py APIkeys_collection.py --verify-downloads`，再用 `py APIkeys_collection.py --manifest-health --list-manifests` 看 SQLite 中的健康統計與明細。若要給 UI 或下一位 Agent 讀，改用 `py APIkeys_collection.py --verify-downloads-json` 取得 summary、issues、repair suggestion 與可重排下載的 plan entry。
7. 修改後跑測試與 Docker。
8. push 後用 GitHub CLI 追 CI：`gh run list --repo YanAnnLu/APIkeys_collection --limit 5`，再對最新 run 執行 `gh run watch RUN_ID --repo YanAnnLu/APIkeys_collection --exit-status`。push 成功不代表 Windows/Ubuntu CI 成功。

## SQLite / Windows CI 注意

Python 的 `sqlite3.Connection` 雖然支援 context manager，但 `with sqlite3.connect(...) as conn:` 只管理 transaction commit/rollback，不會在離開區塊時自動關閉 connection。Linux/macOS 可以 unlink 仍被開啟的檔案，所以本機可能過；Windows 會保留檔案鎖，`TemporaryDirectory.cleanup()` 可能失敗並拋出 `PermissionError: [WinError 32]`。

短生命週期 SQLite probe 或測試資料庫請使用：

```python
from contextlib import closing

with closing(sqlite3.connect(path)) as conn:
    conn.execute(...)
```

`api_launcher/db.py::connect_db()` 這類刻意回傳 connection、由呼叫方管理生命週期的函式可以例外，但測試必須在 `finally` 或 fixture cleanup 中明確 `close()`。

## 之後應該實作的恢復機制

- download staging directory：先下載到 staging，驗證後再 promote。HTTP downloader 已可寫 sidecar manifest，並用 `.part` 續傳。
- manifest table：記錄每個版本的檔案、checksum、大小、schema fingerprint。sidecar JSON manifest 已會同步進 SQLite `dataset_asset_manifests`。
- exact target reuse：若同一目標檔案與 sidecar manifest 已驗證正常，且 provider/dataset/version/source/path 都符合目前下載請求，HTTP adapter 會略過重新下載。
- repair command：掃描 missing/stale/broken asset 並提出修復計畫。
- transaction-like update：更新版本失敗時保留舊版可用狀態。
- UI undo/confirm：刪除、解除納管、降版本、覆蓋資料庫都要二次確認。
