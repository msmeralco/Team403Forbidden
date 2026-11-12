"""Past typhoons and the PDF reports written from them. Everything here is invented data."""
from datetime import datetime

from fastapi.testclient import TestClient

from app import history, report_pdf
from app.main import app


def test_every_figure_of_a_past_typhoon_is_counted_from_its_log():
    listed = history.all_events()
    assert [e["id"] for e in listed] == ["2026-09-bagwis", "2026-07-sinag", "2025-11-hiraya", "2025-10-amihan"]
    assert all("log" not in e and e["simulated"] and e["status"] == "Closed" for e in listed)
    for e in listed:
        full, s = history.find(e["id"]), e["summary"]
        log = full["log"]
        assert history.find(e["id"]) == full                                   # the same record every time
        assert s["interruptions"] == len(log) and s["customers"] == sum(r["customers"] for r in log)
        assert s["reports"] == sum(r["reports"] for r in log) == sum(s["by_channel"].values())
        assert all(sum(r["by_channel"].values()) == r["reports"] for r in log)
        assert s["customer_minutes"] == sum(r["customers"] * r["minutes"] for r in log)
        assert sum(t["customers"] for t in s["by_tier"]) == s["customers"] == sum(c["customers"] for c in s["causes"])
        assert s["followed"] + s["changed"] == s["interruptions"] and s["changed"] == len(full["changed"])
        assert 0 < s["hours_to_half"] <= s["hours_to_90"] <= s["hours_to_all"]
        assert s["curve"][0] == (0.0, 0.0) and s["curve"][-1][1] == 100.0
        assert [p for _, p in s["curve"]] == sorted(p for _, p in s["curve"])    # power only comes back
        clear = datetime.fromisoformat(full["all_clear"])
        for r in log:                                                           # the clock of each interruption runs forwards
            began, sent, back = (datetime.fromisoformat(r[k]) for k in ("began", "dispatched", "restored"))
            assert began < back and clear < sent < back
            assert (sent - clear).total_seconds() >= r["hold_minutes"] * 60     # nothing held is worked on before its hold ends
        assert [r["no"] for r in log] == list(range(1, len(log) + 1))
    by_id = {e["id"]: e["summary"] for e in listed}
    assert by_id["2025-11-hiraya"]["hours_to_all"] > by_id["2026-09-bagwis"]["hours_to_all"] > by_id["2025-10-amihan"]["hours_to_all"]
    assert by_id["2026-07-sinag"]["causes"][0]["cause"] == "Flooded equipment"   # the stories match the logs
    assert by_id["2026-09-bagwis"]["causes"][0]["cause"] == "Tree on the line"
    assert history.find("no-such-storm") is None


def test_the_typhoon_in_progress_is_built_from_the_test_cases():
    now = history.current("Typhoon Dalisay", "2026-11-12T06:00:00+08:00")
    assert now["status"] == "In progress" and now["document"] == "FL-SR-TYPHOON-DALISAY" and len(now["interruptions"]) == 20
    assert now["customers"] == sum(r["customers"] for r in now["interruptions"]) > 0
    assert now["reports"] == sum(now["by_channel"].values()) == sum(r["reports"] for r in now["interruptions"])
    assert now["ranked"] == 0 and all(r["by"] == "Written rule" for r in now["interruptions"])      # nothing opened yet in this run
    assert [r["tier"] for r in now["interruptions"]] == sorted(r["tier"] for r in now["interruptions"])
    assert any(r["first"] == "Hold the crew" for r in now["interruptions"]) and any(r["first"].startswith("Pole at ") for r in now["interruptions"])
    assert any(r["place"] == "Sampaloc, Manila" for r in now["interruptions"]) and "Manila" in now["cities"]


def _text(pdf: bytes) -> str:
    """The words of an uncompressed-enough PDF: good enough to check that a section was written."""
    import re
    import zlib

    out = []
    for stream in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdf, re.S):
        try:
            out.append(zlib.decompress(stream).decode("latin-1"))
        except zlib.error:
            continue
    return re.sub(r"\)\s*-?\d*\.?\d*\s*\(", "", " ".join(re.findall(r"\((?:\\.|[^\\)])*\)", " ".join(out))))


def test_a_restoration_report_has_what_such_a_report_needs():
    for e in history.EVENTS:
        pdf = report_pdf.restoration(history.find(e["id"]))
        assert pdf[:5] == b"%PDF-" and len(pdf) > 8000
        words = _text(pdf)
        for section in ("1. The event", "2. Impact at a glance", "3. Restoration progress", "4. Impact by customer tier",
                        "5. Causes of damage and work done", "6. Customer reports", "7. Safety and holds", "8. How the work was prioritised",
                        "9. Crews and resources", "10. Interruption log", "11. Open items and follow-up", "12. Definitions and limits of the data",
                        "Sign-off", "Prepared by", "Approved by", "Document number", "Simulated data"):
            assert section in words, (e["id"], section)
        assert e["name"] in words and f"FL-RR-{e['id'].upper()}" in words


def test_the_situation_report_and_the_endpoints():
    pdf = report_pdf.situation(history.current("Typhoon Dalisay", "2026-11-12T06:00:00+08:00"))
    words = _text(pdf)
    assert pdf[:5] == b"%PDF-" and "Typhoon situation report" in words and "2. Interruptions and what to check first" in words and "Sign-off" in words

    c = TestClient(app)
    listed = c.get("/api/history").json()
    assert len(listed["events"]) == 4 and listed["current"]["count"] == 20 and "interruptions" not in listed["current"]
    one = c.get("/api/history/2026-09-bagwis").json()
    assert one["name"] == "Typhoon Bagwis" and len(one["log"]) == one["summary"]["interruptions"]
    got = c.get("/api/history/2026-09-bagwis/report.pdf")
    assert got.status_code == 200 and got.headers["content-type"] == "application/pdf" and got.content[:5] == b"%PDF-"
    assert 'filename="FL-RR-2026-09-BAGWIS.pdf"' in got.headers["content-disposition"]
    now = c.get("/api/history/current/report.pdf")
    assert now.status_code == 200 and now.content[:5] == b"%PDF-" and "FL-SR-" in now.headers["content-disposition"]
    assert c.get("/api/history/nope").status_code == 404 and c.get("/api/history/nope/report.pdf").status_code == 404
