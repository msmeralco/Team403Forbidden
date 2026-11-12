# FirstLook – Business case (plain language)

> Team notes for the pitch and Q&A. Figures come from public news reports (sources at the end).
> Check anything marked **[ask mentor]** with the Meralco mentors before the demo.

## The one-liner

**Meralco's ADMS acts like autopilot for the main lines. FirstLook guides crews through everything the autopilot can't see: the poles, transformers and barangay lines where typhoon damage actually happens, and where the only sensors are the people calling, texting and posting.**

## What Meralco already has

| What exists | What it does |
|---|---|
| **ADMS with PLISR** (Pinpoint Location, Isolation and Service Restoration) | Automatically locates faults, isolates the damaged section and restores the healthy parts of the line |
| **Advanced Network Automation** (rolling out) | Remote-controlled switches that reroute power around damage; looped high-voltage circuits |
| **Smart meters (AMI)** | About 165,000–196,000 installed out of ~8.2 million customers (~2%). Target: 11–12 million within a decade |
| **Customer channels** | Hotline 16211 (24/7), SMS 0920-971-6211 / 0917-551-6211, Facebook page and Messenger, X @meralco, Meralco app (outage map, report, track, restoration estimate), web form |
| **Stronger infrastructure** | Concrete/steel poles rated for 270 km/h winds, fiberglass crossarms, elevated substations |
| **Restoration priorities** | Main lines → laterals → critical sites (hospitals, government). DOE also directs priority for hospitals, evacuation centers, telecom and water |

## Where it falls short, and what FirstLook covers

1. **Automation covers the main lines, not the smaller ones.** After Super Typhoon Uwan, Meralco said the damage was *"predominantly… distribution poles and lines."* That damage is on poles, transformers and barangay lines, where nothing is automated. With smart meters at ~2% of customers, **for the other 98% the only signal is a person reporting.**
   → FirstLook works where the automation can't see.
2. **The community's voice arrives scattered across six or more channels.** One dead transformer can produce 40 Facebook comments, 15 texts, 10 calls and 5 app reports. Public posts and comments are unstructured text, hard to turn into map data at scale. **[ask mentor: are FB/X reports merged with hotline/app tickets today?]**
   → FirstLook groups every report from every channel into one pin per barangay, and counts a person who reported three ways only once.
3. **Knowing a line is dead isn't knowing what broke.** Someone still has to go look: fallen pole, tree on the line, blown transformer? Each needs a different crew and different materials. Choosing which site to inspect first is left to judgment. **[ask mentor: how is patrol order decided today?]**
   → FirstLook ranks which visit to make first, says what the crew should check, and estimates repair needs.
4. **Flooding and closed roads slow restoration again and again** (Carina 2024, Uwan 2025).
   → FirstLook accounts for road closures in its ranking and routes.
5. **The scale makes every hour count.** Ulysses (2020) ~4 million customers out; Carina (2024) 662,000; Kristine (2024) ~389,000–535,000; Uwan (2025) 400,000+. **With 400,000 customers out, each hour saved returns 400,000 customer-hours of electricity.**

## How FirstLook decides what comes first (non-technical)

> **Priority = How urgent × How useful the visit is ÷ How long it takes**
> - **Urgent** = people reporting + homes likely without power + critical facilities (hospitals, water pumps, evacuation centers)
> - **Useful** = does one visit explain several outages at once
> - **Safety hazards always go first** (live wire down, sparks or fire, fallen pole), detected automatically from the words in the reports, in Filipino and English.

**"Won't the loudest barangay always win?"** No:
- **Diminishing returns.** Going from 1 to 20 people reporting matters a lot; 200 to 220 barely matters.
- **One person, one voice.** Someone who posts, texts and calls counts once.
- **Homes, not just posts.** Households likely without power are weighed separately from how many people complained.
- **Quiet areas get flagged.** If an area very likely lost power but few people reported (dead phones, evacuated, elderly residents), FirstLook marks it as a *quiet area* so it isn't ignored.
- **Stray reports barely count.** One "kami lang walang kuryente" (just our house) from an area that still has power doesn't move the ranking.

## Benefits for customers and communities

- **Every report counts.** A Facebook comment carries as much weight as a hotline call, so people don't have to keep calling to be noticed.
- **Safety first.** Live wires, sparks and fallen poles are flagged and go to the top.
- **Quiet areas aren't left behind.** Areas with fewer people online still get attention.
- **Most impact first.** Hospitals, evacuation centers, water pumps and areas with many households come first.
- **Faster restoration overall.** Fewer wasted trips means crews spend more time fixing and less time searching.

## Benefits for Meralco

- **One picture for everyone.** Dispatch, field crews and management see the same live map.
- **Fewer wasted trips.** Less fuel, overtime and crew time spent searching.
- **Defensible decisions.** Every ranking explains itself, which helps when LGUs ask "why not us first?"
- **Earlier resource requests.** Repair needs (poles, transformers, crews) are estimated as evidence comes in.
- **Works with existing systems.** It sits beside ADMS, the hotline and the app instead of replacing them.

## Careful wording for the pitch

- Present FirstLook as **working alongside ADMS, not replacing it.**
- **Privacy:** it reads only public posts and comments that mention Meralco, hides names and numbers on the dashboard, and follows the Data Privacy Act (RA 10173).
- **Prototype honesty:** network and reports are synthetic (invented); place names are real.

## Sources

- Power Philippines – Meralco fortifies grid with smart automation (ADMS/PLISR, smart meters): https://powerphilippines.com/?p=23325
- Tribune – Meralco ensures safe and swift power restoration after Uwan: https://tribune.net.ph/2025/11/10/meralco-ensures-safe-and-swift-power-restoration-after-uwan
- GMA – 197k Meralco users still without power after Uwan: https://www.gmanetwork.com/news/topstories/nation/965529/197k-meralco-users-still-without-power-after-uwan/story
- Tribune – Meralco struggles to restore power in flooded areas (Carina): https://tribune.net.ph/2024/07/26/meralco-struggles-to-restore-power-in-flooded-areas
- ABS-CBN – Almost 400k Meralco subscribers affected by Kristine: https://www.abs-cbn.com/business/2024/10/24/almost-400k-meralco-subscribers-see-service-interruptions-due-to-kristine-1304
- Philstar – Nearly 4M households out of power due to Ulysses: https://philstar.com/business/2020/11/12/2056415/nearly-4-m-meralco-households-out-power-due-ulysses
- PTV – Meralco restoring main lines, laterals and critical installations: https://ptvnews.ph/?p=169152
- DOE – Energy sector rallies to restore power after Kristine: https://legacy.doe.gov.ph/node/27160
- Tribune – Meralco seeks go-ahead for full smart meter rollout: https://tribune.net.ph/2025/05/28/meralco-seeks-go-ahead-for-full-smart-meter-rollout
- Philstar Life – Guide to reporting a brownout: https://philstarlife.com/news-and-views/828337-guide-report-brownout-in-your-area
- TechPilipinas – Meralco hotline and SMS numbers: https://techpilipinas.com/meralco-hotline/
