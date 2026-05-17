# Dataset Discovery 補充說明

更新日期：2026-05-18

## 定位

目前專案不應再被理解成單純的 API key 清單，而是科學資料集啟動器。

供應商或資源站點比較像 Steam 上的發行商或資源站，資料集才是實際要下載、安裝、清洗、接到 SQL 或渲染器的內容。

因此不要把每一個資料集都寫成一段 Python 硬編碼。比較健康的模型是：

```text
provider / source platform
-> searchable catalog / index / API / HTML listing
-> dataset candidates
-> reviewed dataset versions / file shards / query templates
-> download plan / import plan / renderer bridge
```

白話說：Alpha Vantage、NOAA、Google Earth Engine、MarineCadastre、ERDDAP 這些首先是供應商或資料平台；背後可能有很多資料集。第 1 階段應該優先把「發現資料集」的 crawler 做好，再挑代表資料集進入下載閉環。

## Discovery seeds

內建 provider/source discovery seeds 已從 8 個擴充到 43 個。範圍包含：

- 氣候與天氣
- 海洋與水文
- 生物多樣性
- 地理空間與地形
- 統計與經濟
- 研究 metadata
- 台灣區域開放資料
- Data.gov / CKAN 類開放資料目錄
- STAC 類地球觀測目錄
- Smithsonian / Wikidata / Dataverse 類文化資產與研究資料目錄
- Marine Regions / VLIZ 類海域法域 GIS 來源
- Google Earth Engine
- NOAA AIS / MarineCadastre
- NOAA GOES-R cloud/moisture imagery

這些 seed 只是搜尋與匯入候選來源的起點，不是最終 catalog。未來使用者可以透過 local seed 檔或 UI 手動新增區域平台、研究機構、政府資料站或團隊內部資料站。

## Dataset discovery sources

`catalog/dataset_discovery_sources.json` 是下一層：它不是新增供應商，而是描述「去哪個供應商的哪個目錄找資料集」。

目前 `catalog/dataset_discovery_sources.json` 內建 10 個可爬資料目錄。支援的通用 crawler 類型：

- `ncei_search`：查 NOAA/NCEI Common Access Search Service，適合從關鍵字找到 NOAA 資料集候選。
- `erddap_all_datasets`：讀 ERDDAP `allDatasets` JSON table，適合從 ERDDAP 站點列出可用 dataset。
- `html_file_index`：讀簡單 HTML 檔案索引，用 regex 找出版本/檔案 shard，例如 MarineCadastre AIS daily CSV.ZST。
- `cmr_collections`：查 NASA Earthdata CMR collection search，適合從 NASA/Earthdata 目錄找到可再審核的衛星、海洋、氣候資料集。
- `stac_collections`：讀 STAC `/collections`，適合 Microsoft Planetary Computer、Earth Search 這類雲端地球觀測 catalog。
- `gbif_dataset_search`：查 GBIF registry dataset search，適合先發現生物多樣性資料集與 record count，再決定是否進入 GBIF download workflow。
- `ckan_package_search`：讀 CKAN `package_search`，適合 Data.gov 這類政府開放資料目錄；resource URL 可能是檔案、API、入口頁或外部系統，必須 review。

這些 crawler 的共通目標是「先產生候選 metadata」。例如 STAC 只先列 collection，不直接抓每一張影像；CMR 只先列 collection，不直接全量抓 granules；CKAN 只先保留 resource 摘要，不把未知 URL 直接交給 downloader。

AIS 與衛星雲圖請當作 crawler 的代表測試案例，不要當成特例硬寫：

- AIS：應從 MarineCadastre/NOAA index 發現 daily shards，metadata 標成 `spatiotemporal_trajectory`。
- 衛星雲圖：應從 NOAA/NCEI/GOES-R 或 Earth Engine 類 catalog 發現，metadata 標成 `raster_or_grid`，後續才進入 renderer/tile/time-animation 設計。

CLI smoke：

```bash
python3 APIkeys_collection.py --init-db --seed --discover-dataset-candidates --dataset-discovery-source marinecadastre_ais_daily_index_2025 --dataset-discovery-limit 2 --write-dataset-candidates dataset_candidates.smoke.json --upsert-dataset-candidates --summary
```

這只會產生候選 metadata，不會下載 AIS 大檔。

## Dataset adapters

Source-site discovery 和 dataset discovery 已經分開：

- `api_launcher/discovery.py`：負責從官方來源站抓取可審核的 provider/source candidate。
- `api_launcher/dataset_discovery.py`：負責從 provider/source 的搜尋 API、ERDDAP `allDatasets`、HTML index、NASA CMR、STAC、GBIF、CKAN 抓取可審核的 dataset candidate。
- `api_launcher/dataset_adapters.py`：集中註冊 provider-specific dataset adapter。
- `api_launcher/adapters/gebco.py`：把 GEBCO 對應成 GEBCO 2025 全球高程網格 dataset。
- `api_launcher/adapters/hyg.py`：第一個具體 adapter，會把 HYG Database 對應成 HYG v3.8 星表 dataset。
- `api_launcher/renderer_contracts.py`：保存渲染器共用 dataset ID，避免 launcher 與 `taichi_global_bathymetry.py` 各自硬編碼名稱。

Adapter 仍然重要，但它應該處理「crawler 找到候選後，如何產生安全的 bounded query、驗證、匯入、轉換」，不是拿來取代 catalog crawler。HYG/GEBCO adapter 測試指令：

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

若計畫裡已有 direct entry，可用 CLI 執行：

```bash
python3 APIkeys_collection.py --init-db --seed --run-download-plan state/hyg_dataset_plan.json --verify-downloads --manifest-health
```

`--run-download-plan` 只會送出有直接 `download_url` 且未標記 `adapter_required` 的 entry。下載完成後會驗 sidecar manifest，並把健康 payload 登錄成 managed filesystem `file` asset。需要 smoke test 時可加 `--download-plan-limit N`。

若下載結果是 CSV/CSV.GZ，且 sidecar manifest 健康，可進一步匯入 curated SQLite table：

```bash
python3 APIkeys_collection.py --init-db --seed --import-csv-manifest downloads/sample.csv.manifest.json --import-sqlite-db state/curated_imports.sqlite --import-table sample_curated
```

目前這是 MVP 級匯入：所有欄位先以 `TEXT` 存放，欄位名稱會轉成安全 SQL identifier，table 會帶 schema fingerprint 登錄回 install registry。要覆蓋既有 table 時必須明確加 `--import-replace-table`。

若 registry 裡已經有多個健康 CSV/CSV.GZ manifest，可批次匯入：

```bash
python3 APIkeys_collection.py --import-verified-csv-manifests --import-sqlite-db state/curated_imports.sqlite
```

批次匯入預設會跳過非 CSV、不健康 manifest，以及已存在的 table；可搭配 `--provider ID` 限定資料商。

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
