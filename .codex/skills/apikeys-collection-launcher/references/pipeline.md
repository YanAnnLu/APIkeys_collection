# APIkeys_collection Pipeline Reference

## Current Package Map

- `APIkeys_collection.py`: compatibility wrapper.
- `APIkeys_collection_ui.py`: Tk launcher UI.
- `api_launcher/models.py`: Provider, ProviderCatalogEntry, Dataset.
- `api_launcher/db.py`: SQLite schema and migrations.
- `api_launcher/repository.py`: repository API for providers, datasets, installs, assets, verification.
- `api_launcher/plans.py`: shared Download Plan JSON schema.
- `api_launcher/ingestion_pipeline.py`: reusable direct-plan download/import slice for CLI, UI, and future subcommands.
- `api_launcher/renderer_contracts.py`: stable IDs and bridge-asset contracts for visualization engines.
- `api_launcher/discovery.py`: source-site seed loading, metadata crawling, candidate dedupe.
- `api_launcher/adapters/`: dataset discovery adapter interface.
- `api_launcher/asset_verifier.py`: local asset verification contracts.
- `api_launcher/asset_roles.py`: source/curated/derived/analysis/cache roles.
- `api_launcher/provenance.py`: source format and schema fingerprint helpers.
- `api_launcher/importers/curation.py`: record-cleaning primitives.
- `api_launcher/sql_assets.py`: safe SQL uninstall metadata generation.

## Documentation Map

Use repo docs as the source of truth; this file is only a compact route map.

- `docs/AGENT_HANDOFF.zh-TW.md`: live handoff, current checkpoint, user preferences, safety incidents.
- `docs/PROJECT_GTD.md`: MVP progress table and next work areas.
- `docs/DEVELOPMENT_LOG.zh-TW.md`: pushed checkpoint log with changes, verification, CI, and residual risks.
- `docs/DOCS_INDEX.zh-TW.md`: doc ownership and reading routes.
- `docs/DATA_ASSET_PLATFORM_CONCEPTS.zh-TW.md`: roadmap concepts for Data Assets, Discovery Tools, lakehouse/K8S, Render Studio, ML, connectors, and local-first desktop shape.
- `docs/DATASET_DISCOVERY_NOTES.zh-TW.md`: crawler-first, candidate review, bounded resolver, and adapter-review design. `docs/appendices/discovery.zh-TW.md` is retained only as a redirect for older references.
- `docs/DATASET_TYPE_MAP.zh-TW.md`: data-family/storage/viewer concept map.
- `docs/TECHNICAL_OVERVIEW.zh-TW.md` and `docs/ARCHITECTURE.md`: pipeline and runtime architecture.
- `docs/DEVELOPMENT_WORKFLOW_OPEN_SPEC.zh-TW.md` and `openspec/specs/development-workflow/spec.md`: spec-driven workflow.
- `docs/USER_GUIDE.zh-TW.md` and `docs/SETUP.zh-TW.md`: user operations, developer CLI command index, and environment setup.
- `docs/WORKSPACE_LAYOUT.zh-TW.md`: file ownership, module split, runtime path rules.
- `docs/appendices/failure_modes.zh-TW.md`: failure recovery and repair design.
- `docs/appendices/render_frontends.zh-TW.md`, `docs/appendices/unreal_bridge.zh-TW.md`, `frontends/unreal/README.zh-TW.md`: renderer and Unreal boundary.

## Documentation Refactor Rule

When organizing docs, pick one document group per commit, choose the canonical source by document role, preserve old paths as redirect/summary files when references may exist, then update `docs/DOCS_INDEX.zh-TW.md`, `docs/AGENT_HANDOFF.zh-TW.md`, `docs/PROJECT_GTD.md`, append `docs/DEVELOPMENT_LOG.zh-TW.md` for pushed checkpoints, and update skill/prompt/script references. In Traditional Chinese docs, Mermaid labels should be Traditional Chinese except precise file names, CLI flags, module paths, product names, and standards.

`docs/DEVELOPMENT_LOG.zh-TW.md` should stay ledger-style. Use GitHub Actions push runs when needed, group by Asia/Taipei date in reverse chronological order with the newest date first, and list entries inside each date newest time first. Use a Markdown table with `時間`, `標記`, `SHA`, `Run`, `原始標題`, and `中文說明` columns. Keep the original English push title, add a Traditional Chinese explanation in the `中文說明` column for every row, mark successful runs as `**CHECKPOINT**`, and keep failed runs as `**CI 失敗**` to preserve the repair path.

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

## MVP Loop Definition

The backend MVP is not "many providers listed". It is a narrow but real closed loop:

```text
provider/source seed
-> crawler/discovery candidate
-> human or policy review
-> download/import plan
-> bounded resolver or adapter handoff
-> direct download with manifest
-> curated CSV/JSON/archive import
-> registry/self-check/UI status
```

Roadmap ideas should not bypass this loop. A feature can be valuable but still remain documentation-only until it has a safe entrypoint in the loop.

## Code Comment Rule

When changing non-trivial code, leave short maintainer comments near logic that protects a boundary or encodes a non-obvious decision. Prioritize orchestration, safety guards, schema/provenance invariants, adapter assumptions, external API quirks, cross-module ownership, and data transformations. Comments should explain why the rule exists or what invariant must hold, not restate obvious code.

## Current Frontier

As of the 2026-05-20 docs, the strongest next slices are:

- More bounded adapter/crawler handoffs, especially NOAA/NCEI file selectors, CMR granule asset links, OGC Records, DOI/DataCite/OpenAlex, Socrata, Dataverse, and STAC-like metadata.
- Guarded repair and database self-check expansion only where install ownership and manifest provenance are explicit.
- UI polish that exposes existing backend flows in Traditional Chinese without scattering integration buttons.
- OpenSpec proposals for medium cross-module work; small fixes may stay lightweight but still update GTD/handoff when state changes.

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
