import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.engine import Model
from app.main import app
from app.network import Roads
from app.state import Conflict, Session


def test_assets_and_posterior_sums_to_one():
    s = Session()
    assert len(s.model.assets) == 44 and len(s.model.transformers) == 8      # 20 on the lines, plus a tap line, pole and fuse before each transformer
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
    s.observe(target, "inconclusive")
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
    # with the road to the Landayan transformer closed, the equipment on that street cannot be reached either
    assert {e["asset_id"] for e in excluded} == {"LS-07", "T-08", "TL-08", "PL-08", "FC-08"}


def test_inspected_place_leaves_the_list_and_cannot_be_recorded_twice():
    s = Session()
    s.observe("F3", "intact", by="Line crew 4")
    assert "F3" not in [r["asset_id"] for r in s.recommendations()[0]]
    assert s.observations[-1]["by"] == "Line crew 4"
    with pytest.raises(Conflict):
        s.observe("F3", "damaged")


def test_inspections_reduce_uncertainty_and_find_the_demo_truth():
    s = Session()

    def check_every_plausible_place():
        for _ in range(20):
            worth = [r for r in s.state()["recommendations"] if r["tier"] != "low"]
            if not worth:
                return
            s.observe(worth[0]["asset_id"], None)

    found = lambda: {o["asset_id"] for o in s.observations if o["result"] == "damaged"}
    check_every_plausible_place()
    # The switch explains San Mateo's outage, so the broken line behind it is not suspected yet.
    assert found() == {"LS-07", "T-03"} and s.state()["resources"]["identified"]
    s.repair("LS-07")                                     # San Mateo stays dark: the second break shows itself
    check_every_plausible_place()
    assert found() == {"LS-07", "L2", "T-03"}
    assert int(np.argmax(s.posterior())) == s.truth
    assert s.history[-1]["pct"] < 30


def test_api_flow():
    c = TestClient(app)
    c.post("/api/reset", json={})
    st = c.get("/api/state").json()
    top = st["recommendations"][0]
    assert c.get(f"/api/recommendations/{top['asset_id']}/explain").json()["if_damaged"]["scenarios"]
    assert "crews" not in st and top["from"] in ("Pasig office", "Pasay office")
    r = c.post("/api/observations", json={"asset_id": top["asset_id"], "result": "intact"})
    assert r.status_code == 200 and r.json()["state"]["log"][0]["result"] == "intact"
    assert c.post("/api/observations", json={"asset_id": top["asset_id"], "result": "damaged"}).status_code == 409
    assert c.post("/api/roads/nope/block").status_code == 404
