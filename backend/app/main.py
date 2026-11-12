"""FIRSTLOOK API. Run with: uvicorn app.main:app --reload (from the backend folder)."""
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .config import CONFIG
from .simulation import evaluate
from .state import Conflict, Session

app = FastAPI(title="FIRSTLOOK", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
                    allow_methods=["*"], allow_headers=["*"])

_current = {"session": Session()}



def s() -> Session:
    return _current["session"]


@app.exception_handler(Conflict)
async def conflict(_: Request, exc: Conflict):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(KeyError)
async def not_found(_: Request, exc: KeyError):
    return JSONResponse(status_code=404, content={"detail": str(exc.args[0])})


class Assign(BaseModel):
    asset_id: str


class Observation(BaseModel):
    asset_id: str
    crew_id: str
    result: Literal["damaged", "intact", "inconclusive"] | None = None   # None = simulate from ground truth
    notes: str = ""


class Priority(BaseModel):
    weight: float = Field(ge=0.1, le=5)


class Reset(BaseModel):
    seed: int | None = None


class Evaluate(BaseModel):
    runs: int = Field(default=200, ge=10, le=1000)
    seed: int = 1


@app.get("/api/state")
def state():
    return s().state()


@app.get("/api/network")
def network():
    st = s().state()
    return {k: st[k] for k in ("substation", "assets", "roads")}


@app.get("/api/reports")
def reports():
    return [{"asset_id": a["id"], "count": a["reports"]} for a in s().state()["assets"] if a["reports"]]


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
    obs = s().observe(body.crew_id, body.asset_id, body.result, body.notes)
    return {"observation": obs, "state": s().state()}


@app.get("/api/crews")
def crews():
    return s().crews_view()


@app.post("/api/crews/{crew_id}/assign")
def assign(crew_id: str, body: Assign):
    s().assign(crew_id, body.asset_id)  
    return s().state()


@app.post("/api/crews/{crew_id}/unassign")
def unassign(crew_id: str):
    s().unassign(crew_id)
    return s().state()


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
    _current["session"] = Session(seed=body.seed)
    return s().state()


@app.post("/api/evaluate")
def run_evaluation(body: Evaluate):
    return evaluate(body.runs, body.seed, s().roads)
