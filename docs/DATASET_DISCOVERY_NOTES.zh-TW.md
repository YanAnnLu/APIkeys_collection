# Dataset Discovery 補充說明

更新日期：2026-05-17

## 定位

目前專案不應再被理解成單純的 API key 清單，而是科學資料集啟動器。

供應商或資源站點比較像 Steam 上的發行商或資源站，資料集才是實際要下載、安裝、清洗、接到 SQL 或渲染器的內容。

## Discovery seeds

內建 discovery seeds 已從 8 個擴充到 30 個。範圍包含：

- 氣候與天氣
- 海洋與水文
- 生物多樣性
- 地理空間與地形
- 統計與經濟
- 研究 metadata
- 台灣區域開放資料

這些 seed 只是搜尋與匯入候選來源的起點，不是最終 catalog。未來使用者可以透過 local seed 檔或 UI 手動新增區域平台、研究機構、政府資料站或團隊內部資料站。

## Dataset adapters

Source-site discovery 和 dataset discovery 已經分開：

- `api_launcher/discovery.py`：負責從官方來源站抓取可審核的 provider/source candidate。
- `api_launcher/dataset_adapters.py`：集中註冊 provider-specific dataset adapter。
- `api_launcher/adapters/gebco.py`：把 GEBCO 對應成 GEBCO 2025 全球高程網格 dataset。
- `api_launcher/adapters/hyg.py`：第一個具體 adapter，會把 HYG Database 對應成 HYG v3.8 星表 dataset。
- `api_launcher/renderer_contracts.py`：保存渲染器共用 dataset ID，避免 launcher 與 `taichi_global_bathymetry.py` 各自硬編碼名稱。

HYG adapter 測試指令：

```powershell
py APIkeys_collection.py --init-db --seed --discover-datasets --provider hyg_database --db state\hyg_adapter_smoke.sqlite --summary
py APIkeys_collection.py --init-db --seed --discover-datasets --provider gebco --db state\gebco_adapter_smoke.sqlite --summary
```

注意：GEBCO 官方目前已釋出 2026 grid，但 `taichi_global_bathymetry.py` 的 bridge contract 仍固定在 GEBCO 2025。現階段先用 GEBCO 2025 作為穩定橋接版本，避免快取檔名與渲染器資料格式突然變動。後續應該獨立做一次 GEBCO 2026 migration 測試。

## 版本新鮮度

Seed 只能代表「官方入口」或「可探索來源」，不能保證它指向的是最新版資料。Dataset adapter 也可能為了 schema、快取檔名、渲染器相容性而刻意固定舊版。

因此後續 dataset metadata 應該包含：

- `version_status`
- `latest_known_version`
- `latest_known_release_date`
- `freshness_review_required`

例如 GEBCO 2025 對目前渲染器是 compatibility-pinned；它不是最新版宣稱，而是為了保持 `taichi_global_bathymetry.py` 目前的快取與資料格式穩定。

這套版本機制不是地圖資料專用。任何資料集都可能有舊版、最新版、穩定版、相容版或已棄用版本。Adapter 應該透過 `metadata.available_versions` 提供版本候選，UI 再透過通用的 `api_launcher/dataset_versions.py` 動態產生右鍵選單。

右鍵選單的設計目標：

- 預設新增 latest/default 版本。
- 可以手動選擇舊版或相容版。
- 下載計畫需要記錄使用者選擇的 dataset version。
- 未來同一資料集應可在同一計畫中同時排入多個版本，用於比較、重現研究或 migration 測試。

Dataset-version 下載計畫也是通用機制。`api_launcher/plans.py` 可把 adapter 發現的 `DatasetVersionOption` 轉成 plan entry，包含 `dataset_version`、direct/review eligibility、staging 設定，以及穩定的 `downloads/{provider}/{dataset}/{version}/...` 目標路徑。CLI 用法：

```bash
python3 APIkeys_collection.py --init-db --seed --provider hyg_database --export-dataset-plan state/hyg_dataset_plan.json
```

若版本 URL 看起來是入口頁、API endpoint 或下載 selector，而不是具體檔案，計畫會標記 `adapter_required`，並把網址放在 `adapter_review_url`；不要直接交給 HTTP downloader。

## 版本轉換與增量更新

版本切換不一定永遠是「更新到最新版」。使用者可能從很早期資料移到中間版本，也可能為了重現研究而降版本。

因此版本規劃要支援：

- install：本機沒有資料，第一次安裝。
- same：本機版本與目標版本相同，應可跳過。
- upgrade：往下一個新版。
- partial_forward：從舊版跳到較新的中間版本或更後版本。
- downgrade：往上一個舊版。
- partial_backward：從新版跳回更早的舊版。
- side-by-side：舊版與新版同時保留，避免破壞渲染器相容性或研究重現性。

實際更新時不應暴力刪除舊資料再重抓全包。比較理想的流程是先比對 manifest、checksum、schema fingerprint、資料列主鍵或 tile key，再只下載與合併變動部分。若 provider 不支援增量更新，才退回全量下載或並存安裝。

## AI / LLM metadata

未來本地 LLM 或 agent 可以利用這個 launcher 管理資料庫，但不是所有下載資料都適合直接拿去訓練語言模型。

表格、網格、時間序列、星表、地形資料，常常更適合放進 SQL、RAG、向量索引、特徵工程或領域模型，而不是直接餵給語言模型。

後續 catalog schema 建議新增：

- `license`
- `attribution_required`
- `redistribution`
- `commercial_use`
- `training_allowed`
- `rag_suitability`
- `data_quality_notes`

這能避免 agent 或開發者誤把只能研究使用、只能本地分析、或需要標註來源的資料拿去訓練或重分發。
