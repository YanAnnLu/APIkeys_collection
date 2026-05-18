# 使用者操作指南

最後更新：2026-05-17

這份文件寫給第一次打開 launcher 的人。它用操作角度說明目前 UI 可以做什麼，以及哪些功能還是骨架。

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

若要先確認後端狀態：

```bash
python APIkeys_collection.py --init-db --seed --manifest-health --summary
python -m unittest discover -s tests
```

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

Tk UI 目前仍可用來完成 MVP 閉環，但它在彈窗比例、複雜設定頁與桌面常駐能力上已接近上限。中期路線已記錄為 PySide6 / Qt：等後端 MVP 穩定後，再把 UI 遷移成 Qt 的主視窗、設定中心、splitter/dock、系統匣 / macOS menu bar shell。現在不展開重寫，先把功能閉環做完。

## 開發者 CLI

`工具 > 開發者 CLI` 會打開一個簡單命令面板，工作目錄固定在專案根目錄。它適合快速跑：

```bash
python APIkeys_collection.py --help
python -m unittest discover -s tests
```

它不是完整終端機，也不適合長時間互動程式；比較像 UI 裡的單次命令快捷入口。

## 資料集候選審核

`資料庫 > 發現資料集候選` 會根據目前設定的 crawler sources 並行抓取資料集目錄。它只抓 metadata，不下載大型資料檔。若你先在左側勾選幾個資料源，UI 會只爬那些資料源；若沒有勾選，會爬所有已設定 crawler 的資料源。

發現完成後，UI 會顯示錯誤與警告。這裡的警告不是程式崩潰，而是 crawler 審核覺得「看起來有跑完，但結果不夠可信」，例如某個來源回傳 0 筆候選、低於最低預期筆數、只抓到已存在的重複候選，或候選 metadata 缺少來源/evidence。看到警告時，應先檢查該供應商頁面、搜尋詞或解析器，而不是直接假設沒有資料。

`資料庫 > 審核資料集候選` 會打開 crawler 找到的資料集候選清單。這裡只審核 metadata，不會下載大檔，也不會改動資料本體。

你可以先看候選的提供商、資料類型、格式、來源網址與 crawler 摘要，再選擇：

- `標記可用`：代表這個候選值得後續做下載/匯入。
- `加入下載計畫`：把候選資料集的特定版本加入目前下載計畫，並把候選狀態標成 `planned`。同一個資料商底下可以加入多個資料集/版本，不會再互相覆蓋。Launcher 會先判斷候選版本是不是直接檔案 URL；只有 direct download 才會送進下載器，入口頁/API selector 會保持需要 adapter 審核，避免把 HTML 頁面誤當資料檔下載。
- `拒絕候選`：代表暫時不適合 MVP 或來源不清楚。

CLI 也能把審核過的候選輸出成下載/匯入計畫：

```bash
python3 APIkeys_collection.py --export-candidate-plan state/candidate_plan.json --candidate-plan-status approved
```

這份 plan 會標出哪些候選可以直接下載、哪些需要 adapter review，以及下載後是否能用目前 CSV/JSON -> SQLite 的 MVP 匯入器處理。UI 下方的下載計畫現在也是同一個概念：每一列是「一個計畫項目」，可能是整個資料商，也可能是某個資料集版本。

若 plan 裡的項目已標示可匯入，可以在執行下載計畫時加上：

```bash
python3 APIkeys_collection.py --run-download-plan state/candidate_plan.json --import-supported-plan-results --import-sqlite-db state/curated_imports.sqlite
```

這會先下載 direct entries、驗證 manifest，然後只把支援的 CSV/JSON 類結果匯入 SQLite；不支援的格式會跳過，不會硬塞進資料庫。

在 UI 裡也有同樣的引導動作：先把資料集版本加入下方下載計畫並按 `開始`，下載完成後按下載計畫區的 `匯入`，或使用 `資料庫 > 匯入可支援下載結果`。Launcher 會先檢查 sidecar manifest，只有健康且 `import_plan` 標示支援的 CSV/JSON 項目會匯入 `state/curated_imports.sqlite`。下載計畫與下載工作表會顯示 `匯入狀態`，例如 `待下載/驗證`、`可匯入 -> table_name`、`已匯入 -> table_name`、`需 adapter` 或 `需解壓/adapter`。若目標 table 已存在，UI 會安全改名成 `table_name_2`、`table_name_3` 之類的新表，不會直接覆蓋既有資料。

如果看到 `需 adapter`，意思不是壞掉，而是這個入口目前還不是直接檔案，可能是 API、資料選擇器、登入後目錄頁，或下載後還需要解壓/轉換。Plan 裡會保存 `adapter_review` 線索，包含 adapter 名稱、來源 URL 與下一步要做的動作，方便後續開發 adapter 接手。

目前 ZIP/TAR 壓縮包已有第一個 MVP adapter：如果 plan 標示 `requires_unpack_or_adapter`，而壓縮包裡有 CSV/JSON/JSONL/GeoJSON，launcher 會抽出第一個支援檔、建立衍生 manifest，再接到 SQLite 匯入流程。它仍然是保守策略，不會嘗試猜測複雜壓縮包裡所有檔案的語意。

可以從 `資料庫 > Adapter 待辦` 或下載計畫上方 `更多 > Adapter 待辦` 打開目前下載計畫的 adapter 工作清單。CLI 也可以讀取已匯出的 plan：

```bash
python3 APIkeys_collection.py --adapter-review-plan state/candidate_plan.json
```

若候選來自 CKAN/Data.gov 這類「一個 dataset 底下有多個 resource」的平台，可以先嘗試解析 plan：

```bash
python3 APIkeys_collection.py --resolve-adapter-plan state/candidate_plan.json --write-resolved-adapter-plan state/candidate_plan.resolved.json
```

這一步會保守地掃描 plan 裡的 resource metadata，只把看起來是直接檔案 URL 的 CSV/JSON/ZIP 等項目轉成 direct download entry；HTML 頁、API selector、登入頁仍會留在 adapter review。白話說，它是把「資料目錄中的可下載檔案」挑出來，不是背景亂爬整站。

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
- SQL/資料庫修復目前以診斷與安全建議為主，不會自動 destructive drop。
- AI OAuth refresh token 與過期刷新還需要強化；目前 access token 過期時通常要重新掃 QR。
