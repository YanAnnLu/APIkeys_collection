from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass

from api_launcher.crawlers.types import DatasetCandidate, DatasetCrawlerOutput, DatasetDiscoverySource


DatasetSourceCrawler = Callable[
    [DatasetDiscoverySource, float, int, tuple[str, ...], bool, int],
    list[DatasetCandidate] | tuple[DatasetCandidate, ...] | DatasetCrawlerOutput,
]

CrawlerMatrixKey = tuple[str, str, str, str]
CapabilityIndex = dict[int, tuple[str, ...]]

CAPABILITY_CODE_WIDTH = 4

# The first capability address pass deliberately keeps only four dimensions.
# A small, fixed width makes the table readable while still letting callers
# query broad families with masks, similar to a tiny CIDR-style route table.
SOURCE_FAMILY_BITS = {
    "catalog_search": 0b0000,
    "catalog_index": 0b1000,
    "index_scan": 0b1000,
    "map_capabilities": 0b1000,
}
TRANSPORT_BITS = {
    "json": 0b0000,
    "html": 0b0100,
    "xml": 0b0100,
    "text": 0b0100,
}
AUTH_PROFILE_BITS = {
    "none": 0b0000,
    "public_or_review": 0b0000,
    "optional_api_key": 0b0010,
    "api_key": 0b0010,
    "oauth": 0b0010,
    "credential_required": 0b0010,
}
RESULT_SHAPE_BITS = {
    "dataset_list": 0b0000,
    "file_links": 0b0001,
    "layer_list": 0b0001,
    "resource_links": 0b0001,
}


@dataclass(frozen=True)
class CrawlerCapabilityCode:
    """Compact, maskable address for crawler dispatch capability.

    The bits are not a replacement for CrawlerSpec.  They are an auxiliary
    index that lets UI/debug tooling ask questions such as "all JSON catalog
    crawlers" without scattering source_type branches.
    """

    bits: int
    width: int = CAPABILITY_CODE_WIDTH

    def __post_init__(self) -> None:
        _validate_bit_width(self.bits, self.width, field_name="bits")

    @property
    def binary(self) -> str:
        return format(self.bits, f"0{self.width}b")

    def to_dict(self) -> dict[str, object]:
        return {
            "bits": self.bits,
            "binary": self.binary,
            "width": self.width,
        }


@dataclass(frozen=True)
class CrawlerCapabilityMask:
    """Mask for querying one or more crawler capability addresses."""

    bits: int
    mask: int
    width: int = CAPABILITY_CODE_WIDTH

    def __post_init__(self) -> None:
        _validate_bit_width(self.bits, self.width, field_name="bits")
        _validate_bit_width(self.mask, self.width, field_name="mask")

    @classmethod
    def from_prefix(
        cls,
        bits: int,
        prefix_len: int,
        width: int = CAPABILITY_CODE_WIDTH,
    ) -> CrawlerCapabilityMask:
        if prefix_len < 0 or prefix_len > width:
            raise ValueError(f"prefix_len must be between 0 and {width}: {prefix_len}")
        if prefix_len == 0:
            mask = 0
        else:
            mask = ((1 << prefix_len) - 1) << (width - prefix_len)
        _validate_bit_width(bits, width, field_name="bits")
        return cls(bits=bits & mask, mask=mask, width=width)

    @property
    def binary(self) -> str:
        return format(self.bits, f"0{self.width}b")

    @property
    def mask_binary(self) -> str:
        return format(self.mask, f"0{self.width}b")

    def matches(self, code: CrawlerCapabilityCode | int) -> bool:
        bits = code.bits if isinstance(code, CrawlerCapabilityCode) else int(code)
        _validate_bit_width(bits, self.width, field_name="code")
        return (bits & self.mask) == self.bits

    def to_dict(self) -> dict[str, object]:
        return {
            "bits": self.bits,
            "binary": self.binary,
            "mask": self.mask,
            "mask_binary": self.mask_binary,
            "width": self.width,
        }


@dataclass(frozen=True)
class CrawlerSpec:
    """Declarative metadata for a crawler handler.

    The registry is a transitional layer toward profile/gateway based crawling.
    It describes what a handler is, but it does not hide the handler's normal
    Python implementation behind a custom DSL.
    """

    source_type: str
    source_family: str
    transport: str
    auth_profile: str
    result_shape: str
    supports_full_crawl: bool
    capability_code: CrawlerCapabilityCode
    handler: DatasetSourceCrawler

    @property
    def matrix_key(self) -> CrawlerMatrixKey:
        return (self.source_family, self.transport, self.auth_profile, self.result_shape)

    @property
    def capability_bits(self) -> int:
        return self.capability_code.bits

    @property
    def capability_binary(self) -> str:
        return self.capability_code.binary

    def to_dict(self) -> dict[str, object]:
        return {
            "source_type": self.source_type,
            "source_family": self.source_family,
            "transport": self.transport,
            "auth_profile": self.auth_profile,
            "result_shape": self.result_shape,
            "supports_full_crawl": self.supports_full_crawl,
            "matrix_key": self.matrix_key,
            "capability_code": self.capability_code.to_dict(),
            "capability_bits": self.capability_bits,
            "capability_binary": self.capability_binary,
            "handler_name": self.handler.__name__,
        }


_REGISTRY: dict[str, CrawlerSpec] = {}


def _validate_bit_width(value: int, width: int, *, field_name: str) -> None:
    if value < 0 or value >= (1 << width):
        raise ValueError(f"{field_name} must fit in {width} bits: {value}")


def _dimension_bits(mapping: dict[str, int], value: str, *, dimension: str) -> int:
    key = value.strip()
    try:
        return mapping[key]
    except KeyError as exc:
        raise ValueError(f"Unsupported crawler capability {dimension}: {key}") from exc


def capability_code_for(
    source_family: str,
    transport: str,
    auth_profile: str,
    result_shape: str,
) -> CrawlerCapabilityCode:
    """Return the 4-bit capability address for one CrawlerSpec cell."""

    bits = (
        _dimension_bits(SOURCE_FAMILY_BITS, source_family, dimension="source_family")
        | _dimension_bits(TRANSPORT_BITS, transport, dimension="transport")
        | _dimension_bits(AUTH_PROFILE_BITS, auth_profile, dimension="auth_profile")
        | _dimension_bits(RESULT_SHAPE_BITS, result_shape, dimension="result_shape")
    )
    return CrawlerCapabilityCode(bits=bits)


def crawler(
    *,
    source_type: str,
    source_family: str,
    transport: str,
    auth_profile: str,
    result_shape: str,
    supports_full_crawl: bool = False,
) -> Callable[[DatasetSourceCrawler], DatasetSourceCrawler]:
    """Register a crawler handler with declarative capability metadata."""

    def decorator(func: DatasetSourceCrawler) -> DatasetSourceCrawler:
        normalized_source_type = source_type.strip()
        normalized_source_family = source_family.strip()
        normalized_transport = transport.strip()
        normalized_auth_profile = auth_profile.strip()
        normalized_result_shape = result_shape.strip()
        if not normalized_source_type:
            raise ValueError("Crawler source_type must not be blank")
        if normalized_source_type in _REGISTRY:
            raise ValueError(f"Duplicate crawler source_type: {normalized_source_type}")
        capability_code = capability_code_for(
            normalized_source_family,
            normalized_transport,
            normalized_auth_profile,
            normalized_result_shape,
        )
        _REGISTRY[normalized_source_type] = CrawlerSpec(
            source_type=normalized_source_type,
            source_family=normalized_source_family,
            transport=normalized_transport,
            auth_profile=normalized_auth_profile,
            result_shape=normalized_result_shape,
            supports_full_crawl=bool(supports_full_crawl),
            capability_code=capability_code,
            handler=func,
        )
        return func

    return decorator


def crawler_spec(source_type: str) -> CrawlerSpec:
    normalized_source_type = source_type.strip()
    try:
        return _REGISTRY[normalized_source_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported dataset discovery source_type: {normalized_source_type}") from exc


def crawler_handler(source_type: str) -> DatasetSourceCrawler:
    return crawler_spec(source_type).handler


def crawler_specs() -> tuple[CrawlerSpec, ...]:
    return tuple(_REGISTRY[source_type] for source_type in sorted(_REGISTRY))


def iter_crawler_specs_by_dims(
    *,
    source_family: str | None = None,
    transport: str | None = None,
    auth_profile: str | None = None,
    result_shape: str | None = None,
) -> Iterator[CrawlerSpec]:
    """Yield registered specs matching any provided capability dimensions.

    This is the read side of the declarative matrix.  Callers can ask for
    "all JSON catalog crawlers" or "all credential-aware crawlers" without
    writing source_type branches in UI, CLI, or import code.
    """

    for spec in crawler_specs():
        if source_family is not None and spec.source_family != source_family:
            continue
        if transport is not None and spec.transport != transport:
            continue
        if auth_profile is not None and spec.auth_profile != auth_profile:
            continue
        if result_shape is not None and spec.result_shape != result_shape:
            continue
        yield spec


def crawler_specs_by_dims(
    *,
    source_family: str | None = None,
    transport: str | None = None,
    auth_profile: str | None = None,
    result_shape: str | None = None,
) -> tuple[CrawlerSpec, ...]:
    return tuple(
        iter_crawler_specs_by_dims(
            source_family=source_family,
            transport=transport,
            auth_profile=auth_profile,
            result_shape=result_shape,
        )
    )


def crawler_handlers_by_source_type() -> dict[str, DatasetSourceCrawler]:
    return {source_type: spec.handler for source_type, spec in _REGISTRY.items()}


def crawler_matrix() -> dict[CrawlerMatrixKey, tuple[str, ...]]:
    matrix: dict[CrawlerMatrixKey, list[str]] = {}
    for spec in _REGISTRY.values():
        matrix.setdefault(spec.matrix_key, []).append(spec.source_type)
    return {key: tuple(sorted(source_types)) for key, source_types in matrix.items()}


def crawler_capability_index() -> CapabilityIndex:
    index: dict[int, list[str]] = {}
    for spec in _REGISTRY.values():
        index.setdefault(spec.capability_bits, []).append(spec.source_type)
    return {bits: tuple(sorted(source_types)) for bits, source_types in index.items()}


def crawler_specs_by_capability_mask(mask: CrawlerCapabilityMask) -> tuple[CrawlerSpec, ...]:
    return tuple(spec for spec in crawler_specs() if mask.matches(spec.capability_code))


def crawler_specs_by_source_type() -> dict[str, CrawlerSpec]:
    return dict(_REGISTRY)


__all__ = [
    "AUTH_PROFILE_BITS",
    "CAPABILITY_CODE_WIDTH",
    "CapabilityIndex",
    "CrawlerCapabilityCode",
    "CrawlerCapabilityMask",
    "CrawlerMatrixKey",
    "CrawlerSpec",
    "DatasetSourceCrawler",
    "RESULT_SHAPE_BITS",
    "SOURCE_FAMILY_BITS",
    "TRANSPORT_BITS",
    "capability_code_for",
    "crawler",
    "crawler_capability_index",
    "crawler_handler",
    "crawler_handlers_by_source_type",
    "crawler_matrix",
    "crawler_spec",
    "crawler_specs",
    "crawler_specs_by_capability_mask",
    "crawler_specs_by_dims",
    "crawler_specs_by_source_type",
    "iter_crawler_specs_by_dims",
]
