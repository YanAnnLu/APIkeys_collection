# 資料庫入口網站收集表

最後更新：2026-05-18

這份文件給團隊成員收集「資料庫 / 資料商 / 資料目錄入口網站」。它的用途不是立刻下載資料，而是把入口整理成可審核、可轉成 crawler 設定的清單。

白話說：組員找到一個可能有資料的網站時，先填這裡。開發端再判斷它應該進 `catalog/APIkeys_collection_catalog.json`、`catalog/dataset_discovery_sources.json`，還是需要新的 adapter。

## 收集原則

- 只收集公開 metadata：網站名稱、網址、API 文件、資料類型、授權、是否需要帳號。
- 不要貼 API key、token、帳號密碼、cookie、私有下載連結或付費授權內容。
- 先分清楚入口類型：資料商首頁、可搜尋資料目錄、單一資料集頁、直接檔案下載、登入後平台。
- 若不確定，就填「待判斷」。不要因為不確定而不記錄。
- 優先找官方入口，不優先找二手整理文章。
- 對大型資料庫，只記資料目錄與 sample，不要要求程式直接全量下載。

## 入口類型

| 類型 | 怎麼辨認 | 進專案後通常變成 |
| --- | --- | --- |
| 資料商 / 機構首頁 | 例如 NOAA、NASA、World Bank 的資料入口首頁 | provider seed |
| 資料目錄 API | 可以搜尋很多 dataset，例如 CKAN、STAC、ERDDAP、Dataverse、Zenodo | dataset discovery source |
| 單一資料集頁 | 只描述某一個資料集，有版本或檔案清單 | dataset candidate 或 adapter review |
| 直接檔案 | URL 看起來是 `.csv`、`.json`、`.zip`、`.nc`、`.parquet` 等 | direct download plan，仍需檢查大小/授權 |
| 登入後平台 | 需要帳號、OAuth、API key 或專案註冊 | integration / auth / adapter，中期處理 |

## 填寫狀態

| 狀態 | 意思 |
| --- | --- |
| `new` | 組員剛新增，還沒檢查。 |
| `triaged` | 已初步分類入口類型與資料方向。 |
| `seeded` | 已加入 provider seed 或 dataset discovery source。 |
| `crawler_supported` | 已有 crawler 可以抓 metadata。 |
| `adapter_needed` | 找得到 metadata，但要 bounded query / auth / transform。 |
| `blocked` | 授權、登入、反爬、付費或不明風險暫停。 |
| `rejected` | 不適合本專案或來源不可靠。 |

## 組員快填模板

複製以下區塊，貼到「待整理入口」表格下方或 issue / chat 裡。

```text
網站名稱：
入口網址：
官方機構 / 擁有者：
入口類型：資料商首頁 / 資料目錄 API / 單一資料集頁 / 直接檔案 / 登入後平台 / 待判斷
資料主題：例如 氣象、海洋、金融、GIS、文化資產、衛星影像、時間序列
地理範圍：全球 / 美國 / 台灣 / 歐洲 / 海洋 / 其他
是否需要登入或 API key：
是否有 API 文件：
授權 / 使用條款網址：
你覺得值得收的原因：
備註：
填寫人：
日期：
```

## 待整理入口

| 狀態 | 優先 | 網站 / 入口 | URL | 擁有者 | 入口類型 | 主題 / 資料類型 | 地理範圍 | 授權 / 登入 | 建議 crawler 類型 | 填寫人 | 備註 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| new | P2 | 範例：某國開放資料 CKAN | `https://example.gov/api/3/action/package_search` | 某國政府 | 資料目錄 API | open data, government, CKAN | national | public metadata | `ckan_package_search` | name | 範例列，正式使用時可刪。 |
| new | P2 |  |  |  | 待判斷 |  |  |  |  |  |  |
| new | P2 |  |  |  | 待判斷 |  |  |  |  |  |  |
| new | P2 |  |  |  | 待判斷 |  |  |  |  |  |  |

## 已納入專案的代表入口

這些已經進入目前專案設定，可作為組員填寫時的參考。

| 狀態 | 入口 | 類型 | 對應設定 |
| --- | --- | --- | --- |
| crawler_supported | NOAA / NCEI Search | NOAA 資料搜尋 API | `noaa_ncei_dataset_search` |
| crawler_supported | ERDDAP allDatasets | ERDDAP 資料目錄 | `*_erddap_all_datasets` |
| crawler_supported | NASA CMR | NASA collection catalog | `nasa_earthdata_cmr_collections` |
| crawler_supported | STAC collections | 衛星 / 地球觀測 catalog | `*_stac_collections` |
| crawler_supported | GBIF dataset search | 生物多樣性資料目錄 | `gbif_dataset_search` |
| crawler_supported | Dataverse search | 研究資料倉儲 | `harvard_dataverse_search` |
| crawler_supported | Zenodo records | 研究資料倉儲 | `zenodo_records_search` |
| crawler_supported | CKAN package_search | 政府 / 開放資料目錄 | `*_package_search` |

## 轉入工程設定的判斷

看到新入口後，先用這個順序判斷：

1. 如果它是機構首頁，先加入 provider seed。
2. 如果它有可搜尋資料目錄 API，加入 dataset discovery source。
3. 如果它只是一個單一資料集頁，先記成候選，不要硬寫 adapter。
4. 如果它提供直接檔案 URL，仍要檢查檔案大小、授權、格式與更新策略。
5. 如果它需要登入、OAuth、API key、選參數、切 bbox / time range，標成 `adapter_needed`。

## 給組員的簡短說明

我們現在做的是「資料工程版 Steam」。Steam 不會讓使用者到處找遊戲本體、存檔、更新器和依賴；我們也希望讓使用者不用到處找資料庫入口、下載方式、版本、授權與匯入工具。

所以你找到的每個入口都很有價值，但請先記錄入口與 metadata，不要急著下載資料。程式會慢慢把這些入口轉成可審核、可下載、可匯入、可修復的流程。
