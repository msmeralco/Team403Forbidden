"""Check the AI reader against the hand-written demo messages and photos.

Run from the backend folder:  .venv/Scripts/python -m app.ai_check
It makes a handful of real requests (a few cents) unless the readings are already cached.
"""
import sys
import time

from . import ai
from .reports import DEMO_EXTRAS, classify


def main() -> int:
    status = ai.availability()
    if status != "ready":
        print("The AI reader is off." if status == "off" else
              "No API key found. Paste one after ANTHROPIC_API_KEY= in backend/.env and run this again.")
        return 1
    print(f"Model: {ai.MODEL}\n")
    started = time.time()
    items = [{"id": str(n), "channel": e["source"], "text": e["text"]} for n, e in enumerate(DEMO_EXTRAS)]
    try:
        readings = ai.read_messages(items)
    except ai.AIError as e:
        print(f"Could not read the messages: {e}")
        return 1
    caught = 0
    for n, e in enumerate(DEMO_EXTRAS):
        keywords, r = classify(e["text"]), readings.get(str(n))
        if not r:
            print(f"[{n}] no reading returned\n")
            continue
        flags = [f"hazard={r['hazard']}" if r["hazard"] != "none" else "", f"clue={r['clue']}" if r["clue"] != "none" else "",
                 "vulnerable" if r["vulnerable"] else "", "single house" if r["single_house"] else ""]
        new = (r["hazard"] != "none" and keywords["category"] != "hazard") or \
              (r["clue"] != "none" and keywords["category"] not in ("hazard", "clue")) or \
              (r["vulnerable"] and not keywords["vulnerable"])
        caught += bool(new)
        print(f"[{n}] {e['text']}")
        print(f"     keyword rules: {keywords['tag'] or keywords['category']}")
        print(f"     AI reader:     {r['what']}")
        print(f"                    {', '.join(f for f in flags if f) or 'no flags'} | place={r['place']} (really {e['area']})"
              f"{'   <- keywords missed this' if new else ''}")
        if e.get("photo"):
            try:
                image, media = ai.photo_bytes(e["photo"])
                seen = ai.read_photo(image, media, e["text"])
                print(f"     photo {e['photo']}: {seen['damage_label']}, hazard={seen['hazard']}, "
                      f"{seen['confidence']} confidence. {seen['sees']}")
                if seen["bring"]:
                    print(f"                    crew may need: {seen['bring']}")
            except ai.AIError as err:
                print(f"     photo {e['photo']}: could not be read ({err})")
        print()
    placed = sum(1 for n, e in enumerate(DEMO_EXTRAS) if readings.get(str(n), {}).get("place") == e["area"])
    print(f"The AI caught something the keyword rules missed in {caught} of {len(DEMO_EXTRAS)} messages, "
          f"and placed {placed} of {len(DEMO_EXTRAS)} in the right barangay. Took {time.time() - started:.0f}s.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
