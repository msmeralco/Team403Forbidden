"""Builds the "Meralco grid" map layer from OpenStreetMap.

Meralco does not publish a map of its lines, substations or transformers. This script takes
what OpenStreetMap volunteers have mapped and tagged operator=Meralco, plus places mapped as
Meralco offices, and writes one compact file the map loads on demand:

    frontend/public/grid/meralco-osm.json

It is a picture of what volunteers have surveyed, not Meralco's own records: it is incomplete
(mostly 115 kV and 34.5 kV lines, few transformers) and can be out of date.

Run it again to refresh (needs internet; standard library only):

    python scripts/fetch_meralco_grid.py
    python scripts/fetch_meralco_grid.py --cache some/folder    # keep the raw downloads

Data (c) OpenStreetMap contributors, Open Database License. Keep the credit on the map.
"""
from __future__ import annotations

import argparse
import json
import math
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "grid" / "meralco-osm.json"
BBOX = "(14.05,120.75,15.0,121.4)"          # Metro Manila with Bulacan, Rizal, Cavite and Laguna around it
AGENT = "grid-layer-build-script/1.0"
SERVERS = ["https://overpass-api.de/api/interpreter", "https://overpass.openstreetmap.fr/api/interpreter"]
QUERIES = {
    "lines": f'[out:json][timeout:120];way["power"~"^(line|minor_line|cable)$"]{BBOX};out tags geom;',
    "subs": f'[out:json][timeout:60];nwr["power"="substation"]{BBOX};out tags center;',
    "transformers": f'[out:json][timeout:90];(node["power"="transformer"]{BBOX};node["power"="pole"]["transformer"]{BBOX};);out body;',
    "offices": f'[out:json][timeout:90];(nwr["name"~"Meralco",i][!"power"]{BBOX};nwr["operator"~"Meralco",i]["office"]{BBOX};'
               f'nwr["brand"~"Meralco",i]{BBOX};);out tags center;',
}
OFFICE_TAGS = {"energy_supplier", "company", "utility", "utilities", "power_utility", "electricity", "electrlic_utility",
               "government", "financial", "office"}
OFFICE_WORDS = ("business center", "business centre", "business office", "branch", "sector", "extension office", "collection office")
NOT_OFFICES = ("bayad", "fitness", "powertech", "travel", "theat", "foundation", "museum", "school", "village", "avenue",
               "road", "street", "gate", "parking", "terminal", "substation", "main building")


def overpass(name: str, cache: Path | None) -> dict:
    if cache and (cache / f"{name}.json").exists():
        return json.loads((cache / f"{name}.json").read_text(encoding="utf-8"))
    body = urllib.parse.urlencode({"data": QUERIES[name]}).encode()
    for attempt in range(6):
        for server in SERVERS:
            try:
                req = urllib.request.Request(server, data=body, headers={"User-Agent": AGENT})
                with urllib.request.urlopen(req, timeout=180) as res:
                    text = res.read().decode("utf-8")
                data = json.loads(text)                # a busy server answers with an HTML page instead
                if cache:
                    cache.mkdir(parents=True, exist_ok=True)
                    (cache / f"{name}.json").write_text(text, encoding="utf-8")
                return data
            except Exception as error:                 # noqa: BLE001 - any failure means "try the next server"
                print(f"  {name}: {server.split('/')[2]} said {str(error)[:70]}")
        time.sleep(8 * (attempt + 1))
    raise SystemExit(f"Could not download {name}. The public servers are busy; try again in a few minutes.")


def is_meralco(tags: dict) -> bool:
    return "meralco" in tags.get("operator", "").lower()


def kilovolts(tags: dict) -> float | None:
    """Highest voltage on the tag, in kV. '13800;230' is a 13.8 kV line with a 230 V circuit under it."""
    values = []
    for part in tags.get("voltage", "").replace(",", ";").split(";"):
        try:
            values.append(float(part))
        except ValueError:
            pass
    return round(max(values) / 1000, 2) if values else None


def metres(a, b) -> float:
    return math.hypot((a[0] - b[0]) * 110_574, (a[1] - b[1]) * 111_320 * math.cos(math.radians(a[0])))


def simplify(points: list, tolerance: float = 4.0) -> list:
    """Douglas-Peucker: drops points that move the line by less than `tolerance` metres."""
    if len(points) < 3:
        return points
    (ay, ax), (by, bx) = points[0], points[-1]
    k = 111_320 * math.cos(math.radians(ay))
    dx, dy = (bx - ax) * k, (by - ay) * 110_574
    length = math.hypot(dx, dy) or 1e-9
    far, index = 0.0, 0
    for i in range(1, len(points) - 1):
        px, py = (points[i][1] - ax) * k, (points[i][0] - ay) * 110_574
        d = abs(dx * py - dy * px) / length
        if d > far:
            far, index = d, i
    if far <= tolerance:
        return [points[0], points[-1]]
    return simplify(points[: index + 1], tolerance)[:-1] + simplify(points[index:], tolerance)


def place(el: dict) -> tuple:
    c = el.get("center") or el
    return round(c["lat"], 5), round(c["lon"], 5)


def city_of(lat: float, lon: float) -> str:
    """Town or city for an office that was mapped without an address (OpenStreetMap's own geocoder)."""
    url = "https://nominatim.openstreetmap.org/reverse?" + urllib.parse.urlencode(
        {"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 10, "accept-language": "en"})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": AGENT}), timeout=30) as res:
            a = json.loads(res.read().decode("utf-8")).get("address", {})
        return a.get("city") or a.get("town") or a.get("municipality") or a.get("village") or ""
    except Exception:                                  # noqa: BLE001 - a missing city is not worth failing for
        return ""
    finally:
        time.sleep(1.1)                                # the geocoder allows one request a second


def build(cache: Path | None) -> dict:
    raw = {name: overpass(name, cache) for name in QUERIES}

    lines = []
    for way in raw["lines"]["elements"]:
        tags = way.get("tags", {})
        if not is_meralco(tags):
            continue
        points = simplify([(p["lat"], p["lon"]) for p in way["geometry"]])
        flat = [round(v, 5) for point in points for v in point]
        lines.append([kilovolts(tags), "cable" if tags["power"] == "cable" else "line", flat])
    lines.sort(key=lambda l: l[0] or 0)                # highest voltage drawn last, on top

    substations = []
    for el in raw["subs"]["elements"]:
        tags = el.get("tags", {})
        if not is_meralco(tags):
            continue
        lat, lon = place(el)
        name = tags.get("name:en") or tags.get("name") or "Substation"
        substations.append({"name": name, "kv": kilovolts(tags), "lat": lat, "lon": lon})
    substations.sort(key=lambda s: s["name"])

    transformers = []
    for el in raw["transformers"]["elements"]:
        tags = el.get("tags", {})
        if tags.get("operator") and not is_meralco(tags):
            continue                                    # someone else's; unlabelled ones are kept
        transformers.append([round(el["lat"], 5), round(el["lon"], 5)])

    cities = {}
    if cache and (cache / "cities.json").exists():
        cities = json.loads((cache / "cities.json").read_text(encoding="utf-8"))
    offices = []
    for el in raw["offices"]["elements"]:
        tags = el.get("tags", {})
        name = (tags.get("name") or tags.get("brand") or "").strip()
        low = name.lower()
        if "highway" in tags or any(word in low for word in NOT_OFFICES):
            continue
        if not (tags.get("office") in OFFICE_TAGS or any(word in low for word in OFFICE_WORDS)):
            continue
        lat, lon = place(el)
        if any(metres((lat, lon), (o["lat"], o["lon"])) < 150 for o in offices):
            continue                                    # the same office mapped twice
        city = tags.get("addr:city") or cities.get(f"{lat},{lon}")
        if city is None:
            city = cities[f"{lat},{lon}"] = city_of(lat, lon)
        if low in ("meralco", "meralco business center", ""):
            name = "Meralco business center" if "business" in low else "Meralco office"
        offices.append({"name": name, "city": city or "", "lat": lat, "lon": lon})
    if cache:
        (cache / "cities.json").write_text(json.dumps(cities, ensure_ascii=False), encoding="utf-8")
    offices.sort(key=lambda o: (o["city"], o["name"]))

    return {
        "source": "OpenStreetMap contributors",
        "licence": "Open Database License (ODbL) 1.0",
        "note": "Mapped by volunteers. Not Meralco's own records; incomplete and possibly out of date.",
        "fetched": date.today().isoformat(),
        "osm_data_as_of": raw["lines"].get("osm3s", {}).get("timestamp_osm_base", ""),
        "lines": lines, "substations": substations, "transformers": transformers, "offices": offices,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cache", type=Path, help="folder to keep (and reuse) the raw downloads")
    grid = build(parser.parse_args().cache)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(grid, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(grid['lines'])} line sections, {len(grid['substations'])} substations, "
          f"{len(grid['transformers'])} transformers, {len(grid['offices'])} offices")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} kB)")
