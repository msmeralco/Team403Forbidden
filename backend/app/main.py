"""FIRSTLOOK API. Run with: uvicorn app.main:app --reload (from the backend folder)."""
from typing import Literal

import base64
import binascii

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import ai, case_reports, cases, liwa
from .config import CONFIG
from .reports import SOURCES
from .state import Conflict, NeedsPlace, Session

app = FastAPI(title="FIRSTLOOK", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
                    allow_methods=["*"], allow_headers=["*"])

_current = {"session": Session()}
liwa.warm(_current["session"])            # load the embedding model and index the storm in the background


def s() -> Session:
    return _current["session"]


# Stand-in photos that residents "attached" in the demo storm (see photos/CREDITS.md).
app.mount("/api/photos", StaticFiles(directory=ai.PHOTOS), name="photos")


@app.exception_handler(NeedsPlace)
async def needs_place(_: Request, exc: NeedsPlace):
    return JSONResponse(status_code=409, content={"detail": str(exc), "need": "area"})


@app.exception_handler(Conflict)
async def conflict(_: Request, exc: Conflict):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(KeyError)
async def not_found(_: Request, exc: KeyError):
    return JSONResponse(status_code=404, content={"detail": str(exc.args[0])})


class Observation(BaseModel):
    asset_id: str
    result: Literal["damaged", "intact", "inconclusive"] | None = None   # None = simulate from ground truth
    notes: str = ""
    by: str = ""     # who reported it, e.g. "Line crew 4" (optional)


class Priority(BaseModel):
    weight: float = Field(ge=0.1, le=5)


class Reset(BaseModel):
    seed: int | None = None


@app.get("/api/state")
def state():
    return s().state()


@app.get("/api/network")
def network():
    st = s().state()
    return {k: st[k] for k in ("substation", "assets", "roads")}


@app.get("/api/reports")
def reports():
    """Every community report in this storm, newest first, with the channel catalogue."""
    return {"event_id": s().id, "sources": SOURCES, "reports": s().reports}


@app.get("/api/liwa")
def liwa_status():
    """Whether Liwa can reach Claude Code, what is indexed (reference documents included), and a one-paragraph brief."""
    return liwa.status(s())


@app.get("/api/liwa/plan")
def liwa_plan(force: bool = False):
    """The inspection plan for the storm as it stands. Rewritten only when something changed, or when forced."""
    return liwa.plan(s(), force)


@app.get("/api/cases")
def list_cases():
    """The test cases (backend/cases/meralco_demo.sqlite) with their jobs, expected answers and any decision made so far."""
    made = liwa.decided()
    return {"cases": [{**c, "place": case_reports.place_of(i), "decision": made.get(c["id"])} for i, c in enumerate(cases.all_cases())],
            "tiers": cases.tiers() if cases.available() else {}, "generator": liwa.generator(), "model": liwa.CLAUDE_MODEL}


@app.get("/api/cases/{case_id}/reports")
def case_reports_for(case_id: str):
    """What customers reported about one interruption: invented messages, linked to the equipment each is about."""
    case = cases.find(case_id)
    if case is None:
        raise KeyError(f"No test case {case_id}")
    found = case_reports.for_case(case)
    return {"case_id": case_id, "channels": case_reports.CHANNELS, "summary": case_reports.summary(found), "reports": found}


@app.get("/api/cases/{case_id}/decision")
def case_decision(case_id: str, force: bool = False):
    """Liwa's recommendation for one test case: retrieve the guidance, decide, and compare with the expected answer."""
    return liwa.decide(case_id, force)


class Photo(BaseModel):
    data: str                                                    # base64, without the data: prefix
    media_type: Literal["image/jpeg", "image/png", "image/webp"]


class NewReport(BaseModel):
    text: str = Field(default="", max_length=600)
    source: Literal["facebook_post", "facebook_comment", "x", "sms", "hotline", "app"] = "facebook_post"
    area_id: str | None = None
    photo: Photo | None = None      # a photo the presenter uploads
    sample: str | None = None       # or one of the bundled stand-in photos, by file name


MAX_PHOTO_BYTES = 4 * 1024 * 1024


@app.post("/api/reports")
def add_report(body: NewReport):
    """Type in a message as if a resident had sent it. It is read, mapped and counted."""
    photo = None
    if body.photo:
        try:
            raw = base64.b64decode(body.photo.data, validate=True)
        except (binascii.Error, ValueError):
            return JSONResponse(status_code=400, content={"detail": "That photo could not be read."})
        if len(raw) > MAX_PHOTO_BYTES:
            return JSONResponse(status_code=413, content={"detail": "That photo is larger than 4 MB. Try a smaller one."})
        photo = (raw, body.photo.media_type)
    out = s().add_report(body.text, body.source, body.area_id, photo, body.sample)
    return {**out, "state": s().state()}


@app.get("/api/reports/{report_id}/photo")
def report_photo(report_id: str):
    if report_id not in s().uploads:
        raise KeyError(f"No photo for {report_id}")
    raw, media_type = s().uploads[report_id]
    return Response(content=raw, media_type=media_type)


class Hazard(BaseModel):
    handled: bool = True


@app.post("/api/areas/{area_id}/hazard")
def hazard(area_id: str, body: Hazard):
    s().set_hazard(area_id, body.handled)
    return s().state()


@app.get("/api/scenarios")
def scenarios(limit: int = 20):
    return s().scenarios(limit)


@app.get("/api/recommendations")
def recommendations():
    recs, excluded = s().recommendations()
    return {"recommendations": recs, "excluded": excluded}


@app.get("/api/recommendations/{asset_id}/explain")
def explain(asset_id: str):
    return s().explain(asset_id)


@app.get("/api/observations")
def observations():
    return s().observations


@app.post("/api/observations")
def observe(body: Observation):
    obs = s().observe(body.asset_id, body.result, body.notes, body.by)
    return {"observation": obs, "state": s().state()}


@app.post("/api/roads/{edge_id}/block")
def block(edge_id: str):
    s().block_road(edge_id, True)
    return s().state()


@app.post("/api/roads/{edge_id}/unblock")
def unblock(edge_id: str):
    s().block_road(edge_id, False)
    return s().state()


@app.post("/api/assets/{asset_id}/restrict")
def restrict(asset_id: str):
    s().restrict(asset_id, True)
    return s().state()


@app.post("/api/assets/{asset_id}/unrestrict")
def unrestrict(asset_id: str):
    s().restrict(asset_id, False)
    return s().state()


class Repair(BaseModel):
    by: str = ""


@app.post("/api/assets/{asset_id}/repaired")
def repaired(asset_id: str, body: Repair):
    """Mark confirmed damage as repaired; residents behind it then report whether power came back."""
    s().repair(asset_id, body.by)
    return s().state()


@app.post("/api/assets/{asset_id}/priority")
def priority(asset_id: str, body: Priority):
    s().set_priority(asset_id, body.weight)
    return s().state()


@app.get("/api/config")
def config():
    return CONFIG.as_dict()


@app.get("/api/truth")
def truth():
    """Demo only: reveal the hidden ground-truth scenario."""
    m = s().model
    return {"label": m.label(s().truth), "assets": [m.ids[i] for i in m.scenarios[s().truth]]}


@app.post("/api/reset")
def reset(body: Reset):
    _current["session"].alive = False        # stop the old storm's AI reader
    _current["session"] = Session(seed=body.seed)
    liwa.warm(s())
    return s().state()
