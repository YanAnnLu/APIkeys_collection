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
