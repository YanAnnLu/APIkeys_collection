# APIkeys Collection GTD

Last updated: 2026-05-17

| Area | Status | Current progress | Next step |
| --- | --- | --- | --- |
| Provider catalog | MVP | Built-in provider list, manual add/edit, categories, metadata fields, source discovery seeds, duplicate-aware provider model. | Improve provider-source separation so the same dataset can have multiple resource sites. |
| Steam-like UI | In progress | Responsive Tk UI, category sidebar, source table, right detail drawer, star/pin, double-click to add to plan. | Add right-click context menu and simplify crowded toolbar actions. |
| Download plan/cart | MVP | Download Plan panel, add/remove/clear/export plan JSON, double-click source row to add, plan schema declares nonblocking pause/resume policy. | Turn plan items into executable download jobs with adapters. |
| Download engine | Skeleton | Nonblocking worker queue with progress snapshots, pause, resume, cancel, tests, and pluggable transfer tool profiles. | Add real HTTP/API/database adapters with ranged resume support and retry policy. |
| Database tool interface | MVP | Local integration config, active database client selection, UI settings dialog, open/test configured client. | Add custom profile creation/editing directly in UI instead of editing JSON. |
| Install registry/uninstall | Skeleton | Install IDs, fingerprints, asset roles, provenance metadata, safe uninstall planning. | Implement SQL-backed install verification and guarded database deletion flow. |
| SQL/database self-check | Planned | Concept defined: detect manually deleted, pre-existing, imported, or drifted databases. | Build DB connector abstraction for MySQL/PostgreSQL/SQLite introspection. |
| Data cleaning pipeline | Planned | Need acknowledged for API/CSV/JSON normalization before import. | Define dataset adapter contract with validation and cleaning stages. |
| Provider discovery/crawling | MVP | Discovery seed config and CLI can collect candidate metadata from source sites without scraping secrets. | Add UI search/import flow for discovered provider candidates. |
| AI summary | MVP | Local Ollama and optional Gemini profile support can generate provider descriptions. | Add per-provider prompt controls and cache generated summaries. |
| Taichi renderer bridge | Skeleton | Renderer contracts, GEBCO/HYG dataset IDs, copied renderer under `renderers/`, renderer requirements documented. | Build adapter that maps installed dataset IDs to renderer-ready file paths. |
| Cross-platform setup | MVP | Git/GitHub, Docker, PowerShell runner, example/local config split, UTF-8/LF rules, startup environment checks. | Add CI workflow and surface startup checks in the UI. |
| Documentation | In progress | `TECH_STACK.md`, renderer contract docs, this GTD tracker. | Keep architecture diagrams and feature status current after each milestone. |
