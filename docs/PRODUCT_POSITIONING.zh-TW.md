# 產品定位

最後更新：2026-05-23

## 一句話

目前對外產品名是 **RuRuKa Asset Launcher**，短稱 **RRKAL**；`APIkeys_collection` 保留為 repo、Python package、CLI 入口與歷史相容名稱。

`RRK` 可作為未來品牌字根，用於新的 UI 模組、功能別名、外部文件或視覺命名；既有程式 namespace、CLI 檔名與相容 wrapper 不應因為短稱好用而直接批量更名，除非另開一個具備遷移路徑與測試範圍的 rename checkpoint。

RuRuKa Asset Launcher 正在從 API key/source 管理器，演進成「資料工程版 Steam」：把原本需要到處找來源、查依賴、比版本、下載、匯入、驗證、修復與橋接的工作，集中成一個懶人化但可追蹤的平台。

## 新定位

它不是單純的 API key 收藏器，也不是單純的下載器。更準確的定位是：

> 一個類 Steam 的科學資料集與爬蟲資產 launcher，負責 discovery、下載、安裝、版本、更新、解除安裝、資料清洗、SQL/檔案/API 納管，並把資料轉接給 Taichi、Unreal 或未來 agent 使用。

Steam 最強的概念不是商店頁本身，而是把「找遊戲、裝依賴、更新 runtime、同步存檔、確認本機是否安裝、修復壞掉檔案」這些麻煩事平台化。RuRuKa Asset Launcher 面對的是資料工程：資料散在 NOAA、ERDDAP、STAC、CKAN、API、CSV、資料庫、物件儲存與研究站台之間；使用者不應每次都從搜尋引擎、文件、壓縮檔、SQL 匯入與路徑設定重新開始。

因此產品核心是：讓資料源與爬蟲能力像 Steam library 裡的遊戲一樣可搜尋、可收藏、可審核、可安裝、可驗證、可更新、可修復；同時把原始資料、本機安裝、個人工作區與渲染/分析橋接分清楚。

更長期的上位概念請見 `docs/DATA_ASSET_PLATFORM_CONCEPTS.zh-TW.md`。那份文件把本專案整理成 local-first 資料資產平台：不只管理資料庫，也管理 raw artifact、pandas/DataFrame 類暫態資料、Discovery Tool、爬蟲資產 / Crawler Asset、adapter/importer、storage backend、renderer backend、ML model、job、recipe 與 lineage。它是 roadmap 與概念總綱，不是目前 MVP 必須一次實作的清單。

## 成熟產品形態

若把 MVP hardening、後端微核心化、雙介面解耦與 Steam-like 複雜度封裝都完成，RRKAL 的成熟形態可定位為：

> 專為科研、地理空間與金融分析人員設計的科學大數據標準化採集與分發平台。

這個定位可以理解成 Scientific Data Gatekeeper：它把野生 API、官方資料入口、語言套件、下載檔、manifest、資料庫匯入、授權邊界與 renderer/分析工具之間的雜訊收斂成一套可審核、可重建、可修復的本機資料資產流程。

成熟架構應分成三層：

1. **Headless SDK Core**：只保留資料源 registry、下載/匯入/repair pipeline、manifest、install registry、adapter contract 與事件紀錄；不直接依賴 Tk/Qt，也不把特定資料源寫死在核心流程。
2. **CLI / automation layer**：用 `crawl`、`download`、`import`、`db check/repair`、`handoff` 這類命令支援伺服器、自動排程、heartbeat 與跨 Agent 接力。
3. **多端 View layer**：Tk Lite 維持零或低依賴的穩定控制面板；Qt Pro 或其他現代前端承接更完整的視覺化、下載佇列、資料商店、乾跑預覽與 renderer bridge。

使用者路徑應保持接近 Steam：先安全配置本機 `.env` 或 profile，再在資料商店瀏覽/收藏來源，將候選加入 Library，下載並驗證，匯入或啟動資料資產，最後用「Verify & Repair」做一鍵健康檢查與修復。底層可以有 SQL、checksum、resolver、adapter review 與 dry-run migration，但一般使用者不應先被迫理解這些內臟。

這一節描述的是中長期產品收斂方向，不代表 repo 已經完成 headless service、Qt Pro 或插件市場。當前開發仍以 `seed -> crawler -> candidate -> plan -> download -> import -> UI` 的 MVP/hardening 閉環為準；任何 rename、plugin、Qt migration、headless RPC 或商業化 installer 都應另開 OpenSpec proposal，保留相容層與回滾策略。

## 產品形態補充

「類 Steam」不只是指資料集清單長得像商店頁，也代表它應該逐步變成一個常駐的本機資料管理器。

中期目標是桌面常駐形態：在 Windows 上可以收進右下角系統匣，在 macOS 上可以收進功能列 / menu bar。主視窗只是控制面板；背景工作者才負責維持下載、匯入、更新提醒、修復提醒與日誌入口。這個方向會影響架構設計：未來不要把流程寫死成「打開視窗一次、跑完就結束」的腳本，而要讓 CLI、Tk UI、系統匣 / menu bar shell 共用同一套資料治理與 library action。

更長期可以包裝成移動端 companion app，但它的角色應該是「遙控器」而不是「資料搬運中心」。手機端可透過 QR/device pairing 連到常駐桌面端或受信任的本機服務，查看下載/匯入/修復狀態、接收通知、暫停或恢復任務、要求桌面端開啟資料庫或 renderer。原始資料、資料庫連線、API token、AI token 與重型運算仍留在桌面端/服務端，避免把敏感資料暴露到手機或公網。

另一個遠期形態是 P2P / BitTorrent-like 資料分發節點。這個方向已有前例，例如 Academic Torrents 類型的學術資料分發服務；本專案的差異在於它會先做資料治理：確認授權、版本、manifest、checksum 與來源，再決定是否允許下載後做種或從 peers 加速下載。這必須是使用者 opt-in，且只適用於授權清楚的 public dataset；需要個人 token、API 條款禁止轉載、私有資料或來源不明的資料，都不能被這個程式自動分享出去。

## 與一般競品的差異

| 類型 | 常見能力 | 本專案差異 |
| --- | --- | --- |
| API client / key manager | 管理 endpoint、token、請求範例 | 本專案不只管理 API，也管理資料集安裝狀態、版本、manifest、下載與清洗。 |
| Open data portal | 提供資料搜尋與下載連結 | 本專案是本機 launcher，可把多來源資料納管到同一 workflow。 |
| 爬蟲腳本集合 | 一堆可執行 scraper / crawler | 本專案會把爬蟲視為可治理資產：有版本、來源範圍、rate limit、credential 邊界、健康狀態、repair 任務與 lineage。 |
| ETL / data pipeline 工具 | 抽取、轉換、載入資料 | 本專案增加 Steam-like library、安裝/解除安裝、renderer bridge、前端消費契約。 |
| Hadoop / Spark / data lake | 大型儲存、批次運算、Hive/Metastore、partition | 本專案不取代 Hadoop，而是把 HDFS path、Spark job、輸出 manifest、批次狀態包成 launcher 可管理流程。 |
| GIS/visualization tool | 地圖或資料視覺化 | 本專案把視覺化視為前端消費者，資料主權保留在 launcher/registry。 |
| Unreal/Taichi renderer project | 專注畫面與互動 | 本專案負責渲染前的資料治理、tile manifest、版本與串流接口。 |

## 核心承諾

1. 資料主權在 launcher，不在 Unreal 或單一 renderer。
2. 資料集要有穩定 ID、版本、manifest、checksum、來源、授權與 install_id。
3. 下載器必須非阻塞、可續傳、可暫停、可恢復，並尊重來源站限制。
4. 前端可以是 Tk、Taichi、Unreal、agent 或其他工具，但都應讀同一套資料契約。
5. 爬蟲資產本身要可被版本化、審核、排程、監控與修復；它產出的 candidate、plan、manifest 與資料資產都要能追 lineage。
6. 任何再散布或 P2P 分享都必須先通過授權、來源、版本與 checksum 檢查。
7. 物理/渲染細節先以 contract 銜接，交給專門模組或 agent 深化。
8. Library / entitlement、local install、workspace/save 要分層；本機沒有資料不等於使用者沒有擁有或沒有個人工作成果。
9. Renderer bridge 本身也是可管理資產；tile/cache/mesh/chart index 應能被版本化、驗證、重建與清理。

## MVP 邊界

目前優先完成：

- Steam-like provider/dataset browser
- download plan/cart
- nonblocking downloader
- manifest/repair/install registry
- dataset version/update skeleton
- tile/cache manifest skeleton
- Taichi reference renderer bridge
- Unreal frontend bridge skeleton
- simulation bridge contract

暫不承諾：

- 完整全球物理模擬
- 高品質 Unreal shader/material system
- 全自動大規模資料清洗
- 所有 provider 的完整 adapter
- 商用等級權限/團隊協作

這些可以在骨架穩定後逐步擴充。
