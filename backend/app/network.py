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
    Asset("F1", "segment", "Power line along EDSA (Ortigas to Cubao)", "Mandaluyong to Quezon City", 14.604, 121.058, "SUB"),
    Asset("LS-01", "switch", "Switch on Aurora Blvd, Cubao", "Quezon City", 14.619, 121.053, "F1"),
    Asset("TL-01", "lateral", "Tap line to Philcoa", "Quezon City", 14.6468, 121.0483, "LS-01"),
    Asset("PL-01", "pole", "Pole before Philcoa", "Quezon City", 14.6501, 121.0519, "TL-01"),
    Asset("FC-01", "fuse", "Fuse cutout at Philcoa", "Quezon City", 14.6515, 121.0497, "PL-01"),
    Asset("T-01", "transformer", "Transformer near Philcoa, Diliman", "Quezon City", 14.651, 121.049, "FC-01"),
    Asset("F2", "segment", "Power line along EDSA (Cubao to Balintawak)", "Quezon City", 14.640, 121.025, "LS-01"),
    Asset("P-04", "pole", "Pole at Balintawak interchange", "Quezon City", 14.657, 121.004, "F2"),
    Asset("L1", "lateral", "Power line along MacArthur Hwy", "Balintawak to Valenzuela", 14.680, 120.990, "P-04"),
    Asset("TL-02", "lateral", "Tap line to Gen. T. de Leon", "Valenzuela", 14.6932, 120.9897, "L1"),
    Asset("PL-02", "pole", "Pole before Gen. T. de Leon", "Valenzuela", 14.6972, 120.9879, "TL-02"),
    Asset("FC-02", "fuse", "Fuse cutout at Gen. T. de Leon", "Valenzuela", 14.6990, 120.9838, "PL-02"),
    Asset("T-02", "transformer", "Transformer on MacArthur Hwy, Gen. T. de Leon", "Valenzuela", 14.700, 120.983, "FC-02"),
    Asset("TL-03", "lateral", "Tap line to Malhacan", "Meycauayan, Bulacan", 14.7240, 120.9599, "L1"),
    Asset("PL-03", "pole", "Pole before Malhacan", "Meycauayan, Bulacan", 14.7292, 120.9613, "TL-03"),
    Asset("FC-03", "fuse", "Fuse cutout at Malhacan", "Meycauayan, Bulacan", 14.7339, 120.9614, "PL-03"),
    Asset("T-03", "transformer", "Transformer in Malhacan", "Meycauayan, Bulacan", 14.735, 120.961, "FC-03"),
    # East corridor
    Asset("F3", "segment", "Power line along C5 and Marcos Hwy", "Pasig to Marikina", 14.612, 121.085, "SUB"),
    Asset("LS-07", "switch", "Switch on Marcos Hwy", "Marikina", 14.640, 121.100, "F3"),
    Asset("TL-04", "lateral", "Tap line to San Roque", "Antipolo, Rizal", 14.5935, 121.1718, "LS-07"),
    Asset("PL-04", "pole", "Pole before San Roque", "Antipolo, Rizal", 14.5881, 121.1720, "TL-04"),
    Asset("FC-04", "fuse", "Fuse cutout at San Roque", "Antipolo, Rizal", 14.5871, 121.1757, "PL-04"),
    Asset("T-04", "transformer", "Transformer on Sumulong Hwy, San Roque", "Antipolo, Rizal", 14.586, 121.176, "FC-04"),
    Asset("L2", "lateral", "Power line along Gen. Luna Ave", "Marikina to San Mateo", 14.670, 121.112, "LS-07"),
    Asset("TL-05", "lateral", "Tap line to Guitnang Bayan I", "San Mateo, Rizal", 14.6896, 121.1168, "L2"),
    Asset("PL-05", "pole", "Pole before Guitnang Bayan I", "San Mateo, Rizal", 14.6950, 121.1176, "TL-05"),
    Asset("FC-05", "fuse", "Fuse cutout at Guitnang Bayan I", "San Mateo, Rizal", 14.6962, 121.1213, "PL-05"),
    Asset("T-05", "transformer", "Transformer in Guitnang Bayan I", "San Mateo, Rizal", 14.697, 121.122, "FC-05"),
    Asset("TL-06", "lateral", "Tap line to San Jose", "Rodriguez, Rizal", 14.7200, 121.1392, "L2"),
    Asset("PL-06", "pole", "Pole before San Jose", "Rodriguez, Rizal", 14.7244, 121.1422, "TL-06"),
    Asset("FC-06", "fuse", "Fuse cutout at San Jose", "Rodriguez, Rizal", 14.7288, 121.1441, "PL-06"),
    Asset("T-06", "transformer", "Transformer in San Jose", "Rodriguez, Rizal", 14.730, 121.144, "FC-06"),
    # South corridor
    Asset("F4", "segment", "Power line along C5 (Ortigas to Taguig)", "Pasig to Taguig", 14.540, 121.040, "SUB"),
    Asset("P-12", "pole", "Pole on Dr. A. Santos Ave, Sucat", "Parañaque", 14.485, 121.045, "F4"),
    Asset("L3", "lateral", "Power line along CAVITEX", "Parañaque to Bacoor", 14.470, 121.000, "P-12"),
    Asset("TL-07", "lateral", "Tap line to Talaba II", "Bacoor, Cavite", 14.4655, 120.9677, "L3"),
    Asset("PL-07", "pole", "Pole before Talaba II", "Bacoor, Cavite", 14.4622, 120.9634, "TL-07"),
    Asset("FC-07", "fuse", "Fuse cutout at Talaba II", "Bacoor, Cavite", 14.4593, 120.9598, "PL-07"),
    Asset("T-07", "transformer", "Transformer in Talaba II", "Bacoor, Cavite", 14.459, 120.960, "FC-07"),
    Asset("LS-05", "switch", "Switch on National Rd, Alabang", "Muntinlupa", 14.423, 121.040, "P-12"),
    Asset("TL-08", "lateral", "Tap line to Landayan", "San Pedro, Laguna", 14.3643, 121.0538, "LS-05"),
    Asset("PL-08", "pole", "Pole before Landayan", "San Pedro, Laguna", 14.3608, 121.0580, "TL-08"),
    Asset("FC-08", "fuse", "Fuse cutout at Landayan", "San Pedro, Laguna", 14.3574, 121.0589, "PL-08"),
    Asset("T-08", "transformer", "Transformer in Landayan", "San Pedro, Laguna", 14.358, 121.058, "FC-08"),
]

@dataclass(frozen=True)
class Area:
    """A barangay served by one transformer. Coordinates are approximate; households are invented."""
    id: str
    transformer: str
    barangay: str
    city: str
    lat: float
    lon: float
    households: int
    critical: tuple[str, ...] = ()


# Three barangays behind each service transformer. Facility names are generic on purpose:
# the storm is synthetic and should not suggest that a real hospital lost power.
AREAS: list[Area] = [
    Area("qc-central", "T-01", "Central", "Quezon City", 14.6480, 121.0470, 1800, ("Barangay health center",)),
    Area("qc-krus-na-ligas", "T-01", "Krus na Ligas", "Quezon City", 14.6445, 121.0618, 1500),
    Area("qc-up-campus", "T-01", "UP Campus", "Quezon City", 14.6545, 121.0647, 1200),

    Area("val-gen-t-de-leon", "T-02", "Gen. T. de Leon", "Valenzuela", 14.6985, 120.9905, 2100, ("Water pumping station",)),
    Area("val-karuhatan", "T-02", "Karuhatan", "Valenzuela", 14.6880, 120.9760, 1700),
    Area("val-paso-de-blas", "T-02", "Paso de Blas", "Valenzuela", 14.7080, 120.9790, 1400),

    Area("mey-malhacan", "T-03", "Malhacan", "Meycauayan, Bulacan", 14.7405, 120.9575, 2400, ("Elementary school (evacuation center)",)),
    Area("mey-pandayan", "T-03", "Pandayan", "Meycauayan, Bulacan", 14.7330, 120.9670, 1900),
    Area("mey-saluysoy", "T-03", "Saluysoy", "Meycauayan, Bulacan", 14.7240, 120.9620, 1300),

    Area("ant-san-roque", "T-04", "San Roque", "Antipolo, Rizal", 14.5860, 121.1760, 2600, ("District hospital",)),
    Area("ant-dela-paz", "T-04", "Dela Paz", "Antipolo, Rizal", 14.5760, 121.1690, 2200),
    Area("ant-san-isidro", "T-04", "San Isidro", "Antipolo, Rizal", 14.5930, 121.1840, 1800),

    Area("sm-guitnang-bayan", "T-05", "Guitnang Bayan I", "San Mateo, Rizal", 14.6960, 121.1210, 2000, ("Water pumping station",)),
    Area("sm-ampid", "T-05", "Ampid I", "San Mateo, Rizal", 14.7040, 121.1180, 1600),
    Area("sm-banaba", "T-05", "Banaba", "San Mateo, Rizal", 14.6830, 121.1140, 1400),

    Area("rod-san-jose", "T-06", "San Jose", "Rodriguez, Rizal", 14.7340, 121.1530, 1700, ("Evacuation center",)),
    Area("rod-burgos", "T-06", "Burgos", "Rodriguez, Rizal", 14.7270, 121.1420, 1300),
    Area("rod-manggahan", "T-06", "Manggahan", "Rodriguez, Rizal", 14.7180, 121.1380, 1100),

    Area("bac-talaba", "T-07", "Talaba II", "Bacoor, Cavite", 14.4500, 120.9580, 2300, ("District hospital",)),
    Area("bac-niog", "T-07", "Niog I", "Bacoor, Cavite", 14.4540, 120.9700, 1900),
    Area("bac-habay", "T-07", "Habay I", "Bacoor, Cavite", 14.4590, 120.9440, 1500),

    Area("sp-landayan", "T-08", "Landayan", "San Pedro, Laguna", 14.3530, 121.0670, 2000, ("Barangay health center",)),
    Area("sp-pacita", "T-08", "Pacita 1", "San Pedro, Laguna", 14.3480, 121.0560, 1800),
    Area("sp-san-antonio", "T-08", "San Antonio", "San Pedro, Laguna", 14.3640, 121.0490, 1500),
]


def households_by_transformer() -> dict[str, int]:
    out: dict[str, int] = {}
    for a in AREAS:
        out[a.transformer] = out.get(a.transformer, 0) + a.households
    return out


# Road nodes: every asset, the substation, and two extra places.
EXTRA_NODES = {
    "MNL": ("Manila", 14.599, 120.984),
    "PSY": ("Pasay", 14.537, 121.000),
}

ROAD_EDGES: list[tuple[str, str, str]] = [
    # Local equipment in front of each transformer is reached along the same street.
    ("TL-01", "PL-01", "local road"), ("PL-01", "FC-01", "local road"), ("FC-01", "T-01", "local road"), ("TL-02", "PL-02", "local road"), ("PL-02", "FC-02", "local road"), ("FC-02", "T-02", "local road"), ("TL-03", "PL-03", "local road"), ("PL-03", "FC-03", "local road"), ("FC-03", "T-03", "local road"), ("TL-04", "PL-04", "local road"), ("PL-04", "FC-04", "local road"), ("FC-04", "T-04", "local road"), ("TL-05", "PL-05", "local road"), ("PL-05", "FC-05", "local road"), ("FC-05", "T-05", "local road"), ("TL-06", "PL-06", "local road"), ("PL-06", "FC-06", "local road"), ("FC-06", "T-06", "local road"), ("TL-07", "PL-07", "local road"), ("PL-07", "FC-07", "local road"), ("FC-07", "T-07", "local road"), ("TL-08", "PL-08", "local road"), ("PL-08", "FC-08", "local road"), ("FC-08", "T-08", "local road"),
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
CREW_DEPOTS = (("crew-1", "Crew 1", "SUB"), ("crew-2", "Crew 2", "PSY"))   # evaluation only
# Where an inspection would start from; drive times in the live view are measured from here.
OFFICES = (("SUB", "Pasig office"), ("PSY", "Pasay office"))


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
