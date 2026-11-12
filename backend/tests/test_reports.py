import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.engine import Model
from app.main import app
from app.network import AREAS
from app.reports import classify
from app.state import Conflict, Session


def test_more_people_reporting_is_stronger_evidence():
    m = Model()
    p_out, p_fine = m.voice_likelihoods(np.array([1, 5, 20, 60, 1, 5, 20, 60]))
    ratio = p_out / p_fine
    assert ratio[1] > ratio[0] and ratio[2] > ratio[1] and ratio[3] > ratio[2]


def test_more_people_reporting_raises_urgency():
    s = Session()
    row, i = s.row_of["T-06"], s.model.idx["T-06"]
    before = s.urgency(s.posterior())[i]
    s.voices[row] = 60
    assert s.urgency(s.posterior())[i] > before


def test_urgency_has_diminishing_returns():
    s = Session()
    i, row = s.model.idx["T-06"], s.row_of["T-06"]
    levels = []
    for k in (10, 20, 200, 210):
        s.voices[row] = k
        levels.append(s.urgency(s.posterior())[i])
    assert levels[1] - levels[0] > levels[3] - levels[2]


def test_safety_hazard_is_pinned_first_until_made_safe():
    s = Session()
    top = s.recommendations()[0][0]
    assert top["asset_id"] == "T-03" and top["tier"] == "critical" and top["hazard"]
    s.set_hazard("mey-malhacan", True)
    top = s.recommendations()[0][0]
    assert not top["hazard"] and top["tier"] != "critical"


def test_site_visit_takes_over_the_hazard():
    s = Session()
    s.observe("T-03", "damaged")
    assert "mey-malhacan" in s.hazard_handled
    assert not any(a["hazard_open"] for a in s.state()["areas"])


def test_one_person_on_several_channels_counts_once():
    s = Session()
    people = {r["person_id"] for r in s.reports}
    assert len(s.reports) > len(people) == int(s.voices.sum())
    assert {r["source"] for r in s.reports} == {"facebook_post", "facebook_comment", "x", "sms", "hotline", "app"}


def test_quiet_area_is_flagged():
    areas = {a["id"]: a for a in Session().state()["areas"]}
    assert areas["rod-burgos"]["quiet"] and not areas["ant-san-roque"]["quiet"]


@pytest.mark.parametrize("text, category, tag", [
    ("May live wire na nakalaylay sa kalsada dito sa Malhacan!", "hazard", "live_wire"),
    ("Nag-spa-spark yung linya sa poste, may usok na", "hazard", "fire"),
    ("Natumba yung poste ng Meralco dito sa amin", "hazard", "pole_down"),
    ("May pumutok na transformer dito kagabi", "clue", "transformer"),
    ("May puno na bumagsak sa linya dito", "clue", "tree"),
    ("Kami lang walang kuryente, yung kapitbahay meron", "noise", "single_house"),
    ("Kami lang ba walang kuryente? Buong street namin patay", "outage", None),
    ("Patay-sindi kuryente sa amin kanina pa", "noise", "flicker"),
    ("Brownout pa rin dito sa Brgy. San Roque", "outage", None),
])
def test_keyword_triage(text, category, tag):
    out = classify(text)
    assert out["category"] == category and out["tag"] == tag


def test_vulnerable_household_is_noticed():
    assert classify("May matanda po kaming kasama na naka-nebulizer")["vulnerable"]


@pytest.mark.parametrize("seed", [1, 2, 3, 11, 42])
def test_random_storms_are_consistent(seed):
    s = Session(seed=seed)
    st = s.state()
    assert st["summary"]["people"] == len({r["person_id"] for r in s.reports}) > 0
    assert st["recommendations"] and len(st["areas"]) == 24
    assert s.posterior().sum() == pytest.approx(1.0)


def test_reports_and_hazard_api():
    c = TestClient(app)
    c.post("/api/reset", json={})
    body = c.get("/api/reports").json()
    assert len(body["reports"]) > 200 and "hotline" in body["sources"]
    st = c.post("/api/areas/mey-malhacan/hazard", json={"handled": True}).json()
    assert st["summary"]["hazards_open"] == 0
    assert c.post("/api/areas/ant-san-roque/hazard", json={"handled": True}).status_code == 409
    assert c.post("/api/areas/nowhere/hazard", json={"handled": True}).status_code == 404


def test_account_counts_come_from_records_not_guesses():
    s = Session()
    f3 = next(r for r in s.recommendations()[0] if r["asset_id"] == "F3")
    served = sum(a.households for a in AREAS if a.transformer in ("T-04", "T-05", "T-06"))
    assert f3["covers"]["accounts"] == served
    assert "homes_out" not in s.state()["summary"]


def test_repair_reveals_a_hidden_second_break():
    # Fix the Marcos Hwy switch before anyone checks the Gen. Luna Ave line behind it.
    s = Session()
    s.observe("T-03", "damaged")
    s.observe("LS-07", "damaged")
    s.repair("LS-07")
    st = s.state()
    areas = {a["id"]: a for a in st["areas"]}
    assert areas["ant-san-roque"]["restored"]                         # Antipolo is back
    assert areas["sm-guitnang-bayan"]["p_out"] >= 0.5                 # San Mateo still dark
    assert st["recommendations"][0]["asset_id"] in ("L2", "T-05", "T-06")
    assert any(r.get("after_repair") and r["category"] == "restored" for r in s.reports)
    assert any(r.get("after_repair") and r["category"] != "restored" for r in s.reports)


def test_handoff_blocks_repairs_behind_unrepaired_damage():
    s = Session()
    s.observe("LS-07", "damaged")
    s.observe("L2", "damaged")
    hand = {h["asset_id"]: h for h in s.state()["handoff"]}
    assert hand["L2"]["blocked_by"] == ["Switch on Marcos Hwy"] and not hand["LS-07"]["blocked_by"]
    assert hand["LS-07"]["restores"]["still_dark"]                   # warns San Mateo stays dark
    with pytest.raises(Conflict):
        s.repair("L2")
    with pytest.raises(Conflict):
        s.repair("F3")                                                # nothing confirmed there


def test_after_repair_messages_do_not_count_as_outage_reports():
    s = Session()
    before = {a["id"]: a["people"] for a in s.state()["areas"]}
    s.observe("T-03", "damaged")
    s.repair("T-03")
    after = {a["id"]: a for a in s.state()["areas"]}
    assert after["mey-malhacan"]["people"] == before["mey-malhacan"]
    assert after["mey-malhacan"]["restored_msgs"] > 0 and after["mey-malhacan"]["restored"]
