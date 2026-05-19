# OpenSpec / Spectra 開發流程

更新日期：2026-05-19

這份文件定義專案接下來的開發習慣。白話說：以前很多決策放在聊天與 handoff 裡，現在專案開始長出 crawler、adapter、下載、匯入、UI、Hadoop/K8S、renderer bridge 等多條線，光靠聊天記憶會越來越危險。OpenSpec 用來把「要做什麼、為什麼做、怎麼驗收」放進 Git；Spectra 是可視化輔助工具，讓人比較容易看 specs、changes、tasks。

## 目前已配置

| 工具 | 狀態 | 使用方式 |
| --- | --- | --- |
| OpenSpec CLI | 已初始化 | `npx -y @fission-ai/openspec@latest ...` |
| OpenSpec repo 目錄 | 已建立 | `openspec/specs/`、`openspec/changes/`、`openspec/changes/archive/` |
| Codex OpenSpec skills | 已建立 | `.codex/skills/openspec-*` |
| Gemini / GitHub Copilot OpenSpec prompt | 已建立 | `.gemini/`、`.github/prompts/`、`.github/skills/` |
| Spectra GUI | 已安裝在使用者層 | `open "$HOME/Applications/Spectra.app"` |
| Qt Designer | 已在專案 Conda env 內 | `conda run -n metal_trade_312 pyside6-designer` |

注意：Spectra 裝在 `~/Applications/Spectra.app`，不是系統 `/Applications`。Python/Qt 相關工具仍以 `metal_trade_312` 為主，不要把套件裝進 base 或 system Python。

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

建議用法：

```bash
open "$HOME/Applications/Spectra.app"
```

打開後選本 repo 根目錄：

```text
/Users/yen-an/Library/CloudStorage/CloudMounter-Google#1/APIkeys_collection
```

如果 Spectra 顯示空白，先確認 `openspec/specs/` 裡至少有一個 spec，並在終端機跑：

```bash
npx -y @fission-ai/openspec@latest validate --all --no-interactive
```

## Qt Designer 的定位

Qt Designer 是中期 UI 路線的設計工具，不代表現在要立刻重寫 Tk。它目前的價值是：

- 先讓未來 PySide6 介面的 layout、表格、抽屜、設定中心可以做原型。
- 避免 Tk UI 越修越大，後端服務邏輯仍要留在 `api_launcher/`。
- 未來若新增 `frontends/qt/`，它應該重用現有 crawler、download、import、event log、integration contract。

啟動方式：

```bash
conda run -n metal_trade_312 pyside6-designer
```

或直接打開 app bundle：

```bash
open "/opt/homebrew/anaconda3/envs/metal_trade_312/lib/qt6/bin/Designer.app"
```

不要為了 Qt Designer 另外在 base/system Python 安裝 PySide6。

## 下一位 Agent 要記住

- 使用者要的是扎實推進 MVP，不是為流程而流程。
- OpenSpec 是用來降低接力成本與返工，不是用來拖慢小修。
- Spectra 是 GUI 輔助；真正要 commit 的是 `openspec/`、`.codex/skills/`、`.gemini/`、`.github/prompts/` 與相關 docs。
- 中大型功能請先寫清楚 acceptance criteria，尤其是 crawler 這種「沒報錯但其實沒抓到資料」的區域。
- 完成一個穩定節點後：測試、更新文件、commit、push、看 CI。
