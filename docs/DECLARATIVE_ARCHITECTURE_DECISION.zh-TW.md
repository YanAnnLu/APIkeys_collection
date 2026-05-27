# 宣告式架構分階段決策

最後更新：2026-05-27

本文件記錄 RRKAL / `APIkeys_collection` 對「宣告式架構」的階段性結論。這是一份架構決策，不是要求立刻全面重寫 crawler、importer 或 UI 的任務清單。

## 結論

我們採納宣告式架構作為中期收斂方向，但第一階段不做全面重構。

第一階段仍以 MVP 閉環為最高優先：

```text
seed -> crawler -> candidate -> plan -> download -> import -> UI
```

在這個階段，現有 Python adapter、service、registry 要先維持可測、可用、可交付。不要為了追求「一個萬能 YAML 引擎」而破壞已通過測試的 MVP pipeline。

## 第一階段原則

- 不把 13 個 crawler 一次重寫成 `universal_interpreter`。
- 不把複雜 API 例外全部塞進 YAML / JSON。
- 不為抽象而抽象；每個抽象都要服務可測的使用路徑。
- Python adapter 負責「這類來源介面怎麼抓」。
- profile / config 負責「這個來源是什麼」。
- UI 只呼叫 service、呈現後端 structured payload，不自行推理業務狀態。

## 第二階段收斂順序

1. UI 狀態 contract
   - `status` / `outcome_bucket` / `warning_code` -> `label` / `tone` / `next_action`
   - Tk、Web、未來 Qt 都讀同一份後端 display payload。
   - 前端不自行判斷業務狀態。

2. 動態界域表單 contract
   - `source_type` / asset capability -> form fields / presets / validation / defaults
   - 前端根據 form spec 產生表單。
   - 不在 Tk/Web 裡硬寫 STAC、CKAN、CMR 等表單邏輯。

3. Content parser / importer capability contract
   - CSV / JSON / GeoJSON 可 import。
   - ZIP / NetCDF / HDF / GeoTIFF / unknown 先進 manifest / adapter review。
   - importer 不到處分支判斷格式。

4. Adapter review / download plan contract
   - `blocked` / `review_required` / `ready_to_download` / `partial_review_required` 等 outcome 集中定義。
   - UI 只呈現後端給的 `next_action`，不自行猜。

5. Feature flags / developer-only surfaces
   - diagnostics、simulation、renderer、experimental bridge 用 feature profile 控制。
   - 未成熟功能不得混入一般使用者流程。

6. Source profile / crawler adapter metadata
   - endpoint、auth profile、query params、bounds facets、rate limit、expected content type 逐步從 Python 硬編碼移到 profile/config。
   - 但 crawler handler 不一次消滅。

## 數據驅動裝飾器爬蟲候選方向

使用者提出的「數據驅動裝飾器爬蟲架構」可視為第二階段 source profile 收斂的候選 PoC。其核心價值不是立即消滅現有 handler，而是把重複的橫切能力抽成可組裝 middleware：

- credential gating
- pagination driver
- timeout / retry / rate limit
- evidence URL / warning code / audit summary
- content detection handoff

落地時請採用「profile schema + middleware pipeline」心法，不要直接用脆弱的 raw list row 當正式 contract。建議用 dataclass / typed dict / JSON schema 描述 task profile，避免欄位順序錯誤造成難查 bug。

目前已落地的 source profile 欄位（timeout、max pages、page size、rate limit、credential mode、terms risk）可以視為這條路線的最小資料面。下一步不是把所有 crawler 改成一個裝飾器函數，而是把這些已穩定的 request/access policy 抽成明確 schema，並讓既有 adapter 逐步共用 middleware。`api_launcher.crawlers.request_policy.SourceRequestPolicy` 是這條路線的第一個 typed staging point。

## Matrix Cell -> Profile -> Gateway -> Pipeline

更精確的中期架構命名是：

```text
Matrix Cell -> Validated Profile -> Capability Gateway -> Middleware Pipeline
```

多維矩陣中的一個 cell 不應直接變成 raw list 或 magic tuple，而應先驗證成 typed profile。例如：

```text
來源範式 × 權限模式 × 分頁模式 × 內容格式 × 界域能力
= CrawlerCapabilityProfile
```

範例：

```text
Socrata × optional_api_key × offset_pagination × csv/json × time+bbox+limit
```

應落成：

```python
CrawlerCapabilityProfile(
    source_type="socrata",
    auth_mode="optional_api_key",
    pagination_mode="offset",
    content_formats=("csv", "json"),
    bound_facets=("time", "bbox", "limit"),
    middleware=(
        "credential_guard",
        "offset_pagination",
        "bounded_fetch",
        "audit_warning",
    ),
    failure_policy={
        "zero_candidates": "review_query_or_bounds",
        "missing_credentials": "open_credential_editor",
        "unsupported_content": "adapter_review",
        "pagination_limit_reached": "show_has_more",
    },
)
```

整體資料流：

```text
Source / URL / Seed
    -> Detector / SourceProfile
    -> Crawler Capability Gateway
    -> Middleware Pipeline
    -> Crawler Adapter
    -> DatasetCandidate[] + warnings + next_action
    -> Plan / Download / Import / UI
```

這個 gateway 的責任是集中分流，不是藏起所有判斷。UI、downloader、importer、resolver 不應散落 `if source_type == "socrata"` 或 `if provider == "NASA"`；它們應消費後端輸出的 capability、status、warning code 與 next action。

## Profile 家族

這個抽象不只適用 crawler。可以逐步整理成以下 profile 家族：

- `CrawlerCapabilityProfile`：source type、auth、pagination、bounds、content hint。
- `BoundsFormProfile`：source type、supported facets、preset、validation、defaults。
- `ContentImportProfile`：format、compression、tabular/grid/raster、importability。
- `DisplayProfile`：status、severity、user role、next action。
- `CredentialProfile`：provider、auth mode、fields、storage policy。
- `StorageProfile`：data size、update frequency、query pattern、format。
- `RecoveryProfile`：error type、stage、recoverability、user action。
- `TestCaseProfile`：source type、auth state、network state、payload shape。

這些 profile 的共同規則：

- 使用 dataclass / TypedDict / JSON schema，不使用 raw matrix row。
- profile 只描述能力與政策；實際 I/O 仍由 adapter / service 執行。
- profile output 必須可測、可序列化、可給 Tk/Web/Qt 共用。
- 不把 provider 名稱當成架構分支；NASA、NOAA、FRED 是 source profile 差異，不是到處散落的 special case。

## 優先落地順序

1. UI display profile
   - 讓 Tk / Web / 未來 Qt 都讀同一份 label / tone / next_action。

2. Bounds form profile
   - 解決使用者盲填欄位問題，讓界域表單由 profile 動態生成。

3. Content parser / import profile
   - 集中 CSV / JSON / GeoJSON 可匯入，ZIP / NetCDF / GeoTIFF 需 review 這類判斷。

4. Crawler capability profile PoC
   - 先選 Socrata 或 HTML file index，不一次接所有 source。
   - 輸出仍是既有 `DatasetCandidate`，不發明新主資料結構。

PoC 成功標準：

- profile 能描述 endpoint、auth、pagination、timeout、rate limit、content hint。
- gateway 能根據 profile 組裝 bounded fetch、credential guard、pagination、audit warning。
- 測試覆蓋 zero candidates、missing credentials、pagination has_more、large payload blocked、unsupported content format、warning code / next action。

這是一種架構維護性優化，不是 CPU 效能優化。它主要改善分流集中度、UI 防呆、測試矩陣、新來源擴充速度與長期代碼體積；HTTP 速度、SQLite 寫入速度與 CPU 運算速度仍需由 downloader / importer / storage 層另行處理。

### 裝飾器順序注意

Python 裝飾器的套用順序與呼叫順序容易誤解。若寫成：

```python
@with_oauth_gating
@with_pagination_driver
def crawl(...):
    ...
```

實際呼叫時通常是外層 oauth wrapper 先執行一次，再進入 pagination wrapper。若需求是「每一頁請求都要重新注入最新 credential / header」，pagination wrapper 應該呼叫 credential wrapper，或直接用明確的 middleware pipeline 控制順序。不要把這個細節藏在看似優雅的 `@decorator` 疊法裡。

### 第一個 PoC 建議

可以從 Socrata 或 HTML file index 開始，原因是它們已有比較穩的 source pattern、seed enumeration 與測試路徑。PoC 成功條件：

- profile 驅動 endpoint / pagination / timeout / max_pages。
- adapter 仍輸出 `DatasetCandidate` 與既有 audit summary。
- zero candidates、blocked credentials、unknown content format 都有 structured warning / next_action。
- 不破壞現有 Python handler；先並行驗證，再逐步收斂。

## 可接受 PoC

第一個宣告式 PoC 可選 Socrata 或 HTML file index。

目標不是取代全部 crawler，而是證明下列路徑能跑通：

```text
profile -> adapter -> candidates -> plan -> download/import
```

PoC 必須有：

- fixture tests
- blocked / unknown tests
- zero candidates tests
- 明確的 fallback / review payload
- 不依賴 live network 的 CI 路徑

## 不採用的做法

- 不在第一階段建立自製大型 DSL。
- 不讓宣告式設定變成另一種難 debug 的自製語言。
- 不用 YAML 隱藏複雜例外，讓錯誤變得比 Python 更難追。
- 不讓 roadmap 抽象干擾目前 crawler seed 枚舉、下載計畫、匯入與 UI 閉環。

一句話：宣告式架構是第二階段的收斂方向，不是第一階段的重寫理由。
