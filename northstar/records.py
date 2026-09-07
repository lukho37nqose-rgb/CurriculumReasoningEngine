"""Read-only synthetic system of record. CRE never owns this storage."""

import json
from pathlib import Path

from .package import INSTITUTION, RELEASE, ROOT


class RecordsUnavailable(ValueError):
    pass


class StudentRecords:
    def __init__(self, path: Path = ROOT / "records/students.json"):
        self.path = path

    def fetch(self, institution_id, subject_reference):
        # Read every time: no canonical student record is cached in CRE or sessions.
        if institution_id != INSTITUTION:
            raise RecordsUnavailable("Record scope is unavailable")
        try:
            records = json.loads(self.path.read_text(encoding="utf-8"))
            matches = [r for r in records if r["person"] == subject_reference and r["issuer"] == institution_id]
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise RecordsUnavailable("Synthetic records service is unavailable") from exc
        if len(matches) != 1 or matches[0].get("edition") != RELEASE:
            raise RecordsUnavailable("Record scope is unavailable")
        return matches[0]
