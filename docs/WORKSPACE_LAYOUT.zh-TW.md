# 工作區分類與拆分規則

最後更新：2026-05-24

這份文件用來回答三個問題：

1. 這個專案的檔案應該放在哪裡。
2. 當核心 `.py` 變大時，應該先拆哪裡、怎麼拆，才不會破壞路徑與相容入口。
3. 看到看似雜亂的檔案時，怎麼先分類，而不是直接刪除或搬移。

若問題是「不知道程式之間誰調誰」，先讀 `docs/CODE_RELATIONSHIP_MAP.zh-TW.md`；若問題是「Demo 到底哪個按鈕已閉環」，先讀 `docs/MVP_FLOW_AUDIT.zh-TW.md`。

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
| `api_launcher/crawlers/` | 資料集發現爬蟲 | `types.py` 放共用資料結構，`metadata.py` 放共用 metadata 判斷，`fetch.py` 放 HTTP/JSON/URL helper，`pagination.py` 放 full-crawl page cap 與去重 append helper，`ncei.py`/`stac.py`/`ckan.py`/`erddap.py`/`cmr.py`/`gbif.py`/`dataverse.py`/`zenodo.py`/`datacite.py`/`ogc_records.py`/`socrata.py`/`openalex.py`/`html_index.py` 是已拆出的 source 模組；query URL builder、payload parser、source-level fetch/parse flow 與 pagination flow 都優先放在各自模組；上層 orchestrator 統一調度。 |
| `api_launcher/downloads/` | 下載/驗證/修復 | 不要被 `.gitignore` 的 `/downloads/` runtime 目錄誤傷。 |
| `api_launcher/importers/` | CSV/JSON/archive 匯入 | raw -> curated 的 bounded transform 放這裡。 |
| `frontends/tk/` | 目前 Tk 控制台 | UI 過渡期仍保留，但業務邏輯要慢慢外移到 `api_launcher/`。`launcher_ui.py` 應只保留 widget、事件與視窗生命週期；純 helper 先放 `ui_helpers.py`，Provider table view-model 先放 `provider_models.py`，避免 7000 行主檔繼續膨脹。 |
| `frontends/unreal/` | Unreal frontend 邊界文件 | Unreal 專案本體仍在 repo 外；這裡只放橋接規則/工具。 |
| `renderers/` | Taichi/renderer prototype | 保持輕量，不要讓重型 renderer 依賴污染 launcher 基本測試。 |
| `catalog/` | 正式可提交 catalog/reference | 只有通過 review/audit 的 seed/source 才進這裡。 |
| `config/` | example config 與 ignored local config | `*.local.json` 放本機設定，不提交 token/key。 |
| `docs/` | 主文件與附錄 | `AGENT_HANDOFF.zh-TW.md` 是接力入口，裡面也包含跨平台檢查表；`PROJECT_GTD.md` 是進度主索引。 |
| `openspec/` | OpenSpec 規格工作區 | 中大型變更的 specs/changes/archive 放這裡；Spectra 只是 GUI，Git 裡的文件才是權威來源。 |
| `.codex/skills/`, `.gemini/`, `.github/prompts/`, `.github/skills/` | AI/Agent OpenSpec workflow glue | 由 OpenSpec init 生成，用來讓 Codex/Gemini/Copilot 採用同一套 propose/apply/archive 習慣。 |
| `scripts/` | 開發/維護腳本 | 不要把一次性 shell hack 寫進核心。 |
| `tests/` | 單元測試 | 新拆出的模組要補小測試，避免核心瘦身後行為漂移。 |
| `state/` | 本機 runtime 狀態 | ignored；放 logs、SQLite、private keys、staging、audit JSON。 |
| `downloads/` | 本機下載成果 | ignored；放資料 payload，不放 Python 原始碼。 |
| `tem/` | 本機暫存與外部產物緩衝 | ignored；放外部 agent 交接包、概念 prototype、截圖、logs 與待評估素材。團隊協作者從 Git clone 看不到這個資料夾，不要讓正式流程依賴 `tem/` 路徑。 |

## 檔案責任地圖

| 類型 | 例子 | 責任 | 整理方式 |
| --- | --- | --- | --- |
| 相容入口 | `APIkeys_collection.py`, `APIkeys_collection_ui.py` | 保留舊指令可用，實際邏輯轉到 package/frontend。 | 不要刪；只保持薄 wrapper。 |
| 後端產品邏輯 | `api_launcher/*.py` | catalog、repository、CLI、下載、匯入、repair、AI、data store、renderer contract。 | 依子系統拆小，不把業務邏輯放回根目錄。 |
| 前端入口 | `frontends/tk/launcher_ui.py`, `frontends/unreal/` | Tk UI 與未來 Unreal/Qt/mobile 前端邊界。 | UI 只呈現與觸發，複雜規則往 `api_launcher/` 移。 |
| 正式 catalog/config | `catalog/*.json`, `config/*.example.json` | 可提交的 provider/source/reference/example 設定。 | 只有通過 review/audit 的資料進正式 catalog。 |
| 文件 | `docs/*.md`, `docs/appendices/*.md` | 保存產品定位、接力狀態、架構、操作、子系統細節。 | 每份都視為重要；先更新索引，不直接刪除。 |
| 規格工作區 | `openspec/specs/*/spec.md`, `openspec/changes/*` | 保存中大型變更的規格、任務、驗收標準與 archive。 | 不用來取代 GTD/handoff；用來降低跨模組改動的接力成本。 |
| 測試 | `tests/test_*.py` | 保護既有行為，尤其下載、匯入、crawler、repair。 | 新拆模組或新功能要補小測試。 |
| 腳本 | `scripts/*` | 開發、啟動、環境設定。 | 不把一次性操作散進核心；跨平台腳本分開維護。 |
| renderer prototype | `renderers/taichi_global_bathymetry.py` | 下游渲染參考，不是資料治理 owner。 | 不讓重型 renderer 依賴影響基本 launcher 測試。 |
| runtime state | `state/`, root `*.sqlite`, `provider_candidates.discovered.json` | 本機資料庫、logs、staging、audit、暫存候選。 | 預設 ignored；能搬進 `state/` 的新輸出就不要留根目錄。 |
| downloaded payload | `downloads/` | 真正下載的資料檔。 | 預設 ignored；用 manifest/registry 管理，不手動提交。 |
| local temporary staging | `tem/` | 外部 agent 產物、概念原型、臨時 handoff bundle、截圖與 logs。 | 預設 ignored；只作本機評估與轉存，若內容變成正式資產，必須搬到 canonical docs/source 後再提交。 |

## 目前已知的根目錄 runtime 檔

workspace inventory 目前會看到這些根目錄 runtime 產物：

- `APIkeys_collection.sqlite`
- `APIkeys_collection.sqlite-shm`
- `APIkeys_collection.sqlite-wal`
- `provider_candidates.discovered.json`

它們不是原始碼，也不應提交。短期保留是為了相容舊路徑與目前使用者環境；新增功能產生的新狀態檔，預設應放進 `state/`。

## 分艙整理節奏

目前工作區不是災難，但已經進入 MVP 長大後需要分艙的階段。整理資料夾本身要當成獨立 checkpoint，不要混在 crawler、UI 或下載功能裡做。每次只搬一組，保留相容 import / wrapper，跑完整測試，再同步 `WORKSPACE_LAYOUT`、`CODE_RELATIONSHIP_MAP` 與必要 handoff。

建議排序：

1. 先收 runtime：新產物一律進 `state/`，不要再落根目錄；舊根目錄 runtime 只為相容保留。
2. 再拆 `core.py` 的 CLI routing：未來目標是 `api_launcher/cli/`，但短期仍可用 `cli_*.py` 小切片。
3. 再拆 discovery / crawler asset / database 三組，避免 `api_launcher/` 根層繼續平鋪膨脹。
4. 最後整理 Tk UI 與 tests 結構，尤其是大 dialog 與 workflow；UI 整理要等後端 service 邊界足夠清楚。

中期目標可以朝這種分艙靠攏，但不要一次搬完：

```text
api_launcher/
  cli/
  discovery/
  crawler_assets/
  database/
  registry/
  rendering/
  crawlers/
  downloads/
  importers/
  adapter_plan_resolvers/

frontends/tk/
  dialogs/
  workflows/
  models/
  launcher_ui.py
```

原則：資料夾整理不是美化，而是降低爆炸半徑。只要搬檔會影響 import path、測試 patch 點、CLI entrypoint 或 UI workflow，就要把它視為重構任務，而不是順手整理。

## 本機暫存資料夾 `tem/`

`tem/` 是本機暫存資料夾，主要用來暫放外部 agent 產出的 prototype、handoff bundle、截圖、logs 或其他還在評估中的素材。它已列入 `.gitignore`，所以不會出現在 GitHub，也不會出現在其他團隊協作者 clone 下來的工作區。

使用 `tem/` 時請遵守三個規則：

1. 不要 `git add`、commit 或 push `tem/` 內容。
2. 不要讓正式文件、程式、測試或自動化流程依賴 `tem/` 裡的路徑。
3. 若某個暫存素材確認有價值，請把重點摘要或必要檔案提升到正式 docs/source，再透過正常 review、測試與 commit 流程納入版本。

## 文件整理規則

- `docs/DOCS_INDEX.zh-TW.md` 是文件地圖；新增或改名文件時要更新它。
- `docs/AGENT_HANDOFF.zh-TW.md` 是接力卡；穩定節點、commit/push、CI 結果、重要雷點、跨平台測試指令與平台雷點都要更新。
- `docs/PROJECT_GTD.md` 是進度主索引；每個功能閉環完成後要更新。
- 子系統文件與附錄都要被尊重。若內容重複，先標註角色與引用關係，不要直接刪。
- 文件合併要分階段：先索引、再摘要、再 redirect，最後才考慮刪除。

## 目前拆分優先順序

| 優先 | 檔案 | 現況 | 建議拆法 |
| --- | --- | --- | --- |
| 1 | `api_launcher/core.py` | CLI orchestration 仍偏胖 | 每新增一群 CLI 功能，先建 `api_launcher/cli_*.py`；`core.py` 只保留 parse/run/order。 |
| 2 | `api_launcher/crawlers/dataset_sources.py` | 共用型別已移到 `api_launcher/crawlers/types.py`，共用 metadata helper 已移到 `metadata.py`，HTTP/JSON/URL helper 已移到 `fetch.py`，full-crawl page cap 與去重 append helper 已移到 `pagination.py`，各 source 的 query URL builder/parser/source-level fetch/parse flow/pagination flow 已移到各自模組；DataCite DOI crawler 已獨立成 `datacite.py`，OGC API Records crawler 已獨立成 `ogc_records.py`，Socrata catalog crawler 已獨立成 `socrata.py`，OpenAlex Works crawler 已獨立成 `openalex.py`；source type dispatcher 已改成 `SOURCE_CRAWLER_HANDLERS` mapping，並匯出 `SUPPORTED_DATASET_SOURCE_TYPES` 給 portal intake 共用 | 後續再新增 crawler type 時，請只新增 handler entry 與測試，不要把 if/elif 鏈加回來；保留 `discover_dataset_candidates_for_source()` 的相容入口。 |
| 3 | `frontends/tk/launcher_ui.py` | UI 檔案最大 | MVP 後依 panel/dialog/service boundary 拆；不要在 UI 裡複製下載、匯入、crawler 判斷。 |
| 4 | `api_launcher/repository.py` | schema 穩定前仍集中 | 等 table contract 穩定後，拆 provider/dataset/manifest/install registry repository。 |
| 5 | `api_launcher/data_store_connections.py` | 多 engine contract 同檔 | 等 MySQL/PostgreSQL/SQLite/Hadoop profiles 更穩後，再拆 driver family。 |

這次已先做幾個小拆分：`api_launcher/cli_flags.py` 集中判斷「是否有 CLI 指令被指定」，讓 `core.py` 不再維護一大段旗標清單；`api_launcher/crawlers/types.py` 集中 crawler 共用資料結構；`api_launcher/crawlers/metadata.py`、`api_launcher/crawlers/fetch.py`、`api_launcher/crawlers/pagination.py`、`api_launcher/crawlers/ncei.py`、`api_launcher/crawlers/stac.py`、`api_launcher/crawlers/ckan.py`、`api_launcher/crawlers/erddap.py`、`api_launcher/crawlers/cmr.py`、`api_launcher/crawlers/gbif.py`、`api_launcher/crawlers/dataverse.py`、`api_launcher/crawlers/zenodo.py`、`api_launcher/crawlers/datacite.py`、`api_launcher/crawlers/ogc_records.py`、`api_launcher/crawlers/socrata.py`、`api_launcher/crawlers/openalex.py`、`api_launcher/crawlers/html_index.py` 先把共用 helper、多個 source parser、query URL builder、source-level fetch/parse flow 與 NCEI/STAC/CMR/CKAN/GBIF/Dataverse/Zenodo/DataCite/OGC Records/Socrata/OpenAlex pagination flow 從 `dataset_sources.py` 拆出來。`dataset_sources.py` 現在也把 source type dispatcher 收斂成 `SOURCE_CRAWLER_HANDLERS` mapping，並讓 portal intake 共用 `SUPPORTED_DATASET_SOURCE_TYPES`。後續若繼續整理，請沿用這種小步、可測、保留舊匯入路徑的方式；不要把 crawler type 清單散回 UI、core 或入口表格。

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

若 Git 在雲端掛載碟上異常，例如 `status`/`diff` 崩潰或 object missing，先停止卡死的 Git 程序、確認沒有正在寫 index，再修復或改用乾淨 clone；不要在不確定 Git 狀態時做大規模搬檔。
