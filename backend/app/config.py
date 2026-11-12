"""Every tunable assumption in one place. Exposed through GET /api/config."""
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Config:
    # Prior chance that an asset of each type failed in the storm.
    prior_failure: dict = field(default_factory=lambda: {
        "segment": 0.06, "lateral": 0.07, "switch": 0.03, "pole": 0.05, "transformer": 0.04,
    })
    # Minutes on site to inspect an asset of each type.
    inspect_minutes: dict = field(default_factory=lambda: {
        "segment": 12, "lateral": 10, "switch": 8, "pole": 6, "transformer": 8,
    })
    max_faults: int = 3               # scenarios cover up to this many simultaneous faults
    report_miss_rate: float = 0.15    # P(no outage report | transformer is out)
    report_false_rate: float = 0.05   # P(outage report | transformer is fine)
    obs_hit_rate: float = 0.95        # P(crew records "damaged" | asset failed)
    obs_false_rate: float = 0.01      # P(crew records "damaged" | asset is fine)
    sim_inconclusive_rate: float = 0.05  # simulator only: chance a visit is inconclusive
    road_speed_kmh: float = 25.0      # post-storm driving speed
    road_detour_factor: float = 1.3   # road distance / straight-line distance
    confidence_threshold: float = 0.85 # posterior at which repair needs count as identified

    # Community reports (people, after de-duplication across channels).
    voice_rate: float = 0.015         # expected people reporting per household that lost power
    voice_dispersion: float = 1.5     # spread of report counts between areas (lower = more uneven)
    false_voice_mean: float = 1.3     # mean people reporting in an area that did NOT lose power
    silent_ratio: float = 0.25        # likely-out area with fewer than this share of expected reports is "quiet"

    # Urgency multiplies the information value of a visit (1 = no extra urgency).
    urgency_reports: float = 1.0      # weight of people reporting (diminishing returns, log scale)
    urgency_households: float = 0.5   # weight of households likely without power
    urgency_critical: float = 0.5     # weight of critical facilities likely without power

    def as_dict(self) -> dict:
        return asdict(self)


CONFIG = Config()
