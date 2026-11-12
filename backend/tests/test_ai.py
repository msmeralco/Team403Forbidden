"""The AI reader's rules, tested with hand-made readings. No request leaves the machine."""
import base64

import pytest
from fastapi.testclient import TestClient

from app import ai
from app.main import app
from app.reports import DEMO_EXTRAS, classify
from app.state import NeedsPlace, Session

READING = {"what": "", "hazard": "none", "clue": "none", "single_house": False, "vulnerable": False,
           "power": "out", "place": "unknown", "landmark": ""}
SEEN = {"sees": "", "damage": "none_visible", "hazard": False, "bring": "", "confidence": "high",
        "damage_label": "No damage visible"}


def find(s: Session, needle: str) -> dict:
    return next(r for r in s.reports if needle in r["text"])


def test_demo_messages_are_ones_the_keyword_rules_miss():
    missed = [e for e in DEMO_EXTRAS if classify(e["text"])["category"] == "outage"
              and not classify(e["text"])["vulnerable"]]
    assert len(missed) == len(DEMO_EXTRAS) - 1          # all but the plainly worded live wire
    s = Session()
    assert sum(1 for r in s.reports if r.get("photo")) == sum(1 for e in DEMO_EXTRAS if e.get("photo"))
    assert s.state()["ai"]["status"] == "off"


def test_ai_reading_raises_a_hazard_the_keywords_missed():
    s = Session()
    r = find(s, "kumikislap")
    assert r["category"] == "outage"
    s.apply_reading(r, {**READING, "what": "Sparks on a pole and a burning smell.", "hazard": "fire"})
    s._recount()
    assert r["category"] == "hazard" and r["tag_label"] == "Sparks or fire"
    assert r["keyword_category"] == "outage" and r["caught"] == [{"what": "hazard", "by": "message"}]
    st = s.state()
    ampid = next(a for a in st["areas"] if a["id"] == "sm-ampid")
    assert ampid["hazard_open"] and st["ai"]["caught"]["hazard"] == 1
    assert any(x["asset_id"] == "T-05" and x["tier"] == "critical" for x in st["recommendations"])


def test_ai_can_never_lower_a_flag():
    s = Session()
    r = find(s, "live wire na nakalaylay dito sa Malhacan, tapat")
    assert r["category"] == "hazard"
    s.apply_reading(r, {**READING, "what": "Just an outage."})          # the AI sees nothing wrong
    s.apply_photo(r, dict(SEEN))                                        # and nothing in the photo
    assert r["category"] == "hazard" and r["tag"] == "live_wire" and "caught" not in r


def test_ai_notices_vulnerable_people_and_clues():
    s = Session()
    r = find(s, "naka-ventilator")
    assert not r["vulnerable"]
    s.apply_reading(r, {**READING, "vulnerable": True})
    assert r["vulnerable"] and r["caught"] == [{"what": "vulnerable", "by": "message"}]
    t = find(s, "sanga ng acacia")
    s.apply_reading(t, {**READING, "clue": "tree"})
    assert t["category"] == "clue" and t["tag_label"] == "Tree on the line"


def test_photo_reading_raises_flags_from_what_is_visible():
    s = Session()
    r = find(s, "Nakahilig na po yung poste")
    s.apply_photo(r, {**SEEN, "damage": "pole_leaning", "hazard": True, "damage_label": "Leaning pole"})
    assert r["category"] == "hazard" and r["tag"] == "pole_down" and r["caught"][0]["by"] == "photo"
    assert r["photo"]["ai"]["damage"] == "pole_leaning"
    t = find(s, "puno ng mangga")
    s.apply_photo(t, {**SEEN, "damage": "tree_on_line", "damage_label": "Tree on the line"})
    assert t["category"] == "clue" and t["tag"] == "tree"


def test_unexpected_ai_answers_are_made_safe():
    cleaned = ai._clean({"what": 5, "hazard": "meteor", "clue": None, "place": "atlantis", "power": "?"})
    assert cleaned["hazard"] == "none" and cleaned["clue"] == "none" and cleaned["place"] == "unknown"
    assert cleaned["power"] == "unclear" and cleaned["what"] == "5" and cleaned["vulnerable"] is False


def test_typed_in_message_without_ai_needs_a_barangay_then_counts():
    s = Session()
    with pytest.raises(NeedsPlace):
        s.add_report("walang kuryente dito sa amin")
    before = next(a for a in s.state()["areas"] if a["id"] == "val-karuhatan")["people"]
    out = s.add_report("May live wire na nakalaylay sa tapat ng simbahan!", "sms", "val-karuhatan")
    r = out["report"]
    assert out["read_by"] == "keywords" and r["category"] == "hazard" and r["added"] and r["author"] == "You (demo)"
    area = next(a for a in s.state()["areas"] if a["id"] == "val-karuhatan")
    assert area["people"] == before + 1 and area["hazard_open"]
    assert s.reports[0]["id"] == r["id"]


def test_typed_in_message_is_placed_by_the_ai_reading(monkeypatch):
    monkeypatch.setattr(ai, "availability", lambda: "ready")
    monkeypatch.setattr(ai, "read_messages", lambda items: {
        "new": {**READING, "what": "Sparks near the bridge.", "hazard": "fire", "place": "sm-ampid", "landmark": "tulay"}})
    monkeypatch.setattr(ai, "read_photo", lambda image, media, text: {**SEEN, "damage": "wire_down", "hazard": True})
    s = Session()
    out = s.add_report("may kumikislap sa may tulay", sample="lines-down-road.jpg")
    r = out["report"]
    assert out["read_by"] == "ai" and r["area_id"] == "sm-ampid" and r["category"] == "hazard"
    assert r["photo"]["url"] == "/api/photos/lines-down-road.jpg" and r["photo"]["ai"]["damage"] == "wire_down"
    assert r["ai"]["landmark"] == "tulay"


def test_ai_failure_falls_back_to_keywords(monkeypatch):
    def broken(items):
        raise ai.AIError("Could not reach the AI service. Check the internet connection.")
    monkeypatch.setattr(ai, "availability", lambda: "ready")
    monkeypatch.setattr(ai, "read_messages", broken)
    out = Session().add_report("Natumba yung poste dito", area_id="qc-central")
    assert out["read_by"] == "keywords" and "internet" in out["note"]
    assert out["report"]["category"] == "hazard"


def test_report_api_and_photos():
    c = TestClient(app)
    c.post("/api/reset", json={})
    assert c.get("/api/photos/leaning-pole.jpg").headers["content-type"] == "image/jpeg"
    assert c.get("/api/photos/../main.py").status_code == 404
    r = c.post("/api/reports", json={"text": "wala pa ring ilaw dito"})
    assert r.status_code == 409 and r.json()["need"] == "area"
    assert c.post("/api/reports", json={"text": ""}).status_code == 409
    tiny_png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 32).decode()
    r = c.post("/api/reports", json={"text": "tingnan nyo po", "source": "x", "area_id": "bac-niog",
                                     "photo": {"data": tiny_png, "media_type": "image/png"}})
    body = r.json()
    assert r.status_code == 200 and body["report"]["photo"]["url"].endswith("/photo")
    assert body["state"]["summary"]["reports"] == len(c.get("/api/reports").json()["reports"])
    assert c.get(body["report"]["photo"]["url"]).content.startswith(b"\x89PNG")
    assert c.post("/api/reports", json={"text": "x", "area_id": "bac-niog", "sample": "nope.jpg"}).status_code == 404
    assert c.post("/api/reports", json={"text": "x", "area_id": "bac-niog",
                                        "photo": {"data": "!!!", "media_type": "image/png"}}).status_code == 400
