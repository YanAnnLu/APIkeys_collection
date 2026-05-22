# OpenSpec / Spectra 開發流程

更新日期：2026-05-22

這份文件定義專案接下來的開發習慣。白話說：以前很多決策放在聊天與 handoff 裡，現在專案開始長出 crawler、adapter、下載、匯入、UI、Hadoop/K8S、renderer bridge 等多條線，光靠聊天記憶會越來越危險。OpenSpec 用來把「要做什麼、為什麼做、怎麼驗收」放進 Git；Spectra 是可視化輔助工具，讓人比較容易看 specs、changes、tasks。

## 目前已配置

| 工具 | 狀態 | 使用方式 |
| --- | --- | --- |
| OpenSpec CLI | 已初始化 | `npx -y @fission-ai/openspec@latest ...` |
| OpenSpec repo 目錄 | 已建立 | `openspec/specs/`、`openspec/changes/`、`openspec/changes/archive/` |
| Codex OpenSpec skills | 已建立 | `.codex/skills/openspec-*` |
| Gemini / GitHub Copilot OpenSpec prompt | 已建立 | `.gemini/`、`.github/prompts/`、`.github/skills/` |
| Spectra GUI | macOS / Windows 皆可作為 OpenSpec 可視化輔助 | macOS: `open "$HOME/Applications/Spectra.app"`；Windows: `"%LOCALAPPDATA%\Spectra\spectra.exe"` |
| Qt Creator | Windows 目前尚未裝好或不在 PATH | 先跑 `.\scripts\check_ui_tooling.cmd` 確認；不要假設已可用 |
| Qt Designer / PySide6 | macOS 走 `metal_trade_312`；Windows 需另行準備 | macOS: `conda run -n metal_trade_312 pyside6-designer`；Windows: 先跑 `.\scripts\check_ui_tooling.cmd` |

注意：跨平台環境不能互相套用。`metal_trade_312` 是另一台 macOS 的 Conda env；本 Windows 工作站目前可找到 `C:\Users\lyn59\anaconda3\Scripts\conda.exe` 與 `py3_12_13`，但 `py3_12_13` 尚未安裝 PySide6，Qt Creator 也尚未裝好或不在 PATH。Python/Qt 相關工具不要裝進 base 或 system Python；先用 `scripts\check_ui_tooling.cmd` 查本機事實，再決定下一步。

## 什麼時候一定要走 OpenSpec

以下改動要先有 proposal / tasks / acceptance criteria，再實作：

- 跨模組改動，例如 crawler -> candidate -> adapter -> download plan -> import。
- 會改資料模型、install registry、manifest、catalog schema、local config schema。
- 會改 UI 資訊架構，例如設定中心、整合中心、Qt/PySide6 migration、背景常駐程式。
- 會接外部系統，例如 Hadoop、K8S、Notion sync、Google/OAuth、AI provider、資料庫 driver。
- 會新增 destructive 或半 destructive action，例如 drop table、delete payload、replace import、uninstall managed asset。
- 會影響跨平台路徑、啟動方式、CI、環境安裝。

小修可以不開正式 change，例如 typo、窄範圍測試補強、單一 parser bug、文件補一句。但完成後仍要更新 `PROJECT_GTD.md`、`AGENT_HANDOFF.zh-TW.md` 或相關文件。

## 建議工作節奏

1. Discuss：先用白話確認問題與限制，尤其要說清楚這一步距離 MVP 是變近還是只是在鋪路。
2. Propose：中大型改動在 `openspec/changes/<change-id>/` 建 proposal、design、tasks。
3. Apply：照 tasks 小步實作，每個可驗證節點跑測試。
4. Ingest：實作完成後，把新行為寫回 `openspec/specs/<capability>/spec.md` 或既有文件。
5. Archive：change 完成並驗證後移到 `openspec/changes/archive/`。

MVP 階段不追求每次都寫很厚的規格。重點是把風險、邊界、驗收標準寫出來，避免「做了很多，但不知道是否閉環」。

## 專案第一批 capability

| Capability | 用途 |
| --- | --- |
| `development-workflow` | 本文件對應的開發流程規格。 |
| `crawler-adapter-contract` | crawler candidate、adapter review、bounded resolver、download plan 的交接契約。 |
| `download-import-loop` | direct download、manifest、registry、CSV/JSON/archive import 的 MVP 閉環。 |
| `steam-like-library-model` | library / local install / workspace/save 三層模型。 |
| `qt-ui-migration` | 中期 PySide6/Qt UI 遷移，不阻塞目前 Tk MVP。 |

目前先建立 `development-workflow` spec。後續做 crawler/adapter 或 Qt UI 大改時，應補對應 capability。

## Spectra 的定位

Spectra 是給人看的 GUI，方便搜尋、瀏覽、追 task、檢查 artifact 一致性。Git 裡的 `openspec/` 仍是權威來源；不要只在 Spectra 裡留狀態而不提交檔案。

更精確地說，Spectra 不是只為 Qt 搬遷而存在。它是 OpenSpec 的可視化工作台：當專案有 UI/UX 發想、crawler/adapter 規格、MVP hardening 習慣、文件同步規則、checkpoint 規則或跨 agent 開發流程時，都可以用 Spectra 協助檢視與整理，但最終仍要落到 Git 追蹤的 `openspec/`、docs 或 skill。

建議用法：

```bash
open "$HOME/Applications/Spectra.app"
```

Windows：

```powershell
& "$env:LOCALAPPDATA\Spectra\spectra.exe"
```

打開後選本 repo 根目錄：

```text
/Users/yen-an/Library/CloudStorage/CloudMounter-Google#1/APIkeys_collection
```

如果 Spectra 顯示空白，先確認 `openspec/specs/` 裡至少有一個 spec，並在終端機跑：

```bash
npx -y @fission-ai/openspec@latest validate --all --no-interactive
```

若未來使用 `/spectra-apply`、`/spectra-commit` 或類似自動化來整理 commit message、搬運 tasks、同步 GTD / handoff，Agent 可以在使用者授權範圍內主動使用它們代辦行政文書、規格套用與 checkpoint 整理。這些工作視為 Agent 可直接執行的流程工作；自動化的目標是減少細顆粒 checkpoint 的文書成本。每個實質 commit 仍要留下清楚意圖、可回溯測試與 CI 結果，作為接力與問題回溯的證據；log-only commit 仍不新增開發日誌列，避免形成「更新日誌 -> commit -> 再更新日誌」的遞迴。

## Skill 與 OpenSpec 的分工

可以把它們想成同一套開發習慣的兩種呈現：

- `skill` 是代理人執行任務時的操作手冊，負責提醒「本輪要怎麼做」。
- `OpenSpec` 是專案層級的流程記憶與規格契約，負責保存「未來每一輪都應該遵守的習慣、驗收標準、任務切分、風險邊界」。
- docs / GTD / handoff 是人類與 agent 的閱讀入口，負責說明目前狀態與下一步。

因此，新的開發習慣不一定要立刻塞進 skill。若它是跨 agent、跨平台、跨模組或會反覆影響開發方式的習慣，優先整理成 OpenSpec requirement / change / task，再讓 skill 指向它。skill 不應取代 OpenSpec；skill 應該遵守並消費 OpenSpec。

## 可移植工作流套件

這套模式未來可以複製到其他專案，但不要整包硬搬 APIkeys_collection 的領域內容。可移植的是「開發治理骨架」，不是特定 crawler、provider、dataset、Qt 或 MySQL 規則。

最小可移植套件如下：

| 元件 | 搬到新專案時的角色 | APIkeys_collection 對應 |
| --- | --- | --- |
| 專案狀態板 | 告訴 agent 現在做完什麼、下一步是什麼 | `docs/PROJECT_GTD.md` |
| 接力卡 | 讓跨 agent / 跨機器交接不用重問背景 | `docs/AGENT_HANDOFF.zh-TW.md` |
| 開發日誌 | 保留 checkpoint、CI、驗證與階段標籤 | `docs/DEVELOPMENT_LOG.zh-TW.md` |
| 文件索引 | 讓 agent 只讀必要文件，降低 token 成本 | `docs/DOCS_INDEX.zh-TW.md` |
| OpenSpec workspace | 保存可版本化的開發習慣、規格與驗收標準 | `openspec/specs/`、`openspec/changes/` |
| 專案 skill | 把 OpenSpec / docs 的規則變成本輪執行提示 | `.codex/skills/<project-name>/SKILL.md` |
| 本地預檢腳本 | 在 push 前攔截常見錯誤 | `scripts/pre_push_smoke*` |
| 階段化回報規則 | 每輪說明目前階段、測試證據、剩餘進度 | 開發日誌的 `階段` 欄與 final 回報 |

移植順序建議：

1. 先建立 `docs/PROJECT_GTD.md`、`docs/AGENT_HANDOFF.<locale>.md`、`docs/DEVELOPMENT_LOG.<locale>.md`，讓專案有狀態、交接、歷史三層。
2. 再建立 `openspec/specs/development-workflow/spec.md`，只放跟該專案真的有關的 workflow requirement。
3. 接著建立專案 skill，內容只保留「每輪該讀哪些文件、怎麼驗證、怎麼提交、怎麼回報」。
4. 最後才加入專案特化的 pre-push smoke、CI watch、UI tooling 或資料庫 tooling。

原則：新專案先複製流程形狀，再刪掉所有 APIkeys_collection 專用名詞。若新專案還很小，OpenSpec 可以只放一份 `development-workflow` capability；等出現跨模組風險後再增加專門 capability。

## 本地預檢與 pre-push hook

推送前可先跑本地預檢：

```powershell
.\scripts\pre_push_smoke.cmd
```

這會檢查 working tree、staged diff，以及有 upstream 時的 `upstream..HEAD` 待推送 diff，接著執行核心入口 `py_compile`、完整 `unittest discover -s tests`、`--summary` 與離線 MVP demo smoke，並把 pycache 固定到 temp 目錄，降低 Windows/RaiDrive 鎖檔問題。若希望每次 `git push` 前自動執行，可在該 clone 本機安裝 hook：

```powershell
.\scripts\install_pre_push_hook.cmd
```

pre-push hook 是 `.git/hooks/` 內的本機設定，不會被 Git 追蹤；它負責把錯誤盡量擋在 push 前。push 後仍要跑 `gh run watch --exit-status`，讓遠端 checkpoint 留下可回溯 CI 紀錄。

若 agent 對話的 token 成本太高，優先使用簡報版預檢：

```powershell
.\scripts\pre_push_smoke_brief.cmd
```

它仍然執行同一套 `pre_push_smoke`，但完整輸出會落到 `state/logs/pre_push_smoke_*.log`，螢幕只顯示關鍵狀態、錯誤、traceback、unittest 與 MVP smoke 行。外部摘要器如 `distill` 只能作為可選後處理：用在 saved log 或 tail 上，不取代原始 log、CI、測試結果或開發日誌證據。Windows 上請用 `distill.cmd`；若 `distill.cmd --version` 失敗，就不要把它寫入工作流。2026-05-22 實測 `@samuelfaj/distill@1.5.2` 會尋找尚未發布的 `@samuelfaj/distill-win32-x64`，因此目前只記為可選工具，不列為專案依賴。

## Qt Creator / Qt Designer 的定位

Qt Creator / Qt Designer 是中期 UI 路線的工具，不代表現在要立刻重寫 Tk。它目前的價值是：

- 先讓未來 PySide6 介面的 layout、表格、抽屜、設定中心可以做原型。
- 避免 Tk UI 越修越大，後端服務邏輯仍要留在 `api_launcher/`。
- 未來若新增 `frontends/qt/`，它應該重用現有 crawler、download、import、event log、integration contract。

macOS 目前記錄的啟動方式：

```bash
conda run -n metal_trade_312 pyside6-designer
```

或直接打開 app bundle：

```bash
open "/opt/homebrew/anaconda3/envs/metal_trade_312/lib/qt6/bin/Designer.app"
```

不要為了 Qt Designer 另外在 base/system Python 安裝 PySide6。

Windows 目前先跑工具盤點：

```powershell
.\scripts\check_ui_tooling.cmd
.\scripts\check_ui_tooling.cmd -Json
```

截至 2026-05-22 這台 Windows 工作站的盤點結果：Spectra 2.3.1 可用；Qt Creator 尚未安裝或不在 PATH；Conda 可用於 `C:\Users\lyn59\anaconda3\Scripts\conda.exe`；`py3_12_13` 存在但尚未安裝 PySide6；`metal_trade_312` 不存在，因為它屬於另一台 macOS 工作站。

## 下一位 Agent 要記住

- 使用者要的是扎實推進 MVP，不是為流程而流程。
- OpenSpec 是用來降低接力成本與返工，不是用來拖慢小修。
- Spectra 是 GUI 輔助；真正要 commit 的是 `openspec/`、`.codex/skills/`、`.gemini/`、`.github/prompts/` 與相關 docs。
- 中大型功能請先寫清楚 acceptance criteria，尤其是 crawler 這種「沒報錯但其實沒抓到資料」的區域。
- 完成一個穩定節點後：測試、更新文件、commit、push、看 CI。
