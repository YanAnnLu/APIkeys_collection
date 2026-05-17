# Unreal Frontend Skeleton

這個資料夾保留給未來 Unreal 前端工具與橋接腳本。

目前不要把 `.uproject`、`Content/`、大型 `.uasset` 或本機 cache 放進 repo。實際本機測試專案目前在：

```text
K:\UnrealProjects\APIkeysVirtualTwin\APIkeysVirtualTwin.uproject
```

## 邊界

Unreal 是前端，不是資料主權所在。

- Raw data、版本、checksum、license、清洗紀錄、install_id 留在 launcher 後端。
- Unreal 可以讀取 tile manifest、local tile service、preview OBJ/CSV 或必要的 baked/imported asset。
- Unreal 工具只負責匯入、串流、材質、光照、烘焙、UI 與互動。
- 水、空品、雲霧等物理/視覺模擬先接 `api_launcher/simulation_bridge.py` 的 contract，不在這裡硬寫物理引擎。

## 目前可用入口

產生 Unreal preview asset：

```powershell
py scripts\export_unreal_preview.py --project K:\UnrealProjects\APIkeysVirtualTwin\APIkeysVirtualTwin.uproject --sample-step 2
```

查看 Unreal bridge plan：

```powershell
py APIkeys_collection.py --unreal-bridge-plan
```

查看 renderer profile 與 simulation contracts：

```powershell
py APIkeys_collection.py --show-render-profile unreal --list-render-effects --list-simulation-contracts
```

## 後續骨架

未來可以在這裡加入：

- Unreal Editor Python import script
- tile manifest reader
- data-source locator for `/Game/APIkeysCollection/...`
- runtime streamer interface draft
- frontend-only smoke test notes

這些工具都應讀取 launcher 輸出的 manifest/contract，不要繞過後端自行管理資料集。
