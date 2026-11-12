"""The test cases: which piece of equipment should the one truck go to next?

They live in backend/cases/meralco_demo.sqlite. That file is opened read-only and never changed:
it is copied into memory when first needed, and everything below reads and writes the copy.

    scenarios   one row per case: title, setup, and the expected action (DISPATCH to a pole, or HOLD)
    pole_jobs   the jobs waiting in each case: facility, customer tier, safe or unsafe, flood status,
                customers the repair restores, linked outage reports, driving ETA
    tiers       1 Critical, 2 Community services, 3 Residential
    ranked_jobs, dispatch_results
                views that apply the written policy in plain SQL. Their answer is used as a
                cross-check on Liwa's, and as the fallback when Claude cannot be reached.

backend/cases/extra_poles.json adds to the copy: more equipment for each supplied case, seven more
cases, and a plain title for every case. Added rows pass the table's own checks, and no expected
answer of a supplied case changes. FIRSTLOOK_EXTRA_POLES=off (or deleting the file) runs the cases
exactly as supplied.

Conditions change during a restoration: a site is made safe, floodwater goes down, a crew arrives
and finds it cannot work. change() records that in the copy, so the rule (and Liwa) rank the case
as it now stands. restart() puts one case back as it was. Nothing is ever written to the file.

The expected answer is shown on screen next to Liwa's and is never given to her.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from pathlib import Path

DB = Path(os.environ.get("FIRSTLOOK_CASES") or Path(__file__).resolve().parent.parent / "cases" / "meralco_demo.sqlite")
_extra_setting = os.environ.get("FIRSTLOOK_EXTRA_POLES", "")
EXTRA: Path | None = None if _extra_setting == "off" else Path(_extra_setting) if _extra_setting else DB.parent / "extra_poles.json"

_lock = threading.RLock()
_copy: sqlite3.Connection | None = None
_added: set[tuple[str, str]] = set()          # (case_id, pole_id) of the rows that came from extra_poles.json
_equipment: dict[tuple[str, str], str] = {}   # what kind of equipment an added job is on; a supplied job is a pole
_new_cases: set[str] = set()                  # cases that came from extra_poles.json
_titles: dict[str, str] = {}                  # the plain title shown on screen, by case
_places: dict[str, dict] = {}                 # where an added case is drawn
_start: dict[str, list[dict]] = {}            # every case's jobs as they were when the copy was made
_changes: dict[str, list[dict]] = {}          # what has changed since, by case
EQUIPMENT = ("pole", "transformer", "line")
COLUMNS = ("pole_id", "facility_label", "tier", "safety", "status", "customers_restored", "report_count",
           "eta_seconds", "distance_meters", "work_type", "flood_status", "scope_note")
DEFAULTS = {"safety": "safe", "status": "pending", "eta_seconds": None, "distance_meters": None,
            "work_type": "restore", "flood_status": "clear", "scope_note": None}
# What can change at a job while the restoration is under way, and how it is said.
CHANGES = {
    "safe": "is now safe for the crew",
    "unsafe": "is not safe for the crew after all",
    "flood_cleared": "is clear of flood and cleared for restoration",
    "done": "is done",
}


def available() -> bool:
    return DB.is_file()


def _insert_job(con: sqlite3.Connection, case_id: str, row: dict) -> None:
    values = [case_id] + [row[c] if c in row else DEFAULTS[c] for c in COLUMNS]
    con.execute(f"INSERT INTO pole_jobs (case_id, {', '.join(COLUMNS)}) VALUES ({', '.join('?' * (len(COLUMNS) + 1))})", values)
    _added.add((case_id, row["pole_id"]))
    if row.get("equipment") in EQUIPMENT:
        _equipment[(case_id, row["pole_id"])] = row["equipment"]


def _add_extra(con: sqlite3.Connection) -> None:
    for store in (_added, _equipment, _new_cases, _titles, _places):
        store.clear()
    if EXTRA is None or not EXTRA.is_file():
        return
    try:
        extra = json.loads(EXTRA.read_text(encoding="utf-8"))
        poles, more, titles = extra.get("poles", {}), extra.get("cases", []), extra.get("titles", {})
    except (ValueError, OSError, AttributeError):
        return
    for case in more if isinstance(more, list) else []:          # a whole new case: its scenario row, then its jobs
        try:
            con.execute("INSERT INTO scenarios (case_id, title, setup, expected_action, expected_pole_id, expected_reason) VALUES (?, ?, ?, ?, ?, ?)",
                        (case["case_id"], case["title"], case["setup"], case["expected_action"], case.get("expected_pole_id"), case["expected_reason"]))
        except (KeyError, TypeError, sqlite3.Error):
            continue
        _new_cases.add(case["case_id"])
        if isinstance(case.get("place"), dict):
            _places[case["case_id"]] = case["place"]
        poles = {**poles, case["case_id"]: case.get("poles", [])}
    known = {r[0] for r in con.execute("SELECT case_id FROM scenarios")}
    for case_id, rows in poles.items():
        for row in rows if case_id in known and isinstance(rows, list) else []:
            try:
                _insert_job(con, case_id, row)
            except (KeyError, TypeError, sqlite3.Error):
                continue                      # a row the table's own checks refuse is left out
    _titles.update({k: str(v) for k, v in titles.items() if k in known} if isinstance(titles, dict) else {})
    con.commit()


def _open() -> sqlite3.Connection:
    """The working copy, in memory. The file on disk is only ever read."""
    global _copy
    with _lock:
        if _copy is None:
            source = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
            copy = sqlite3.connect(":memory:", check_same_thread=False)
            try:
                source.backup(copy)
            finally:
                source.close()
            copy.row_factory = sqlite3.Row
            copy.execute("PRAGMA foreign_keys = ON")           # an added row must name a real case and a real tier
            _add_extra(copy)
            _start.clear()
            _changes.clear()
            for r in copy.execute("SELECT * FROM pole_jobs ORDER BY case_id, tier, pole_id"):
                _start.setdefault(r["case_id"], []).append(dict(r))
            _copy = copy
        return _copy


def reload() -> None:
    """Forget the working copy; the next read starts again from the file."""
    global _copy
    with _lock:
        if _copy is not None:
            _copy.close()
        _copy = None


def tiers() -> dict[int, str]:
    with _lock:
        return {r["tier"]: r["name"] for r in _open().execute("SELECT tier, name FROM tiers ORDER BY tier")}


def _job(row: dict, case_id: str, names: dict[int, str]) -> dict:
    j = {k: v for k, v in row.items() if k != "case_id"}
    j["tier_name"] = names.get(j["tier"], f"Tier {j['tier']}")
    j["extra"] = (case_id, j["pole_id"]) in _added
    j["equipment"] = _equipment.get((case_id, j["pole_id"]), "pole")
    return j


def all_cases() -> list[dict]:
    """Every case with its jobs as they now stand, the expected answer, and what the database's own rule says."""
    if not available():
        return []
    with _lock:
        con = _open()
        names = {r["tier"]: r["name"] for r in con.execute("SELECT tier, name FROM tiers")}
        rule = {r["case_id"]: r for r in con.execute("SELECT case_id, action, pole_id FROM dispatch_results")}
        order: dict[str, list[str]] = {}
        for r in con.execute("SELECT case_id, pole_id FROM ranked_jobs ORDER BY case_id, dispatch_rank, pole_id"):
            order.setdefault(r["case_id"], []).append(r["pole_id"])
        jobs: dict[str, list[dict]] = {}
        for r in con.execute("SELECT * FROM pole_jobs ORDER BY case_id, tier, pole_id"):
            jobs.setdefault(r["case_id"], []).append(_job(dict(r), r["case_id"], names))
        return [{
            "id": s["case_id"], "title": _titles.get(s["case_id"], s["title"]), "scenario": s["title"], "setup": s["setup"],
            "jobs": jobs.get(s["case_id"], []), "added": s["case_id"] in _new_cases, "place": _places.get(s["case_id"]),
            "changes": list(_changes.get(s["case_id"], [])),
            "expected": {"action": s["expected_action"], "pole_id": s["expected_pole_id"], "reason": s["expected_reason"]},
            "rule": {"action": rule[s["case_id"]]["action"], "pole_id": rule[s["case_id"]]["pole_id"], "order": order.get(s["case_id"], [])},
        } for s in con.execute("SELECT * FROM scenarios ORDER BY case_id")]


def find(case_id: str) -> dict | None:
    return next((c for c in all_cases() if c["id"] == case_id), None)


def at_start(case_id: str) -> list[dict]:
    """The case's jobs as they were before anything changed: what customers were reporting about."""
    with _lock:
        _open()
        names = tiers()
        return [_job(dict(r), case_id, names) for r in _start.get(case_id, [])]


def change(case_id: str, pole_id: str, what: str) -> dict:
    """Record that something changed at one job, and return the case as it now stands.

    safe            the site or the route was made safe: the crew can now work there
    unsafe          the crew cannot work there after all
    flood_cleared   the water is down and restoration is cleared
    done            the job is finished
    """
    if what not in CHANGES:
        raise ValueError(f"Unknown change: {what}")
    with _lock:
        con = _open()
        row = con.execute("SELECT * FROM pole_jobs WHERE case_id = ? AND pole_id = ?", (case_id, pole_id)).fetchone()
        if row is None:
            raise KeyError(f"No job {pole_id} in {case_id}")
        # A job that had no way in has no driving time in the case. Give it one that is the same every run.
        eta = row["eta_seconds"] or 300 + int(hashlib.sha1(f"{case_id}/{pole_id}".encode()).hexdigest()[:4], 16) % 13 * 60
        if what == "safe":
            con.execute("UPDATE pole_jobs SET safety = 'safe', eta_seconds = ? WHERE case_id = ? AND pole_id = ?", (eta, case_id, pole_id))
        elif what == "unsafe":
            con.execute("UPDATE pole_jobs SET safety = 'unsafe', eta_seconds = NULL WHERE case_id = ? AND pole_id = ?", (case_id, pole_id))
        elif what == "flood_cleared":
            con.execute("UPDATE pole_jobs SET flood_status = 'clear', scope_note = NULL, eta_seconds = ? WHERE case_id = ? AND pole_id = ?",
                        (eta, case_id, pole_id))
        else:
            con.execute("UPDATE pole_jobs SET status = 'completed' WHERE case_id = ? AND pole_id = ?", (case_id, pole_id))
        con.commit()
        _changes.setdefault(case_id, []).append({"pole_id": pole_id, "what": what, "said": CHANGES[what]})
    return find(case_id)


def restart(case_id: str) -> dict:
    """Put one case back as it was when the server started."""
    with _lock:
        con = _open()
        if case_id not in _start:
            raise KeyError(f"No test case {case_id}")
        for row in _start[case_id]:
            con.execute("UPDATE pole_jobs SET safety = ?, status = ?, eta_seconds = ?, work_type = ?, flood_status = ?, scope_note = ? WHERE case_id = ? AND pole_id = ?",
                        (row["safety"], row["status"], row["eta_seconds"], row["work_type"], row["flood_status"], row["scope_note"], case_id, row["pole_id"]))
        con.commit()
        _changes.pop(case_id, None)
    return find(case_id)
