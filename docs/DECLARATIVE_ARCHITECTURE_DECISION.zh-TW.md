# 宣告式架構分階段決策

最後更新：2026-05-28

本文件記錄 RRKAL / `APIkeys_collection` 對「宣告式架構」的階段性結論。這是一份架構決策，不是要求立刻全面重寫 crawler、importer 或 UI 的任務清單。

## 結論

我們採納宣告式架構作為中期收斂方向，但第一階段不做全面重構。

宣告式與管道式不是互斥架構。RRKAL 的方向應是：

```text
Declarative profile says what is allowed / requested.
Middleware pipeline controls how it runs safely.
```

也就是 profile 描述 source type、credential、pagination、bounds、content hint、recursion / traversal budget、failure policy；pipeline 負責依序套用 credential guard、bounded fetch、pagination、rate limit、dedupe、audit warning、content detection 與 import handoff。不要偏向「全 YAML」或「全手寫流程」任何一端；可維護、可測、可給 UI/agent 讀懂才是標準。

第一階段仍以 MVP 閉環為最高優先：

```text
seed -> crawler -> candidate -> plan -> download -> import -> UI
```

在這個階段，現有 Python adapter、service、registry 要先維持可測、可用、可交付。不要為了追求「一個萬能 YAML 引擎」而破壞已通過測試的 MVP pipeline。

本專案採用的是混合式「準宣告式」寫法，不是上帝 YAML，也不是純命令式巨石。合理組合如下：

- 用 registry / profile / matrix / array 描述來源能力、分頁、權限、內容格式與 UI 顯示契約。
- 用 pipeline 表達執行順序，例如 credential guard -> bounded fetch -> pagination -> dedupe -> audit warning -> content detection -> import handoff。
- 用 decorator 做輕量註冊與 metadata 標註，並保留 handler 原本的回傳值。
- 保留少量清楚的 `if` / `match` / dispatch branch，集中在 gateway、policy、registry 或 adapter 邊界，不散落到 UI 與 importer。
- 保留必要迴圈、range、slice、`islice()` 與 bounded queue traversal，用來處理分頁、可見窗口、批次與資料流。
- 遞迴只作淺層、可證明有 budget 的樹狀 metadata helper；crawler / download / import 主路徑不用深遞迴。

可實作成「主管道 + 分流膠囊」：

```text
main pipeline
  -> normalized input
  -> branch capsule: registry array + decorator metadata + small policy branch
  -> handler returns DatasetCandidate[] / DatasetCrawlerOutput
  -> normalize back to main pipeline contract
  -> plan / download / import / UI
```

分流膠囊內可以有陣列、裝飾器、少量條件分支、迴圈或受控淺遞迴；膠囊外只看標準回傳 contract。這能把 `source_type` 分支收束在 gateway/adapter 邊界，避免 UI、downloader、importer 到處判斷同一件事。

條件分支本身只負責選路，例如選 adapter、policy、middleware 或 fallback。不要讓分支同時做 in-box-return、payload 包裝、UI 文案、錯誤正規化或狀態回填；這些收斂動作應由膠囊出口 / gateway / normalizer 統一處理。否則分支雖然被搬進膠囊，仍會變成新的雜物箱。

## 第一階段原則

- 不把 13 個 crawler 一次重寫成 `universal_interpreter`。
- 不把複雜 API 例外全部塞進 YAML / JSON。
- 不為抽象而抽象；每個抽象都要服務可測的使用路徑。
- Python adapter 負責「這類來源介面怎麼抓」。
- profile / config 負責「這個來源是什麼」。
- UI 只呼叫 service、呈現後端 structured payload，不自行推理業務狀態。

## 遞迴與低算力裝置基準

RRKAL 的產品原則包含全平台與低成本設備可運行。不能假設使用者一定在高階桌機上跑完整 crawler。遞迴不是禁用，但必須受明確 budget 約束，並以 Raspberry Pi-class 裝置可承受的互動體驗作為預設基準。

守則：

- Crawler、網站探索、HTML index traversal、遠端目錄掃描、pagination、下載/匯入主路徑，預設不要用 Python recursive call stack。用 queue / stack / `collections.deque`、`seen` set、`max_depth`、`max_pages`、`max_nodes`、timeout、rate limit 控制。
- 遠端互動探索預設 `max_depth=2`。若來源 profile 需要更深，必須明確宣告，且沒有 OpenSpec / 測試 / 使用者確認時不得超過 `max_depth=4`。
- Local filesystem 或本機 artifact 掃描可以用較高 budget，但仍要用 iterative traversal；互動 UI preview 預設應限制 `max_depth<=6`、`max_nodes<=1000`，背景 job 才能在有進度、取消與 memory guard 時放寬。
- JSON / XML / schema / tree-like metadata parser 若使用遞迴 helper，必須傳入 `depth` / `max_depth` / `node_count` guard；預設 `max_depth<=20`，且不得在遞迴內做網路請求、資料庫寫入或 UI 更新。
- 若碰到 budget，回傳 structured warning，例如 `traversal_limit_reached`、`recursion_depth_limited`、`pagination_limit_reached`，並讓 UI 顯示「可展開更多」或「需要更窄界域」，不要假裝已列完整個來源。

這些數字是安全預設，不是永久上限。若未來有實測證據、來源 profile、CI fixture 與 UI 防呆，可針對特定來源調整；但調整必須留在 profile / policy，不要散落在 crawler 或 UI 裡。

## Loop Sentinel / Range / Slice 規則

迴圈一定要有停止條件，但停止條件不應優先靠寫死的魔法哨兵值。RRKAL 應優先用資料結構、range、slice 與 profile budget 表達可見清單、批次枚舉、分頁與 sample 邊界。

守則：

- 停止條件優先來自 protocol response、source profile、使用者 bounds、job budget、schema size、content length、remote pagination metadata 或 runtime policy。
- 硬寫 sentinel value 只能作為最後安全網；若必須使用，必須是具名常數或 profile 欄位，可覆寫、可測、會回報 `limit_reached` / `sentinel_stop` 類 structured warning。
- 建有序表、seed page、download queue、candidate preview、schema preview 時，優先用 `range(start, stop, step)` 或明確 page window 描述順序；不要把 `0..49`、`50`、`100` 這類值散落在 UI 或 handler。
- 展示部分清單時優先用 slice，例如 `items[offset:offset + page_size]` 或 iterator 上的 `itertools.islice()`。slice 是 UI preview / seed page / head sample 的正常工具，不代表遠端已完整枚舉。
- array / list / tuple 適合表達有序集合；set / dict 適合 dedupe 與 membership。不要用字串拼接或 sentinel row 混在同一 list 來表示 metadata。
- 若 slice 只顯示部分資料，payload 必須帶 `shown_start`、`shown_end`、`total_known`、`has_more`、`remaining` 或 equivalent 欄位，讓 UI 清楚知道這是窗口，不是全集。

這條規則和 declarative profile / middleware pipeline 是同一方向：profile 定義 page size、range、depth、max nodes；pipeline 用 range/slice/islice 安全執行；UI 只呈現窗口與 next action。

## 第二階段收斂順序

1. UI 狀態 contract
   - `status` / `outcome_bucket` / `warning_code` -> `label` / `tone` / `next_action`
   - Tk、Web、未來 Qt 都讀同一份後端 display payload。
   - 前端不自行判斷業務狀態。
   - 2026-05-27 已開始落地：`api_launcher.crawler_asset_display.DisplayProfile` / `plan_outcome_display_profile()` 會把 plan outcome 的 `outcome_bucket -> label/tone/summary/next_action_label` 收成 typed display profile，並隨 plan outcome payload 輸出 `display_profile`。

2. 動態界域表單 contract
   - `source_type` / asset capability -> form fields / presets / validation / defaults
   - 前端根據 form spec 產生表單。
   - 不在 Tk/Web 裡硬寫 STAC、CKAN、CMR 等表單邏輯。
   - 2026-05-27 已開始落地：`api_launcher.crawler_asset_bound_forms.CrawlerAssetBoundFormProfile` / `crawler_asset_bound_form_profile()` 會把 bounds form 的欄位數、facet、groups、schema probe 需求、presets、recommended values 與 next action 收成 typed profile，並隨 `CrawlerAssetBoundFormSpec.to_dict()` 輸出 `form_profile`。前端仍保留原本 `fields` / `presets` / `recommended_values` 相容欄位。

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

2026-05-27 後續切片已新增 `api_launcher.crawler_capability_profiles.CrawlerCapabilityProfile`。它把一個來源的 source type、auth mode、terms risk、pagination mode、content format hints、bounds facets、middleware ids、failure policy 與 effective request policy 收成可序列化 profile，並掛到 crawler asset payload 的 `capability_profile`。這仍然不取代既有 Python handler；它只是把 matrix cell 先落成 validated profile，供 Tk/Web/Qt、agent 與後續 gateway 共用。

裝飾器在這條路線中的定位是「註冊與標註」，不是把控制流藏起來。`@crawler(...)` 應把 handler 與 `CrawlerSpec` 登記到 registry / matrix，並保留 handler 原本的回傳值與錯誤語意；真正的 `DatasetCandidate[]` / `DatasetCrawlerOutput` 仍由 handler 回傳，再交給 gateway / pipeline 包裝。這能讓程式碼優雅，但不會讓 decorator 變成難 debug 的隱形業務邏輯。

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
