# 工作區分類與拆分規則

最後更新：2026-05-18

這份文件用來回答兩個問題：

1. 這個專案的檔案應該放在哪裡。
2. 當核心 `.py` 變大時，應該先拆哪裡、怎麼拆，才不會破壞路徑與相容入口。

## 快速盤點指令

```bash
conda run -n metal_trade_312 python APIkeys_collection.py --workspace-inventory --write-workspace-inventory-json state/workspace_inventory.json
```

這個指令會輸出目前工作區分類、過大的 Python 檔案，以及疑似還留在根目錄的 runtime 產物。它只是盤點，不會自動搬檔或刪檔。

## 主要資料夾

| 路徑 | 角色 | 規則 |
| --- | --- | --- |
| `APIkeys_collection.py` | CLI 相容啟動入口 | 根目錄只保留薄 wrapper，不再塞業務邏輯。 |
| `APIkeys_collection_ui.py` | Tk UI 相容啟動入口 | 只轉呼叫 `frontends/tk/launcher_ui.py`。 |
| `api_launcher/` | 後端主套件 | Catalog、下載、匯入、crawler、整合、repository、CLI 都在這裡。 |
| `api_launcher/cli_*.py` | CLI 子功能 | 新 CLI 群組優先放這裡，避免 `core.py` 繼續變大。 |
| `api_launcher/crawlers/` | 資料集發現爬蟲 | 上層 orchestrator 統一調度，小爬蟲依 source type 拆分。 |
| `api_launcher/downloads/` | 下載/驗證/修復 | 不要被 `.gitignore` 的 `/downloads/` runtime 目錄誤傷。 |
| `api_launcher/importers/` | CSV/JSON/archive 匯入 | raw -> curated 的 bounded transform 放這裡。 |
| `frontends/tk/` | 目前 Tk 控制台 | UI 過渡期仍保留，但業務邏輯要慢慢外移到 `api_launcher/`。 |
| `frontends/unreal/` | Unreal frontend 邊界文件 | Unreal 專案本體仍在 repo 外；這裡只放橋接規則/工具。 |
| `renderers/` | Taichi/renderer prototype | 保持輕量，不要讓重型 renderer 依賴污染 launcher 基本測試。 |
| `catalog/` | 正式可提交 catalog/reference | 只有通過 review/audit 的 seed/source 才進這裡。 |
| `config/` | example config 與 ignored local config | `*.local.json` 放本機設定，不提交 token/key。 |
| `docs/` | 主文件與附錄 | `AGENT_HANDOFF.zh-TW.md` 是接力入口，`PROJECT_GTD.md` 是進度主索引。 |
| `scripts/` | 開發/維護腳本 | 不要把一次性 shell hack 寫進核心。 |
| `tests/` | 單元測試 | 新拆出的模組要補小測試，避免核心瘦身後行為漂移。 |
| `state/` | 本機 runtime 狀態 | ignored；放 logs、SQLite、private keys、staging、audit JSON。 |
| `downloads/` | 本機下載成果 | ignored；放資料 payload，不放 Python 原始碼。 |

## 目前拆分優先順序

| 優先 | 檔案 | 現況 | 建議拆法 |
| --- | --- | --- | --- |
| 1 | `api_launcher/core.py` | CLI orchestration 仍偏胖 | 每新增一群 CLI 功能，先建 `api_launcher/cli_*.py`；`core.py` 只保留 parse/run/order。 |
| 2 | `api_launcher/crawlers/dataset_sources.py` | 多種 source parser 擠在同檔 | 依 source type 拆成 CKAN、STAC、ERDDAP、CMR、repository index 等模組，再由 orchestrator 調度。 |
| 3 | `frontends/tk/launcher_ui.py` | UI 檔案最大 | MVP 後依 panel/dialog/service boundary 拆；不要在 UI 裡複製下載、匯入、crawler 判斷。 |
| 4 | `api_launcher/repository.py` | schema 穩定前仍集中 | 等 table contract 穩定後，拆 provider/dataset/manifest/install registry repository。 |
| 5 | `api_launcher/data_store_connections.py` | 多 engine contract 同檔 | 等 MySQL/PostgreSQL/SQLite/Hadoop profiles 更穩後，再拆 driver family。 |

這次已先做第一步小拆分：`api_launcher/cli_flags.py` 集中判斷「是否有 CLI 指令被指定」，讓 `core.py` 不再維護一大段旗標清單。

## 路徑規則

- 所有專案內路徑優先走 `api_launcher/paths.py`、`api_launcher/db.py` 的 resolver。
- 新增 CLI 輸出檔時，預設放 `state/`，除非它是正式 catalog/config/doc。
- 不要把 macOS `/Users/...` 或 Windows `K:\...` 類絕對路徑寫進程式碼。
- 跨平台路徑請用 `pathlib.Path` 與 `.as_posix()` 做可攜表示；只有在呼叫外部工具時才轉成本機字串。
- `.gitignore` runtime 目錄要用 `/state/`、`/downloads/` 這種 repo-root 寫法，避免忽略掉 `api_launcher/downloads/` 原始碼。
- CloudMounter / 雲端同步碟上跑測試時，建議加：

  ```bash
  PYTHONPYCACHEPREFIX=/tmp/apikeys_collection_pycache conda run -n metal_trade_312 python -m unittest discover -s tests
  ```

## 給下一位 Agent

整理工作區時，先跑 workspace inventory，再看 `git status --short`。不要因為某檔案位置看起來怪，就直接刪除或 `git restore`；先確認它是 runtime、local config、相容入口、正式 catalog，還是上一位 Agent/使用者留下的未提交成果。
