# 資料類型地圖

最後更新：2026-05-18

這份文件用來補足專案的概念層：資料集不只是「一堆數字」或「一段文字」。同一個 launcher 未來會碰到表格、地圖、時間序列、科學陣列、粒子事件、圖片、影片、3D 模型、文件、圖網路與即時串流。不同資料類型需要不同儲存、分析與渲染目標。

核心原則：SQL 是很好的目錄與治理中心，但不一定是 raw data 的家。它適合保存 metadata、檔案索引、版本、checksum、授權、安裝狀態、provenance 與查詢入口。大型 raw payload 應優先保留在合適的原始格式、檔案系統或物件儲存中，再用 manifest 把它們和 install registry 綁起來。

## 快速判斷表

| 資料類型 | 常見例子 | Raw data 適合放哪裡 | SQL 適合管什麼 | 分析/渲染對標 |
| --- | --- | --- | --- | --- |
| 關聯式/表格資料 | 統計表、清單、行政資料、整理後的 CSV | SQLite/MySQL/PostgreSQL、CSV/Parquet | 表格 schema、索引、來源、版本、品質旗標 | SQL client、BI、Pandas、DuckDB |
| 半結構化文件/API | JSON API、metadata records、巢狀文件 | JSONL、document DB、物件儲存 | provider、endpoint、schema fingerprint、更新批次 | API adapter、document query |
| 時間序列/金融資料 | K 線、tick、IoT、氣象站、成交量 | TimescaleDB、ClickHouse、Parquet/DuckDB、object storage | symbol、時間窗、ingest run、revision、retention | TradingView-like chart、回測、指標計算 |
| GIS/空間資料 | 領海、EEZ、公海、行政邊界、道路 | GeoPackage、Shapefile、GeoJSON、PostGIS | 圖層 catalog、版本、來源、授權、空間索引 metadata | PostGIS、QGIS、Cesium、Unreal globe layer |
| AIS/軌跡資料 | 船舶 AIS、飛航 ADS-B、移動裝置軌跡 | CSV/Parquet、object storage、PostGIS/TimescaleDB/ClickHouse | vessel/entity ID、event time、軌跡 shard、空間索引、清洗規則 | 地圖軌跡、熱區、時間軸、航線分析 |
| 網格/陣列/遙測資料 | NetCDF 氣候格點、海溫、衛星 raster、衛星雲圖 | NetCDF、Zarr、HDF5、COG、object storage | dataset ID、維度、時間範圍、tile/index manifest | xarray、Dask、Taichi/Unreal tile renderer、地球雲層動畫 |
| 大型科學事件資料 | 粒子對撞機 event、探測器讀數、天文巡天 | ROOT、HDF5、Parquet、FITS、object storage | run ID、檔案索引、校準版本、provenance | ROOT/uproot、Spark/Dask、ClickHouse |
| 文化資產/多媒體/3D | 歷史建築、文物照片、影片、3D 掃描 | 圖片/影片檔、GLTF/GLB、OBJ、USD、IFC、LAS/LAZ | 資產目錄、地點、年代、授權、LOD、依賴檔 | Three.js、Cesium、Unreal、Blender |
| 文字/文件/RAG | 論文、法規、報告、網頁、OCR | PDF/HTML/TXT/Markdown、object storage | 文件 metadata、授權、切片索引、來源鏈 | 全文搜尋、向量 DB、RAG |
| 圖網路/關係圖 | 供應鏈、知識圖譜、引用網路、社群網 | graph DB、edge list、Parquet | 節點/邊版本、來源、權重、命名空間 | Neo4j、network analysis、graph visualization |
| 即時串流/log | market feed、感測器 stream、系統 log | Kafka/Redpanda、Redis stream、append-only files | topic、offset、checkpoint、retention、consumer state | stream processor、live dashboard |
| 分散式資料湖/批次運算 | 大量 raw files、跨資料集 join、長時間 ETL、特徵工程 | HDFS、Hive table、Parquet/ORC、object storage | dataset ID、manifest、partition、job run、lineage、權限 | Hadoop、Hive、Spark、MapReduce |
| ML artifact/embedding | 模型權重、特徵、向量索引 | model registry、object storage、vector DB | 模型版本、訓練資料來源、評估結果、license | vector search、模型 serving、agent tools |

## MVP 怎麼落地

目前專案先專注在 MVP 閉環，不要一次把所有資料庫都做完。實作順序應該是：

1. 用 SQLite/MySQL 做 catalog、install registry、manifest、下載健康狀態與基本 metadata。
2. Raw file 保留原格式，用 sidecar manifest 記 `source_url`、`version`、`sha256`、`size_bytes`、`schema_fingerprint`。
3. Adapter 只要先能描述資料類型、版本、下載方式、原始格式、預期儲存位置與後續工具提示。
4. 等資料真的被下載並驗證後，再決定是否產出 curated table、tile manifest、chart query window、renderer asset 或 RAG index。

白話說：先把「這是什麼資料、來自哪裡、下載了沒有、能不能驗證、該用什麼工具看」管理好，再談大型資料庫與高級渲染。

## 代表挑戰資料

- AIS 船舶資料：它看起來是 CSV 表格，但本質上是「時間 + 空間 + 船舶 ID」的軌跡資料。SQL 可以先管 metadata 與小樣本；大量資料應考慮日期 partition、PostGIS、TimescaleDB、ClickHouse、Parquet/DuckDB 或 Hadoop/Spark。
- 衛星雲圖：它不是文字或一般表格，而是 raster/grid/time animation。MVP 先記錄來源、時間、波段、projection、檔案 shard 與 manifest；渲染目標可以是地球貼圖、雲層透明疊加、時間滑桿動畫，後續才接 Taichi/Unreal/Cesium。

## 給未來 adapter 的欄位建議

Adapter metadata 可以逐步補這些欄位，不需要一次全部完成：

| 欄位 | 目的 |
| --- | --- |
| `data_family` | 例如 `table`、`timeseries`、`gis`、`array_grid`、`event_data`、`media_3d`、`document`、`graph`、`stream`。 |
| `native_format` | 原始格式，例如 `csv`、`netcdf`、`zarr`、`root`、`gltf`、`geojson`、`parquet`。 |
| `storage_hint` | 建議 raw data 放哪裡，例如 `filesystem`、`object_storage`、`postgis`、`timescaledb`。 |
| `sql_role` | SQL 在這類資料中的角色，例如 `primary_table`、`metadata_index`、`manifest_only`。 |
| `analysis_hint` | 建議分析工具，例如 `duckdb`、`xarray`、`uproot`、`qgis`、`dask`。 |
| `viewer_hint` | 建議前端或 renderer，例如 `tradingview_like_chart`、`cesium`、`unreal`、`threejs`、`rag_search`。 |
| `chunking_hint` | 大資料如何切分，例如 time window、tile、LOD、run ID、file shard。 |
| `license_scope` | 下載、再散佈、AI 訓練、商用或展示限制。 |
| `distributed_backend_hint` | 是否適合交給 Hadoop/HDFS/Hive/Spark，例如大量檔案、Parquet partition、批次 ETL 或跨資料集 join。 |
| `orchestration_hint` | 是否適合交給 K8S worker/job，例如定期同步、長時間 importer、repair scanner 或 ETL job。 |

## 不要硬塞進 SQL 的訊號

看到下列特徵時，SQL 多半應該退到 metadata/index 角色：

- 單一檔案很大，或一個 dataset 由大量 shard/tile/file 組成。
- 資料本身是影像、影片、音訊、mesh、點雲、模型權重、壓縮陣列或二進位事件。
- 查詢方式主要是時間窗、空間 tile、LOD、向量相似度、串流 offset 或專門科學格式。
- 需要保留原始格式才能被領域工具讀取，例如 ROOT、FITS、NetCDF、Zarr、GLTF、IFC。
- 版本、校準、回補、修正與 provenance 比單表覆蓋更新更重要。

## 專案目前的取捨

短期內，SQL 仍是 MVP 的主軸，因為它最容易支撐 catalog、manifest、registry、repair 與 UI。中長期則要讓每個 adapter 清楚宣告自己的 data family，然後把 raw data 交給適合的儲存與渲染/分析工具。這樣專案可以先跑通閉環，又不會把未來的大型資料類型鎖死在錯誤的資料庫選擇裡。
