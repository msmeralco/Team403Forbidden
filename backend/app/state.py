"""One storm event: community reports, inspection results and dispatcher controls.

FirstLook advises; it does not dispatch or track crews. It ranks the places worth checking,
and whoever goes out reports back what they found, which updates the ranking.
"""
from datetime import datetime, timedelta
from uuid import uuid4

import numpy as np

from .config import CONFIG, Config
from .engine import Model, entropy
from .network import AREAS, ASSETS, DEFAULT_BLOCKED, OFFICES, SUBSTATION, Roads
from .reports import MANILA, SOURCES, STORM, after_repair, all_clear_time, generate, summarize

RESOURCES = {
    "segment": "Line crew + conductor span",
    "lateral": "Line crew + conductor span",
    "switch": "Switch replacement crew",
    "pole": "Pole replacement + bucket truck",
    "transformer": "Transformer + lift crew",
}
OBJECTIVES = {
    "segment": "Drive along the line and look for fallen wires, broken poles or trees on the line.",
    "lateral": "Drive along the line and look for fallen wires, broken poles or trees on the line.",
    "switch": "Check whether the switch is open, burnt or damaged.",
    "pole": "Check for a broken or leaning pole, or a broken crossarm.",
    "transformer": "Check for a blown fuse, oil leak, burn marks or a fallen transformer.",
}
PLAIN_TYPE = {"segment": "power line", "lateral": "power line", "switch": "switch",
              "pole": "pole", "transformer": "transformer"}
CAVEAT = ("Recommendation depends on scenario coverage (up to two simultaneous faults) "
          "and on the quality of the outage reports.")

# The fixed demo storm. People reporting per barangay (after de-duplication), one live
# wire in Meycauayan, and a few damage clues. Rodriguez lost power, but few people could
# report it: a "quiet area". Central QC and Landayan send a few stray reports.
# Three breaks: the Malhacan transformer, the Marcos Hwy switch, and a hidden second break
# on the Gen. Luna Ave line behind it, which only shows up once the switch is repaired.
DEMO_TRUTH = ("LS-07", "L2", "T-03")
DEMO_VOICES = {
    "mey-malhacan": 26, "mey-pandayan": 18, "mey-saluysoy": 11,
    "ant-san-roque": 40, "ant-dela-paz": 30, "ant-san-isidro": 22,
    "sm-guitnang-bayan": 28, "sm-ampid": 20, "sm-banaba": 12,
    "rod-san-jose": 4, "rod-burgos": 3, "rod-manggahan": 2,
    "qc-central": 1, "sp-landayan": 2,
}
DEMO_HAZARDS = {"mey-malhacan": "live_wire"}
DEMO_CLUES = {"mey-pandayan": ["transformer"], "sm-ampid": ["tree"], "ant-dela-paz": ["tree"]}


class Conflict(ValueError):
    """The request is valid but not allowed in the current state."""


def _short(city: str) -> str:
    return city.split(",")[0]


def _join(names: list[str], limit: int = 3) -> str:
    names = list(dict.fromkeys(names))
    if len(names) > limit:
        return ", ".join(names[:limit]) + f" and {len(names) - limit} more"
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def about(n: float) -> str:
    """Account counts are known from Meralco's records; shown rounded so they read as such."""
    n = int(round(n))
    return f"{n:,}" if n < 1000 else f"{int(round(n, -2)):,}"


class Session:
    def __init__(self, cfg: Config = CONFIG, seed: int | None = None):
        self.cfg, self.seed, self.id = cfg, seed, uuid4().hex[:8]
        self.started = datetime.now(MANILA)
        self.model = m = Model(ASSETS, cfg)
        self.roads = Roads(DEFAULT_BLOCKED, cfg)
        self.rng = np.random.default_rng(7 if seed is None else seed)
        self.row_of = {m.ids[t]: row for row, t in enumerate(m.transformers)}
        if seed is None:
            self.truth = m.scenarios.index(tuple(sorted(m.idx[a] for a in DEMO_TRUTH)))
            area_voices, hazards, clues = dict(DEMO_VOICES), dict(DEMO_HAZARDS), dict(DEMO_CLUES)
        else:
            area_voices, hazards, clues = self._random_storm()

        out_rows = set(np.flatnonzero(m.OUT[self.truth]))
        out_areas = {a.id for a in AREAS if self.row_of[a.transformer] in out_rows}
        self.all_clear = all_clear_time()
        self.reports = generate(self.rng, area_voices, out_areas, hazards, clues, self.all_clear)
        self.area_stats = summarize(self.reports)
        self.voices = np.zeros(len(m.transformers), dtype=int)
        for a in AREAS:
            self.voices[self.row_of[a.transformer]] += self.area_stats.get(a.id, {}).get("people", 0)
        self.reported = self.voices > 0
        self.hazard_handled: dict[str, str] = {}   # area id -> who made it safe

        self.observations: list[dict] = []
        self.restricted: set[str] = set()
        self.priority: dict[str, float] = {}
        self.repaired: dict[str, dict] = {}       # asset id -> {time, by}
        self.after: list[tuple[int, bool, np.ndarray]] = []   # (transformer row, still dark?, repaired mask)
        # ancestors[i] = assets upstream of asset i, nearest first
        self.ancestors = {}
        for i, a in enumerate(m.assets):
            chain, node = [], a.parent
            while node != "SUB":
                chain.append(m.idx[node])
                node = m.assets[m.idx[node]].parent
            self.ancestors[i] = chain
        self.h0 = float(entropy(self.posterior()))
        self.history = [{"t": 0.0, "pct": 100.0}]

    def _random_storm(self) -> tuple[dict, dict, dict]:
        """Draw a hidden scenario, how many people report per barangay, hazards and clues."""
        m, rng = self.model, self.rng
        while True:
            self.truth = int(rng.choice(len(m.scenarios), p=m.prior))
            voices = m.draw_voices(rng, self.truth)
            if voices.any():
                break
        failed = {m.ids[i] for i in m.scenarios[self.truth]}
        area_voices, hazards, clues = {}, {}, {}
        for row, t in enumerate(m.transformers):
            mine = [a for a in AREAS if a.transformer == m.ids[t]]
            if not mine or not voices[row]:
                continue
            w = np.array([a.households for a in mine], dtype=float)
            for a, k in zip(mine, rng.multinomial(voices[row], w / w.sum())):
                area_voices[a.id] = int(k)
            reporting = [a for a in mine if area_voices.get(a.id)]
            if not m.OUT[self.truth, row] or not reporting:
                continue
            if voices[row] >= 5 and len(hazards) < 2 and rng.random() < 0.35:
                hazards[reporting[int(rng.integers(len(reporting)))].id] = \
                    ("live_wire", "fire", "pole_down")[int(rng.integers(3))]
            upstream_failed = [m.ids[i] for i in np.flatnonzero(m.upstream[row]) if m.ids[i] in failed]
            if upstream_failed and rng.random() < 0.6:
                kind = "transformer" if m.ids[t] in failed else "tree"
                clues.setdefault(reporting[int(rng.integers(len(reporting)))].id, []).append(kind)
        return area_voices, hazards, clues

    # ---- inference ---------------------------------------------------------
    def posterior(self) -> np.ndarray:
        m = self.model
        obs = [(m.idx[o["asset_id"]], o["result"]) for o in self.observations]
        w = m.posterior(self.voices, obs)
        # After a repair, people report whether power came back: evidence about any other
        # break still on that area's path.
        for row, dark, fixed in self.after:
            path = m.upstream[row] & ~fixed
            other = m.F[:, path].any(axis=1)
            # Power coming back is near-proof that nothing else on the path is broken;
            # "still dark" is strong but softer (a single house or a late report can mislead).
            w = w * np.where(other, 0.95 if dark else 0.02, 0.05 if dark else 0.98)
        return w / w.sum()

    def repaired_mask(self) -> np.ndarray:
        m = self.model
        mask = np.zeros(len(m.assets), dtype=bool)
        for aid in self.repaired:
            mask[m.idx[aid]] = True
        return mask

    def p_now(self, post: np.ndarray, extra_fixed: int | None = None) -> np.ndarray:
        """Probability that each transformer's area is dark right now: some break on its
        path that has not been repaired (optionally pretending one more asset is fixed)."""
        m = self.model
        live = ~self.repaired_mask()
        if extra_fixed is not None:
            live[extra_fixed] = False
        out_now = ((m.F & live).astype(int) @ m.upstream.T.astype(int)) > 0
        return post @ out_now

    def uncertainty_pct(self, post: np.ndarray) -> float:
        return round(float(entropy(post)) / self.h0 * 100, 1) if self.h0 > 0 else 0.0

    def status(self, asset_id: str) -> str:
        """damaged | intact | inconclusive | uninspected (latest observation wins)."""
        for o in reversed(self.observations):
            if o["asset_id"] == asset_id:
                return o["result"]
        return "uninspected"

    def _asset(self, asset_id: str):
        if asset_id not in self.model.idx:
            raise KeyError(f"Unknown asset {asset_id}")
        return self.model.assets[self.model.idx[asset_id]]

    @property
    def elapsed(self) -> float:
        """Real minutes since this storm was loaded; the storm clock runs from the all-clear."""
        return (datetime.now(MANILA) - self.started).total_seconds() / 60

    def _nearest_office(self, asset_id: str) -> tuple[float, str, str] | None:
        options = [(self.roads.minutes(node, asset_id), node, name) for node, name in OFFICES]
        options = [o for o in options if o[0] is not None]
        return min(options) if options else None

    # ---- community impact --------------------------------------------------
    def _areas_behind(self, i: int) -> list:
        """Barangays whose supply runs through asset i."""
        m = self.model
        ts = {m.ids[m.transformers[row]] for row in np.flatnonzero(m.upstream[:, i])}
        return [a for a in AREAS if a.transformer in ts]

    def open_hazards(self) -> dict[str, dict]:
        """Area id -> {label: count} for hazards nobody has made safe yet."""
        return {aid: st["hazards"] for aid, st in self.area_stats.items()
                if st["hazards"] and aid not in self.hazard_handled}

    def urgency(self, post: np.ndarray) -> np.ndarray:
        """How much is riding on each asset: people reporting (diminishing returns),
        customer accounts likely without power and critical facilities behind it."""
        m, c = self.model, self.cfg
        pout = self.p_now(post)
        crit = np.zeros(len(m.transformers))
        for a in AREAS:
            crit[self.row_of[a.transformer]] += len(a.critical)
        down = m.upstream.T.astype(float)            # asset x transformer
        people = down @ (self.voices * pout)         # stray reports from areas with power barely count
        accounts = down @ (m.households * pout)
        critical = down @ (crit * pout)
        total_people = max(float((self.voices * pout).sum()), 1.0)
        return (1 + c.urgency_reports * np.log1p(people) / np.log1p(total_people)
                + c.urgency_households * accounts / max(m.households.sum(), 1.0)
                + c.urgency_critical * np.minimum(critical, 1.0))

    def _covers(self, i: int, pout: np.ndarray) -> dict:
        areas = self._areas_behind(i)
        rows = {a.id: self.row_of[a.transformer] for a in areas}
        # Barangays this could still explain: likely dark now (restored or stray-report areas don't count).
        live = [a for a in areas if pout[rows[a.id]] >= 0.3
                or (self.area_stats.get(a.id, {}).get("people") and pout[rows[a.id]] >= 0.1)]
        hazards = self.open_hazards()
        return {
            "areas": [{"id": a.id, "name": f"{a.barangay}, {_short(a.city)}"} for a in live],
            "barangays": len(live),
            "cities": list(dict.fromkeys(_short(a.city) for a in live)),
            "accounts": int(sum(a.households for a in areas)),     # served by this asset, from records
            "people": int(sum(self.area_stats.get(a.id, {}).get("people", 0) for a in live)),
            "reports": int(sum(self.area_stats.get(a.id, {}).get("reports", 0) for a in live)),
            "critical": [f"{f} – {a.barangay}" for a in areas if pout[rows[a.id]] >= 0.3 for f in a.critical],
            "hazards": [{"area": a.barangay, "label": label} for a in areas
                        for label in hazards.get(a.id, {})],
        }

    def _hazard_here(self, i: int) -> list[dict]:
        """Open hazards in the barangays served by this asset, if it is a transformer."""
        a = self.model.assets[i]
        if a.type != "transformer":
            return []
        hazards = self.open_hazards()
        return [{"area": ar.barangay, "city": _short(ar.city), "label": label}
                for ar in AREAS if ar.transformer == a.id for label in hazards.get(ar.id, {})]

    # ---- recommendations ---------------------------------------------------
    def _reason(self, i: int, cov: dict) -> str:
        m, a = self.model, self.model.assets[i]
        below = [m.ids[t] for row, t in enumerate(m.transformers) if m.upstream[row, i] and self.reported[row]]
        reporting = [ar for ar in self._areas_behind(i) if self.area_stats.get(ar.id, {}).get("people")]
        cities = list(dict.fromkeys(_short(ar.city) for ar in reporting))
        if a.type == "transformer":
            if not below:
                return "No one has reported an outage here yet; a visit mainly rules it out."
            where = _join([ar.barangay for ar in reporting]) + (f" ({cities[0]})" if len(cities) == 1 else "")
            return (f"{cov['people']} people reported from {where}. "
                    "A visit confirms whether the problem is this transformer itself.")
        if len(below) >= 2:
            return (f"Outages in {_join(cities)} all run through this {PLAIN_TYPE[a.type]}, which serves "
                    f"about {about(cov['accounts'])} customer accounts. If the damage is here, one repair "
                    "could restore all of them.")
        if len(below) == 1:
            return f"Tells whether the outage in {_join(cities)} starts here or at its own transformer."
        return "No reports downstream; a visit mainly rules it out."

    def _headline(self, i: int, cov: dict, hazard: list[dict]) -> str:
        a = self.model.assets[i]
        if hazard:
            h = hazard[0]
            return f"Safety first: {h['label'].lower()} reported in {h['area']}, {h['city']}"
        if a.type != "transformer" and len(cov["cities"]) >= 2:
            return f"One visit could explain outages in {len(cov['areas'])} barangays"
        if cov["areas"]:
            return f"Check the {PLAIN_TYPE[a.type]} serving {_join([x['name'].split(',')[0] for x in cov['areas']], 2)}"
        return "No reports nearby; a visit only rules it out"

    def recommendations(self) -> tuple[list[dict], list[dict]]:
        m = self.model
        post = self.posterior()
        gain, marg, pout = m.info_gain(post), m.marginals(post), self.p_now(post)
        urg = self.urgency(post)
        recs, excluded = [], []
        for i, a in enumerate(m.assets):
            if self.status(a.id) in ("damaged", "intact"):
                continue
            if a.id in self.restricted:
                excluded.append({"asset_id": a.id, "name": a.name, "reason": "Marked unreachable"})
                continue
            nearest = self._nearest_office(a.id)
            if nearest is None:
                excluded.append({"asset_id": a.id, "name": a.name, "reason": "No open road access"})
                continue
            travel, node, office = nearest
            inspect = self.cfg.inspect_minutes[a.type]
            weight = self.priority.get(a.id, 1.0)
            info_rate = float(gain[i]) / (travel + inspect) * 60      # bits per hour
            cov, hazard = self._covers(i, pout), self._hazard_here(i)
            recs.append({
                "asset_id": a.id, "name": a.name, "type": a.type, "kind": PLAIN_TYPE[a.type], "place": a.place,
                "score": info_rate * float(urg[i]) * weight,
                "info_rate": round(info_rate, 3), "urgency": round(float(urg[i]), 2),
                "info_gain_bits": round(float(gain[i]), 3),
                "p_damaged": round(float(marg[i]), 3),
                "travel_min": round(travel), "inspect_min": inspect, "from": office,
                "route": self.roads.route(node, a.id),
                "priority": weight, "hazard": hazard, "covers": cov,
                "headline": self._headline(i, cov, hazard), "reason": self._reason(i, cov),
            })
        recs.sort(key=lambda r: (not r["hazard"], -r["score"]))
        top = max((r["score"] for r in recs), default=0.0) or 1.0
        for rank, r in enumerate(recs, 1):
            rel = r["score"] / top
            r["rank"], r["score_rel"], r["score"] = rank, round(rel, 3), round(r["score"], 3)
            if r["hazard"]:
                r["tier"] = "critical"
            elif r["info_gain_bits"] < 0.05:   # a visit would tell us almost nothing new
                r["tier"] = "low"
            else:
                r["tier"] = "high" if rel >= 0.6 else "medium" if rel >= 0.25 else "low"
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

        cov = self._covers(i, self.p_now(post))
        rec = next((r for r in self.recommendations()[0] if r["asset_id"] == asset_id), None)
        return {
            "asset_id": a.id, "name": a.name, "type": a.type, "kind": PLAIN_TYPE[a.type], "place": a.place,
            "establishes": f"Whether {a.name} is damaged. The current estimate is "
                           f"{float(m.marginals(post)[i]):.0%}.",
            "reason": self._reason(i, cov), "covers": cov,
            "urgency": round(float(self.urgency(post)[i]), 2),
            "uncertainty_pct": self.uncertainty_pct(post),
            "info_gain_bits": round(float(m.info_gain(post)[i]), 3),
            "if_damaged": branch(post_d, p_d), "if_intact": branch(post_i, 1 - p_d),
            "recommendation": rec, "caveat": CAVEAT,
        }

    # ---- field results and dispatcher controls -----------------------------
    def observe(self, asset_id: str, result: str | None, notes: str = "", by: str = "") -> dict:
        """Record what someone found on site. result None = simulate it from the hidden truth (demo)."""
        a = self._asset(asset_id)
        if self.status(asset_id) in ("damaged", "intact"):
            raise Conflict(f"{a.name} has already been inspected")
        simulated = result is None
        if simulated:
            result = self.model.draw_observation(self.rng, self.truth, self.model.idx[asset_id])
        reporter = by.strip() or ("Field team (demo)" if simulated else "Field team")
        if a.type == "transformer" and result in ("damaged", "intact"):
            for ar in AREAS:   # someone was on site: hazards there are now in their hands
                if ar.transformer == a.id and self.area_stats.get(ar.id, {}).get("hazards"):
                    self.hazard_handled.setdefault(ar.id, reporter)
        now = self.all_clear + timedelta(minutes=self.elapsed)
        obs = {"id": len(self.observations) + 1, "time": now.isoformat(), "t": round(self.elapsed),
               "asset_id": asset_id, "asset_name": a.name, "place": a.place,
               "result": result, "notes": notes, "by": reporter, "simulated": simulated}
        self.observations.append(obs)
        obs["uncertainty_pct"] = self.uncertainty_pct(self.posterior())
        self.history.append({"t": round(self.elapsed), "pct": obs["uncertainty_pct"]})
        return obs

    def repair(self, asset_id: str, by: str = "") -> dict:
        """Record that confirmed damage was repaired. Residents behind it then report whether
        power came back (simulated from the hidden truth), which may reveal another break."""
        m, a = self.model, self._asset(asset_id)
        if self.status(asset_id) != "damaged":
            raise Conflict(f"No confirmed damage at {a.name} to repair")
        if asset_id in self.repaired:
            raise Conflict(f"{a.name} is already repaired")
        i = m.idx[asset_id]
        blocked = [m.assets[j].name for j in self.ancestors[i]
                   if self.status(m.ids[j]) == "damaged" and m.ids[j] not in self.repaired]
        if blocked:
            raise Conflict(f"Repair {blocked[0]} first; nothing behind it can come back until then")
        now = self.all_clear + timedelta(minutes=self.elapsed)
        self.repaired[asset_id] = {"time": now.isoformat(), "by": by.strip() or "Repair team"}
        fixed = self.repaired_mask()
        truth = set(m.scenarios[self.truth])
        new_reports = []
        for row in np.flatnonzero(m.upstream[:, i]):
            path = np.flatnonzero(m.upstream[row] & ~fixed)
            dark = bool(truth & set(path.tolist()))
            self.after.append((int(row), dark, fixed.copy()))
            for ar in AREAS:
                if ar.transformer == m.ids[m.transformers[row]] and (self.area_stats.get(ar.id) or dark):
                    new_reports += after_repair(self.rng, ar, dark, now, 5000 + len(self.reports) + len(new_reports))
        self.reports = sorted(self.reports + new_reports, key=lambda r: r["time"], reverse=True)
        self.area_stats = summarize(self.reports)
        return self.repaired[asset_id]

    def restrict(self, asset_id: str, restricted: bool) -> None:
        self._asset(asset_id)
        (self.restricted.add if restricted else self.restricted.discard)(asset_id)

    def set_priority(self, asset_id: str, weight: float) -> None:
        self._asset(asset_id)
        self.priority[asset_id] = weight

    def block_road(self, edge: str, blocked: bool) -> None:
        self.roads.set_blocked(edge, blocked)

    def set_hazard(self, area_id: str, handled: bool, by: str = "Dispatcher") -> None:
        if area_id not in {a.id for a in AREAS}:
            raise KeyError(f"Unknown area {area_id}")
        if not self.area_stats.get(area_id, {}).get("hazards"):
            raise Conflict("No hazard has been reported in this area")
        if handled:
            self.hazard_handled[area_id] = by
        else:
            self.hazard_handled.pop(area_id, None)

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

    def handoff(self, post: np.ndarray) -> list[dict]:
        """Confirmed damage waiting for repair, with the facts a repair decision needs.
        FirstLook does not rank repairs; this is sorted so what can be fixed now comes first."""
        m = self.model
        fixed = self.repaired_mask()
        hazards = self.open_hazards()
        out = []
        for o in self.observations:
            aid = o["asset_id"]
            if o["result"] != "damaged" or self.status(aid) != "damaged" or aid in self.repaired:
                continue
            if any(x["asset_id"] == aid for x in out):
                continue
            i, a = m.idx[aid], m.assets[m.idx[aid]]
            blocked = [m.assets[j].name for j in self.ancestors[i]
                       if self.status(m.ids[j]) == "damaged" and m.ids[j] not in self.repaired]
            unknown_up = [j for j in self.ancestors[i] if self.status(m.ids[j]) == "uninspected" and not fixed[j]]
            p_up = float(post @ m.F[:, unknown_up].any(axis=1)) if unknown_up else 0.0
            sure, maybe, still = [], [], []
            sure_acc = maybe_acc = 0
            for row in np.flatnonzero(m.upstream[:, i]):
                path = m.upstream[row] & ~fixed
                path[i] = False
                p_other = float(post @ m.F[:, path].any(axis=1))
                for ar in AREAS:
                    if ar.transformer != m.ids[m.transformers[row]]:
                        continue
                    name = f"{ar.barangay}, {_short(ar.city)}"
                    if p_other < 0.15:
                        sure.append(name); sure_acc += ar.households
                    elif p_other < 0.85:
                        maybe.append(name); maybe_acc += ar.households
                    else:
                        still.append(name)
            areas_behind = self._areas_behind(i)
            out.append({
                "asset_id": aid, "name": a.name, "place": a.place, "kind": PLAIN_TYPE[a.type],
                "found_at": o["time"], "found_by": o["by"], "notes": o["notes"],
                "blocked_by": blocked, "p_upstream_damage": round(p_up, 3),
                "restores": {"sure": sure, "sure_accounts": sure_acc, "maybe": maybe,
                             "maybe_accounts": maybe_acc, "still_dark": still},
                "hazards": [{"area": ar.barangay, "label": lab} for ar in areas_behind for lab in hazards.get(ar.id, {})],
                "critical": [f"{f} – {ar.barangay}" for ar in areas_behind for f in ar.critical],
            })
        out.sort(key=lambda h: (bool(h["blocked_by"]), not h["hazards"],
                                -(h["restores"]["sure_accounts"] + 0.5 * h["restores"]["maybe_accounts"])))
        return out

    def repaired_view(self, post: np.ndarray) -> list[dict]:
        m = self.model
        pnow = self.p_now(post)
        out = []
        for aid, info in self.repaired.items():
            i = m.idx[aid]
            back, dark = [], []
            for row in np.flatnonzero(m.upstream[:, i]):
                for ar in AREAS:
                    if ar.transformer == m.ids[m.transformers[row]]:
                        (dark if pnow[row] >= 0.5 else back).append(f"{ar.barangay}, {_short(ar.city)}")
            out.append({"asset_id": aid, "name": m.assets[i].name, "place": m.assets[i].place,
                        **info, "back": back, "still_dark": dark})
        return out

    def assets_view(self, post: np.ndarray) -> list[dict]:
        m, marg = self.model, self.model.marginals(post)
        reports = {}
        for a in AREAS:
            reports[a.transformer] = reports.get(a.transformer, 0) + self.area_stats.get(a.id, {}).get("reports", 0)
        people = {m.ids[t]: int(self.voices[row]) for row, t in enumerate(m.transformers)}
        return [{"id": a.id, "type": a.type, "kind": PLAIN_TYPE[a.type], "name": a.name, "place": a.place,
                 "pos": [a.lat, a.lon], "parent": a.parent, "status": self.status(a.id),
                 "p_fail": round(float(marg[i]), 3), "reports": reports.get(a.id, 0),
                 "people": people.get(a.id, 0),
                 "restricted": a.id in self.restricted, "priority": self.priority.get(a.id, 1.0),
                 "repaired": a.id in self.repaired,
                 "inspect_min": self.cfg.inspect_minutes[a.type],
                 "objective": OBJECTIVES[a.type]} for i, a in enumerate(m.assets)]

    def areas_view(self, post: np.ndarray, recs: list[dict]) -> list[dict]:
        """One entry per barangay: what people report, how likely it is dark, how urgent."""
        m, c = self.model, self.cfg
        pout = self.p_now(post)
        best: dict[str, dict] = {}       # transformer id -> best-ranked rec that covers it
        for r in recs:
            for row in np.flatnonzero(m.upstream[:, m.idx[r["asset_id"]]]):
                best.setdefault(m.ids[m.transformers[row]], r)
        damaged = {o["asset_id"] for o in self.observations
                   if self.status(o["asset_id"]) == "damaged" and o["asset_id"] not in self.repaired}
        out = []
        for a in AREAS:
            st = self.area_stats.get(a.id, {})
            row = self.row_of[a.transformer]
            p = float(pout[row])
            path = {m.ids[i] for i in np.flatnonzero(m.upstream[row])}
            hazard_open = bool(st.get("hazards")) and a.id not in self.hazard_handled
            confirmed = bool(path & damaged)
            restored = bool(path & set(self.repaired)) and p < 0.15
            rec = best.get(a.transformer)
            if hazard_open:
                tier = "critical"
            elif confirmed:
                tier = "confirmed"
            elif restored:
                tier = "restored"
            elif p < 0.15:
                tier = "ok"
            else:
                tier = rec["tier"] if rec and rec["tier"] != "critical" else "medium"
            expected = a.households * c.voice_rate
            out.append({
                "id": a.id, "barangay": a.barangay, "city": a.city, "pos": [a.lat, a.lon],
                "transformer": a.transformer, "accounts": a.households, "critical": list(a.critical),
                "p_out": round(p, 3),
                "people": st.get("people", 0), "reports": st.get("reports", 0),
                "by_source": st.get("by_source", {}), "hazards": st.get("hazards", {}),
                "hazard_open": hazard_open, "hazard_handled_by": self.hazard_handled.get(a.id),
                "clues": st.get("clues", {}), "vulnerable": st.get("vulnerable", 0),
                "noise": st.get("noise", 0), "latest": st.get("latest"),
                "quiet": bool(p >= 0.5 and st.get("people", 0) < c.silent_ratio * expected),
                "expected_people": int(round(expected)),
                "confirmed": confirmed, "restored": restored, "tier": tier,
                "restored_msgs": st.get("restored_msgs", 0), "still_dark_msgs": st.get("still_dark_msgs", 0),
                "best_rank": rec["rank"] if rec else None, "best_asset": rec["asset_id"] if rec else None,
            })
        return out

    def summary(self, areas: list[dict]) -> dict:
        by_source = {k: 0 for k in SOURCES}
        for r in self.reports:
            by_source[r["source"]] += 1
        affected = [a for a in areas if a["people"] and a["tier"] not in ("ok", "restored")]
        return {
            "reports": len(self.reports), "people": int(self.voices.sum()), "by_source": by_source,
            "areas_reporting": len(affected),
            "accounts_reporting": sum(a["accounts"] for a in affected),
            "hazards_open": sum(1 for a in areas if a["hazard_open"]),
            "quiet_areas": sum(1 for a in areas if a["quiet"]),
            "critical_out": sum(len(a["critical"]) for a in areas if a["p_out"] >= 0.5),
            "vulnerable": sum(a["vulnerable"] for a in areas),
            "inspected": sum(1 for o in self.observations if o["result"] != "inconclusive"),
            "restored_areas": sum(1 for a in areas if a["restored"]),
        }

    def state(self) -> dict:
        post = self.posterior()
        recs, excluded = self.recommendations()
        areas = self.areas_view(post, recs)
        now = self.all_clear + timedelta(minutes=self.elapsed)
        return {
            "event": {"id": self.id, "name": f"Typhoon {STORM}", "drill": True, "synthetic": True,
                      "seed": self.seed, "all_clear": self.all_clear.isoformat(), "now": now.isoformat()},
            "substation": {**SUBSTATION, "pos": [SUBSTATION["lat"], SUBSTATION["lon"]]},
            "offices": [{"name": name, "pos": list(self.roads.pos[node])} for node, name in OFFICES],
            "assets": self.assets_view(post), "roads": self.roads.as_list(),
            "areas": areas, "summary": self.summary(areas),
            "scenarios": self.scenarios(), "scenario_count": len(self.model.scenarios),
            "uncertainty": {"bits": round(float(entropy(post)), 3), "pct": self.uncertainty_pct(post),
                            "history": self.history},
            "elapsed_min": round(self.elapsed),
            "recommendations": recs, "excluded": excluded,
            "log": list(reversed(self.observations)), "resources": self.resources(post),
            "handoff": self.handoff(post), "repaired": self.repaired_view(post),
        }
