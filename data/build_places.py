"""One-time build: fetch Durham-area providers from Google Places (New) Text Search into
data/providers_places.json. Chat, tests and evals only read that file; they never call Google.

Dry run by default: it prints the plan and the most calls it could spend. Add --run to spend them.

  python data/build_places.py                    # plan only, 0 calls
  python data/build_places.py --run              # 10 trades x 2 pages = at most 20 calls
  python data/build_places.py --run --trades plumbing hvac --zips 27701 27705 27707 27713 --pages 3

Each request (one page of up to 20 results) is one billable call. Calls are counted in
data/.places_usage.json and capped by NLA_PLACES_MONTHLY_CAP (see nla/places_budget.py).
Rerunning spends the calls again; results merge into the existing file, so a run for a few
trades refreshes those trades and keeps the rest.
"""
import argparse
import datetime
import json
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from nla import places_budget  # noqa: E402
from nla.taxonomy import TRADES  # noqa: E402

OUT = ROOT / "data" / "providers_places.json"
URL = "https://places.googleapis.com/v1/places:searchText"
FIELDS = ("places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.rating,"
          "places.userRatingCount,places.websiteUri,places.googleMapsUri,places.businessStatus,places.location,"
          "places.regularOpeningHours,nextPageToken")
DURHAM = {"circle": {"center": {"latitude": 35.994, "longitude": -78.8986}, "radius": 25000.0}}

# Text queries used for Google Places per trade
PLACES_QUERY = {
    "plumbing": "plumber", "water_damage_restoration": "water damage restoration",
    "waterproofing_foundation": "basement waterproofing crawl space", "roofing": "roofing contractor",
    "gutters": "gutter repair", "hvac": "HVAC repair", "electrical": "electrician",
    "appliance_repair": "appliance repair", "handyman": "handyman", "pest_control": "pest control",
}


def fetch(key: str, query: str, max_pages: int) -> list[dict]:
    import httpx  # only needed for real calls, so a dry run works without it

    places, token = [], None
    for page in range(max_pages):
        body = {"textQuery": query, "pageSize": 20, "locationBias": DURHAM}
        if token:
            body["pageToken"] = token
            time.sleep(2)  # give the page token time to become valid instead of wasting a call
        n = places_budget.spend()
        r = httpx.post(URL, headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": FIELDS}, json=body, timeout=20)
        r.raise_for_status()
        data = r.json()
        places += data.get("places", [])
        print(f"  {query!r} page {page + 1}: {len(data.get('places', []))} results  (call {n}/{places_budget.cap()} this month)")
        token = data.get("nextPageToken")
        if not token:
            break
    return places


def open_24_7(hours: dict | None) -> bool | None:
    """True if Google lists the place as always open, False if it lists other hours, None if no hours.

    Google marks always-open places with a single period that opens Sunday 00:00 and never closes.
    """
    if not hours:
        return None
    periods = hours.get("periods") or []
    if len(periods) == 1 and "close" not in periods[0]:
        o = periods[0].get("open", {})
        return o.get("day") == 0 and o.get("hour", 0) == 0 and o.get("minute", 0) == 0
    days = hours.get("weekdayDescriptions") or []
    return len(days) == 7 and all("open 24 hours" in d.lower() for d in days)


def to_provider(pl: dict, trade: str) -> dict:
    addr = pl.get("formattedAddress", "")
    hours = pl.get("regularOpeningHours")
    return dict(id="gp-" + pl["id"].lower(), place_id=pl["id"], name=pl["displayName"]["text"], trades=[trade],
                city=addr.split(",")[-3].strip() if addr.count(",") >= 2 else "Durham",
                phone=pl["nationalPhoneNumber"], google_rating=pl.get("rating"), google_reviews=pl.get("userRatingCount"),
                address=addr, lat=pl.get("location", {}).get("latitude"), lng=pl.get("location", {}).get("longitude"),
                website=pl.get("websiteUri"), emergency_24_7=open_24_7(hours),
                hours=(hours or {}).get("weekdayDescriptions"), source_url=pl.get("googleMapsUri"),
                notes="", maps_url=pl.get("googleMapsUri"), retrieved=datetime.date.today().isoformat(),
                data_source="google_places")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="store_true", help="actually call Google (default: dry run, 0 calls)")
    ap.add_argument("--trades", nargs="+", choices=list(PLACES_QUERY), help="default: all trades")
    ap.add_argument("--zips", nargs="+", default=[], help="one query per trade per ZIP (default: one 'in Durham, NC' query per trade)")
    ap.add_argument("--pages", type=int, default=2, choices=[1, 2, 3], help="pages per query, 20 results each (default 2)")
    ap.add_argument("--fresh", action="store_true", help="replace the existing file instead of merging into it")
    args = ap.parse_args()

    trades = args.trades or [t for t in TRADES if t in PLACES_QUERY]
    areas = [f"near {z}, NC" for z in args.zips] or ["in Durham, NC"]
    queries = [(t, f"{PLACES_QUERY[t]} {a}") for t in trades for a in areas]
    max_calls = len(queries) * args.pages
    print(f"Plan: {len(queries)} queries x up to {args.pages} pages = at most {max_calls} calls")
    print(f"Used this month: {places_budget.used()}/{places_budget.cap()}  (remaining {places_budget.remaining()})")
    if max_calls > places_budget.remaining():
        print("Aborting: this plan could exceed the monthly cap. Use fewer trades, ZIPs or pages.")
        return 1
    if not args.run:
        print(f"Dry run: no calls made. Add --run to spend up to {max_calls} calls.")
        return 0

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not key:
        print("GOOGLE_MAPS_API_KEY is not set in .env")
        return 1

    by_id = {} if args.fresh or not OUT.exists() else {p["place_id"]: p for p in json.loads(OUT.read_text())}
    seen = set()  # places already refreshed in this run
    for trade, query in queries:
        for pl in fetch(key, query, args.pages):
            if pl.get("businessStatus") not in (None, "OPERATIONAL") or not pl.get("nationalPhoneNumber"):
                continue
            if ", NC " not in pl.get("formattedAddress", ""):
                continue
            old = by_id.get(pl["id"])
            if pl["id"] in seen:
                if trade not in old["trades"]:
                    old["trades"].append(trade)
                continue
            fresh = to_provider(pl, trade)
            if old:  # refresh fields, keep trades an earlier run found
                fresh["trades"] += [t for t in old["trades"] if t != trade]
            by_id[pl["id"]] = fresh
            seen.add(pl["id"])
        OUT.write_text(json.dumps(list(by_id.values()), indent=1))  # save after each query so a crash keeps paid results

    per_trade = {t: sum(t in p["trades"] for p in by_id.values()) for t in trades}
    print(f"{len(by_id)} providers -> {OUT}")
    print("Per trade:", per_trade)
    print(f"Calls used this month: {places_budget.used()}/{places_budget.cap()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
