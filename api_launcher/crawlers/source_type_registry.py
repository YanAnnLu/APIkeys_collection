from __future__ import annotations

from api_launcher.crawlers.types import DatasetDiscoverySource


HTML_FILE_INDEX_SOURCE_TYPE = "html_file_index"
FILE_INDEX_SOURCE_TYPES = frozenset({HTML_FILE_INDEX_SOURCE_TYPE})


def source_type_is_file_index(source_type: str) -> bool:
    return source_type.strip().lower() in FILE_INDEX_SOURCE_TYPES


def source_uses_file_index(source: DatasetDiscoverySource) -> bool:
    return bool(source.file_url_regex) or source_type_is_file_index(source.source_type)


__all__ = [
    "FILE_INDEX_SOURCE_TYPES",
    "HTML_FILE_INDEX_SOURCE_TYPE",
    "source_type_is_file_index",
    "source_uses_file_index",
]
