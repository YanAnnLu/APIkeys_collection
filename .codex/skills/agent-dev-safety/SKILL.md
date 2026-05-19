---
name: agent-dev-safety
description: Use for general software development handoff and repository safety. Trigger when taking over an unfamiliar repo, coordinating with another agent, protecting user changes, avoiding destructive Git/file operations, managing environments safely, or deciding what to verify before commit/push.
---

# Agent Dev Safety

這是通用開發守則，不綁定 APIkeys_collection。目標是讓 Agent 在任何 repo 裡都先保護使用者成果，再開始改程式。

## 接手流程

1. 先確認位置與狀態：

```bash
pwd
git status --short --branch
git log -1 --oneline
```

2. 如果工作區不乾淨，先看 diff，不要直接 restore / reset / delete。
3. 如果有另一位 Agent 同時工作，先確認自己負責的檔案範圍；避免兩邊同時改同一個大型檔。
4. 開始前說明你會改哪些檔案；編輯前給使用者簡短更新。
5. 小步實作、小步驗證；不要把多個無關主題混成一個 commit。

如果使用者說「另一位 AI 會處理 git / push / commit」，本輪只做被要求的檔案工作與驗證，不要自行 commit、push、restore 或修 Git metadata。

## 禁止預設動作

- 不要執行 `git reset --hard`、`git checkout -- .`、大範圍 `git restore`，除非使用者明確要求。
- 不要刪除看起來奇怪的檔案；先查來源、diff、mtime、git status。
- 使用者若說「文件只需要讀」，不要順手整理、合併、刪除或重寫文件；只能摘出需要的規則，除非使用者明確授權編輯某類檔案。
- 不要提交 secrets、API key、token、cookie、private config。
- 不要把套件裝進 base/system Python；優先使用專案 env 或使用者指定 env。
- 不要因為測試卡住就用 destructive cleanup。先找 lock、process、cache、路徑問題。

## Git 與同步碟

如果 repo 在雲端同步碟或掛載碟，Git 可能出現假異常：

```text
index.lock 殘留
.git/index 被改名成 index 1
大量檔案被誤判刪除或 modified
CRLF/LF 或 filemode 假變更
```

先用非破壞性診斷：

```bash
git status --porcelain=v2 --branch
ls -la .git | sed -n '1,60p'
ps -ax -o pid,stat,command | rg 'git '
git diff --name-status
git diff --cached --name-status
```

移除 `.git/index.lock` 前，必須確認沒有 Git 程序正在跑。
如果 `.git/index` 不存在但有 `.git/index 1`，或 branch ref 變成 `main 1`，那通常是雲端同步造成的 Git metadata 錯位；先備份再修 metadata，不要把它當成源碼刪除事故處理。

## 驗證原則

改程式後至少跑與改動相關的測試。若不能跑，明確說明原因。

常見順序：

```bash
python -m py_compile TARGETS
python -m unittest TARGET_TESTS
python -m unittest discover -s tests
git diff --check
```

文件-only 改動至少跑 `git diff --check`。

## 匯報格式

對初學者說明時，用白話講：

```text
我改了什麼
為什麼這樣改
怎麼驗證
還剩什麼風險
距離 MVP / 目標還差哪幾塊
```

不要只列檔案名或工程術語。
