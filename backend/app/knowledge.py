"""Turns the current storm into records Liwa can retrieve.

Each record is one short, self-contained paragraph about one thing: a barangay, a city, a
place on the list, a topic (hazards, the ranking rule, what is waiting for repair...), a draft
advisory, or one resident's message. Records are rebuilt from the storm's own numbers every
time something changes, so whatever Liwa retrieves matches the rest of the app.

Nothing here calls a model or a database; see liwa.py for storage, search and wording.
"""
from __future__ import annotations

import re
from pathlib import Path

from .network import AREAS
from .reports import SOURCES

MAX_ADVISORY = 320
HAZARD_TAGLISH = {"Live wire down": "nakalaylay na live wire", "Sparks or fire": "nag-i-spark na linya",
                  "Fallen pole": "natumbang poste", "Danger reported": "panganib sa linya ng kuryente"}
CHANNEL = {"facebook_post": "Facebook posts", "facebook_comment": "Facebook comments", "x": "X posts",
           "sms": "SMS", "hotline": "hotline calls", "app": "Meralco App reports"}
RULE = ("The list is ranked in strict order. First, safety: a place with an open hazard such as a live wire, sparks or a "
        "fallen pole goes to the top. Second, essential facilities: places that feed hospitals, health centers, evacuation "
        "centers or water pumping stations that are likely without power. Third, the network: a main line comes before a "
        "switch or pole on it, then a branch line, then a distribution transformer, because more depends on what is closer "
        "to the substation. Fourth, customers and load: how many customer accounts the engine predicts are without power "
        "behind the place. Fifth, reports: how many people reported from the barangays behind it. Sixth, access: the shorter "
        "drive first. This order applies to places where damage is plausible: a place the evidence points away from (less than a "
        "5% chance the damage is there) or where a visit would tell us almost nothing stays at the bottom.")


def _n(count: int, one: str, many: str | None = None) -> str:
    return f"{count:,} {one if count == 1 else (many or one + 's')}"


def _names(items: list[str], limit: int = 4) -> str:
    items = [i.split(",")[0] for i in items]
    if len(items) > limit:
        items = items[:limit] + [f"{len(items) - limit} more"]
    if not items:
        return ""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _short(city: str) -> str:
    return city.split(",")[0]


def _lower(text: str) -> str:
    return text[0].lower() + text[1:] if text else text


def likelihood(p: float) -> str:
    """Completes the sentence "It ..."."""
    return ("is almost certainly without power" if p >= 0.9 else "is probably without power" if p >= 0.5
            else "may be without power" if p >= 0.2 else "probably has power")


def doc(kind: str, ref: str, title: str, body: str, link: tuple[str, str] | None = None) -> dict:
    return {"kind": kind, "ref": ref, "title": title, "body": " ".join(body.split()),
            "link_kind": link[0] if link else None, "link_id": link[1] if link else None}


# ---------------------------------------------------------------------------
# Draft advisories for customers (Taglish, calm, no restoration time)
# ---------------------------------------------------------------------------
def advisory_kind(a: dict) -> str:
    if a["restored"]:
        return "restored"
    if a["still_dark_msgs"] and a["p_out"] >= 0.5:
        return "still_dark"
    return "damage_found" if a["confirmed"] else "assessing"


def advisory_text(a: dict) -> str:
    """Safety comes first where there is a hazard or a vulnerable household. Under 320 characters."""
    b, kind = a["barangay"], advisory_kind(a)
    safety = ""
    if a["hazard_open"]:
        hz = HAZARD_TAGLISH.get(next(iter(a["hazards"])), "panganib sa linya ng kuryente")
        safety = f"INGAT PO: may na-report na {hz} sa inyong lugar. Huwag lalapit o hahawak sa anumang kawad o poste. "
        if a["vulnerable"]:
            safety += "May umaasa sa medical equipment? Tawag po sa 16211. "
    elif a["vulnerable"] and kind != "restored":
        safety = "Kung may kasama kayong umaasa sa medical equipment, tumawag po agad sa 16211. "
    long, short = {
        "assessing": (f"Magandang araw po, Brgy. {b}. Natanggap namin ang inyong mga report ng brownout. Ina-assess na ng aming crews ang sanhi at mag-a-update kami agad. Salamat po sa pasensya. – Meralco",
                      f"Natanggap namin ang reports ng brownout sa Brgy. {b}. Ina-assess na ng crews ang sanhi; mag-a-update kami. Salamat po. – Meralco"),
        "damage_found": (f"Update po, Brgy. {b}: natukoy na ng aming crews ang sira na nakaaapekto sa inyong area at naka-schedule na ang repair. Mag-a-update kami kapag naibalik na ang kuryente. Salamat po. – Meralco",
                         f"Update, Brgy. {b}: natukoy na ang sira at naka-schedule na ang repair. Mag-a-update kami. Salamat po. – Meralco"),
        "still_dark": (f"Sa mga taga-Brgy. {b}: alam po naming wala pa ring kuryente sa inyo kahit may naayos nang linya. May isa pang sira na hinahanap ng aming crews. Pasensya na po at salamat sa pag-unawa. – Meralco",
                       f"Brgy. {b}: alam naming wala pa ring kuryente kahit may naayos na. May isa pang sirang hinahanap ang crews. Salamat po. – Meralco"),
        "restored": (f"Good news po, Brgy. {b}: naibalik na ang kuryente sa inyong area. Kung wala pa rin sa bahay ninyo, i-report po sa Meralco app o sa 16211. Salamat po sa pasensya. – Meralco",
                     f"Naibalik na ang kuryente sa Brgy. {b}. Kung wala pa rin sa inyo, i-report sa Meralco app o 16211. Salamat po. – Meralco"),
    }[kind]
    text = safety + long if len(safety + long) < MAX_ADVISORY else safety + short
    return text[:MAX_ADVISORY - 1]


def needs_advisory(a: dict) -> bool:
    return bool(a["hazard_open"] or a["p_out"] >= 0.5 or a["restored"])


# ---------------------------------------------------------------------------
# Records about places and barangays
# ---------------------------------------------------------------------------
def situation(st: dict) -> str:
    s, res = st["summary"], st["resources"]
    if not s["areas_reporting"]:
        return "No barangay is reporting an outage right now."
    dark = _n(s["areas_reporting"], "barangay") + (" reports" if s["areas_reporting"] == 1 else " report") + " no power"
    hazard = f", and {_n(s['hazards_open'], 'safety hazard')} {'is' if s['hazards_open'] == 1 else 'are'} open" if s["hazards_open"] else ""
    cause = (f"The damage is pinned down: {_lower(res['top_label'])}." if res["identified"]
             else f"The most likely cause so far, at {round(res['top_p'] * 100)}%, is {_lower(res['top_label'])}.")
    return f"{dark}{hazard}. {cause}"


def _why(rec: dict) -> str:
    """The three ranking levels, spelled out for one place."""
    b = rec["basis"]
    safety = ("Safety: " + "; ".join(b["safety"]).lower() + ", still open." if b["safety"] else "Safety: no open hazard here.")
    essential = ("Essential facilities likely without power behind it: " + ", ".join(f"{e['name']} in {e['area']}" for e in b["essential"]) + "."
                 if b["essential"] else "Essential facilities: none behind it are likely without power.")
    network = f"Network: {b['level_label'].lower()}."
    homes = (f"Customers and load: about {b['predicted_accounts']:,} customer accounts predicted without power behind it, roughly {b['load_mw']} MW; "
             f"{_n(b['reported_people'], 'person', 'people')} reported; the engine puts the chance that the damage is at this place at {round(b['p_damaged'] * 100)}%.")
    return f"{safety} {essential} {network} {homes}"


def _place(asset: dict, st: dict) -> dict:
    name, link = asset["name"], ("priority", asset["id"])
    rec = next((r for r in st["recommendations"] if r["asset_id"] == asset["id"]), None)
    hand = next((h for h in st["handoff"] if h["asset_id"] == asset["id"]), None)
    fixed = next((x for x in st["repaired"] if x["asset_id"] == asset["id"]), None)
    if fixed:
        body = f"{name} ({asset['place']}) was repaired." + (f" Power is back in {_names(fixed['back'])}." if fixed["back"] else "") \
            + (f" Still dark afterwards: {_names(fixed['still_dark'])}, so another break is likely." if fixed["still_dark"] else "")
        return doc("place", asset["id"], f"{name}: repaired", body, link)
    if hand:
        r = hand["restores"]
        body = f"Damage was found at {name} ({asset['place']}) by {hand['found_by']}. It is waiting for Meralco's repair teams."
        if hand["blocked_by"]:
            body += f" It cannot help until {hand['blocked_by'][0]} is fixed first."
        elif r["sure"] or r["maybe"]:
            body += f" Fixing it should bring back about {r['sure_accounts'] + r['maybe_accounts']:,} customer accounts in {_names(r['sure'] + r['maybe'])}."
        if r["still_dark"]:
            body += f" {_names(r['still_dark'])} would stay dark even then."
        return doc("place", asset["id"], f"{name}: damage found, waiting for repair", body, link)
    if asset["status"] == "intact":
        return doc("place", asset["id"], f"{name}: checked, no damage", f"{name} ({asset['place']}) was checked and no damage was found.", link)
    if not rec:
        return doc("place", asset["id"], f"{name}: not on the list", f"{name} ({asset['place']}) is not on the list right now: no open road reaches it.", link)
    via = f", {rec['route']['km']} km via {', '.join(rec['route']['via'])}" if rec["route"]["via"] else ""
    level = {"critical": "safety", "high": "essential facilities", "medium": "network and customers", "low": "little to learn from a visit"}[rec["tier"]]
    body = (f"{name} ({rec['place']}) is number {rec['rank']} on the list of places to check. It ranks at the level of {level}. {rec['headline']}. "
            f"{_why(rec)} {rec['reason']} It is a {rec['travel_min']} minute drive from the {rec['from']}{via}, plus about {rec['inspect_min']} minutes on site. "
            f"What to look for on site: {_lower(asset['objective'])}")
    return doc("place", asset["id"], f"{name}: number {rec['rank']} on the list, why, how far, what to look for", body, link)


def _barangay(a: dict, st: dict) -> dict:
    name = f"Brgy. {a['barangay']}, {_short(a['city'])}"
    parts = []
    if a["restored"]:
        parts.append(f"Power is back in {name}" + (f"; {_n(a['restored_msgs'], 'resident')} confirmed it." if a["restored_msgs"] else "."))
    elif a["people"]:
        parts.append(f"{name}: {_n(a['people'], 'person', 'people')} reported no power, in {_n(a['reports'], 'message')}. It {likelihood(a['p_out'])}.")
    else:
        parts.append(f"Nobody has reported from {name}. It {likelihood(a['p_out'])}.")
    for label, count in a["hazards"].items():
        parts.append(f"{label} reported in {_n(count, 'message')}: " + ("still open, keep people away." if a["hazard_open"] else f"made safe by {a['hazard_handled_by']}."))
    if a["still_dark_msgs"] and not a["restored"]:
        parts.append(f"{_n(a['still_dark_msgs'], 'resident')} say it is still dark after a repair, so another break is likely.")
    if a["quiet"] and not a["restored"]:
        parts.append(f"It is a quiet area: about {a['expected_people']} reports would be expected from {a['accounts']:,} customer accounts. Phones may be dead or people evacuated.")
    if a["vulnerable"]:
        parts.append(f"{_n(a['vulnerable'], 'message')} mention someone elderly, sick or very young.")
    if a["critical"]:
        parts.append(f"Essential facility here: {_names(list(a['critical']))}.")
    rec = next((r for r in st["recommendations"] if r["asset_id"] == a.get("best_asset")), None)
    if rec and not a["restored"]:
        parts.append(f"Next step: check {rec['name']}, number {rec['rank']} on the list, {rec['travel_min']} minutes from the {rec['from']}.")
    elif a["confirmed"] and not a["restored"]:
        parts.append("Damage is confirmed upstream; the repair should bring it back.")
    return doc("barangay", a["id"], f"{name}: what is happening there", " ".join(parts), ("area", a["id"]))


def _city(label: str, areas: list[dict], st: dict) -> dict:
    out = sorted([a for a in areas if a["people"] and not a["restored"]], key=lambda a: -a["people"])
    back = [a for a in areas if a["restored"]]
    if not out:
        body = f"{label}: no barangay is reporting an outage" + (f"; power is back in {_names([a['barangay'] for a in back])}." if back else ".")
    else:
        body = f"{label}: {_n(sum(a['people'] for a in out), 'person', 'people')} reporting no power from {_n(len(out), 'barangay')}: " \
            + ", ".join(f"{a['barangay']} {a['people']}" for a in out) + "."
        hazards = [a for a in out if a["hazard_open"]]
        if hazards:
            body += " Open hazard: " + "; ".join(f"{', '.join(a['hazards']).lower()} in {a['barangay']}" for a in hazards) + "."
        recs = {r["asset_id"]: r for r in st["recommendations"]}
        best = sorted({a["best_asset"] for a in out if a.get("best_asset") in recs}, key=lambda i: recs[i]["rank"])
        if best:
            body += f" To clear it up, check {recs[best[0]]['name']}, number {recs[best[0]]['rank']} on the list."
    link = ("area", out[0]["id"]) if out else None
    return doc("city", label.lower().replace(" ", "-"), f"{label}: outages by barangay", body, link)


# ---------------------------------------------------------------------------
# Records about topics
# ---------------------------------------------------------------------------
def _topics(st: dict, session) -> list[dict]:
    s, res = st["summary"], st["resources"]
    worth = [r for r in st["recommendations"] if r["tier"] != "low"]
    top = worth[0] if worth else None
    top_link = ("priority", top["asset_id"]) if top else None
    out = []

    damaged = sum(1 for o in st["log"] if o["result"] == "damaged")
    clear = sum(1 for o in st["log"] if o["result"] == "intact")
    done = (f"So far {_n(len(st['log']), 'place')} checked ({damaged} with damage, {clear} clear), {_n(len(st['repaired']), 'repair')} done and "
            f"{_n(s['restored_areas'], 'barangay')} with power back." if st["log"] or st["repaired"] else "Nothing has been checked or repaired yet.")
    out.append(doc("topic", "situation", "Summary of the situation now: overview, status, what has happened and what has been done so far",
                   f"{situation(st)} {done} " + (f"The place to check next is {top['name']}." if top else "Nothing urgent is left to check."), top_link))

    if worth:
        rows = " ".join(f"{r['rank']}. {r['name']}, {r['place']}, {r['travel_min']} min away: {_lower(r['headline'])}." for r in worth[:5])
        out.append(doc("topic", "ranking", "Where should we look next? What to check first: the ranked list of priorities",
                       f"Check these first. {rows} " + (f"{len(worth) - 5} more places follow." if len(worth) > 5 else ""), top_link))
    else:
        out.append(doc("topic", "ranking", "Where should we look next? What to check first: the ranked list of priorities", "Nothing urgent is left to check. " + situation(st)))
    out.append(doc("topic", "rule", "How the ranking works: why a place is first, safety, essential facilities, network level, customers and load, reports, access", RULE, top_link))

    pct = round(res["top_p"] * 100)
    cause = f"{res['top_label']} is the most likely explanation, at {pct}%" + (": the damage is pinned down." if res["identified"] else ", so it is not settled yet.")
    scenarios = [x for x in st.get("scenarios", [])[1:3] if x.get("p", 0) >= 0.03]
    if scenarios and not res["identified"]:
        cause += " Next most likely: " + "; ".join(f"{_lower(x['label'])} ({round(x['p'] * 100)}%)" for x in scenarios) + "."
    cause += f" This rests on {_n(s['people'], 'person', 'people')} reporting from {_n(s['areas_reporting'], 'barangay')}."
    out.append(doc("topic", "cause", "What broke? Likely cause of the outage and how sure the engine is: confidence, probability", cause, top_link))

    open_ = [a for a in st["areas"] if a["hazard_open"]]
    closed = [a for a in st["areas"] if a["hazards"] and not a["hazard_open"]]
    hz = ("; ".join(f"{', '.join(a['hazards'])} in Brgy. {a['barangay']}, {_short(a['city'])} ({_n(sum(a['hazards'].values()), 'message')})" for a in open_)
          + ". Keep people away until it is made safe." if open_ else "No safety hazards are open right now.")
    if closed:
        hz += " Made safe: " + ", ".join(f"Brgy. {a['barangay']}" for a in closed) + "."
    out.append(doc("topic", "hazards", "Safety hazards and danger: live wires, sparks, fallen poles", hz, ("area", open_[0]["id"]) if open_ else None))

    dark_sites = [(c, a) for a in st["areas"] if a["p_out"] >= 0.5 and not a["restored"] for c in a["critical"]]
    recs = {r["asset_id"]: r for r in st["recommendations"]}
    ess = ("Essential facilities likely without power: " + "; ".join(
        f"{c} in Brgy. {a['barangay']}" + (f" (check {recs[a['best_asset']]['name']}, number {recs[a['best_asset']]['rank']})" if a.get("best_asset") in recs else "")
        for c, a in dark_sites) + "." if dark_sites else "No essential facility is likely without power right now.")
    out.append(doc("topic", "essential", "Essential facilities without power, hospitals affected: health centers, evacuation centers, schools, water pumping stations",
                   ess + " These decide the second level of the ranking.", ("area", dark_sites[0][1]["id"]) if dark_sites else None))

    vul = sorted([a for a in st["areas"] if a["vulnerable"]], key=lambda a: -a["vulnerable"])
    vtext = f"{_n(s['vulnerable'], 'message')} mention someone elderly, sick, on medical equipment or very young."
    if vul:
        vtext += " Most are in " + ", ".join(f"Brgy. {a['barangay']} ({a['vulnerable']})" for a in vul[:4]) + "."
    out.append(doc("topic", "vulnerable", "Vulnerable people: elderly, sick, babies, people on oxygen, nebulizers or dialysis", vtext, ("area", vul[0]["id"]) if vul else None))

    by = s["by_source"]
    repeats = len(session.reports) - len({r["person_id"] for r in session.reports})
    out.append(doc("topic", "counts", "How many reports came in: messages, people and channels, Facebook, X, SMS, hotline, Meralco App",
                   f"{_n(s['reports'], 'message')} from {_n(s['people'], 'person', 'people')}; {_n(repeats, 'message')} repeated someone already counted. By channel: "
                   + ", ".join(f"{CHANNEL[k]} {v}" for k, v in sorted(by.items(), key=lambda kv: -kv[1]) if v)
                   + f". {_n(s['areas_reporting'], 'barangay')} without power."))

    worst = sorted([a for a in st["areas"] if a["people"] and not a["restored"]], key=lambda a: -a["people"])[:4]
    if worst:
        out.append(doc("topic", "worst", "Which barangay is worst hit: where the most people are reporting",
                       "Most people reporting: " + ", ".join(f"Brgy. {a['barangay']} ({_short(a['city'])}) {a['people']}" for a in worst) + ".", ("area", worst[0]["id"])))

    if st["handoff"]:
        rows = []
        for h in st["handoff"]:
            r = h["restores"]
            rows.append(f"{h['name']}: " + (f"blocked, fix {h['blocked_by'][0]} first" if h["blocked_by"]
                        else f"brings back about {r['sure_accounts'] + r['maybe_accounts']:,} accounts in {_names(r['sure'] + r['maybe'])}" if r["sure"] or r["maybe"]
                        else "no barangay comes back from this alone"))
        rep = f"{_n(len(st['handoff']), 'confirmed spot')} waiting for repair. " + "; ".join(rows) + "."
        link = ("priority", st["handoff"][0]["asset_id"])
    else:
        rep, link = "No damage has been confirmed yet, so nothing is waiting for repair.", top_link
    fixed = "; ".join(f"{x['name']} (power back in {_names(x['back']) or 'no barangay yet'}" + (f", still dark: {_names(x['still_dark'])}" if x["still_dark"] else "") + ")" for x in st["repaired"])
    still = [a for a in st["areas"] if a["still_dark_msgs"] and not a["restored"]]
    rep += (f" Repaired so far: {fixed}." if fixed else " Nothing has been repaired yet.")
    rep += (" Still dark after a repair: " + ", ".join(f"Brgy. {a['barangay']}" for a in still) + "; another break is likely there." if still else "")
    out.append(doc("topic", "repair", "Repairs: damage found, what is ready or waiting for repair, what was repaired, still dark after a repair",
                   rep + " The repair order is Meralco's decision; FirstLook does not rank or do repairs.", link))

    quiet = [a for a in st["areas"] if a["quiet"] and not a["restored"]]
    out.append(doc("topic", "quiet", "Quiet areas: barangays predicted without power where few or no people reported",
                   ("Quiet areas, where far fewer people reported than expected: " + "; ".join(f"Brgy. {a['barangay']} ({a['people']} reported, about {a['expected_people']} expected)" for a in quiet)
                    + ". Phones may be dead or people evacuated, so do not wait for more reports there. This is the predictive side of the ranking."
                    if quiet else "No quiet areas: every barangay that looks affected is reporting about as much as expected."),
                   ("area", quiet[0]["id"]) if quiet else None))

    out.append(doc("topic", "eta", "When will power be back: restoration time, how long, ETA",
                   "FirstLook does not estimate a restoration time and Liwa will not guess one. What is known: " + situation(st)
                   + f" {_n(len(st['handoff']), 'confirmed spot')} {'is' if len(st['handoff']) == 1 else 'are'} waiting for repair."))
    out.append(doc("topic", "limits", "What Liwa can and cannot do: can you fix the outage, dispatch or send a crew, restore power, message customers",
                   "No. Liwa cannot fix an outage, dispatch or send a crew, restore power, or send a message to customers. Liwa reads the residents' reports and "
                   "FirstLook's numbers, says where to look first and why, and drafts what to tell customers. People decide, and Meralco's crews do the work."))

    advisories = [a for a in st["areas"] if needs_advisory(a)]
    first = sorted(advisories, key=lambda a: (not a["hazard_open"], -a["people"]))[:1]
    out.append(doc("topic", "advisories", "What to tell or announce to customers and residents: advisories overview",
                   (f"{_n(len(advisories), 'draft advisory', 'draft advisories')} ready in Taglish, one per affected barangay. None is sent from here. "
                    f"For Brgy. {first[0]['barangay']}: “{advisory_text(first[0])}” Ask for a barangay by name to see its draft." if first
                    else "No barangay needs an advisory right now."),
                   ("area", first[0]["id"]) if first else None))
    return out


def build(session) -> list[dict]:
    """Every record for the storm as it stands now."""
    st = session.state()
    docs = _topics(st, session)
    docs += [_place(a, st) for a in st["assets"]]
    docs += [_barangay(a, st) for a in st["areas"]]
    for a in st["areas"]:
        if needs_advisory(a):
            docs.append(doc("advisory", a["id"], f"What to tell customers in Brgy. {a['barangay']}, {_short(a['city'])}: draft advisory",
                            f"Draft advisory for Brgy. {a['barangay']}, {_short(a['city'])}, not sent: “{advisory_text(a)}” A person has to approve and send it.", ("area", a["id"])))
    cities: dict[str, list[dict]] = {}
    for a in st["areas"]:
        for part in a["city"].split(","):
            cities.setdefault(part.strip(), []).append(a)
    docs += [_city(label, areas, st) for label, areas in cities.items()]
    by_id = {a.id: a for a in AREAS}
    for r in session.reports:
        text = (r.get("text") or "").strip()
        if not text:
            continue
        a = by_id[r["area_id"]]
        docs.append(doc("message", r["id"], f"{SOURCES[r['source']]['label']} from Brgy. {a.barangay}, {_short(a.city)}", text, ("report", r["id"])))
    return docs


# ---------------------------------------------------------------------------
# Reference documents: the guidance that decides how inspections are ranked
# ---------------------------------------------------------------------------
CHUNK = 900        # characters; about one screen of text, small enough to retrieve precisely


def _chunks(text: str) -> list[str]:
    """Pack whole paragraphs into pieces of at most CHUNK characters; a paragraph longer than that is cut at sentences."""
    pieces, current = [], ""
    for para in (" ".join(p.split()) for p in re.split(r"\n\s*\n", text)):
        if not para:
            continue
        parts = [para] if len(para) <= CHUNK else re.split(r"(?<=[.!?])\s+", para)
        for part in parts:
            if current and len(current) + len(part) + 1 > CHUNK:
                pieces.append(current)
                current = ""
            current = f"{current} {part}".strip()
            while len(current) > CHUNK:           # one sentence longer than a chunk: cut it hard
                pieces.append(current[:CHUNK])
                current = current[CHUNK:]
    return pieces + ([current] if current else [])


def reference_docs(folder: Path) -> list[dict]:
    """Every .md and .txt file in the folder (except README.md), split by heading and then into chunks."""
    docs = []
    for path in sorted(folder.glob("*")) if folder.is_dir() else []:
        if path.suffix.lower() not in (".md", ".txt") or path.name.lower() == "readme.md":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        name, heading, section, n = path.stem.replace("-", " ").replace("_", " "), "", [], 0
        sections = []
        for line in text.splitlines():
            m = re.match(r"^#{1,6}\s+(.*)", line)
            if m:
                sections.append((heading, "\n".join(section)))
                heading, section = m.group(1).strip(), []
                if not sections[-1][1].strip() and len(sections) == 1 and not sections[-1][0]:
                    sections.pop()                # nothing before the first heading
            else:
                section.append(line)
        sections.append((heading, "\n".join(section)))
        for heading, body in sections:
            for piece in _chunks(body):
                n += 1
                docs.append(doc("reference", f"{path.name}#{n}", f"{name}: {heading}" if heading else name, piece))
    return docs
