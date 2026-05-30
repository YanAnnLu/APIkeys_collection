# Codex Cloud Handoff

最後更新：2026-05-30

這份文件定義 RRKAL / `APIkeys_collection` 在本機 Codex 不穩定時，如何把工作交給 Codex Cloud 或新的本機 thread 接手。它只保存可公開的工程接力資訊；完整對話或 raw transcript 不放進本公開 repo。

## 專案身分

| 項目 | 目前值 |
| --- | --- |
| Product display name | RuRuKa Asset Launcher |
| Short name | RRKAL |
| Compatibility repo name | APIkeys_collection |
| GitHub repo | `https://github.com/Kagamihara-Ruruka/APIkeys_collection` |
| 本 session 主工作區 | `L:\RRKAL_project` |
| 目前 active branch | `rrkal-32e215c-recovery` |
| 舊工作區 | `K:\APIkeys_collection`，本 session 只作唯讀參考 |

`RRKAL_displaytools` 是相鄰但不同的專案。它可作 renderer / Qt / display workflow 參考，但不是本 repo 的產品碼來源；不要把它的 raw transcript 或專案檔案搬進 `APIkeys_collection`。

## 接手啟動順序

新的 agent 或 Codex Cloud 工作環境接手時，先做這些事：

```powershell
cd L:\RRKAL_project
git fetch origin
git status --short --branch
git log -1 --oneline --decorate
```

然後依序讀：

1. `docs/AGENT_START_HERE.zh-TW.md`
2. `docs/CODEX_CLOUD_HANDOFF.zh-TW.md`
3. `docs/WORKFLOW.zh-TW.md`
4. `docs/AGENT_HANDOFF.zh-TW.md`
5. `docs/PROJECT_GTD.md`
6. 需要找文件時再讀 `docs/DOCS_INDEX.zh-TW.md`

若上述文件和已驗證行為衝突，以 verified behavior 為準：tests、CLI JSON、smoke result、實際 UI 行為、`git diff`、GitHub Actions。

## Cloud / Local 分工

| 場景 | 建議位置 | 原因 |
| --- | --- | --- |
| 小型程式切片、文件治理、CI 修補 | Codex Cloud 或 `L:\RRKAL_project` | 以 GitHub / CI 作權威 checkpoint。 |
| Tk / Web 視覺驗收、GUI 操作、展示前跑 UI | 本地 clone | 避免雲端碟 GUI / pycache / SQLite lock 干擾。 |
| 大型 smoke / pre-push smoke | 優先本地 clone，通過後回補 L 槽 | 降低 L 槽 I/O 延遲與 WinError 5 類問題。 |
| raw transcript 備份 | private `dialogue-save` repo | 不可進公開 repo。 |

本地 clone 測過的修補，必須回補到 `L:\RRKAL_project`，再從 L 槽 commit / push。L 槽是目前 RRKAL 的共享雲端工作區；除 `L:\RRKAL_project` 外的其他資料夾都視為唯讀。

## 對話備份規則

完整對話備份只放 private repo：

```text
https://github.com/Kagamihara-Ruruka/dialogue-save
```

建議路徑格式：

```text
APIkeys_collection/<topic-slug>__YYYY-MM-DD__<thread-short-id>/
```

建議內容：

| 檔案 | 內容 |
| --- | --- |
| `metadata.json` | repo、branch、commit、日期、來源 thread id、是否含敏感資訊。 |
| `thread-summary.md` | 可讀摘要、決策、已完成工作、剩餘風險。 |
| `transcript-redacted.md` | 必要時放人工或工具過濾後的 transcript。 |
| `artifacts-manifest.json` | 對話中提到的 log、CI run、smoke 檔案、commit 對照。 |

公開 repo 只放蒸餾後資訊：

- handoff
- workflow
- decision record
- development log
- docs index / registry

不要把 raw transcript、私密對話、API key、`.env`、本機帳號資訊或未整理的長聊天紀錄放進公開 repo。

## Public Handoff 內容邊界

公開文件應回答：

- 目前可驗證的 HEAD / branch / CI 狀態。
- 這輪改了什麼、如何驗證。
- 下一位 agent 先讀哪些文件。
- 哪些功能是 stable、bounded、partial、contract-only、planned。
- 哪些工作區可寫、哪些只能 read-only。
- raw transcript 若必要，應到 private `dialogue-save` 哪個路徑查。

公開文件不應保存：

- 未整理 raw transcript。
- 登入資訊、credential、API key、cookie、token。
- 使用者個人資料。
- 其他專案的私有內容。
- 尚未確認可公開的第三方資料。

## Checkpoint 模板

完成一個可接手 checkpoint 時，在公開 repo 留下最小資訊：

```text
Checkpoint:
- Commit:
- Branch:
- Tests / checks:
- GitHub Actions:
- Docs updated:
- Raw transcript backup:
  - private repo path only, no transcript content in public repo
- Next safe action:
```

若沒有 raw transcript 備份，明確寫：

```text
Raw transcript backup: not created for this slice.
```

## 目前主線

RRKAL 目前仍以資料資產小閉環為第一優先：

```text
seed -> crawler -> candidate -> plan -> download -> import -> UI
```

Codex Cloud handoff 不是產品功能，而是工作流穩定性補強。它不能取代 smoke、CI、docs drift check 或 maturity matrix。
