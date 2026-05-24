# RRKAL 中午展示操作稿

## 展示定位
這是一個「穩定展示模式」，用來面向組員展示目前已經可操作的核心閉環。展示模式不是一次性假功能；它會回到正式產品路線，之後只需要把顆粒度補細。

## 展示前準備
1. 在 Windows 檔案總管或 PowerShell 中執行 `scripts\run_showcase_ui.cmd`。
2. 等 Tk 視窗顯示 `RuRuKa Asset Launcher`。
3. 展示過程中不要改程式碼，也不要要求觀眾執行 CLI。

## 展示流程 A：可控小樣本下載到本機資料夾
1. 打開 GUI 上方 `工具`。
2. 點選 `展示模式：下載資料到本機資料夾`。
3. 資料夾選擇器預設會指向系統 Downloads；也可以選 K 槽或其他雲端同步資料夾，但雲端資料夾可能比較慢。
4. 輸入樣本筆數。建議現場用 `10` 或 `100`；數字越大下載與匯入越久。
5. 若公開 Socrata 來源逾時，GUI 會明確顯示切換到備援公開 CSV；這仍然是真下載、真 manifest、真 SQLite 匯入，不是假成功。
6. 等待完成彈窗。完成後展示輸出路徑：
   - `RuRuKa Asset Launcher Showcase\downloads\...`：下載 payload 與 manifest。
   - `RuRuKa Asset Launcher Showcase\curated_showcase.db`：展示用 SQLite 資料庫。
   - `showcase_download_summary.json`：機器可讀摘要。

## 展示流程 B：大型 CSV 續傳能力
1. 打開 `工具`。
2. 點選 `展示模式：大型 CSV 續傳下載`。
3. 選擇下載資料夾，預設仍是 Downloads。
4. 下方下載工作面板會出現大型 CSV 工作。
5. 現場可以按暫停，再按繼續，展示 `.part` 續傳能力。
6. 這條路徑只把完整 CSV 下載到本機資料夾，不自動寫 SQL；SQL/MySQL/PostgreSQL 對接在展示中先短路。

## 展示流程 C：Seed 覆蓋報告
1. 打開 `工具`。
2. 點選 `展示模式：產生 seed 覆蓋報告`。
3. 展示 `state/showcase/dataset_seed_coverage.md`，說明目前哪些入口有完整 seed 嘗試路徑，哪些仍是採樣或待 adapter review。

## 現場說法
- 穩定部分可以展示：GUI、小樣本真下載、manifest、SQLite `.db`、大型 CSV pause/resume、seed 覆蓋報告。
- 不穩定部分仍在開發：全來源無界爬取、所有資料庫完整 adapter、自動 SQL/MySQL/PostgreSQL 對接。
- 展示模式不是分支外產品；它是正式產品的簡化入口，後續會併回 dashboard / library actions。

## 若現場卡住
- 網路慢：把樣本筆數改成 5 或 10。
- 雲端碟慢：仍可選雲端資料夾，但建議先用本機 Downloads 展示成功閉環。
- GUI 沒浮出：重新執行 `scripts\run_showcase_ui.cmd`。
