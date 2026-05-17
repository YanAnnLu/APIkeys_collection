---
name: apikeys-collection-launcher
description: Use when working on the APIkeys_collection repository, a Steam-like big-data/API/database source launcher. Trigger for tasks involving the Tk UI, provider catalog, download-plan cart, dataset adapters, install/uninstall registry, SQL assets, provenance, curation, cross-platform Git/Docker handoff, or safe local database integration.
---

# APIkeys Collection Launcher

## Workflow

1. Start by checking `git status --short --branch`; never overwrite user changes.
2. Read `docs/AGENT_HANDOFF.zh-TW.md`, `docs/PROJECT_GTD.md`, and `docs/PROJECT_STATE.md` before architectural changes.
3. Read `docs/TECH_STACK.md` and `docs/GIT_HANDOFF.md` before changing dependencies, Docker, Git, or renderer code.
4. If there are uncommitted or surprising large changes, preserve them first with a patch or ignored recovery copy before interpreting them. Do not restore, delete, or overwrite such files just because they differ from the docs.
5. Keep the launcher model clear:
   `Provider catalog -> Download Plan cart -> Dataset adapter -> Import/curation -> Install registry -> Local assets`.
6. Keep destructive operations disabled unless an adapter can prove ownership by `install_id` and asset registry metadata.
7. Run tests before commit:

```powershell
py -m unittest discover -s tests
$env:PYTHONDONTWRITEBYTECODE='1'; py -m py_compile APIkeys_collection.py APIkeys_collection_ui.py api_launcher\core.py api_launcher\db.py api_launcher\models.py api_launcher\repository.py
```

8. After pushing, verify GitHub Actions rather than assuming push success means CI success:

```bash
gh run list --repo YanAnnLu/APIkeys_collection --limit 5
gh run watch RUN_ID --repo YanAnnLu/APIkeys_collection --exit-status
```

## Design Rules

- Treat `APIkeys_collection.py` as a compatibility wrapper; put new logic in `api_launcher/`.
- Keep UI JSON formats shared through core modules such as `api_launcher/plans.py`.
- Keep the default user-facing Tk UI in Traditional Chinese. When adding or touching visible UI text, prefer `ApiCollectionUi.tr("繁中", "English")` so `Settings > Interface language` can keep working.
- Reuse `api_launcher.library_actions` for install/update/repair/open/render/uninstall decisions. For agent-readable output, call the CLI instead of rebuilding policy:

```bash
python APIkeys_collection.py --show-library-actions PROVIDER_ID --library-actions-json
```

- Register local installs through `provider_installations.install_id`; do not infer ownership from names alone.
- Register SQL/file assets in `provider_installation_assets` with `asset_role`, `source_format`, `source_uri`, and `schema_fingerprint`. Use `register_provider_database_asset` for whole databases and `register_provider_table_asset` for individual tables.
- Distinguish official source data from curated, derived, analysis, and cache assets.
- Do not execute `DROP DATABASE`, delete files, or remove tables until an adapter verifies the target and ownership.
- API data still needs curation. Use `api_launcher/curation.py` patterns for field mapping, type casting, required checks, and deduplication.
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

- Read `references/pipeline.md` when changing the architecture or adding adapters.
