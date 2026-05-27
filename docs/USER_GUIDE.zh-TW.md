# 使用者操作指南

最後更新：2026-05-28

這份文件寫給第一次打開 launcher 的人。它用操作角度說明目前 UI 可以做什麼，以及哪些功能還是骨架。

## 目前校準狀態（2026-05-27）

本文件已用第二輪文件漂移審計重新校準。請注意：

- Web Preview 的後端 API 已用 in-process HTTP smoke 驗證：`/api/health`、`/api/crawler-assets`、`/api/diagnostics/crawler-handler-smoke`、`/api/events/recent` 可回應；本機 crawler asset card 數為 23，handler diagnostics 顯示 14 個 source type 的離線 contract smoke 為 pass。
- Web Preview 也已用瀏覽器實際開啟驗證：四個工作區「爬蟲資產 / 下載器 / 匯入審核 / 事件紀錄」可見；下載器主按鈕已改為「下載 / 匯入目前資產」，會呼叫正式 crawler asset download/import endpoint；選取 NASA Earthdata CMR 會出現「需要登入 / API Key」與「記住我的帳號」登入設定流程。
- `--handoff-report-json` 驗證 canonical MVP demo 仍可跑到 `download_import_completed`，目前 demo 匯入表為 `nyc_open_data_socrata_socrata_311_sample_190`、`row_count=3`。
- `--crawler-run-summary-json` 目前回報 `summary_scope.status=missing_listing`，代表本機事件視窗沒有最新 crawler listing event。若要向人展示「某入口目前已枚舉的 seed 清單」，請先在 Web/Tk 重新枚舉該入口，不要把舊文件描述當成最新 seed 狀態。
- 舊「真下載示範」與「展示模式」是過渡 / demo-only surface，用來證明下載、manifest、SQLite import 或續傳能力，不代表所有 crawler source 都已完全打通。Web Preview 的主要下載心流已改回 crawler asset -> seed listing -> bounds/credential -> download plan -> download/import；舊 real-download demo 已移到 developer diagnostics 路由，不再是一般使用者 API。

## 啟動方式

目前主要入口是 Tk 桌面 UI：

```bash
python APIkeys_collection_ui.py
```

在目前 macOS 接力環境，請用專案指定的 Conda env，不要把套件裝進 `base`：

```bash
cd "/Users/yen-an/Library/CloudStorage/CloudMounter-Google#1/APIkeys_collection"
conda run -n metal_trade_312 python APIkeys_collection_ui.py
```

Windows 可以用：

```powershell
py APIkeys_collection_ui.py
```

若 UI 一啟動就因 `init.tcl`、Tcl/Tk runtime 或 display 問題失敗，入口會在 stderr 印出修復建議並回傳非零錯誤碼。Windows 上先改用系統 Python 的 `py -B APIkeys_collection_ui.py`；若一定要使用 `.venv`，請用包含 Tcl/Tk 的 Python 重建 venv，不要把 base/system Python 套件混進專案環境。

從 IDE 或背景 shell 啟動時，主視窗會在初始化後自動浮出並在終端機印出 `RuRuKa Asset Launcher (RRKAL) UI ready ...`，方便確認 UI 已經完成啟動。

若要先確認後端狀態：

```bash
python APIkeys_collection.py --init-db --seed --manifest-health --summary
python -m unittest discover -s tests
```

## Web Preview / UIUX 對照層

目前主要操作入口仍是 Tk 桌面 UI。若要用瀏覽器討論介面心流、CSS 視覺語言或未來 Qt/QSS 參照，可以啟動 Web Preview：

```powershell
scripts\run_web_preview.cmd
```

或：

```powershell
py -B -m frontends.web.server --host 127.0.0.1 --port 8765 --port-scan 20 --open
```

接著開啟：

```text
http://127.0.0.1:8765/
```

Web Preview 會顯示 crawler asset 清單、Crawler Passport、動態界域表單、任務互動紀錄與後端 JSON 結果。建立下載計畫後，如果後端回報仍有內容 Parser / 內容格式待辦，界域表單狀態列會用同一份 `plan_outcome.content_review` 顯示待辦徽章。Web 右側資產護照與 Tk Crawler Passport 都會顯示 compact `plan_passport` 摘要，包含候選、可下載、待 Adapter、內容待辦、憑證與缺 Provider 狀態；完整 resolved plan 仍留在 review/download path，不會複製到 UI 狀態。這不是另一套後端，也不會重寫 crawler；它只呼叫 `api_launcher` 的既有 JSON contract。Tk 可以維持樸素穩定的控制台語言，Web Preview 則可以用更完整的視覺和互動設計來討論 UIUX、響應式版面與未來 QSS token。

下載器分頁的「下載 / 匯入目前資產」會使用目前選取的 crawler asset 與表單值，呼叫 `POST /api/crawler-assets/{asset_id}/download-import`。這條路徑會先建立 resolved download plan，再只提交 bounded direct download/import slice；若來源需要登入或 API Key，會先停在「記住我的帳號」設定流程，不會假裝下載成功。正式下載匯入的輸出預設寫到本機下載資料夾下的 `RuRuKa Asset Launcher Web Preview`，避免把 live SQLite import 壓在 K 槽雲端同步路徑上。

Seed 清單中的「下載此 seed」會呼叫正式 seed 下載 / 匯入路徑。Web 會走 `POST /api/crawler-assets/{asset_id}/seed-download-import`；Tk 會從右側 Crawler Passport 開「Seed 表格 / 下載」，選取 seed 後呼叫同一個後端 service。後端會驗證該 seed 是否屬於目前 crawler asset，再從 catalog seed 建立 resolved plan。它不會重新打遠端 crawler，也不是舊「真下載示範」；若 seed 沒有可直接下載的 URL、需要憑證或需要 adapter review，畫面應依後端回傳的 `plan_outcome` / `next_action` 顯示下一步。Web seed row、Tk Seed 表格與 Tk Crawler Passport 摘要會先顯示後端 `content_import_profile` 產生的匯入路徑，例如可匯入 SQLite、下載後需解壓或轉換、內容 Parser 待辦，讓使用者在按下載前就知道這筆 seed 大致會進哪條處理路徑。

Tk 版在啟動 seed 下載前也會先做本機登入檢查。若來源需要登入或 API Key，但目前尚未設定完整，Tk 會先停下並開啟「登入設定 / 記住我的帳號」視窗。這個視窗會顯示官方登入 / 申請 API Key 入口、需要貼上的欄位、目前是否已設定，以及「清除已保存」與「記住我的帳號」勾選。留空代表不變，不會預填已保存的明文金鑰；儲存後才會交給後端本機 credential service 更新本機忽略檔或目前執行環境。它不會直接啟動背景下載 thread 去送出必然失敗的請求。

Web seed bar 與 Tk Crawler Passport 都會盡量呈現後端的 seed 枚舉完整度：如果 crawler 回報遠端仍有下一頁，畫面會說明「還有下一頁線索」；如果遠端已列完，會說明已列完；如果 handler 尚未回報遠端完整度，畫面只會說明目前能依本機 catalog 視窗判斷。使用者不需要看到 raw pagination token。

若 8765 已經被其他前端工具或另一份本地 clone 使用，Web Preview 會自動改用下一個可用 port，終端機會印出實際網址。不要為了預覽 UI 去終止不明程序。

如果只用 IDE Live Preview 直接開 `frontends/web/static/index.html`，可以看見靜態版面，但 `/api/...` endpoints 不會存在，因此看不到真實 crawler asset 清單與動態界域表單。要看完整互動，請使用上面的 `frontends.web.server` 啟動方式。

開發者若要確認 crawler handler contract，可在 Web Preview 讀 `GET /api/diagnostics/crawler-handler-smoke`，或在 Tk 版開啟「工具 > 開發者：Crawler handler diagnostics」。兩者只回傳 / 顯示 compact summary 與 developer-only 標記，不包含每個來源的完整 smoke report，也不代表 live endpoint 可用；一般使用者下載資料不需要操作它。

## 主畫面

主畫面可以先理解成「科學資料集的 Steam 收藏庫」：

- 左側是篩選區。
- 中間是資料源清單。
- 右側是資料源詳情抽屜。
- 下方是下載計畫與下載工作狀態。

清單中的「下載」欄不是所有資料都能直接下載。只有明確像檔案 URL 的來源會走目前的 direct downloader；API endpoint 或文件頁通常會標為需要 adapter，避免把網頁誤當資料集下載。

## 左側篩選

左側有兩種模式：

- `依類型`：用氣象、海洋、衛星、金融等資料類型篩選。
- `依提供商`：用 NOAA、NASA、GEBCO 等提供商篩選。

切到 `依提供商` 時，launcher 會用每個提供商的官方網址嘗試抓網站 favicon，也就是瀏覽器分頁左邊的小圖示。圖示會快取在：

```text
state/favicons/
```

如果第一次沒有馬上顯示，通常只是背景還在抓；抓不到時會顯示預設小圖示，不會阻擋操作。

## 右側詳情抽屜

點選資料源後，右側抽屜會顯示：

- 提供商名稱
- metadata 預覽
- AI 生成描述 textbox
- 標籤、存取方式、狀態、範圍、官方連結
- 常用操作按鈕

抽屜寬度會依畫面比例調整，開關時有短動畫，內容太長會出現捲動，不應再把描述擠成窄直欄。

## 搜尋與欄寬

上方搜尋框可以搜尋資料源名稱、分類、提供商、API 或關鍵字。灰色提示文字只是提示，不會真的當成搜尋條件。

表格欄位可以像 Excel 一樣拖曳欄線調整寬度。調整後會寫進本機設定：

```text
config/launcher_integrations.local.json
```

這個檔案不會提交 Git。

## AI 輔助模型

AI 相關設定集中在：

```text
整合 > AI 輔助模型選擇
```

這裡最重要的是「選擇」。你可以登入多個 AI 服務，也可以在 profile 裡保存 token，但真正生成描述時，只會調用這裡勾選的 profile。

目前支援的方向：

- `Local Ollama`：本機模型，不需要雲端登入。
- `Gemini Flash`：現階段 MVP 主路線是 `GEMINI_API_KEY`。貼一次後會保存到本機 `state/private`，下次啟動自動載入。Google 帳號瀏覽器登入保留為未來正式 OAuth 入口。
- `OpenAI-compatible`：使用 chat-completions JSON 格式，可指向 OpenAI 或相容服務。

## AI 描述生成與 key

在 `整合 > AI 輔助模型選擇` 選取某個 profile 後，可以按 `保存 API key`。

如果要用 Gemini 產生資料源描述，現階段最短路徑是：

```text
整合 > AI / Gemini 串接中心 > 保存 Gemini API key 並啟用
```

這個 key 會寫入：

```text
state/private/ai_api_keys.private.json
```

這個資料夾被 `.gitignore` 排除，不會提交到 GitHub。程式啟動時會自動讀取已保存的 key，使用者不需要每次重貼。

啟動時只會讀取本機保存的 API key，不應該自動啟動 Google/OAuth 登入、開瀏覽器、開本機設定檔，或要求使用者貼 OAuth Client ID。Google 登入入口只在使用者主動從 `整合` 選單開啟時才出現。

Google 帳號登入與 QR / 裝置碼登入不是取消，而是中期再做：等 MVP 閉環完成、專案有官方 OAuth App 或後端授權 broker 後，再當成正式入口。一般網路服務能讓使用者直接選 Google 帳號，是因為服務方已經替使用者處理好 OAuth App；使用者不應被要求貼 OAuth Client ID。若目前開發版沒有官方 OAuth App，launcher 只會說明尚未開通，不再把使用者導到 Client ID 輸入框。

OAuth 登入成功後，token 會存在：

```text
state/private/ai_oauth_tokens/
```

`整合 > Google OAuth（中期 / 開發者） > Google QR / 裝置碼（中期正式入口）` 保留給 device-code 情境：例如沒有鍵盤的裝置、或需要在另一台裝置輸入代碼。它不是一般 Google 網頁服務的快速登入。如果某個 AI 服務沒有官方 OAuth / device-code 端點，launcher 不會假裝可以掃 QR。

## Google / Gemini 入口

`整合 > AI / Gemini 串接中心` 是 Google/Gemini 的快速入口。現階段主按鈕是 `保存 Gemini API key 並啟用`，用途是先讓 AI 描述生成能跑。`中期：Google 帳號登入` 與 `中期：QR / 裝置碼` 是稍後要做的正式 OAuth 方向，不會在 MVP 階段要求一般使用者手動貼 OAuth Client ID。

要切換模型，仍然回到：

```text
整合 > AI 輔助模型選擇
```

## 登入 / 串接入口整理

帳號、API key、OAuth、資料庫工具與資料儲存連線都集中在上方選單列的 `整合`。右側資料源抽屜只保留跟目前資料源直接相關的動作，例如開啟文件、AI 產生說明、檢查 metadata、加入下載計畫與納管操作。

右側抽屜分成固定標題列、可捲動內容區、固定底部動作區。也就是說：關閉按鈕和底部動作按鈕不應該被長描述推走。

Crawler 發現的資料集候選會先進入本機 catalog。主列表可以直接顯示在各 provider 底下，若畫面太滿，可用：

```text
資料庫 > 在列表顯示 crawler 資料集
```

切換顯示/隱藏。更完整的審核、標記可用、拒絕、加入下載計畫，仍在 `資料庫 > 審核資料集候選`。

Tk UI 目前仍可用來完成 MVP 閉環，但它在彈窗比例、複雜設定頁與桌面常駐能力上已接近上限。中期路線已記錄為 PySide6 / Qt：等後端 MVP 穩定後，再把 UI 遷移成 Qt 的主視窗、設定中心、splitter/dock、系統匣 / macOS menu bar shell。現在不展開重寫，先把功能閉環做完。

## MVP Demo Flow

如果只是要快速驗證下載、manifest 與 SQLite 匯入管線，可以使用兩種 UI 入口：

```text
工具 > 產生 MVP Demo Flow
工具 > 一鍵驗證 MVP Demo Flow
```

`產生 MVP Demo Flow` 會呼叫 `api_launcher.mvp_demo`，在 `state/mvp_demo/` 寫出固定 flow JSON、Socrata adapter review plan、agent-readable adapter review JSON、離線 JSON fixture 與離線 direct plan，並把離線 direct plan 加到下方下載計畫。它不會自動下載，也不會自動匯入；下一步要在下載計畫按 `開始`，下載完成後再按 `匯入`。

`一鍵驗證 MVP Demo Flow` 會在背景直接執行同一條 canonical 離線 smoke：重寫 demo artifacts，跑完 `download -> manifest -> SQLite import`，再用彈窗顯示 `stage`、資料表、匯入筆數、下載/匯入成功數與 artifact 路徑。若失敗，彈窗會提示先看 `工具 > 最近事件紀錄`、`工具 > 修復 / 驗證資產`，並附上可在 PowerShell 重跑的 CLI 指令。

這條 Demo 是 smoke test，不是正式新增供應商的捷徑。正式新增資料源仍應走 crawler/source/candidate/review 流程。

## 開發者 CLI

`工具 > 開發者 CLI` 會打開一個簡單命令面板，工作目錄固定在專案根目錄。它適合快速跑：

```bash
python APIkeys_collection.py --help
python -m unittest discover -s tests
```

它不是完整終端機，也不適合長時間互動程式；比較像 UI 裡的單次命令快捷入口。

如果是在 Windows PowerShell，下面範例可把 `python3` 換成 `py -B`。`-B` 會避免在同步碟工作區寫入 `__pycache__`。

### 常用閉環指令

| 目的 | 指令 |
| --- | --- |
| 初始化 catalog / SQLite schema | `python3 APIkeys_collection.py --init-db --seed --summary` |
| 看 provider 清單 | `python3 APIkeys_collection.py --list-providers` |
| 看分類清單 | `python3 APIkeys_collection.py --list-categories` |
| 產生範本 | `python3 APIkeys_collection.py --generate-templates --output-dir .` |
| 檢查下載 manifest 與 catalog 摘要 | `python3 APIkeys_collection.py --verify-downloads --manifest-health --summary` |
| 看最近事件紀錄 | `python3 APIkeys_collection.py --show-logs 20` |

### Provider / portal intake

| 目的 | 指令 |
| --- | --- |
| 從官方來源頁抓 provider 候選 | `python3 APIkeys_collection.py --discover-provider-candidates --write-provider-candidates state/provider_candidates.review.json` |
| 將 provider 候選寫成本機 source 草稿 | `python3 APIkeys_collection.py --write-provider-candidate-source-drafts --provider-candidate-source-drafts-input state/provider_candidates.review.json --write-provider-candidate-source-drafts-json state/provider_candidate_source_drafts.summary.json` |
| 新增本機 provider discovery seed | `python3 APIkeys_collection.py --add-discovery-seed --seed-provider-id ID --seed-name "名稱" --seed-homepage-url URL` |
| 解析團隊入口表 | `python3 APIkeys_collection.py --portal-intake-report --write-portal-intake-json state/portal_intake.review.json` |
| 把乾淨入口草稿提升到本機 ignored config | `python3 APIkeys_collection.py --promote-portal-intake-local` |
| 審核本機 discovery config 是否可提升正式 catalog | `python3 APIkeys_collection.py --promote-local-discovery-catalog --promote-local-discovery-dry-run --write-local-discovery-audit-json state/local_discovery_audit.json` |

Tk UI 可用 `資料庫 > 審核本機 discovery 草稿` 跑同一條 dry-run audit。它會把結果寫到 `state/local_discovery_audit.ui.json`，並用 crawler `audit_summary` 顯示整體狀態、warning 分組、下一步與略過來源；這個入口不會寫入正式 catalog。

Tk UI 也可用 `資料庫 > 發現 provider 候選` 跑 provider/source discovery。它只輸出 `state/provider_candidates.ui.json` 作為 review JSON，並在彈窗中預覽候選 provider id 與 confidence；這不是安裝、納管或正式 catalog 寫入，也不會抓取 API key 或登入內容。接著可用 `資料庫 > 審核 provider 候選` 讀取同一份 JSON，用列表查看 provider id、名稱、confidence、auth type、文件 URL，右側會列出 source/docs/API/signup/evidence 與 review-only 提醒，並可直接開來源、開文件或打開 review JSON。若確認某筆候選值得保留，可按「寫入本機 seed」把它寫進 ignored local provider discovery seed；若候選已明確標出或可保守推導出支援的 crawler type 與 endpoint，也可按「寫入 source 草稿」寫入 ignored local dataset discovery source。這兩個動作都仍未寫正式 catalog，下一步應跑 `資料庫 > 審核本機 discovery 草稿` 或 CLI dry-run promotion guard。

`--write-provider-candidate-source-drafts-json` 的 summary 會帶出 `next_action`、`audit_command` 與 `audit_source_ids`，同時 CLI 會留下 `provider_candidate_source_drafts_written` structured event；`--handoff-report` / `--handoff-report-json` 會顯示最近一次 source draft 寫入與下一步 dry-run audit 指令，方便 Mac 或 heartbeat agent 接力。

### Dataset discovery / candidate review

| 目的 | 指令 |
| --- | --- |
| 跑資料集候選爬蟲 | `python3 APIkeys_collection.py --init-db --seed --discover-dataset-candidates --write-dataset-candidates state/dataset_candidates.review.json --upsert-dataset-candidates` |
| 只跑單一 source | `python3 APIkeys_collection.py --discover-dataset-candidates --dataset-discovery-source SOURCE_ID --dataset-discovery-limit 10` |
| full-crawl 到沒有下一頁或安全 cap | `python3 APIkeys_collection.py --discover-dataset-candidates --dataset-discovery-full-crawl --dataset-discovery-max-pages 10 --dataset-discovery-strict-audit` |
| 離線檢查所有 crawler handler 的 audit contract | `python3 APIkeys_collection.py --dataset-discovery-handler-smoke-json` |
| 列出候選 | `python3 APIkeys_collection.py --list-dataset-candidates --dataset-candidate-status all` |
| 以 JSON 列出候選 | `python3 APIkeys_collection.py --list-dataset-candidates --dataset-candidates-json` |
| 標記候選可用 | `python3 APIkeys_collection.py --review-dataset-candidate DATASET_UID --dataset-candidate-decision approved` |
| 匯出候選下載 / 匯入計畫 | `python3 APIkeys_collection.py --export-candidate-plan state/candidate_plan.json --candidate-plan-status approved` |

`--dataset-discovery-handler-smoke-json` 是開發者 / agent 用的離線 contract smoke，不會連到 NASA、NOAA 或任何 live endpoint。若只想看目前交接狀態，`--handoff-report` / `--handoff-report-json`、`--heartbeat-plan-json`、heartbeat agent prompt、Web Preview 的 `/api/diagnostics/crawler-handler-smoke`，以及 Tk 的開發者 diagnostics 入口也會顯示同一組 compact 摘要；只有摘要異常時才需要跑完整 smoke JSON 看 per-source 細節。

### Adapter review / download / import

| 目的 | 指令 |
| --- | --- |
| 產生可重複 MVP Demo Flow | `python3 APIkeys_collection.py --db state/mvp_demo/launcher.sqlite --init-db --seed --write-mvp-demo-flow state/mvp_demo/flow.json` |
| 一鍵離線驗證 MVP Demo Flow | `python3 APIkeys_collection.py --db state/mvp_demo/launcher.sqlite --init-db --seed --run-mvp-demo-smoke-json state/mvp_demo/flow.json` |
| 產生 yfinance 離線金融時間序列 Demo plan | `python3 APIkeys_collection.py --write-yfinance-demo-plan state/yfinance_demo/plan.json --yfinance-symbol AAPL --yfinance-symbol MSFT` |
| 明確 opt-in 抓取 yfinance live CSV 並產生匯入 plan | `python3 APIkeys_collection.py --write-yfinance-live-plan state/yfinance_live/plan.json --yfinance-symbol AAPL --yfinance-query-window daily_1mo --yfinance-storage-target auto --yfinance-retention-days 365 --yfinance-acknowledge-unofficial` |
| 針對 yfinance plan 產生儲存目標 dry-run 審查檔 | `python3 APIkeys_collection.py --write-yfinance-storage-review state/yfinance_live/storage_review.json --yfinance-storage-review-plan state/yfinance_live/plan.json` |
| 從 yfinance 儲存審查檔產生人類 / DBA 交接文件 | `python3 APIkeys_collection.py --write-yfinance-storage-handoff state/yfinance_live/storage_handoff.md --yfinance-storage-handoff-review state/yfinance_live/storage_review.json` |
| 列出 plan 裡需要轉接器處理的項目 | `python3 APIkeys_collection.py --adapter-review-plan state/candidate_plan.json` |
| 寫出 agent-readable Adapter 待辦 JSON | `python3 APIkeys_collection.py --adapter-review-plan state/candidate_plan.json --write-adapter-review-json state/adapter_review.json` |
| 解析可安全下載的小樣本或 direct resource | `python3 APIkeys_collection.py --resolve-adapter-plan state/candidate_plan.json --write-resolved-adapter-plan state/candidate_plan.resolved.json` |
| 執行 direct entries 下載 | `python3 APIkeys_collection.py --run-download-plan state/candidate_plan.resolved.json --download-plan-limit 1 --verify-downloads --manifest-health` |
| 以 JSON 取得下載/匯入摘要 | `python3 APIkeys_collection.py --run-download-plan state/candidate_plan.resolved.json --run-download-plan-json --download-plan-limit 1` |
| 下載後匯入支援格式 | `python3 APIkeys_collection.py --run-download-plan state/candidate_plan.resolved.json --import-supported-plan-results --import-sqlite-db state/curated_imports.sqlite` |
| 為本機 CSV/JSON 檔建立 sidecar manifest | `python3 APIkeys_collection.py --write-local-file-manifest state/manual_imports/weather.csv.manifest.json --local-file C:\data\weather.csv` |
| 直接匯入本機 CSV/JSON 檔 | `python3 APIkeys_collection.py --import-local-file C:\data\weather.csv --import-sqlite-db state/curated_imports.sqlite --import-table weather_manual` |
| 讓 agent 讀取手動匯入結果 | `python3 APIkeys_collection.py --import-local-file C:\data\weather.csv --import-sqlite-db state/curated_imports.sqlite --import-table weather_manual --manual-import-json` |
| 匯入單一 CSV manifest | `python3 APIkeys_collection.py --import-csv-manifest downloads/sample.csv.manifest.json --import-sqlite-db state/curated_imports.sqlite --import-table sample_curated` |
| 匯入單一 JSON / JSONL / GeoJSON manifest | `python3 APIkeys_collection.py --import-json-manifest downloads/sample.json.manifest.json --import-sqlite-db state/curated_imports.sqlite --import-table sample_curated` |
| 批次匯入健康 CSV manifests | `python3 APIkeys_collection.py --import-verified-csv-manifests --import-sqlite-db state/curated_imports.sqlite` |
| 批次匯入健康 JSON manifests | `python3 APIkeys_collection.py --import-verified-json-manifests --import-sqlite-db state/curated_imports.sqlite` |

`--write-mvp-demo-flow` 會寫出 `state/mvp_demo/flow.json`、一份 Socrata adapter review plan、一份 agent-readable adapter review JSON、一份離線 JSON fixture plan，以及對應的下一步指令。`--run-mvp-demo-smoke-json` 會重寫同一組 artifacts，直接執行離線 `download -> manifest -> SQLite import`，並輸出單一 JSON，包含 `stage`、`succeeded`、`table_name`、`row_count` 與 download/import 摘要。離線 fixture 可以在沒有網路時驗證核心閉環；Socrata `$limit=25` plan 則用來驗證真實 adapter resolver 會把 API view 轉成 bounded sample。

`--write-yfinance-demo-plan` 會寫出一份離線 OHLCV CSV fixture plan，欄位包含 `event_time`、`symbol`、`open/high/low/close`、`adj_close`、`volume`、`received_at`、`ingest_run_id`、`source_sequence` 與 `revision`。它的用途是驗證金融時間序列可以走現有下載、manifest 與 SQLite 匯入閉環；它不安裝 `yfinance`，也不在 CI 打 Yahoo。

`--write-local-file-manifest` 是給使用者自備本機檔案的入口。它只接受目前匯入器能處理的 CSV/CSV.GZ/JSON/JSON.GZ/JSONL/NDJSON/GeoJSON 類檔案，寫出 sidecar manifest、記錄 `file://` provenance、checksum 與來源格式，並把 raw file 記到 `manual_local_files` 這個本機 synthetic provider 底下。`--import-local-file` 會先做同一件 manifest 工作，再呼叫既有 CSV/JSON manifest importer 匯入 SQLite。它不會掃整個資料夾、不會刪除來源檔、不會背景重新下載，也不會覆蓋既有 table，除非你另外明確傳入 `--import-replace-table`。

`--manual-import-json` 可以加在 `--write-local-file-manifest` 或 `--import-local-file` 後面，讓輸出變成單一 JSON payload。這個 payload 會列出 manifest、raw asset id、匯入 table、列數、欄位、schema fingerprint、provenance review 與下一步建議，適合 heartbeat、自動化 agent 或外部工具接續 `--self-check-databases --self-check-databases-json`。不要單獨使用 `--manual-import-json`，因為它只是手動匯入流程的輸出格式。

手動匯入 manifest 的 `metadata.provenance_review` 會用中文固定說明：這是「使用者自備本機檔案」、Launcher 可安全做 checksum、raw asset 登記與 SQLite 匯入，但不會掃描整個資料夾、不會移動或刪除來源檔、不會把 `file://` 當成可重新下載來源，也不推定檔案授權可再散布或商用。這段文字是給初學使用者、團隊協作者與 agent 判斷風險用的審查摘要，不會改變匯入資料本身。

若手動匯入遇到 SQL、Excel、Parquet、Shapefile、NetCDF、HDF、ZIP/TAR 原始包或其他目前不支援格式，CLI/Tk 會拒絕匯入並提示先轉成支援的 CSV/JSON 類檔案，或把該來源留在 adapter/manual review。不要為了讓 Demo 過關而把未知格式硬塞進 SQLite。

Tk UI 也有同一條單檔入口：`資料庫 > 匯入本機 CSV/JSON 檔`，或上方 `更多 > 匯入本機 CSV/JSON 檔`。UI 會要求你選一個本機檔，並可輸入目標 table 名稱；若同名 table 已存在，會自動改成下一個可用名稱，例如 `weather_2`，不會直接覆蓋。匯入完成對話框會顯示短版「來源審查」，提醒這是使用者自備本機檔案、Launcher 只驗 checksum/匯入結果，不代表原始來源或授權已驗證。

`--write-yfinance-live-plan` 是正式 live 抓取的第一個窄入口，但必須手動加 `--yfinance-acknowledge-unofficial`。這會呼叫本機 Python 環境裡的選用 `yfinance` 套件，把結果寫成一份 local CSV，並產生 file-backed download/import plan；`--yfinance-query-window` 可選 `intraday_5d_5m`、`daily_1mo`、`daily_6mo`、`weekly_1y`，用來帶入 chart-friendly 的 period/interval 與 storage hint。若另加 `--yfinance-period` 或 `--yfinance-interval`，CLI 會把它記為 manual override。`--yfinance-storage-target` 可選 `auto`、`sqlite_mvp_table`、`mysql_timeseries_table`、`parquet_duckdb_archive`、`timescaledb_hypertable`、`clickhouse_ohlcv_table`，只寫入 plan/source/dataset metadata，表示後續可考慮的儲存目標；目前不會直接寫 MySQL、Parquet、TimescaleDB 或 ClickHouse。`--yfinance-retention-days` 也只寫入 metadata，作為本機快取治理提示，不會自動刪檔或背景刷新。後續仍要用 `--run-download-plan ... --import-supported-plan-results` 明確匯入。這條路徑不會在 crawler、CI 或背景排程中自動執行；Yahoo/yfinance 仍是非官方、personal/research-only 來源，不要把資料視為可商業再散布。

若要把 plan 裡的 storage target 推進到可審查階段，使用 `--write-yfinance-storage-review` 搭配 `--yfinance-storage-review-plan`。它會輸出 review JSON，若目標是 MySQL、TimescaleDB/PostgreSQL、ClickHouse 或 Parquet/DuckDB，還會在同名 `.dry_run.sql` 寫出審查用 SQL/命令草稿；launcher 不會連線、不會建表、不會匯入資料，也不會把 dry-run 視為已執行。若要把這份 JSON/SQL 交給人類或 DBA 審查，可以再用 `--write-yfinance-storage-handoff` 搭配 `--yfinance-storage-handoff-review` 產生 Markdown，裡面會列出 source、target、table、dry-run SQL、execution guard 與審查清單；它同樣只寫文件，不代表批准或執行。SQLite 仍是目前唯一接上既有 `--run-download-plan ... --import-supported-plan-results` 的可操作路徑。

Tk UI 也提供同一條保守入口：`工具 > 產生 yfinance 離線 Demo plan` 只建立 fixture-backed plan 並加入下載計畫；`工具 > 建立 yfinance live plan（需確認）` 會先要求使用者填寫 symbol、query window、storage target、period、interval、保留天數，並勾選 unofficial/personal-research 確認框，才會呼叫本機選用 `yfinance` 產生 CSV-backed plan；`工具 > 產生 yfinance 儲存審查 dry-run` 可讀取既有 plan，寫出 review JSON、handoff Markdown 與必要時的 `.dry_run.sql`，讓使用者或 DBA 先審查目標 schema、命令草稿與風險。query window 只輔助選擇圖表友善的查詢範圍，storage target 與保留天數也只進入 metadata，不代表 launcher 會自動寫資料庫、自動刷新或自動刪檔。這些 UI 入口都不會自動下載、匯入、背景重複抓取、直接連線寫庫或接到 crawler。

下載計畫區在 Tk UI 下方，可以用「收合下載計畫 / 展開下載計畫」切換。收合時只隱藏購物車與下載工作表格，標題列、項目數、計畫名稱與主要動作仍保留；背景下載 queue 不會因為收合而停止。

### Database / repair

| 目的 | 指令 |
| --- | --- |
| 測單一 data-store profile | `python3 APIkeys_collection.py --test-data-store mysql_default` |
| 測所有 data-store profiles | `python3 APIkeys_collection.py --test-data-store all` |
| 輸出 data-store 連線測試 JSON 與下一步指引 | `python3 APIkeys_collection.py --test-data-store mysql_default --test-data-store-json` |
| 設定本機作用中 data-store profile | `python3 APIkeys_collection.py --set-active-data-store-profile mysql_default` |
| 寫出 MySQL/PostgreSQL 等 data-store env 範本 | `python3 APIkeys_collection.py --write-data-store-env-template state/data_store_env_templates/mysql.env.template --data-store-env-template-profile mysql_default` |
| 檢查 managed database/table assets | `python3 APIkeys_collection.py --self-check-databases` |
| 產生 agent-readable database issue JSON | `python3 APIkeys_collection.py --self-check-databases-json` |
| 停止追蹤單一 database/table asset | `python3 APIkeys_collection.py --unmanage-database-asset ASSET_ID --database-repair-json` |
| 從健康 manifest 重建 missing SQLite table | `python3 APIkeys_collection.py --reimport-missing-sqlite-table ASSET_ID --database-repair-json` |
| 產生 missing MySQL/PostgreSQL table 的 dry-run SQL | `python3 APIkeys_collection.py --write-database-repair-sql ASSET_ID --database-repair-json` |

Tk `整合 > 資料儲存連線` 的測試結果現在會顯示下一步提示：缺 env 時先寫出 env 範本，缺 optional driver 時只建議在專案環境安裝 driver，連線錯誤時再檢查 host、port、database、權限、網路與 driver 相容性。

### Handoff / automation / workspace

| 目的 | 指令 |
| --- | --- |
| 產生接力報告 | `python3 APIkeys_collection.py --handoff-report state/handoff.md --manifest-health --show-logs 20` |
| 以 JSON 取得接力 snapshot | `python3 APIkeys_collection.py --handoff-report-json` |
| 產生 heartbeat 報告 | `python3 APIkeys_collection.py --heartbeat-report state/heartbeat.md --heartbeat-skip-ci` |
| 產生 heartbeat plan JSON | `python3 APIkeys_collection.py --heartbeat-plan-json --heartbeat-skip-ci` |
| 寫出外部 agent prompt | `python3 APIkeys_collection.py --heartbeat-agent-prompt state/heartbeat_prompt.md --heartbeat-skip-ci` |
| 盤點工作區檔案分類 | `python3 APIkeys_collection.py --workspace-inventory --write-workspace-inventory-json state/workspace_inventory.json` |

`--handoff-report` 會列出目前作用中 data-store profile、對應測試指令、JSON 測試指令與 env 範本指令；也會顯示最近一次 MVP demo smoke 的 `stage`、成功狀態、table 與 `row_count` 摘要。現在報告也會有 `MVP Readiness` 區塊：只要 canonical smoke 是 `download_import_completed`、`succeeded=true` 且 `row_count > 0`，就把 canonical MVP Demo closure 標成可交付，避免把 GTD 裡的 post-MVP 擴充誤算成 MVP blocker。它不會代替使用者測連線，也不會輸出密碼。若要給 heartbeat 或外部 agent 直接解析同一份交接 snapshot，使用 `--handoff-report-json`，stdout 會是純 JSON，不會混入 `[db]`、`[seed]` 或 `[handoff]` 人類提示，並包含同源的 `mvp_readiness` 欄位。

### AI / renderer / export

| 目的 | 指令 |
| --- | --- |
| 產生 provider AI 描述 | `python3 APIkeys_collection.py --generate-ai-summary PROVIDER_ID --ai-profile gemini_flash` |
| 儲存 provider AI 描述 | `python3 APIkeys_collection.py --generate-ai-summary PROVIDER_ID --ai-profile gemini_flash --write-ai-summary` |
| 寫出 tile manifest 骨架 | `python3 APIkeys_collection.py --write-tile-manifest state/tile_manifest.json --tile-dataset-uid gebco:2025` |
| 查看 library action JSON | `python3 APIkeys_collection.py --show-library-actions PROVIDER_ID --library-actions-json` |
| 匯出 catalog JSON/CSV/Markdown | `python3 APIkeys_collection.py --export-json state/catalog.json --export-csv state/catalog.csv --export-markdown state/catalog.md` |

CLI 的原則和 UI 一樣：能直接下載的才下載；入口頁、登入頁、未界定 API、過大或未知格式會留在 adapter review。需要寫入、覆蓋、DROP 或刪除資料的動作，必須有明確 ownership 與額外參數，不會默默執行。

`--show-library-actions ... --library-actions-json` 會列出每個 action 的 `enabled`、`risk`、`reason` 與 `status_badge`。`status_badge` 是短狀態碼，例如 `ready_to_plan`、`repair_requeue_ready` 或 `guarded_uninstall_ready`，方便 UI 顯示徽章，也方便 agent 不用重建 action 規則。
Tk 右鍵選單現在會把這些 `status_badge` 轉成繁中或英文短標籤顯示在動作後方；使用者可以先看見「可加入計畫」、「可重排修復」、「可受控移除」這類狀態，再決定是否執行動作。

## 資料集候選審核

`資料庫 > 發現資料集候選` 會根據目前設定的 crawler sources 並行抓取資料集目錄。它只抓 metadata，不下載大型資料檔。若你先在左側勾選幾個資料源，UI 會只爬那些資料源；若沒有勾選，會爬所有已設定 crawler 的資料源。

目前內建來源包含 NOAA/NCEI、ERDDAP、NASA CMR、STAC、GBIF、Dataverse、Zenodo、DataCite、OpenAlex、Socrata 與多個 CKAN 入口。Dataverse/Zenodo/OpenAlex 這類研究倉儲或 metadata 目錄常只先告訴你 DOI、landing page、file count 或 work metadata，所以 crawler 只記錄可審核 metadata，不會自動下載。

發現完成後，UI 會顯示錯誤、警告與「下一步」。這裡的警告不是程式崩潰，而是 crawler 審核覺得「看起來有跑完，但結果不夠可信」，例如某個來源回傳 0 筆候選、低於最低預期筆數、只抓到已存在的重複候選、重複候選數量異常偏高，或候選 metadata 缺少來源/evidence。看到警告時，應依 UI 顯示的下一步先檢查供應商頁面、搜尋詞、分頁、去重/id mapping 或解析器，而不是直接假設沒有資料。新的警告彈窗會先列出 `audit_summary` 的整體狀態、warning 分組、下一步分組與優先檢查來源，再列逐來源明細；這能讓一般使用者先知道要處理哪一類問題。

CLI 寫出的 `state/dataset_candidates.review.json` 會在頂層與每個 `source_results` 放入 `next_action`，每個來源也會列出 `warning_codes`。頂層另有 `audit_summary`，會把 crawler 狀態依 `by_status`、`by_warning_code`、`by_next_action` 分組，並列出需要處理的 `problem_sources`；heartbeat 或 agent 可先讀這個摘要，再決定要修哪個 source。常見值包含：`repair_crawler_query_or_parser` 代表該 source 可能抓到 0 筆，需要檢查搜尋詞、分頁或 parser；`review_source_overlap_or_dedupe` 代表重複過多或全部重複，需要檢查 id mapping、來源重疊或 pagination；`repair_candidate_metadata_mapping` 代表候選缺少 dataset id、title、source url 或 evidence。這些欄位是給 UI、heartbeat 與 agent 接力用的穩定狀態碼；Tk UI 會把常見狀態碼翻成繁中操作提示，不需要解析整段 warning 文字。

`資料庫 > 審核資料集候選` 會打開 crawler 找到的資料集候選清單。這裡只審核 metadata，不會下載大檔，也不會改動資料本體。

你可以先看候選的提供商、資料類型、格式、來源網址與 crawler 摘要，再選擇：

- `標記可用`：代表這個候選值得後續做下載/匯入。
- `加入下載計畫`：把候選資料集的特定版本加入目前下載計畫，並把候選狀態標成 `planned`。同一個資料商底下可以加入多個資料集/版本，不會再互相覆蓋。Launcher 會先判斷候選版本是不是直接檔案 URL；只有 direct download 才會送進下載器，入口頁/API selector 會保持需要 adapter 審核，避免把 HTML 頁面誤當資料檔下載。
- `拒絕候選`：代表暫時不適合 MVP 或來源不清楚。

CLI 也能把審核過的候選輸出成下載/匯入計畫：

```bash
python3 APIkeys_collection.py --export-candidate-plan state/candidate_plan.json --candidate-plan-status approved
```

這份 plan 會標出哪些候選可以直接下載、哪些需要 adapter review，以及下載後是否能用目前 CSV/JSON/GeoJSON -> SQLite 的 MVP 匯入器處理。UI 下方的下載計畫現在也是同一個概念：每一列是「一個計畫項目」，可能是整個資料商，也可能是某個資料集版本。

若 plan 裡的項目已標示可匯入，可以在執行下載計畫時加上：

```bash
python3 APIkeys_collection.py --run-download-plan state/candidate_plan.json --import-supported-plan-results --import-sqlite-db state/curated_imports.sqlite
```

這會先下載 direct entries、驗證 manifest，然後只把支援的 CSV/JSON/GeoJSON 類結果匯入 SQLite；不支援的格式會跳過，不會硬塞進資料庫。如果你重跑同一份 plan，而目標 table 已經存在，CLI 預設會把它記成 `skipped_existing_table`，意思是「這張表已經在了，所以先不覆蓋」，不是壞掉。若你想保留舊表、再匯入一份新表，可加 `--plan-import-existing-table-policy rename`，它會產生像 `table_name_2` 的新 table。只有你很確定要重建資料表時，才加 `--import-replace-table` 或 `--plan-import-existing-table-policy replace`。

如果 `--run-download-plan` 顯示 `submitted=0`，先看下一行的 `skip_summary`。`adapter_required` 表示還要跑 `--adapter-review-plan` 或 `--resolve-adapter-plan`，`metadata_only` 表示目前只有目錄資訊，`missing_download_url` 表示 plan 還沒有可交給下載器的 URL。這不是下載器壞掉，而是 launcher 保守地擋住未界定的 API、入口頁或 metadata；CLI 也會輸出 `next_action=run_adapter_review_or_resolve_adapter_plan_before_downloading`，提醒你先走修復/解析步驟。
若這一步是給 heartbeat 或 agent 接力判讀，請加 `--run-download-plan-json`，stdout 會改成 JSON，包含 `stage`、`next_action`、`result.skip_summary`、下載/匯入統計與 errors；人類預設摘要仍維持原本的 `[download-plan] ...` 文字。每次執行也會寫入 `download_plan_executed` structured event，後續 `--handoff-report` 會顯示最近一次 plan、stage、counts、skip_summary 與 next_action。

在 UI 裡也有同樣的引導動作：先把資料集版本加入下方下載計畫並按 `開始`，下載完成後按下載計畫區的 `匯入`，或使用 `資料庫 > 匯入可支援下載結果`。Launcher 會先檢查 sidecar manifest，只有健康且 `import_plan` 標示支援的 CSV/JSON/GeoJSON 項目會匯入 `state/curated_imports.sqlite`。下載計畫與下載工作表會顯示 `匯入狀態`，例如 `待下載/驗證`、`可匯入 -> table_name`、`已匯入 -> table_name`、`略過`、`需 adapter` 或 `需解壓/adapter`。如果同一份計畫裡一部分可以匯入、另一部分會被略過，匯入確認框會列出略過原因預覽，讓你知道哪些項目需要先做 Adapter 待辦、解析 Adapter 計畫、補下載或修 manifest。若目標 table 已存在，UI 會安全改名成 `table_name_2`、`table_name_3` 之類的新表，不會直接覆蓋既有資料；如果共用匯入流程回報已存在 table，UI 會把它顯示成「略過」，不是「失敗」。

如果資料不是透過下載計畫取得，而是你手上已有 CSV/JSON 類本機檔案，使用 `資料庫 > 匯入本機 CSV/JSON 檔`。這條 UI 路徑也會先建立 manifest，再匯入 SQLite；它只處理你選取的那一個檔案，不會掃整個資料夾。

如果看到 `需 adapter`，意思不是壞掉，而是這個入口目前還不是直接檔案，可能是 API、資料選擇器、登入後目錄頁，或下載後還需要解壓/轉換。按 `開始` 時若沒有任何 direct download，UI 會顯示略過分類並提示你先開 `Adapter 待辦` 或 `解析 Adapter 計畫`；若同一份計畫有一部分已開始下載、另一部分被略過，UI 也會另外提示已啟動的下載會繼續排隊，被略過的項目仍要走 Adapter 待辦或解析流程。Plan 裡會保存 `adapter_review` 線索，包含 adapter 名稱、來源 URL 與下一步要做的動作，方便後續開發 adapter 接手。

目前 ZIP/TAR 壓縮包已有第一個 MVP adapter：如果 plan 標示 `requires_unpack_or_adapter`，而壓縮包裡有 CSV/CSV.GZ/JSON/JSON.GZ/JSONL/NDJSON/GeoJSON 類成員，launcher 會抽出第一個支援檔、建立衍生 manifest，再接到 SQLite 匯入流程。它仍然是保守策略，不會嘗試猜測複雜壓縮包裡所有檔案的語意。

可以從 `資料庫 > Adapter 待辦` 或下載計畫上方 `更多 > Adapter 待辦` 打開目前下載計畫的 adapter 工作清單。CLI 也可以讀取已匯出的 plan：

```bash
python3 APIkeys_collection.py --adapter-review-plan state/candidate_plan.json
```

Adapter 待辦會列出 `action` 與 `outcome`：`source_resolution_required` 代表還要把 API/入口頁/selector 解析成 direct download；`downloaded_payload_transform` 代表檔案可下載，但下載後還要解壓或轉換；`import_adapter_required` / `import_transform_required` 代表匯入前仍需要 adapter 或轉換規則。JSON 輸出會在 summary 裡提供 `by_outcome`，方便 agent 先批次處理同類問題。

若候選來自 CKAN/Data.gov 這類「一個 dataset 底下有多個 resource」的平台，可以先嘗試解析 plan：

```bash
python3 APIkeys_collection.py --resolve-adapter-plan state/candidate_plan.json --write-resolved-adapter-plan state/candidate_plan.resolved.json
```

若要給 heartbeat 或 agent 讀取解析結果，可加上 `--resolve-adapter-plan-json`。這會讓 stdout 只輸出 JSON summary，包含輸入/輸出 plan、direct 新增數、resolved/unresolved 數、warning 數與 resolved plan summary；resolved plan 本體仍寫在 `--write-resolved-adapter-plan` 指定的位置。

這一步會保守地掃描 plan 裡的 resource/link metadata，只把看起來是直接檔案 URL 的 CSV/JSON/GeoJSON/ZIP 等項目轉成 direct download entry；HTML 頁、API selector、登入頁仍會留在 adapter review。不同資料目錄對檔案欄位命名不一定一樣，所以解析器會認得 `resources`、`distribution` / `distributions`、`dcat:distribution`、`links`、JSON-LD `@graph` 這些常見包裝，也會認得常見的 `download_url`、`downloadURL`、`contentUrl`、`fileUrl`、`url`、`href`，以及 `dcat:downloadURL`、`schema:contentUrl` 這類 JSON-LD 命名空間欄位；欄位值可以是字串、list，或像 `{"@id": "..."}` 這種 JSON-LD 物件，但只有 `label` 的物件不會被當成下載連結。格式提示可用 `format`、`mediaType`、`contentType`、`encodingFormat`、`dct:format`、`dcat:mediaType` 等欄位；大小提示可用 `byteSize` / `contentSize`、`dcat:byteSize`、`{"@value": "..."}`。若 CKAN/Data.gov 候選只有 `package_show` URL，或只有 `package_search` URL 加上 dataset id，解析器可以只查一次單一 package metadata，再從 resources 裡挑安全的 direct file。若候選是 DataCite DOI 或帶 DOI 的 OpenAlex work，解析器可以只查一次 DataCite DOI API，再從 metadata 的 `contentUrl` 裡挑支援格式、未宣告超過 100MB 的 direct file；DOI 頁面或 repository HTML 頁不會被當成檔案，也不會被背景爬取。若候選是 ERDDAP，而且 metadata 裡已經有 tabledap/griddap 入口，解析器也可以讀官方 `info/{dataset}/index.json`，產生一個很小的 sample CSV 下載項目。若候選是 Socrata/SODA，像 `/resource/abcd-1234.json` 或 `/api/views/abcd-1234` 這種入口會被改成 `$limit=25` 的小樣本 JSON/CSV/GeoJSON URL，避免一開始就抓完整資料表。若候選是 NOAA/NCEI Search，解析器可以把 `/search/v1/datasets` 或 `/search/v1/data` 改成 `limit=25&offset=0` 的 JSON metadata sample；這只是保存搜尋結果，不是下載 NOAA 原始資料檔。如果 `/search/v1/data` 查詢已經有 dataset 加站點或空間條件，解析器會先查 1 筆 metadata，只有第一筆結果提供小於 100MB 的 `/data/...` CSV/JSON 等明確檔案路徑時，才會把它排成 direct download。若 plan 已經是 NOAA/NCEI Access Data `/access/services/data/v1` 查詢，只有同時具備 dataset、短日期範圍與站點/空間條件時，才會變成 CSV/JSON 小樣本 direct entry；沒有邊界的查詢仍會留在審核。白話說，它是把「資料目錄中的可下載檔案或可安全小量查詢的資料」挑出來，不是背景亂爬整站，也不是一次抓完整大型資料集。

UI 裡也有同一個入口：`資料庫 > 解析 Adapter 計畫`、上方 `更多 > 解析 Adapter 計畫`，或 `Adapter 待辦` 視窗中的 `解析可下載 resources`。成功解析後，下方下載計畫會新增可下載項目，接著按 `開始` 即可跑下載。

這符合 Steam-like 模型：審核候選像把遊戲加入 library 或願望清單；本機是否已安裝、是否有個人工作區資料，是另一件事。

## Steam-like 資料模型

可以把這套 launcher 想成資料工程版 Steam：它不是只保存連結，而是把找來源、查依賴、挑版本、下載、匯入、驗證、修復與橋接懶人化。

三個概念要分開：

- `Library / entitlement`：你有權使用、收藏或審核通過哪些資料集。
- `Local install`：這台電腦實際下載、匯入或快取了哪些資料。
- `Workspace / save`：你的標註、修正、分析筆記、下載計畫與偏好。

原始資料集應該像遊戲本體一樣盡量唯讀；你的修正與分析結果應該像存檔或 mod 一樣放在 workspace/overlay。渲染橋接資產，例如 tile manifest、cache、mesh、chart index，也會逐步變成 launcher 可管理的資產。

## Mac 路徑注意

不要在 macOS 設定裡硬寫 Windows 路徑，例如：

```text
K:\UnrealProjects\...
```

跨平台路徑應放在 `*_by_platform` 類型設定中，讓 launcher 依目前系統挑路徑。啟動檢查會辨識外平台路徑，避免把 Windows 路徑當成 macOS 相對路徑。

## 目前仍在進化的部分

- provider-specific adapters 還沒有全部完成。
- API endpoint 轉資料檔的流程還需要更多 adapter。
- SQL/資料庫修復目前以診斷與安全建議為主；Repair / verify assets 的資料庫分頁可以調整單一資產的 data-store profile/schema，也可以把單一 database/table asset 停止追蹤並重新自檢。CLI/agent 流程可用 `--unmanage-database-asset ASSET_ID --database-repair-json` 做同一個 registry-only 停止追蹤動作，不會修改資料庫物件。若缺失的是先前由健康 CSV/JSON/GeoJSON 類 manifest 匯入的 SQLite table，也可以用「重新匯入資料表」從記錄的 sidecar manifest 重建它；CLI/agent 流程可用 `--reimport-missing-sqlite-table ASSET_ID --database-repair-json` 跑同一個 guard。重新匯入只會在 JSON 建議標成 `can_auto_repair=true` 的安全條件下啟用，不會 DROP 或覆蓋既有 table。若缺失的是 MySQL/PostgreSQL table，資料庫分頁可用「產生 dry-run SQL」寫出 `state/database_repair/*.dry_run.sql`；CLI 也可以用 `--write-database-repair-sql ASSET_ID` 做同一件事。這只是人工審核用 SQL，不會連線、不會執行 DDL/DML，也不會修改 registry。CLI/UI 修復成功後可用 `--show-logs 20` 查看最近的 `database_repair_completed` 紀錄；下載檔案分頁的重新排下載會寫入 `download_repair_requeue_requested`，方便從最近事件紀錄確認是否已排入佇列、被擋下或失敗。`--verify-downloads-json` 的 `repair_suggestion` 也會提供 `outcome_bucket` 與 `next_action`；例如可安全重排是 `requeue_ready` / `requeue_download`，manifest 無來源 URL 是 `source_url_missing` / `inspect_manifest_or_recreate_plan`，有 adapter 線索但不能直接重排時會回到 adapter review 或 adapter-specific repair。
- AI OAuth refresh token 與過期刷新還需要強化；目前 access token 過期時通常要重新掃 QR。
## 展示 / 進度說明模式

這個模式用來在中午展示或後續進度說明時，快速證明「目前有哪些入口爬蟲已經具備完整 seed 嘗試路徑」。它是可重跑的展示流程，不是臨時註解掉開發路徑的分支。

建議命令：

```powershell
py -3 -B APIkeys_collection.py --write-dataset-seed-coverage state/showcase/dataset_seed_coverage.json --write-dataset-seed-coverage-md state/showcase/dataset_seed_coverage.md --dataset-discovery-max-pages 3
```

GUI 展示入口：

- Windows 展示者可直接執行 `scripts\run_showcase_ui.cmd`，不需要打開程式碼或手動輸入 Python 指令；開發者仍可用 `py -3 -B APIkeys_collection_ui.py`。
- 點選 `工具 > 展示模式：產生 seed 覆蓋報告`，或主畫面 `更多 > 展示模式：產生 seed 覆蓋報告`。
- 完成後會顯示 source 數量、完整 seed 嘗試路徑數量、需要展示模式忽略 `search_terms` 的數量，並把 JSON/Markdown 寫到 `state/showcase/`。
- 點選 `工具 > 展示模式：下載資料到本機資料夾`，選擇資料夾後輸入要展示的樣本筆數上限。系統會顯示「展示下載進行中」進度視窗，先嘗試從公開 Socrata demo source 下載 JSON payload；若該公開 API 逾時，會在進度中明確切換到備援公開 CSV，而不是偽裝 Socrata 成功。兩條路徑都會寫出 sidecar manifest，並在選定資料夾的 `RuRuKa Asset Launcher Showcase\curated_showcase.db` 建立本機 SQLite `.db`。進度視窗使用 0-100% 的真實流程百分比；下載階段若遠端提供 `Content-Length` 才顯示 byte 下載百分比，若遠端沒有提供總大小，會顯示已接收 bytes 並明確說明不顯示假的下載百分比。
- 點選 `工具 > 展示模式：大型 CSV 續傳下載`，選擇資料夾後會把完整 CSV 匯出排入下方下載面板。展示時可選取該工作，按 `暫停`、等待狀態變成 `paused`，再按 `繼續`，用同一條正常下載佇列演示 `.part` 續傳能力。這條展示線只寫 CSV/manifest 到本機資料夾，刻意短路 SQL 匯入。

展示模式分流原則：

- 組員展示只走 GUI，不要求修改程式碼、註解路徑或執行開發 CLI。
- 穩定可展示的功能放在 `展示模式` 選單；仍在實驗中的完整來源爬蟲、全量 seed、SQL/MySQL/PostgreSQL 對接與轉接器補齊，留在開發或審核流程。
- 「小樣本」不是固定玩具資料，展示者可在 GUI 輸入筆數上限控制大小；真正大型或無界感的下載展示改走大型 CSV 續傳線。
- 資料夾選擇預設會指到系統 Downloads；若展示者手動選擇雲端同步資料夾，系統不會阻擋。雲端資料夾可能較慢或有短暫鎖檔，因此展示時若遇到外部網路或同步延遲，可用同一個下載面板重試或續傳。
- Web Preview 目前主下載按鈕已改為 `下載 / 匯入目前資產`，它會走正式 crawler asset download/import endpoint。舊 real-download demo 只保留在 `POST /api/diagnostics/real-download-demo` 作為 developer diagnostics / regression helper；一般使用者路徑不再暴露 `/api/demo/real-download`。

如果只需要給 agent 或自動化工具讀取的 JSON：

```powershell
py -3 -B APIkeys_collection.py --dataset-discovery-seed-coverage-json --dataset-discovery-max-pages 3
```

如果要做單一入口的完整 seed 嘗試示範：

```powershell
py -3 -B APIkeys_collection.py --discover-dataset-candidates --dataset-discovery-complete-seed --dataset-discovery-source marinecadastre_ais_daily_index_2025 --write-dataset-candidates showcase/marinecadastre_seed_candidates.json --dataset-discovery-max-pages 1 --dataset-discovery-limit 0
```

展示材料可放在 `state/showcase/`。這個資料夾現在是可追蹤的展示資產區：講稿、覆蓋率報告、樣本 CSV、簡報與截圖可以提交到 Git，方便小組展示與跨機器接力；但本機驗證下載資料、SQLite `.db`、`.log`、臨時依賴與大型 live output 仍由 `.gitignore` 排除，避免把 runtime 產物或私有資料推上去。
若需要重產展示簡報，可執行 `py -3 -B scripts\build_showcase_presentation.py`。腳本會輸出 `state/showcase/RRKAL_Showcase_Guide.zh-TW.pptx`，並讀回投影片文字檢查是否出現亂碼或缺少關鍵繁中內容；不要只用檔案是否存在判定簡報可交付。

一般使用者路徑的預設值已改為系統 Downloads 下的 `RuRuKa Asset Launcher` 子資料夾：下載 payload/manifest 預設在 `Downloads/RuRuKa Asset Launcher/downloads`，匯入後的 SQLite curated database 預設在 `Downloads/RuRuKa Asset Launcher/curated_imports.db`。開發、測試或 CI 仍可用 `--downloads-root` 與 `--import-sqlite-db` 明確覆寫。
## 爬蟲資產送進下載器

目前 Tk UI 已有第一版可操作閉環：

1. 進入「爬蟲資產」分頁，選一張 crawler asset 卡片。
   - 右側 Crawler Passport 的「Seed 清單」區塊可按「查看 Seed 清單」讀取本機 catalog 已枚舉的第一批 seed。
   - 「顯示更多 Seed」會讀下一批本機 seed，例如第 51-100 筆；這不會重新連到遠端 crawler。
   - 如果最近執行過清單擷取，Seed 清單也會顯示遠端完整度提示，例如遠端還有下一頁、遠端已列完，或目前 handler 尚未回報完整度。
   - 清單中的 `★` 代表該 seed 已被收藏；收藏狀態來自本機 crawler asset profile，Web / Tk 讀同一份後端 seed registry contract。
   - 按 `開 Seed 表格 / 下載` 會開啟本頁 seed 表格。選一筆 seed 後，可以切換收藏，或按 `下載此 Seed` 走正式 seed-level download/import service。Tk 不會在表格裡重新爬遠端，也不會自行猜 provider 規則。
2. 按「送進下載器」或同等下載計畫動作。
3. 如果該爬蟲支援界域，系統會依後端 `bounds_schema` 動態產生表單，例如 limit、bbox、time range、collection、format。
4. 送出後，UI 會在背景建立下載計畫，並把可直接下載的項目加入下方下載器。
5. 建立結果會用明確狀態提示下一步：
   - `可直接下載`：已加入下載器，可到下載器使用開始 / 暫停控制隊列。
   - `部分待辦`：已有項目可下載，但仍有項目需要 Adapter review。
   - `需 Adapter review`：目前沒有可直接下載項目，請開 Adapter review 或回到界域設定調整條件。
   - `零候選`：沒有找到符合界域的資料，請放寬時間 / 空間 / 筆數條件或重新擷取清單。
   - `被封存 / 停用`：必須先解除封存或啟用該爬蟲資產。

送進下載器後，表格的「下一步」欄與右側 Crawler Passport 會留下本次結果的短標籤，例如 `已加入 3`、`已加入 1 / 待辦 2`、`待 Adapter 2`、`零候選` 或 blocked reason。這讓你回到爬蟲資產分頁時仍能看出剛剛按下動作後發生了什麼；目前這是本次 UI session 的狀態提示，正式跨 session 履歷會等後續 profile / event log 收斂。

如果結果顯示 `待 Adapter` 或 `已加入 / 待辦`，右側 Crawler Passport 可以直接按 `開本次 Adapter 待辦`。這會打開剛才那一次爬蟲資產 resolved plan 裡的待辦清單，方便接著查看來源 URL、required action 與 outcome，而不必先到全域選單重新找目前下載計畫的 Adapter queue。

Launcher 也會把這個短狀態寫進本機事件紀錄。只要對應的 resolved plan 檔案還在，重開 UI 後仍可在爬蟲資產分頁看到最近一次結果，並從 Crawler Passport 打開本次 Adapter 待辦。

系統會把計畫草稿寫到：

```text
state/crawler_asset_plans/{asset_id}.original.json
state/crawler_asset_plans/{asset_id}.resolved.json
```

這條路徑的目的，是讓使用者先用「資料入口 -> 定義界域 -> 下載器」的心流操作；後續 Qt 介面也應呼叫同一個 service，而不是重寫另一套下載規則。
