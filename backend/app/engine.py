"""Scenario model: Bayesian posterior over damage scenarios and information value.

All functions are pure; the posterior is always recomputed from the prior, the
outage reports and the list of observations.
"""
from itertools import combinations
from math import lgamma

import numpy as np

from .config import CONFIG, Config
from .network import ASSETS, Asset, households_by_transformer

_lgamma = np.frompyfunc(lgamma, 1, 1)


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

        homes = households_by_transformer()
        self.households = np.array([homes.get(assets[t].id, 0) for t in self.transformers], dtype=float)
        self.expected_voices = np.maximum(self.households * cfg.voice_rate, 1.0)

    # ---- likelihoods -------------------------------------------------------
    def voice_likelihoods(self, voices: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """P(k people report | area lost power) and P(k | area is fine), per transformer.

        Lost power: nobody reports with the miss rate (dead phones, evacuated households);
        otherwise the count follows an over-dispersed negative binomial around the expected
        number for the area's size. Fine: stray reports with the false rate, rarely more
        than one or two people (a tripped house breaker, a flicker).
        """
        c, mu, r = self.cfg, self.expected_voices, self.cfg.voice_dispersion
        k = np.asarray(voices, dtype=float)
        log_nb = (_lgamma(k + r) - _lgamma(k + 1) - lgamma(r)).astype(float) \
            + r * np.log(r / (r + mu)) + k * np.log(mu / (r + mu))
        nb0 = (r / (r + mu)) ** r
        p_out = np.where(k == 0, c.report_miss_rate,
                         (1 - c.report_miss_rate) * np.exp(log_nb) / (1 - nb0))
        stay = 1 - 1 / c.false_voice_mean   # geometric tail of stray reports
        p_fine = np.where(k == 0, 1 - c.report_false_rate,
                          c.report_false_rate * (1 - stay) * stay ** np.maximum(k - 1, 0))
        return p_out, p_fine

    def report_likelihood(self, reported: np.ndarray) -> np.ndarray:
        """Likelihood of the outage reports under each scenario.

        A boolean array means "anyone reported behind this transformer"; an integer
        array is the number of distinct people reporting, so many voices count as
        stronger evidence than one.
        """
        c = self.cfg
        reported = np.asarray(reported)
        if reported.dtype == bool:
            p = np.where(self.OUT,
                         np.where(reported, 1 - c.report_miss_rate, c.report_miss_rate),
                         np.where(reported, c.report_false_rate, 1 - c.report_false_rate))
            return p.prod(axis=1)
        p_out, p_fine = self.voice_likelihoods(reported)
        logl = np.where(self.OUT, np.log(p_out), np.log(p_fine)).sum(axis=1)
        return np.exp(logl - logl.max())

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
        return "Damage at " + " and ".join(self.assets[i].name.lower()[0] + self.assets[i].name[1:]
                                           for i in combo)

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

    def draw_voices(self, rng: np.random.Generator, truth: int) -> np.ndarray:
        """Draw how many distinct people report behind each transformer, from the same model."""
        c, r = self.cfg, self.cfg.voice_dispersion
        out = self.OUT[truth]
        voices = np.zeros(len(self.transformers), dtype=int)
        for row in range(len(self.transformers)):
            if out[row]:
                if rng.random() < c.report_miss_rate:
                    continue
                mu = self.expected_voices[row]
                k = 0
                while k == 0:
                    k = int(rng.negative_binomial(r, r / (r + mu)))
                voices[row] = k
            elif rng.random() < c.report_false_rate:
                voices[row] = int(rng.geometric(1 / c.false_voice_mean))
        return voices

    def p_out(self, post: np.ndarray) -> np.ndarray:
        """Probability that each transformer's area is without power."""
        return post @ self.OUT

    def draw_observation(self, rng: np.random.Generator, truth: int, asset: int,
                         inconclusive_rate: float = 0.0) -> str:
        if rng.random() < inconclusive_rate:
            return "inconclusive"
        return "damaged" if rng.random() < self._Ld[truth, asset] else "intact"
