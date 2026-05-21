# 文件索引與整理規則

最後更新：2026-05-20

這份文件是「文件地圖」。它不是要把其他文件降級，而是要讓下一位 Agent 或組員知道每份文件負責什麼、該先讀哪裡、改完功能後要回頭更新哪幾份文件。

核心原則：目前 `docs/` 裡的每份文件都可能保存重要決策。不要因為兩份文件看起來重複，就直接刪除、覆蓋或忽略；先確認它們各自承載的是接力、產品定位、使用說明、技術總覽、子系統細節，還是歷史狀態。

另一個重要原則：這些 `.md` 是專案知識與文件結構的 source of truth；Agent skill、handoff prompt、OpenSpec/Spectra 流程或外部自動化是消費這些文件的操作層。文件整理的方向應由 `.md` 的角色與專案維護性決定，不應反過來讓舊 skill 路徑凍結文件架構。合併、改名、刪除文件前，仍必須搜尋 `.codex/skills/`、`.gemini/`、`.github/skills/`、`.github/prompts/`、`openspec/`、`scripts/` 是否引用該路徑；整理好 `.md` 後，再回頭更新 skill/prompt/script 的引用，並在過渡期保留 redirect/summary 以免舊流程立刻失效。

## 雙語文件規則

未來如果新增英文文件，必須同時準備繁中版本，或至少在同一輪提交裡提供清楚的繁中入口摘要與連結。若大幅更新既有英文文件，例如 `ARCHITECTURE.md`、`TECH_STACK.md`、`PROJECT_STATE.md`、`GIT_HANDOFF.md`，也要同步更新對應的繁中文件或在 `DOCS_INDEX.zh-TW.md` 標出繁中閱讀路線。

白話說：英文可以保留給工程細節與工具慣例，但接力、產品判斷、使用者會讀的流程，必須有繁中版本讓下一位人類或 Agent 不用猜。

## Mermaid 圖說規則

凡是描述調度流程、資料流、跨模組依賴、Demo 操作路線或中長期平台邊界，優先用 Mermaid 補圖說，再搭配文字表格。尤其是這幾類文件：

- `ARCHITECTURE.zh-TW.md`
- `CODE_RELATIONSHIP_MAP.zh-TW.md`
- `MVP_FLOW_AUDIT.zh-TW.md`
- `USER_MANUAL.zh-TW.md`
- `TECHNICAL_OVERVIEW.zh-TW.md`

小型規則或單一 CLI 指令不用硬畫圖；但只要牽涉「誰調誰」或「按下按鈕後資料怎麼走」，就應該有 Mermaid。

## 快速閱讀路線

| 情境 | 建議先讀 | 目的 |
| --- | --- | --- |
| 新 Agent 接手 | `AGENT_HANDOFF.zh-TW.md` -> `PROJECT_GTD.md` -> `DOCS_INDEX.zh-TW.md` | 先知道目前做到哪、怎麼安全換平台、下一步在哪、文件怎麼找。 |
| 想理解產品 | `PRODUCT_POSITIONING.zh-TW.md` -> `TECHNICAL_OVERVIEW.zh-TW.md` -> `ARCHITECTURE.zh-TW.md` | 先理解「資料工程版 Steam」和整體資料管線。 |
| 想理解中長期資料資產平台概念 | `DATA_ASSET_PLATFORM_CONCEPTS.zh-TW.md` -> `PRODUCT_POSITIONING.zh-TW.md` -> `PROJECT_GTD.md` | 先看資料資產、Discovery Tool、湖倉/K8S、Render Studio、ML 與 connector 的總體概念，再回到 MVP 收束。 |
| 要改 crawler / adapter | `DATASET_DISCOVERY_NOTES.zh-TW.md` -> `appendices/discovery.zh-TW.md` -> `PROJECT_GTD.md` | 避免把資料集硬寫死，維持 crawler-first。 |
| 要改下載 / 匯入 / repair | `TECHNICAL_OVERVIEW.zh-TW.md` -> `ARCHITECTURE.zh-TW.md` -> `PROJECT_GTD.md` | 先確認 manifest、registry、SQLite 匯入和修復邊界。 |
| 要整理檔案或重構 | `CODE_RELATIONSHIP_MAP.zh-TW.md` -> `WORKSPACE_LAYOUT.zh-TW.md` -> `ARCHITECTURE.zh-TW.md` | 先看程式調度關係、檔案分類、路徑規則與拆分優先順序。 |
| 要檢查 Demo 閉環 | `MVP_FLOW_AUDIT.zh-TW.md` -> `USER_MANUAL.zh-TW.md` -> `PROJECT_GTD.md` | 先確認按鈕、CLI、下載、匯入、repair、MySQL 哪些真的閉環，哪些仍是骨架。 |
| 要改開發策略 / OpenSpec | `DEVELOPMENT_WORKFLOW_OPEN_SPEC.zh-TW.md` -> `AGENT_HANDOFF.zh-TW.md` -> `PROJECT_GTD.md` | 先確認哪些改動要走 spec-driven 流程、Spectra/Qt Designer 怎麼用、不能阻塞 MVP 的界線。 |
| 要給使用者操作 | `USER_GUIDE.zh-TW.md` -> `SETUP.zh-TW.md` | 先確認 UI、設定、啟動與日常操作說法。 |

## 主文件地圖

| 文件 | 角色 | 何時更新 |
| --- | --- | --- |
| `AGENT_HANDOFF.zh-TW.md` | 跨機器/跨 Agent 接力卡，記錄最新狀態、雷點與下一步。 | 每次穩定節點、commit/push 前後、跨 Agent 前更新。 |
| `PROJECT_GTD.md` | 進度主索引，列出每個產品區塊目前狀態與下一步。 | 每完成或改變一個功能閉環後更新。 |
| `HEARTBEAT_AUTOMATION.zh-TW.md` | heartbeat automation 的安全規則、CLI/script 入口、外部排程與 agent runner 邊界。 | 更改 heartbeat CLI、scheduler、停止條件或自動推進規則時更新。 |
| `DOCS_INDEX.zh-TW.md` | 文件地圖與整理規則。 | 新增、移動、合併文件時更新。 |
| `CODE_RELATIONSHIP_MAP.zh-TW.md` | 程式關聯地圖，說明入口、子系統、調度方向、測試入口與註解規則。 | 拆模組、搬資料夾、調整 CLI/UI/backend 邊界時更新。 |
| `MVP_FLOW_AUDIT.zh-TW.md` | MVP 閉環稽核表，列出 Demo 流程、下載/匯入/repair/MySQL 的可驗證狀態與缺口。 | Demo 前後、發現按鈕沒有閉環、下載/匯入/crawler 行為改變時更新。 |
| `USER_MANUAL.zh-TW.md` | 帶圖說的使用者操作手冊，面向 Demo 與第一次操作。 | 新增 UI/CLI 操作、改變使用者流程、補圖說時更新。 |
| `PRODUCT_POSITIONING.zh-TW.md` | 產品定位：科學資料集 launcher、資料工程版 Steam、虛擬孿生資料管線。 | 產品語言或中長期方向改變時更新。 |
| `DATA_ASSET_PLATFORM_CONCEPTS.zh-TW.md` | 中長期概念總綱，整理資料資產、Discovery Tool、標準化策略、湖倉/K8S、Render Studio、ML、Notion/TradingView connector 與 local-first 桌面形態。 | 重大產品概念討論、平台接口方向、商業化定位或中期 roadmap 改變時更新；不要把它當成當前 MVP 實作清單。 |
| `ARCHITECTURE.zh-TW.md` | 中文架構入口，說明本機 MVP、分散式閉環、模組層、資料夾目標結構與重要邊界。 | 模組責任、資料流、Hadoop/K8S/renderer/mobile/P2P 邊界改變時更新。 |
| `ARCHITECTURE.md` | 英文架構原文與跨語系參考。 | 大幅更新時同步更新 `ARCHITECTURE.zh-TW.md` 或至少補中文摘要。 |
| `TECHNICAL_OVERVIEW.zh-TW.md` | 中文技術總覽，白話說明資料、下載、SQL、AI、renderer 等主線。 | 新功能進入 MVP 或 skeleton 邊界改變時更新。 |
| `DATASET_TYPE_MAP.zh-TW.md` | 資料類型地圖，說明 table、GIS、time-series、array、media、RAG 等資料該怎麼想。 | 新增資料類型、storage hint、viewer hint 時更新。 |
| `DATASET_DISCOVERY_NOTES.zh-TW.md` | dataset discovery 補充說明，聚焦 crawler-first、candidate review、adapter 邊界與版本計畫。 | 改 crawler、candidate、adapter resolver、download plan 時更新。 |
| `DATABASE_PORTAL_INTAKE.zh-TW.md` | 組員收集資料入口網站的表格與規則。 | intake 欄位、promotion 流程、Notion 同步規則改變時更新。 |
| `DEVELOPMENT_WORKFLOW_OPEN_SPEC.zh-TW.md` | OpenSpec / Spectra / Qt Designer 開發流程，定義中大型改動的規格化習慣。 | 開發流程、OpenSpec 工具、Spectra GUI、Qt/PySide6 工具位置或規格門檻改變時更新。 |
| `WORKSPACE_LAYOUT.zh-TW.md` | 工作區分類、檔案責任、`.py` 拆分優先順序與路徑規則。 | 新增資料夾、搬檔、拆大型模組、改 runtime 目錄時更新。 |
| `USER_GUIDE.zh-TW.md` | 使用者操作指南，保留較完整背景與操作說明。 | UI/CLI 操作、選單名稱、使用流程改變時更新；Demo 快速手冊同步看 `USER_MANUAL.zh-TW.md`。 |
| `SETUP.zh-TW.md` | 安裝與啟動說明。 | Python/Conda/Docker/GitHub CLI/跨平台設定改變時更新。 |
| `TECH_STACK.md` | 技術棧與依賴邊界，目前偏工程英文。 | 依賴、CI、Docker、optional renderer stack 改變時更新，並同步補繁中摘要或對應文件。 |
| `PROJECT_STATE.md` | 較完整的狀態快照與歷史脈絡，目前偏英文。 | 大型里程碑或需要保留歷史狀態時更新；平常優先更新 GTD/handoff，若大改要補繁中入口。 |
| `GIT_HANDOFF.md` | Git/接力相關補充，目前偏英文。 | Git 流程、雲端同步碟風險、CI 追蹤方式改變時更新，並同步補繁中摘要或對應文件。 |

## 附錄地圖

| 文件 | 角色 | 何時更新 |
| --- | --- | --- |
| `appendices/discovery.zh-TW.md` | discovery 子系統完整補充，與 `DATASET_DISCOVERY_NOTES.zh-TW.md` 互相對照。 | crawler source type、adapter handoff、candidate plan 流程改變時更新。 |
| `appendices/failure_modes.zh-TW.md` | 失敗模式與修復思路。 | 新增 repair scanner、database self-check、path repair、download recovery 時更新。 |
| `appendices/render_frontends.zh-TW.md` | renderer / frontend 方向補充。 | Taichi、Unreal、Cesium、chart frontend 邊界改變時更新。 |
| `appendices/unreal_bridge.zh-TW.md` | Unreal bridge 設計補充。 | Unreal exporter、tile manifest、UE 專案邊界改變時更新。 |

## 每次改動後的文件回頭檢查

改完程式後，請至少問自己這六件事：

1. 這個改動有沒有改變「目前進度」？有的話更新 `PROJECT_GTD.md`。
2. 這個改動會不會影響下一位 Agent 接力？有的話更新 `AGENT_HANDOFF.zh-TW.md`。
3. 這個改動是否新增/改變一條使用流程？有的話更新 `USER_GUIDE.zh-TW.md` 或 `SETUP.zh-TW.md`。
4. 這個改動是否改變資料流、模組邊界或長期架構？有的話更新 `ARCHITECTURE.md` 或 `TECHNICAL_OVERVIEW.zh-TW.md`。
5. 這個改動是否屬於某個子系統細節？有的話更新對應附錄或補充文件，例如 discovery、failure modes、Unreal bridge。
6. 這次是否新增英文文件，或大幅更新英文文件？有的話同步準備繁中版本、繁中摘要或清楚的繁中閱讀路線。

白話說：程式讓機器知道怎麼跑，文件讓下一個人知道為什麼這樣跑。兩邊都要保留。

## 整理策略

目前不建議一次大搬家。比較安全的整理順序是：

1. 先在 `DOCS_INDEX.zh-TW.md` 裡標出每份文件的角色。
2. 再在 `WORKSPACE_LAYOUT.zh-TW.md` 裡標出每類檔案的責任。
3. 等內容穩定後，若真的要合併文件，先把被合併文件改成短 redirect/summary，再觀察一段時間。
4. 只有在 Git 狀態乾淨、測試通過、使用者知道風險時，才搬移或刪除文件。

目前文件結構的目標不是「文件越少越好」，而是「每份文件有清楚任務」。接力文件、GTD、架構、技術總覽、使用者指南、工作區規則與各附錄都可以共存，只要索引清楚即可。

## 近期收攏評估

這一段是文件重構候選，不代表立刻刪檔。原則是先保留入口、補 redirect/summary，再觀察下一輪 Agent 是否還依賴舊文件。

| 群組 | 現況 | 建議 |
| --- | --- | --- |
| 使用者操作 | `USER_GUIDE.zh-TW.md` 與 `USER_MANUAL.zh-TW.md` 有重疊 | 短期保留兩份：`USER_MANUAL` 做 Demo/圖說快速路線，`USER_GUIDE` 做完整背景。穩定後可把 `USER_GUIDE` 改成進階章節，手冊成為主入口。 |
| Discovery 說明 | `DATASET_DISCOVERY_NOTES.zh-TW.md` 與 `appendices/discovery.zh-TW.md` 標題相同且內容接近 | 近期應比對差異，把重複段落收進主文件；附錄改成歷史補充或 redirect。不要直接刪，因為舊 handoff 可能引用附錄。 |
| 架構/技術棧/技術總覽 | `ARCHITECTURE.md`, `TECH_STACK.md`, `TECHNICAL_OVERVIEW.zh-TW.md`, `CODE_RELATIONSHIP_MAP.zh-TW.md` 互相重疊 | `CODE_RELATIONSHIP_MAP` 負責「誰調誰」，`TECHNICAL_OVERVIEW` 負責中文白話，`ARCHITECTURE` 負責圖與架構契約，`TECH_STACK` 負責依賴。未來若合併，先補繁中摘要，不要讓重要資訊只剩英文。 |
| 狀態/接力 | `PROJECT_STATE.md`, `PROJECT_GTD.md`, `AGENT_HANDOFF.zh-TW.md` 都描述狀態 | `AGENT_HANDOFF` 保持最新接力卡，`PROJECT_GTD` 保持進度表，`PROJECT_STATE` 逐步降級為歷史快照。未來大里程碑後可把舊 state 摘要化。 |
| Git/Setup/Heartbeat | `GIT_HANDOFF.md`, `SETUP.zh-TW.md`, `HEARTBEAT_AUTOMATION.zh-TW.md` 有跨平台與接力重疊 | 保留分工：`SETUP` 給安裝環境，`GIT_HANDOFF` 給 Git 事故與 CI，`HEARTBEAT` 給排程自動化。若重複，優先在 `AGENT_HANDOFF` 留短摘要和連結。 |
| Renderer/Unreal | `appendices/render_frontends.zh-TW.md`, `appendices/unreal_bridge.zh-TW.md`, `frontends/unreal/README.zh-TW.md` | 保留，因為一份講策略、一份講 bridge 設計、一份講 frontend 邊界。等 Unreal code 進 repo 後再重新整理。 |

近期文件整理任務：

1. 對 `DATASET_DISCOVERY_NOTES.zh-TW.md` 與 `appendices/discovery.zh-TW.md` 做逐節 diff，收斂重複內容。
2. 將 `USER_MANUAL.zh-TW.md` 作為 Demo 主入口，再把 `USER_GUIDE.zh-TW.md` 中重複的 step-by-step 段落改成連結。
3. 把 `PROJECT_STATE.md` 中仍是現況的段落搬到 GTD/handoff 或對應技術文件，剩下保留歷史快照。
4. 每次合併都只做一組文件；先依 `.md` 的職責決定新結構，再搜尋並更新 skill/prompt/script 依賴，必要時保留 redirect/summary，跑 `git diff --check`，並在 `AGENT_HANDOFF` 記錄新的閱讀入口。

## Heartbeat Automation 補充入口

`docs/HEARTBEAT_AUTOMATION.zh-TW.md` 記錄 heartbeat automation 的安全規則、CLI/script 入口、外部排程與後續 agent runner 邊界。更改 heartbeat CLI、scheduler、停止條件或自動推進規則時，請同步更新該文件、`PROJECT_GTD.md` 與 `AGENT_HANDOFF.zh-TW.md`。
