---
name: apikeys-collection-launcher
description: Use for developer-level work on the APIkeys_collection repository, a Steam-like data asset launcher. Trigger when modifying source code, tests, docs, Tk UI, provider catalog, discovery/crawler tools, adapter resolvers, download/import plans, manifests, install registry, SQL/data-store assets, provenance, curation, cross-platform handoff, or local database integration. For operating the launcher without code changes, use the client/user skill instead.
---

# RuRuKa Asset Launcher

Product display name: **RuRuKa Asset Launcher**. Short name: **RRKAL**. Compatibility name: `APIkeys_collection`; keep repo, package, CLI wrappers, generated filenames, and historical references compatible unless a dedicated rename migration explicitly scopes them.

This is the project developer skill, the second layer in the skill plan:

```text
general dev safety -> APIkeys_collection developer -> APIkeys_collection client/user
```

Use this skill when changing the repository. If the task is only to use the launcher as a consumer, do not edit code; use the client workflow.

## Task Triage

Classify the request before editing:

- **Operate**: run the launcher/CLI, inspect UI, generate reports, run discovery, export/resolve/download/import plans. Prefer the client skill and do not change code.
- **Repair**: fix a broken MVP path or CI/test failure. Keep the patch narrow and verify the affected path.
- **Extend MVP**: add a bounded crawler/resolver/import/repair slice that advances `seed -> crawler -> candidate -> plan -> download -> import -> UI`.
- **Concept / roadmap**: record or route ideas such as Hadoop, K8S, Render Studio, ML registry, P2P, mobile, Qt, OAuth, or Notion sync. Do not implement a large stub unless it has a current MVP entrypoint.
- **Docs/skill only**: if the user says documentation is read-only, read and extract rules without editing docs. If the user asks to organize/refactor `.md` files, use the documentation refactor workflow below and update repo skill references after the docs are reorganized.

## Workflow

1. Start by checking `git status --short --branch`; never overwrite user changes.
2. Read `docs/AGENT_HANDOFF.zh-TW.md` and `docs/PROJECT_GTD.md` before making changes. These are the live handoff and progress sources.
3. Read `docs/DATA_ASSET_PLATFORM_CONCEPTS.zh-TW.md` when work touches long-term platform concepts such as data assets, Discovery Tools, lakehouse/K8S, renderer connectors, ML artifacts, Notion/TradingView connectors, or local-first product shape.
4. Read `docs/PROJECT_STATE.md`, `docs/TECH_STACK.md`, and `docs/GIT_HANDOFF.md` before architectural, dependency, Docker, Git, or renderer changes.
5. If there are uncommitted or surprising large changes, preserve them first with a patch or ignored recovery copy before interpreting them. Do not restore, delete, or overwrite such files just because they differ from the docs.
6. Keep the current MVP path clear:
   `seed -> crawler -> candidate -> plan -> download -> import -> UI`.
7. Keep destructive operations disabled unless an adapter can prove ownership by `install_id` and asset registry metadata.
8. For medium/risky work across modules, write or update an OpenSpec change first. Small fixes can stay lightweight, but must update GTD/handoff/docs when behavior changes.
   Treat OpenSpec as the durable project habit/specification memory, and this skill as the execution-time routing layer that consumes those rules. Recurring development habits, acceptance criteria, checkpoint rules, UI process boundaries, and cross-agent workflow contracts should usually become OpenSpec requirements/changes/tasks before being compressed into skill reminders. If adapting this workflow to another repository, copy the governance shape first (GTD, handoff, development log, docs index, OpenSpec workspace, project skill, smoke checks, checkpoint reporting) and remove APIkeys_collection-specific crawler/provider/database/renderer rules. Spectra/OpenSpec automation may be used proactively for administrative task movement, commit-message drafting, spec cleanup, and GTD/handoff synchronization under delegated authority. Spectra is a visual workbench for OpenSpec artifacts, not only a Qt migration tool. Treat these steps as agent-executable workflow work; substantive checkpoints still need test/CI evidence so future agents can trace what changed and why.
9. Run tests before commit. On macOS use the project env; on Windows avoid CloudMounter pycache issues with `-B` or `PYTHONDONTWRITEBYTECODE=1`:

```bash
PYTHONPYCACHEPREFIX=/tmp/apikeys_collection_pycache conda run -n metal_trade_312 python -m unittest discover -s tests
PYTHONPYCACHEPREFIX=/tmp/apikeys_collection_pycache conda run -n metal_trade_312 python -m py_compile APIkeys_collection.py APIkeys_collection_ui.py frontends/tk/launcher_ui.py api_launcher/core.py
```

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -B -m unittest discover -s tests
.\.venv\Scripts\python.exe -B -m py_compile APIkeys_collection.py APIkeys_collection_ui.py frontends\tk\launcher_ui.py api_launcher\core.py
```

10. Before pushing on Windows, prefer the local pre-push smoke when time allows. It checks working tree, staged diff, and pending-push `upstream..HEAD` whitespace, then runs core `py_compile`, full unittest discovery, `--summary`, and the offline MVP demo smoke with temp pycache:

```powershell
.\scripts\pre_push_smoke.cmd
```

For lower-token agent sessions, use the brief wrapper first:

```powershell
.\scripts\pre_push_smoke_brief.cmd
```

It writes the full log to `state/logs/pre_push_smoke_*.log` and prints only key pass/fail, traceback, unittest, and MVP smoke lines. External summarizers such as `distill` are optional post-processors for saved logs or selected tails only; do not use them for raw JSON, SQL, secrets/env/credential output, destructive-action review, or as a replacement for CI/test evidence. On Windows call `distill.cmd`, and use it only when `distill.cmd --version` succeeds. As of 2026-05-22, `@samuelfaj/distill@1.5.2` is blocked on Windows because npm does not publish the expected `@samuelfaj/distill-win32-x64` package.

To install the same check as a local-only Git hook for this clone, run `.\scripts\install_pre_push_hook.cmd`. Hooks live under `.git/hooks/` and are not committed; they reduce failed CI queue time. Still watch GitHub Actions after push so each checkpoint has a remote CI record.

11. After pushing, verify GitHub Actions rather than assuming push success means CI success:

```bash
gh run list --repo kagamihara-rururka/APIkeys_collection --limit 5
gh run watch RUN_ID --repo kagamihara-rururka/APIkeys_collection --exit-status
```

The CI workflow should stay on Node 24-ready official actions. As of 2026-05-20, `.github/workflows/ci.yml` uses
`actions/checkout@v6` and `actions/setup-python@v6`; if GitHub reports a Node.js action deprecation warning, check
those `uses:` versions before changing Python test logic.
As of 2026-05-22, the Windows CI matrix uses `windows-2025-vs2026` explicitly so the project tests GitHub's upcoming
Windows Server 2025 / Visual Studio 2026 image instead of relying on an implicit `windows-latest` migration.

If another agent owns git for the session, do not commit, push, repair refs, remove lock files, or stage changes unless the user explicitly hands that responsibility back.

## Documentation Routing

Do not load every document into context by default. Use this route map after checking `docs/DOCS_INDEX.zh-TW.md`:

- Current handoff, user preferences, next step: `docs/AGENT_HANDOFF.zh-TW.md`.
- Progress and MVP status: `docs/PROJECT_GTD.md`.
- Pushed checkpoint history, verification, CI, and residual risk: `docs/DEVELOPMENT_LOG.zh-TW.md`.
- Long-term data asset platform concepts: `docs/DATA_ASSET_PLATFORM_CONCEPTS.zh-TW.md`.
- Product positioning: `docs/PRODUCT_POSITIONING.zh-TW.md`.
- Architecture or runtime layers: `docs/ARCHITECTURE.md`, then `docs/TECHNICAL_OVERVIEW.zh-TW.md`.
- Crawler, Discovery Tool, candidate, adapter review, dataset plan: `docs/DATASET_DISCOVERY_NOTES.zh-TW.md`. `docs/appendices/discovery.zh-TW.md` is only a retained redirect for older references.
- New data types or storage/viewer hints: `docs/DATASET_TYPE_MAP.zh-TW.md`.
- Portal intake, team source collection, Notion-like intake: `docs/DATABASE_PORTAL_INTAKE.zh-TW.md`.
- OpenSpec, Spectra, Qt Creator / Qt Designer process: `docs/DEVELOPMENT_WORKFLOW_OPEN_SPEC.zh-TW.md` and `openspec/specs/development-workflow/spec.md`.
- Workspace cleanup, module split, path rules: `docs/WORKSPACE_LAYOUT.zh-TW.md`.
- User-facing UI behavior and developer CLI command index: `docs/USER_GUIDE.zh-TW.md`.
- Setup, env, cross-platform commands: `docs/SETUP.zh-TW.md`, `docs/TECH_STACK.md`.
- Git handoff details: `docs/GIT_HANDOFF.md`.
- Failure and repair context: `docs/appendices/failure_modes.zh-TW.md`.
- Renderer frontend, Taichi, Unreal: `docs/appendices/render_frontends.zh-TW.md`, `docs/appendices/unreal_bridge.zh-TW.md`, and `frontends/unreal/README.zh-TW.md`.
- OpenSpec workspace basics: `openspec/README.md`.

If a code change affects documentation, update the relevant zh-TW route. Do not add English-only docs without a Traditional Chinese version, summary, or clear entrypoint.

When the user asks to reread all docs, first scan all Markdown file names and headings, then load only the documents that affect the current task. Treat `docs/AGENT_HANDOFF.zh-TW.md`, `docs/PROJECT_GTD.md`, and `docs/DOCS_INDEX.zh-TW.md` as the live routing layer; treat the large concept document as roadmap context, not proof that a feature is in MVP.

## Development Log Workflow

Use this when updating `docs/DEVELOPMENT_LOG.zh-TW.md`.

1. Prefer GitHub Actions push history over local `git log` when local Git history is damaged or incomplete:

```bash
gh run list --repo kagamihara-rururka/APIkeys_collection --limit 200 --json databaseId,headSha,displayTitle,event,status,conclusion,createdAt
```

2. Keep the log ledger-style, not only summarized. Group entries by Asia/Taipei date in reverse chronological order, newest date first. Within each date, list entries newest time first. Add a one-line daily main theme, then list every relevant push run.
3. Use a Markdown table for each date section with these columns:
   `時間 | 開發階段 | 標記 | SHA | Run | 原始標題 | 中文說明`.
4. Keep the original English push title for lookup, but every row must also include a coarse development-stage label in the `開發階段` column and a Traditional Chinese explanation in the `中文說明` column. Use phase labels such as `MVP Demo Closure`, `MVP Hardening`, `Database / Repair`, `Discovery / Crawler`, and `Docs / Workflow`.
5. Mark successful push runs as `**CHECKPOINT**`. Mark failed push runs as `**CI 失敗**` and keep them in the ledger so later agents can see the repair path.
6. A single user turn may contain multiple substantive checkpoint commits. Prefer grouping adjacent small slices under one MVP theme when it is safe, but keep each commit reviewable and CI-verifiable. Record every substantive feature, fix, workflow, or documentation checkpoint in the development log after it has been pushed and verified.
7. Avoid development-log recursion: do not add a new log row for a commit whose only purpose is updating `docs/DEVELOPMENT_LOG.zh-TW.md`. A log-sync commit may be pushed and verified, but it must not trigger another log-sync commit.
8. Add known risks when the history source is imperfect, such as missing local Git objects or a fallback to GitHub Actions as the source of truth.

## Documentation Refactor Workflow

Use this when the user asks to整理文件, 重構 `.md`, 收攏 docs, or make documentation easier to maintain.

1. Start with `git status --short --branch`; preserve unrelated user changes.
2. Read `docs/DOCS_INDEX.zh-TW.md`, `docs/AGENT_HANDOFF.zh-TW.md`, and `docs/PROJECT_GTD.md`.
3. Inventory Markdown files and headings with `rg`/PowerShell; do not load every large concept doc unless needed.
4. Search references in `.codex/skills/`, `.gemini/`, `.github/skills/`, `.github/prompts/`, `openspec/`, `scripts/`, and `README.md` before renaming, deleting, or merging.
5. Pick one document group per commit. Decide the canonical source of truth by role, not by old skill paths.
6. Keep old paths as redirect/summary files when references may exist; do not delete duplicated-looking `.md` files abruptly.
7. Update `docs/DOCS_INDEX.zh-TW.md`, `docs/AGENT_HANDOFF.zh-TW.md`, `docs/PROJECT_GTD.md`, and append `docs/DEVELOPMENT_LOG.zh-TW.md` for pushed checkpoints; then update repo skills/prompts/scripts that reference moved docs.
8. In Traditional Chinese docs, Mermaid node labels and edge labels should be Traditional Chinese. Keep exact file names, CLI flags, module paths, product names, and standards in their original spelling only when precision matters.
9. Verify with `git diff --check`; for docs-only changes, tests are optional unless examples, scripts, or generated docs behavior changed.

## MVP Acceptance Checklist

Before adding code, answer these in plain language:

```text
Which exact MVP step does this advance?
What CLI, UI, test, or documented flow will use it now?
What input proves it worked beyond "no exception"?
What stays in review instead of being guessed or silently downloaded?
What beginner-friendly status should be reported, including remaining MVP work?
```

For crawler/resolver work, "done" means at least one of these is true:

- A real configured source produces credible candidates with evidence URLs and warnings for suspiciously low/zero output.
- A bounded resolver turns an existing candidate/adapter-review item into a small safe plan entry.
- Ambiguous landing pages, login pages, unbounded APIs, oversized files, and unknown formats remain in adapter review with a clear reason.
- Tests cover the parser/normalizer/handoff shape, not only the happy CLI command.

For UI work, "done" means the visible text is Traditional Chinese by default, the action lives in the right menu/panel, and the control is connected to the backend path rather than being a decorative button.

## Design Rules

- Treat `APIkeys_collection.py` as a compatibility wrapper; put new logic in `api_launcher/`.
- Avoid over-engineering. Before adding implementation, answer: which MVP step does it serve, which CLI/UI/test/documented flow uses it now, and would removing it hurt the MVP?
- Keep crawler-first / discovery-tool-first. Do not hard-code representative datasets when a provider/source crawler or bounded adapter handoff is the right abstraction.
- Crawler success is not just "no exception". Zero candidates, suspiciously low counts, duplicate-only output, duplicate-heavy output, missing evidence URLs, or unexpected payload shape should create warnings/errors. Prefer machine-readable `warning_codes`, `next_action`, and top-level `audit_summary` for crawler audit output so UI/agents can route to query/parser repair, dedupe/id-mapping review, metadata mapping repair, or normal candidate review without parsing warning prose.
- Blocked downloads need guided repair. If a plan cannot submit direct downloads, report the exact blocked category and point the user/agent to adapter review, adapter-plan resolution, missing URL repair, or a new adapter rather than only saying `skipped`.
- Use `--run-download-plan-json` with `--run-download-plan` when an agent needs machine-readable pipeline status, stage, `next_action`, skip buckets, import counts, and errors instead of parsing human CLI lines. Completed runs also write a `download_plan_executed` structured event, and `--handoff-report` surfaces the latest input plan, stage, counts, skip summary, and next action.
- Use `--handoff-report-json` when a heartbeat or external agent needs the same handoff snapshot as JSON stdout instead of parsing the Markdown `--handoff-report` file. The snapshot includes `mvp_readiness`; treat `ready_for_mvp_demo` as the canonical MVP Demo closure gate, and do not count unrelated post-MVP GTD hardening as a blocker for that demo closure.
- Adapter review payloads include `outcome_bucket` and summary `by_outcome`. Use `--adapter-review-json` for stdout or `--write-adapter-review-json PATH` for file handoff, then group follow-up work by machine-readable buckets such as `source_resolution_required` and `downloaded_payload_transform`; do not infer adapter next steps only from UI labels or free-text reasons. Use `--resolve-adapter-plan-json` with `--resolve-adapter-plan` when an agent needs a machine-readable resolver summary instead of parsing human stdout.
- Keep concept work as docs/contracts unless it directly serves the MVP. Hadoop, K8S, P2P, mobile, full Google OAuth, multi-AI profiles, Qt migration, Render Studio, ML registry, and connector ecosystems are roadmap unless the current task explicitly scopes a bounded slice.
- Concept ideation is useful but must be bounded. Offer product/architecture opinions when the user asks, when a design choice is underspecified, or when a concept affects MVP safety; then collapse the idea into at most one concrete artifact: a short decision, a docs/skill rule, a GTD/backlog item, or an OpenSpec proposal for medium/risky work. Do not start implementation from ideation unless it directly advances the current MVP loop, and after a concept pass return to the active checkpoint instead of continuing to brainstorm.
- If adding financial providers, include `Yahoo Finance via yfinance` only as an optional unofficial personal/research adapter candidate. Do not make yfinance a hard dependency, do not treat Yahoo data as commercial redistribution-safe, and use fixtures rather than live Yahoo calls in CI. Use `--write-yfinance-demo-plan` to prove the OHLCV time-series `download -> manifest -> SQLite import` loop without live Yahoo access. Live yfinance is allowed only through explicit opt-in `--write-yfinance-live-plan ... --yfinance-acknowledge-unofficial`; it writes local CSV plus a file-backed plan and may record `--yfinance-query-window` only as chart/storage metadata, `--yfinance-storage-target` only as storage-target planning metadata, and `--yfinance-retention-days` only as local cache-governance metadata. `--write-yfinance-storage-review ... --yfinance-storage-review-plan ...` may create a review JSON and optional dry-run SQL/Parquet-DuckDB sketch from an existing yfinance plan, and `--write-yfinance-storage-handoff ... --yfinance-storage-handoff-review ...` may convert that review into a human/DBA Markdown checklist, but both must stay review-only: no database connection, no table creation, no import, no background execution. Query-window, storage-target, retention, storage-review, and handoff metadata must not become automatic deletion, background refresh, crawler, CI behavior, or direct database mutation. Tk Tools menu entries may create the offline demo plan or guarded live plan, and may create a storage review dry-run plus handoff Markdown from an existing plan; they must only add entries to the download plan or write review artifacts, and still require explicit user download/import or human/DBA review.
- Python/R/MATLAB/other-language package or toolbox-backed entries should be stored as metadata on the canonical backing source first, not as separate providers or sources. Represent them as explicit relationships: backing source, language/runtime, package/tool name, plus official status, docs URL, credential mode, and terms risk. Package ecosystems such as PyPI, CRAN, Bioconductor, MATLAB Add-On, Julia registries, npm, Maven, NuGet, Go modules, and crates.io may provide discovery evidence; merge wrappers that point to the same database/API by union into fields such as `language_clients` or `access_surfaces`. Create a new source candidate only when the backing database/API is unknown, distinct, or materially different in terms/licensing. Do not add a package as a hard dependency or background live crawler just because a wrapper exists.
- Public wrapper code does not imply public API keys. Direct adapter fetches are allowed only for keyless public endpoints with bounded terms/rate limits, for user-configured credentials from env/profile/private state, or for fixture/mock/dry-run paths. Never use example keys, commit credentials, or make CI/background live calls just because a package documents an API.
- Treat package/API adapters as format-simplification boundaries: their value is not just calling a library, but turning JSON/CSV/DataFrame/SDMX/OData/paged/archive outputs into manifests, checksums, schema/provenance metadata, importable SQLite/MySQL/lakehouse assets, and repairable registry records.
- For UI/product framing, prefer canonical data sources over language packages. Let users choose the source/database/API first; language packages, REST endpoints, CLI tools, and drivers are access surfaces recorded on the source passport and selected by the launcher based on credential, terms, format, and import target.
- For repeatable MVP smoke checks, prefer `--run-mvp-demo-smoke-json state/mvp_demo/flow.json` when an agent needs one command that writes the canonical MVP demo artifacts, runs the offline `download -> manifest -> SQLite import` loop, emits machine-readable `stage`/`succeeded`/`row_count` JSON, and leaves a handoff-visible `mvp_demo_smoke_completed` event. After the smoke, `--handoff-report` / `--handoff-report-json` should show `MVP Readiness` / `mvp_readiness` as `ready_for_mvp_demo` when stage is `download_import_completed`, succeeded is true, and row_count is greater than zero. Use `--write-mvp-demo-flow state/mvp_demo/flow.json` or Tk `工具 > 產生 MVP Demo Flow` when the user only needs artifacts or a UI-loaded offline plan. All paths call `api_launcher.mvp_demo`; do not duplicate demo business logic inside `launcher_ui.py`.
- For download/import orchestration, use `api_launcher.ingestion_pipeline.run_download_import_slice()` as the service boundary. For Tk/UI import of already-downloaded sidecar manifests, use `run_existing_download_import_slice()`. Do not make new UI panels, subcommands, or agents call `run_download_plan_payload()` directly unless they are intentionally testing the low-level runner.
- Every significant code change should leave a beginner-friendly status: what changed, why it matters, what was tested, and roughly what MVP work remains.
- Every non-trivial code change should also leave maintainer comments near the logic that would be hard for a human to infer quickly. In this repository, use a slightly higher comment density than usual because human maintainers may be early-career or unfamiliar with the codebase. Write maintainer comments in Traditional Chinese by default; keep exact identifiers, file paths, CLI flags, API names, standards, and product names in their original spelling when precision matters. Prioritize comments for function intent, orchestration, safety guards, schema or provenance invariants, adapter assumptions, external API quirks, cross-module ownership, and data transformations. Explain why and what boundary is being protected; do not add purely mechanical comments that only restate obvious assignments.
- Keep UI JSON formats shared through core modules such as `api_launcher/plans.py`.
- Keep the default user-facing Tk UI in Traditional Chinese. When adding or touching visible UI text, prefer `ApiCollectionUi.tr("繁中", "English")` so `Settings > Interface language` can keep working.
- UI integration/login/API key/data-store entries belong under the top `整合` menu. Do not scatter new account or database settings buttons into the drawer or toolbar.
- AI description MVP uses explicit AI profile selection and saved local API keys under ignored `state/private/`. Startup must not open Google OAuth, browser sign-in, QR/device-code windows, or a system plist/config editor. Full Google OAuth/QR sign-in is a mid-term product feature that needs an official OAuth app or broker.
- Tk is an MVP control panel. PySide6/Qt is a mid-term route; do not rewrite UI before backend MVP is stable. On Windows, run `scripts\check_ui_tooling.cmd` before assuming Qt Creator, PySide6, or a named Conda env exists. `metal_trade_312` is a macOS workstation env, not a cross-platform project requirement.
- Be careful with cross-platform local paths. Windows paths such as `K:\...` in ignored local config must not become blocking macOS startup errors; choose `*_by_platform` first and ignore/warn on foreign generic paths before `pathlib.Path` resolves them.
- CloudMounter has previously damaged Git metadata (`index` renamed to `index 1`, refs renamed to `main 1`, stale lock files). Diagnose Git metadata non-destructively before any restore/reset.
- Treat every `.md` as intentional handoff context. Future English docs need a Traditional Chinese version, summary, or clear Chinese entrypoint.
- `tem/` 是本機暫存資料夾，用來暫放外部 agent 產物、概念原型、截圖、logs 與待評估素材。它預設不進 Git；除非使用者明確要求把某個素材提升成正式文件或原始碼，否則不要 `git add`、commit 或 push `tem/` 內容。從 `tem/` 取用內容時，應把通過評估的重點收斂到 canonical docs/source，不要讓正式流程依賴 `tem/` 路徑。
- Reuse `api_launcher.library_actions` for install/update/repair/open/render/uninstall decisions. For agent-readable output, call the CLI instead of rebuilding policy:

```bash
python APIkeys_collection.py --show-library-actions PROVIDER_ID --library-actions-json
```

The action payload includes `status_badge` for short UI/agent routing states such as `ready_to_plan`, `repair_requeue_ready`, and `guarded_uninstall_ready`. Treat badges as summaries only; execution still depends on `enabled`, `risk`, ownership metadata, and guarded CLI parameters.

- Register local installs through `provider_installations.install_id`; do not infer ownership from names alone.
- Register SQL/file assets in `provider_installation_assets` with `asset_role`, `source_format`, `source_uri`, and `schema_fingerprint`. Use `register_provider_database_asset` for whole databases and `register_provider_table_asset` for individual tables.
- Distinguish official source data from curated, derived, analysis, and cache assets.
- Do not execute `DROP DATABASE`, delete files, or remove tables until an adapter verifies the target and ownership.
- Existing table imports are conservative: plan-driven reruns should skip existing target tables by default; replace requires explicit `--import-replace-table`.
- API data still needs curation. Use `api_launcher/importers/curation.py` patterns for field mapping, type casting, required checks, and deduplication.
- For short-lived SQLite probes/tests, use `contextlib.closing(sqlite3.connect(...))`. Python's sqlite connection context manager does not close the connection, and Windows CI can fail with `WinError 32` when temp SQLite files remain locked.

## Repair Workflow

- Inspect file health with `python APIkeys_collection.py --verify-downloads --manifest-health --list-manifests`.
- Use `python APIkeys_collection.py --verify-downloads-json` when an agent needs structured repair routing. `repair_suggestion` includes `outcome_bucket`, `next_action`, `adapter_id`, and `review_hint`; only `requeue_ready` with `can_requeue=true` should be treated as safe to queue automatically.
- Use Tk `Tools > Repair / verify manifests` for human repair work. Rows with missing/size/checksum problems and a manifest-recorded HTTP(S) `source_url` can be safely requeued through staging with `Requeue selected`.
- Do not invent a repair action for `manifest_error` or manifests without `source_url`; those require manual inspection or adapter-specific recovery.

## Data Store Self-check

- Use `python APIkeys_collection.py --test-data-store PROFILE_ID` to test one configured data-store profile, or `--test-data-store all` for every profile.
- Use `python APIkeys_collection.py --test-data-store PROFILE_ID --test-data-store-json` when an agent needs status/details/next_action instead of human text.
- Use `python APIkeys_collection.py --set-active-data-store-profile PROFILE_ID` to record the local active data-store profile in ignored local config. This records only the profile id, not credentials.
- Use `python APIkeys_collection.py --write-data-store-env-template state/data_store_env_templates/mysql.env.template --data-store-env-template-profile mysql_default` to write a local empty-value `.env` template before setting MySQL/PostgreSQL credentials. This helper must list env var names only; do not fill or commit secrets.
- Use `python APIkeys_collection.py --self-check-databases` to verify managed database/table assets recorded in the install registry.
- Use `python APIkeys_collection.py --self-check-databases-json` when another tool or agent needs a pure JSON issue list with stable repair suggestion IDs.
- Tk `工具 > 修復 / 驗證資產` shows database issues in a dedicated tab using `database_self_check_issues()`; it can edit registry profile/schema, stop tracking one asset, reimport safe missing SQLite tables, and write MySQL/PostgreSQL dry-run SQL. Keep any real SQL execution disabled until ownership and DBA review boundaries are explicit.
- SQLite checks are read-only and should not create a missing database file.
- SQLite managed database assets with `schema_fingerprint` are checked for database-level table/column drift and will be marked `error` when the actual fingerprint changes.
- SQLite managed table assets use `source_uri` as the database path and `asset_name` as the table name; missing tables are marked `missing`, and table-level fingerprint drift is marked `error`.
- MySQL/PostgreSQL checks first report missing env vars or optional Python drivers; do not add driver packages to base/system environments without user approval.
- MySQL/PostgreSQL connection probes can use `information_schema` helpers for table counts, table existence, column signatures, and schema fingerprints when drivers/env vars are available. SQL table asset database ownership comes from `install_location`; PostgreSQL table assets may use `schema.table` in `asset_name`.
- For manifest-backed missing MySQL/PostgreSQL table assets, use Tk `產生 dry-run SQL` or `python APIkeys_collection.py --write-database-repair-sql ASSET_ID --database-repair-json` to write a reviewable dry-run SQL file under `state/database_repair/`. This action must not connect to or mutate the remote database, and it must not be treated as automatic repair.
- Database self-check repair suggestions are diagnostic only. They may say to configure env vars, install an optional driver in the project env, restore/reimport a table/database, review schema drift, or fix a profile mapping; do not execute destructive SQL from a suggestion alone.

## References

- Read `references/pipeline.md` when changing architecture, adapters, or the package map.
