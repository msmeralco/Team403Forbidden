"""One storm event: reports, crews, observations and dispatcher controls."""
from dataclasses import dataclass

import numpy as np

from .config import CONFIG, Config
from .engine import Model, entropy
from .network import ASSETS, CREW_DEPOTS, DEFAULT_BLOCKED, SUBSTATION, Roads, node_label

RESOURCES = {
    "segment": "Line crew + conductor span",
    "lateral": "Line crew + conductor span",
    "switch": "Switch replacement crew",
    "pole": "Pole replacement + bucket truck",
    "transformer": "Transformer + lift crew",
}
OBJECTIVES = {
    "segment": "Patrol {n} for downed conductors or tree contact.",
    "lateral": "Patrol {n} for downed conductors or tree contact.",
    "switch": "Check whether {n} is open or damaged.",
    "pole": "Check {n} for a broken pole, crossarm or leaning structure.",
    "transformer": "Check {n} for a blown fuse, oil leak or burn marks.",
}
CAVEAT = ("Recommendation depends on scenario coverage (up to two simultaneous faults) "
          "and on the quality of the outage reports.")


class Conflict(ValueError):
    """The request is valid but not allowed in the current state."""


@dataclass
class Crew:
    id: str
    name: str
    node: str
    asset_id: str | None = None
    clock: float = 0.0   # minutes this crew has spent travelling and inspecting


class Session:
    def __init__(self, cfg: Config = CONFIG, seed: int | None = None):
        self.cfg, self.seed = cfg, seed
        self.model = m = Model(ASSETS, cfg)
        self.roads = Roads(DEFAULT_BLOCKED, cfg)
        self.rng = np.random.default_rng(7 if seed is None else seed)
        if seed is None:   # fixed demo storm: one shared fault in the east plus one local failure
            self.truth = m.scenarios.index(tuple(sorted((m.idx["LS-07"], m.idx["T-03"]))))
            self.reported = m.OUT[self.truth].copy()
        else:
            self.truth, self.reported = m.draw_event(self.rng)
        self.report_counts = np.where(self.reported, self.rng.integers(4, 40, len(m.transformers)), 0)
        self.crews = [Crew(*c) for c in CREW_DEPOTS]
        self.observations: list[dict] = []
        self.restricted: set[str] = set()
        self.priority: dict[str, float] = {}
        self.h0 = float(entropy(self.posterior()))
        self.history = [{"t": 0.0, "pct": 100.0}]

    # ---- inference ---------------------------------------------------------
    def posterior(self) -> np.ndarray:
        obs = [(self.model.idx[o["asset_id"]], o["result"]) for o in self.observations]
        return self.model.posterior(self.reported, obs)

    def uncertainty_pct(self, post: np.ndarray) -> float:
        return round(float(entropy(post)) / self.h0 * 100, 1) if self.h0 > 0 else 0.0

    def status(self, asset_id: str) -> str:
        """damaged | intact | inconclusive | uninspected (latest observation wins)."""
        for o in reversed(self.observations):
            if o["asset_id"] == asset_id:
                return o["result"]
        return "uninspected"

    def _crew(self, crew_id: str) -> Crew:
        for c in self.crews:
            if c.id == crew_id:
                return c
        raise KeyError(f"Unknown crew {crew_id}")

    def _asset(self, asset_id: str):
        if asset_id not in self.model.idx:
            raise KeyError(f"Unknown asset {asset_id}")
        return self.model.assets[self.model.idx[asset_id]]

    @property
    def elapsed(self) -> float:
        return max(c.clock for c in self.crews)

    # ---- recommendations ---------------------------------------------------
    def _reason(self, i: int) -> str:
        m, a = self.model, self.model.assets[i]
        below = [m.ids[t] for row, t in enumerate(m.transformers)
                 if m.upstream[row, i] and self.reported[row]]
        if a.type == "transformer":
            return ("Confirms or rules out a local failure behind its own outage reports."
                    if below else "No reports here; a visit mainly rules it out.")
        if len(below) >= 2:
            return (f"Tells one shared fault here, cutting {len(below)} reporting transformers, "
                    "apart from separate local failures downstream.")
        if len(below) == 1:
            return f"Checks whether the outage at {below[0]} starts here or at the transformer itself."
        return "No reports downstream; a visit mainly rules it out."

    def recommendations(self) -> tuple[list[dict], list[dict]]:
        m = self.model
        post = self.posterior()
        gain, marg = m.info_gain(post), m.marginals(post)
        assigned = {c.asset_id for c in self.crews if c.asset_id}
        free = [c for c in self.crews if not c.asset_id] or self.crews
        recs, excluded = [], []
        for i, a in enumerate(m.assets):
            if self.status(a.id) in ("damaged", "intact") or a.id in assigned:
                continue
            if a.id in self.restricted:
                excluded.append({"asset_id": a.id, "name": a.name, "reason": "Restricted by dispatcher"})
                continue
            options = [(self.roads.minutes(c.asset_id or c.node, a.id), c) for c in free]
            options = [o for o in options if o[0] is not None]
            if not options:
                excluded.append({"asset_id": a.id, "name": a.name, "reason": "No open road access"})
                continue
            travel, crew = min(options, key=lambda o: o[0])
            inspect = self.cfg.inspect_minutes[a.type]
            weight = self.priority.get(a.id, 1.0)
            recs.append({
                "asset_id": a.id, "name": a.name, "type": a.type, "place": a.place,
                "score": float(gain[i]) / (travel + inspect) * 60 * weight,   # bits per hour
                "info_gain_bits": round(float(gain[i]), 3),
                "p_damaged": round(float(marg[i]), 3),
                "travel_min": round(travel), "inspect_min": inspect,
                "crew_id": crew.id, "crew_name": crew.name,
                "route": self.roads.route(crew.asset_id or crew.node, a.id),
                "priority": weight, "reason": self._reason(i),
            })
        recs.sort(key=lambda r: -r["score"])
        top = recs[0]["score"] if recs and recs[0]["score"] > 0 else 1.0
        for rank, r in enumerate(recs, 1):
            r["rank"], r["score_rel"] = rank, round(r["score"] / top, 3)
            r["score"] = round(r["score"], 3)
        return recs, excluded

    def explain(self, asset_id: str) -> dict:
        m, a = self.model, self._asset(asset_id)
        i = m.idx[asset_id]
        post = self.posterior()
        p_d, post_d, post_i = m.outcome_posteriors(post, i)

        def branch(after: np.ndarray, prob: float) -> dict:
            top = np.argsort(-after)[:4]
            return {"probability": round(prob, 3), "uncertainty_pct": self.uncertainty_pct(after),
                    "scenarios": [{"label": m.label(int(s)), "before": round(float(post[s]), 3),
                                   "after": round(float(after[s]), 3)} for s in top]}

        rec = next((r for r in self.recommendations()[0] if r["asset_id"] == asset_id), None)
        return {
            "asset_id": a.id, "name": a.name, "type": a.type, "place": a.place,
            "establishes": f"Whether {a.name} is damaged. The current estimate is "
                           f"{float(m.marginals(post)[i]):.0%}.",
            "reason": self._reason(i),
            "uncertainty_pct": self.uncertainty_pct(post),
            "info_gain_bits": round(float(m.info_gain(post)[i]), 3),
            "if_damaged": branch(post_d, p_d), "if_intact": branch(post_i, 1 - p_d),
            "recommendation": rec, "caveat": CAVEAT,
        }

    # ---- dispatcher and crew actions ---------------------------------------
    def assign(self, crew_id: str, asset_id: str) -> None:
        crew, a = self._crew(crew_id), self._asset(asset_id)
        if crew.asset_id:
            raise Conflict(f"{crew.name} is already assigned to {crew.asset_id}")
        if self.status(asset_id) in ("damaged", "intact"):
            raise Conflict(f"{a.name} has already been inspected")
        if asset_id in self.restricted:
            raise Conflict(f"{a.name} is restricted")
        if any(c.asset_id == asset_id for c in self.crews):
            raise Conflict(f"{a.name} is already assigned")
        if self.roads.minutes(crew.node, asset_id) is None:
            raise Conflict(f"No open road from {crew.name} to {a.name}")
        crew.asset_id = asset_id

    def unassign(self, crew_id: str) -> None:
        self._crew(crew_id).asset_id = None

    def observe(self, crew_id: str, asset_id: str, result: str | None, notes: str = "") -> dict:
        crew, a = self._crew(crew_id), self._asset(asset_id)
        if crew.asset_id != asset_id:
            raise Conflict(f"{crew.name} is not assigned to {a.name}")
        travel = self.roads.minutes(crew.node, asset_id)
        if travel is None:
            raise Conflict(f"No open road from {crew.name} to {a.name}")
        simulated = result is None
        if simulated:   # draw the field result from the hidden ground truth
            result = self.model.draw_observation(self.rng, self.truth, self.model.idx[asset_id])
        crew.clock += travel + self.cfg.inspect_minutes[a.type]
        crew.node, crew.asset_id = asset_id, None
        obs = {"id": len(self.observations) + 1, "t": round(crew.clock), "crew_id": crew.id,
               "crew_name": crew.name, "asset_id": asset_id, "asset_name": a.name,
               "result": result, "notes": notes, "simulated": simulated}
        self.observations.append(obs)
        obs["uncertainty_pct"] = self.uncertainty_pct(self.posterior())
        self.history.append({"t": round(self.elapsed), "pct": obs["uncertainty_pct"]})
        return obs

    def restrict(self, asset_id: str, restricted: bool) -> None:
        self._asset(asset_id)
        if restricted and any(c.asset_id == asset_id for c in self.crews):
            raise Conflict("Unassign the crew before restricting this asset")
        (self.restricted.add if restricted else self.restricted.discard)(asset_id)

    def set_priority(self, asset_id: str, weight: float) -> None:
        self._asset(asset_id)
        self.priority[asset_id] = weight

    def block_road(self, edge: str, blocked: bool) -> None:
        self.roads.set_blocked(edge, blocked)

    # ---- views -------------------------------------------------------------
    def scenarios(self, limit: int | None = 6) -> list[dict]:
        m, post = self.model, self.posterior()
        order = np.argsort(-post)[:limit]
        return [{"label": m.label(int(s)), "assets": [m.ids[i] for i in m.scenarios[s]],
                 "prior": round(float(m.prior[s]), 4), "p": round(float(post[s]), 4)} for s in order]

    def resources(self, post: np.ndarray) -> dict:
        m, marg = self.model, self.model.marginals(post)
        expected: dict[str, float] = {}
        for i, a in enumerate(m.assets):
            expected[RESOURCES[a.type]] = expected.get(RESOURCES[a.type], 0.0) + float(marg[i])
        top = int(np.argmax(post))
        return {"identified": bool(post[top] >= self.cfg.confidence_threshold),
                "top_label": m.label(top), "top_p": round(float(post[top]), 3),
                "items": sorted(({"resource": k, "expected": round(v, 2)} for k, v in expected.items()),
                                key=lambda x: -x["expected"])}

    def assets_view(self, post: np.ndarray) -> list[dict]:
        m, marg = self.model, self.model.marginals(post)
        counts = {m.ids[t]: int(self.report_counts[row]) for row, t in enumerate(m.transformers)}
        crew_of = {c.asset_id: c.id for c in self.crews if c.asset_id}
        return [{"id": a.id, "type": a.type, "name": a.name, "place": a.place,
                 "pos": [a.lat, a.lon], "parent": a.parent, "status": self.status(a.id),
                 "p_fail": round(float(marg[i]), 3), "reports": counts.get(a.id, 0),
                 "restricted": a.id in self.restricted, "priority": self.priority.get(a.id, 1.0),
                 "assigned_crew": crew_of.get(a.id), "inspect_min": self.cfg.inspect_minutes[a.type],
                 "objective": OBJECTIVES[a.type].format(n=a.name)} for i, a in enumerate(m.assets)]

    def crews_view(self) -> list[dict]:
        out = []
        for c in self.crews:
            d = {"id": c.id, "name": c.name, "pos": list(self.roads.pos[c.node]),
                 "at": node_label(c.node), "asset_id": c.asset_id, "clock": round(c.clock),
                 "status": "assigned" if c.asset_id else "idle", "route": None, "travel_min": None}
            if c.asset_id and self.roads.minutes(c.node, c.asset_id) is not None:
                d["route"] = self.roads.route(c.node, c.asset_id)
                d["travel_min"] = round(self.roads.minutes(c.node, c.asset_id))
            out.append(d)
        return out

    def state(self) -> dict:
        post = self.posterior()
        recs, excluded = self.recommendations()
        return {
            "event": {"name": "Typhoon drill · Greater Manila", "synthetic": True, "seed": self.seed},
            "substation": {**SUBSTATION, "pos": [SUBSTATION["lat"], SUBSTATION["lon"]]},
            "assets": self.assets_view(post), "roads": self.roads.as_list(), "crews": self.crews_view(),
            "scenarios": self.scenarios(), "scenario_count": len(self.model.scenarios),
            "uncertainty": {"bits": round(float(entropy(post)), 3), "pct": self.uncertainty_pct(post),
                            "history": self.history},
            "elapsed_min": round(self.elapsed),
            "recommendations": recs, "excluded": excluded,
            "log": list(reversed(self.observations)), "resources": self.resources(post),
        }
