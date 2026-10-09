"""Writes data/PROVIDERS.md: every provider in the merged directory, with links to spot-check it."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from nla.providers import ProviderDirectory  # noqa: E402

d = ProviderDirectory()
rows = sorted(d.providers, key=lambda p: (p["trades"][0], -(p.get("google_reviews") or 0)))
L = ["# Durham-area provider directory", "",
     f"{len(rows)} providers after entity matching: 43 hand-researched seed rows plus Google Places listings, retrieved "
     "2026-10-08. 'Website jobs' counts the specific jobs the provider's own site says it does (data/provider_profiles.json). "
     "Spot-check any row through its Google Maps or source link.", "",
     "| Trade (primary) | Provider | Phone | City | Google rating | 24/7 | Website jobs | Source |", "|---|---|---|---|---|---|---|---|"]
for p in rows:
    pr = p.get("profile") or {}
    rating = f"{p['google_rating']} ({p['google_reviews']:,})" if p.get("google_rating") else "-"
    e = {True: "yes", False: "no", None: "unknown"}[p.get("emergency_24_7")]
    jobs = str(len(pr.get("job_tags", []))) if pr else "no site text"
    if pr and not pr.get("is_home_service_provider", True) and p.get("site_chars", 0) >= 1000:
        jobs = "excluded: not residential"
    link = p.get("maps_url") or p.get("source_url")
    L.append(f"| {p['trades'][0]} | {p['name']} | {p['phone']} | {p.get('city')} | {rating} | {e} | {jobs} | [link]({link}) |")
out = ROOT / "data" / "PROVIDERS.md"
out.write_text("\n".join(L) + "\n")
print(len(rows), "rows ->", out)
