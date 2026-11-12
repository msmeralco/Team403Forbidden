"""Past typhoons: what happened, and the record a restoration report is written from.

Every event here is invented for the demonstration. The names are not PAGASA names and none of
this is a Meralco record.

Only the headline of each event is written by hand (name, strength, dates, the story, what was
learned). Its interruption log is generated from a seed, and every figure shown on screen or
printed in a report (customers affected, time to restore, customer-minutes, causes, reports by
channel) is counted from that log. So the numbers always add up: the log is the single source.

How a log is made, in short: interruptions are placed in the service area's barangays, each with
a customer tier, a cause and a number of customers. Crews then work through them in the order the
hierarchy gives (safety and flood holds first, then customer tier, then customers), a few crews at
a time, and the clock that produces is what the report prints.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache

import numpy as np

from . import network
from .reports import MANILA

TIERS = {1: "Critical", 2: "Community services", 3: "Residential"}
CHANNELS = ["Meralco App", "SMS", "Hotline 16211", "Facebook", "X"]
CHANNEL_MIX = [0.18, 0.15, 0.14, 0.41, 0.12]
FACILITY = {1: ["Hospital", "Evacuation center", "School serving as an evacuation center"],
            2: ["Public market", "Barangay hall", "High school", "Elementary school"],
            3: ["Residential area", "Apartment block", "Residential area"]}
CAUSES = ["Tree on the line", "Pole down", "Line down", "Transformer failure", "Flooded equipment", "Debris on the line"]
REPAIR = {"Tree on the line": "Tree cleared, span restrung", "Pole down": "Pole replaced", "Line down": "Span restrung",
          "Transformer failure": "Transformer replaced", "Flooded equipment": "Equipment dried, tested and re-energised",
          "Debris on the line": "Debris cleared, line inspected"}

EVENTS = [
    {
        "id": "2026-09-bagwis", "name": "Typhoon Bagwis", "class": "Typhoon", "peak_kmh": 155, "signal": 3,
        "landfall": "2026-09-18T22:00", "all_clear": "2026-09-19T06:00", "seed": 918, "count": 21, "crews": 12, "focus": ("Meycauayan", "Valenzuela", "Rodriguez", "San Mateo"),
        "cause_mix": [0.34, 0.22, 0.18, 0.08, 0.08, 0.10], "flood": 0.10, "pace": 1.0,
        "track": "Made landfall in Aurora, crossed Central Luzon north of Metro Manila overnight and left through Zambales.",
        "what": "Strong winds brought trees down onto lines across the northern part of the service area. Most interruptions were in "
                "Bulacan, Valenzuela and Rizal. Critical customers that could be reached safely were back first; the last streets waited on "
                "sites that were not yet safe for the crews and on two poles that had to be replaced.",
        "changed": [("Road to the first item was closed by a fallen tree", "The crew took the second item first and returned.")],
        "lessons": ["Trees accounted for the largest share of damage. Trimming along the Bulacan feeders is scheduled before the next season.",
                    "Two replacement poles had to come from another sector. A small stock is now kept at the Montalban office."],
        "open": ["2 poles on temporary bracing in Rodriguez, permanent replacement scheduled."],
    },
    {
        "id": "2026-07-sinag", "name": "Typhoon Sinag", "class": "Typhoon", "peak_kmh": 130, "signal": 2,
        "landfall": "2026-07-24T15:00", "all_clear": "2026-07-25T06:00", "seed": 724, "count": 16, "crews": 10, "focus": ("Bacoor", "San Pedro"),
        "cause_mix": [0.20, 0.10, 0.14, 0.10, 0.36, 0.10], "flood": 0.38, "pace": 1.15,
        "track": "Passed south of Metro Manila over Batangas and Cavite with heavy monsoon rain on its northern side.",
        "what": "Rain did more damage than wind. Low-lying streets in Cavite and Laguna stayed flooded for most of a day, so several "
                "interruptions were held until the water went down and the equipment could be tested. Restoration was slow at the end "
                "for that reason, not for lack of crews.",
        "changed": [("Flood clearance for a hospital's upper floors arrived earlier than planned", "The hospital was moved ahead of an evacuation center.")],
        "lessons": ["Flood holds decided the last third of the restoration. Clearance requests now go to the city engineering offices as soon as an interruption is logged.",
                    "Customers on flooded streets asked the same question many times. A standing message on flood holds was added to the hotline."],
        "open": ["1 pad-mounted transformer in Bacoor to be raised above the July flood line."],
    },
    {
        "id": "2025-11-hiraya", "name": "Typhoon Hiraya", "class": "Super typhoon", "peak_kmh": 195, "signal": 4,
        "landfall": "2025-11-09T19:00", "all_clear": "2025-11-10T06:00", "seed": 1109, "count": 36, "crews": 10, "focus": (),
        "cause_mix": [0.28, 0.30, 0.22, 0.10, 0.04, 0.06], "flood": 0.06, "pace": 2.6,
        "track": "Made landfall in Quezon province at peak strength and crossed directly over Metro Manila before weakening.",
        "what": "The strongest storm in this record. Poles and lines came down across the whole service area, and each repair took far "
                "longer than usual. With every crew committed from the first hour, the last customers waited into the second day. Help "
                "from neighbouring sectors was asked for only after the storm had passed.",
        "changed": [("A main line repair restored an evacuation center without a visit", "The crew skipped it and went to the next item."),
                    ("An unsafe site was made safe by the city's clearing team ahead of plan", "The hospital pole was moved back to first place.")],
        "lessons": ["Help from neighbouring sectors was asked for too late to shorten this restoration. The request is now made at wind signal 3, before landfall.",
                    "Pole stock ran out on the first afternoon. Minimum stock per office was raised for the typhoon months.",
                    "Hospitals on generator asked for fuel updates. A single contact per hospital is now named before each storm."],
        "open": ["6 poles on temporary bracing across Quezon City and Antipolo.", "1 main line section in Antipolo running on a temporary bypass."],
    },
    {
        "id": "2025-10-amihan", "name": "Severe Tropical Storm Amihan", "class": "Severe tropical storm", "peak_kmh": 105, "signal": 2,
        "landfall": "2025-10-03T04:00", "all_clear": "2025-10-03T11:00", "seed": 1003, "count": 9, "crews": 8, "focus": ("Antipolo", "San Mateo", "Rodriguez", "Quezon City"),
        "cause_mix": [0.40, 0.08, 0.20, 0.06, 0.10, 0.16], "flood": 0.08, "pace": 0.85,
        "track": "Skirted the east coast of Luzon and brushed Rizal and northern Quezon City without making landfall nearby.",
        "what": "A short event. Gusts brought branches onto lines in Rizal and eastern Quezon City. Nothing needed more than one crew, "
                "and every customer was back the same day.",
        "changed": [],
        "lessons": ["No changes to procedure. The storm confirmed that the eastern feeders are the first to see tree contact."],
        "open": [],
    },
]


def _time(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=MANILA)


def _log(event: dict) -> list[dict]:
    """The event's interruptions, with the clock each one ran on."""
    rng = np.random.default_rng(event["seed"])
    landfall, clear = _time(event["landfall"]), _time(event["all_clear"])
    weight = np.array([5.0 if a.city.split(",")[0] in event["focus"] else 1.0 for a in network.AREAS])      # where the storm hit hardest
    areas = [network.AREAS[int(i)] for i in rng.choice(len(network.AREAS), size=event["count"], replace=True, p=weight / weight.sum())]
    rows = []
    for n, area in enumerate(areas, 1):
        tier = int(rng.choice([1, 2, 3], p=[0.26, 0.26, 0.48]))
        cause = CAUSES[int(rng.choice(len(CAUSES), p=event["cause_mix"]))]
        flooded = cause == "Flooded equipment" or rng.random() < event["flood"] * 0.4
        unsafe = not flooded and rng.random() < 0.22
        customers = int({1: rng.integers(20, 130), 2: rng.integers(30, 170), 3: rng.integers(90, 460)}[tier])
        reports = max(1, int(customers * rng.uniform(0.10, 0.30)))
        by_channel = [int(x) for x in rng.multinomial(reports, CHANNEL_MIX)]
        hold = int(rng.integers(240, 900)) if flooded else int(rng.integers(60, 300)) if unsafe else 0
        rows.append({
            "barangay": area.barangay, "city": area.city.split(",")[0], "tier": tier, "tier_name": TIERS[tier],
            "serves": str(rng.choice(FACILITY[tier])), "cause": cause, "repair": REPAIR[cause], "customers": customers,
            "reports": reports, "by_channel": dict(zip(CHANNELS, by_channel)),
            "hazard_reports": int(reports * rng.uniform(0.15, 0.4)) if unsafe or cause in ("Pole down", "Line down") else int(rng.random() < 0.3),
            "vulnerable_reports": int(reports * rng.uniform(0.03, 0.10)),
            "equipment": int(rng.integers(4, 12)), "hold_reason": "Flooded, waiting for clearance" if flooded else "Not safe for the crew" if unsafe else None,
            "hold_minutes": hold, "began": landfall + timedelta(minutes=int(rng.integers(-150, 200))),
            "reported": None, "_work": int(rng.integers(80, 330) * event["pace"]), "_travel": int(rng.integers(8, 36)),
        })
        rows[-1]["reported"] = max(rows[-1]["began"] + timedelta(minutes=int(rng.integers(4, 45))), landfall - timedelta(hours=3))
    # Crews take the interruptions in the hierarchy's order: what can be worked on first, then tier, then customers.
    free = [clear + timedelta(minutes=20)] * event["crews"]
    for row in sorted(rows, key=lambda r: (r["hold_minutes"] > 0, r["tier"], -r["customers"])):
        crew = min(range(len(free)), key=lambda i: free[i])
        ready = clear + timedelta(minutes=row["hold_minutes"])
        row["dispatched"] = max(free[crew], ready)
        row["restored"] = row["dispatched"] + timedelta(minutes=row.pop("_travel") + row.pop("_work"))
        free[crew] = row["restored"]
    rows.sort(key=lambda r: r["restored"])
    for n, row in enumerate(rows, 1):
        row["no"] = n
        row["minutes"] = int((row["restored"] - row["began"]).total_seconds() // 60)
        row["after_clear_h"] = round((row["restored"] - clear).total_seconds() / 3600, 1)
    return rows


def _hours_to(rows: list[dict], share: float) -> float:
    total, done = sum(r["customers"] for r in rows), 0
    for r in rows:                                               # rows are in the order they were restored
        done += r["customers"]
        if done >= total * share - 1e-9:
            return r["after_clear_h"]
    return rows[-1]["after_clear_h"]


def _summary(event: dict, rows: list[dict]) -> dict:
    customers = sum(r["customers"] for r in rows)
    minutes = sum(r["customers"] * r["minutes"] for r in rows)
    held = [r for r in rows if r["hold_minutes"]]
    curve, done = [(0.0, 0.0)], 0
    for r in rows:
        done += r["customers"]
        curve.append((r["after_clear_h"], round(100 * done / customers, 1)))
    by_tier = []
    for tier, name in TIERS.items():
        mine = [r for r in rows if r["tier"] == tier]
        if mine:
            by_tier.append({"tier": tier, "name": name, "interruptions": len(mine), "customers": sum(r["customers"] for r in mine),
                            "average_h": round(sum(r["after_clear_h"] for r in mine) / len(mine), 1), "last_h": max(r["after_clear_h"] for r in mine)})
    causes = sorted(({"cause": c, "interruptions": sum(r["cause"] == c for r in rows), "customers": sum(r["customers"] for r in rows if r["cause"] == c)}
                     for c in CAUSES), key=lambda c: -c["customers"])
    longest = max(rows, key=lambda r: r["minutes"])
    critical = [r for r in rows if r["tier"] == 1]
    return {
        "interruptions": len(rows), "customers": customers, "reports": sum(r["reports"] for r in rows),
        "by_channel": {c: sum(r["by_channel"][c] for r in rows) for c in CHANNELS},
        "hazard_reports": sum(r["hazard_reports"] for r in rows), "vulnerable_reports": sum(r["vulnerable_reports"] for r in rows),
        "equipment_checked": sum(r["equipment"] for r in rows), "crews": event["crews"],
        "hours_to_half": _hours_to(rows, 0.5), "hours_to_90": _hours_to(rows, 0.9), "hours_to_all": rows[-1]["after_clear_h"],
        "critical_all_h": max((r["after_clear_h"] for r in critical), default=None), "critical_count": len(critical),
        "customer_minutes": minutes, "average_outage_h": round(minutes / customers / 60, 1),
        "longest_h": round(longest["minutes"] / 60, 1), "longest_where": f"Brgy. {longest['barangay']}, {longest['city']}",
        "held": len(held), "held_hours": round(sum(r["hold_minutes"] for r in held) / 60, 1),
        "by_tier": by_tier, "causes": [c for c in causes if c["interruptions"]], "curve": curve,
        "cities": sorted({r["city"] for r in rows}), "followed": len(rows) - len(event["changed"]), "changed": len(event["changed"]),
        "injuries": 0, "restored": rows[-1]["restored"].isoformat(),
    }


@lru_cache(maxsize=None)
def _built(event_id: str) -> dict:
    event = next(e for e in EVENTS if e["id"] == event_id)
    rows = _log(event)
    out = {k: event[k] for k in ("id", "name", "class", "peak_kmh", "signal", "track", "what", "lessons", "open")}
    out.update(
        landfall=_time(event["landfall"]).isoformat(), all_clear=_time(event["all_clear"]).isoformat(), status="Closed", simulated=True,
        document=f"FL-RR-{event['id'].upper()}", changed=[{"why": why, "what": what} for why, what in event["changed"]],
        summary=_summary(event, rows),
        log=[{**r, "began": r["began"].isoformat(), "reported": r["reported"].isoformat(), "dispatched": r["dispatched"].isoformat(),
              "restored": r["restored"].isoformat()} for r in rows],
    )
    return out


def all_events() -> list[dict]:
    """Past typhoons, newest first, each with its summary. The full log comes with find()."""
    return [{k: v for k, v in _built(e["id"]).items() if k != "log"} for e in EVENTS]


def find(event_id: str) -> dict | None:
    return _built(event_id) if any(e["id"] == event_id for e in EVENTS) else None


def current(name: str, all_clear: str) -> dict:
    """The typhoon in progress: every interruption as it stands, and what to check first in each.
    The first check is Liwa's where she has ranked the interruption, and the written rule's otherwise."""
    from . import case_reports, cases, liwa                      # here, not at the top: liwa loads the search index

    made = liwa.decided()
    rows, channels, hazards, vulnerable = [], dict.fromkeys(CHANNELS, 0), 0, 0
    for index, case in enumerate(cases.all_cases()):
        place = case_reports.place_of(index)
        pending = [j for j in case["jobs"] if j["status"] == "pending"]
        held = [j for j in pending if j["safety"] == "unsafe" or (j["flood_status"] == "flooded_hold" and j["work_type"] != "inspect")]
        waiting = {j["pole_id"] for j in pending}                 # reports about work already done are not part of the situation
        told = case_reports.summary([r for r in case_reports.for_case(case, index) if r["pole_id"] in waiting])
        for channel, n in told["by_channel"].items():
            channels[channel] += n
        hazards, vulnerable = hazards + told["hazard"], vulnerable + told["vulnerable"]
        decision = made.get(case["id"])
        chosen = decision if decision else case["rule"]
        job = next((j for j in case["jobs"] if j["pole_id"] == chosen["pole_id"]), None)
        tier = min((j["tier"] for j in pending), default=3)
        rows.append({
            "id": case["id"], "title": case["title"], "place": place["label"], "city": place["city"].split(",")[0],
            "tier": tier, "tier_name": TIERS[tier], "customers": sum(j["customers_restored"] for j in pending),
            "reports": sum(j["report_count"] for j in pending), "equipment": len(case["jobs"]), "on_hold": len(held),
            "first": f"{job['equipment'].capitalize()} at {job['facility_label']}" if job else "Hold the crew",
            "by": "Liwa" if decision and decision["generator"] == "claude-code" else "Written rule",
        })
    rows.sort(key=lambda r: (r["tier"], -r["customers"]))
    return {
        "id": "current", "name": name, "status": "In progress", "simulated": True, "all_clear": all_clear,
        "document": "FL-SR-" + "".join(ch for ch in name.upper().replace(" ", "-") if ch.isalnum() or ch == "-"),
        "interruptions": rows, "customers": sum(r["customers"] for r in rows), "reports": sum(r["reports"] for r in rows),
        "equipment": sum(r["equipment"] for r in rows), "on_hold": sum(r["on_hold"] for r in rows),
        "critical": sum(r["tier"] == 1 for r in rows), "ranked": sum(r["by"] == "Liwa" for r in rows),
        "by_channel": channels, "hazard_reports": hazards, "vulnerable_reports": vulnerable, "cities": sorted({r["city"] for r in rows}),
    }
