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
    max_faults: int = 2               # scenarios cover up to this many simultaneous faults
    report_miss_rate: float = 0.15    # P(no outage report | transformer is out)
    report_false_rate: float = 0.05   # P(outage report | transformer is fine)
    obs_hit_rate: float = 0.95        # P(crew records "damaged" | asset failed)
    obs_false_rate: float = 0.01      # P(crew records "damaged" | asset is fine)
    sim_inconclusive_rate: float = 0.05  # simulator only: chance a visit is inconclusive
    road_speed_kmh: float = 25.0      # post-storm driving speed
    road_detour_factor: float = 1.3   # road distance / straight-line distance
    confidence_threshold: float = 0.85 # posterior at which repair needs count as identified

    def as_dict(self) -> dict:
        return asdict(self)


CONFIG = Config()
