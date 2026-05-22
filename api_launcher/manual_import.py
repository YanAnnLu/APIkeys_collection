from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from api_launcher.manifests import AssetManifest, sha256_file, write_manifest
from api_launcher.models import Provider
from api_launcher.paths import STATE_DIR
from api_launcher.repository import ApiCatalogRepository, source_format_from_path


DEFAULT_MANUAL_LOCAL_PROVIDER_ID = "manual_local_files"
DEFAULT_MANUAL_LOCAL_VERSION = "local"
DEFAULT_MANUAL_MANIFEST_DIR = STATE_DIR / "manual_imports"

CSV_MANUAL_IMPORT_FORMATS = {"csv", "csv.gz"}
JSON_MANUAL_IMPORT_FORMATS = {"json", "json.gz", "jsonl", "jsonl.gz", "ndjson", "ndjson.gz", "geojson", "geojson.gz"}
SUPPORTED_MANUAL_IMPORT_FORMATS = tuple(sorted(CSV_MANUAL_IMPORT_FORMATS | JSON_MANUAL_IMPORT_FORMATS))


@dataclass(frozen=True)
class LocalFileManifestResult:
    # 這個結果同時給 CLI 與未來 UI wizard 使用；next_command 讓新手知道下一步該跑哪個既有匯入器。
    manifest_path: Path
    payload_path: Path
    provider_id: str
    dataset_id: str
    dataset_uid: str
    version: str
    source_format: str
    import_kind: str
    next_command: str

    def as_dict(self) -> dict[str, object]:
        return {
            "manifest_path": str(self.manifest_path),
            "payload_path": str(self.payload_path),
            "provider_id": self.provider_id,
            "dataset_id": self.dataset_id,
            "dataset_uid": self.dataset_uid,
            "version": self.version,
            "source_format": self.source_format,
            "import_kind": self.import_kind,
            "next_command": self.next_command,
        }


def manual_local_file_provider(provider_id: str = DEFAULT_MANUAL_LOCAL_PROVIDER_ID) -> Provider:
    # 手動匯入需要一個穩定的 registry owner；它代表「使用者本機檔案入口」，不代表外部資料商。
    return Provider(
        provider_id=provider_id,
        name="Manual Local Files",
        owner="Local user workspace",
        categories=("local", "manual_import", "workspace"),
        geographic_scope="user-provided",
        docs_url="https://github.com/YanAnnLu/APIkeys_collection/blob/main/docs/USER_GUIDE.zh-TW.md",
        api_base_url="",
        signup_url="",
        auth_type="local_file",
        key_env_var="",
        license_url="",
        terms_url="",
        notes=(
            "Synthetic local provider used for user-provided CSV/JSON files. "
            "No external account, credential, or network endpoint is implied."
        ),
    )


def ensure_manual_local_file_provider(
    repository: ApiCatalogRepository,
    provider_id: str = DEFAULT_MANUAL_LOCAL_PROVIDER_ID,
) -> None:
    # provider_installations 有 provider_id 外鍵；預設手動匯入 provider 必須先落進 DB，匯入資產才能登記。
    if provider_id == DEFAULT_MANUAL_LOCAL_PROVIDER_ID:
        repository.upsert_provider(manual_local_file_provider(provider_id))


def write_local_file_manifest(
    input_path: str | Path,
    manifest_path: str | Path | None = None,
    *,
    manifest_dir: str | Path = DEFAULT_MANUAL_MANIFEST_DIR,
    provider_id: str = DEFAULT_MANUAL_LOCAL_PROVIDER_ID,
    dataset_id: str = "",
    dataset_uid: str = "",
    version: str = DEFAULT_MANUAL_LOCAL_VERSION,
    source_url: str = "",
) -> LocalFileManifestResult:
    payload_path = Path(input_path).expanduser()
    if not payload_path.exists() or not payload_path.is_file():
        raise FileNotFoundError(f"Local import file does not exist or is not a file: {payload_path}")

    source_format = source_format_from_path(payload_path)
    if source_format not in SUPPORTED_MANUAL_IMPORT_FORMATS:
        supported = ", ".join(SUPPORTED_MANUAL_IMPORT_FORMATS)
        raise ValueError(f"Unsupported manual import format '{source_format}' for {payload_path}; supported: {supported}")

    clean_dataset_id = _dataset_id(dataset_id, payload_path)
    clean_provider_id = _slug(provider_id, fallback=DEFAULT_MANUAL_LOCAL_PROVIDER_ID)
    clean_version = _slug(version, fallback=DEFAULT_MANUAL_LOCAL_VERSION)
    clean_dataset_uid = dataset_uid.strip() or f"{clean_provider_id}:{clean_dataset_id}"
    resolved_payload = payload_path.resolve(strict=True)
    manifest_file = Path(manifest_path) if manifest_path else default_local_file_manifest_path(
        resolved_payload,
        manifest_dir=manifest_dir,
        provider_id=clean_provider_id,
        dataset_id=clean_dataset_id,
        version=clean_version,
    )
    manifest = AssetManifest(
        provider_id=clean_provider_id,
        dataset_uid=clean_dataset_uid,
        dataset_id=clean_dataset_id,
        version=clean_version,
        source_url=source_url.strip() or resolved_payload.as_uri(),
        path=str(resolved_payload),
        size_bytes=resolved_payload.stat().st_size,
        sha256=sha256_file(resolved_payload),
        metadata={
            "manual_import": True,
            "manual_source": "local_file",
            "source_format": source_format,
            "original_path": str(payload_path),
            "notes_zh_TW": "使用者自備本機檔案；manifest 只記錄 checksum/provenance，不代表可重新從網路下載。",
        },
    )
    write_manifest(manifest, manifest_file)
    import_kind = local_file_import_kind(source_format)
    return LocalFileManifestResult(
        manifest_path=manifest_file,
        payload_path=resolved_payload,
        provider_id=manifest.provider_id,
        dataset_id=manifest.dataset_id,
        dataset_uid=manifest.dataset_uid,
        version=manifest.version,
        source_format=source_format,
        import_kind=import_kind,
        next_command=local_file_next_import_command(manifest_file, import_kind),
    )


def default_local_file_manifest_path(
    input_path: str | Path,
    *,
    manifest_dir: str | Path = DEFAULT_MANUAL_MANIFEST_DIR,
    provider_id: str = DEFAULT_MANUAL_LOCAL_PROVIDER_ID,
    dataset_id: str = "",
    version: str = DEFAULT_MANUAL_LOCAL_VERSION,
) -> Path:
    payload_path = Path(input_path)
    clean_dataset_id = _dataset_id(dataset_id, payload_path)
    clean_provider_id = _slug(provider_id, fallback=DEFAULT_MANUAL_LOCAL_PROVIDER_ID)
    clean_version = _slug(version, fallback=DEFAULT_MANUAL_LOCAL_VERSION)
    # 依 provider/dataset/version 分層，避免不同手動檔案都塞到 state/manual_imports 根目錄。
    return Path(manifest_dir) / clean_provider_id / clean_dataset_id / clean_version / f"{payload_path.name}.manifest.json"


def local_file_import_kind(source_format: str) -> str:
    value = source_format.strip().lower()
    if value in CSV_MANUAL_IMPORT_FORMATS:
        return "csv"
    if value in JSON_MANUAL_IMPORT_FORMATS:
        return "json"
    return ""


def local_file_next_import_command(manifest_path: str | Path, import_kind: str) -> str:
    path_arg = _cli_path(manifest_path)
    if import_kind == "csv":
        return f"--import-csv-manifest {path_arg}"
    if import_kind == "json":
        return f"--import-json-manifest {path_arg}"
    return ""


def _dataset_id(dataset_id: str, payload_path: Path) -> str:
    if dataset_id.strip():
        return _slug(dataset_id, fallback="manual_dataset")
    # `.csv.gz` 這類雙副檔名要退兩層，否則 dataset_id 會殘留 `.csv`。
    name = payload_path.name
    for suffix in (".csv.gz", ".json.gz", ".jsonl.gz", ".ndjson.gz", ".geojson.gz"):
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
            break
    else:
        name = payload_path.stem
    return _slug(name, fallback="manual_dataset")


def _slug(value: str, fallback: str) -> str:
    clean = re.sub(r"[^0-9A-Za-z_]+", "_", value.strip()).strip("_").lower()
    if not clean:
        clean = fallback
    if clean[0].isdigit():
        clean = f"item_{clean}"
    return clean[:80].rstrip("_") or fallback


def _cli_path(path: str | Path) -> str:
    # next_command 是給人複製的提示；有空白時先加引號，避免 Windows 使用者的路徑被 shell 拆開。
    text = str(path)
    if any(char.isspace() for char in text):
        escaped = text.replace('"', '\\"')
        return f'"{escaped}"'
    return text
