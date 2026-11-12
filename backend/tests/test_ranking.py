"""The ranking rule: safety, essential facilities, network level, customers, reports, access."""
from app.state import Session, essential_weight

LEVEL = {"critical": 0, "high": 1, "medium": 1, "low": 2}


def test_order_is_safety_then_essential_then_homes():
    recs = Session().recommendations()[0]
    assert recs[0]["tier"] == "critical" and recs[0]["basis"]["safety"]
    keys = [(LEVEL[r["tier"]], -r["basis"]["essential_score"], r["basis"]["level"], -r["basis"]["predicted_accounts"],
             -r["basis"]["reported_people"], r["travel_min"]) for r in recs]
    assert keys == sorted(keys)
    assert [r["rank"] for r in recs] == list(range(1, len(recs) + 1))


def test_a_place_feeding_a_hospital_outranks_one_with_more_reports_but_no_essential_site():
    recs = [r for r in Session().recommendations()[0] if r["tier"] in ("high", "medium")]
    with_site = [r for r in recs if r["basis"]["essential_score"]]
    without = [r for r in recs if not r["basis"]["essential_score"]]
    assert with_site and all(r["tier"] == "high" for r in with_site) and all(r["tier"] == "medium" for r in without)
    if without:
        assert max(r["rank"] for r in with_site) < min(r["rank"] for r in without)


def test_basis_shows_reported_and_predicted_homes():
    s = Session()
    for r in s.recommendations()[0]:
        b = r["basis"]
        assert b["reported_people"] == r["covers"]["people"] and b["predicted_accounts"] >= 0 and 0 <= b["p_damaged"] <= 1
        assert all(e["weight"] == essential_weight(e["name"]) for e in b["essential"])
    top_essential = next(r for r in s.recommendations()[0] if r["tier"] == "high")
    assert "likely without power" in top_essential["headline"]


def test_upstream_equipment_comes_before_what_it_feeds_when_the_same_essential_sites_depend_on_both():
    recs = {r["asset_id"]: r for r in Session().recommendations()[0]}
    line, switch = recs["F3"], recs["LS-07"]                     # the main line and the switch on it feed the same hospital
    assert line["basis"]["essential_score"] == switch["basis"]["essential_score"] > 0
    assert (line["basis"]["level"], line["basis"]["level_label"]) == (1, "Main line") and switch["basis"]["level"] == 2
    assert line["rank"] < switch["rank"]
    assert line["basis"]["load_mw"] == round(line["basis"]["predicted_accounts"] * 0.5 / 1000, 1) > 0


def test_a_place_the_evidence_points_away_from_waits_at_the_bottom():
    s = Session()
    s.observe("T-03", "damaged")
    s.observe("LS-07", "damaged")
    s.repair("LS-07")                                   # Antipolo comes back, so the main line feeding the switch is live
    recs = {r["asset_id"]: r for r in s.recommendations()[0]}
    assert recs["F3"]["basis"]["p_damaged"] < 0.05 and recs["F3"]["tier"] == "low"
    assert recs["L2"]["rank"] == 1 and recs["L2"]["basis"]["p_damaged"] > 0.5
    assert all(r["basis"]["p_damaged"] >= 0.05 or r["hazard"] for r in recs.values() if r["tier"] != "low")


def test_essential_weights():
    assert essential_weight("District hospital") == 3
    assert essential_weight("Elementary school (evacuation center)") == 2
    assert essential_weight("Water pumping station") == 2 and essential_weight("Public market") == 1


def test_safety_drops_out_once_the_hazard_is_made_safe():
    s = Session()
    assert s.recommendations()[0][0]["asset_id"] == "T-03"
    s.set_hazard("mey-malhacan", True)
    top = s.recommendations()[0][0]
    assert top["tier"] == "high" and not top["basis"]["safety"]
