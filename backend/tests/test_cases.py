"""Test cases: a typhoon first, then the interruptions that follow, loaded stage by stage."""
import json

import pytest
from fastapi.testclient import TestClient

from app import cases
from app.main import app
from app.state import Session


def test_the_example_case_is_valid():
    found, errors = cases.load_all()
    assert not errors
    example = next(c for c in found if c["id"] == "example-typhoon-then-interruptions")
    assert [s["kind"] for s in example["stages"]] == ["typhoon", "interruption", "interruption"]
    shown = cases.summary(example, 2)
    assert shown["stage"] == 2 and "damaged" not in json.dumps(shown)      # what is damaged stays hidden from the screen


def test_a_stage_starts_a_storm_with_exactly_that_damage():
    s = Session(scenario={"name": "Interruption in Bacoor", "kind": "interruption", "damaged": ["T-07"],
                          "reports": {"bac-talaba": 16, "bac-niog": 9}, "hazards": {}, "seed": 3})
    assert sorted(s.model.ids[i] for i in s.model.scenarios[s.truth]) == ["T-07"]
    st = s.state()
    assert st["event"]["name"] == "Interruption in Bacoor" and st["event"]["kind"] == "interruption"
    people = {a["id"]: a["people"] for a in st["areas"] if a["people"]}
    assert people == {"bac-talaba": 16, "bac-niog": 9} and st["summary"]["hazards_open"] == 0
    top = st["recommendations"][0]
    assert "bac-talaba" in [a["id"] for a in top["covers"]["areas"]]


def test_details_left_out_are_simulated_and_repeatable():
    a = Session(scenario={"damaged": ["L1"], "seed": 5})
    b = Session(scenario={"damaged": ["L1"], "seed": 5})
    assert a.state()["summary"]["reports"] == b.state()["summary"]["reports"] > 0
    with_hazard = Session(scenario={"damaged": ["L1"], "hazards": {"val-karuhatan": "pole_down"}, "seed": 5}).state()
    assert with_hazard["summary"]["hazards_open"] == 1 and with_hazard["recommendations"][0]["tier"] == "critical"


@pytest.mark.parametrize("stage, message", [
    ({"damaged": []}, "1 to 3 equipment ids"),
    ({"damaged": ["T-01", "T-02", "T-03", "T-04"]}, "1 to 3 equipment ids"),
    ({"damaged": ["NOPE"]}, "unknown equipment NOPE"),
    ({"damaged": ["T-01"], "kind": "earthquake"}, '"kind" must be one of'),
    ({"damaged": ["T-01"], "hazards": {"qc-central": "flood"}}, "hazards must map"),
    ({"damaged": ["T-01"], "reports": {"nowhere": 3}}, "reports must map"),
])
def test_bad_case_files_are_reported_not_loaded(tmp_path, stage, message):
    (tmp_path / "bad.json").write_text(json.dumps({"stages": [stage]}), encoding="utf-8")
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    found, errors = cases.load_all(tmp_path)
    assert found == [] and len(errors) == 2
    assert any(e.startswith("bad.json: stage 1") and message in e for e in errors)
    assert any(e.startswith("broken.json: not valid JSON") for e in errors)


def test_stages_load_through_the_api_and_the_plan_follows():
    c = TestClient(app)
    listed = c.get("/api/cases").json()
    case = next(x for x in listed["cases"] if x["id"] == "example-typhoon-then-interruptions")
    assert len(case["stages"]) == 3 and listed["errors"] == []
    first = c.post(f"/api/cases/{case['id']}/stages/1").json()
    assert first["case"]["stage"] == 1 and first["event"]["name"] == "Typhoon Dalisay"
    second = c.post(f"/api/cases/{case['id']}/stages/2").json()
    assert second["case"]["stage"] == 2 and second["event"]["kind"] == "interruption" and second["event"]["id"] != first["event"]["id"]
    assert not second["log"] and not second["repaired"]                # a stage starts fresh
    plan = c.get("/api/liwa/plan").json()
    assert plan["storm"] == second["event"]["id"] and plan["steps"]
    assert c.get("/api/cases").json()["current"]["stage"] == 2
    assert c.post(f"/api/cases/{case['id']}/stages/9").status_code == 404
    assert c.post("/api/cases/nope/stages/1").status_code == 404
    assert c.post("/api/reset", json={}).json()["case"] is None
