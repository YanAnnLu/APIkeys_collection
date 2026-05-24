# RuRuKa Asset Launcher

RuRuKa Asset Launcher（短稱：RRKAL；內部相容名稱：APIkeys_collection）是一個類 Steam 的科學資料集、資料資產與本機資料庫 launcher。它不是單純 API key 清單，而是把「找資料源、審核資料集、挑版本、下載、驗證 manifest、匯入 SQLite / MySQL、修復資產、橋接渲染或分析工具」收進同一個可維護流程。

英文入口仍保留在 [README.md](README.md)。Agent 接手時先看 [docs/AGENT_START_HERE.zh-TW.md](docs/AGENT_START_HERE.zh-TW.md)，更完整的文件地圖請看 [docs/DOCS_INDEX.zh-TW.md](docs/DOCS_INDEX.zh-TW.md)。

## 目前能做什麼

- 管理 provider / source catalog，而不是把每個資料集硬寫死。
- 透過 crawler-first 流程產生 dataset candidates，再由人或規則審核。
- 把候選資料集輸出成 download/import plan。
- 只下載 direct file 或 bounded resolver 產生的安全小樣本，不把 HTML、登入頁或無邊界 API 當資料檔。
- 為下載結果寫 sidecar manifest、checksum 與 install registry 記錄。
- 將健康的 CSV / JSON / JSONL / NDJSON / GeoJSON 類 manifest 匯入 SQLite。
- 對下載檔、SQLite table、MySQL/PostgreSQL profile 做 self-check 與安全修復建議。
- 提供繁中 Tk UI 作為 MVP 控制台。
- 保留 Taichi / Unreal / Hadoop / K8S / P2P / mobile companion 等中長期架構邊界，但不讓它們搶走 MVP 主線。

## 快速啟動

Windows PowerShell：

```powershell
cd K:\APIkeys_collection
py -B APIkeys_collection.py --init-db --seed --summary
py -B APIkeys_collection_ui.py
```

macOS / Linux：

```bash
cd APIkeys_collection
python3 APIkeys_collection.py --init-db --seed --summary
python3 APIkeys_collection_ui.py
```

如果專案放在同步碟，建議測試時設定本機 bytecode 暫存，避免 `__pycache__` 鎖檔：

```bash
PYTHONPYCACHEPREFIX=/tmp/apikeys_collection_pycache python3 -m unittest discover -s tests
```

## CLI 開發入口

常用 CLI 指令索引先收攏在 [docs/USER_GUIDE.zh-TW.md](docs/USER_GUIDE.zh-TW.md) 的「開發者 CLI」章節，避免再新增一份重複文件。常見閉環：

```bash
python3 APIkeys_collection.py --discover-dataset-candidates --upsert-dataset-candidates
python3 APIkeys_collection.py --export-candidate-plan state/candidate_plan.json --candidate-plan-status approved
python3 APIkeys_collection.py --resolve-adapter-plan state/candidate_plan.json --write-resolved-adapter-plan state/candidate_plan.resolved.json
python3 APIkeys_collection.py --run-download-plan state/candidate_plan.resolved.json --import-supported-plan-results --import-sqlite-db state/curated_imports.sqlite
python3 APIkeys_collection.py --verify-downloads --manifest-health --self-check-databases
```

## 主要文件

| 文件 | 用途 |
| --- | --- |
| [docs/AGENT_START_HERE.zh-TW.md](docs/AGENT_START_HERE.zh-TW.md) | Agent 最短入口、權威順序、目前主線、不要做什麼。 |
| [docs/DOCS_INDEX.zh-TW.md](docs/DOCS_INDEX.zh-TW.md) | 文件地圖、整理規則、Mermaid 與雙語規則。 |
| [docs/AGENT_HANDOFF.zh-TW.md](docs/AGENT_HANDOFF.zh-TW.md) | 跨機器 / 跨 Agent 接力卡。 |
| [docs/PROJECT_GTD.md](docs/PROJECT_GTD.md) | 目前進度、MVP 狀態、下一步。 |
| [docs/DEVELOPMENT_LOG.zh-TW.md](docs/DEVELOPMENT_LOG.zh-TW.md) | 從 2026-05-21 起的開發日誌與 checkpoint 驗證紀錄。 |
| [docs/USER_GUIDE.zh-TW.md](docs/USER_GUIDE.zh-TW.md) | UI 操作、CLI 指令索引、日常使用。 |
| [docs/USER_MANUAL.zh-TW.md](docs/USER_MANUAL.zh-TW.md) | Demo / 第一次操作的圖說手冊。 |
| [docs/ARCHITECTURE.zh-TW.md](docs/ARCHITECTURE.zh-TW.md) | 中文架構入口。 |
| [docs/CODE_RELATIONSHIP_MAP.zh-TW.md](docs/CODE_RELATIONSHIP_MAP.zh-TW.md) | 程式調度關係與重構順序。 |
| [docs/DATASET_DISCOVERY_NOTES.zh-TW.md](docs/DATASET_DISCOVERY_NOTES.zh-TW.md) | crawler / candidate / adapter review 主入口。 |
| [docs/MVP_FLOW_AUDIT.zh-TW.md](docs/MVP_FLOW_AUDIT.zh-TW.md) | Demo 閉環稽核。 |
| [docs/SETUP.zh-TW.md](docs/SETUP.zh-TW.md) | 跨平台環境設定。 |

## 重要資料夾

| 路徑 | 用途 |
| --- | --- |
| `api_launcher/` | 核心 Python package。 |
| `frontends/tk/` | 目前 Tk UI 實作。 |
| `catalog/` | 內建 provider/source catalog 與參考資料。 |
| `config/` | 可提交的範例設定；本機覆寫檔不要提交。 |
| `docs/` | 文件、GTD、handoff、架構與操作手冊。 |
| `scripts/` | 啟動、heartbeat、自動化與維護腳本。 |
| `state/` | 本機 runtime 狀態，應被 Git 忽略。 |
| `downloads/` | 實際下載 payload，應被 Git 忽略。 |
| `.codex/skills/` | 專案本地 Codex skill 草稿。 |

## 安全規則

- 不提交 `state/`、`downloads/`、`.env`、`*.private.json`、真實 API key、token、cookie。
- 不把本機絕對路徑硬寫進程式或可提交 config。
- 不在 base/system Python 安裝套件；使用專案 venv、Conda env 或明確 optional requirements。
- 不自動 DROP table、刪檔或覆蓋資料，除非 adapter 能用 install_id 與 registry metadata 證明 ownership。
- crawler 成功不等於「沒有 exception」；0 筆、過少、全重複、payload shape 不符都要 warning/error。
- 繁中 `.md` 的 Mermaid 圖，節點與箭頭文字要優先使用繁體中文；檔名、CLI flag、模組路徑、產品名與標準名可保留原文。

## 目前進度

GTD 估算目前 MVP 剩餘約 `6.0% 到 6.5%`。下一批主要工作是把下載 / adapter / crawler / MySQL 這幾條閉環補得更完整，並持續整理文件與 skill 引用，避免功能與說明分裂。
