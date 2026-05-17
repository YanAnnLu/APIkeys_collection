# Unreal Engine Bridge 設計筆記

更新日期：2026-05-17

## 產品位置

`APIkeys_collection` 負責資料 discovery、下載、版本、清洗、manifest、健康檢查與資料庫/檔案納管。

Unreal Engine 5 負責最終互動前端，也就是全球尺度虛擬孿生的展示層。

目前本機偵測到：

- Unreal Engine: `C:\Program Files\Epic Games\UE_5.7`
- Unreal project: 尚未設定 `.uproject`

## 橋接原則

Launcher 不應直接把科學 raw data 塞進 Unreal。比較穩的流程是：

```text
provider/dataset
-> raw download
-> manifest + SQLite registry
-> curated/renderer bridge asset
-> Unreal bridge staging
-> Unreal project Content/APIkeysCollection
```

## 目前支援的概念

- `config/launcher_integrations.example.json` 有 `unreal_projects` profile。
- `api_launcher/environment.py` 會檢查 Unreal Engine、UnrealEditor、`.uproject`、Content 目錄。
- `api_launcher/unreal_bridge.py` 會把 `render_bridge_assets` 規劃成 Unreal target path。
- CLI `--unreal-bridge-plan` 可以列出目前 bridge asset 應該同步到哪裡。

## 暫定 Unreal 目錄

假設 Unreal project 是：

```text
K:\VirtualTwin\VirtualTwin.uproject
```

資料會同步到：

```text
K:\VirtualTwin\Content\APIkeysCollection\
```

Unreal mount path 會類似：

```text
/Game/APIkeysCollection/gebco_2025/topography_grid/topo
```

## 後續要解決

- 決定 Unreal 端讀取格式：直接讀 `.npy`、轉 `.uasset`、或使用中介格式。
- 地形資料可能要切 tile，不應一次載入全球高解析網格。
- 星表資料可轉成 Niagara/Instanced Mesh/自定 shader buffer。
- 大型資料應該以 manifest 驗證後再同步，不應在 Unreal Editor 內下載。
- 需要 Unreal project 建立後，把 `launcher_integrations.local.json` 的 `project_path` 與 `content_root` 補上。
