"""Immutable release-local provenance. No academic evaluation lives here."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def plain(value):
    if isinstance(value, Mapping):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [plain(item) for item in value]
    return value


@dataclass(frozen=True)
class InstitutionalSource:
    source_id: str
    institution_id: str
    release_id: str
    source_kind: str
    title: str
    source_status: str


@dataclass(frozen=True)
class RequirementSourceRelationship:
    relationship_id: str
    institution_id: str
    release_id: str
    requirement_id: str
    programme_key: str
    source_id: str
    relationship_type: str
    locator: Mapping[str, Any]
    relationship_status: str = "unverified"
    rule_status: str = "unverified"

    def __post_init__(self):
        object.__setattr__(self, "locator", _freeze(dict(self.locator)))


@dataclass(frozen=True)
class ReleaseProvenance:
    institution_id: str
    release_id: str
    sources: tuple[InstitutionalSource, ...] = ()
    relationships: tuple[RequirementSourceRelationship, ...] = ()
    requirement_keys: frozenset[tuple[str, str]] = field(default_factory=frozenset)

    def __post_init__(self):
        object.__setattr__(self, "sources", tuple(self.sources))
        object.__setattr__(self, "relationships", tuple(self.relationships))
        object.__setattr__(self, "requirement_keys", frozenset(self.requirement_keys))
        sources = {item.source_id: item for item in self.sources}
        ids = [item.relationship_id for item in self.relationships]
        if len(sources) != len(self.sources) or len(set(ids)) != len(ids):
            raise ValueError("Duplicate provenance identity")
        for item in (*self.sources, *self.relationships):
            if (item.institution_id, item.release_id) != (self.institution_id, self.release_id):
                raise ValueError("Cross-release provenance")
        if any(not item.source_id or not item.source_kind or not item.title for item in self.sources):
            raise ValueError("Source identity, kind and title are required")
        seen = set()
        for item in self.relationships:
            if not item.relationship_id or item.source_id not in sources:
                raise ValueError("Invalid relationship/source identity")
            if (item.programme_key, item.requirement_id) not in self.requirement_keys:
                raise ValueError("Unknown requirement identity")
            if item.relationship_type not in {"DIRECT_RULE_SOURCE", "INHERITED_POLICY_SOURCE", "PACKAGE_SOURCE"}:
                raise ValueError("Unknown source relationship type")
            identity = (item.programme_key, item.requirement_id, item.source_id, repr(plain(item.locator)))
            if identity in seen:
                raise ValueError("Duplicate source relationship")
            seen.add(identity)

    def for_requirement(self, programme_key, requirement_id):
        return tuple(item for item in self.relationships if
                     (item.programme_key, item.requirement_id) == (programme_key, requirement_id))

    def for_source(self, source_id):
        return tuple(item for item in self.relationships if item.source_id == source_id)

    def source(self, source_id):
        return next(item for item in self.sources if item.source_id == source_id)


def from_package(package, institution_id, release_id):
    keys = set()

    def collect(node, programme):
        if isinstance(node, dict):
            if "id" in node and "type" in node:
                keys.add((programme, node["id"]))
            for value in node.values():
                collect(value, programme)
        elif isinstance(node, list):
            for value in node:
                collect(value, programme)

    for programme, value in package.get("programmes", {}).items():
        collect(value.get("curriculum_rules", []), programme)
        collect(value.get("pathways", {}), programme)
    return ReleaseProvenance(
        institution_id, release_id,
        tuple(InstitutionalSource(**item) for item in package.get("institution_sources", [])),
        tuple(RequirementSourceRelationship(**item) for item in package.get("requirement_source_relationships", [])),
        frozenset(keys),
    )
