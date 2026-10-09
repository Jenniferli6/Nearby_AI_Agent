"""Provider directory: real Durham-area businesses, read from local files only (never calls an API).

  * data/providers_durham.json - seed researched from public listings.
  * data/providers_places.json - optional, written once by data/build_places.py from Google Places.

Entity matching: rows are the same business if the phone matches, or the normalized name matches and
the location agrees (same house number + ZIP, or same city when one side has no street address).
Those become one row (see _merge). Same brand at a different address (a franchise branch) stays a
separate row, but search shows at most one row per brand.

The data source is never a ranking signal. emergency_24_7 is True / False / None (unknown); unknown
gets no boost and no penalty.

search() is the v0 baseline, kept so the ranking eval can measure against it: trade fit, then
quality (rating weighted by review volume), proximity (Durham-based > neighbouring town), and 24/7
availability for emergencies. Live chat ranks with nla/ranking.py. Nobody pays for rank.
"""
from __future__ import annotations

import json
import math
import pathlib
import re
from dataclasses import dataclass

from .taxonomy import TRADES

DATA = pathlib.Path(__file__).resolve().parent.parent / "data" / "providers_durham.json"
PLACES_DATA = DATA.with_name("providers_places.json")
PROFILES = DATA.with_name("provider_profiles.json")  # from each provider's website, by data/build_profiles.py

# Fields where the later file (Google) is fresher than the hand-researched seed
FRESHER = ("google_rating", "google_reviews", "lat", "lng", "place_id", "maps_url", "address", "hours")


NAME_STOP = {"the", "llc", "inc", "co", "company", "corp", "corporation", "ltd", "pllc"}


def brand_key(name: str) -> str:
    """'Roto-Rooter Plumbing & Water Cleanup (Durham)' -> 'rotorooter plumbing and water cleanup'."""
    n = re.sub(r"\([^)]*\)", " ", name.lower().replace("&", " and "))
    n = re.sub(r"[^a-z0-9 ]", "", n.replace("-", ""))
    return " ".join(w for w in n.split() if w not in NAME_STOP)


def _phone_key(p: dict) -> str:
    return re.sub(r"\D", "", p.get("phone") or "")[-10:]


def _street_key(addr: str | None) -> tuple[str, str] | None:
    """(house number, ZIP), which survives 'Road' vs 'Rd' and 'Hwy 70 E' vs 'US-70'."""
    num = re.match(r"\s*(\d+)\b", addr or "")
    zips = re.findall(r"\b(\d{5})\b", addr or "")
    return (num.group(1), zips[-1]) if num and zips else None


def _same_place(a: dict, b: dict) -> bool:
    ka, kb = _street_key(a.get("address")), _street_key(b.get("address"))
    if ka and kb:
        return ka == kb
    city = lambda p: (p.get("city") or "").lower().split(" (")[0].strip()  # "Raleigh (serves Durham)" -> "raleigh"
    return bool(city(a)) and city(a) == city(b)


def _merge(base: dict, other: dict) -> None:
    """Fold a later row for the same business into the row already kept.

    The listing-specific fields (rating, reviews, location, Maps link, hours) move together from one
    listing: from Google when the kept row is the hand-researched seed, else from whichever listing has
    more reviews. The kept row keeps its id, phone, primary trade, notes and source link; the other phone
    is kept in alt_phones. Either source saying 24/7 counts, since the seed's True came from the company's
    own page.
    """
    if not base.get("place_id") or (other.get("google_reviews") or 0) > (base.get("google_reviews") or 0):
        for k in FRESHER:
            if other.get(k) is not None:
                base[k] = other[k]
    if _phone_key(other) != _phone_key(base) and other.get("phone"):
        base.setdefault("alt_phones", []).append(other["phone"])
    if not base.get("website"):
        base["website"] = other.get("website")
    base["trades"] += [t for t in other["trades"] if t not in base["trades"]]
    flags = (base.get("emergency_24_7"), other.get("emergency_24_7"))
    base["emergency_24_7"] = True if True in flags else False if False in flags else None
    if other.get("data_source") and other["data_source"] not in base.get("data_source", ""):
        base["data_source"] = f"{base.get('data_source')}+{other['data_source']}"


@dataclass
class Match:
    provider: dict
    score: float
    reasons: list[str]


class ProviderDirectory:
    def __init__(self, paths: tuple[pathlib.Path, ...] = (DATA, PLACES_DATA)):
        self.providers: list[dict] = []
        by_phone: dict[str, dict] = {}
        by_brand: dict[str, list[dict]] = {}
        for path in paths:
            if not path.exists():
                continue
            for p in json.loads(path.read_text()):
                digits, brand = _phone_key(p), brand_key(p["name"])
                same = by_phone.get(digits) if digits else None
                same = same or next((q for q in by_brand.get(brand, []) if _same_place(q, p)), None)
                if same:
                    _merge(same, p)
                else:
                    same = p
                    self.providers.append(p)
                    by_brand.setdefault(brand, []).append(p)
                if digits:
                    by_phone.setdefault(digits, same)
        profiles = json.loads(PROFILES.read_text()) if PROFILES.exists() else {}
        for p in self.providers:
            if p["id"] in profiles:
                p["profile"] = profiles[p["id"]]
                p["site_chars"] = p["profile"].get("site_chars", 0)
        self._by_id = {p["id"]: p for p in self.providers}

    def get(self, pid: str) -> dict | None:
        return self._by_id.get(pid)

    @property
    def ids(self) -> set[str]:
        return set(self._by_id)

    # ---------- search ----------
    def search(self, trade: str, zip_code: str | None = None, emergency: bool = False, limit: int = 3) -> list[Match]:
        if trade not in TRADES:
            return []
        pool = [p for p in self.providers if trade in p["trades"]]

        matches = []
        for p in pool:
            reasons, score = [], 0.0
            primary = p["trades"][0] == trade
            score += 3.0 if primary else 1.5
            reasons.append(f"{TRADES[trade]['label'].lower()} is {'their core trade' if primary else 'one of their listed services'}")
            if p.get("google_rating") and p.get("google_reviews"):
                q = p["google_rating"] * math.log10(1 + p["google_reviews"])
                score += q / 2
                reasons.append(f"{p['google_rating']}★ from {p['google_reviews']:,} Google reviews")
            else:
                reasons.append("no review data on file")
            if "durham" in (p.get("city") or "").lower() and "serves" not in (p.get("city") or "").lower():
                score += 1.0
                reasons.append("based in Durham")
            else:
                reasons.append(f"based in {p.get('city')}")
            if emergency:
                e = p.get("emergency_24_7")
                if e:
                    score += 3.0
                    reasons.append("listed as open 24/7")
                elif e is False:
                    reasons.append("posted hours aren't 24/7 (they may still take emergency calls)")
                else:
                    reasons.append("24/7 availability unknown")
            matches.append(Match(p, round(score, 2), reasons))
        matches.sort(key=lambda m: -m.score)
        out, brands = [], set()
        for m in matches:  # one row per brand, so a franchise's branches don't fill every slot
            b = brand_key(m.provider["name"])
            if b not in brands:
                brands.add(b)
                out.append(m)
            if len(out) == limit:
                break
        return out


def public_view(m: Match) -> dict:
    p = m.provider
    return {"provider_id": p["id"], "name": p["name"], "phone": p["phone"], "city": p.get("city"),
            "address": p.get("address"), "website": p.get("website"), "google_rating": p.get("google_rating"),
            "google_reviews": p.get("google_reviews"), "emergency_24_7": p.get("emergency_24_7"),
            "why": "; ".join(m.reasons), "maps_url": p.get("maps_url"), "data_source": p.get("data_source")}
