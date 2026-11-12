"""Gives the exercise's power lines a realistic path: along the roads between the points they connect.

The network in backend/app/network.py only knows where each piece of equipment is. Drawn as straight
strokes, a "line along EDSA" would cut across the city. This script asks a public road router (OSRM,
which uses OpenStreetMap roads) for the road path of every connection and saves the result once:

    frontend/public/grid/network-routes.json      {"SUB>F1": [lat, lon, lat, lon, ...], ...}

Connections: substation and equipment to the equipment they feed, and each transformer to the
barangays it serves. A connection the router cannot path sensibly is left out and drawn straight.

Run from the repository root with the backend's Python (needs internet, about a minute):

    backend/.venv/Scripts/python scripts/fetch_network_routes.py

Road data (c) OpenStreetMap contributors, Open Database License. Keep the credit on the map.
"""
from __future__ import annotations

import json
import math
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.network import AREAS, ASSETS, SUBSTATION  # noqa: E402

OUT = ROOT / "frontend" / "public" / "grid" / "network-routes.json"
ROUTER = "https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
AGENT = "grid-layer-build-script/1.0"


def metres(a, b) -> float:
    return math.hypot((a[0] - b[0]) * 110_574, (a[1] - b[1]) * 111_320 * math.cos(math.radians(a[0])))


def simplify(points: list, tolerance: float = 6.0) -> list:
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


def road_path(a, b) -> list | None:
    url = ROUTER.format(lat1=a[0], lon1=a[1], lat2=b[0], lon2=b[1])
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": AGENT}), timeout=40) as res:
                data = json.loads(res.read().decode("utf-8"))
            if data.get("code") != "Ok":
                return None
            points = [(lat, lon) for lon, lat in data["routes"][0]["geometry"]["coordinates"]]
            along = sum(metres(p, q) for p, q in zip(points, points[1:]))
            if along > 2.0 * max(metres(a, b), 300):        # a long way round (one-way loops, ramps): not how a line runs
                return None
            return [a, *simplify(points), b]
        except Exception as error:                           # noqa: BLE001 - try again, then give up on this one
            print(f"    retry: {str(error)[:60]}")
            time.sleep(3 * (attempt + 1))
    return None


if __name__ == "__main__":
    pos = {a.id: (a.lat, a.lon) for a in ASSETS}
    pos["SUB"] = (SUBSTATION["lat"], SUBSTATION["lon"])
    links = [(a.parent, a.id, pos[a.parent], pos[a.id]) for a in ASSETS]
    links += [(a.transformer, a.id, pos[a.transformer], (a.lat, a.lon)) for a in AREAS]
    routes, straight = {}, []
    for start, end, a, b in links:
        path = road_path(a, b) if metres(a, b) > 120 else None
        if path:
            routes[f"{start}>{end}"] = [round(v, 5) for p in path for v in p]
        else:
            straight.append(f"{start}>{end}")
        print(f"  {start:>6} > {end:<18} {'road path, ' + str(len(path)) + ' points' if path else 'straight'}")
        time.sleep(1.1)                                      # the public router asks for at most one request a second
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"source": "Road paths from OSRM on OpenStreetMap data", "routes": routes}, separators=(",", ":")), encoding="utf-8")
    print(f"{len(routes)} road paths, {len(straight)} drawn straight; wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} kB)")
