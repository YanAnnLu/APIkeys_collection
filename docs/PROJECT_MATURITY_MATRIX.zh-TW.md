# RRKAL 專案成熟度矩陣

最後更新：2026-05-28

這份文件定義 RRKAL / `APIkeys_collection` 之後回答「整體進度多少」時的標準口徑。

結論很直接：**不要再用單一百分比回答整個專案進度**。RRKAL 同時包含已驗證的小閉環、bounded live-source 路徑、partial importer、contract-only renderer/simulation，以及未開始的 Qt。把它們揉成 `94%` 或 `70%` 都會誤導交付判斷。

## 機器可讀入口

```powershell
py -3 -B APIkeys_collection.py --db state\mvp_demo\launcher.sqlite --project-maturity-json
```

如需寫出 JSON 或 Markdown：

```powershell
py -3 -B APIkeys_collection.py --db state\mvp_demo\launcher.sqlite --write-project-maturity-json state\reports\project_maturity.json
py -3 -B APIkeys_collection.py --db state\mvp_demo\launcher.sqlite --project-maturity-markdown state\reports\project_maturity.md
```

此 CLI 會輸出：

- `canonical_delivery_scope`：目前可明確說 100% 的 bounded 小閉環。
- `rows`：各能力區塊的成熟度。
- `reporting_rule`：禁止用單一百分比描述整體專案。
- `why_no_single_percent`：說明為什麼 single percent 會混淆 contract、partial 與 delivered。
- `background_jobs_and_scheduler.metrics`：目前會列出 Tk 背景工作 policy registry 是否可用、bounded policy 數量，以及各 policy 的 `max_active_jobs`；截至本 checkpoint，Tk bounded policy count 為 11。

## 成熟度等級

| 等級 | 可以怎麼說 | 不可以怎麼說 |
| --- | --- | --- |
| `deliverable_100` | 明確 bounded scope 已實作、測試、CI 通過，可對該範圍說 100%。 | 擴張成全產品 100%。 |
| `implemented_bounded` | 在標明限制的範圍內已可使用。 | 說成所有來源、所有格式、所有 UI 都完成。 |
| `partial_bounded` | 已有真實路徑，但覆蓋率未完成。 | 說成該大類已全面完成。 |
| `contract_only` | 已定義契約、資料結構、目標行為。 | 說成已有真實執行引擎或 real I/O。 |
| `planned_not_started` | roadmap 或未來皮膚/平台方向。 | 寫進使用者正式流程或交付範圍。 |
| `hardening_needed` | 可用，但還需要穩固性設計。 | 當成長期大量使用已無風險。 |

## 目前矩陣摘要

| 區塊 | 成熟度 | 可交付範圍 | 主要限制 |
| --- | --- | --- | --- |
| Canonical MVP demo closure | `deliverable_100` | Offline Socrata 311 fixture 已完成 `seed -> candidate -> plan -> download -> manifest -> SQLite import -> JSON handoff`。 | 只代表 canonical 小閉環，不代表全部 crawler / renderer / Qt。 |
| Source pattern 與 crawler handlers | `implemented_bounded` | 支援來源介面類型的 bounded detection、draft、crawl audit、warning / next_action。 | 這是 discovery 能力，不是所有來源都有 deep adapter 或 curated import。 |
| Crawler asset download/import | `partial_bounded` | Web/Tk/CLI 有正式 asset / seed download-import path，可在 capability 允許時跑真下載與匯入。 | 很多 live source 仍需要 credential、adapter review 或 content parser。 |
| Content parser/import | `partial_bounded` | CSV / JSON / JSONL / GeoJSON 與部分 archive-derived tabular payload 可進 manifest/import。 | NetCDF、HDF、GeoTIFF、Zarr、Parquet、unknown 仍不能普遍 curated import。 |
| Provider-specific deep adapters | `partial_bounded` | GEBCO、HYG、yfinance 有明確 adapter registry。 | source handler 覆蓋遠大於 deep adapter 覆蓋，不能混講。 |
| Tk / Web UI | `implemented_bounded` | Tk 是穩定控制台，Web 是 UIUX / Qt-QSS 前導面；兩者已接後端 display/form/profile contract。 | 仍有部分 live-source 入口需要更直覺的 preset/dropdown/credential flow。 |
| Credential setup | `implemented_bounded` | 本機登入設定、`記住我的帳號`、缺憑證 guard、`.env` 原子寫入已具備。 | Provider 官方註冊 / API Key 取得仍主要靠連結與人工登入。 |
| Renderer / Unreal / Simulation | `contract_only` | 已有 renderer/simulation/unreal bridge contract 或 planned target。 | Unreal 不做 real I/O；simulation backend 是 `contract_only`，不能說已實作引擎。 |
| Qt modern UI | `planned_not_started` | 未來 Qt/QSS 會消費同一份後端 contract。 | 目前正式可操作面是 Tk / Web Preview，不是 Qt。 |
| Background jobs / scheduler | `hardening_needed` | Tk/Web 已用背景 thread/queue 避免立即卡 UI；Tk 主要背景工作上限已收斂到 typed policy registry。 | 還缺 unified bounded job scheduler / DB write gate，policy registry 不是完整 scheduler。 |
| Docs / handoff / governance | `implemented_bounded` | AGENT_START_HERE、handoff、GTD、docs drift guard、development log、pre-push smoke、CI watch 已成工作流。 | 若 checkpoint 忘記更新文件，仍會再次漂移。 |

## 之後回答進度的模板

當使用者問「整體進度多少」時，請不要回答單一百分比。應回答：

```text
目前不能用單一百分比回答。

- 可交付小閉環：100%
- Source pattern / crawler discovery：implemented_bounded
- Formal crawler asset download/import：partial_bounded
- Content parser/import：partial_bounded
- Provider-specific deep adapters：partial_bounded
- Tk/Web UI：implemented_bounded
- Renderer/Unreal/Simulation：contract_only
- Qt：planned_not_started
- Background scheduler：hardening_needed

若要交付客戶，必須先說明交付的是哪一個 bounded scope。
```

## 客戶交付原則

客戶交付不應追求「整個願景 100%」，而是要交付明確範圍：

1. 定義交付邊界。
2. 定義 acceptance criteria。
3. 用 CLI JSON / smoke / tests / CI 證明該邊界已完成。
4. 在文件中明確寫出不包含哪些範圍。

目前可最穩定交付的是 `canonical_mvp_demo_closure`。下一個交付候選應選一條 live source 的 bounded closure，例如：

```text
一個 public source profile
-> seed 枚舉
-> 選 seed
-> bounds preset
-> 下載 / 匯入
-> SQLite artifact
-> Web/Tk 顯示結果
```

該 closure 完成後，也應新增自己的 readiness artifact，而不是覆蓋 canonical MVP 的 100%。
