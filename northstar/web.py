"""Demo orchestration: identity -> records -> adapter -> existing analysis boundary."""

import json
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from curriculum_advisor.legibility import requirement_instructions
from curriculum_reasoning_engine.institutions import register_institution_release
from engine.registration import (
    RegistrationHistoryCoverage,
    RegistrationHistoryEvidence,
    evaluate_registration_duration,
)

from .adapter import adapt
from .identity import SUBJECTS, DemoIdentity
from .package import INSTITUTION, PROGRAMME, RELEASE, ROOT, read_package, release
from .records import RecordsUnavailable, StudentRecords

COOKIE = "northstar_demo_session"


def install(app, analyse, *, identity=None, records=None):
    identity = identity or DemoIdentity()
    records = records or StudentRecords()
    selected_release = release()
    register_institution_release(selected_release)
    router = APIRouter()

    def session(request):
        try:
            return identity.resolve(request.cookies.get(COOKIE))
        except ValueError as exc:
            raise HTTPException(401, "Please log into a Northstar demo account") from exc

    def response(payload):
        return JSONResponse(payload, headers={"Cache-Control": "no-store"})

    @router.get("/northstar")
    async def page():
        return FileResponse(Path(__file__).resolve().parents[1] / "static/northstar.html", headers={"Cache-Control": "no-store"})

    @router.get("/api/northstar/accounts")
    async def accounts():
        return response({"subjects": SUBJECTS, "synthetic": True})

    @router.get("/api/northstar/presentation")
    async def presentation():
        config = json.loads((ROOT / "presentation.json").read_text(encoding="utf-8"))
        config["course_titles"] = {row["code"]: row["name"] for row in read_package("courses.json")}
        rules = read_package("degree_requirements.json")["programmes"][PROGRAMME]["curriculum_rules"]
        config["requirement_instructions"] = {
            f"curriculum:{rule['id']}": requirement_instructions(rule, config["course_titles"]) for rule in rules
        }
        config["requirement_titles"] = {**{f"curriculum:{rule['id']}": rule["label"] for rule in rules},
                                         **config.get("requirement_titles", {})}
        cases = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))
        return response({"config": config, "cases": [{"subject": row["subject"], "label": row["purpose"]} for row in cases]})

    @router.get("/api/northstar/rules/{record_id}")
    async def registry_record(record_id: str):
        for record in read_package("registry.json"):
            if record["record_id"] == record_id:
                return response(record)
        raise HTTPException(404, "Unknown synthetic registry record")

    @router.post("/api/northstar/login")
    async def login(body: dict, request: Request):
        try:
            token = identity.login(body.get("subject"), body.get("access_code", ""))
        except ValueError as exc:
            raise HTTPException(401, "Unknown demo account or access code") from exc
        identity.logout(request.cookies.get(COOKIE))
        current = identity.resolve(token)
        result = response({"subject_reference": current.subject_reference, "institution_id": current.institution_id,
                           "launch_request_id": current.launch_request_id, "synthetic": True})
        result.set_cookie(COOKIE, token, httponly=True, samesite="strict", max_age=identity.lifetime, path="/api/northstar")
        return result

    @router.post("/api/northstar/logout")
    async def logout(request: Request):
        identity.logout(request.cookies.get(COOKIE))
        result = response({"logged_out": True})
        result.delete_cookie(COOKIE, path="/api/northstar")
        return result

    @router.post("/api/northstar/analyse")
    async def workspace(request: Request):
        current = session(request)
        try:
            native = records.fetch(current.institution_id, current.subject_reference)
            converted = adapt(native, current)
        except (RecordsUnavailable, ValueError) as exc:
            raise HTTPException(503, "The synthetic record could not be retrieved for this session. No conclusion was made.") from exc
        raw = await analyse(converted.body)
        report = json.loads(raw.body)
        # Retrieval receipts describe transport only, not use or applicability.
        academic_supplied = any(r["domain"] == "academic" and r["state"] == "RECEIVED" for r in converted.domain_receipt)
        for name in ("student_reasoning_view", "advisor_reasoning_view"):
            receipt = report[name]["evidence_receipt"]
            receipt["academic_record"] = "RECEIVED" if academic_supplied else "NOT_SUPPLIED"
            entry = next(e for e in receipt["entries"] if e["category"] == "academic_record")
            entry.update(supplied=academic_supplied, receipt_state=receipt["academic_record"])
        duration = None
        if converted.body.get("registration_history"):
            binding = dict(student_id=current.subject_reference, institution_id=INSTITUTION, release_id=RELEASE)
            entries = tuple(RegistrationHistoryEvidence(**row, **binding) for row in converted.body["registration_history"])
            coverage = tuple(RegistrationHistoryCoverage(**row, **binding) for row in converted.body.get("registration_history_coverage", []))
            duration = asdict(evaluate_registration_duration(entries, coverage, **binding,
                period_scheme=selected_release.period_scheme, programme_key=PROGRAMME, count_basis="active_academic_cycles"))
        return response({"subject_reference": current.subject_reference, "institution_id": INSTITUTION, "release_id": RELEASE,
                         "retrieval": converted.domain_receipt, "report": report,
                         "registration_duration": duration, "synthetic": True})

    app.include_router(router)
    return identity, records
