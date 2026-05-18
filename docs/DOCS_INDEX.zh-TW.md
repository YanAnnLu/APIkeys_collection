# 文件索引與整理計畫

最後更新：2026-05-18

目前文件已開始整理成「少數主文件 + 附錄」。主文件回答產品定位、目前進度、架構、操作與設定；附錄保留 discovery、failure modes、Unreal/render frontend 等子系統細節，避免接手者一進來就被大量 `.md` 淹沒。

## 建議閱讀順序

| 順序 | 文件 | 角色 |
| --- | --- | --- |
| 1 | `AGENT_HANDOFF.zh-TW.md` | 跨機器/跨 Agent 接力的固定入口。 |
| 2 | `PRODUCT_POSITIONING.zh-TW.md` | 先理解產品定位：科學資料集 launcher + 虛擬孿生資料管線。 |
| 3 | `PROJECT_GTD.md` | 看目前功能進度與下一步。 |
| 4 | `ARCHITECTURE.md` | 看總 pipeline 與模組邊界。 |
| 5 | `USER_GUIDE.zh-TW.md` | 初學者/使用者操作指南：UI、AI 登入、提供商圖示、常用操作。 |
| 6 | `TECHNICAL_OVERVIEW.zh-TW.md` | 中文技術總覽，給團隊快速接手。 |
| 7 | `DATASET_TYPE_MAP.zh-TW.md` | 初學者友善的資料類型地圖：不同資料該用什麼儲存、分析、渲染方式。 |
| 8 | `DATABASE_PORTAL_INTAKE.zh-TW.md` | 組員收集資料庫入口網站的統一表格與規則。 |
| 9 | `WORKSPACE_LAYOUT.zh-TW.md` | 工作區分類、`.py` 拆分優先順序與路徑規則。 |
| 10 | `SETUP.zh-TW.md` | 本機環境、Windows/macOS/Linux 啟動方式。 |

## 附錄現況

| 文件 | 建議 |
| --- | --- |
| `appendices/unreal_bridge.zh-TW.md` | 長期可併入 `frontends/unreal/README.zh-TW.md`，保留必要設計重點即可。 |
| `appendices/render_frontends.zh-TW.md` | 長期可併入 `TECHNICAL_OVERVIEW.zh-TW.md` 的 renderer/frontends 章節。 |
| `appendices/failure_modes.zh-TW.md` | 保留為附錄，和 repair/logs 功能同步更新。 |
| `appendices/discovery.zh-TW.md` | 保留為 discovery/provider adapter 附錄。 |
| `DATASET_TYPE_MAP.zh-TW.md` | 保留為概念層附錄，也可在成熟後併入中文技術總覽。 |
| `DATABASE_PORTAL_INTAKE.zh-TW.md` | 保留為團隊資料入口收集表，定期轉入 catalog/crawler 設定。 |
| `WORKSPACE_LAYOUT.zh-TW.md` | 保留為工作區分類與拆分規則，避免 core/UI/crawler 持續膨脹。 |
| `TECH_STACK.md` | 可保留英文/雙語技術棧，但避免和中文 overview 重複太多。 |
| `PROJECT_STATE.md` | 可被 `PROJECT_GTD.md` 與 handoff report 取代，之後考慮縮短。 |

## 整理目標

目前文件結構目標：

```text
docs/
  PRODUCT_POSITIONING.zh-TW.md
  USER_GUIDE.zh-TW.md
  PROJECT_GTD.md
  ARCHITECTURE.md
  TECHNICAL_OVERVIEW.zh-TW.md
  DATASET_TYPE_MAP.zh-TW.md
  DATABASE_PORTAL_INTAKE.zh-TW.md
  WORKSPACE_LAYOUT.zh-TW.md
  SETUP.zh-TW.md
  appendices/
    discovery.zh-TW.md
    failure_modes.zh-TW.md
    unreal_bridge.zh-TW.md
    render_frontends.zh-TW.md
```

整理原則：

- 主文件回答「這是什麼、做到哪、怎麼跑、下一步」。
- `AGENT_HANDOFF.zh-TW.md` 是唯一的跨 Agent 接力卡，每次換手前都要更新。
- 附錄回答「某個子系統的細節」，路徑統一放在 `docs/appendices/`。
- GTD 是唯一進度主索引。
- 文件不要重複敘述同一段 pipeline；改成互相引用。
- 中文文件優先，英文文件保留給開源與跨團隊使用。
