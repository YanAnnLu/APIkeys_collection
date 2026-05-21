---
name: apikeys-collection-launcher
description: Use for developer-level work on the APIkeys_collection repository, a Steam-like data asset launcher. Trigger when modifying source code, tests, docs, Tk UI, provider catalog, discovery/crawler tools, adapter resolvers, download/import plans, manifests, install registry, SQL/data-store assets, provenance, curation, cross-platform handoff, or local database integration. For operating the launcher without code changes, use the client/user skill instead.
---

# APIkeys Collection Launcher

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

10. After pushing, verify GitHub Actions rather than assuming push success means CI success:

```bash
gh run list --repo YanAnnLu/APIkeys_collection --limit 5
gh run watch RUN_ID --repo YanAnnLu/APIkeys_collection --exit-status
```

The CI workflow should stay on Node 24-ready official actions. As of 2026-05-20, `.github/workflows/ci.yml` uses
`actions/checkout@v6` and `actions/setup-python@v6`; if GitHub reports a Node.js action deprecation warning, check
those `uses:` versions before changing Python test logic.

If another agent owns git for the session, do not commit, push, repair refs, remove lock files, or stage changes unless the user explicitly hands that responsibility back.

## Documentation Routing

Do not load every document into context by default. Use this route map after checking `docs/DOCS_INDEX.zh-TW.md`:

- Current handoff, user preferences, next step: `docs/AGENT_HANDOFF.zh-TW.md`.
- Progress and MVP status: `docs/PROJECT_GTD.md`.
- Long-term data asset platform concepts: `docs/DATA_ASSET_PLATFORM_CONCEPTS.zh-TW.md`.
- Product positioning: `docs/PRODUCT_POSITIONING.zh-TW.md`.
- Architecture or runtime layers: `docs/ARCHITECTURE.md`, then `docs/TECHNICAL_OVERVIEW.zh-TW.md`.
- Crawler, Discovery Tool, candidate, adapter review, dataset plan: `docs/DATASET_DISCOVERY_NOTES.zh-TW.md`. `docs/appendices/discovery.zh-TW.md` is only a retained redirect for older references.
- New data types or storage/viewer hints: `docs/DATASET_TYPE_MAP.zh-TW.md`.
- Portal intake, team source collection, Notion-like intake: `docs/DATABASE_PORTAL_INTAKE.zh-TW.md`.
- OpenSpec, Spectra, Qt Designer process: `docs/DEVELOPMENT_WORKFLOW_OPEN_SPEC.zh-TW.md` and `openspec/specs/development-workflow/spec.md`.
- Workspace cleanup, module split, path rules: `docs/WORKSPACE_LAYOUT.zh-TW.md`.
- User-facing UI behavior and developer CLI command index: `docs/USER_GUIDE.zh-TW.md`.
- Setup, env, cross-platform commands: `docs/SETUP.zh-TW.md`, `docs/TECH_STACK.md`.
- Git handoff details: `docs/GIT_HANDOFF.md`.
- Failure and repair context: `docs/appendices/failure_modes.zh-TW.md`.
- Renderer frontend, Taichi, Unreal: `docs/appendices/render_frontends.zh-TW.md`, `docs/appendices/unreal_bridge.zh-TW.md`, and `frontends/unreal/README.zh-TW.md`.
- OpenSpec workspace basics: `openspec/README.md`.

If a code change affects documentation, update the relevant zh-TW route. Do not add English-only docs without a Traditional Chinese version, summary, or clear entrypoint.

When the user asks to reread all docs, first scan all Markdown file names and headings, then load only the documents that affect the current task. Treat `docs/AGENT_HANDOFF.zh-TW.md`, `docs/PROJECT_GTD.md`, and `docs/DOCS_INDEX.zh-TW.md` as the live routing layer; treat the large concept document as roadmap context, not proof that a feature is in MVP.

## Documentation Refactor Workflow

Use this when the user asks to整理文件, 重構 `.md`, 收攏 docs, or make documentation easier to maintain.

1. Start with `git status --short --branch`; preserve unrelated user changes.
2. Read `docs/DOCS_INDEX.zh-TW.md`, `docs/AGENT_HANDOFF.zh-TW.md`, and `docs/PROJECT_GTD.md`.
3. Inventory Markdown files and headings with `rg`/PowerShell; do not load every large concept doc unless needed.
4. Search references in `.codex/skills/`, `.gemini/`, `.github/skills/`, `.github/prompts/`, `openspec/`, `scripts/`, and `README.md` before renaming, deleting, or merging.
5. Pick one document group per commit. Decide the canonical source of truth by role, not by old skill paths.
6. Keep old paths as redirect/summary files when references may exist; do not delete duplicated-looking `.md` files abruptly.
7. Update `docs/DOCS_INDEX.zh-TW.md`, `docs/AGENT_HANDOFF.zh-TW.md`, and `docs/PROJECT_GTD.md`; then update repo skills/prompts/scripts that reference moved docs.
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
- Crawler success is not just "no exception". Zero candidates, suspiciously low counts, duplicate-only output, missing evidence URLs, or unexpected payload shape should create warnings/errors.
- Keep concept work as docs/contracts unless it directly serves the MVP. Hadoop, K8S, P2P, mobile, full Google OAuth, multi-AI profiles, Qt migration, Render Studio, ML registry, and connector ecosystems are roadmap unless the current task explicitly scopes a bounded slice.
- Every significant code change should leave a beginner-friendly status: what changed, why it matters, what was tested, and roughly what MVP work remains.
- Keep UI JSON formats shared through core modules such as `api_launcher/plans.py`.
- Keep the default user-facing Tk UI in Traditional Chinese. When adding or touching visible UI text, prefer `ApiCollectionUi.tr("繁中", "English")` so `Settings > Interface language` can keep working.
- UI integration/login/API key/data-store entries belong under the top `整合` menu. Do not scatter new account or database settings buttons into the drawer or toolbar.
- AI description MVP uses explicit AI profile selection and saved local API keys under ignored `state/private/`. Startup must not open Google OAuth, browser sign-in, QR/device-code windows, or a system plist/config editor. Full Google OAuth/QR sign-in is a mid-term product feature that needs an official OAuth app or broker.
- Tk is an MVP control panel. PySide6/Qt is a mid-term route; do not rewrite UI before backend MVP is stable.
- Be careful with cross-platform local paths. Windows paths such as `K:\...` in ignored local config must not become blocking macOS startup errors; choose `*_by_platform` first and ignore/warn on foreign generic paths before `pathlib.Path` resolves them.
- CloudMounter has previously damaged Git metadata (`index` renamed to `index 1`, refs renamed to `main 1`, stale lock files). Diagnose Git metadata non-destructively before any restore/reset.
- Treat every `.md` as intentional handoff context. Future English docs need a Traditional Chinese version, summary, or clear Chinese entrypoint.
- Reuse `api_launcher.library_actions` for install/update/repair/open/render/uninstall decisions. For agent-readable output, call the CLI instead of rebuilding policy:

```bash
python APIkeys_collection.py --show-library-actions PROVIDER_ID --library-actions-json
```

- Register local installs through `provider_installations.install_id`; do not infer ownership from names alone.
- Register SQL/file assets in `provider_installation_assets` with `asset_role`, `source_format`, `source_uri`, and `schema_fingerprint`. Use `register_provider_database_asset` for whole databases and `register_provider_table_asset` for individual tables.
- Distinguish official source data from curated, derived, analysis, and cache assets.
- Do not execute `DROP DATABASE`, delete files, or remove tables until an adapter verifies the target and ownership.
- Existing table imports are conservative: plan-driven reruns should skip existing target tables by default; replace requires explicit `--import-replace-table`.
- API data still needs curation. Use `api_launcher/importers/curation.py` patterns for field mapping, type casting, required checks, and deduplication.
- For short-lived SQLite probes/tests, use `contextlib.closing(sqlite3.connect(...))`. Python's sqlite connection context manager does not close the connection, and Windows CI can fail with `WinError 32` when temp SQLite files remain locked.

## Repair Workflow

- Inspect file health with `python APIkeys_collection.py --verify-downloads --manifest-health --list-manifests`.
- Use Tk `Tools > Repair / verify manifests` for human repair work. Rows with missing/size/checksum problems and a manifest-recorded HTTP(S) `source_url` can be safely requeued through staging with `Requeue selected`.
- Do not invent a repair action for `manifest_error` or manifests without `source_url`; those require manual inspection or adapter-specific recovery.

## Data Store Self-check

- Use `python APIkeys_collection.py --test-data-store PROFILE_ID` to test one configured data-store profile, or `--test-data-store all` for every profile.
- Use `python APIkeys_collection.py --self-check-databases` to verify managed database/table assets recorded in the install registry.
- Use `python APIkeys_collection.py --self-check-databases-json` when another tool or agent needs a pure JSON issue list with stable repair suggestion IDs.
- Tk `工具 > 修復 / 驗證資產` shows database issues in a dedicated tab using `database_self_check_issues()`; keep it diagnostic until an adapter can prove asset ownership.
- SQLite checks are read-only and should not create a missing database file.
- SQLite managed database assets with `schema_fingerprint` are checked for database-level table/column drift and will be marked `error` when the actual fingerprint changes.
- SQLite managed table assets use `source_uri` as the database path and `asset_name` as the table name; missing tables are marked `missing`, and table-level fingerprint drift is marked `error`.
- MySQL/PostgreSQL checks first report missing env vars or optional Python drivers; do not add driver packages to base/system environments without user approval.
- MySQL/PostgreSQL connection probes can use `information_schema` helpers for table counts, table existence, column signatures, and schema fingerprints when drivers/env vars are available. SQL table asset database ownership comes from `install_location`; PostgreSQL table assets may use `schema.table` in `asset_name`.
- Database self-check repair suggestions are diagnostic only. They may say to configure env vars, install an optional driver in the project env, restore/reimport a table/database, review schema drift, or fix a profile mapping; do not execute destructive SQL from a suggestion alone.

## References

- Read `references/pipeline.md` when changing architecture, adapters, or the package map.
