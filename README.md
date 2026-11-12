# FirstLook

*Know where to look next.*

After a typhoon, a utility has many power interruptions at once and too few crews. FirstLook shows each interruption on a map, draws a zone around it with the infrastructure inside, and has **Liwa**, a retrieval-augmented planner, rank what to check first, with the reason and the crew's ETA.

FirstLook recommends. People decide, and Meralco's crews do the work.

All data is simulated: an invented power network laid over real places in Greater Manila, and 20 hand-made interruption cases (13 supplied by the team, 7 added for this build). Nothing here is Meralco's own data.

## What you see

1. **The typhoon.** The app opens on a simulated typhoon: its forecast track, a point every 12 hours and the area the center may pass through. Press **Start the typhoon** and it crosses Luzon near Metro Manila in about 17 seconds. No interruption is shown until it has passed. The track is generated in code (`frontend/src/typhoon/track.js`) and is different every time. *Skip* jumps past it; *Replay the typhoon* is in the menu.
2. **The power interruptions.** Once the storm has passed, every interruption appears as a "!" pin on the map and as a row in the side panel, grouped by the highest customer tier still waiting: Critical customers, Community services, Residential. The number beside a pin is how many **outage reports** are linked to it (reports, not people or households).
3. **One interruption.** Open a pin or a row. Everything outside its **2 km zone** is blurred and the other pins are hidden. The side panel starts with three numbers: **customers without power**, **reports from customers**, and how many things there are to check. Two pills switch between **What to check, in order** and **Customer reports**. The ranking is shown the same way on the map and in the side panel:
   - **1, in blue, is what to check first.** It carries the crew's ETA from the nearest Meralco office and Liwa's reason.
   - **2, 3, ... come next**, in order, under a heading for each customer tier, each with a short reason. The things ranked are equipment: poles, transformers and line sections. On the map each marker carries the equipment's own mark beside its number; the side panel shows the same mark beside the name.
   - **On hold** carries a pause mark and the reason (not safe for the crew yet, or flooded and waiting for clearance). When everything is on hold, the answer is *Hold the crew*.
   - **The crew's road route** from the office to number 1 is drawn in blue. Click another number, on the map or in the panel, to see the route to it instead. Only one route is drawn at a time.
   - **Resolve** on number 1 is pressed once the crew has checked it, whether they fixed something or found nothing to fix. It marks it done: it moves to *Done*, number 2 becomes the new number 1, the route moves with it, and the count of customers without power drops. *Undo* puts it back. This walks down the order Liwa already gave; it does not ask her again.
   - **When conditions change, Liwa ranks again.** Anything on hold has a button for what has changed (*Now safe for the crew*, *Flood cleared*). Pressing one records the change and Liwa ranks the interruption as it now stands, in 6 to 10 seconds. A panel then says what changed and what moved (for example: Pole at Flooded hospital, on hold to number 1), with her new reason. *Put this interruption back as it was* undoes every change.
   - **Customer reports** (the second pill) lists the reports by channel (Meralco App, SMS, Hotline 16211, Facebook, X), with what Liwa took from them on top. Open a channel to list its reports, hazards and people who depend on power first; open a report to see it the way that channel shows it (a Facebook post or comment, an X post, a text message, a hotline call ticket, a Meralco App report) and how it counts.
   - *How Liwa decided*, folded at the bottom, has the records she used, the comparison with the test file's expected answer, and *Ask Liwa again*.
4. **Liwa.** She ranks an interruption live, at the moment it is opened (about 6 to 10 seconds), and again whenever its conditions change. An answer is kept for as long as the server runs, so the same situation is never ranked twice. Click the character for the hierarchy she ranks by. *Test me on all 20* ranks every interruption afresh and reports how many answers match. There is nothing to type.

### History and reports

The menu has two more entries under *Replay the typhoon*. Both open the **Typhoon records** page.

- **History.** Past typhoons on a time line, newest first, with the one in progress at the top. For each: what happened, four figures (customers affected, interruptions, time to restore 90%, time until everyone was back), and the **restoration curve**: the share of customers with power back, by hours after the all clear. *More about ...* adds the causes of damage, who was affected by customer tier, the customer reports, the holds, and what was changed afterwards.
- **Reports.** One PDF per typhoon, exported as a file: a **restoration report** for each past typhoon and a **situation report** for the one in progress.

A restoration report (`backend/app/report_pdf.py`) has what such a report needs in practice: document number, status, period and area covered; the event; impact at a glance, including customer-minutes interrupted; the restoration curve and its milestones; impact by customer tier; causes of damage and the work done; customer reports by channel; safety and holds; how the work was prioritised and where a dispatcher changed it; crews; the full interruption log with times; open items and follow-up actions; definitions and limits of the data; and a sign-off block (prepared, reviewed, approved).

**The past typhoons are invented** (`backend/app/history.py`). Their names are not PAGASA names. Only each event's headline is written by hand; its interruption log is generated from a seed, and every figure on screen and in the PDF is counted from that log, so the numbers add up. The page and every PDF page say that the data is simulated.

### The road route

The route is real roads, not a straight line. `frontend/src/map/route.js` asks, in order:

1. **Google Maps directions**, with the same key as the map. This needs the **Routes API** enabled for that key's Google Cloud project (APIs and Services, Library, "Routes API", Enable; if the key is restricted to certain APIs, add Routes API to the list). The older Directions API also works if it is already enabled.
2. The public **OpenStreetMap router** (OSRM), when Google refuses or there is no key.
3. A straight dotted line, when neither answers.

The side panel says which one drew the line. Only the path is used: the ETA shown is always the one in the case.

## The cases and the hierarchy

Three files drive the ranking. Replace them to run other cases or another policy.

- **`backend/cases/meralco_demo.sqlite`**: the test cases. The file is only ever read: it is copied into memory at start-up. `scenarios` holds each case and its expected answer; `pole_jobs` holds the poles: facility, customer tier, safety, flood status, customers restored, report count, driving time, distance, work type. The views `ranked_jobs` and `dispatch_results` are the policy written as plain SQL.
- **`backend/reference/rag_documents.jsonl`**: the team's reference records for the vector database: 7 policy records and 13 worked examples. `.md` and `.txt` files in that folder are loaded too.
- **`backend/reference/customer_reports.jsonl`**: two more policy records, a **draft written for this build**, on how customer reports are weighed (see *Customer reports* below). Edit or delete it to change that.

**More to rank.** The supplied cases have one to four poles each. `backend/cases/extra_poles.json` adds six to nine more jobs to each (poles, transformers and line sections serving a public market, schools, a barangay hall, residential areas; some unsafe, flooded or already done), so every interruption has ten or eleven. They are added to the in-memory copy only, must pass the table's own checks, and are chosen so that **no expected answer changes**: a test checks that the database's own rule still gives every expected answer. Delete that file, or set `FIRSTLOOK_EXTRA_POLES=off`, to run the cases exactly as supplied.

**Seven more cases.** The same file adds case-14 to case-20, written for this build to cover situations the supplied thirteen do not: two hospitals where one is only partly cleared of flood; every Critical job on flood hold; a restoration against an inspection; flood and unsafe roads holding everything; only residential jobs left; a tie that driving time decides between community services; and a tie that reports decide between two Critical jobs. Each has its own expected answer, which a test requires to be the answer the database's own rule gives. They are drawn in places that had no interruption yet: Sampaloc and Tondo in Manila, Makati, Pasig, Marikina, Taguig and Caloocan. They have no worked example in the reference records.

**Plain titles.** The scenario names in the test file ("Safety first", "Critical before residential") name the rule being tested, not what is happening. The same file gives every case a title that says what is out and what makes it hard ("Hospital and evacuation center out: the hospital pole is not safe to reach"). The scenario name is still shown under *How Liwa decided*.

The hierarchy, in short: **safety** first, then **flood clearance**, then the **highest customer tier**, the **most customers restored**, the **most reports**, and the **shortest driving ETA**.

Each case's expected answer is shown beside Liwa's and is never sent to her. **A case never sees its own worked example**, since it contains the answer (`FIRSTLOOK_USE_OWN_EXAMPLE=1` allows it). In the last full run, with the extra equipment and the customer reports in front of her, all 20 first choices matched, and her whole order was the same as the database's own rule in all 20. Once an interruption's conditions have been changed on screen, the scenario's expected answer no longer applies: her answer is then compared with what the written rule gives for the situation as it stands.

### Customer reports

The test file gives every job a number of linked outage reports. `backend/app/case_reports.py` writes that many messages for it, so the number has something behind it that a person, and Liwa, can read. They are **invented and repeatable**: the same case always gets the same messages, each from a different invented person, spread over the Meralco App, SMS, the hotline, Facebook and X. What they say follows the job's own facts: a job marked unsafe gets several people describing the same hazard, a flooded one gets flood reports, the rest are ordinary no-power reports, some mentioning someone who depends on power (oxygen, dialysis, a nebulizer). A few posts carry a photo; these are stand-ins from Wikimedia Commons (`backend/app/photos/CREDITS.md`), not pictures of these places.

**Reports are weighed lightly.** Liwa reads every report, under the two draft policy records in `customer_reports.jsonl`:

- Reports are evidence, not orders. They never override safety, flood clearance, the customer tier or the customers restored. Their number counts only where the hierarchy already puts it: as the tie-break after customers restored.
- **One report does not move a job.** To show this, a few busy residential jobs carry exactly one alarming report that nobody else confirms (someone thinks they saw a spark). Liwa notes it for the crew to confirm on arrival, and the order stays as it was.
- What reports say is read for the crew: hazards to confirm, and people who depend on power. Three or more separate people describing the same hazard at a job marked safe is a reason to re-check its safety status, not to re-rank it.

These two records are this project's own draft, not Meralco's or the team's supplied policy. They are worth a review by whoever owns the hierarchy.

### What is drawn and what is given

The case file has no coordinates. Each case is drawn in a real barangay, its poles are placed inside the zone, and the crew is drawn coming from the nearest Meralco office on the map. That picture is a drawing aid. The facts, including the **ETA and distance of every pole, are the case file's own** and are not recomputed from the map or from the drawn route.

## How Liwa works

Liwa is retrieval-augmented and local:

1. **Database.** One SQLite file, `backend/.cache/firstlook.db`: the reference records, and records of the simulated service area, in a normal table, with a full-text index (FTS5) and a vector index (the `sqlite-vec` extension) beside it. Only records that changed are rewritten.
2. **Retrieval.** The case is embedded with a small local model (`BAAI/bge-small-en-v1.5`, 67 MB, downloaded once). Vector search and keyword search each rank the records and the two rankings are fused. Every policy record is passed on, the most relevant first, together with the three worked examples closest to the case.
3. **Decision.** The retrieved records, the case's jobs and the customer reports linked to each job go to **Claude Opus 5.5 through the Claude Code CLI** (`claude -p`). It returns the action, the order with a short reason for each place, what it took from the reports, and the records it used. The code keeps only equipment that exists in the case. A reply that cannot be read is asked for once more.

This uses the account Claude Code is signed in to on this computer, **not an API key**: every `ANTHROPIC_*` variable is removed before the command runs. It counts against that account's usage, needs internet, and takes about 5 seconds per case.

If Claude Code is missing, signed out or slow, the answer is the one from the case file's SQL views, and the screen says so. `FIRSTLOOK_LIWA=offline` forces that; `FIRSTLOOK_EMBED=hash` skips the embedding model. Every decision is logged in the `plan` table.

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

Open http://localhost:5173. For Liwa's written answers, Claude Code must be installed and signed in (`claude auth status`).

### Google Maps

With a key the app shows Google Maps; without one it falls back to a free OpenStreetMap map in similar colors. Create `frontend/.env.local` (ignored by git):

```
VITE_GOOGLE_MAPS_API_KEY=your-key
```

### Tests

```bash
cd backend
.venv/Scripts/python -m pytest -q
```

The tests never call an AI service, Claude Code or the embedding model.

## The map layers

- **Interruptions.** The pins. On by default.
- **Landmarks.** Place labels on the basemap.
- **Meralco grid.** The whole simulated network at once: one substation and 44 pieces of equipment (lines, switches, poles, fuse cutouts, distribution transformers). Lines follow real roads: `scripts/fetch_network_routes.py` asked a public road router (OSRM, on OpenStreetMap data) for each path once and saved it in `frontend/public/grid/network-routes.json`, so it works offline. Zoomed in, sample houses and kWh meters are drawn per barangay. While an interruption is open the network is drawn inside its zone only when this chip is on, so that by default nothing but the ranked equipment and the crew's route is in the circle.
- **Meralco offices.** Offices as mapped by OpenStreetMap volunteers (`scripts/fetch_meralco_grid.py`), not Meralco's own list. The crew in each case is drawn from the nearest of these.

Data (c) OpenStreetMap contributors, Open Database License. The credit appears on the map while these are shown; keep it there.

## Layout

| Path | Contents |
| --- | --- |
| `backend/cases/meralco_demo.sqlite` | The 13 supplied test cases, expected answers, and the policy as SQL views |
| `backend/cases/extra_poles.json` | Added in memory: extra equipment for each case, seven more cases, and a plain title for every case |
| `backend/reference/rag_documents.jsonl` | The team's reference records for the vector database: 7 policies, 13 worked examples |
| `backend/reference/customer_reports.jsonl` | Draft policy records on how customer reports are weighed |
| `backend/app/cases.py` | Reads the test cases |
| `backend/app/case_reports.py` | Invented customer reports for each job, and the barangay each case is drawn in |
| `backend/app/knowledge.py` | Turns the reference documents into records for the database |
| `backend/app/liwa.py` | Liwa: the SQLite database, vector and keyword search, the decision through Claude Code, the fallback |
| `backend/app/history.py` | The invented past typhoons and their interruption logs; the record of the typhoon in progress |
| `backend/app/report_pdf.py` | The PDF reports (restoration report, situation report) |
| `backend/app/main.py` | FastAPI endpoints under `/api` |
| `backend/app/network.py`, `state.py`, `engine.py`, `reports.py`, `ai.py` | The simulated service area. The app now uses it for the barangays and the network on the map; its earlier screens (message reading, the engine's own ranking) are no longer shown |
| `frontend/src/App.jsx` | The app: typhoon, then the interruptions |
| `frontend/src/panel` | Side panel: the list of interruptions and the page for one |
| `frontend/src/map` | Map, interruption pins and ranked poles (`CaseLayer.jsx`, `cases.js`), the crew's road route (`RouteLayer.jsx`, `route.js`), the blur outside the zone (`ZoneFocus.jsx`), the network layer (`GridLayer.jsx`, `network.js`) |
| `frontend/src/typhoon` | The opening typhoon: generated track, map drawing, its panel |
| `frontend/src/records` | The Typhoon records page: History and Reports |
| `frontend/src/assistant` | Liwa: the 3D character and her panel |
| `frontend/public/grid` | Road paths for the network's lines; Meralco offices from OpenStreetMap |
| `scripts/` | Rebuild those two files |

## Limits

- Everything is simulated. The 20 cases are test scenarios, not field records.
- The past typhoons and their reports are generated. They show what a record and a report would look like, not how FirstLook performed in a real storm. A report covers one sector and gives no system-wide reliability figures (SAIFI, SAIDI).
- The situation report is a snapshot from the server. Equipment marked resolved on screen is not in it.
- Liwa's answer is written by Claude from the retrieved records and can still misapply them. The records and her reason are shown so a person can check, and the case file's own answer is shown beside hers.
- The 20 of 20 result is on these 20 cases. The 13 supplied ones had their own worked example held out; the 7 added ones were written by the same hand that wired up the ranking, with expected answers taken from the written rule, so they show consistency rather than independent proof. None of it says anything yet about cases the policy records do not cover.
- A change of conditions is recorded in the server's working copy and is lost when the server restarts. When a site with no way in is made safe, its driving time is not in the case, so a fixed stand-in (5 to 17 minutes) is used.
- ETAs are given in the case file. FirstLook does not compute travel time: the road route is drawn for orientation, between an office on a volunteer-made map and a pole position that is itself a drawing aid.
- Resolve is kept on screen only. It is not saved, and it does not make Liwa rank again.
- The customer reports are invented to fit each job's facts, so they agree with the case by construction. Real reports would be messier: wrong places, duplicates, rumours. How Liwa copes with those has not been tested.
- "Customers without power" is the sum of the customers each unfinished job would restore, as given in the cases. It is a count of customer accounts, not of people.
- The network on the map is invented. Its lines follow real roads, but they are not Meralco's lines.
- A written answer needs internet and a signed-in Claude Code, and counts against that account's usage limits.
