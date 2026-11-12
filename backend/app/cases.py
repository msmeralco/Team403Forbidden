"""The test cases: which pole should the one truck go to next?

They live in backend/cases/meralco_demo.sqlite. That file is opened read-only and never changed:
it is copied into memory when first needed, and everything below reads the copy.

    scenarios   one row per case: title, setup, and the expected action (DISPATCH to a pole, or HOLD)
    pole_jobs   the jobs waiting in each case: facility, customer tier, safe or unsafe, flood status,
                customers the repair restores, linked outage reports, driving ETA
    tiers       1 Critical, 2 Community services, 3 Residential
    ranked_jobs, dispatch_results
                views that apply the written policy in plain SQL. Their answer is used as a
                cross-check on Liwa's, and as the fallback when Claude cannot be reached.

backend/cases/extra_poles.json adds more poles to each case, so that there is more to rank. Those
rows go into the copy only, pass the table's own checks, and are chosen so that no expected answer
changes. FIRSTLOOK_EXTRA_POLES=off (or deleting the file) runs the cases exactly as supplied.

The expected answer is shown on screen next to Liwa's and is never given to her.
"""
from __future__ import annotations

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
EQUIPMENT = ("pole", "transformer", "line")
COLUMNS = ("pole_id", "facility_label", "tier", "safety", "status", "customers_restored", "report_count",
           "eta_seconds", "distance_meters", "work_type", "flood_status", "scope_note")
DEFAULTS = {"safety": "safe", "status": "pending", "eta_seconds": None, "distance_meters": None,
            "work_type": "restore", "flood_status": "clear", "scope_note": None}


def available() -> bool:
    return DB.is_file()


def _add_extra(con: sqlite3.Connection) -> None:
    _added.clear()
    _equipment.clear()
    if EXTRA is None or not EXTRA.is_file():
        return
    try:
        poles = json.loads(EXTRA.read_text(encoding="utf-8")).get("poles", {})
    except (ValueError, OSError, AttributeError):
        return
    known = {r[0] for r in con.execute("SELECT case_id FROM scenarios")}
    for case_id, rows in poles.items():
        for row in rows if case_id in known and isinstance(rows, list) else []:
            try:
                values = [case_id] + [row[c] if c in row else DEFAULTS[c] for c in COLUMNS]
                con.execute(f"INSERT INTO pole_jobs (case_id, {', '.join(COLUMNS)}) VALUES ({', '.join('?' * (len(COLUMNS) + 1))})", values)
                _added.add((case_id, row["pole_id"]))
                if row.get("equipment") in EQUIPMENT:
                    _equipment[(case_id, row["pole_id"])] = row["equipment"]
            except (KeyError, TypeError, sqlite3.Error):
                continue                      # a row the table's own checks refuse is left out
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


def all_cases() -> list[dict]:
    """Every case with its jobs, the expected answer, and what the database's own rule says."""
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
            j = dict(r)
            case_id = j.pop("case_id")
            j["tier_name"] = names.get(j["tier"], f"Tier {j['tier']}")
            j["extra"] = (case_id, j["pole_id"]) in _added
            j["equipment"] = _equipment.get((case_id, j["pole_id"]), "pole")
            jobs.setdefault(case_id, []).append(j)
        return [{
            "id": s["case_id"], "title": s["title"], "setup": s["setup"], "jobs": jobs.get(s["case_id"], []),
            "expected": {"action": s["expected_action"], "pole_id": s["expected_pole_id"], "reason": s["expected_reason"]},
            "rule": {"action": rule[s["case_id"]]["action"], "pole_id": rule[s["case_id"]]["pole_id"], "order": order.get(s["case_id"], [])},
        } for s in con.execute("SELECT * FROM scenarios ORDER BY case_id")]


def find(case_id: str) -> dict | None:
    return next((c for c in all_cases() if c["id"] == case_id), None)
