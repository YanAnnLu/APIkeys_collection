# Dataset Discovery 補充說明

更新日期：2026-05-19

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

目前 `catalog/dataset_discovery_sources.json` 內建 23 個可爬資料目錄。支援的通用 crawler 類型：

- `ncei_search`：查 NOAA/NCEI Common Access Search Service，適合從關鍵字找到 NOAA 資料集候選。
- `erddap_all_datasets`：讀 ERDDAP `allDatasets` JSON table，適合從 ERDDAP 站點列出可用 dataset。
- `html_file_index`：讀簡單 HTML 檔案索引，用 regex 找出版本/檔案 shard，例如 MarineCadastre AIS daily CSV.ZST。
- `cmr_collections`：查 NASA Earthdata CMR collection search，適合從 NASA/Earthdata 目錄找到可再審核的衛星、海洋、氣候資料集。
- `stac_collections`：讀 STAC `/collections`，適合 Microsoft Planetary Computer、Earth Search 這類雲端地球觀測 catalog。
- `ogc_api_records`：讀 OGC API Records `items` / FeatureCollection，適合從地理空間 metadata catalog 產生可審核資料集候選；只保留 record metadata，不直接下載背後的大型資料。若 record 連到 `mqtts://` 這類 broker/notification stream，crawler 會把它留在 metadata links，但不把它當成主要 `api_url` 或 direct download。
- `gbif_dataset_search`：查 GBIF registry dataset search，適合先發現生物多樣性資料集與 record count，再決定是否進入 GBIF download workflow。
- `dataverse_search`：查 Dataverse search API，適合 Harvard Dataverse 這類研究資料平台，先取得可審核的 dataset metadata。
- `zenodo_records_search`：查 Zenodo records API，適合先發現研究資料記錄與檔案摘要，再決定是否能進入 direct download 或 adapter review。
- `datacite_dois`：查 DataCite `/dois` public API，並以 `resource-type-id=dataset` 先找研究資料 DOI metadata；它只產生候選，不直接下載 DOI landing page 背後的檔案。若 metadata 裡有明確 `contentUrl`，會先整理成 resource 線索，交給後續 resolver 安全判斷。
- `openalex_works_search`：查 OpenAlex Works API，使用 `type:dataset` 篩選研究資料型 work；它只保留 OpenAlex/DOI/landing-page metadata，不直接下載 repository 檔案。
- `ckan_package_search`：讀 CKAN `package_search`，適合 Data.gov 這類政府開放資料目錄；resource URL 可能是檔案、API、入口頁或外部系統，必須 review。
- `socrata_catalog_search`：讀 Socrata Discovery/Catalog API，例如 NYC Open Data、DataSF、Chicago Data Portal；crawler 只把每個 resource 變成可審核候選，並保留 domain/resource id 給後續 `$limit=25` 小樣本 resolver。

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
- `api_launcher/crawlers/types.py`：放 dataset crawler 共用資料結構，例如 `DatasetDiscoverySource`、`DatasetCandidate` 與候選 metadata 轉換 helper。
- `api_launcher/crawlers/metadata.py`：放共用 metadata helper，例如安全 dataset id、分類合併、資料家族推論、storage/sql/analysis/viewer hint。
- `api_launcher/crawlers/fetch.py`：放 crawler 共用的 HTTP fetch helper、JSON 讀取檢查與搜尋 endpoint URL 組裝。
- `api_launcher/crawlers/pagination.py`：放 crawler 共用的 full-crawl page cap 與候選去重 append helper。
- `api_launcher/crawlers/ncei.py`：放 NOAA/NCEI Search query URL builder、payload parser、source-level fetch/parse flow 與 NCEI pagination flow，保留 result/file id、format、observation type、keyword、link 與 temporal coverage metadata。
- `api_launcher/crawlers/stac.py`：放 STAC collection payload parser、source-level fetch/parse flow 與 STAC `next` link pagination flow。
- `api_launcher/crawlers/ckan.py`：放 CKAN `package_search` query URL builder、payload parser、source-level fetch/parse flow、resource 摘要 helper 與 CKAN pagination flow。
- `api_launcher/crawlers/erddap.py`：放 ERDDAP `allDatasets` source-level fetch/parse flow，保留 griddap/tabledap/wms protocol metadata 給後續 bounded adapter resolver 使用。
- `api_launcher/crawlers/cmr.py`：放 NASA CMR collection query URL builder、payload parser、source-level fetch/parse flow、CMR link/platform helper 與 CMR pagination flow。
- `api_launcher/crawlers/gbif.py`：放 GBIF dataset search query URL builder、payload parser、source-level fetch/parse flow 與 GBIF pagination flow，保留 GBIF key、record count 與 organization metadata。
- `api_launcher/crawlers/dataverse.py`：放 Dataverse search query URL builder、payload parser、source-level fetch/parse flow 與 Dataverse pagination flow，保留 global id、版本、dataverse alias 與 file count metadata。
- `api_launcher/crawlers/zenodo.py`：放 Zenodo records query URL builder、payload parser、source-level fetch/parse flow、Zenodo pagination flow、檔案摘要 helper 與簡單 markup 清理 helper。
- `api_launcher/crawlers/datacite.py`：放 DataCite `/dois` query URL builder、payload parser、source-level fetch/parse flow 與 DataCite pagination flow；保留 DOI、publisher、client id、subjects、formats、rights、usage count 與 `contentUrl` resource metadata。
- `api_launcher/crawlers/ogc_records.py`：放 OGC API Records query URL builder、FeatureCollection payload parser、source-level fetch/parse flow 與 `next` link pagination flow；保留 record id、keywords/themes、formats、geometry type、links 與 temporal coverage metadata。primary `api_url` 只會選 HTTP(S) data/download/items/self links；非 HTTP broker links 只留 metadata，等待未來 WIS2/stream adapter。
- `api_launcher/crawlers/socrata.py`：放 Socrata catalog query URL builder、payload parser、source-level fetch/parse flow 與 offset pagination flow；保留 Socrata domain、resource id、`api/views` metadata URL、bounded resolver 可用的 `/resource/{id}.json`、欄位摘要與 attribution/license metadata。
- `api_launcher/crawlers/openalex.py`：放 OpenAlex Works search URL builder、payload parser、source-level fetch/parse flow 與 cursor pagination flow；保留 OpenAlex work id、DOI、primary location、open access metadata、作者/機構/concepts/keywords。
- `api_launcher/crawlers/html_index.py`：放 HTML file index source-level fetch/parse flow，負責把簡單目錄頁裡符合 regex 的檔案連結整理成可審核版本 shards。
- `api_launcher/crawlers/orchestrator.py`：統一調度所有 dataset crawler，負責並行、去重、錯誤收斂與回傳統一結果。
- `api_launcher/crawlers/dataset_sources.py`：目前主要保留 source type dispatcher、limit/search_terms 正規化與舊匯入相容；各來源 API 參數組裝、一般抓取解析與 full-crawl 分頁都已優先放回 source module。dispatcher 已集中成 `SOURCE_CRAWLER_HANDLERS` mapping，並匯出 `SUPPORTED_DATASET_SOURCE_TYPES` 給 portal intake 使用。
- `api_launcher/dataset_discovery.py`：相容入口；新 crawler 程式碼應放在 `api_launcher/crawlers/`。

新增供應商時，原則是先看它能否使用既有 crawler type；若不能，新增一個小 crawler，再交給 orchestrator 調度。特殊網頁結構的硬規則可以存在，但要集中在該 crawler 裡，不要散到 UI、core 或下載器。

白話說，新增 crawler type 只應該有一份「正式支援清單」。目前這份清單在 `SOURCE_CRAWLER_HANDLERS`；`portal_intake.py` 會讀同一份清單，所以入口表格不需要另外手抄一份 crawler type。測試會檢查 catalog 內的 source type、dispatcher mapping、portal intake 支援清單三者一致。

Crawler 不能只用「沒報錯」當成功標準。現在 orchestrator 會對每個 source 做基礎審核：

- endpoint 回傳的資料結構若不像預期，例如 NCEI 沒有 `results`、STAC 沒有 `collections`、OGC API Records 沒有 `features`、Socrata 沒有 `results`、CKAN 沒有 `result.results`，解析器會直接報錯。
- source 成功跑完但回傳 0 筆，會標成 warning，因為這可能是搜尋詞、分頁、網頁結構或反爬規則失效。
- 每個 source 可設定 `min_expected_candidates`；若候選數低於最低預期，也會標成 warning。
- source 有回傳候選，但全部都是其他來源已經抓過的重複項，也會標成 warning，避免「看似有資料、其實沒有新增資訊」。
- 候選缺少 dataset id、title、source url、evidence 或 provider 對不上，也會標成 warning。

白話說，crawler 的審核要回答「我真的看到了資料嗎？」而不是只回答「我有沒有崩潰？」。CLI 可用 `--dataset-discovery-strict-audit` 把 warning/error 變成失敗，適合未來 CI 或定期健康檢查。
- `api_launcher/dataset_adapters.py`：集中註冊 provider-specific dataset adapter。
- `api_launcher/adapters/gebco.py`：把 GEBCO 對應成 GEBCO 2025 全球高程網格 dataset。
- `api_launcher/adapters/hyg.py`：第一個具體 adapter，會把 HYG Database 對應成 HYG v3.8 星表 dataset。
- `api_launcher/renderer_contracts.py`：保存渲染器共用 dataset ID，避免 launcher 與 `taichi_global_bathymetry.py` 各自硬編碼名稱。

Adapter 仍然重要，但它應該處理「crawler 找到候選後，如何產生安全的 bounded query、驗證、匯入、轉換」，不是拿來取代 catalog crawler。HYG/GEBCO adapter 測試指令：

目前 `api_launcher/adapter_plan_resolver.py` 已有幾條從候選 metadata 走向 MVP 閉環的安全橋：

- CKAN/Data.gov：只查單一 `package_show`，挑 100MB 以下、格式可辨識的 direct resource。
- Dataverse：用 persistent id 查單一 dataset 最新版本 metadata，只挑未受限、格式可支援、100MB 以下的檔案，轉成 `/api/access/datafile/{id}` plan entry。
- ERDDAP：讀 `info/{dataset}/index.json`，產生最多 25 列或最小維度切片的 CSV sample。
- STAC：把 collection 轉成 `items?limit=1` 的 GeoJSON metadata sample，不抓 raster asset。
- NASA CMR：把 collection concept id 轉成 `granules.json?page_size=1` 的 JSON metadata sample；若 plan 已經是單筆 granule metadata，才從 CMR `links` 裡挑明確 `data` / `download` / `enclosure` 檔案連結。
- Socrata/SODA：把 resource/API view 轉成 `$limit=25` 的 JSON/CSV/GeoJSON sample。
- NOAA/NCEI Search / Access Data：Search data query 若已有 dataset 加站點/空間條件，可先查 1 筆 metadata 並挑小於 100MB 的 `/data/...` direct file；Access Data 仍只在 query 已有 dataset、時間、空間邊界時產生小樣本；否則留在 adapter review。

這些 resolver 的共同原則是：先用小、可驗證、可匯入的樣本打通下載與 SQLite MVP，不假裝已經完成完整大量下載。

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

Dataset-version 下載計畫也是通用機制。`api_launcher/plans.py` 可把 adapter 發現的 `DatasetVersionOption` 或 crawler 審核後的候選資料集轉成 plan entry，包含 `dataset_version`、direct/review eligibility、staging 設定、保守的 `import_plan`，以及穩定的 `downloads/{provider}/{dataset}/{version}/...` 目標路徑。CLI 用法：

```bash
python3 APIkeys_collection.py --init-db --seed --provider hyg_database --export-dataset-plan state/hyg_dataset_plan.json
```

Crawler candidate 版本可用：

```bash
python3 APIkeys_collection.py --export-candidate-plan state/candidate_plan.json --candidate-plan-status approved
```

若版本 URL 看起來是入口頁、API endpoint 或下載 selector，而不是具體檔案，計畫會標記 `adapter_required`，並把網址放在 `adapter_review_url`；不要直接交給 HTTP downloader。

若候選來自 DataCite 或 OpenAlex，DOI/OpenAlex URL 也會先留在 adapter review。白話說：DOI 像資料的門牌或索引卡，OpenAlex work 像研究記錄，不是檔案本身。DataCite metadata 若明確提供 `contentUrl`，crawler 會把它整理進 `resources`，讓 generic resolver 只挑已支援、可界定的檔案連結。若 plan 只有 DataCite DOI metadata，或 OpenAlex work 只有 DOI，resolver 現在也可以只查一次 DataCite DOI API，再從 `contentUrl` 裡挑支援格式、未宣告超過 100MB 的 direct file；但 DOI landing page 或 repository HTML 頁仍然不能直接當成下載檔，也不會被背景爬取。

若 `adapter_required` 來自 CKAN/Data.gov 類平台，且 plan 只拿到 `package_show` URL，或只有 `package_search` URL 加 dataset id，`--resolve-adapter-plan` 現在可以只查一次單一 package metadata，再從 resources 裡挑安全的 direct file。這仍然是 bounded adapter：它不掃整個 CKAN catalog，也不下載 HTML 頁或大型未知資源。泛用 resource resolver 目前會辨識 `resources`、`distribution` / `distributions`、`dcat:distribution`、`links`、JSON-LD `@graph` 這些常見包裝，也會辨識 `download_url`、`downloadURL`、`contentUrl`、`fileUrl`、`url`、`href`、`dcat:downloadURL`、`schema:contentUrl` 這類明確下載欄位，欄位值可以是字串、list，或 `{"@id": "..."}` 這類 JSON-LD 物件；物件裡若只有 `label` 而沒有 URL，不會被當成下載連結。格式提示可用 `format`、`mediaType`、`contentType`、`encodingFormat`、`dct:format`、`dcat:mediaType` 等欄位；大小可讀 `byteSize` / `contentSize`、`dcat:byteSize` 與 `{"@value": "..."}` 等提示。白話說，資料目錄欄位名稱或寫法不同時，也能先找出「看起來真的像檔案」的小樣本；`accessURL` 這類可能只是入口頁的欄位仍然不會被泛用 resolver 自動當成檔案。

若候選來自 Socrata/SODA，`socrata_catalog_search` crawler 會刻意把候選的主要 API URL 設為 `/api/views/abcd-1234` 這種 metadata URL，而不是直接把 `/resource/abcd-1234.json` 交給下載器。resolver 目前只處理已能辨認的 v2-style resource 入口，例如 `/resource/abcd-1234.json`、`/resource/abcd-1234.csv`，或 metadata URL `/api/views/abcd-1234`。它會保留既有 `$select` 等查詢條件，再加上 `$limit=25`，產生一個小樣本 direct plan entry；泛用 direct-file resolver 會跳過這類 resource URL，避免把 `.json` API 當成完整檔案直接下載。SODA v3 token/query POST 形狀目前仍留在 adapter review，等 credential 與 query contract 明確後再做。

若候選來自 NOAA/NCEI Common Access Search，resolver 現在可以把 crawler 留下的 `/search/v1/datasets` 或 `/search/v1/data` URL 變成 `limit=25&offset=0` 的 JSON metadata sample。白話說，這是在下載「搜尋結果清單」的小樣本，不是在下載 NOAA 真正的資料檔；後者仍需要依 dataset、時間、空間、格式、授權與檔案大小再做下一層 adapter。若 plan 已經是 `/search/v1/data`，且 query 有 dataset 加站點/框選/位置條件，resolver 會先做一次 `limit=1&offset=0` metadata lookup；只有第一筆結果提供 `/data/...` direct file path、格式可辨識、且 `fileSize` 未超過 100MB 時，才會把那個 CSV/JSON 等檔案排進 direct download。沒有站點/空間條件，或檔案太大時，仍只保留 bounded JSON metadata sample。

若 plan 已經進到 NOAA/NCEI Access Data Service 的 `/access/services/data/v1`，resolver 現在只會在查詢同時具備 dataset、startDate、endDate、站點/框選/位置等空間條件，且日期跨度不超過 7 天時，才把它提升成 CSV/JSON 小樣本 direct entry。沒有時間或空間邊界的 Access Data 查詢會留在 adapter review，避免把看似 API URL 的大範圍資料誤當成安全下載。

若候選來自 NASA CMR collection search，`api_launcher/adapter_plan_resolver.py` 現在可以把 `cmr_concept_id` / `collection_concept_id` 轉成 `/search/granules.json?collection_concept_id=...&page_size=1` 的 JSON metadata sample。這只下載一筆 granule metadata，用來打通 `candidate -> plan -> resolver -> JSON manifest/import` 的 MVP 小閉環；它不直接下載整批 HDF/NetCDF/COG 等衛星科學資料資產。若 plan 已經是單筆 CMR granule metadata，resolver 也可以只查一次 CMR concept/granules JSON，從 `links` 裡挑明確 `data` / `download` / `enclosure` rel、格式可辨識、未宣告超過 100MB 的檔案連結。CMR 的 `granules.json` 雖然網址以 `.json` 結尾，也仍被視為 API endpoint，必須先經 bounded resolver，不可直接當成任意檔案下載。若 CMR granule metadata 裡有 `metadata`、`documentation`、`browse`、`service`、`opendap`、`self` 等 rel，resolver 會保守留在 adapter review。白話說，metadata 是「資料的說明書」，data link 才是「可能要下載的檔案」。JSON importer 也已能把 CMR 回應裡的 `feed.entry` 攤成 SQLite 資料列。

若候選來自 OGC API Records，例如 WMO WIS2 catalog，resolver 會保守處理 record links：`self`、`alternate`、`canonical`、`describedby`、`items`、`related` 等 rel 代表 metadata/navigation/broker 入口，不會因為 URL 或 media type 看起來像 GeoJSON 就被提升成 direct download；只有 `data` / `download` 這類明確資料連結才可進入 generic direct-resource resolver。

`import_plan` 不是自動匯入，而是下一步提示：CSV/CSV.GZ 與 JSON/JSONL/GeoJSON 可在下載驗證後進入現有 SQLite MVP importer；CSV.ZST、ZIP、TAR 等壓縮包可下載但需要解壓或 adapter；API/入口頁仍需 adapter review。

若計畫裡已有 direct entry，可用 CLI 執行：

```bash
python3 APIkeys_collection.py --init-db --seed --run-download-plan state/hyg_dataset_plan.json --verify-downloads --manifest-health
```

`--run-download-plan` 只會送出有直接 `download_url` 且未標記 `adapter_required` 的 entry。下載完成後會驗 sidecar manifest，並把健康 payload 登錄成 managed filesystem `file` asset。需要 smoke test 時可加 `--download-plan-limit N`。

若 plan entry 的 `import_plan.status` 是 `supported_after_download`，可讓 runner 在驗證後自動匯入支援的 CSV/JSON 類 payload：

```bash
python3 APIkeys_collection.py --run-download-plan state/candidate_plan.json --import-supported-plan-results --import-sqlite-db state/curated_imports.sqlite
```

這仍然是保守流程：下載失敗與匯入失敗分開回報，不支援的格式只會跳過，不會被硬轉成 SQL。

若下載結果是 CSV/CSV.GZ，且 sidecar manifest 健康，可進一步匯入 curated SQLite table：

```bash
python3 APIkeys_collection.py --init-db --seed --import-csv-manifest downloads/sample.csv.manifest.json --import-sqlite-db state/curated_imports.sqlite --import-table sample_curated
```

目前這是 MVP 級匯入：所有欄位先以 `TEXT` 存放，欄位名稱會轉成安全 SQL identifier，table 會帶 schema fingerprint 登錄回 install registry。重跑 plan 時若目標 table 已存在，預設會略過而不覆蓋；想保留舊表並匯入新表，可用 `--plan-import-existing-table-policy rename` 產生 `table_2` 這類安全新名稱。要覆蓋既有 table 時必須明確加 `--import-replace-table` 或 `--plan-import-existing-table-policy replace`。

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
