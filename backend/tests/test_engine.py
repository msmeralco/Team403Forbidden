import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.engine import Model
from app.main import app
from app.network import Roads
from app.simulation import evaluate
from app.state import Conflict, Session


def test_twenty_assets_and_posterior_sums_to_one():
    s = Session()
    assert len(s.model.assets) == 20
    assert s.posterior().sum() == pytest.approx(1.0)


def test_intact_lowers_scenarios_containing_the_asset():
    m = Model()
    reported = m.OUT[m.scenarios.index((m.idx["F3"],))]
    before = m.posterior(reported)
    after = m.posterior(reported, [(m.idx["F3"], "intact")])
    has_f3 = m.F[:, m.idx["F3"]]
    assert after[has_f3].sum() < before[has_f3].sum()


def test_damaged_raises_scenarios_containing_the_asset():
    m = Model()
    reported = m.OUT[m.scenarios.index((m.idx["F3"],))]
    before, after = m.posterior(reported), m.posterior(reported, [(m.idx["F3"], "damaged")])
    assert m.marginals(after)[m.idx["F3"]] > m.marginals(before)[m.idx["F3"]]


def test_inconclusive_changes_nothing_and_keeps_asset_eligible():
    s = Session()
    before = s.posterior()
    target = s.recommendations()[0][0]["asset_id"]
    s.assign("crew-1", target)
    s.observe("crew-1", target, "inconclusive")
    assert np.allclose(before, s.posterior())
    assert target in [r["asset_id"] for r in s.recommendations()[0]]


def test_blocked_road_changes_travel_and_can_isolate():
    open_roads, roads = Roads(blocked=()), Roads(blocked=())
    roads.set_blocked("F3~LS-07", True)
    assert roads.minutes("SUB", "LS-07") > open_roads.minutes("SUB", "LS-07")
    roads.set_blocked("LS-05~T-08", True)
    assert roads.minutes("SUB", "T-08") is None


def test_restricted_and_inaccessible_assets_are_not_recommended():
    s = Session()
    s.restrict("LS-07", True)
    s.block_road("LS-05~T-08", True)
    recs, excluded = s.recommendations()
    ids = [r["asset_id"] for r in recs]
    assert "LS-07" not in ids and "T-08" not in ids
    assert {e["asset_id"] for e in excluded} == {"LS-07", "T-08"}


def test_engine_never_assigns_on_its_own_and_guards_assignments():
    s = Session()
    assert all(c.asset_id is None for c in s.crews)
    s.assign("crew-1", "F3")
    with pytest.raises(Conflict):
        s.assign("crew-2", "F3")
    with pytest.raises(Conflict):
        s.observe("crew-2", "F3", "intact")


def test_inspections_reduce_uncertainty_and_find_the_demo_truth():
    s = Session()
    for _ in range(12):
        recs, _ = s.recommendations()
        if s.resources(s.posterior())["identified"] or not recs:
            break
        s.assign(recs[0]["crew_id"], recs[0]["asset_id"])
        s.observe(recs[0]["crew_id"], recs[0]["asset_id"], None)
    assert s.resources(s.posterior())["identified"]
    assert int(np.argmax(s.posterior())) == s.truth
    assert s.history[-1]["pct"] < 30


def test_firstlook_matches_or_beats_baselines():
    res = evaluate(runs=200, seed=1)
    by = {x["key"]: x for x in res["strategies"]}
    assert by["firstlook"]["total_min"] <= by["nearest"]["total_min"]
    assert by["firstlook"]["total_min"] <= by["fixed"]["total_min"]


def test_api_flow():
    c = TestClient(app)
    c.post("/api/reset", json={})
    st = c.get("/api/state").json()
    top = st["recommendations"][0]
    assert c.get(f"/api/recommendations/{top['asset_id']}/explain").json()["if_damaged"]["scenarios"]
    assert c.post(f"/api/crews/{top['crew_id']}/assign", json={"asset_id": top["asset_id"]}).status_code == 200
    assert c.post("/api/crews/crew-2/assign", json={"asset_id": top["asset_id"]}).status_code == 409
    r = c.post("/api/observations", json={"asset_id": top["asset_id"], "crew_id": top["crew_id"], "result": "intact"})
    assert r.status_code == 200 and r.json()["state"]["log"][0]["result"] == "intact"
    assert c.post("/api/roads/nope/block").status_code == 404
