# APIkeys_collection Pipeline Reference

## Current Package Map

- `APIkeys_collection.py`: compatibility wrapper.
- `APIkeys_collection_ui.py`: Tk launcher UI.
- `api_launcher/models.py`: Provider, ProviderCatalogEntry, Dataset.
- `api_launcher/db.py`: SQLite schema and migrations.
- `api_launcher/repository.py`: repository API for providers, datasets, installs, assets, verification.
- `api_launcher/plans.py`: shared Download Plan JSON schema.
- `api_launcher/renderer_contracts.py`: stable IDs and bridge-asset contracts for visualization engines.
- `api_launcher/discovery.py`: source-site seed loading, metadata crawling, candidate dedupe.
- `api_launcher/adapters/`: dataset discovery adapter interface.
- `api_launcher/asset_verifier.py`: local asset verification contracts.
- `api_launcher/asset_roles.py`: source/curated/derived/analysis/cache roles.
- `api_launcher/provenance.py`: source format and schema fingerprint helpers.
- `api_launcher/curation.py`: record-cleaning primitives.
- `api_launcher/sql_assets.py`: safe SQL uninstall metadata generation.

## Product Model

```text
Provider = publisher/source station, similar to a game company or download mirror
Source site = download/API station, not necessarily the canonical dataset identity
Download Plan = cart/install queue
Dataset = downloadable unit under a provider
Install ID = launcher-owned identity for a managed local install
Asset = concrete local database/table/file/bridge output owned by an install
Renderer contract = stable bridge between launcher-managed data and a visualization engine
```

## Safety Model

- `unmanaged`: launcher stops tracking; local data remains.
- `removed`: launcher marks owned registry assets removed.
- `missing`: registry says asset should exist but verifier cannot find it.
- `error`: verifier could not prove present/missing, usually connection/config failure.

Do not compare user-derived output directly against upstream provider metadata. Use `asset_role='derived'` or
`asset_role='analysis'`, set `derived_from_asset_id`, and store a separate schema fingerprint.

Treat `taichi_global_bathymetry.py` as a visualization engine. The launcher should produce registered bridge assets
such as GEBCO topography grids and HYG star catalogs rather than making the renderer rediscover/download everything.

Discovery candidates are reviewable metadata only. Never collect real API keys or tokens. Prefer canonical dataset
identity for dedupe; use source-site URLs as provenance and mirror information.
