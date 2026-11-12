# FirstLook

The people's side of a power outage. *Know where to look next.*

After a typhoon, grid equipment can tell a utility which part of the network went down. It cannot see a fallen wire that is still live, a street that is still dark after its area was marked restored, or the hundreds of people posting on Facebook because the hotline is busy. FirstLook reads what those people write and the photos they attach, and turns it into a short list of places worth checking first.

FirstLook advises. It does not dispatch crews, track them, or decide the order of repairs.

All data is simulated: an invented network of 20 pieces of equipment laid over real places in Greater Manila, 24 barangays, and about 300 invented messages per storm. The photos are stand-ins from Wikimedia Commons (`backend/app/photos/CREDITS.md`).

## What it does

1. **Hears everyone.** Outage messages from Facebook posts and comments, X, SMS, the hotline and the Meralco App land on one map. Someone who calls, texts and posts counts as one person.
2. **Reads for meaning.** An AI reader (Claude) reads each message the way a dispatcher would: what is being reported, whether someone is in danger, whether a vulnerable person is mentioned, and where it is. It also looks at attached photos and says what damage is visible.
3. **Puts safety first.** Live wires, sparks and fallen poles are pinned to the top, whether a keyword rule or the AI reader found them.
4. **Ranks where to check next**, with a plain reason for each place, and re-ranks when a result is recorded.
5. **Hands over confirmed damage for repair** with what each repair would bring back and what must be fixed first.
6. **Notices who is still dark after a repair** and puts the likely second break back on the list.

### The AI reader's two rules

- **It can raise a flag, never lower one.** Anything the keyword rules flagged stays flagged, whatever the AI thinks.
- **Without a key or a connection, everything still works** on the keyword rules alone. The screen says which one read each message.

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

Open http://localhost:5173.

### Turning on the AI reader

Create `backend/.env` (ignored by git) with an Anthropic API key, then restart the backend:

```
ANTHROPIC_API_KEY=your-key
```

- The default model is `claude-opus-5-5`. Set `FIRSTLOOK_AI_MODEL` in the same file to use another.
- Readings are cached in `backend/.cache/`, so a storm that was read once replays instantly and costs nothing.
- To check it works: `.venv/Scripts/python -m app.ai_check` (from `backend`). It reads the hand-written demo messages and photos and prints what the AI understood next to what the keyword rules made of them.
- A real deployment would need a data agreement before sending residents' messages to an AI service. The demo's messages are invented.

### Google Maps

With a key the app shows Google Maps; without one it falls back to a free OpenStreetMap map in similar colors. Create `frontend/.env.local` (ignored by git):

```
VITE_GOOGLE_MAPS_API_KEY=your-key
```

### The power network on the map

The network is drawn the way it is built: the **substation**, the **lines** and equipment on them, the **distribution transformers**, and the **kWh meters** in the houses of each barangay.

- **Open a barangay pin** and a circle is drawn around the case (2 km by default; 5 km, 10 km or the whole supply path are one tap away). Only the infrastructure inside the circle is shown. Equipment that could be why the houses are dark carries its number on the list, and the side panel lists it in the order to check, with anything further up the line listed separately. *Zoom in to the houses and meters* shows each house, its service drop and its meter: has power, likely no power, or reported no power.
- **Open a place** (a line, switch or transformer) and everything it feeds is picked out.
- **The Meralco grid chip** draws the whole network at once.

This is the exercise's own network: one substation, 20 pieces of equipment, and 24 meters drawn per barangay as a sample of its accounts. Lines follow real roads: `scripts/fetch_network_routes.py` asks a public road router (OSRM, on OpenStreetMap data) for the path of each connection once and saves it in `frontend/public/grid/network-routes.json`, so it works offline. Connections it could not path are drawn straight.

The **Meralco offices** chip is separate: offices as mapped by OpenStreetMap volunteers (`scripts/fetch_meralco_grid.py`), not Meralco's own list. The earlier overlay of OpenStreetMap power lines is no longer drawn.

Data (c) OpenStreetMap contributors, Open Database License. The credit appears on the map while these are shown; keep it there.

### Tests

```bash
cd backend
.venv/Scripts/python -m pytest -q
```

The tests never call an AI service, Claude Code or the embedding model.

### Liwa, the inspection planner

One character stands over the map. Click her for the **inspection plan**: which places to check, in what order, and why. There is nothing to type. The plan is rewritten whenever the picture changes (a new stage, a field result, a repair, a hazard made safe), and each step opens its place on the map.

Liwa is retrieval-augmented and local:

1. **Reference documents.** Put the guidance that should decide the ranking in `backend/reference/` as `.md` or `.txt` files (see the README there). They are split into records of about 900 characters and stored in the vector database. Until there is one, the only reference is FirstLook's built-in rule.
2. **Database.** One SQLite file, `backend/.cache/firstlook.db`: the reference records and the event's own records (every barangay, place and message) in a normal table, with a full-text index (FTS5) and a vector index (the `sqlite-vec` extension) beside it. Only records that changed are rewritten.
3. **Retrieval.** The situation is embedded with a small local model (`BAAI/bge-small-en-v1.5`, 67 MB, downloaded once). Vector search and keyword search each rank the reference records and the two rankings are fused.
4. **Plan.** The retrieved guidance, the situation and the candidate places go to **Claude Opus 5.5 through the Claude Code CLI** (`claude -p`). It returns the order and one reason per place, citing the reference it followed. The code keeps only real places, and anything Claude leaves out keeps the engine's position. This uses the account Claude Code is signed in to on this computer, not an API key: every `ANTHROPIC_*` variable is removed before the command runs. It counts against that account's usage and needs internet.

If Claude Code is missing, signed out or slow, the plan is the engine's own order with the engine's reasons, and says so. `FIRSTLOOK_LIWA=offline` forces that; `FIRSTLOOK_EMBED=hash` skips the embedding model. Every plan is logged in the `plan` table.

**She only advises.** She cannot dispatch a crew, repair anything, give a restoration time or send a message.

Note: the *Check next* list in the side panel is still the engine's order. With no reference documents the plan and the list agree; once documents change the order, the plan shows it and says "the references changed the order".

### Test cases: a typhoon, then interruptions

A test case is a JSON file in `backend/cases/` with stages in the order they happen: the typhoon first, then each interruption. A stage gives what is really damaged (kept hidden in the app) and, optionally, who reports and which hazards; anything left out is simulated. The format is described at the top of `backend/app/cases.py`, and `example-typhoon-then-interruptions.json` is a worked example.

Open the menu (☰) and pick a case to load its first stage; the side panel then shows the stage and a **Next** link. Each stage starts fresh, and Liwa writes a new plan for it. A file with a mistake is listed in the menu with what is wrong.

## Using it

- **Opening: the typhoon.** The app opens on a simulated typhoon: its forecast track, a point every 12 hours and the area the center may pass through, drawn on the map. Press **Start the typhoon** and it crosses Luzon near Metro Manila in about 17 seconds. Nothing about outages is shown until it has passed. The track is generated in code (`frontend/src/typhoon/track.js`) and is different every time; *Replay the typhoon* in the menu shows it again, and *Skip* jumps past it.
- **After the storm.** One sentence on the situation, then three tabs.
- **Check next.** The ranked list. Open a place for one short page: the reasons it ranks where it does, what to look for, how to get there, and three buttons for what was found.
- **Damage found.** Confirmed damage and what each repair would bring back, then what has been repaired or checked clear. Meralco decides the repair order.
- **Messages.** Every message. Filter by safety hazards, vulnerable people or photos. Open one to see it as it was sent and what FirstLook understood.
- **Liwa.** Click her for the inspection plan. Drag her out of the way, or minimise her to the orange bolt button.
- **Menu (☰).** Test cases, and the demo controls: play the demo, replay the typhoon, restart the storm, load a random storm.

## How the ranking works

Places are ranked in strict order:

1. **Safety.** A place with an open hazard (live wire, sparks, fallen pole) goes to the top.
2. **Essential facilities.** Places that feed a hospital, health center, evacuation center or water pumping station that is likely without power. Hospitals count 3, the others 2.
3. **Position in the network.** A main line comes before a switch or pole on it, then a branch line, then a distribution transformer: more depends on what is closer to the substation.
4. **Customers and load.** How many customer accounts the engine predicts are without power behind the place, and the load that implies (a rough 0.5 kW per account).
5. **Reports.** How many people reported from the barangays behind it.
6. **Access.** The shorter drive first.

The order applies only to places where damage is plausible. A place the evidence points away from (under a 5% chance that the damage is there, for example a main line that is clearly live because a barangay behind it has power) or where a visit would tell us almost nothing waits at the bottom.

**Where the order comes from.** Meralco does not publish a formal ranking. Its statements during Ulysses, Carina, Kristine and other storms consistently describe safety first, then hospitals and other vital installations, then main lines and lateral lines, working from the largest outages down. Other utilities publish the same sequence step by step: hazards, critical facilities, the bulk system, main feeders, branch lines, then individual services. The six levels above follow that; the weights and the 5% line are this project's own choices.

The predictions come from the engine: it keeps every combination of up to three simultaneous breaks (1,350 of them) and weighs each against the evidence, meaning how many people reported from each area, what was found on site, and whether power came back after each repair. That is plain probability math, not machine learning. Every assumption is in `backend/app/config.py`.

The Insights page has been taken out of the app. Its comparison (`POST /api/evaluate`) measured the engine's older information-based search, not this rule.

## Layout

| Path | Contents |
| --- | --- |
| `backend/app/config.py` | Every tunable assumption |
| `backend/app/network.py` | Invented equipment, barangays and road graph |
| `backend/app/reports.py` | Invented messages per channel, hand-written demo messages, keyword rules |
| `backend/app/ai.py` | The AI reader: prompts, requests, cache |
| `backend/app/ai_check.py` | One-command check of the AI reader |
| `backend/app/knowledge.py` | Turns the event and the reference documents into records for the database |
| `backend/app/liwa.py` | Liwa: the SQLite database, vector and keyword search, the plan through Claude Code, the offline fallback |
| `backend/app/cases.py` | Reads and checks test cases |
| `backend/cases/` | Test cases: one JSON file each, a typhoon then the interruptions that follow |
| `backend/reference/` | Reference documents that decide how inspections are ranked |
| `backend/app/photos/` | Stand-in photos and their credits |
| `backend/app/engine.py` | Damage scenarios, evidence weighing, information value |
| `backend/app/state.py` | One storm: ranking, results, repair handoff, AI readings |
| `backend/app/simulation.py` | Comparison with other ways of choosing where to look |
| `backend/app/main.py` | FastAPI endpoints under `/api` |
| `frontend/src/panel` | Left panel: first screen, priorities, reports, roads |
| `frontend/src/typhoon` | The opening typhoon: generated track, map drawing, its panel |
| `frontend/src/assistant` | Liwa: 3D character and the inspection plan panel |
| `frontend/src/map` | Map, pins, basemap, and the power network layer (`GridLayer.jsx`, `network.js`) |
| `frontend/public/grid/network-routes.json` | Road paths for the network's lines |
| `frontend/public/grid/meralco-osm.json` | Meralco offices (and the unused line overlay) as mapped on OpenStreetMap |
| `scripts/fetch_network_routes.py`, `scripts/fetch_meralco_grid.py` | Rebuild those two files |

## Limits

- Everything is simulated. Results on the Insights page show relative behaviour, not field performance.
- Liwa's plan is written by Claude from the retrieved guidance and can still misapply it. The guidance and the reason for each step are shown so a person can check.
- A written plan needs internet and a signed-in Claude Code and takes roughly 5 to 15 seconds; without them the engine's own order is shown. It counts against that account's usage limits.
- The AI reader can misread a message or a photo. Its reading is always shown next to the original, and a person decides what to do.
- FirstLook can only see areas where someone has reported. An outage nobody reports stays invisible to it.
- The network on the map is invented for the exercise. Its lines follow real roads, but they are not Meralco's lines, and the houses and meters are a drawing aid placed around each barangay's pin, not surveyed buildings.
- The model covers up to three simultaneous breaks on a 20-item network. A real feeder map is far larger.
- Routes follow a simplified road graph, not turn-by-turn streets.
- One storm is held in memory; restarting the backend resets it.
