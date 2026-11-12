# FirstLook

An information-driven inspection planner for post-storm power restoration. *Know where to look next.*

FirstLook ranks field inspections by how much each visit is expected to reduce uncertainty about the damage, per minute of travel and inspection. Dispatchers keep control of assignments, road closures and access restrictions.

All data is synthetic: 20 invented assets laid over real places in Greater Manila (Metro Manila, Bulacan, Rizal, Cavite, Laguna), two assessment crews and 210 damage scenarios covering up to two simultaneous faults.

## How it works

1. **Combine** outage reports, asset connectivity and road access.
2. **Model** damage scenarios and weigh them against the reports (Bayesian update).
3. **Rank** each inspection by expected information gain ÷ (travel + inspection minutes).
4. **Inspect** and record the result: damaged, intact or inconclusive.
5. **Update** the scenarios and the next recommendation. Inconclusive visits change nothing.

## Run it

Backend (Python 3.11+):

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # macOS/Linux: .venv/bin/python
.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

Frontend (Node 18+), in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The map tiles come from OpenStreetMap, so the map needs an internet connection.

Tests:

```bash
cd backend
.venv/Scripts/python -m pytest -q
```

## Screens

- **Console** – ranked inspections, the network map, damage scenarios, repair needs and the evidence log. Click a road on the map to close or reopen it.
- **Field** – what a crew sees: the assignment, the objective and three buttons to record the result.
- **Evaluation** – simulated storms comparing FirstLook with nearest-first and fixed-order inspection, plus a sensitivity check and every assumption the engine uses.

## Layout

| Path | Contents |
| --- | --- |
| `backend/app/config.py` | Every tunable assumption |
| `backend/app/network.py` | Synthetic assets and road graph |
| `backend/app/engine.py` | Scenario model, posterior, information gain |
| `backend/app/state.py` | Storm event, crews, recommendations, explanations |
| `backend/app/simulation.py` | Strategy comparison |
| `backend/app/main.py` | FastAPI endpoints under `/api` |
| `frontend/src` | React + Leaflet interface |

## Limits

Recommendations depend on scenario coverage and data quality. Routes follow a simplified road graph, not turn-by-turn streets. Evaluation numbers describe relative behaviour on synthetic storms, not field performance.
