from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from api_launcher.manifests import AssetManifest, read_manifest, sha256_file, write_manifest
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
    provenance_review: dict[str, object]
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
            "provenance_review": self.provenance_review,
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


def register_local_file_manifest_asset(repository: ApiCatalogRepository, manifest_path: str | Path) -> str:
    # 手動本機檔案也要進 manifest registry；否則後續 manifest-health / repair panel 會看不到 raw file。
    manifest = read_manifest(manifest_path)
    repository.upsert_dataset_asset_manifest(manifest, manifest_path, status="ok")
    return repository.register_downloaded_manifest_asset(
        manifest,
        manifest_path,
        notes="Manual local source asset registered from verified sidecar manifest.",
    )


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
        raise ValueError(manual_import_unsupported_format_message(payload_path, source_format))

    clean_dataset_id = _dataset_id(dataset_id, payload_path)
    clean_provider_id = _slug(provider_id, fallback=DEFAULT_MANUAL_LOCAL_PROVIDER_ID)
    clean_version = _slug(version, fallback=DEFAULT_MANUAL_LOCAL_VERSION)
    clean_dataset_uid = dataset_uid.strip() or f"{clean_provider_id}:{clean_dataset_id}"
    resolved_payload = payload_path.resolve(strict=True)
    import_kind = local_file_import_kind(source_format)
    provenance_review = local_file_provenance_review(source_format, import_kind)
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
            "provenance_review": provenance_review,
            "notes_zh_TW": "使用者自備本機檔案；manifest 只記錄 checksum/provenance，不代表可重新從網路下載。",
        },
    )
    write_manifest(manifest, manifest_file)
    return LocalFileManifestResult(
        manifest_path=manifest_file,
        payload_path=resolved_payload,
        provider_id=manifest.provider_id,
        dataset_id=manifest.dataset_id,
        dataset_uid=manifest.dataset_uid,
        version=manifest.version,
        source_format=source_format,
        import_kind=import_kind,
        provenance_review=provenance_review,
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


def local_file_provenance_review(source_format: str, import_kind: str) -> dict[str, object]:
    # 這份摘要是給人類與 agent 的審查提示；它不改變匯入結果，只固定安全邊界與下一步語意。
    format_label = {
        "csv": "CSV 表格檔",
        "csv.gz": "壓縮 CSV 表格檔",
        "json": "JSON 記錄檔",
        "json.gz": "壓縮 JSON 記錄檔",
        "jsonl": "JSON Lines 記錄檔",
        "jsonl.gz": "壓縮 JSON Lines 記錄檔",
        "ndjson": "NDJSON 記錄檔",
        "ndjson.gz": "壓縮 NDJSON 記錄檔",
        "geojson": "GeoJSON FeatureCollection",
        "geojson.gz": "壓縮 GeoJSON FeatureCollection",
    }.get(source_format, source_format.upper())
    if import_kind == "csv":
        importer_label = "CSV manifest importer"
    elif import_kind == "json":
        importer_label = "JSON/JSONL/GeoJSON manifest importer"
    else:
        importer_label = "manual review"
    return {
        "source_label_zh_TW": "使用者自備本機檔案",
        "format_label_zh_TW": format_label,
        "importer_label": importer_label,
        "risk_level": "local_review_required",
        "trust_boundary_zh_TW": "Launcher 只能保證當下檔案的 checksum、大小與匯入結果，不能保證檔案原始來源或授權。",
        "safe_operations_zh_TW": [
            "建立 sidecar manifest",
            "計算 checksum 與檔案大小",
            "登記 raw file asset",
            "使用既有 CSV/JSON 匯入器寫入 SQLite",
            "後續可用 database self-check 檢查匯入 table",
        ],
        "blocked_operations_zh_TW": [
            "不掃描整個資料夾",
            "不移動或刪除來源檔",
            "不把 file:// 視為可重新下載的網路來源",
            "不自動覆蓋既有 table",
            "不推定授權可再散布或可商用",
        ],
        "recommended_next_step_zh_TW": "匯入後執行資料庫自檢，並由使用者確認檔案來源、授權與欄位意義。",
    }


def manual_import_unsupported_format_message(path: str | Path, source_format: str) -> str:
    # 錯誤訊息直接給修復方向，避免 UI/agent 只看到「不支援」卻不知道下一步。
    supported = ", ".join(SUPPORTED_MANUAL_IMPORT_FORMATS)
    return (
        f"Unsupported manual import format '{source_format}' for {path}; supported: {supported}. "
        "目前手動匯入只支援 CSV/JSON/JSONL/NDJSON/GeoJSON 類檔案。"
        "若來源是 SQL、Excel、Parquet、Shapefile、NetCDF、HDF、ZIP/TAR 原始包或其他格式，"
        "請先轉成支援格式，或把它留在 adapter/manual review，不要硬塞進 SQLite。"
    )


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
