"""The dispatch test cases (backend/cases/meralco_demo.sqlite) and Liwa's decision on them.

These tests run offline: no Claude Code, no embedding model (see conftest.py)."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import ai, case_reports, cases, knowledge, liwa
from app.main import app

REFERENCE = Path(__file__).resolve().parents[1] / "reference"


@pytest.fixture()
def guidance(monkeypatch):
    """Point Liwa at the real reference folder (the tests otherwise use an empty one)."""
    monkeypatch.setattr(liwa, "REFERENCE", REFERENCE)
    liwa._decisions.clear()
    yield
    monkeypatch.undo()
    liwa._decisions.clear()
    liwa.store().sync("reference", [], liwa.embedder())


def test_the_cases_load_with_their_jobs_and_expected_answers():
    found = cases.all_cases()
    assert [c["id"] for c in found] == [f"case-{n:02d}" for n in range(1, 14)]
    first = found[0]
    assert first["title"] == "Safety first" and first["expected"] == {
        "action": "DISPATCH", "pole_id": "P-EVAC", "reason": "Send the truck to the evacuation center pole and hold the hospital pole job."}
    supplied = [j for j in first["jobs"] if not j["extra"]]
    assert {j["pole_id"]: (j["safety"], j["tier_name"]) for j in supplied} == {"P-EVAC": ("safe", "Critical"), "P-HOSP": ("unsafe", "Critical")}
    assert sum(not j["extra"] for c in found for j in c["jobs"]) == 30
    assert cases.tiers() == {1: "Critical", 2: "Community services", 3: "Residential"}


def test_the_databases_own_rule_gives_every_expected_answer():
    for c in cases.all_cases():
        assert (c["rule"]["action"], c["rule"]["pole_id"]) == (c["expected"]["action"], c["expected"]["pole_id"]), c["id"]


def test_extra_poles_give_every_case_more_to_rank_without_changing_an_answer():
    found = cases.all_cases()
    assert all(10 <= len(c["jobs"]) <= 11 for c in found), [(c["id"], len(c["jobs"])) for c in found]
    assert {j["equipment"] for c in found for j in c["jobs"]} == {"pole", "transformer", "line"}
    assert all(j["equipment"] == "pole" for c in found for j in c["jobs"] if not j["extra"])
    assert all(any(j["extra"] for j in c["jobs"]) for c in found)
    for c in found:                                            # the rule is recomputed over all the poles, added ones included
        assert (c["rule"]["action"], c["rule"]["pole_id"]) == (c["expected"]["action"], c["expected"]["pole_id"]), c["id"]
        assert len(c["rule"]["order"]) == len(set(c["rule"]["order"]))
    by_id = {c["id"]: c for c in found}
    assert len(by_id["case-01"]["rule"]["order"]) == 8 and by_id["case-08"]["rule"]["order"] == []


def test_without_the_extra_poles_the_cases_are_as_supplied(monkeypatch):
    monkeypatch.setattr(cases, "EXTRA", None)
    cases.reload()
    try:
        found = cases.all_cases()
        assert sum(len(c["jobs"]) for c in found) == 30 and not any(j["extra"] for c in found for j in c["jobs"])
        assert all((c["rule"]["action"], c["rule"]["pole_id"]) == (c["expected"]["action"], c["expected"]["pole_id"]) for c in found)
    finally:
        monkeypatch.undo()
        cases.reload()


def test_a_bad_extra_row_is_left_out(monkeypatch, tmp_path):
    extra = tmp_path / "extra.json"
    extra.write_text(json.dumps({"poles": {"case-01": [
        {"pole_id": "P-OK", "facility_label": "Public market", "tier": 2, "customers_restored": 3, "report_count": 1, "eta_seconds": 60},
        {"pole_id": "P-BAD-TIER", "facility_label": "Nowhere", "tier": 9, "customers_restored": 3, "report_count": 1},
        {"facility_label": "No id", "tier": 2, "customers_restored": 3, "report_count": 1}], "case-99": [{"pole_id": "P-X"}]}}), encoding="utf-8")
    monkeypatch.setattr(cases, "EXTRA", extra)
    cases.reload()
    try:
        first = cases.find("case-01")
        assert [j["pole_id"] for j in first["jobs"] if j["extra"]] == ["P-OK"] and len(first["jobs"]) == 3
    finally:
        monkeypatch.undo()
        cases.reload()


def test_the_file_is_never_written_to():
    before = cases.DB.read_bytes()
    cases.all_cases()
    with cases._lock:                                          # even a write to the working copy leaves the file alone
        cases._open().execute("UPDATE pole_jobs SET status = 'completed' WHERE case_id = 'case-01'")
        cases._open().commit()
    cases.reload()
    assert cases.DB.read_bytes() == before
    assert any(j["status"] == "pending" for j in cases.find("case-01")["jobs"])


def test_reference_records_come_from_the_jsonl_file():
    docs = knowledge.reference_docs(REFERENCE)
    by_ref = {d["ref"]: d for d in docs}
    assert len(docs) == 22 and all(d["kind"] == "reference" for d in docs)
    assert sum(d["case_id"] is None for d in docs) == 9 and sum("Customer reports" in d["title"] or "customer reports" in d["title"] for d in docs) == 2
    policy = by_ref["rag_documents.jsonl#dispatch-safety"]
    assert policy["title"] == "Safety is the first dispatch check" and policy["case_id"] is None and "Hold unsafe jobs" in policy["body"]
    assert by_ref["rag_documents.jsonl#case-07"]["case_id"] == "case-07"
    assert sum(d["case_id"] is not None for d in docs) == 13


def test_bad_jsonl_lines_are_skipped(tmp_path):
    (tmp_path / "x.jsonl").write_text('{"id": "a", "text": "Keep this.", "metadata": {"title": "A"}}\nnot json\n{"id": "b"}\n\n', encoding="utf-8")
    docs = knowledge.reference_docs(tmp_path)
    assert [(d["ref"], d["title"], d["body"]) for d in docs] == [("x.jsonl#a", "A", "Keep this.")]


def test_a_case_never_retrieves_its_own_worked_example(guidance):
    out = liwa.decide("case-05")
    titles = [r["title"] for r in out["references"]]
    assert "Farther pole is faster" not in titles and out["own_example_hidden"]
    assert any(not r["example"] for r in out["references"])                 # policy records are there
    row = liwa.store().db.execute("SELECT count(*) FROM doc WHERE kind = 'reference' AND case_id = 'case-05'").fetchone()[0]
    assert row == 1                                                         # it is stored; it is only kept out of this case


def test_offline_the_decision_is_the_databases_rule(guidance):
    for case_id, action, pole in (("case-01", "DISPATCH", "P-EVAC"), ("case-08", "HOLD", None), ("case-13", "DISPATCH", "P-HOSP")):
        out = liwa.decide(case_id)
        assert out["generator"] == "rule" and (out["action"], out["pole_id"]) == (action, pole)
        assert out["correct"] and out["agrees_with_rule"]
    assert liwa.decide("case-01") is liwa.decide("case-01")                 # served from memory until something changes


def test_claude_decides_from_the_retrieved_guidance(guidance, monkeypatch):
    seen = {}

    def fake(prompt):
        seen["prompt"] = prompt
        return 'Sure: {"action": "dispatch", "pole_id": "[P-EVAC]", "reason": "The hospital pole is unsafe,  so it is held.", ' \
               '"order": ["P-EVAC", "P-NOPE"], "held": [{"pole_id": "P-HOSP", "why": "unsafe"}], "refs": [1, 42]}'

    monkeypatch.setattr(liwa, "generator", lambda: "claude-code")
    monkeypatch.setattr(liwa, "_claude", fake)
    out = liwa.decide("case-01", force=True)
    assert out["generator"] == "claude-code" and (out["action"], out["pole_id"]) == ("DISPATCH", "P-EVAC") and out["correct"]
    assert out["reason"] == "The hospital pole is unsafe, so it is held." and out["order"] == ["P-EVAC"] and out["whys"] == {}
    assert out["held"] == [{"pole_id": "P-HOSP", "why": "unsafe"}] and out["refs"] == [1] and out["references"][0]["used"]
    assert "[P-HOSP] Hospital. Tier 1 (Critical). Safety: unsafe." in seen["prompt"] and "Driving ETA: 10 min" in seen["prompt"]
    assert "Expected action" not in seen["prompt"].split("CASE\n")[1]       # the answer is not in what she is asked
    assert "Send the truck to the evacuation center pole and hold" not in seen["prompt"]


@pytest.mark.parametrize("reply", [None, "no json here", '{"action": "DISPATCH", "pole_id": "P-MADE-UP"}', '{"action": "FLY", "pole_id": null}',
                                   '{"action": "HOLD", "pole_id": "P-EVAC"}'])
def test_an_unusable_reply_falls_back_to_the_rule(guidance, monkeypatch, reply):
    monkeypatch.setattr(liwa, "generator", lambda: "claude-code")
    monkeypatch.setattr(liwa, "_claude", lambda prompt: reply)
    out = liwa.decide("case-01", force=True)
    assert out["generator"] == "rule" and out["pole_id"] == "P-EVAC"


def test_each_pole_in_the_order_can_carry_its_reason(guidance, monkeypatch):
    reply = json.dumps({"action": "DISPATCH", "pole_id": "P-EVAC", "reason": "Safe and critical.", "order": [
        {"pole_id": "P-EVAC", "why": "Only  safe critical pole"}, {"pole_id": "P-MARKET", "why": "Tier 2, most customers"},
        {"pole_id": "P-GHOST", "why": "made up"}, "P-SCHOOL", {"pole_id": "P-EVAC", "why": "again"}]})
    monkeypatch.setattr(liwa, "generator", lambda: "claude-code")
    monkeypatch.setattr(liwa, "_claude", lambda prompt: reply)
    out = liwa.decide("case-01", force=True)
    assert out["order"] == ["P-EVAC", "P-MARKET", "P-SCHOOL"]
    assert out["whys"] == {"P-EVAC": "Only safe critical pole", "P-MARKET": "Tier 2, most customers"}


def test_every_job_has_as_many_reports_as_the_case_says():
    for c in cases.all_cases():
        found = case_reports.for_case(c)
        assert found == case_reports.for_case(c)                                  # the same messages every time
        assert len({r["id"] for r in found}) == len(found) == sum(j["report_count"] for j in c["jobs"])
        for j in c["jobs"]:
            mine = [r for r in found if r["pole_id"] == j["pole_id"]]
            assert len(mine) == j["report_count"], (c["id"], j["pole_id"])
            hazards = sum(bool(r["hazard"]) for r in mine)
            if j["safety"] == "unsafe" and j["report_count"] >= 2:
                assert hazards >= 2, (c["id"], j["pole_id"])                      # several people describe the hazard
            elif j["safety"] == "safe":
                assert hazards <= 1, (c["id"], j["pole_id"])                      # at most one alarm nobody confirms
        assert all(r["text"].strip() and r["channel"] in case_reports.CHANNELS for r in found)
        assert all((ai.PHOTOS / r["photo"]["file"]).is_file() for r in found if r["photo"])
    everything = [r for c in cases.all_cases() for r in case_reports.for_case(c)]
    assert {r["channel"] for r in everything} == set(case_reports.CHANNELS)
    assert any(r["photo"] for r in everything) and any(r["vulnerable"] for r in everything)
    assert any(r["hazard"] for c in cases.all_cases() for r in case_reports.for_case(c)
               if next(j for j in c["jobs"] if j["pole_id"] == r["pole_id"])["safety"] == "safe")     # the lone alarms exist


def test_each_case_is_drawn_in_its_own_barangay():
    places = [case_reports.place_of(i)["area_id"] for i in range(13)]
    assert len(set(places)) == 13 and case_reports.place_of(0)["barangay"]


def test_liwa_reads_the_reports_and_always_gets_every_policy_record(guidance, monkeypatch):
    seen = {}

    def fake(prompt):
        seen["prompt"] = prompt
        return json.dumps({"action": "DISPATCH", "pole_id": "P-EVAC", "reason": "Safe and critical.", "order": ["P-EVAC"],
                           "report_note": "One person reports  a spark at Residential area A; the crew should confirm. The order did not change.", "refs": [1]})

    monkeypatch.setattr(liwa, "generator", lambda: "claude-code")
    monkeypatch.setattr(liwa, "_claude", fake)
    out = liwa.decide("case-01", force=True)
    policies = [r for r in out["references"] if not r["example"]]
    assert len(policies) == 9 and sum(r["example"] for r in out["references"]) == liwa.EXAMPLES
    assert any("weighed lightly" in r["title"] for r in policies)
    reports = seen["prompt"].split("CUSTOMER REPORTS (invented")[1]
    first = cases.find("case-01")
    assert all(f"[{j['pole_id']}] {j['report_count']} reports" in reports for j in first["jobs"] if j["report_count"])
    assert reports.count('  - ') == sum(j["report_count"] for j in first["jobs"])
    assert "Equipment: transformer." in seen["prompt"] and "Equipment: pole." in seen["prompt"]
    assert out["report_note"].startswith("One person reports a spark") and out["reports"]["total"] == sum(j["report_count"] for j in first["jobs"])


def test_a_wrong_answer_is_reported_as_wrong(guidance, monkeypatch):
    monkeypatch.setattr(liwa, "generator", lambda: "claude-code")
    monkeypatch.setattr(liwa, "_claude", lambda prompt: json.dumps({"action": "DISPATCH", "pole_id": "P-HOSP", "reason": "Hospitals first."}))
    out = liwa.decide("case-01", force=True)
    assert out["generator"] == "claude-code" and not out["correct"] and not out["agrees_with_rule"]
    assert out["expected"]["pole_id"] == "P-EVAC"


def test_endpoints(guidance):
    c = TestClient(app)
    listed = c.get("/api/cases").json()
    assert len(listed["cases"]) == 13 and listed["tiers"] == {"1": "Critical", "2": "Community services", "3": "Residential"}
    assert listed["cases"][0]["decision"] is None and listed["generator"] == "offline"
    assert listed["cases"][0]["place"]["area_id"] and listed["cases"][0]["place"]["barangay"]
    told = c.get("/api/cases/case-01/reports").json()
    assert told["summary"]["total"] == len(told["reports"]) == sum(j["report_count"] for j in listed["cases"][0]["jobs"])
    assert told["channels"] == ["Meralco App", "SMS", "Hotline 16211", "Facebook", "X"] and sum(told["summary"]["by_channel"].values()) == told["summary"]["total"]
    photo = next(r["photo"] for r in told["reports"] if r["photo"])
    assert c.get(photo["url"]).status_code == 200
    assert c.get("/api/cases/case-99/reports").status_code == 404
    out = c.get("/api/cases/case-08/decision").json()
    assert out["action"] == "HOLD" and out["pole_id"] is None and out["correct"]
    assert c.get("/api/cases").json()["cases"][7]["decision"]["action"] == "HOLD"
    assert c.get("/api/cases/case-99/decision").status_code == 404
