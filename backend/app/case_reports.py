"""What customers reported about each interruption: invented messages, one set per piece of equipment.

The test cases give every job a number of linked outage reports. This module writes that many
messages for it, spread over the channels people really use (Meralco App, SMS, the hotline,
Facebook, X), so the number has something behind it that a person, and Liwa, can read.

    - The messages are invented and repeatable: the same case always gets the same messages.
    - Each message is written by a different invented person, so reports and people are the same count.
    - What they say follows the job's own facts: a job marked unsafe gets several people describing
      the same hazard, a flooded one gets flood reports, the rest are ordinary no-power reports,
      some mentioning someone who depends on power.
    - A few busy residential jobs get exactly one alarming report that nobody else confirms. It is
      there on purpose: one report must not be enough to move a job.
    - Photos are stand-ins from Wikimedia Commons (photos/CREDITS.md), not pictures of these places.

Each case is also given a real barangay to be drawn in (the case file has no coordinates).
"""
from __future__ import annotations

import hashlib
import math
from datetime import timedelta
from functools import lru_cache

import numpy as np

from . import cases, network
from . import reports as R

CHANNELS = ["Meralco App", "SMS", "Hotline 16211", "Facebook", "X"]        # the order they are listed on screen
HAZARDS = ("live_wire", "pole_down", "tree")
LONE_ALARM_FROM = 12                # a safe residential job with at least this many reports gets one unconfirmed alarm
PHOTO_FOR = {"live_wire": ["lines-down-road.jpg"], "pole_down": ["pole-down-street.jpg", "leaning-pole.jpg", "pole-down-field.jpg"],
             "tree": ["tree-on-lines.jpg"], "plain": ["typhoon-debris.jpg", "street-normal.jpg"]}
PHOTO_SHOWS = {
    "lines-down-road.jpg": "Power lines and a broken crossarm lying on a road",
    "leaning-pole.jpg": "A utility pole leaning over a road",
    "tree-on-lines.jpg": "A tree fallen onto roadside power lines",
    "pole-down-street.jpg": "A pole and its equipment fallen across a street",
    "pole-down-field.jpg": "A snapped pole lying on the ground",
    "street-normal.jpg": "An ordinary street with nothing visibly damaged",
    "typhoon-debris.jpg": "Debris and stripped trees after a typhoon",
}

# Where the customers of a facility say they are: (Filipino, English).
WHERE = {
    "hospital": ("sa may ospital", "at the hospital"), "evac": ("sa evacuation center", "at the evacuation center"),
    "school": ("sa may eskwelahan", "at the school"), "market": ("sa palengke", "at the public market"),
    "hall": ("sa may barangay hall", "at the barangay hall"), "apartment": ("sa apartment namin", "at the apartment building"),
    "homes": ("sa street namin", "on the caller's street"),
}
PLAIN = {
    "facebook_post": [
        "Wala pa ring kuryente {where} dito sa Brgy. {brgy}, {city} since {since} kagabi 😩 @Meralco sana po maayos agad",
        "{hours} hours na walang kuryente {where}, {brgy}. May update po ba @Meralco?",
        "Lowbat na lahat ng phone dito {where}, Brgy. {brgy}. Wala pa ring kuryente since {since} 🥲",
    ],
    "facebook_comment": [
        "Brgy. {brgy}, {city} po, {where}. Wala pa rin since kagabi",
        "Paki-check po {where} sa {brgy}, {hours} hrs na po",
        "Same here po {where}, {brgy}. Wala pa ring kuryente",
    ],
    "x": [
        "@meralco wala pa ring kuryente {where}, Brgy. {brgy} {city}. {hours} oras na po 😩 #{storm}PH",
        "@meralco hello po, brownout {where} sa {brgy} since {since}. Any ETA?",
        "{hours}hrs no power {where}, {brgy} {city} @meralco 🥲 #{storm}PH",
    ],
    "sms": [
        "BROWNOUT {BRGY} {CITY} - walang kuryente {where} since {since}",
        "Report brownout po Brgy {brgy} {city}, {where}. {hours}hrs na",
        "WALANG KURYENTE {where}. {brgy}, {city}. Pls send crew. Salamat",
    ],
    "hotline": [
        "Caller reports no power {where_en} in Brgy. {brgy}, {city}, since about {since}. Asked for a restoration time; advised crews are assessing.",
        "Customer reports an outage {where_en}, Brgy. {brgy} ({lm_en}). No power for about {hours} hours.",
    ],
    "app": ["Walang kuryente {where}", "No power since {since}", "Patay lahat ng ilaw {where}, {lm}"],
}
# What is particular to each kind of place: (what the customer wrote, the hotline agent's note).
SPECIAL = {
    "hospital": [
        ("Naka-generator lang po ang ospital dito sa {brgy} mula {since}. Paubos na raw ang krudo. May mga pasyenteng naka-oxygen 🙏",
         "Caller from the hospital's admin office: on generator since about {since}, fuel is running low. Patients on oxygen. Requests priority."),
        ("May dialysis po ang nanay ko sa ospital sa {brgy} bukas, wala pa ring kuryente doon",
         "Caller says a relative has dialysis at the hospital tomorrow and asks when power will be back."),
    ],
    "evac": [
        ("Ang daming evacuees dito sa evacuation center sa {brgy}, walang ilaw at bentilador. May mga sanggol at senior po dito 🙏",
         "Caller from the evacuation center in Brgy. {brgy}: many evacuees, no lights or fans, infants and elderly present."),
        ("Hindi makapag-charge ng phone ang mga tao sa evacuation center sa {brgy}, {hours} oras nang walang kuryente",
         "Evacuation center staff report no power for {hours} hours; evacuees cannot charge their phones."),
    ],
    "school": [
        ("Wala pa ring kuryente sa school dito sa {brgy}. May pasok na po ba bukas?",
         "Caller from the school office in Brgy. {brgy} reports no power and asks whether classes can resume."),
        ("Yung school sa {brgy} madilim pa rin, hindi rin umaandar ang water pump nila",
         "School reports no power; its water pump is not running."),
    ],
    "market": [
        ("Masisira na po ang mga paninda naming isda at karne sa palengke ng {brgy}, {hours} oras nang walang kuryente",
         "Market vendor reports no power for {hours} hours; chilled goods are spoiling."),
        ("Palengke sa {brgy} wala pa ring ilaw, madilim sa loob kahit umaga",
         "Caller reports the public market in Brgy. {brgy} is dark inside; vendors are using candles."),
    ],
    "hall": [
        ("Barangay hall ng {brgy} walang kuryente, dito pa naman nagcha-charge at kumukuha ng relief ang mga tao",
         "Barangay official reports the hall has no power; it is the relief and charging point for residents."),
        ("Patay ang radyo at ilaw sa barangay hall ng {brgy} mula {since}",
         "Barangay hall reports no power since {since}; its radio base is running on battery."),
    ],
    "apartment": [
        ("Buong apartment namin sa {brgy} walang kuryente, pati water pump kaya wala ring tubig",
         "Caller reports the whole apartment building has no power, and no water because the pump is electric."),
        ("5th floor po kami, patay ang elevator dito sa apartment sa {brgy}. May senior po kaming kasama",
         "Caller on an upper floor reports the building has no power; an elderly resident cannot use the stairs."),
    ],
    "homes": [
        ("Wala pa ring kuryente sa street namin sa {brgy}. May lola po kaming naka-oxygen concentrator 🙏",
         "Caller reports no power on the street; an elderly household member relies on an oxygen concentrator."),
        ("{hours} oras na pong brownout dito sa {brgy} {lm}. Naka-nebulizer po ang anak ko",
         "Caller reports no power for {hours} hours; a child in the house uses a nebulizer."),
        ("Sira na po lahat ng laman ng ref namin dito sa {brgy}, wala pa ring kuryente since {since}",
         "Caller reports food spoiling after no power since {since}."),
        ("Yung kabilang street sa {brgy} may ilaw na, dito sa amin wala pa rin",
         "Caller says the next street already has power but theirs does not."),
        ("Wala pa ring kuryente dito sa {brgy} {lm}, hindi makapag-online class ang mga bata",
         "Caller reports no power {lm_en}; asks for a restoration time."),
    ],
}
FLOOD = [
    ("Baha pa rin dito {where} sa {brgy}, hanggang tuhod pa ang tubig. Wala ring kuryente",
     "Caller reports floodwater still about knee-deep {where_en}, Brgy. {brgy}; no power."),
    ("Hindi pa humuhupa ang baha sa {brgy} {lm}. Kailan po kaya maibabalik ang kuryente?",
     "Caller reports the street is still flooded {lm_en} and asks when power can be restored."),
]
LONE = ("Parang may nag-spark sa poste {lm} kaninang madaling-araw, isang beses lang. Wala pa ring kuryente dito sa {brgy}",
        "Caller thinks they saw a spark on a pole {lm_en} before dawn, once. No power since.")


def _facility(label: str) -> str:
    text = label.lower()
    for word, kind in (("evacuation", "evac"), ("hospital", "hospital"), ("school", "school"), ("market", "market"),
                       ("hall", "hall"), ("apartment", "apartment")):
        if word in text:
            return kind
    return "homes"


# ---------------------------------------------------------------------------
# Where each case is drawn
# ---------------------------------------------------------------------------
def _km(a, b) -> float:
    return math.hypot((b.lon - a.lon) * 111.32 * math.cos(math.radians(a.lat)), (b.lat - a.lat) * 110.574)


@lru_cache(maxsize=1)
def _spread() -> tuple[int, ...]:
    """The barangays in an order that keeps the cases apart: each next one is the farthest from those already used."""
    areas = network.AREAS
    order, rest = [0], set(range(1, len(areas)))
    while rest:
        best = max(sorted(rest), key=lambda i: min(_km(areas[i], areas[j]) for j in order))
        order.append(best)
        rest.discard(best)
    return tuple(order)


def place_of(index: int) -> dict:
    """Where the case at this position is drawn. A case added with its own place (Manila and other cities
    outside the simulated sector) keeps it; the others are spread over the sector's barangays."""
    found = cases.all_cases()
    own = found[index].get("place") if index < len(found) else None
    if own:
        return {"area_id": None, "barangay": own["barangay"], "city": own["city"], "label": own["label"], "pos": [own["lat"], own["lon"]]}
    order = _spread()
    area = network.AREAS[order[index % len(order)]]
    return {"area_id": area.id, "barangay": area.barangay, "city": area.city, "label": f"Brgy. {area.barangay}, {area.city.split(',')[0]}",
            "pos": [area.lat, area.lon]}


def index_of(case_id: str) -> int:
    ids = [c["id"] for c in cases.all_cases()]
    return ids.index(case_id) if case_id in ids else 0


# ---------------------------------------------------------------------------
# The messages
# ---------------------------------------------------------------------------
def _kinds(rng: np.random.Generator, job: dict) -> list[str]:
    """What each of the job's reports is about."""
    n = job["report_count"]
    kinds = ["plain"] * n
    if n == 0:
        return kinds
    if job["safety"] == "unsafe":                              # several people describe the same hazard
        hazard = HAZARDS[int(rng.integers(len(HAZARDS)))]
        for i in rng.choice(n, size=min(n, max(2, round(n * 0.4))), replace=False):
            kinds[int(i)] = hazard
    elif job["flood_status"] != "clear":
        for i in rng.choice(n, size=min(n, max(1, round(n * 0.45))), replace=False):
            kinds[int(i)] = "flood"
    elif job["tier"] == 3 and job["status"] == "pending" and n >= LONE_ALARM_FROM:
        kinds[int(rng.integers(n))] = "lone"                   # one alarm nobody else confirms
    return ["special" if k == "plain" and rng.random() < 0.3 else k for k in kinds]


def _write(rng: np.random.Generator, source: str, kind: str, facility: str, ctx: dict) -> str:
    if kind in HAZARDS:
        return R._text(rng, source, kind, ctx)[0]
    if kind == "plain":
        return R._pick(rng, PLAIN[source]).format(**ctx)
    said, noted = LONE if kind == "lone" else R._pick(rng, FLOOD if kind == "flood" else SPECIAL[facility])
    if source == "hotline":
        return noted.format(**ctx)
    text = said.format(**ctx)
    if source == "x":
        return f"@meralco {text} #{ctx['storm']}PH"
    if source in ("sms", "app"):
        return text.replace(" 🙏", "").replace(" 😩", "")
    return text


def for_case(case: dict, index: int | None = None) -> list[dict]:
    """Every report linked to the case's jobs, newest first. They were written when the interruption began,
    so they follow the jobs as they were then, not as they stand after conditions changed."""
    place = place_of(index_of(case["id"]) if index is None else index)
    clear = R.all_clear_time()
    out: list[dict] = []
    for job in cases.at_start(case["id"]) or case["jobs"]:
        seed = int(hashlib.sha1(f"{case['id']}/{job['pole_id']}".encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        facility = _facility(job["facility_label"])
        for k, kind in enumerate(_kinds(rng, job)):
            hazard = kind in HAZARDS
            source = "x" if kind == "lone" else R._choose(rng, R.HAZARD_MIX if hazard else R.PRIMARY_MIX)
            landmark = R._pick(rng, R.LANDMARKS)
            hours = int(rng.integers(6, 16))
            city = place["city"].split(",")[0]
            ctx = {"brgy": place["barangay"], "city": city, "BRGY": place["barangay"].upper(), "CITY": city.upper(),
                   "lm": landmark, "lm_en": R.LANDMARKS_EN[landmark], "hours": hours, "since": f"{int(rng.integers(8, 12))}pm",
                   "storm": R.STORM, "where": WHERE[facility][0], "where_en": WHERE[facility][1]}
            text = _write(rng, source, kind, facility, ctx)
            person = R._person(rng, seed % 9000 + k)
            photo = None
            if source in ("facebook_post", "x", "app"):
                pool = PHOTO_FOR.get(kind) if hazard else PHOTO_FOR["plain"] if kind == "plain" and rng.random() < 0.06 else None
                if pool and (not hazard or rng.random() < 0.6):
                    name = R._pick(rng, pool)
                    photo = {"file": name, "url": f"/api/photos/{name}", "shows": PHOTO_SHOWS[name]}
            read = R.classify(text)
            out.append({
                "id": f"{case['id']}/{job['pole_id']}/{k + 1}", "pole_id": job["pole_id"], "source": source,
                "label": R.SOURCES[source]["label"], "channel": R.SOURCES[source]["channel"],
                "person": {"name": person["name"], "initials": person["initials"], "handle": person["handle"]},
                "time": (clear + timedelta(minutes=int(rng.integers(15, 540)))).isoformat(), "text": text,
                "meta": R._meta(rng, source, kind, person, seed % 100000 + k),
                "hazard": read["tag_label"] if read["category"] in ("hazard", "clue") else None, "vulnerable": read["vulnerable"], "photo": photo,
            })
    return sorted(out, key=lambda r: r["time"], reverse=True)


def summary(found: list[dict]) -> dict:
    by_channel = {c: sum(r["channel"] == c for r in found) for c in CHANNELS}
    return {"total": len(found), "by_channel": by_channel, "hazard": sum(bool(r["hazard"]) for r in found),
            "vulnerable": sum(r["vulnerable"] for r in found), "photos": sum(bool(r["photo"]) for r in found)}


def for_prompt(case: dict, found: list[dict]) -> str:
    """The reports as Liwa reads them: grouped under the job they are linked to."""
    blocks = []
    for job in case["jobs"]:
        mine = [r for r in found if r["pole_id"] == job["pole_id"]]
        if not mine:
            blocks.append(f"[{job['pole_id']}] no linked reports")
            continue
        channels = ", ".join(f"{c} {n}" for c, n in summary(mine)["by_channel"].items() if n)
        lines = [f'  - {r["channel"]}: "{r["text"]}"' + (" [photo attached]" if r["photo"] else "") for r in mine]
        blocks.append(f"[{job['pole_id']}] {len(mine)} reports from {len(mine)} people ({channels})\n" + "\n".join(lines))
    return "\n".join(blocks)
