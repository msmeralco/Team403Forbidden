"""Scenario model: Bayesian posterior over damage scenarios and information value.

All functions are pure; the posterior is always recomputed from the prior, the
outage reports and the list of observations.
"""
from itertools import combinations

import numpy as np

from .config import CONFIG, Config
from .network import ASSETS, Asset


def entropy(p: np.ndarray) -> np.ndarray | float:
    """Shannon entropy in bits along axis 0."""
    return -(p * np.log2(np.where(p > 0, p, 1.0))).sum(axis=0)


class Model:
    def __init__(self, assets: list[Asset] = ASSETS, cfg: Config = CONFIG,
                 prior_scale: np.ndarray | None = None):
        self.assets, self.cfg = list(assets), cfg
        self.ids = [a.id for a in assets]
        self.idx = {a.id: i for i, a in enumerate(assets)}
        n = len(assets)
        self.transformers = [i for i, a in enumerate(assets) if a.type == "transformer"]

        # upstream[t, a] = 1 when asset a lies on transformer t's path to the substation
        self.upstream = np.zeros((len(self.transformers), n), dtype=bool)
        for row, t in enumerate(self.transformers):
            node = assets[t].id
            while node != "SUB":
                self.upstream[row, self.idx[node]] = True
                node = assets[self.idx[node]].parent

        p = np.array([cfg.prior_failure[a.type] for a in assets])
        if prior_scale is not None:
            p = np.clip(p * prior_scale, 1e-3, 0.5)
        self.p_fail = p

        self.scenarios: list[tuple[int, ...]] = [
            c for k in range(1, cfg.max_faults + 1) for c in combinations(range(n), k)]
        self.F = np.zeros((len(self.scenarios), n), dtype=bool)   # failed[scenario, asset]
        for s, combo in enumerate(self.scenarios):
            self.F[s, list(combo)] = True
        prior = np.where(self.F, p, 1 - p).prod(axis=1)
        self.prior = prior / prior.sum()
        # out[scenario, transformer]: transformer loses supply under the scenario
        self.OUT = (self.F.astype(int) @ self.upstream.T.astype(int)) > 0
        self._Ld = np.where(self.F, cfg.obs_hit_rate, cfg.obs_false_rate)  # P(obs damaged | scenario)

    # ---- likelihoods -------------------------------------------------------
    def report_likelihood(self, reported: np.ndarray) -> np.ndarray:
        c = self.cfg
        p = np.where(self.OUT,
                     np.where(reported, 1 - c.report_miss_rate, c.report_miss_rate),
                     np.where(reported, c.report_false_rate, 1 - c.report_false_rate))
        return p.prod(axis=1)

    def obs_likelihood(self, asset: int, result: str) -> np.ndarray:
        if result == "damaged":
            return self._Ld[:, asset]
        if result == "intact":
            return 1 - self._Ld[:, asset]
        return np.ones(len(self.scenarios))   # inconclusive carries no information

    def posterior(self, reported: np.ndarray, observations: list[tuple[int, str]] = ()) -> np.ndarray:
        w = self.prior * self.report_likelihood(reported)
        for asset, result in observations:
            w = w * self.obs_likelihood(asset, result)
        return w / w.sum()

    # ---- information value -------------------------------------------------
    def outcome_posteriors(self, post: np.ndarray, asset: int) -> tuple[float, np.ndarray, np.ndarray]:
        """P(observe damaged), posterior if damaged, posterior if intact."""
        jd = post * self._Ld[:, asset]
        ji = post - jd
        return float(jd.sum()), jd / jd.sum(), ji / ji.sum()

    def info_gain(self, post: np.ndarray) -> np.ndarray:
        """Expected entropy reduction (bits) from inspecting each asset."""
        jd = post[:, None] * self._Ld
        ji = post[:, None] - jd
        pd, pi = jd.sum(axis=0), ji.sum(axis=0)
        expected = pd * entropy(jd / pd) + pi * entropy(ji / pi)
        return np.maximum(entropy(post) - expected, 0.0)

    def marginals(self, post: np.ndarray) -> np.ndarray:
        """Probability that each asset has failed."""
        return post @ self.F

    # ---- helpers -----------------------------------------------------------
    def label(self, s: int) -> str:
        combo = self.scenarios[s]
        if len(combo) == 1:
            return f"{self.assets[combo[0]].name} fault"
        return " + ".join(self.ids[i] for i in combo) + " faults"

    def draw_event(self, rng: np.random.Generator) -> tuple[int, np.ndarray]:
        """Draw a hidden ground-truth scenario and noisy outage reports."""
        c = self.cfg
        while True:
            truth = int(rng.choice(len(self.scenarios), p=self.prior))
            out = self.OUT[truth]
            u = rng.random(len(self.transformers))
            reported = np.where(out, u > c.report_miss_rate, u < c.report_false_rate)
            if reported.any():
                return truth, reported

    def draw_observation(self, rng: np.random.Generator, truth: int, asset: int,
                         inconclusive_rate: float = 0.0) -> str:
        if rng.random() < inconclusive_rate:
            return "inconclusive"
        return "damaged" if rng.random() < self._Ld[truth, asset] else "intact"
