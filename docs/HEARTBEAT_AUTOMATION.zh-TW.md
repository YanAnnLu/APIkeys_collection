# Heartbeat Automation 設計

Last updated: 2026-05-21

本文件定義 `APIkeys_collection` 的 heartbeat automation。第一階段做「喚醒後檢查、產生報告、推薦下一個 bounded task、產生可餵給外部 Codex/agent runner 的 prompt」。若要真的讓 agent 定時推進，使用 `scripts/heartbeat_codex.cmd`；它會先跑同一套安全檢查，只有 `safe_to_progress=true` 時才把 prompt 交給 `codex exec`。

## 目標

外部排程每 45 分鐘喚醒一次 launcher 檢查流程。每次檢查最多應支援 30 分鐘工作 checkpoint 的決策需求：

- 讀取 `docs/AGENT_HANDOFF.zh-TW.md` 與 `docs/PROJECT_GTD.md`。
- 檢查 Git 狀態、最新 commit、最新 GitHub Actions 狀態。
- 檢查是否有 tracked changes 或未追蹤檔案。
- 從 GTD 中挑出下一個符合 MVP 主線的候選任務。
- 產生 human-readable Markdown 與 agent-readable JSON。

## 目前入口

```powershell
py -B APIkeys_collection.py --heartbeat-report state\heartbeat\heartbeat.md
py -B APIkeys_collection.py --heartbeat-plan-json
py -B APIkeys_collection.py --write-heartbeat-plan-json state\heartbeat\heartbeat_plan.json
py -B APIkeys_collection.py --heartbeat-agent-prompt state\heartbeat\agent_prompt.md
```

Windows 可直接執行檢查。若 PowerShell 顯示「已停用指令碼執行」，請用 `.cmd` wrapper；它只對這次呼叫使用 `-ExecutionPolicy Bypass`，不會改系統設定：

```powershell
.\scripts\heartbeat_check.cmd
```

若要產生 agent prompt，但先不真的啟動外部 agent：

```powershell
.\scripts\heartbeat_agent.cmd
```

若要真的呼叫本機 Codex CLI 非互動推進：

```powershell
.\scripts\heartbeat_codex.cmd
```

首次接排程前建議先 dry-run：

```powershell
.\scripts\heartbeat_codex.cmd -DryRun
```

若要在 `safe_to_progress=true` 時呼叫外部 agent runner：

```powershell
.\scripts\heartbeat_agent.cmd -RunAgent -AgentExecutable "YOUR_AGENT_EXE" -AgentArguments "ARG1" "ARG2"
```

輸出位置預設為：

```text
state/heartbeat/heartbeat.md
state/heartbeat/heartbeat_plan.json
state/heartbeat/agent_prompt.md
state/heartbeat/codex_run.log
state/heartbeat/codex_last_message.md
```

`state/` 是 runtime/ignored 區域，適合讓外部排程反覆寫入。

## 任務選擇規則

Heartbeat planner 只推薦服務 MVP 主線的任務：

```text
seed -> crawler -> candidate -> plan -> download -> import -> UI
```

優先 lane：

1. CI / tests
2. repair / observability
3. adapter resolver
4. crawler source cleanup
5. UI 串接既有 backend
6. docs / handoff sync

中長期方向，例如 Qt rewrite、OAuth 產品化、Hadoop/K8S 實作、P2P、mobile，不應被 heartbeat 自動選為實作任務，除非 GTD 明確把它們拆成當前 MVP 的 bounded slice。

## 安全規則

Heartbeat 自動化不得：

- 執行 destructive DB/file 操作。
- 讀寫 API key、token、cookie、OAuth secret 或 private config。
- 安裝 base/system Python 套件。
- 覆蓋使用者或其他 agent 的變更。
- 直接 merge 未驗證成果。

如果 Git tracked worktree 不乾淨、CI 還在跑或失敗，heartbeat plan 會標記 `safe_to_progress=false`，建議停止並回報。

## 完成條件

後續若接上 agent runner，任一自動實作 checkpoint 必須：

- 有程式變更時跑 targeted tests。
- 合理情況下跑 full unittest。
- 跑 `py_compile` 與 `git diff --check`。
- commit message 描述單一 bounded slice。
- push 後用 `gh run watch --exit-status` 確認 CI。
- 更新受影響的 `AGENT_HANDOFF` / `PROJECT_GTD`。

## Windows Task Scheduler 範例

先用檢查模式：

```powershell
K:\APIkeys_collection\scripts\heartbeat_check.cmd
```

準備接外部 agent 時，改用 dry-run agent 模式：

```powershell
K:\APIkeys_collection\scripts\heartbeat_agent.cmd
```

要讓本機 Codex CLI 定時推進，Task Scheduler 建議設定：

```text
Program/script: cmd.exe
Arguments: /c K:\APIkeys_collection\scripts\heartbeat_codex.cmd
Start in: K:\APIkeys_collection
```

Trigger 設成每 45 分鐘重複一次，Settings 建議啟用「如果工作執行超過 30 分鐘則停止」。

確認外部 agent command 穩定後，才加上 `-RunAgent -AgentExecutable ...`。若需要 PowerShell array 或更複雜的 quoting，可直接使用：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File K:\APIkeys_collection\scripts\heartbeat_agent.ps1 -RunAgent -AgentExecutable "YOUR_AGENT_EXE" -AgentArguments @("ARG1", "ARG2")
```

## 後續階段

目前已具備 agent prompt / dry-run runner。真正進入第二階段前仍應先確認：

- 外部排程讀取 `heartbeat_plan.json`。
- 若 `safe_to_progress=true`，開 branch。
- 呼叫 Codex/API runner 執行單一 bounded slice。
- 跑測試、提交、推送 branch 或 draft PR。
- CI 綠燈後才允許人工或後續流程合併。
