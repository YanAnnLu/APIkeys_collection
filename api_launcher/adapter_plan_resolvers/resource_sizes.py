from __future__ import annotations

from collections.abc import Callable


ResourceTextReader = Callable[..., str]


def resource_exceeds_size_bound(
    resource: dict[str, object],
    max_bytes: int,
    *,
    text_reader: ResourceTextReader,
) -> bool:
    size = resource_size_bytes(resource, text_reader=text_reader)
    return size > max_bytes if size is not None else False


def resource_size_bytes(resource: dict[str, object], *, text_reader: ResourceTextReader) -> int | None:
    # 不同 catalog 對檔案大小欄位命名不一致；這裡集中吸收差異，避免每個 resolver 重複猜欄位。
    for key in (
        "size",
        "bytes",
        "content_length",
        "contentLength",
        "file_size",
        "fileSize",
        "FileSize",
        "size_bytes",
        "sizeInBytes",
        "SizeInBytes",
        "byteSize",
        "dcat:byteSize",
        "http://www.w3.org/ns/dcat#byteSize",
        "https://www.w3.org/ns/dcat#byteSize",
        "contentSize",
        "schema:contentSize",
        "http://schema.org/contentSize",
        "https://schema.org/contentSize",
    ):
        value = resource.get(key)
        if value in ("", None):
            continue
        size = positive_int_from_resource_value(value, text_reader=text_reader)
        if size is not None:
            return size
    return None


def positive_int_from_resource_value(value: object, *, text_reader: ResourceTextReader) -> int | None:
    if isinstance(value, (list, tuple)):
        # JSON-LD 欄位可能是多值陣列；取第一個可解析的正整數，避免因單一壞值放棄整個 resource。
        for item in value:
            size = positive_int_from_resource_value(item, text_reader=text_reader)
            if size is not None:
                return size
        return None
    if isinstance(value, dict):
        return positive_int_from_resource_value(
            text_reader(
                value.get("@value"),
                value.get("value"),
                value.get("bytes"),
                value.get("size"),
            ),
            text_reader=text_reader,
        )
    return positive_int_or_none(value)


def positive_int_or_none(value: object) -> int | None:
    try:
        size = int(float(str(value)))
    except (TypeError, ValueError):
        return None
    return size if size >= 0 else None
