# 文件索引與整理規則

最後更新：2026-05-27

這份文件是「文件地圖」。它不是要把其他文件降級，而是要讓下一位 Agent 或組員知道每份文件負責什麼、該先讀哪裡、改完功能後要回頭更新哪幾份文件。

核心原則：目前 `docs/` 裡的每份文件都可能保存重要決策。不要因為兩份文件看起來重複，就直接刪除、覆蓋或忽略；先確認它們各自承載的是接力、產品定位、使用說明、技術總覽、子系統細節，還是歷史狀態。

文檔漂移防護：文件是契約，但可能漂移。接手時先以已驗證行為建立現況：tests、CLI JSON、smoke result、實際 UI 行為、`git diff`、GitHub Actions。若文件和已驗證行為衝突，以已驗證行為為準，回報漂移，並做最小必要修補。`DEVELOPMENT_LOG.zh-TW.md` 是歷史證據，不是目前真相。

另一個重要原則：這些 `.md` 是專案知識與文件結構的 source of truth；Agent skill、handoff prompt、OpenSpec/Spectra 流程或外部自動化是消費這些文件的操作層。文件整理的方向應由 `.md` 的角色與專案維護性決定，不應反過來讓舊 skill 路徑凍結文件架構。合併、改名、刪除文件前，仍必須搜尋 `.codex/skills/`、`.gemini/`、`.github/skills/`、`.github/prompts/`、`openspec/`、`scripts/` 是否引用該路徑；整理好 `.md` 後，再回頭更新 skill/prompt/script 的引用，並在過渡期保留 redirect/summary 以免舊流程立刻失效。

## 雙語文件規則

未來如果新增英文文件，必須同時準備繁中版本，或至少在同一輪提交裡提供清楚的繁中入口摘要與連結。若大幅更新既有英文文件，例如 `ARCHITECTURE.md`、`TECH_STACK.md`、`PROJECT_STATE.md`、`GIT_HANDOFF.md`，也要同步更新對應的繁中文件或在 `DOCS_INDEX.zh-TW.md` 標出繁中閱讀路線。

白話說：英文可以保留給工程細節與工具慣例，但接力、產品判斷、使用者會讀的流程，必須有繁中版本讓下一位人類或 Agent 不用猜。

根目錄 `README.md` 已有繁中對應入口 `README.zh-TW.md`。README 類型的根入口允許成對存在，因為它們是新使用者最先看到的語言入口，不視為不必要的文件碎片。

## Mermaid 圖說規則

凡是描述調度流程、資料流、跨模組依賴、Demo 操作路線或中長期平台邊界，優先用 Mermaid 補圖說，再搭配文字表格。尤其是這幾類文件：

- `ARCHITECTURE.zh-TW.md`
- `CODE_RELATIONSHIP_MAP.zh-TW.md`
- `MVP_FLOW_AUDIT.zh-TW.md`
- `USER_MANUAL.zh-TW.md`
- `TECHNICAL_OVERVIEW.zh-TW.md`

小型規則或單一 CLI 指令不用硬畫圖；但只要牽涉「誰調誰」或「按下按鈕後資料怎麼走」，就應該有 Mermaid。

繁中 `.md` 裡的 Mermaid 圖，人類可見的節點名稱與箭頭文字要優先使用繁體中文。模組路徑、CLI 參數、檔名、產品名、標準名可以保留英文或原文，但不要讓整張流程圖以英文術語為主要閱讀語言。

## 快速閱讀路線

| 情境 | 建議先讀 | 目的 |
| --- | --- | --- |
| 新 Agent 接手 | `AGENT_START_HERE.zh-TW.md` -> `AGENT_HANDOFF.zh-TW.md` -> `PROJECT_GTD.md` -> `DOCS_INDEX.zh-TW.md` | 先看權威順序、目前主線與不要做什麼，再看最新接力、進度與文件地圖。 |
| 檢查文件是否漂移 | `DOCS_DRIFT_AUDIT.zh-TW.md` -> `AGENT_HANDOFF.zh-TW.md` -> 實際 CLI/test/UI/CI 證據 | 先看已知漂移與本輪修補，再用已驗證行為判斷文件是否可採信。 |
| 要看版本變更 | `DEVELOPMENT_LOG.zh-TW.md` -> `PROJECT_GTD.md` -> `AGENT_HANDOFF.zh-TW.md` | 先看每個已推送 checkpoint 屬於哪個開發階段、改了什麼、如何驗證、還有什麼風險。 |
| 想理解產品 | `PRODUCT_POSITIONING.zh-TW.md` -> `TECHNICAL_OVERVIEW.zh-TW.md` -> `ARCHITECTURE.zh-TW.md` | 先理解「資料工程版 Steam」和整體資料管線。 |
| 想理解中長期資料資產平台概念 | `DATA_ASSET_PLATFORM_CONCEPTS.zh-TW.md` -> `PRODUCT_POSITIONING.zh-TW.md` -> `PROJECT_GTD.md` | 先看資料資產、Discovery Tool、爬蟲資產 / Crawler Asset、湖倉/K8S、Render Studio、ML 與 connector 的總體概念，再回到 MVP 收束。 |
| 要改 crawler / adapter | `DATASET_DISCOVERY_NOTES.zh-TW.md` -> `MVP_FLOW_AUDIT.zh-TW.md` -> `PROJECT_GTD.md` | 避免把資料集硬寫死，維持 crawler-first，並確認候選、resolver、下載與匯入是否真的閉環。 |
| 要改 Web Preview / UIUX 對照層 | `WEB_PREVIEW_UIUX.zh-TW.md` -> `UI_UX_DEVELOPMENT_CONTRACT.zh-TW.md` -> `USER_GUIDE.zh-TW.md` | Web Preview 只做瀏覽器可檢查的 UIUX 薄層，必須共用後端 JSON contract，不得重寫 crawler/downloader/importer。 |
| 要改下載 / 匯入 / repair | `TECHNICAL_OVERVIEW.zh-TW.md` -> `ARCHITECTURE.zh-TW.md` -> `PROJECT_GTD.md` | 先確認 manifest、registry、SQLite 匯入和修復邊界。 |
| 要整理檔案或重構 | `CODE_RELATIONSHIP_MAP.zh-TW.md` -> `WORKSPACE_LAYOUT.zh-TW.md` -> `ARCHITECTURE.zh-TW.md` | 先看程式調度關係、檔案分類、路徑規則與拆分優先順序。 |
| 要檢查 Demo 閉環 | `MVP_FLOW_AUDIT.zh-TW.md` -> `USER_MANUAL.zh-TW.md` -> `PROJECT_GTD.md` | 先確認按鈕、CLI、下載、匯入、repair、MySQL 哪些真的閉環，哪些仍是骨架。 |
| 要改開發策略 / OpenSpec | `DEVELOPMENT_WORKFLOW_OPEN_SPEC.zh-TW.md` -> `AGENT_HANDOFF.zh-TW.md` -> `PROJECT_GTD.md` | 先確認哪些改動要走 spec-driven 流程、Spectra/Qt Designer 怎麼用、不能阻塞 MVP 的界線。 |
| 要給使用者操作 | `USER_GUIDE.zh-TW.md` -> `SETUP.zh-TW.md` | 先確認 UI、設定、啟動與日常操作說法。 |
| 要查 CLI 指令 | `USER_GUIDE.zh-TW.md` 的「開發者 CLI」章節 -> `CODE_RELATIONSHIP_MAP.zh-TW.md` | 先查常用指令與閉環 recipe，再看背後由哪些模組調度。 |

## 主文件地圖

| 文件 | 角色 | 何時更新 |
| --- | --- | --- |
| `AGENT_HANDOFF.zh-TW.md` | 跨機器/跨 Agent 接力卡，記錄最新狀態、雷點與下一步。 | 每次穩定節點、commit/push 前後、跨 Agent 前更新。 |
| `AGENT_START_HERE.zh-TW.md` | Agent 最短入口地圖，定義權威順序、目前主線、不要做什麼、K 槽參考邊界。 | 文檔分層、工作流或主線方向改變時更新；平常保持短。 |
| `PROJECT_GTD.md` | 進度主索引，列出每個產品區塊目前狀態與下一步。 | 每完成或改變一個功能閉環後更新。 |
| `DEVELOPMENT_LOG.zh-TW.md` | 開發日誌，從 2026-05-21 起用流水帳記錄 push / CI run；最近日期與同日內最新時間放最上方，成功 run 用 `**CHECKPOINT**` 標醒目，失敗 run 保留為 `**CI 失敗**`，每筆都要有 `開發階段` 與中文說明。 | 每次完成並推送一個版本 checkpoint 後追加，不重寫舊紀錄；需要回補時可用 GitHub Actions run list 反推。 |
| `HEARTBEAT_AUTOMATION.zh-TW.md` | heartbeat automation 的安全規則、CLI/script 入口、外部排程與 agent runner 邊界。 | 更改 heartbeat CLI、scheduler、停止條件或自動推進規則時更新。 |
| `DOCS_INDEX.zh-TW.md` | 文件地圖與整理規則。 | 新增、移動、合併文件時更新。 |
| `DOCS_DRIFT_AUDIT.zh-TW.md` | 文件漂移審計紀錄，列出已驗證現況、已修漂移、已知剩餘漂移風險與後續驗收路徑。 | 做文檔對齊、發現文件和實際行為衝突、或 showcase/驗收前做文件審計時更新。 |
| `CODE_RELATIONSHIP_MAP.zh-TW.md` | 程式關聯地圖，說明入口、子系統、調度方向、測試入口與註解規則。 | 拆模組、搬資料夾、調整 CLI/UI/backend 邊界時更新。 |
| `MVP_FLOW_AUDIT.zh-TW.md` | MVP 閉環稽核表，列出 Demo 流程、下載/匯入/repair/MySQL 的可驗證狀態與缺口。 | Demo 前後、發現按鈕沒有閉環、下載/匯入/crawler 行為改變時更新。 |
| `USER_MANUAL.zh-TW.md` | 帶圖說的使用者操作手冊，面向 Demo 與第一次操作。 | 新增 UI/CLI 操作、改變使用者流程、補圖說時更新。 |
| `PRODUCT_POSITIONING.zh-TW.md` | 產品定位：科學資料集與爬蟲資產 launcher、資料工程版 Steam、虛擬孿生資料管線。 | 產品語言或中長期方向改變時更新。 |
| `DATA_ASSET_PLATFORM_CONCEPTS.zh-TW.md` | 中長期概念總綱，整理資料資產、Discovery Tool、爬蟲資產 / Crawler Asset、標準化策略、湖倉/K8S、Render Studio、ML、Notion/TradingView connector 與 local-first 桌面形態。 | 重大產品概念討論、平台接口方向、商業化定位或中期 roadmap 改變時更新；不要把它當成當前 MVP 實作清單。 |
| `ARCHITECTURE.zh-TW.md` | 中文架構入口，說明本機 MVP、分散式閉環、模組層、資料夾目標結構與重要邊界。 | 模組責任、資料流、Hadoop/K8S/renderer/mobile/P2P 邊界改變時更新。 |
| `ARCHITECTURE.md` | 英文架構原文與跨語系參考。 | 大幅更新時同步更新 `ARCHITECTURE.zh-TW.md` 或至少補中文摘要。 |
| `TECHNICAL_OVERVIEW.zh-TW.md` | 中文技術總覽，白話說明資料、下載、SQL、AI、renderer 等主線。 | 新功能進入 MVP 或 skeleton 邊界改變時更新。 |
| `DATASET_TYPE_MAP.zh-TW.md` | 資料類型地圖，說明 table、GIS、time-series、array、media、RAG 等資料該怎麼想。 | 新增資料類型、storage hint、viewer hint 時更新。 |
| `DATASET_DISCOVERY_NOTES.zh-TW.md` | dataset discovery 主入口，聚焦 crawler-first、爬蟲資產 / Crawler Asset 的落點、candidate review、adapter 邊界、bounded resolver、download/import plan 與版本計畫。 | 改 crawler、crawler asset 概念、candidate、adapter resolver、download plan 時更新。 |
| `DATABASE_PORTAL_INTAKE.zh-TW.md` | 組員收集資料入口網站的表格與規則。 | intake 欄位、promotion 流程、Notion 同步規則改變時更新。 |
| `DEVELOPMENT_WORKFLOW_OPEN_SPEC.zh-TW.md` | OpenSpec / Spectra / Qt Designer 開發流程，定義中大型改動的規格化習慣。 | 開發流程、OpenSpec 工具、Spectra GUI、Qt/PySide6 工具位置或規格門檻改變時更新。 |
| `WORKSPACE_LAYOUT.zh-TW.md` | 工作區分類、檔案責任、`.py` 拆分優先順序、路徑規則，以及 `tem/` 本機暫存區的使用規則。 | 新增資料夾、搬檔、拆大型模組、改 runtime/暫存目錄時更新。 |
| `USER_GUIDE.zh-TW.md` | 使用者操作指南，保留較完整背景、操作說明與開發者 CLI 指令索引。 | UI/CLI 操作、選單名稱、使用流程改變時更新；Demo 快速手冊同步看 `USER_MANUAL.zh-TW.md`。 |
| `WEB_PREVIEW_UIUX.zh-TW.md` | HTML/CSS Web Preview 的定位、啟動方式與 Tk/Qt/QSS 對照規則。 | Web Preview endpoint、UIUX 對照流程、CSS/QSS token 或瀏覽器驗證方式改變時更新。 |
| `SETUP.zh-TW.md` | 安裝與啟動說明。 | Python/Conda/Docker/GitHub CLI/跨平台設定改變時更新。 |
| `TECH_STACK.md` | 技術棧與依賴邊界，目前偏工程英文。 | 依賴、CI、Docker、optional renderer stack 改變時更新，並同步補繁中摘要或對應文件。 |
| `PROJECT_STATE.md` | 較完整的狀態快照與歷史脈絡，目前偏英文。 | 大型里程碑或需要保留歷史狀態時更新；平常優先更新 GTD/handoff，若大改要補繁中入口。 |
| `GIT_HANDOFF.md` | Git/接力相關補充，目前偏英文。 | Git 流程、雲端同步碟風險、CI 追蹤方式改變時更新，並同步補繁中摘要或對應文件。 |

## 附錄地圖

| 文件 | 角色 | 何時更新 |
| --- | --- | --- |
| `appendices/discovery.zh-TW.md` | 舊 discovery 附錄路徑，現在保留為 redirect/摘要，避免舊 handoff、skill 或 prompt 失效。 | 不新增新規格；新 discovery 內容改寫到 `DATASET_DISCOVERY_NOTES.zh-TW.md`。 |
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

## 固定整理流程

當使用者要求「整理文件」、「重構 .md」、「收攏文件」或類似任務時，請依這套順序執行，避免每次重新討論規則：

1. 先跑 `git status --short --branch`，保護未提交或不屬於本輪的變更。
2. 先讀本文件、`AGENT_HANDOFF.zh-TW.md`、`PROJECT_GTD.md`，再依任務讀相關文件。
3. 用檔名與 heading 盤點，不要一次把所有大型概念文件塞進上下文。
4. 合併、改名、刪除前，搜尋 `.codex/skills/`、`.gemini/`、`.github/skills/`、`.github/prompts/`、`openspec/`、`scripts/`、`README.md` 的路徑引用。
5. 每次只整理一組文件，先判斷哪一份是 canonical source of truth，再決定其他文件要保留、改 redirect、或變成進階補充。
6. 舊路徑可能被 skill、prompt 或外部自動化使用時，先保留 redirect/summary，不直接刪檔。
7. `.md` 先整理好，再回頭更新 skill/prompt/script；不要讓舊 skill 路徑決定文件不能重構。
8. 繁中 `.md` 的 Mermaid 節點與箭頭文字要以繁體中文為主；檔名、CLI flag、模組路徑、產品名與標準名可保留原文。
9. 更新 `DOCS_INDEX.zh-TW.md`、`AGENT_HANDOFF.zh-TW.md`、`PROJECT_GTD.md`，追加 `DEVELOPMENT_LOG.zh-TW.md`，並同步 repo 內 `.codex/skills/apikeys-collection-launcher`。開發日誌採流水帳倒序格式，最近日期與同日內最新時間都在最上方；每筆 push/CI run 保留時間、開發階段、短 SHA、run ID、原始英文標題、中文說明與醒目的 `**CHECKPOINT**` / `**CI 失敗**` 標記。
10. 跑 `git diff --check`；若文件範例、腳本或生成流程有改，再跑對應測試。

## 近期收攏評估

這一段是文件重構候選，不代表立刻刪檔。原則是先保留入口、補 redirect/summary，再觀察下一輪 Agent 是否還依賴舊文件。

| 群組 | 現況 | 建議 |
| --- | --- | --- |
| 使用者操作 | `USER_GUIDE.zh-TW.md` 與 `USER_MANUAL.zh-TW.md` 有重疊 | 短期保留兩份：`USER_MANUAL` 做 Demo/圖說快速路線，`USER_GUIDE` 做完整背景。穩定後可把 `USER_GUIDE` 改成進階章節，手冊成為主入口。 |
| Discovery 說明 | `DATASET_DISCOVERY_NOTES.zh-TW.md` 已成為主入口；`appendices/discovery.zh-TW.md` 已改成 redirect | 保留 appendix 路徑給舊引用，但不要再把新 crawler/adapter 規格寫進 appendix。下一步可整理使用者手冊與使用者指南的重疊。 |
| 架構/技術棧/技術總覽 | `ARCHITECTURE.md`, `TECH_STACK.md`, `TECHNICAL_OVERVIEW.zh-TW.md`, `CODE_RELATIONSHIP_MAP.zh-TW.md` 互相重疊 | `CODE_RELATIONSHIP_MAP` 負責「誰調誰」，`TECHNICAL_OVERVIEW` 負責中文白話，`ARCHITECTURE` 負責圖與架構契約，`TECH_STACK` 負責依賴。未來若合併，先補繁中摘要，不要讓重要資訊只剩英文。 |
| 狀態/接力 | `PROJECT_STATE.md`, `PROJECT_GTD.md`, `AGENT_HANDOFF.zh-TW.md`, `DEVELOPMENT_LOG.zh-TW.md` 都描述狀態 | `AGENT_HANDOFF` 保持最新接力卡，`PROJECT_GTD` 保持進度表，`DEVELOPMENT_LOG` 保持版本日誌，`PROJECT_STATE` 逐步降級為歷史快照。 |
| Git/Setup/Heartbeat | `GIT_HANDOFF.md`, `SETUP.zh-TW.md`, `HEARTBEAT_AUTOMATION.zh-TW.md` 有跨平台與接力重疊 | 保留分工：`SETUP` 給安裝環境，`GIT_HANDOFF` 給 Git 事故與 CI，`HEARTBEAT` 給排程自動化。若重複，優先在 `AGENT_HANDOFF` 留短摘要和連結。 |
| Renderer/Unreal | `appendices/render_frontends.zh-TW.md`, `appendices/unreal_bridge.zh-TW.md`, `frontends/unreal/README.zh-TW.md` | 保留，因為一份講策略、一份講 bridge 設計、一份講 frontend 邊界。等 Unreal code 進 repo 後再重新整理。 |

近期文件整理任務：

1. 將 `USER_MANUAL.zh-TW.md` 作為 Demo 主入口，再把 `USER_GUIDE.zh-TW.md` 中重複的 step-by-step 段落改成連結。
2. 把 `PROJECT_STATE.md` 中仍是現況的段落搬到 GTD/handoff 或對應技術文件，剩下保留歷史快照。
3. 視 `TECHNICAL_OVERVIEW.zh-TW.md` 與 `ARCHITECTURE.zh-TW.md` 的重疊程度，補出更清楚的「白話總覽」與「架構契約」分工。
4. 每次合併都只做一組文件；先依 `.md` 的職責決定新結構，再搜尋並更新 skill/prompt/script 依賴，必要時保留 redirect/summary，跑 `git diff --check`，並在 `AGENT_HANDOFF` 記錄新的閱讀入口。

## Heartbeat Automation 補充入口

`docs/HEARTBEAT_AUTOMATION.zh-TW.md` 記錄 heartbeat automation 的安全規則、CLI/script 入口、外部排程與後續 agent runner 邊界。更改 heartbeat CLI、scheduler、停止條件或自動推進規則時，請同步更新該文件、`PROJECT_GTD.md` 與 `AGENT_HANDOFF.zh-TW.md`。
## UI/UX 開發契約

`docs/UI_UX_DEVELOPMENT_CONTRACT.zh-TW.md` 是 UI/UX 需求進入實作前的契約文件。當使用者用 Foxy、Steam、tem 或其他軟體舉例時，Agent 必須先萃取「互動精神」與「心流」，不能把參照軟體名稱直接寫進正式命名、程式碼或 UI 文案。中大型 UI 變更應先整理操作對象、入口、觸發方式、狀態變化、後端服務、錯誤狀態與驗收方式，再進入 Tk / Qt 實作。

## 2026-05-27 新增索引

- `DECLARATIVE_ARCHITECTURE_DECISION.zh-TW.md`：宣告式架構分階段決策。第一階段維持 MVP 閉環與 Python adapter/service/registry，第二階段才把穩定重複規則抽成 UI state、bounds form、content parser/importer、adapter review/download plan、feature flag 與 source profile contract。討論「一個通用蟲」、source profile YAML 或宣告式 contract 時，先讀這份文件，避免為抽象而全面重寫 crawler/importer/UI。
