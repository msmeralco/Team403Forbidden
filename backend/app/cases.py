"""Test cases: a typhoon first, then the interruptions that follow.

A case is one JSON file in backend/cases/. It lists stages in the order they happen. Each stage
says what is really damaged (the app keeps that hidden, as in a real event), and optionally who
reports and which hazards are reported; anything left out is simulated from the damage.

    {
      "name": "Typhoon, then two interruptions",
      "description": "optional, one line",
      "stages": [
        {"name": "Typhoon Dalisay", "kind": "typhoon", "damaged": ["LS-07", "L2", "T-03"],
         "hazards": {"mey-malhacan": "live_wire"}},
        {"name": "Interruption in Bacoor", "kind": "interruption", "damaged": ["T-07"],
         "reports": {"bac-talaba": 14, "bac-niog": 9}, "seed": 4}
      ]
    }

    damaged   1 to 3 equipment ids from network.py (required)
    kind      "typhoon" or "interruption" (default "interruption" after the first stage)
    hazards   barangay id -> live_wire | fire | pole_down. Leave the key out to let the simulation decide; {} means none.
    reports   barangay id -> people reporting. Leave out to simulate from the damage.
    seed      any whole number; the same seed gives the same simulated messages (default 1)

Loading a stage starts it fresh: the earlier stage's results are not carried over.
"""
from __future__ import annotations

import json
from pathlib import Path

from .config import CONFIG
from .network import AREAS, ASSETS

FOLDER = Path(__file__).resolve().parent.parent / "cases"
KINDS = ("typhoon", "interruption")
HAZARDS = ("live_wire", "fire", "pole_down")


def _check(path: Path) -> dict:
    """Read one case file and make sure the app can run it. Raises ValueError naming what is wrong."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise ValueError(f"not valid JSON ({e})") from e
    assets, areas = {a.id for a in ASSETS}, {a.id for a in AREAS}
    if not isinstance(data, dict) or not isinstance(data.get("stages"), list) or not data["stages"]:
        raise ValueError('needs a "stages" list with at least one stage')
    stages = []
    for n, stage in enumerate(data["stages"], 1):
        where = f"stage {n}"
        if not isinstance(stage, dict):
            raise ValueError(f"{where} must be an object")
        damaged = stage.get("damaged")
        if not isinstance(damaged, list) or not 1 <= len(set(damaged)) <= CONFIG.max_faults:
            raise ValueError(f'{where}: "damaged" must list 1 to {CONFIG.max_faults} equipment ids')
        unknown = [a for a in damaged if a not in assets]
        if unknown:
            raise ValueError(f"{where}: unknown equipment {', '.join(map(str, unknown))}")
        kind = stage.get("kind", "typhoon" if n == 1 else "interruption")
        if kind not in KINDS:
            raise ValueError(f'{where}: "kind" must be one of {", ".join(KINDS)}')
        out = {"name": str(stage.get("name") or f"Stage {n}"), "kind": kind, "damaged": sorted(set(damaged)),
               "seed": int(stage.get("seed", 1))}
        if "hazards" in stage:
            bad = [k for k, v in stage["hazards"].items() if k not in areas or v not in HAZARDS]
            if bad:
                raise ValueError(f"{where}: hazards must map a barangay id to one of {', '.join(HAZARDS)} (check {', '.join(bad)})")
            out["hazards"] = dict(stage["hazards"])
        if "reports" in stage:
            bad = [k for k, v in stage["reports"].items() if k not in areas or not isinstance(v, int) or v < 0]
            if bad:
                raise ValueError(f"{where}: reports must map a barangay id to a whole number of people (check {', '.join(bad)})")
            out["reports"] = dict(stage["reports"])
        stages.append(out)
    return {"id": path.stem, "name": str(data.get("name") or path.stem), "description": str(data.get("description") or ""), "stages": stages}


def load_all(folder: Path = FOLDER) -> tuple[list[dict], list[str]]:
    """Every usable case, and a plain message for each file that could not be used."""
    cases, errors = [], []
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            cases.append(_check(path))
        except ValueError as e:
            errors.append(f"{path.name}: {e}")
    return cases, errors


def find(case_id: str, folder: Path = FOLDER) -> dict | None:
    return next((c for c in load_all(folder)[0] if c["id"] == case_id), None)


def summary(case: dict, stage: int | None = None) -> dict:
    """What the screen needs: names only. What is damaged stays hidden."""
    return {"id": case["id"], "name": case["name"], "description": case["description"], "stage": stage,
            "stages": [{"name": s["name"], "kind": s["kind"]} for s in case["stages"]]}
