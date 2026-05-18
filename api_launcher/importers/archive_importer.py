from __future__ import annotations

import shutil
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from api_launcher.downloads.repair import verify_manifest_file
from api_launcher.downloads.staging import safe_path_part
from api_launcher.manifests import AssetManifest, read_manifest, sha256_file, write_manifest
from api_launcher.paths import STATE_DIR


SUPPORTED_ARCHIVE_SUFFIXES = {".zip", ".tar", ".tgz", ".tar.gz", ".tar.bz2", ".tar.xz"}
SUPPORTED_MEMBER_SUFFIXES = {".csv", ".csv.gz", ".json", ".jsonl", ".geojson"}


@dataclass(frozen=True)
class ExtractedArchiveMember:
    manifest_path: Path
    payload_path: Path
    member_name: str
    source_format: str


def extract_first_supported_member_manifest(manifest_path: str | Path) -> ExtractedArchiveMember:
    verification = verify_manifest_file(manifest_path)
    if verification.status != "ok":
        raise ValueError(f"Archive manifest is not healthy: {verification.status} {verification.message}")
    manifest = read_manifest(manifest_path)
    archive_path = Path(manifest.path)
    if not is_supported_archive(archive_path):
        raise ValueError(f"Unsupported archive format for MVP extraction: {archive_path}")
    output_dir = extracted_output_dir(manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    if archive_path.suffix.lower() == ".zip":
        return extract_from_zip(archive_path, output_dir, manifest, Path(manifest_path))
    return extract_from_tar(archive_path, output_dir, manifest, Path(manifest_path))


def is_supported_archive(path: Path) -> bool:
    lower = path.name.lower()
    return any(lower.endswith(suffix) for suffix in SUPPORTED_ARCHIVE_SUFFIXES)


def is_supported_member(name: str) -> bool:
    lower = name.lower()
    return any(lower.endswith(suffix) for suffix in SUPPORTED_MEMBER_SUFFIXES)


def member_source_format(name: str) -> str:
    lower = name.lower()
    for suffix in sorted(SUPPORTED_MEMBER_SUFFIXES, key=len, reverse=True):
        if lower.endswith(suffix):
            return suffix.removeprefix(".")
    return "unknown"


def extracted_output_dir(manifest: AssetManifest) -> Path:
    return (
        STATE_DIR
        / "extracted"
        / safe_path_part(manifest.provider_id)
        / safe_path_part(manifest.dataset_id or manifest.dataset_uid or "dataset")
        / safe_path_part(manifest.version or "unversioned")
    )


def extract_from_zip(
    archive_path: Path,
    output_dir: Path,
    manifest: AssetManifest,
    source_manifest_path: Path,
) -> ExtractedArchiveMember:
    with zipfile.ZipFile(archive_path) as archive:
        names = sorted(name for name in archive.namelist() if not name.endswith("/") and is_supported_member(name))
        if not names:
            raise ValueError(f"Archive has no supported CSV/JSON member: {archive_path}")
        member_name = names[0]
        output_path = output_dir / safe_path_part(Path(member_name).name)
        with archive.open(member_name) as source, output_path.open("wb") as target:
            shutil.copyfileobj(source, target)
    return write_extracted_manifest(output_path, member_name, manifest, source_manifest_path)


def extract_from_tar(
    archive_path: Path,
    output_dir: Path,
    manifest: AssetManifest,
    source_manifest_path: Path,
) -> ExtractedArchiveMember:
    with tarfile.open(archive_path) as archive:
        members = sorted(
            (member for member in archive.getmembers() if member.isfile() and is_supported_member(member.name)),
            key=lambda member: member.name,
        )
        if not members:
            raise ValueError(f"Archive has no supported CSV/JSON member: {archive_path}")
        member = members[0]
        extracted = archive.extractfile(member)
        if extracted is None:
            raise ValueError(f"Could not extract archive member: {member.name}")
        member_name = member.name
        output_path = output_dir / safe_path_part(Path(member_name).name)
        with extracted as source, output_path.open("wb") as target:
            shutil.copyfileobj(source, target)
    return write_extracted_manifest(output_path, member_name, manifest, source_manifest_path)


def write_extracted_manifest(
    output_path: Path,
    member_name: str,
    manifest: AssetManifest,
    source_manifest_path: Path,
) -> ExtractedArchiveMember:
    source_format = member_source_format(member_name)
    extracted_manifest = AssetManifest(
        provider_id=manifest.provider_id,
        dataset_uid=manifest.dataset_uid,
        dataset_id=manifest.dataset_id,
        version=manifest.version,
        source_url=manifest.source_url,
        path=str(output_path),
        size_bytes=output_path.stat().st_size,
        sha256=sha256_file(output_path),
        metadata={
            **manifest.metadata,
            "derived_from_manifest": str(source_manifest_path),
            "archive_member": member_name,
            "source_format": source_format,
        },
    )
    extracted_manifest_path = output_path.with_suffix(output_path.suffix + ".manifest.json")
    write_manifest(extracted_manifest, extracted_manifest_path)
    return ExtractedArchiveMember(
        manifest_path=extracted_manifest_path,
        payload_path=output_path,
        member_name=member_name,
        source_format=source_format,
    )
