# RRKAL Workflow

最後更新：2026-05-31

這份文件定義 RRKAL / `APIkeys_collection` 的日常開發、Codex Cloud 接手、對話備份與 checkpoint 規則。它是工作流契約，不取代 `AGENT_HANDOFF.zh-TW.md`、`PROJECT_GTD.md` 或各專題文件。

## 標準開工流程

每輪開始前：

```powershell
cd L:\RRKAL_project
git status --short --branch
git log -1 --oneline --decorate
```

再讀：

1. `docs/AGENT_START_HERE.zh-TW.md`
2. `docs/CODEX_CLOUD_HANDOFF.zh-TW.md`
3. `docs/AGENT_HANDOFF.zh-TW.md`
4. `docs/PROJECT_GTD.md`
5. 需要找文件才讀 `docs/DOCS_INDEX.zh-TW.md`

若 task 是中大型跨模組改動，再讀 `docs/DEVELOPMENT_WORKFLOW_OPEN_SPEC.zh-TW.md`，必要時走 OpenSpec。

同時檢查跨 agent 交換區：

```powershell
Get-ChildItem -LiteralPath L:\AGENT_EXCHANGE\inbox -Filter '*_RRKAL_project.md'
```

若收信檔中有與 RRKAL 相關的 `Status: new` entry，必須在該 entry 的 `Responses` 區塊追加回覆，至少包含：

- `Decision: accepted / backlogged / needs-evidence / rejected`
- `Response: ...`
- `Next: ...`

交換區是跨 agent 論壇，不是 RRKAL repo 的 source of truth。採納建議後，必須轉成本 repo 內可驗證的 GTD、handoff、docs、OpenSpec 或 code slice。

## 權威順序

1. 使用者最新明確指令。
2. 已驗證行為：tests、CLI JSON、smoke result、實際 UI 行為、`git diff`、GitHub Actions。
3. `docs/AGENT_HANDOFF.zh-TW.md` 與 `docs/PROJECT_GTD.md`。
4. `docs/AGENT_START_HERE.zh-TW.md`、`docs/CODEX_CLOUD_HANDOFF.zh-TW.md`、`docs/DOCS_INDEX.zh-TW.md`。
5. 專題文件與使用者文件。
6. `docs/DEVELOPMENT_LOG.zh-TW.md` 與歷史筆記。

歷史日誌是證據，不是目前真相。若文件和 verified behavior 衝突，先回報 drift，再做最小必要修補。

## 工作區規則

| 位置 | 權限 |
| --- | --- |
| `L:\RRKAL_project` | RRKAL 目前主工作區，可讀寫、commit、push。 |
| `K:\APIkeys_collection` | 舊工作區，本 session 唯讀參考。 |
| `L:` 其他資料夾 | 其他專案或共享資料，除非使用者明確授權，否則唯讀。 |
| `K:\CODE_KM` | 其他專案，RRKAL 工作中唯讀。 |
| `L:\AGENT_EXCHANGE` | 跨 agent 意見交換區，不上 GitHub；RRKAL 主寫可讀收信檔並在相關 entry 的 `Responses` 區塊回覆，不可把原始信件複製進公開 repo。 |
| `C:\Users\lyn59\Documents\Codex\RRKAL_local_test\...` | 可作 GUI / smoke / showcase 本地 clone 測試；修補要回補 L 槽。 |

若 L 槽遇到 git metadata、pycache、SQLite lock、WinError 5 或雲端同步延遲，先重試或改用本地 clone 驗證；不要直接破壞 `.git` 或覆蓋工作區。

## 開發節奏

採固定節奏：

```text
功能切片 -> 功能切片 -> consolidation 切片
```

功能切片要可驗證，consolidation 切片用來：

- 拆出 service/helper。
- 移除重複分支。
- 補測試。
- 補 docs contract。
- 防止 `core.py`、`preview_api.py`、`crawler_asset_workflows.py`、`dialogs.py` 繼續變大。

第一階段仍以 MVP 小閉環為準：

```text
seed -> crawler -> candidate -> plan -> download -> import -> UI
```

宣告式 profile / matrix / pipeline 是收斂方向，不是一次性重寫理由。

## 對話備份與公開文件邊界

raw transcript 只放 private repo：

```text
https://github.com/Kagamihara-Ruruka/dialogue-save
```

RRKAL 建議路徑：

```text
APIkeys_collection/<topic-slug>__YYYY-MM-DD__<thread-short-id>/
```

公開 repo 只放：

- `docs/CODEX_CLOUD_HANDOFF.zh-TW.md`
- `docs/WORKFLOW.zh-TW.md`
- `docs/AGENT_HANDOFF.zh-TW.md`
- `docs/PROJECT_GTD.md`
- `docs/DEVELOPMENT_LOG.zh-TW.md`
- decision / audit / user-facing docs

公開 repo 不放 raw transcript。若需要引用 private transcript，只放 private repo 路徑與摘要，不貼原文。

## Checkpoint 結束流程

每個 checkpoint 結束前：

1. 跑相關測試或 smoke。
2. 跑 `git diff --check`。
3. 若改了 `.md` / `SKILL.md` / zh-TW docs，跑 mojibake scan。
4. 檢查 `L:\AGENT_EXCHANGE\inbox\*_RRKAL_project.md`，並回覆相關 `Status: new` entry。
5. 做 docs drift check。
6. 更新必要文件：
   - `PROJECT_GTD.md`
   - `AGENT_HANDOFF.zh-TW.md`
   - `DEVELOPMENT_LOG.zh-TW.md`
   - `DOCS_INDEX.zh-TW.md` 或專題文件
7. commit / push。
8. push 後查 GitHub Actions。

常用指令：

```powershell
.\scripts\pre_push_smoke_brief.cmd
git diff --check
gh run list --repo Kagamihara-Ruruka/APIkeys_collection --limit 5
gh run watch RUN_ID --repo Kagamihara-Ruruka/APIkeys_collection --exit-status
```

文件掃描：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\lyn59\.codex\skills\agent-dev-safety\scripts\scan_mojibake.ps1 -Path L:\RRKAL_project\docs
```

## Final Report Checklist

回報時至少包含：

```text
Files changed:
Tests / checks run:
Docs drift check:
Handoff/GTD/log updated:
Verified behavior source:
Raw transcript backup:
Next safe action:
```

若本輪沒有 raw transcript 備份：

```text
Raw transcript backup: not created for this slice.
```

若本輪不需更新文檔：

```text
Docs drift check: no documentation update required for this slice.
```

## 與 RRKAL_displaytools 的邊界

`RRKAL_displaytools` 的工程真相是：

```text
https://github.com/Kagamihara-Ruruka/RRKAL_displaytools
```

它處理 display / renderer / Qt / Taichi / layer visualization 等方向。RRKAL / `APIkeys_collection` 處理 crawler、seed、download plan、download/import、credential、Tk/Web control panel 與資料資產治理。

可借鑑 workflow、handoff 與 display contract 概念；不可把它的 raw transcript 或專案碼直接放進本公開 repo。
