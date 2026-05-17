# 文件索引與整理計畫

最後更新：2026-05-17

目前文件數量偏多，原因是專案定位快速擴張，需要先留下決策痕跡。下一階段應整理成「少數主文件 + 附錄」，避免接手者不知道該先讀哪裡。

## 建議閱讀順序

| 順序 | 文件 | 角色 |
| --- | --- | --- |
| 1 | `PRODUCT_POSITIONING.zh-TW.md` | 先理解產品定位：科學資料集 launcher + 虛擬孿生資料管線。 |
| 2 | `PROJECT_GTD.md` | 看目前功能進度與下一步。 |
| 3 | `ARCHITECTURE.md` | 看總 pipeline 與模組邊界。 |
| 4 | `TECHNICAL_OVERVIEW.zh-TW.md` | 中文技術總覽，給團隊快速接手。 |
| 5 | `SETUP.zh-TW.md` | 本機環境、Windows/macOS/Linux 啟動方式。 |

## 可合併候選

| 文件 | 建議 |
| --- | --- |
| `UNREAL_BRIDGE.zh-TW.md` | 長期可併入 `frontends/unreal/README.zh-TW.md`，保留必要設計重點即可。 |
| `RENDER_FRONTENDS.zh-TW.md` | 長期可併入 `TECHNICAL_OVERVIEW.zh-TW.md` 的 renderer/frontends 章節。 |
| `FAILURE_MODES.zh-TW.md` | 保留為附錄，和 repair/logs 功能同步更新。 |
| `DATASET_DISCOVERY_NOTES.zh-TW.md` | 保留為 discovery/provider adapter 附錄。 |
| `TECH_STACK.md` | 可保留英文/雙語技術棧，但避免和中文 overview 重複太多。 |
| `PROJECT_STATE.md` | 可被 `PROJECT_GTD.md` 與 handoff report 取代，之後考慮縮短。 |

## 整理目標

下一階段文件結構建議：

```text
docs/
  PRODUCT_POSITIONING.zh-TW.md
  PROJECT_GTD.md
  ARCHITECTURE.md
  TECHNICAL_OVERVIEW.zh-TW.md
  SETUP.zh-TW.md
  appendices/
    discovery.zh-TW.md
    failure_modes.zh-TW.md
    unreal_bridge.zh-TW.md
    render_frontends.zh-TW.md
```

整理原則：

- 主文件回答「這是什麼、做到哪、怎麼跑、下一步」。
- 附錄回答「某個子系統的細節」。
- GTD 是唯一進度主索引。
- 文件不要重複敘述同一段 pipeline；改成互相引用。
- 中文文件優先，英文文件保留給開源與跨團隊使用。
