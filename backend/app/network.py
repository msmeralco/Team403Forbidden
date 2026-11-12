"""Synthetic network laid over Greater Manila: 20 inspectable assets and a road graph.

Locations are real places; the electrical assets, their connectivity and the
outage data are invented for the prototype.
"""
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt

import networkx as nx

from .config import CONFIG, Config


@dataclass(frozen=True)
class Asset:
    id: str
    type: str      # segment | lateral | switch | pole | transformer
    name: str
    place: str
    lat: float
    lon: float
    parent: str    # upstream asset id, or "SUB"


SUBSTATION = {"id": "SUB", "name": "Ortigas source substation", "place": "Pasig", "lat": 14.588, "lon": 121.063}

# Listed from the substation outward (this is also the fixed-order baseline).
ASSETS: list[Asset] = [
    # North corridor
    Asset("F1", "segment", "Line section F1", "Ortigas – Cubao", 14.604, 121.058, "SUB"),
    Asset("LS-01", "switch", "Line switch LS-01", "Cubao, Quezon City", 14.619, 121.053, "F1"),
    Asset("T-01", "transformer", "Transformer T-01", "Diliman, Quezon City", 14.651, 121.049, "LS-01"),
    Asset("F2", "segment", "Line section F2", "Cubao – Balintawak", 14.640, 121.025, "LS-01"),
    Asset("P-04", "pole", "Structure P-04", "Balintawak, Quezon City", 14.657, 121.004, "F2"),
    Asset("L1", "lateral", "Lateral L1", "Balintawak – Valenzuela", 14.680, 120.990, "P-04"),
    Asset("T-02", "transformer", "Transformer T-02", "Valenzuela", 14.700, 120.983, "L1"),
    Asset("T-03", "transformer", "Transformer T-03", "Meycauayan, Bulacan", 14.735, 120.961, "L1"),
    # East corridor
    Asset("F3", "segment", "Line section F3", "Ortigas – Marikina", 14.612, 121.085, "SUB"),
    Asset("LS-07", "switch", "Lateral switch LS-07", "Marikina", 14.640, 121.100, "F3"),
    Asset("T-04", "transformer", "Transformer T-04", "Antipolo, Rizal", 14.586, 121.176, "LS-07"),
    Asset("L2", "lateral", "Lateral L2", "Marikina – San Mateo", 14.670, 121.112, "LS-07"),
    Asset("T-05", "transformer", "Transformer T-05", "San Mateo, Rizal", 14.697, 121.122, "L2"),
    Asset("T-06", "transformer", "Transformer T-06", "Rodriguez, Rizal", 14.730, 121.144, "L2"),
    # South corridor
    Asset("F4", "segment", "Line section F4", "Ortigas – Taguig", 14.540, 121.040, "SUB"),
    Asset("P-12", "pole", "Structure P-12", "Sucat, Parañaque", 14.485, 121.045, "F4"),
    Asset("L3", "lateral", "Lateral L3", "Sucat – Bacoor", 14.470, 121.000, "P-12"),
    Asset("T-07", "transformer", "Transformer T-07", "Bacoor, Cavite", 14.459, 120.960, "L3"),
    Asset("LS-05", "switch", "Line switch LS-05", "Alabang, Muntinlupa", 14.423, 121.040, "P-12"),
    Asset("T-08", "transformer", "Transformer T-08", "San Pedro, Laguna", 14.358, 121.058, "LS-05"),
]

# Road nodes: every asset, the substation, and two extra places.
EXTRA_NODES = {
    "MNL": ("Manila", 14.599, 120.984),
    "PSY": ("Pasay", 14.537, 121.000),
}

ROAD_EDGES: list[tuple[str, str, str]] = [
    ("SUB", "F1", "EDSA"), ("F1", "LS-01", "EDSA"), ("LS-01", "F2", "EDSA"), ("F2", "P-04", "EDSA"),
    ("LS-01", "T-01", "Katipunan Ave"), ("T-01", "F2", "Quezon Ave"),
    ("P-04", "L1", "NLEX"), ("L1", "T-02", "MacArthur Hwy"), ("T-02", "T-03", "MacArthur Hwy"),
    ("L1", "T-03", "NLEX"),
    ("SUB", "F3", "C5"), ("F3", "LS-07", "Marcos Hwy"), ("LS-01", "F3", "Aurora Blvd"),
    ("LS-07", "T-04", "Sumulong Hwy"), ("SUB", "T-04", "Ortigas Ave Ext"),
    ("LS-07", "L2", "J.P. Rizal St"), ("L2", "T-05", "Gen. Luna Ave"), ("T-05", "T-06", "Rodriguez Hwy"),
    ("T-01", "L2", "Batasan – San Mateo Rd"),
    ("SUB", "F4", "C5"), ("F4", "P-12", "SLEX"), ("P-12", "LS-05", "SLEX"),
    ("LS-05", "T-08", "National Hwy"), ("P-12", "L3", "Dr. A. Santos Ave"),
    ("L3", "T-07", "Aguinaldo Hwy"), ("LS-05", "T-07", "Daang Hari"),
    ("MNL", "P-04", "A. Bonifacio Ave"), ("MNL", "SUB", "Magsaysay Blvd"), ("MNL", "PSY", "Roxas Blvd"),
    ("PSY", "F4", "EDSA"), ("PSY", "L3", "CAVITEX"),
]

DEFAULT_BLOCKED = ("F3~LS-07", "L1~T-02")   # Marcos Hwy and MacArthur Hwy flooded
CREW_DEPOTS = (("crew-1", "Crew 1", "SUB"), ("crew-2", "Crew 2", "PSY"))


def edge_id(a: str, b: str) -> str:
    return "~".join(sorted((a, b)))


def _km(p: tuple[float, float], q: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(radians, (*p, *q))
    h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * asin(sqrt(h))


def node_positions() -> dict[str, tuple[float, float]]:
    pos = {SUBSTATION["id"]: (SUBSTATION["lat"], SUBSTATION["lon"])}
    pos.update({a.id: (a.lat, a.lon) for a in ASSETS})
    pos.update({k: (v[1], v[2]) for k, v in EXTRA_NODES.items()})
    return pos


def node_label(node: str) -> str:
    if node == "SUB":
        return SUBSTATION["place"]
    if node in EXTRA_NODES:
        return EXTRA_NODES[node][0]
    return next(a.place for a in ASSETS if a.id == node)


class Roads:
    """Road graph with travel minutes; blocked edges are excluded from routing."""

    def __init__(self, blocked=DEFAULT_BLOCKED, cfg: Config = CONFIG):
        self.pos = node_positions()
        self.g = nx.Graph()
        for a, b, name in ROAD_EDGES:
            km = _km(self.pos[a], self.pos[b]) * cfg.road_detour_factor
            self.g.add_edge(a, b, id=edge_id(a, b), name=name, km=km,
                            minutes=km / cfg.road_speed_kmh * 60)
        self.ids = {d["id"]: (a, b) for a, b, d in self.g.edges(data=True)}
        self.blocked: set[str] = set()
        for e in blocked:
            self.set_blocked(e, True, recompute=False)
        self._recompute()

    def set_blocked(self, eid: str, blocked: bool, recompute: bool = True) -> None:
        if eid not in self.ids:
            raise KeyError(f"Unknown road {eid}")
        (self.blocked.add if blocked else self.blocked.discard)(eid)
        if recompute:
            self._recompute()

    def _recompute(self) -> None:
        self._open = nx.Graph()
        self._open.add_nodes_from(self.g.nodes)
        self._open.add_edges_from(
            (a, b, d) for a, b, d in self.g.edges(data=True) if d["id"] not in self.blocked)
        self._dist = dict(nx.all_pairs_dijkstra_path_length(self._open, weight="minutes"))

    def minutes(self, a: str, b: str) -> float | None:
        """Travel minutes between two nodes, or None when no open road connects them."""
        return self._dist[a].get(b)

    def path(self, a: str, b: str) -> list[str]:
        return nx.shortest_path(self._open, a, b, weight="minutes")

    def route(self, a: str, b: str) -> dict:
        nodes = self.path(a, b)
        names: list[str] = []
        for u, v in zip(nodes, nodes[1:]):
            n = self.g[u][v]["name"]
            if not names or names[-1] != n:
                names.append(n)
        return {"points": [list(self.pos[n]) for n in nodes], "via": names,
                "km": round(sum(self.g[u][v]["km"] for u, v in zip(nodes, nodes[1:])), 1)}

    def as_list(self) -> list[dict]:
        return [{"id": d["id"], "name": d["name"], "a": list(self.pos[a]), "b": list(self.pos[b]),
                 "minutes": round(d["minutes"], 1), "blocked": d["id"] in self.blocked}
                for a, b, d in self.g.edges(data=True)]
