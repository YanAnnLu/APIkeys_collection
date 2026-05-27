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
