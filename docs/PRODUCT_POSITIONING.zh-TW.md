# 產品定位

最後更新：2026-05-17

## 一句話

APIkeys Collection 正在從 API key/source 管理器，演進成「科學資料集安裝器 + 虛擬孿生資料管線」。

## 新定位

它不是單純的 API key 收藏器，也不是單純的下載器。更準確的定位是：

> 一個類 Steam 的科學資料集 launcher，負責 discovery、下載、安裝、版本、更新、解除安裝、資料清洗、SQL/檔案/API 納管，並把資料轉接給 Taichi、Unreal 或未來 agent 使用。

## 與一般競品的差異

| 類型 | 常見能力 | 本專案差異 |
| --- | --- | --- |
| API client / key manager | 管理 endpoint、token、請求範例 | 本專案不只管理 API，也管理資料集安裝狀態、版本、manifest、下載與清洗。 |
| Open data portal | 提供資料搜尋與下載連結 | 本專案是本機 launcher，可把多來源資料納管到同一 workflow。 |
| ETL / data pipeline 工具 | 抽取、轉換、載入資料 | 本專案增加 Steam-like library、安裝/解除安裝、renderer bridge、前端消費契約。 |
| GIS/visualization tool | 地圖或資料視覺化 | 本專案把視覺化視為前端消費者，資料主權保留在 launcher/registry。 |
| Unreal/Taichi renderer project | 專注畫面與互動 | 本專案負責渲染前的資料治理、tile manifest、版本與串流接口。 |

## 核心承諾

1. 資料主權在 launcher，不在 Unreal 或單一 renderer。
2. 資料集要有穩定 ID、版本、manifest、checksum、來源、授權與 install_id。
3. 下載器必須非阻塞、可續傳、可暫停、可恢復，並尊重來源站限制。
4. 前端可以是 Tk、Taichi、Unreal、agent 或其他工具，但都應讀同一套資料契約。
5. 物理/渲染細節先以 contract 銜接，交給專門模組或 agent 深化。

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
