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
