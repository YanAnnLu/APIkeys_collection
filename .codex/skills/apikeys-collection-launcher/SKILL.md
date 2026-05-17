---
name: apikeys-collection-launcher
description: Use when working on the APIkeys_collection repository, a Steam-like big-data/API/database source launcher. Trigger for tasks involving the Tk UI, provider catalog, download-plan cart, dataset adapters, install/uninstall registry, SQL assets, provenance, curation, cross-platform Git/Docker handoff, or safe local database integration.
---

# APIkeys Collection Launcher

## Workflow

1. Start by checking `git status --short --branch`; never overwrite user changes.
2. Read `PROJECT_STATE.md` and `GIT_HANDOFF.md` before architectural changes.
3. Keep the launcher model clear:
   `Provider catalog -> Download Plan cart -> Dataset adapter -> Import/curation -> Install registry -> Local assets`.
4. Keep destructive operations disabled unless an adapter can prove ownership by `install_id` and asset registry metadata.
5. Run tests before commit:

```powershell
py -m unittest discover -s tests
$env:PYTHONDONTWRITEBYTECODE='1'; py -m py_compile APIkeys_collection.py APIkeys_collection_ui.py api_launcher\core.py api_launcher\db.py api_launcher\models.py api_launcher\repository.py
```

## Design Rules

- Treat `APIkeys_collection.py` as a compatibility wrapper; put new logic in `api_launcher/`.
- Keep UI JSON formats shared through core modules such as `api_launcher/plans.py`.
- Register local installs through `provider_installations.install_id`; do not infer ownership from names alone.
- Register SQL/file assets in `provider_installation_assets` with `asset_role`, `source_format`, `source_uri`, and `schema_fingerprint`.
- Distinguish official source data from curated, derived, analysis, and cache assets.
- Do not execute `DROP DATABASE`, delete files, or remove tables until an adapter verifies the target and ownership.
- API data still needs curation. Use `api_launcher/curation.py` patterns for field mapping, type casting, required checks, and deduplication.

## References

- Read `references/pipeline.md` when changing the architecture or adding adapters.
