# 使用者操作手冊

最後更新：2026-05-22

這份手冊是面向第一次操作 Demo 的使用者。更細的背景說明仍保留在 `docs/USER_GUIDE.zh-TW.md`；本文件聚焦「照著做」。

## 操作流程圖

```mermaid
flowchart LR
    open["開啟 UI"] --> browse["瀏覽資料源"]
    browse --> discover["發現資料集候選"]
    discover --> review["審核候選"]
    review --> plan["加入下載計畫"]
    plan --> resolve["必要時解析轉接器計畫"]
    resolve --> download["開始下載"]
    download --> import["匯入支援結果"]
    import --> repair["驗證 / 修復資產"]
```

圖說：這條線才是目前 MVP Demo 的主要路線。只按「下載」但沒有 direct download entry 時，下載器不會硬抓網頁。

## 0. 快速 Demo

如果想先確認整條 Demo 閉環，UI 裡可以直接用：

```text
工具 > 產生 MVP Demo Flow
```

這會在 `state/mvp_demo/` 寫出 flow 說明、Socrata review plan、離線 JSON fixture plan，並把離線 direct plan 加到下方下載計畫。接著按：

```text
下載計畫 > 開始
下載計畫 > 匯入
```

圖說：UI 入口只幫你建立 demo 檔案並排入下載計畫，不會自動下載或自動寫資料庫；下載與匯入仍要由使用者確認。

如果只是要先確認後端閉環，不必打開 UI，也可以用 CLI 產生同一條固定的 MVP Demo Flow：

```powershell
py -B APIkeys_collection.py --db state/mvp_demo/launcher.sqlite --init-db --seed --write-mvp-demo-flow state/mvp_demo/flow.json
```

這會在 `state/mvp_demo/` 寫出 flow 說明、Socrata review plan、離線 JSON fixture plan 與後續指令。先跑離線 direct plan，可以在沒有網路時驗證下載、sidecar manifest、SQLite 匯入是否正常：

```powershell
py -B APIkeys_collection.py --db state/mvp_demo/launcher.sqlite --init-db --seed --run-download-plan state/mvp_demo/socrata_311.offline_direct.json --downloads-root state/mvp_demo/downloads --import-supported-plan-results --import-sqlite-db state/mvp_demo/curated_demo.sqlite --plan-import-existing-table-policy rename
```

圖說：這是穩定 smoke test，不取代真正 crawler discovery；它只是先證明核心下載/匯入管線沒有斷。

## 0-1. 金融時間序列 Demo

如果要確認金融/市場資料的 append-only 時間序列欄位可以進入同一條下載與匯入閉環，可以先產生 yfinance 離線 demo plan：

```powershell
py -B APIkeys_collection.py --write-yfinance-demo-plan state/yfinance_demo/plan.json --yfinance-symbol AAPL --yfinance-symbol MSFT
```

接著跑：

```powershell
py -B APIkeys_collection.py --db state/yfinance_demo/launcher.sqlite --init-db --seed --run-download-plan state/yfinance_demo/plan.json --downloads-root state/yfinance_demo/downloads --import-supported-plan-results --import-sqlite-db state/yfinance_demo/curated.sqlite --plan-import-existing-table-policy rename
```

圖說：這只使用本機產生的 CSV fixture，不會安裝 `yfinance`，也不會連到 Yahoo。若要真的抓取 live yfinance，必須由使用者明確 opt-in：

```powershell
py -B APIkeys_collection.py --write-yfinance-live-plan state/yfinance_live/plan.json --yfinance-symbol AAPL --yfinance-query-window daily_1mo --yfinance-storage-target auto --yfinance-retention-days 365 --yfinance-acknowledge-unofficial
```

這會在本機寫出 live CSV 與可匯入 plan；`--yfinance-query-window` 只會選擇 chart-friendly 的 period/interval 與 storage hint，可用值包含 `intraday_5d_5m`、`daily_1mo`、`daily_6mo`、`weekly_1y`。`--yfinance-storage-target` 只會寫入建議儲存目標 metadata，可用值包含 `auto`、`sqlite_mvp_table`、`mysql_timeseries_table`、`parquet_duckdb_archive`、`timescaledb_hypertable`、`clickhouse_ohlcv_table`；目前不會直接寫 MySQL、Parquet、TimescaleDB 或 ClickHouse。`--yfinance-retention-days` 只會寫進 plan metadata，提醒這份本機快取預期保留多久，不會自動刪檔或背景刷新。之後仍要用 `--run-download-plan ... --import-supported-plan-results` 明確執行。它只適合作為非官方、personal/research 用途資料源，不應視為商用或可再散布資料來源，也不會在 CI 或 crawler 裡自動執行。

若要先審查「這份 yfinance plan 將來應該如何進 MySQL/Parquet/TimescaleDB/ClickHouse」，可以產生 dry-run review：
```powershell
py -B APIkeys_collection.py --write-yfinance-storage-review state/yfinance_live/storage_review.json --yfinance-storage-review-plan state/yfinance_live/plan.json
```

若要把審查結果整理成人類 / DBA 可以簽核的 Markdown：
```powershell
py -B APIkeys_collection.py --write-yfinance-storage-handoff state/yfinance_live/storage_handoff.md --yfinance-storage-handoff-review state/yfinance_live/storage_review.json
```

圖說：這一步只產生 `storage_review.json`、必要時的 `.dry_run.sql`，以及可閱讀的 `storage_handoff.md`，用來列出目標 schema、審查動作、execution guard 與後續命令草稿；程式不會連線、不會建表、不會匯入，也不會把 storage target metadata 或 handoff 文件當成自動執行命令。SQLite 匯入仍走上面的 `--run-download-plan ... --import-supported-plan-results` 閉環，其他儲存目標必須等人或 DBA 審查後另行執行。

在 Tk UI 中，對應入口在 `工具` 選單。`產生 yfinance 離線 Demo plan` 只建立本機 fixture-backed plan 並加入下載計畫；`建立 yfinance live plan（需確認）` 會要求填寫 symbol、query window、storage target、period、interval、保留天數，並勾選 unofficial/personal-research 確認框後才呼叫本機 `yfinance`。`產生 yfinance 儲存審查 dry-run` 會讀取既有 plan，寫出 review JSON、handoff Markdown 與必要時的 `.dry_run.sql`，讓使用者或 DBA 先審查 schema、命令草稿與風險。UI 仍然只把項目排進下載計畫或產生審查檔，接下來要由使用者按「開始」與「匯入」或另行人工審查，不會自動排程、背景抓取、依 query window 自動刷新、直接寫入資料庫，或依保留天數自動刪檔。

## 1. 開啟程式

Windows：

```powershell
py APIkeys_collection_ui.py
```

macOS / Linux：

```bash
python3 APIkeys_collection_ui.py
```

啟動成功時，終端機會看到：

```text
APIkeys_collection UI ready ...
```

若 UI 沒有浮出，先看終端機錯誤與 `state/logs/launcher_events.jsonl`。

## 2. 找資料源

主畫面分成四塊：

| 區域 | 用途 |
| --- | --- |
| 左側篩選 | 依類型或提供商縮小清單 |
| 中央表格 | 顯示 provider 與 crawler 找到的 dataset rows |
| 右側抽屜 | 顯示選中資料源的詳情與動作 |
| 下方下載計畫 | 顯示即將下載/匯入的 plan items |

圖說：provider 是資料供應商，不一定等於單一資料集；一個供應商可能有很多 dataset。

## 3. 發現資料集候選

在 UI 使用：

```text
資料庫 > 發現資料集候選
```

這一步只抓 metadata，不下載大型檔案。若候選太少，先確認：

- 是否只選了少數 provider。
- source 是否支援 full-crawl pagination。
- 是否有 warning，例如 0 筆、低於預期、payload shape 不符。

## 4. 審核候選並加入下載計畫

打開：

```text
資料庫 > 審核資料集候選
```

選候選後可以：

- 標記可用。
- 加入下載計畫。
- 拒絕候選。

加入下載計畫後，還要看該項目是 direct download、需要 adapter，或需要解壓/轉換。這是避免把 HTML 頁或 API selector 誤當資料檔。

## 5. 解析 Adapter 計畫

如果下載計畫中有 `需 adapter`，可以試：

```text
資料庫 > 解析 Adapter 計畫
```

圖說：解析器只會挑安全的小樣本或明確 direct file。例如 CKAN resources、Socrata `$limit=25`、ERDDAP sample CSV、STAC `limit=1` metadata。它不會掃整站，也不會抓未知大型檔案。

## 6. 下載與匯入

下載：

```text
下載計畫 > 開始
```

匯入：

```text
下載計畫 > 匯入
```

或：

```text
資料庫 > 匯入可支援下載結果
```

目前支援自動匯入：

- CSV / CSV.GZ
- JSON / JSON.GZ
- JSONL / NDJSON
- GeoJSON / GeoJSON.GZ
- ZIP/TAR 中第一個可支援的 CSV/JSON/GeoJSON 類成員

不支援的檔案不會硬塞進 SQLite，會留在 adapter/manual review。

如果檔案不是由 launcher 下載，而是使用者已經放在本機，可以先走 CLI 手動匯入入口：

```bash
python3 APIkeys_collection.py --import-local-file C:\data\weather.csv --import-sqlite-db state/curated_imports.sqlite --import-table weather_manual
```

這會先為本機檔案建立 sidecar manifest，再用相同的 CSV/JSON 匯入器寫入 SQLite。來源檔不會被移動或刪除；raw file 與 curated table 會以 `manual_local_files` 這個本機 synthetic provider 登記，方便後續 manifest health、schema fingerprint 與修復流程追蹤。

若是給自動化 agent、heartbeat 或外部工具接續處理，可以在同一個命令後面加 `--manual-import-json`。這會輸出單一 JSON，內容包含 manifest、raw asset id、匯入 table、列數、欄位、來源審查摘要與下一步資料庫自檢建議，避免工具只能解析人類可讀文字。

手動匯入的來源審查摘要會提醒：Launcher 只確認當下檔案的 checksum、格式與匯入結果，不能替使用者確認原始來源或授權；它不會掃資料夾、不會刪檔、不會把本機 `file://` 路徑當成可重新下載的網路來源，也不會自動覆蓋既有 table。

Tk UI 的入口是：

```text
資料庫 > 匯入本機 CSV/JSON 檔
```

匯入成功後，UI 對話框會列出 manifest、SQLite 位置與短版來源審查摘要。這個摘要是為了讓使用者在 Demo 或日常操作時，不需要翻 manifest JSON 也能立刻知道「這是本機檔案、可追蹤 checksum、但來源與授權仍要人工確認」。

或：

```text
更多 > 匯入本機 CSV/JSON 檔
```

UI 會開檔案選擇器，只處理你選的單一檔案。table 名稱可以留空由檔名推導；若同名 table 已經存在，會自動改成 `table_2` 這類新名稱，不會覆蓋舊表。

## 7. 驗證與修復

打開：

```text
工具 > 修復 / 驗證資產
```

下載檔案分頁會檢查 manifest、檔案大小與 checksum。資料庫分頁會檢查 SQLite/MySQL/PostgreSQL registry asset。

自動修復只在安全條件下啟用。例如：missing SQLite table 有健康 sidecar manifest 且來源格式支援。它不會自動 DROP table 或刪檔。

## 8. 連接本地 MySQL

目前 MySQL 連線走環境變數，不把密碼寫進 Git。

```powershell
$env:APIKEYS_MYSQL_HOST = "127.0.0.1"
$env:APIKEYS_MYSQL_PORT = "3306"
$env:APIKEYS_MYSQL_DATABASE = "你的測試資料庫"
$env:APIKEYS_MYSQL_USER = "你的使用者"
$env:APIKEYS_MYSQL_PASSWORD = "你的密碼"
py -B APIkeys_collection.py --test-data-store mysql_default
```

如果顯示 missing env，代表環境變數還沒設好。如果顯示 driver missing，代表目前 Python 環境缺 `mysql-connector-python`。不要把這個套件裝進 base/system Python；要裝在專案指定 env 或本機專用 venv。

## 9. 常見誤解

| 現象 | 可能原因 | 正確處理 |
| --- | --- | --- |
| 按下載沒反應 | plan 沒有 direct entry | 先看 Adapter 待辦或解析 Adapter 計畫 |
| crawler 只出現少量結果 | 只跑 smoke/default limit | 開 full-crawl，但要保留 page cap 與 warning |
| 匯入顯示略過 | table 已存在 | 預設不覆蓋，可選 rename 或明確 replace |
| MySQL 連不上 | env vars、driver、database/user 未配置 | 先跑 `--test-data-store mysql_default` |
| UI 顯示 provider 但沒有 dataset | provider 只是入口，不代表已完成 dataset discovery | 跑資料集候選發現與審核 |

## 10. 新功能說明規則

之後每新增功能，至少補三件事：

1. 使用者在哪裡按。
2. 它會改變什麼資料或狀態。
3. 怎麼驗證成功，以及失敗時看哪裡。

若功能跨 UI、CLI、資料庫或檔案系統，請同步更新 `docs/CODE_RELATIONSHIP_MAP.zh-TW.md` 或 `docs/MVP_FLOW_AUDIT.zh-TW.md`。
