# APIkeys Collection GTD

Last updated: 2026-05-17

## Product GTD

| Area | Status | Current Progress | Next Step |
| --- | --- | --- | --- |
| Product architecture | In progress | Architecture documented in `docs/ARCHITECTURE.md`; pipeline, runtime layers, and path resolver are explicit. | Keep architecture current as UI/download/database workflows are connected. |
| Folder hygiene | MVP | Docs, catalog/reference files, example config, and scripts moved into folders; resolver keeps legacy root files compatible. | Move remaining runtime files into ignored `state/` after compatibility checks. |
| Provider catalog | MVP | Built-in provider list, manual add/edit, categories, metadata fields, source discovery seeds, duplicate-aware provider model. | Improve provider-source separation so one dataset can have multiple resource sites. |
| Provider/source discovery | MVP | Discovery seed config and CLI collect candidate metadata from source sites without scraping secrets. Built-in discovery seeds expanded from 8 to 30 source sites across climate, ocean, biodiversity, statistics, maps, research metadata, and Taiwan open data. | Add UI search/import flow for discovered provider candidates and periodic seed review. |
| Dataset adapters | Skeleton | Adapter registry exists; HYG v3.8 star catalog and GEBCO 2025 elevation grid can be discovered into the dataset table from their providers. | Add NOAA/NASA and ERDDAP dataset adapters with download manifests. |
| Dataset freshness/versioning | Skeleton | Generic version option model exists; adapters can expose `available_versions`; UI right-click can add a provider with a specific dataset version to the download plan. GEBCO 2025 is marked compatibility-pinned while GEBCO 2026 requires review. | Persist multiple versions of the same dataset in one plan and add stale/compatibility-pinned UI badges. |
| Dataset transition/delta planning | Skeleton | Generic transition planner exists for install-new, same-version skip, upgrade, downgrade, partial forward/backward, compare-then-update, and keep-legacy-side-by-side decisions; adapter version metadata can declare update strategy and dedupe keys. | Implement provider manifests/checksums, row-level/table-level dedupe, rollback-safe installs, and incremental update adapters where providers support deltas. |
| Steam-like UI | In progress | Responsive Tk UI, category sidebar, source table, right detail drawer, star/pin, double-click to add to plan, basic download job controls. | Add right-click context menu, simplify toolbar, and expose environment checks. |
| Download plan/cart | MVP | Download Plan panel, add/remove/clear/export plan JSON, double-click source row to add, plan schema declares nonblocking download policy, Start/Pause/Resume/Cancel controls exist, source rows show Direct/Adapter/Docs eligibility. | Add provider-specific adapters for non-direct sources. |
| Download engine | MVP | Nonblocking worker queue, progress snapshots, pause/resume/cancel/retry, tests, pluggable transfer tools, HTTP(S) adapter with `.part` resume, configurable polite per-host pacing, 429/503 cooldown, UI job table, completion registry update. | Add provider-specific adapters and expose rate-limit settings in UI. |
| Download staging/manifests | Skeleton | HTTP downloads now stage payloads under `state/staging/`, promote atomically to final downloads, and write sidecar JSON manifests with size/checksum/version/source metadata. Legacy `.part` files are migrated into staging for resume. | Persist manifests in SQLite and use them for repair/update/dedupe decisions. |
| Download repair scanner | Skeleton | CLI `--verify-downloads` and `api_launcher/repair.py` can scan sidecar manifests and detect missing payloads, size mismatch, checksum mismatch, and manifest parse errors. | Add UI repair panel and automatic requeue suggestions. |
| External transfer tools | MVP | `python_internal`, `aria2c`, and `curl` profiles exist; commands are built as cross-platform argument lists. | Add runtime selection UI and optional `aria2c` install guidance. |
| Database client interface | MVP | Local integration config, active database client selection, UI settings dialog, open/test configured client. | Add custom profile creation/editing directly in UI instead of editing JSON. |
| SQL/database self-check | Planned | Requirement defined: detect manually deleted, pre-existing, imported, or drifted databases. | Build MySQL/PostgreSQL/SQLite introspection layer. |
| Install registry | Skeleton | Install IDs, fingerprints, asset roles, provenance metadata, managed/unmanaged states. | Connect real downloaded/imported assets to install records automatically. |
| Uninstall/delete database | Skeleton | Safe uninstall metadata exists; current flow marks registry assets removed, not destructive SQL. | Implement guarded SQL `DROP DATABASE` / file delete only for verified install IDs. |
| Data cleaning pipeline | Planned | Need acknowledged for API/CSV/JSON/manual SQL normalization. | Define adapter contract for raw -> curated validation, schema fingerprinting, and error reports. |
| Manual import support | Planned | Product requirement defined for CSV/JSON/manual SQL imports. | Add import wizard and provenance rules for user-provided files/tables. |
| AI summary | MVP | Local Ollama and optional Gemini profile support can generate provider descriptions. | Add per-provider prompt controls, cache generated summaries, and UI status. |
| Renderer bridge | Skeleton | Renderer contracts, GEBCO/HYG dataset IDs, copied `taichi_global_bathymetry.py`, renderer requirements documented; HYG and GEBCO discovery now use shared renderer contract IDs. | Map installed dataset IDs to renderer-ready file paths, test with real assets, and evaluate GEBCO 2026 migration. |
| AI-ready dataset metadata | Planned | Product requirement defined: catalog entries should eventually state license, usage policy, training suitability, attribution, and redistribution limits. | Extend provider/dataset schema with license and AI training suitability fields before using downloaded data for local LLM workflows. |
| Taichi renderer health | Planned | Renderer copied into project but not refactored or performance-tested in this cycle. | Add smoke tests/config checks without forcing heavy renderer dependencies into launcher. |
| Cross-platform setup | MVP | Git/GitHub, Docker, PowerShell/bash runners, example/local config split, UTF-8/LF rules, startup environment checks. | Add CI workflow and macOS/Windows setup notes. |
| Error logs / observability | Skeleton | Structured JSONL event log and human-readable error log exist under `state/logs/`; UI and CLI start recording startup/download/crawl/AI/database failures. | Add UI log viewer, repair command, and agent-readable failure summaries. |
| Failure recovery | Planned | Failure-mode document exists for network, user actions, manual deletion, SQLite locks, version transitions, path changes, and provider URL drift. | Implement staging/promote, manifest verification, rollback-safe updates, and path repair workflow. |
| Agent skill packaging | Skeleton | Local `.codex/skills/apikeys-collection-launcher` draft exists. | Turn launcher operations into a documented agent skill interface. |
| Documentation | In progress | `docs/ARCHITECTURE.md`, `docs/TECH_STACK.md`, `docs/TECHNICAL_OVERVIEW.zh-TW.md`, `docs/DATASET_DISCOVERY_NOTES.zh-TW.md`, `docs/FAILURE_MODES.zh-TW.md`, renderer notes, GTD tracker, handoff docs exist. | Repair/normalize Chinese overview encoding and keep Chinese and English docs aligned as features move from skeleton to MVP. |

## Status Legend

| Status | Meaning |
| --- | --- |
| Planned | Requirement is known, but implementation has not started. |
| Skeleton | Core shape exists, but not enough for normal user workflow. |
| MVP | Works in a narrow tested path and can be built upon. |
| In progress | Partially usable, active design/implementation still changing. |
| Done | Stable enough that only maintenance is expected. |
