---
name: apikeys-collection-launcher
description: Use when working on the APIkeys_collection repository, a Steam-like big-data/API/database source launcher. Trigger for tasks involving the Tk UI, provider catalog, download-plan cart, dataset adapters, install/uninstall registry, SQL assets, provenance, curation, cross-platform Git/Docker handoff, or safe local database integration.
---

# APIkeys Collection Launcher

## Workflow

1. Start by checking `git status --short --branch`; never overwrite user changes.
2. Read `PROJECT_STATE.md` and `GIT_HANDOFF.md` before architectural changes.
3. Read `TECH_STACK.md` before changing dependencies, Docker, or renderer code.
4. If there are uncommitted or surprising large changes, preserve them first with a patch or ignored recovery copy before interpreting them. Do not restore, delete, or overwrite such files just because they differ from the docs.
5. Keep the launcher model clear:
   `Provider catalog -> Download Plan cart -> Dataset adapter -> Import/curation -> Install registry -> Local assets`.
6. Keep destructive operations disabled unless an adapter can prove ownership by `install_id` and asset registry metadata.
7. Run tests before commit:

```powershell
py -m unittest discover -s tests
$env:PYTHONDONTWRITEBYTECODE='1'; py -m py_compile APIkeys_collection.py APIkeys_collection_ui.py api_launcher\core.py api_launcher\db.py api_launcher\models.py api_launcher\repository.py
```

## Design Rules

- Treat `APIkeys_collection.py` as a compatibility wrapper; put new logic in `api_launcher/`.
- Keep UI JSON formats shared through core modules such as `api_launcher/plans.py`.
- Reuse `api_launcher.library_actions` for install/update/repair/open/render/uninstall decisions. For agent-readable output, call the CLI instead of rebuilding policy:

```bash
python APIkeys_collection.py --show-library-actions PROVIDER_ID --library-actions-json
```

- Register local installs through `provider_installations.install_id`; do not infer ownership from names alone.
- Register SQL/file assets in `provider_installation_assets` with `asset_role`, `source_format`, `source_uri`, and `schema_fingerprint`.
- Distinguish official source data from curated, derived, analysis, and cache assets.
- Do not execute `DROP DATABASE`, delete files, or remove tables until an adapter verifies the target and ownership.
- API data still needs curation. Use `api_launcher/curation.py` patterns for field mapping, type casting, required checks, and deduplication.

## Repair Workflow

- Inspect file health with `python APIkeys_collection.py --verify-downloads --manifest-health --list-manifests`.
- Use Tk `Tools > Repair / verify manifests` for human repair work. Rows with missing/size/checksum problems and a manifest-recorded HTTP(S) `source_url` can be safely requeued through staging with `Requeue selected`.
- Do not invent a repair action for `manifest_error` or manifests without `source_url`; those require manual inspection or adapter-specific recovery.

## Data Store Self-check

- Use `python APIkeys_collection.py --test-data-store PROFILE_ID` to test one configured data-store profile, or `--test-data-store all` for every profile.
- Use `python APIkeys_collection.py --self-check-databases` to verify managed database assets recorded in the install registry.
- SQLite checks are read-only and should not create a missing database file.
- MySQL/PostgreSQL checks first report missing env vars or optional Python drivers; do not add driver packages to base/system environments without user approval.

## References

- Read `references/pipeline.md` when changing the architecture or adding adapters.
