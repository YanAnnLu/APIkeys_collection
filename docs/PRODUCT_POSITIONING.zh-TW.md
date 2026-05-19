# 產品定位

最後更新：2026-05-18

## 一句話

APIkeys Collection 正在從 API key/source 管理器，演進成「資料工程版 Steam」：把原本需要到處找來源、查依賴、比版本、下載、匯入、驗證、修復與橋接的工作，集中成一個懶人化但可追蹤的平台。

## 新定位

它不是單純的 API key 收藏器，也不是單純的下載器。更準確的定位是：

> 一個類 Steam 的科學資料集 launcher，負責 discovery、下載、安裝、版本、更新、解除安裝、資料清洗、SQL/檔案/API 納管，並把資料轉接給 Taichi、Unreal 或未來 agent 使用。

Steam 最強的概念不是商店頁本身，而是把「找遊戲、裝依賴、更新 runtime、同步存檔、確認本機是否安裝、修復壞掉檔案」這些麻煩事平台化。APIkeys Collection 面對的是資料工程：資料散在 NOAA、ERDDAP、STAC、CKAN、API、CSV、資料庫、物件儲存與研究站台之間；使用者不應每次都從搜尋引擎、文件、壓縮檔、SQL 匯入與路徑設定重新開始。

因此產品核心是：讓資料源像 Steam library 裡的遊戲一樣可搜尋、可收藏、可審核、可安裝、可驗證、可更新、可修復；同時把原始資料、本機安裝、個人工作區與渲染/分析橋接分清楚。

更長期的上位概念請見 `docs/DATA_ASSET_PLATFORM_CONCEPTS.zh-TW.md`。那份文件把本專案整理成 local-first 資料資產平台：不只管理資料庫，也管理 raw artifact、pandas/DataFrame 類暫態資料、Discovery Tool、adapter/importer、storage backend、renderer backend、ML model、job、recipe 與 lineage。它是 roadmap 與概念總綱，不是目前 MVP 必須一次實作的清單。

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
| ETL / data pipeline 工具 | 抽取、轉換、載入資料 | 本專案增加 Steam-like library、安裝/解除安裝、renderer bridge、前端消費契約。 |
| Hadoop / Spark / data lake | 大型儲存、批次運算、Hive/Metastore、partition | 本專案不取代 Hadoop，而是把 HDFS path、Spark job、輸出 manifest、批次狀態包成 launcher 可管理流程。 |
| GIS/visualization tool | 地圖或資料視覺化 | 本專案把視覺化視為前端消費者，資料主權保留在 launcher/registry。 |
| Unreal/Taichi renderer project | 專注畫面與互動 | 本專案負責渲染前的資料治理、tile manifest、版本與串流接口。 |

## 核心承諾

1. 資料主權在 launcher，不在 Unreal 或單一 renderer。
2. 資料集要有穩定 ID、版本、manifest、checksum、來源、授權與 install_id。
3. 下載器必須非阻塞、可續傳、可暫停、可恢復，並尊重來源站限制。
4. 前端可以是 Tk、Taichi、Unreal、agent 或其他工具，但都應讀同一套資料契約。
5. 任何再散布或 P2P 分享都必須先通過授權、來源、版本與 checksum 檢查。
6. 物理/渲染細節先以 contract 銜接，交給專門模組或 agent 深化。
7. Library / entitlement、local install、workspace/save 要分層；本機沒有資料不等於使用者沒有擁有或沒有個人工作成果。
8. Renderer bridge 本身也是可管理資產；tile/cache/mesh/chart index 應能被版本化、驗證、重建與清理。

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
