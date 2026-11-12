"""Liwa, the inspection planner: records in a local SQLite database, retrieval, then a plan.

These tests run offline: no Claude Code, no embedding model (see conftest.py)."""
import json

import pytest
from fastapi.testclient import TestClient

from app import knowledge, liwa
from app.main import app
from app.state import Session

GUIDE = """# Inspection ranking guide

## Hospitals and dialysis centers

Feeders that serve a hospital are inspected before any other feeder, unless a live wire is reported elsewhere.

## Evacuation centers

Evacuation centers come next after hospitals. Inspect the transformer nearest the center first.

## Residential areas

Residential laterals are inspected last, largest number of customers first.
"""


@pytest.fixture()
def s():
    return Session()


@pytest.fixture()
def guide(tmp_path, monkeypatch):
    (tmp_path / "inspection-guide.md").write_text(GUIDE, encoding="utf-8")
    (tmp_path / "README.md").write_text("ignored", encoding="utf-8")
    (tmp_path / "notes.pdf").write_bytes(b"%PDF not read")
    monkeypatch.setattr(liwa, "REFERENCE", tmp_path)
    yield tmp_path
    monkeypatch.undo()
    liwa.store().sync("reference", [], liwa.embedder())        # leave the shared test database without reference records


def test_every_part_of_the_storm_becomes_a_record(s):
    docs = knowledge.build(s)
    assert {d["kind"] for d in docs} == {"topic", "place", "barangay", "city", "advisory", "message"}
    assert sum(d["kind"] == "barangay" for d in docs) == len(s.state()["areas"])
    assert sum(d["kind"] == "place" for d in docs) == len(s.state()["assets"])
    assert len({(d["kind"], d["ref"]) for d in docs}) == len(docs)
    assert all(d["title"] and d["body"] and "\n" not in d["body"] for d in docs)


def test_the_database_matches_the_storm_and_only_changes_what_changed(s):
    liwa.index(s)
    counts = liwa.store().counts()
    assert counts["barangay"] == 24 and counts["place"] == 20 and counts["message"] > 200
    db = liwa.store().db
    total = db.execute("SELECT count(*) FROM doc").fetchone()[0]
    assert db.execute("SELECT count(*) FROM doc_vec").fetchone()[0] == total
    assert db.execute("SELECT count(*) FROM doc_fts").fetchone()[0] == total
    again = liwa.index(s)
    assert {k: again[k] for k in ("added", "changed", "removed", "embedded")} == {"added": 0, "changed": 0, "removed": 0, "embedded": 0}
    s.observe("T-03", "damaged")
    after = liwa.index(s)
    assert after["changed"] > 0 and after["added"] == 0
    assert "waiting for" in liwa.store().get("place", "T-03")["body"]


def test_reference_documents_are_split_stored_and_survive_a_new_storm(guide):
    docs = knowledge.reference_docs(guide)
    assert [d["ref"] for d in docs] == ["inspection-guide.md#1", "inspection-guide.md#2", "inspection-guide.md#3"]
    assert docs[0]["title"] == "inspection guide: Hospitals and dialysis centers" and "hospital" in docs[0]["body"]
    liwa.index(Session(seed=3))
    second = Session(seed=4)
    liwa.index(second)
    db = liwa.store()
    assert db.counts()["reference"] == 3
    assert sorted(r[0] for r in db.db.execute("SELECT DISTINCT storm FROM doc")) == sorted([second.id, "reference"])
    vector = liwa.embedder().embed_query(["which feeder first when a hospital has no power"])[0]
    found = db.search("which feeder first when a hospital has no power", vector, group="reference", k=2)
    assert found[0]["ref"] == "inspection-guide.md#1"
    (guide / "inspection-guide.md").write_text("# Guide\n\nOnly one rule now: safety first.", encoding="utf-8")
    liwa.index(second)
    assert db.counts()["reference"] == 1                       # edited file: old records gone, new one in


def test_long_reference_text_is_cut_into_chunks():
    text = " ".join(f"Sentence number {i} about inspecting feeders after a storm." for i in range(80))
    pieces = knowledge._chunks(text)
    assert len(pieces) > 3 and all(len(p) <= knowledge.CHUNK for p in pieces)
    assert "".join(pieces).replace(" ", "") == text.replace(" ", "")


def test_offline_plan_is_the_engines_order_with_the_built_in_rule(s):
    out = liwa.plan(s)
    worth = [r for r in s.state()["recommendations"] if r["tier"] != "low"]
    assert out["generator"] == "offline" and out["model"] is None and not out["reordered"]
    assert [x["asset_id"] for x in out["steps"]] == [r["asset_id"] for r in worth]
    assert [x["n"] for x in out["steps"]] == list(range(1, len(worth) + 1))
    assert out["steps"][0]["tier"] == "critical" and "live wire" in out["steps"][0]["why"].lower()
    assert out["reference_documents"] == 0 and [r["own"] for r in out["references"]] == [False]
    assert "safety" in out["references"][0]["text"].lower()
    assert liwa.plan(s) is out                                  # nothing changed: the same plan is served
    s.observe("T-03", "damaged")
    assert liwa.plan(s) is not out                              # a field result means a new plan
    assert "T-03" not in [x["asset_id"] for x in liwa.plan(s)["steps"]]


def test_claude_reorders_by_the_reference_documents(s, guide, monkeypatch):
    worth = [r["asset_id"] for r in s.state()["recommendations"] if r["tier"] != "low"]
    order = [worth[1], worth[0], "MADE-UP", worth[1]] + worth[3:]      # worth[2] left out, one invented id, one repeat
    seen = {}

    def fake(prompt):
        seen["prompt"] = prompt
        steps = [{"id": a, "why": f"Because of guide for {a}.", "refs": [1, 99]} for a in order]
        return "Here you go:\n" + json.dumps({"summary": "Hospitals first.  Then the rest.", "steps": steps})

    monkeypatch.setattr(liwa, "generator", lambda: "claude-code")
    monkeypatch.setattr(liwa, "_claude", fake)
    out = liwa.plan(s)
    got = [x["asset_id"] for x in out["steps"]]
    assert out["generator"] == "claude-code" and out["model"] == liwa.CLAUDE_MODEL and out["reordered"]
    assert got[:2] == [worth[1], worth[0]] and sorted(got) == sorted(worth) and "MADE-UP" not in got
    skipped = next(x for x in out["steps"] if x["asset_id"] == worth[2])      # left out by Claude: kept, after the ones it ranked
    assert skipped["n"] > len(set(order) & set(worth[:liwa.MAX_CANDIDATES])) and skipped["refs"] == []
    assert out["steps"][0]["refs"] == [1]
    assert out["summary"] == "Hospitals first. Then the rest."
    assert out["reference_documents"] == 3 and out["references"][0]["own"] and out["references"][0]["used"]
    assert out["references"][-1]["title"] == "FirstLook's built-in rule"
    assert "Feeders that serve a hospital" in seen["prompt"] and f"[{worth[0]}]" in seen["prompt"]
    row = liwa.store().db.execute("SELECT generator, steps FROM plan ORDER BY id DESC LIMIT 1").fetchone()
    assert row["generator"] == "claude-code" and json.loads(row["steps"]) == got


def test_a_bad_claude_reply_falls_back_to_the_engines_order(s, monkeypatch):
    monkeypatch.setattr(liwa, "generator", lambda: "claude-code")
    for reply in (None, "I cannot do that.", "{not json}", '{"steps": "none"}'):
        monkeypatch.setattr(liwa, "_claude", lambda prompt, reply=reply: reply)
        out = liwa.plan(s, force=True)
        assert out["generator"] == "offline" and not out["reordered"]


def test_claude_is_never_given_an_api_key(monkeypatch):
    captured = {}

    class Done:
        returncode, stdout = 0, '{"result": "ok", "is_error": false}'

    def run(cmd, **kwargs):
        captured.update(kwargs, cmd=cmd)
        return Done()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-never-be-used")
    monkeypatch.setattr(liwa.shutil, "which", lambda name: "claude")
    monkeypatch.setattr(liwa.subprocess, "run", run)
    assert liwa._claude("hello") == "ok"
    assert not any(k.startswith("ANTHROPIC_") for k in captured["env"])
    assert "-p" in captured["cmd"] and liwa.CLAUDE_MODEL in captured["cmd"] and captured["input"] == "hello"


def test_endpoints():
    c = TestClient(app)
    c.post("/api/reset", json={})
    status = c.get("/api/liwa").json()
    assert status["generator"] == "offline" and status["records"]["barangay"] == 24 and status["brief"]
    assert status["reference"] == {"folder": "backend/reference", "files": [], "chunks": 0}
    plan = c.get("/api/liwa/plan").json()
    assert plan["steps"][0]["asset_id"] == "T-03" and plan["generator"] == "offline"
    assert c.get("/api/liwa/plan?force=true").json()["key"] == plan["key"]
    assert c.post("/api/liwa/ask", json={"question": "hello"}).status_code in (404, 405)     # there is no prompt box
