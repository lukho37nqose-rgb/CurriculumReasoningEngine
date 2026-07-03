"""Controlled Tier 1 curriculum-administration support.

The functions in this module deliberately keep quick edits outside the
published catalogue JSON.  They validate role/field permissions, append an
audit event, and can replay approved metadata overlays at runtime.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from engine.models import Catalogue, CourseFact

ADMIN_AUDIT_DIR_ENV = "ADMIN_AUDIT_DIR"
ADMIN_TOKEN_ENV = "ADMIN_WRITE_TOKEN"
ADMIN_WRITES_ENV = "ADMIN_WRITES_ENABLED"
TRUTHY = {"1", "true", "yes", "on"}


class AdminGovernanceError(ValueError):
    """Raised when a governed admin operation is not allowed."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class AdminActor:
    name: str
    email: str
    role: str


ROLE_MATRIX: tuple[dict[str, Any], ...] = (
    {
        "role": "read_only_auditor",
        "label": "Read-only auditor",
        "scope": "All published governance status and audit summaries",
        "tier_1_quick_edit": [],
        "tier_2_review": False,
        "tier_3_release_approval": False,
        "publication": False,
    },
    {
        "role": "faculty_data_steward",
        "label": "Faculty data steward",
        "scope": "Assigned faculty metadata and source references",
        "tier_1_quick_edit": ["course_name", "course_description", "source_page_or_section"],
        "tier_2_review": False,
        "tier_3_release_approval": False,
        "publication": False,
    },
    {
        "role": "department_curriculum_editor",
        "label": "Department curriculum editor",
        "scope": "Assigned department metadata and draft structured proposals",
        "tier_1_quick_edit": ["course_name", "course_description", "source_page_or_section"],
        "tier_2_review": False,
        "tier_3_release_approval": False,
        "publication": False,
    },
    {
        "role": "department_reviewer",
        "label": "Department reviewer",
        "scope": "Departmental structured changes submitted by another user",
        "tier_1_quick_edit": [],
        "tier_2_review": True,
        "tier_3_release_approval": False,
        "publication": False,
    },
    {
        "role": "governance_admin",
        "label": "Governance admin",
        "scope": "Cross-faculty governance queue, audits and validation",
        "tier_1_quick_edit": ["course_name", "course_description", "source_page_or_section"],
        "tier_2_review": True,
        "tier_3_release_approval": False,
        "publication": False,
    },
    {
        "role": "faculty_authority",
        "label": "Faculty authority",
        "scope": "Formal release approval after validation",
        "tier_1_quick_edit": [],
        "tier_2_review": True,
        "tier_3_release_approval": True,
        "publication": False,
    },
    {
        "role": "system_admin",
        "label": "System admin",
        "scope": "Runtime configuration and platform operations",
        "tier_1_quick_edit": [],
        "tier_2_review": False,
        "tier_3_release_approval": False,
        "publication": False,
    },
)

QUICK_EDIT_FIELDS: dict[str, dict[str, Any]] = {
    "course_name": {
        "label": "Course name",
        "target": "name",
        "risk": "display_metadata",
        "max_length": 180,
    },
    "course_description": {
        "label": "Course description",
        "target": "description",
        "risk": "display_metadata",
        "max_length": 5000,
    },
    "source_page_or_section": {
        "label": "Source page or section",
        "target": "source.page_or_section",
        "risk": "source_metadata",
        "max_length": 160,
    },
}

BLOCKED_TIER_1_FIELDS = (
    "credits",
    "department",
    "offered",
    "prerequisites",
    "co_requisites",
    "programme_rules",
    "major_requirements",
)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def admin_writes_enabled() -> bool:
    return os.environ.get(ADMIN_WRITES_ENV, "").strip().lower() in TRUTHY


def _configured_write_token() -> str:
    return os.environ.get(ADMIN_TOKEN_ENV, "").strip()


def verify_admin_write_gate(token: str | None) -> None:
    """Require explicit runtime opt-in and a shared write token for Tier 1."""
    if not admin_writes_enabled():
        raise AdminGovernanceError(
            "Tier 1 admin writes are disabled. Set ADMIN_WRITES_ENABLED=1 to enable them.",
            status_code=403,
        )
    expected = _configured_write_token()
    if not expected:
        raise AdminGovernanceError(
            "Tier 1 admin writes require ADMIN_WRITE_TOKEN to be configured.",
            status_code=403,
        )
    if not token or not hmac.compare_digest(token, expected):
        raise AdminGovernanceError("Invalid admin write token.", status_code=403)


def permission_matrix_payload() -> dict[str, Any]:
    return {
        "writes_enabled": admin_writes_enabled(),
        "write_token_configured": bool(_configured_write_token()),
        "publication_enabled": False,
        "quick_edit": {
            "allowed_fields": [
                {"field": key, **value}
                for key, value in QUICK_EDIT_FIELDS.items()
            ],
            "blocked_tier_1_fields": list(BLOCKED_TIER_1_FIELDS),
            "audit_store": "governance/admin/quick_edits.jsonl",
            "applies_to": "runtime metadata overlay; published catalogue JSON is not rewritten",
        },
        "roles": list(ROLE_MATRIX),
    }


def _normalise_role(value: str) -> str:
    return "_".join(value.strip().lower().replace("-", "_").split())


def _role_record(role: str) -> dict[str, Any] | None:
    for record in ROLE_MATRIX:
        if record["role"] == role:
            return record
    return None


def _actor_from_payload(payload: dict[str, Any]) -> AdminActor:
    name = str(payload.get("actor_name", "")).strip()
    email = str(payload.get("actor_email", "")).strip().lower()
    role = _normalise_role(str(payload.get("actor_role", "")))
    if not name:
        raise AdminGovernanceError("actor_name is required.")
    if "@" not in email:
        raise AdminGovernanceError("actor_email must identify the editor.")
    if _role_record(role) is None:
        raise AdminGovernanceError("actor_role is not recognised.")
    return AdminActor(name=name, email=email, role=role)


def _quick_edit_path(project_root: Path) -> Path:
    override = os.environ.get(ADMIN_AUDIT_DIR_ENV, "").strip()
    directory = Path(override) if override else project_root / "governance" / "admin"
    return directory / "quick_edits.jsonl"


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _get_course_value(course: CourseFact, field: str) -> str:
    if field == "course_name":
        return course.name
    if field == "course_description":
        return course.description
    if field == "source_page_or_section":
        return str(course.source.get("page_or_section", ""))
    raise AdminGovernanceError(f"{field!r} is not a Tier 1 quick-edit field.")


def _set_course_value(course: CourseFact, field: str, value: str) -> None:
    if field == "course_name":
        course.name = value
        return
    if field == "course_description":
        course.description = value
        return
    if field == "source_page_or_section":
        source = dict(course.source)
        source["page_or_section"] = value
        course.source = source
        return
    raise AdminGovernanceError(f"{field!r} is not a Tier 1 quick-edit field.")


def _validate_quick_edit_payload(
    catalogue: Catalogue,
    payload: dict[str, Any],
) -> tuple[AdminActor, str, str, str, str]:
    actor = _actor_from_payload(payload)
    role = _role_record(actor.role)
    assert role is not None

    field = str(payload.get("field", "")).strip()
    if field not in QUICK_EDIT_FIELDS:
        raise AdminGovernanceError(f"{field or 'field'} is not allowed for Tier 1 quick edits.")
    if field not in role["tier_1_quick_edit"]:
        raise AdminGovernanceError(
            f"{role['label']} may not edit {QUICK_EDIT_FIELDS[field]['label'].lower()}.",
            status_code=403,
        )

    faculty_key = str(payload.get("faculty_key", "")).strip()
    if faculty_key != catalogue.faculty_key:
        raise AdminGovernanceError("faculty_key does not match the loaded catalogue.")

    course_code = str(payload.get("course_code", "")).strip().upper()
    if course_code not in catalogue.courses:
        raise AdminGovernanceError(f"Course {course_code or '(blank)'} is not in {faculty_key}.", status_code=404)

    new_value = str(payload.get("new_value", "")).strip()
    if not new_value:
        raise AdminGovernanceError("new_value is required.")
    max_length = int(QUICK_EDIT_FIELDS[field]["max_length"])
    if len(new_value) > max_length:
        raise AdminGovernanceError(f"new_value must be {max_length} characters or fewer.")

    reason = str(payload.get("reason", "")).strip()
    if len(reason) < 8:
        raise AdminGovernanceError("reason must explain why the edit is being made.")
    if len(reason) > 1000:
        raise AdminGovernanceError("reason must be 1000 characters or fewer.")

    old_value = _get_course_value(catalogue.courses[course_code], field)
    if old_value == new_value:
        raise AdminGovernanceError("new_value is the same as the current value.")
    return actor, course_code, field, old_value, new_value


def append_quick_edit_event(project_root: Path, event: dict[str, Any]) -> Path:
    path = _quick_edit_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n")
    return path


def create_quick_edit_event(
    project_root: Path,
    catalogue: Catalogue,
    payload: dict[str, Any],
) -> dict[str, Any]:
    actor, course_code, field, old_value, new_value = _validate_quick_edit_payload(catalogue, payload)
    event = {
        "schema_version": 1,
        "status": "applied",
        "change_id": f"QE-{uuid4().hex[:12].upper()}",
        "applied_at": _utc_now(),
        "faculty_key": catalogue.faculty_key,
        "course_code": course_code,
        "field": field,
        "field_label": QUICK_EDIT_FIELDS[field]["label"],
        "old_value": old_value,
        "new_value": new_value,
        "reason": str(payload.get("reason", "")).strip(),
        "source": {
            "document": str(payload.get("source_document", "")).strip(),
            "page_or_section": str(payload.get("source_page_or_section", "")).strip(),
        },
        "owner_unit": str(payload.get("owner_unit", "")).strip(),
        "actor": {
            "name": actor.name,
            "email": actor.email,
            "role": actor.role,
        },
        "publication_effect": "runtime_overlay_only",
    }
    event["event_hash"] = _canonical_hash(event)
    append_quick_edit_event(project_root, event)
    _set_course_value(catalogue.courses[course_code], field, new_value)
    return event


def iter_quick_edit_events(project_root: Path) -> Any:
    path = _quick_edit_path(project_root)
    if not path.exists():
        return
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                yield event


def recent_quick_edit_events(project_root: Path, limit: int = 25) -> list[dict[str, Any]]:
    rows: deque[dict[str, Any]] = deque(maxlen=max(1, min(limit, 100)))
    for event in iter_quick_edit_events(project_root) or ():
        rows.append(event)
    return list(reversed(rows))


def apply_quick_edit_overlays(catalogue: Catalogue, project_root: Path) -> int:
    applied = 0
    for event in iter_quick_edit_events(project_root) or ():
        if event.get("status") != "applied":
            continue
        if event.get("faculty_key") != catalogue.faculty_key:
            continue
        course_code = str(event.get("course_code", "")).strip().upper()
        field = str(event.get("field", "")).strip()
        if course_code not in catalogue.courses or field not in QUICK_EDIT_FIELDS:
            continue
        _set_course_value(catalogue.courses[course_code], field, str(event.get("new_value", "")).strip())
        applied += 1
    return applied
