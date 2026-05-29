# GitHub 外部專案上下文

最後更新：2026-05-29

這份文件記錄 RRKAL 相關 GitHub 專案的 read-only 盤點結果。它不是依賴清單，也不是要求主寫 agent 去修改其他 repo。用途是讓 RRKAL 接手者知道哪些外部專案有可借鑑的工程節奏、UI/renderer 概念或治理模式。

## 邊界

- RRKAL 目前 recovery lane 的 canonical 工作區是 `L:\RRKAL_project`；舊 `K:\APIkeys_collection` 只作唯讀參考。
- 其他 GitHub repo 只作 read-only 參考；除非使用者明確要求，不要 clone、修改、commit 或 push 其他專案。
- `K:\CODE_KM` 在 RRKAL 任務中只作 read-only 參考，不寫入。
- 可借鑑的是 contract、workflow、smoke 節奏與概念，不直接搬產品碼。

## 2026-05-29 盤點摘要

| Repo | 最新觀察 | 對 RRKAL 的參考價值 |
| --- | --- | --- |
| `RRKAL_displaytools` | 2026-05-29 持續推進 renderer / UI contract；最新 commit `08a6eab`：`Acknowledge boundary highlight renderer input`；最近 smoke runs 皆 success。 | 可借鑑 display contract、renderer input acknowledgement、locked layer sync 與 smoke-first 節奏。不要直接把 displaytools 的 renderer 假設寫進 RRKAL 後端。 |
| `rrkal-renderer` | 最新 commit `a1351c3`：`feat: allow disabling auto-open preview in photo sample runner`。 | 可借鑑 preview runtime 開關與展示流程的防干擾設計。RRKAL 仍應先維持 renderer bridge 為 `contract_only` / planned，避免假裝已完成實體 renderer pipeline。 |
| `rrkal-visual-compressor` | 最新 commit `03d7232`：`Add one-command MVP pipeline`。 | 可借鑑 one-command pipeline / smoke closure 的操作形態，對 RRKAL 的 `pre_push_smoke`、MVP readiness 與 future visual compression bridge 有價值。 |
| `video-downloader` | 最新 commit `42a34d9`：AVIS 工作站加入 BITC 與來源檔名浮水印，並記錄 8 個單元測試通過。 | 可借鑑使用者可見的「來源證據浮水印 / provenance surfaced in output」概念。RRKAL 可映射到 manifest、source_url、license/provenance 與 UI display payload。 |
| `CODE_KM` | 最新 commit `bc78f85`：`Record next action checkpoint`；最近 CI runs success。 | 可借鑑 governed ingestion workflow、status gates、rights/provenance、next-action checkpoint。RRKAL 不寫 CODE_KM，只把治理概念抽回 docs / pipeline state。 |
| `Web-UI-Templates` | 最新 commit `815d9f4`：`Create Web UI Templates gallery`。 | 可當 Web Preview / future Qt/QSS 的視覺語彙參考。正式 RRKAL 文案與流程仍必須用資料資產語彙重寫。 |
| `rrkal-visual-editor` | 最新 commit `9b185a0`：`Initial visual editor scaffold`。 | 可作中長期 visual asset editor / renderer ecosystem 參考；不列入當前 MVP closure。 |

## 對 RRKAL 的工作流結論

1. `RRKAL_displaytools` 與 `rrkal-visual-compressor` 都支持「小閉環 + smoke + CI」節奏；RRKAL 應繼續維持每個 bounded slice 有測試、pre-push smoke、CI watch 與 docs checkpoint。
2. Display / renderer 類 repo 的進度提醒 RRKAL：未完成 renderer bridge 必須在成熟度矩陣和 UI payload 顯示 `🚧` / `contract_only` / `planned`，避免被使用者誤認為已交付。
3. CODE_KM 的 governed workflow 支持 RRKAL 的 docs drift guard、rights/provenance gate、structured next_action 與 status gate 設計。
4. 其他 repo 的成果只作概念樣本；RRKAL 的產品主線仍是 `seed -> crawler -> candidate -> plan -> download -> import -> UI`。
