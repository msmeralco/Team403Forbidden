"""Community reports from every channel: synthetic generation and plain keyword triage.

Each report belongs to one person ("voice"). People sometimes report the same outage
through two or three channels; FirstLook counts them once when it weighs evidence.
Names, numbers and handles are invented and always shown masked.
"""
import re
from datetime import datetime, timedelta, timezone

import numpy as np

from .network import AREAS, Area

MANILA = timezone(timedelta(hours=8))
STORM = "Dalisay"

SOURCES = {
    "facebook_post": {"label": "Facebook post", "channel": "Facebook"},
    "facebook_comment": {"label": "Comment on Meralco's page", "channel": "Facebook"},
    "x": {"label": "X post", "channel": "X"},
    "sms": {"label": "Text message", "channel": "SMS"},
    "hotline": {"label": "Hotline call", "channel": "Hotline 16211"},
    "app": {"label": "Meralco App report", "channel": "Meralco App"},
}
PRIMARY_MIX = {"facebook_comment": 0.27, "facebook_post": 0.17, "x": 0.12,
               "sms": 0.15, "hotline": 0.13, "app": 0.16}
HAZARD_MIX = {"hotline": 0.35, "facebook_post": 0.25, "x": 0.15, "app": 0.15, "sms": 0.10}

LANDMARKS = ["malapit sa chapel", "tapat ng barangay hall", "sa may palengke", "sa kanto ng Rizal St.",
             "malapit sa elementary school", "sa likod ng covered court", "tapat ng 7-Eleven",
             "sa may tulay", "sa may basketball court", "malapit sa health center"]
LANDMARKS_EN = {"malapit sa chapel": "near the chapel", "tapat ng barangay hall": "in front of the barangay hall",
                "sa may palengke": "near the market", "sa kanto ng Rizal St.": "at the corner of Rizal St.",
                "malapit sa elementary school": "near the elementary school",
                "sa likod ng covered court": "behind the covered court", "tapat ng 7-Eleven": "in front of 7-Eleven",
                "sa may tulay": "near the bridge", "sa may basketball court": "near the basketball court",
                "malapit sa health center": "near the health center"}

FIRST = ["Maria", "Jose", "Ana", "Mark", "Angelica", "John Paul", "Kristine", "Rodel", "Mylene", "Jerome",
         "Liza", "Carlo", "Jasmine", "Ramon", "Teresa", "Paolo", "Rhea", "Arnel", "Cecilia", "Noel",
         "Grace", "Dennis", "Joy", "Bong", "Mae", "Ricky", "Lorna", "Jun", "Trixie", "Aileen", "Miguel",
         "Camille", "Edgar", "Nina", "Ronald", "Shiela", "Vince", "Aling Nena", "Mang Ben", "Princess"]
LAST = ["Santos", "Reyes", "Cruz", "Bautista", "Ocampo", "Garcia", "Mendoza", "Torres", "Villanueva",
        "Ramos", "Aquino", "Castillo", "Rivera", "Navarro", "Dela Cruz", "Fernandez", "Gonzales", "Lopez",
        "Pascual", "Salazar", "Manalo", "Domingo", "Soriano", "Magbanua", "Panganiban"]

# ---------------------------------------------------------------------------
# Message templates. {brgy} {city} {lm} {lm_en} {hours} {since} {storm}
# ---------------------------------------------------------------------------
SOCIAL = {
    "outage": [
        "Brownout pa rin dito sa Brgy. {brgy}, {city} since {since} kagabi 😩 @Meralco sana po maayos agad",
        "{hours} hours na walang kuryente dito sa {brgy}. May update po ba @Meralco? Wala na rin kaming tubig kasi walang pump",
        "Grabe yung bagyo. Wala pa ring ilaw sa buong {brgy}, {city}. Sana unahin din kami 🙏",
        "Kami lang ba walang kuryente? Brgy. {brgy}, {city}. Buong street namin patay",
        "Lowbat na lahat ng phone dito sa {brgy}, {city}. Wala pa ring kuryente since {since} 🥲",
        "PSA: wala pang kuryente sa {brgy} ({lm}). Naka-report na po kami sa Meralco.",
        "Wala pa ring kuryente sa {brgy}, {city}. May matanda po kaming kasama na naka-nebulizer 🙏 @Meralco",
        "Day 1 ng walang kuryente sa Brgy. {brgy}. Sana po maayos na today 🙏",
    ],
    "follow_up": [
        "Update: wala pa rin po sa {brgy}, {city}. {hours} hours na 😓",
        "Follow up lang po @Meralco, {brgy} {city} wala pa rin kuryente",
        "{hours} oras na po. Brgy. {brgy} pa rin, wala pa ring kuryente",
    ],
    "live_wire": [
        "May live wire na nakalaylay sa kalsada dito sa {brgy}, {lm}! Delikado po, maraming bata dito ⚠️ @Meralco",
        "URGENT: naputol na kawad nakalaylay sa daan, Brgy. {brgy} {city} {lm}. Iwas po muna lahat!",
    ],
    "fire": [
        "Nag-spa-spark yung linya sa poste {lm}, {brgy}! May usok na rin 😨 @Meralco",
        "May sunog sa poste dito sa {brgy}, {city}!! Tumawag na kami sa BFP",
    ],
    "pole_down": [
        "Natumba yung poste ng Meralco dito sa {brgy} {lm}, harang sa daan ⚠️",
        "Bumagsak na poste sa Brgy. {brgy}, {city}. Nakahiga sa kalsada yung mga kawad",
    ],
    "transformer": [
        "May pumutok na transformer dito sa {brgy} kagabi, malakas na pagsabog tapos nawala kuryente",
        "Sumabog po yung transformer {lm}, Brgy. {brgy}, {city}",
    ],
    "tree": [
        "May puno na bumagsak sa linya dito sa {brgy}, {lm}. Wala nang kuryente simula noon",
        "Nadaganan ng puno yung mga kawad sa {brgy}, {city} 😟",
    ],
    "flicker": [
        "Nag-fi-flicker ilaw namin dito sa {brgy}, normal lang ba yan? @Meralco",
        "Patay-sindi kuryente sa {brgy} {city} kanina pa",
    ],
    "single_house": [
        "Kami lang walang kuryente sa {brgy}, yung kapitbahay meron. Bakit po kaya @Meralco?",
    ],
}
X_ONLY = {
    "outage": [
        "@meralco wala pa ring kuryente sa Brgy. {brgy}, {city}. {hours} oras na po 😩 #{storm}PH",
        "@meralco hello po, brownout sa {brgy} {city} since {since}. Any ETA?",
        "{hours}hrs no power here sa {brgy}, {city} @meralco 🥲 #{storm}PH",
        "buong {brgy} madilim pa rin @meralco pls 🙏",
    ],
}
COMMENT = {
    "outage": [
        "Brgy. {brgy}, {city} po wala pa rin since kagabi",
        "Paki-check po {brgy} {city}, {hours} hrs na po",
        "Same here po sa {brgy}. Wala pa ring kuryente",
        "{brgy}, {city} po. May senior po kami dito na bedridden 🙏",
        "Wala pa rin po sa amin, {brgy} {lm}",
        "Kailan po babalik kuryente sa {brgy}? Salamat po sa mga crew niyo",
        "{brgy} {city} po, buong area walang kuryente",
    ],
    "follow_up": [
        "Wala pa rin po {brgy}, {city} 😢",
        "Up po. {brgy} pa rin wala",
    ],
}
SMS = {
    "outage": [
        "BROWNOUT {BRGY} {CITY} - walang kuryente buong kalye since {since}",
        "Report brownout po Brgy {brgy} {city} {lm}",
        "WALANG KURYENTE. {brgy}, {city}. Pls send crew. Salamat",
        "Brgy {brgy} {city} no power po {hours}hrs na",
    ],
    "follow_up": ["FOLLOW UP: {brgy} {city} wala pa rin kuryente {hours}hrs na"],
    "live_wire": ["URGENT LIVE WIRE nakalaylay sa daan {brgy} {city} {lm}"],
    "fire": ["SUNOG SA POSTE {brgy} {city} nag-spark po"],
    "pole_down": ["Natumba poste {brgy} {city} {lm}"],
    "transformer": ["Pumutok transformer {brgy} {city}"],
    "tree": ["May puno sa linya {brgy} {city}"],
    "flicker": ["Mahina kuryente {brgy} {city}, patay-sindi"],
    "single_house": ["Kami lang walang kuryente {brgy} {city}, kapitbahay meron"],
}
HOTLINE = {
    "outage": [
        ("No power – area", "Caller reports no power on the whole street since about {since}. Neighbors also affected. Brgy. {brgy}, {city}."),
        ("No power – area", "Customer reports an outage in Brgy. {brgy} ({lm_en}). Asked for restoration time; advised crews are assessing."),
        ("No power – area", "Caller from Brgy. {brgy}, {city}: entire block without power. Elderly household member, asks for priority."),
    ],
    "follow_up": [("Follow-up", "Follow-up call. No power for {hours} hours in Brgy. {brgy}, {city}. Customer frustrated; reference given.")],
    "live_wire": [("Emergency – hazard", "EMERGENCY: caller reports a live wire down on the road {lm_en}, Brgy. {brgy}. Children nearby. Advised to stay away.")],
    "fire": [("Emergency – hazard", "EMERGENCY: sparking and smoke on a pole {lm_en}, Brgy. {brgy}, {city}. Fire department called.")],
    "pole_down": [("Emergency – hazard", "Caller reports a fallen pole blocking the road {lm_en}, Brgy. {brgy}.")],
    "transformer": [("Damage report", "Caller heard a loud explosion from the transformer {lm_en}, Brgy. {brgy}, then power went out.")],
    "tree": [("Damage report", "Caller reports a tree fallen on the power lines {lm_en}, Brgy. {brgy}, {city}.")],
    "flicker": [("Power quality", "Caller reports flickering lights and low voltage in Brgy. {brgy}. Single household.")],
    "single_house": [("No power – single house", "Only the caller's house is without power in Brgy. {brgy}; neighbors have power.")],
}
APP = {
    "outage": [("No power", "Walang kuryente buong street"), ("No power", "No power since {since}"),
               ("No power", ""), ("No power", "Patay lahat ng ilaw {lm}")],
    "follow_up": [("No power", "Wala pa rin po, {hours} hours na")],
    "live_wire": [("Hazard", "Live wire nakalaylay sa daan {lm}")],
    "fire": [("Hazard", "Nag-spark at umuusok yung poste {lm}")],
    "pole_down": [("Hazard", "Natumba poste {lm}")],
    "transformer": [("No power", "Pumutok yung transformer bago nawala kuryente")],
    "tree": [("No power", "May puno na bumagsak sa linya")],
    "flicker": [("Fluctuating power", "Patay-sindi ilaw")],
    "single_house": [("No power", "Kami lang walang kuryente, kapitbahay meron")],
}
ADVISORY = f"POWER ADVISORY: Restoration work continues in areas affected by Typhoon {STORM}. Report outages through our official channels."

# ---------------------------------------------------------------------------
# Triage: read the words, not a hidden label
# ---------------------------------------------------------------------------
HAZARD_RULES = [
    ("live_wire", "Live wire down", r"live ?wire|nakalaylay|naputol na kawad|kawad.{0,25}(kalsada|daan)|wire down"),
    ("fire", "Sparks or fire", r"spark|usok|sunog|smoke|apoy|\bfire\b"),
    ("pole_down", "Fallen pole", r"(natumba|bumagsak|tumba).{0,15}poste|poste.{0,15}(natumba|bumagsak)|fallen pole"),
]
CLUE_RULES = [
    ("transformer", "Transformer blew", r"(pumutok|sumabog).{0,20}transformer|transformer.{0,20}(pumutok|sumabog)|explosion from the transformer"),
    ("tree", "Tree on the line", r"puno.{0,30}(linya|kawad)|nadaganan ng puno|tree fallen on the power lines"),
]
NOISE_RULES = [
    ("single_house", "Only one house", r"kami lang walang|single household|only the caller's house|kapitbahay (meron|may)"),
    ("flicker", "Flickering or low voltage", r"flicker|patay-?sindi|mahina kuryente|low voltage|fluctuating"),
]
VULNERABLE = r"nebulizer|oxygen|dialysis|bedridden|senior|matanda|elderly|sanggol|baby|\bpwd\b"
RESTORED = r"bumalik na (ang |po )?(kuryente|ilaw)|may kuryente na|power is back|power came back here|naibalik na"

# Messages that arrive after a repair: either power is back, or it still isn't.
AFTER_REPAIR = {
    "still_dark": {
        "facebook_post": "Naayos na raw yung linya pero wala pa rin kuryente dito sa {brgy}, {city} 😩 @Meralco",
        "facebook_comment": "{brgy} {city} po wala pa rin, kahit may naayos na daw",
        "x": "@meralco bumalik daw kuryente sa iba pero kami sa {brgy}, {city} wala pa rin 😓",
        "sms": "WALA PA RIN KURYENTE {BRGY} {CITY} kahit naayos na daw",
        "hotline": ("Follow-up", "Caller says power came back in nearby areas but Brgy. {brgy}, {city} is still without power."),
        "app": ("No power", "Wala pa rin po kahit may naayos na"),
    },
    "restored": {
        "facebook_post": "Bumalik na ang kuryente dito sa {brgy}! Salamat po Meralco 🙏",
        "facebook_comment": "May kuryente na po sa {brgy}, {city}. Salamat sa mga crew!",
        "x": "@meralco power is back sa {brgy}, {city}! salamat po ⚡",
        "sms": "May kuryente na {brgy} {city}. Salamat",
        "hotline": ("Follow-up", "Caller confirms power came back here in Brgy. {brgy}. Thanked the crews."),
        "app": ("Resolved", "Bumalik na po ang kuryente"),
    },
}


def classify(text: str) -> dict:
    """Plain keyword triage, in Filipino and English. Safety hazards win over everything."""
    t = text.lower()
    out = {"category": "outage", "tag": None, "tag_label": None,
           "vulnerable": bool(re.search(VULNERABLE, t))}
    for group, rules in (("hazard", HAZARD_RULES), ("clue", CLUE_RULES), ("noise", NOISE_RULES)):
        for key, label, pattern in rules:
            if re.search(pattern, t):
                out.update(category=group, tag=key, tag_label=label)
                return out
    if re.search(RESTORED, t):
        out.update(category="restored", tag="restored", tag_label="Power is back")
        return out
    if re.search(r"follow[- ]?up|^update:|^up po|wala pa rin.*naayos|naayos.*wala pa rin", t):
        out["category"] = "follow_up"
    return out


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
def all_clear_time(now: datetime | None = None) -> datetime:
    """06:00 Manila time on the most recent morning: when the storm passed and crews can go out."""
    now = now or datetime.now(MANILA)
    t = now.replace(hour=6, minute=0, second=0, microsecond=0)
    return t if now >= t else t - timedelta(days=1)


def _clock(dt: datetime) -> str:
    return dt.strftime("%I:%M %p").lstrip("0").replace(" AM", "am").replace(" PM", "pm")


def _pick(rng: np.random.Generator, items: list):
    return items[int(rng.integers(len(items)))]


def _choose(rng: np.random.Generator, mix: dict, exclude: set = frozenset()) -> str:
    keys = [k for k in mix if k not in exclude]
    w = np.array([mix[k] for k in keys])
    return keys[int(rng.choice(len(keys), p=w / w.sum()))]


def _person(rng: np.random.Generator, n: int) -> dict:
    first, last = _pick(rng, FIRST), _pick(rng, LAST)
    tail = int(rng.integers(1000, 9999))
    handle = (first.split()[0] + last.replace(" ", "")[:4]).lower() + str(int(rng.integers(1, 99)))
    return {"id": f"P{n:04d}", "name": f"{first} {last[0]}.", "initials": first[0] + last[0],
            "handle": "@" + handle, "phone": f"09{int(rng.integers(15, 99))} ••• {tail}",
            "service_id": f"•••• {int(rng.integers(1000, 9999))}"}


def _text(rng, source: str, kind: str, ctx: dict) -> tuple[str, dict]:
    """Message text plus source-specific extras."""
    if source == "hotline":
        category, note = _pick(rng, HOTLINE.get(kind, HOTLINE["outage"]))
        return note.format(**ctx), {"call_category": category}
    if source == "app":
        outage_type, desc = _pick(rng, APP.get(kind, APP["outage"]))
        return desc.format(**ctx), {"outage_type": outage_type}
    if source == "sms":
        return _pick(rng, SMS.get(kind, SMS["outage"])).format(**ctx), {}
    if source == "facebook_comment" and kind in COMMENT:
        return _pick(rng, COMMENT[kind]).format(**ctx), {}
    if source == "x" and kind in X_ONLY and rng.random() < 0.6:
        return _pick(rng, X_ONLY[kind]).format(**ctx), {}
    return _pick(rng, SOCIAL.get(kind, SOCIAL["outage"])).format(**ctx), {}


def _meta(rng, source: str, kind: str, person: dict, seq: int) -> dict:
    loud = kind in ("live_wire", "fire", "pole_down")
    if source == "facebook_post":
        return {"reactions": int(rng.integers(40, 400) if loud else rng.integers(2, 120)),
                "comments": int(rng.integers(5, 80) if loud else rng.integers(0, 30)),
                "shares": int(rng.integers(10, 150) if loud else rng.integers(0, 12)), "audience": "Public"}
    if source == "facebook_comment":
        return {"on_post": ADVISORY, "reactions": int(rng.integers(0, 25)), "replies": int(rng.integers(0, 6))}
    if source == "x":
        return {"handle": person["handle"], "replies": int(rng.integers(0, 12)),
                "reposts": int(rng.integers(0, 60) if loud else rng.integers(0, 8)),
                "likes": int(rng.integers(5, 300) if loud else rng.integers(0, 40)),
                "views": int(rng.integers(300, 9000))}
    if source == "sms":
        return {"from": person["phone"], "to": _pick(rng, ["0920-971-6211 (Smart)", "0917-551-6211 (Globe)"])}
    if source == "hotline":
        secs = int(rng.integers(70, 420))
        return {"ticket": f"HL-{seq:06d}", "duration": f"{secs // 60}m {secs % 60:02d}s",
                "agent": f"CSR-{int(rng.integers(100, 399))}", "caller": person["name"]}
    return {"ref": f"OR-{seq:07d}", "service_id": person["service_id"], "account": person["name"]}


def generate(rng: np.random.Generator, area_voices: dict[str, int], out_areas: set[str],
             hazards: dict[str, str], clues: dict[str, list[str]], all_clear: datetime) -> list[dict]:
    """Build the report feed.

    area_voices: distinct people reporting per area. out_areas: areas that really lost power.
    hazards: area -> hazard kind reported by one or two people. clues: area -> damage clue kinds.
    """
    by_id = {a.id: a for a in AREAS}
    reports, seq, n_people = [], 200000 + int(rng.integers(0, 90000)), 0
    for area_id, voices in area_voices.items():
        if voices <= 0:
            continue
        area: Area = by_id[area_id]
        is_out = area_id in out_areas
        start = all_clear - timedelta(minutes=int(rng.integers(400, 560)))   # when this area went dark
        special = []
        if area_id in hazards:
            special += [hazards[area_id]] * min(2, voices)
        special += clues.get(area_id, [])
        for p in range(voices):
            n_people += 1
            person = _person(rng, n_people)
            if p < len(special):
                kind = special[p]
            elif is_out:
                kind = "outage"
            else:
                kind = "single_house" if rng.random() < 0.5 else "flicker"
            first = _choose(rng, HAZARD_MIX if kind in ("live_wire", "fire", "pole_down") else PRIMARY_MIX)
            channels = [(first, kind, 0)]
            if rng.random() < 0.28:   # same person tries another channel later
                second = _choose(rng, PRIMARY_MIX, {first})
                channels.append((second, "follow_up" if kind == "outage" else kind, 1))
                if rng.random() < 0.3:
                    channels.append((_choose(rng, PRIMARY_MIX, {first, second}), "follow_up" if kind == "outage" else kind, 2))
            t = start + timedelta(minutes=float(rng.exponential(70)) + 5)
            for source, k, nth in channels:
                if nth:
                    t = t + timedelta(minutes=float(rng.uniform(45, 200)))
                t = min(t, all_clear - timedelta(minutes=2))
                hours = max(1, int((t - start).total_seconds() // 3600))
                lm = _pick(rng, LANDMARKS)
                ctx = {"brgy": area.barangay, "BRGY": area.barangay.upper(), "city": area.city.split(",")[0],
                       "CITY": area.city.split(",")[0].upper(), "lm": lm, "lm_en": LANDMARKS_EN[lm],
                       "hours": hours, "since": _clock(start), "storm": STORM}
                text, extra = _text(rng, source, k, ctx)
                seq += 1
                lat = area.lat + float(rng.normal(0, 0.0028))
                lon = area.lon + float(rng.normal(0, 0.0028))
                tri = classify(text + " " + extra.get("call_category", "") + " " + extra.get("outage_type", ""))
                reports.append({
                    "id": f"R{seq}", "source": source, "source_label": SOURCES[source]["label"],
                    "channel": SOURCES[source]["channel"], "time": t.isoformat(),
                    "minutes_before_clear": int((all_clear - t).total_seconds() // 60),
                    "area_id": area.id, "barangay": area.barangay, "city": area.city,
                    "transformer": area.transformer, "pos": [round(lat, 5), round(lon, 5)],
                    "person_id": person["id"], "author": person["name"], "initials": person["initials"],
                    "text": text, **tri, "meta": {**_meta(rng, source, k, person, seq), **extra},
                })
    reports.sort(key=lambda r: r["time"], reverse=True)
    return reports


# Hand-written messages for the demo storm, in the messy way people really write, some with
# a photo. The keyword rules miss what matters in most of them: they are here to show what
# reading for meaning adds. Photos are stand-ins from Wikimedia Commons (see photos/CREDITS.md).
DEMO_EXTRAS = [
    {"area": "mey-malhacan", "source": "facebook_post", "photo": "lines-down-road.jpg",
     "text": "Ito po yung live wire na nakalaylay dito sa Malhacan, tapat ng elementary school. Kanina pa po yan, daming batang dumadaan ⚠️ @Meralco"},
    {"area": "sm-ampid", "source": "facebook_post",
     "text": "grabe dito samen sa may tulay pa-Ampid, may kumikislap sa taas ng poste tas amoy natutunaw na goma 😨 wag muna dumaan mga ka-barangay"},
    {"area": "sm-guitnang-bayan", "source": "x",
     "text": "@meralco yung kable sa tapat ng tricycle terminal sa Guitnang Bayan nakasayad na sa bubong ng mga tricycle, dinadaan-daanan lang ng mga tao 😬"},
    {"area": "sm-banaba", "source": "facebook_comment",
     "text": "Banaba po. 2 gabi na. Yung kapatid ko naka-ventilator sa bahay, paubos na yung battery backup namin. Pakiusap po 🙏"},
    {"area": "rod-san-jose", "source": "sms",
     "text": "d2 sa san jose montalban bumigay ung malaking sanga ng acacia nakapatong na sa mga linya. wala ilaw buong looban"},
    {"area": "mey-pandayan", "source": "app", "photo": "leaning-pole.jpg",
     "text": "Nakahilig na po yung poste sa kanto namin, parang babagsak na pag humangin ulit"},
    {"area": "mey-saluysoy", "source": "facebook_post", "photo": "pole-down-street.jpg",
     "text": "Bagsak yung poste dito sa Saluysoy, nakahambalang sa daan pati yung mga bakal sa taas"},
    {"area": "sm-guitnang-bayan", "source": "x", "photo": "tree-on-lines.jpg",
     "text": "@meralco natumba yung puno ng mangga sa may court, sabit sa mga kable. kaya pala wala kaming kuryente"},
    {"area": "rod-burgos", "source": "app", "photo": "pole-down-field.jpg",
     "text": "Putol yung poste malapit sa bukid, nakahiga na pati mga insulator. Walang signal kagabi kaya ngayon lang nakapag-report"},
    {"area": "ant-san-isidro", "source": "facebook_post", "photo": "typhoon-debris.jpg",
     "text": "Ganito itsura dito sa San Isidro ngayong umaga. Wala pa ring kuryente, ang daming kalat sa daan"},
    {"area": "qc-central", "source": "app", "photo": "street-normal.jpg",
     "text": "Brownout sa unit namin since kagabi pero ok naman sa katabing building, may ilaw pa nga yung poste sa labas"},
]


def one_report(rng: np.random.Generator, area: Area, source: str, text: str, when: datetime,
               all_clear: datetime, person_no: int, seq: int, author: str | None = None,
               photo: dict | None = None) -> dict:
    """A single report written by hand or typed into the app, in the same shape as generated ones."""
    person = _person(rng, person_no)
    if author:
        person["name"], person["initials"] = author, "".join(w[0] for w in author.split()[:2]).upper()
    extra = {}
    if source == "hotline":
        extra["call_category"] = "No power – area"
    elif source == "app":
        extra["outage_type"] = "No power"
    tri = classify(text)
    report = {
        "id": f"R{seq}", "source": source, "source_label": SOURCES[source]["label"],
        "channel": SOURCES[source]["channel"], "time": when.isoformat(),
        "minutes_before_clear": int((all_clear - when).total_seconds() // 60),
        "area_id": area.id, "barangay": area.barangay, "city": area.city,
        "transformer": area.transformer,
        "pos": [round(area.lat + float(rng.normal(0, 0.0028)), 5), round(area.lon + float(rng.normal(0, 0.0028)), 5)],
        "person_id": person["id"], "author": person["name"], "initials": person["initials"],
        "text": text, **tri, "meta": {**_meta(rng, source, "outage", person, seq), **extra},
    }
    if photo:
        report["photo"] = dict(photo)
    return report


def handwritten(rng: np.random.Generator, extras: list[dict], all_clear: datetime, people_from: int) -> list[dict]:
    by_id = {a.id: a for a in AREAS}
    out = []
    for n, e in enumerate(extras):
        when = all_clear - timedelta(minutes=float(rng.uniform(25, 240)))
        photo = {"name": e["photo"], "url": f"/api/photos/{e['photo']}"} if e.get("photo") else None
        out.append(one_report(rng, by_id[e["area"]], e["source"], e["text"], when, all_clear,
                              people_from + n, 700000 + n, photo=photo))
    return out


def after_repair(rng: np.random.Generator, area: Area, dark: bool, when: datetime, people_from: int) -> list[dict]:
    """A few residents report back after a repair: still no power, or power is back."""
    kind = "still_dark" if dark else "restored"
    reports = []
    n = int(rng.integers(3, 7) if dark else rng.integers(1, 4))
    for p in range(n):
        person = _person(rng, people_from + p)
        source = _choose(rng, PRIMARY_MIX)
        tpl = AFTER_REPAIR[kind][source]
        ctx = {"brgy": area.barangay, "BRGY": area.barangay.upper(), "city": area.city.split(",")[0],
               "CITY": area.city.split(",")[0].upper()}
        extra = {}
        if source == "hotline":
            extra, text = {"call_category": tpl[0]}, tpl[1].format(**ctx)
        elif source == "app":
            extra, text = {"outage_type": tpl[0]}, tpl[1].format(**ctx)
        else:
            text = tpl.format(**ctx)
        t = when + timedelta(minutes=float(rng.uniform(4, 25)))
        seq = 900000 + people_from * 10 + p
        tri = classify(text + " " + extra.get("call_category", "") + " " + extra.get("outage_type", ""))
        reports.append({
            "id": f"R{seq}", "source": source, "source_label": SOURCES[source]["label"],
            "channel": SOURCES[source]["channel"], "time": t.isoformat(), "minutes_before_clear": 0,
            "area_id": area.id, "barangay": area.barangay, "city": area.city,
            "transformer": area.transformer,
            "pos": [round(area.lat + float(rng.normal(0, 0.0028)), 5), round(area.lon + float(rng.normal(0, 0.0028)), 5)],
            "person_id": person["id"], "author": person["name"], "initials": person["initials"],
            "text": text, **tri, "after_repair": True,
            "meta": {**_meta(rng, source, "outage", person, seq), **extra},
        })
    return reports


def summarize(reports: list[dict]) -> dict:
    """Per-area tallies: reports, distinct people, channels, hazards, clues."""
    areas: dict[str, dict] = {}
    for r in reports:
        a = areas.setdefault(r["area_id"], {"reports": 0, "people": set(), "by_source": {},
                                            "hazards": {}, "clues": {}, "vulnerable": 0,
                                            "noise": 0, "latest": r["time"], "restored_msgs": 0,
                                            "still_dark_msgs": 0})
        if r.get("after_repair"):   # shown in the feed, but not counted as outage reports
            a["restored_msgs" if r["category"] == "restored" else "still_dark_msgs"] += 1
            continue
        a["reports"] += 1
        a["people"].add(r["person_id"])
        a["by_source"][r["source"]] = a["by_source"].get(r["source"], 0) + 1
        if r["category"] == "hazard":
            a["hazards"][r["tag_label"]] = a["hazards"].get(r["tag_label"], 0) + 1
        elif r["category"] == "clue":
            a["clues"][r["tag_label"]] = a["clues"].get(r["tag_label"], 0) + 1
        elif r["category"] == "noise":
            a["noise"] += 1
        a["vulnerable"] += int(r["vulnerable"])
        a["latest"] = max(a["latest"], r["time"])
    for a in areas.values():
        a["people"] = len(a["people"])
    return areas
