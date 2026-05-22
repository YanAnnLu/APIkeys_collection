---
name: apikeys-collection-client
description: Use when operating APIkeys_collection as a user/client rather than developing it. Trigger for tasks like finding dataset sources, running discovery, reviewing candidates, exporting or resolving download plans, downloading direct entries, importing supported CSV/JSON results into SQLite, checking manifests, repairing downloads, testing data-store profiles, generating AI summaries, or producing handoff reports without changing source code.
---

# APIkeys Collection Client

這是客戶端 / 使用者層 skill。目標是讓 Agent 會使用 APIkeys_collection，而不是一遇到問題就改程式碼。

若使用者明確要求開發、修 bug、改 UI、改 crawler/adapter，改用 developer skill。

## 啟動前

1. 進入 repo 後先確認：

```bash
git status --short --branch
git log -1 --oneline
```

2. 讀使用者入口：

```text
docs/USER_GUIDE.zh-TW.md
docs/AGENT_HANDOFF.zh-TW.md
docs/PROJECT_GTD.md
```

如果任務涉及平台長期概念、湖倉/K8S、渲染器、ML、Notion/TradingView connector，讀：

```text
docs/DATA_ASSET_PLATFORM_CONCEPTS.zh-TW.md
```

3. macOS 優先使用使用者指定環境：

```bash
conda run -n metal_trade_312 python APIkeys_collection.py --summary
```

不要把套件裝進 base/system Python。

## 文件路由

客戶端使用時不用讀完整 repo 文件。依任務選：

- 操作 UI / CLI：`docs/USER_GUIDE.zh-TW.md`。
- 安裝、啟動、環境問題：`docs/SETUP.zh-TW.md`。
- 目前能做什麼、還差什麼：`docs/PROJECT_GTD.md`。
- 接力與安全提醒：`docs/AGENT_HANDOFF.zh-TW.md`。
- 資料入口網站收集：`docs/DATABASE_PORTAL_INTAKE.zh-TW.md`。
- 資料發現、候選、adapter review：`docs/DATASET_DISCOVERY_NOTES.zh-TW.md`。
- 資料類型判斷：`docs/DATASET_TYPE_MAP.zh-TW.md`。
- 長期概念，如湖倉、Render Studio、ML、Notion/TradingView connector：`docs/DATA_ASSET_PLATFORM_CONCEPTS.zh-TW.md`。

## 使用者工作流

優先走現有 CLI/UI，不改 source code。

```text
找資料來源
-> 跑 discovery
-> 審核 candidates
-> 匯出 candidate/download plan
-> 解析 bounded adapter plan
-> 下載 direct entries
-> 驗證 manifest
-> 匯入支援的 CSV/JSON 到 SQLite
-> 查看或修復狀態
```

回報時不要只說「指令成功」。要說明目前走到哪一段：

```text
已發現候選 / 已審核 / 已產生 plan / 已解析 direct entry / 已下載 / 已驗 manifest / 已匯入 SQLite / 尚未閉環
```

## 常用 CLI

摘要與初始化：

```bash
python APIkeys_collection.py --summary
python APIkeys_collection.py --init-db --seed --summary
```

資料發現：

```bash
python APIkeys_collection.py --discover-dataset-candidates --summary
python APIkeys_collection.py --list-dataset-candidates
python APIkeys_collection.py --dataset-candidates-json
```

候選審核：

```bash
python APIkeys_collection.py --review-dataset-candidate UID --dataset-candidate-decision approved
```

下載計畫：

```bash
python APIkeys_collection.py --export-candidate-plan state/candidate_plan.json --candidate-plan-status approved
python APIkeys_collection.py --adapter-review-plan state/candidate_plan.json
python APIkeys_collection.py --resolve-adapter-plan state/candidate_plan.json --write-resolved-adapter-plan state/resolved_plan.json
python APIkeys_collection.py --run-download-plan state/resolved_plan.json --download-plan-limit 1
```

匯入與驗證：

```bash
python APIkeys_collection.py --run-download-plan state/resolved_plan.json --import-supported-plan-results --import-sqlite-db state/curated_imports.sqlite
python APIkeys_collection.py --verify-downloads --manifest-health --list-manifests
python APIkeys_collection.py --verify-downloads-json
```

重跑同一份 plan 時，已存在的目標 SQLite table 預設應被視為 skipped，不是失敗；不要要求覆蓋，除非使用者明確要求 replace。

資料庫 / data-store 健康：

```bash
python APIkeys_collection.py --test-data-store all
python APIkeys_collection.py --test-data-store mysql_default --test-data-store-json
python APIkeys_collection.py --write-data-store-env-template state/data_store_env_templates/mysql.env.template --data-store-env-template-profile mysql_default
python APIkeys_collection.py --self-check-databases
python APIkeys_collection.py --self-check-databases-json
```

AI 描述：

```bash
python APIkeys_collection.py --generate-ai-summary PROVIDER_ID --ai-profile PROFILE_ID
```

目前 AI 描述的 MVP 路線是「選 profile + 保存本機 API key」。不要引導一般使用者貼 Google OAuth Client ID，也不要在啟動時自動開 OAuth、QR/device-code、瀏覽器登入或系統 plist/config 編輯器；那些屬於中期正式 Google 登入工作。

接力報告：

```bash
python APIkeys_collection.py --handoff-report state/handoff_report.md
```

## 操作規則

- 不要把 metadata URL、landing page、API selector 當成 direct download。
- 不確定的來源進 adapter review，不要硬下載。
- Direct download 只跑 plan 裡明確 direct 且 bounded 的 entry。
- 大型未知資源、需要登入、授權不明、格式不明，先停止並回報。
- 匯入 SQLite 前先驗 manifest；不要覆蓋既有 table，除非使用者明確要求 replace。
- 使用 UI 時，優先從繁中選單操作；登入/API key/data-store 入口集中在 `整合` 選單。
- 如果 UI 或 CLI 看起來已完成但資料沒有進入 `candidate -> plan -> download -> import` 主線，要回報「尚未閉環」，不要假裝成功。
- 如果 crawler 跑完但候選數為 0、低於預期、全是重複、沒有 evidence/source URL，這是可疑結果；回報給 developer，不要說「來源沒有資料」。

## 何時升級給 developer

遇到以下情況，不要自己改邏輯，改請 developer-level Agent：

```text
crawler 抓不到任何候選但來源看起來應該有資料
adapter review 無法解析且需要新 bounded resolver
importer 不支援新格式
UI 顯示錯誤或入口缺失
manifest/registry/schema 出現疑似程式錯誤
測試失敗
```
