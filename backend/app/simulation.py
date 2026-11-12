"""Compare FIRSTLOOK with nearest-first and fixed-order inspection on simulated storms."""
import numpy as np

from .config import CONFIG, Config
from .engine import Model, entropy
from .network import CREW_DEPOTS, Roads

STRATEGIES = [
    ("firstlook", "FIRSTLOOK"),
    ("nearest", "Nearest-first"),
    ("fixed", "Fixed order"),
]
GRID = np.arange(0, 481, 10)   # minutes at which the uncertainty curve is sampled


def run_once(truth_model: Model, planner: Model, roads: Roads, cfg: Config,
             rng: np.random.Generator, strategy: str, truth: int, reported: np.ndarray) -> dict:
    """Two crews inspect until one scenario passes the confidence threshold."""
    n = len(planner.assets)
    crews = [{"node": depot, "t": 0.0, "pending": None} for _, _, depot in CREW_DEPOTS]
    obs: list[tuple[int, str]] = []
    done: set[int] = set()
    post = planner.posterior(reported, obs)
    h0 = float(entropy(post)) or 1.0
    series = [(0.0, 100.0)]
    travel_total, visits, identified_at, last_t = 0.0, 0, None, 0.0

    while True:
        crew = min(crews, key=lambda c: c["t"])
        if crew["t"] == float("inf"):
            break
        if crew["pending"] is not None:
            a, crew["pending"], last_t = crew["pending"], None, crew["t"]
            result = truth_model.draw_observation(rng, truth, a, cfg.sim_inconclusive_rate)
            visits += 1
            if result != "inconclusive":
                done.add(a)
                obs.append((a, result))
                post = planner.posterior(reported, obs)
            series.append((crew["t"], float(entropy(post)) / h0 * 100))
            if post.max() >= cfg.confidence_threshold:
                identified_at = crew["t"]
                break
        taken = {c["pending"] for c in crews}
        options = [(a, roads.minutes(crew["node"], planner.ids[a])) for a in range(n)
                   if a not in done and a not in taken]
        options = [(a, m) for a, m in options if m is not None]
        if not options:
            crew["t"] = float("inf")
            continue
        if strategy == "firstlook":
            gain = planner.info_gain(post)
            a, minutes = max(options, key=lambda o: gain[o[0]] / (
                o[1] + cfg.inspect_minutes[planner.assets[o[0]].type]))
        elif strategy == "nearest":
            a, minutes = min(options, key=lambda o: (o[1], o[0]))
        else:   # fixed order: substation outward
            a, minutes = min(options, key=lambda o: o[0])
        crew["t"] += minutes + cfg.inspect_minutes[planner.assets[a].type]
        crew["node"], crew["pending"] = planner.ids[a], a
        travel_total += minutes

    end = identified_at if identified_at is not None else last_t
    times = np.array([t for t, _ in series])
    values = np.array([v for _, v in series])
    curve = values[np.searchsorted(times, GRID, side="right") - 1]   # step function, held at the end
    return {"total_min": end, "travel_min": travel_total, "visits": visits,
            "identified": identified_at is not None,
            "correct": bool(int(np.argmax(post)) == truth), "curve": curve}


def evaluate(runs: int = 200, seed: int = 1, roads: Roads | None = None, cfg: Config = CONFIG) -> dict:
    roads = roads or Roads(cfg=cfg)
    model = Model(cfg=cfg)
    scale = np.exp(np.random.default_rng([seed, 999]).normal(0, 0.5, len(model.assets)))
    perturbed = Model(cfg=cfg, prior_scale=scale)   # planner with wrong scenario weights
    arms = [(k, label, model) for k, label in STRATEGIES]
    arms.append(("firstlook_perturbed", "FIRSTLOOK, perturbed weights", perturbed))

    results = {k: [] for k, _, _ in arms}
    for r in range(runs):
        truth, reported = model.draw_event(np.random.default_rng([seed, r]))
        for k, _, planner in arms:
            rng = np.random.default_rng([seed, r, 1])   # same field noise for every strategy
            results[k].append(run_once(model, planner, roads, cfg, rng,
                                       k.split("_")[0], truth, reported))

    def summary(key: str, label: str) -> dict:
        rs = results[key]
        mean = lambda f: round(float(np.mean([r[f] for r in rs])), 2)
        return {"key": key, "label": label, "total_min": mean("total_min"),
                "travel_min": mean("travel_min"), "visits": mean("visits"),
                "identified_rate": mean("identified"), "correct_rate": mean("correct"),
                "curve": [{"t": int(t), "pct": round(float(v), 1)}
                          for t, v in zip(GRID, np.mean([r["curve"] for r in rs], axis=0))]}

    out = [summary(k, label) for k, label, _ in arms]
    return {"runs": runs, "seed": seed, "strategies": out[:3], "sensitivity": out[3],
            "notes": ["Each run draws a hidden damage scenario from the disclosed prior and noisy outage reports.",
                      "Time is measured until one scenario reaches the confidence threshold, "
                      "which is when repair-resource needs count as identified.",
                      "All data is synthetic; results show relative behaviour, not field performance."]}
