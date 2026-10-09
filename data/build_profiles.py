"""Provider profiles from each provider's own website: what jobs they say they do, where, and evidence.

Two cached stages (each skips providers already done, so reruns cost nothing):

  python data/build_profiles.py crawl              # homepage + up to 2 service pages -> data/provider_pages.json
  python data/build_profiles.py extract --limit 10 # Claude reads the pages -> data/provider_profiles.json
  python data/build_profiles.py extract            # the rest

The crawler respects robots.txt and fetches at most 3 pages per site. Extraction uses structured
outputs, so every profile has the same schema; job tags come from nla.taxonomy.JOBS and must be stated
on the site, with short verbatim quotes kept as evidence.
"""
import argparse
import concurrent.futures as cf
import datetime
import json
import os
import pathlib
import re
import sys
import time
import urllib.robotparser
from urllib.parse import urljoin, urlparse, urlunparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from nla.providers import ProviderDirectory  # noqa: E402
from nla.taxonomy import JOBS, TRADES  # noqa: E402

PAGES = ROOT / "data" / "provider_pages.json"
PROFILES = ROOT / "data" / "provider_profiles.json"
UA = "Mozilla/5.0 (compatible; NearbyLeadAgentResearch/0.1; one-time crawl of public service pages)"
SERVICE_WORDS = re.compile(r"service|repair|plumb|hvac|heat|cool|air|electric|roof|gutter|water|flood|mold|basement|crawl|"
                           r"foundation|pest|termite|appliance|handyman|drain|sewer|what-we-do|residential", re.I)
MAX_CHARS = 7000
EXTRACT_MODEL = os.getenv("NLA_EXTRACT_MODEL", "claude-haiku-5-5")
PRICE = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0)}  # $/1M in, out


def load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


# ---------------- crawl ----------------
def site_url(website: str) -> str:
    u = website if "//" in website else "https://" + website
    p = urlparse(u)
    return urlunparse((p.scheme or "https", p.netloc, p.path or "/", "", "", ""))  # drop utm query strings


def page_text(html: str) -> tuple[str, list[tuple[str, str]]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    links = [(a.get("href", ""), a.get_text(" ", strip=True)) for a in soup.find_all("a")]
    for t in soup(["script", "style", "noscript", "svg", "iframe"]):
        t.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    return text, links


def crawl_one(p: dict) -> dict:
    import httpx

    out = {"website": p["website"], "fetched": datetime.date.today().isoformat(), "pages": [], "error": None}
    home = site_url(p["website"])
    try:
        with httpx.Client(headers={"User-Agent": UA}, timeout=12, follow_redirects=True) as c:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = c.get(urljoin(home, "/robots.txt"))
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except httpx.HTTPError:
                rp.parse([])
            if not rp.can_fetch(UA, home):
                out["error"] = "disallowed by robots.txt"
                return out
            r = c.get(home)
            r.raise_for_status()
            text, links = page_text(r.text)
            out["pages"].append({"url": str(r.url), "text": text[:MAX_CHARS]})
            host = urlparse(str(r.url)).netloc
            seen, extra = {str(r.url).rstrip("/")}, []
            for href, label in links:
                u = urljoin(str(r.url), href).split("#")[0].rstrip("/")
                if urlparse(u).netloc != host or u in seen or not u.startswith("http"):
                    continue
                if SERVICE_WORDS.search(urlparse(u).path) or SERVICE_WORDS.search(label):
                    seen.add(u)
                    extra.append(u)
            for u in extra[:2]:
                if not rp.can_fetch(UA, u):
                    continue
                try:
                    r2 = c.get(u)
                    if r2.status_code == 200 and "html" in r2.headers.get("content-type", ""):
                        out["pages"].append({"url": str(r2.url), "text": page_text(r2.text)[0][:MAX_CHARS]})
                except httpx.HTTPError:
                    pass
    except Exception as e:  # one bad site must not stop the crawl
        out["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    return out


def crawl(providers: list[dict], refresh: bool) -> None:
    pages = load(PAGES)
    todo = [p for p in providers if p.get("website") and (refresh or p["id"] not in pages)]
    print(f"Crawling {len(todo)} sites ({len(pages)} already cached)")
    t0 = time.time()
    with cf.ThreadPoolExecutor(12) as ex:
        for i, (p, res) in enumerate(zip(todo, ex.map(crawl_one, todo)), 1):
            pages[p["id"]] = res
            if i % 25 == 0 or i == len(todo):
                PAGES.write_text(json.dumps(pages, indent=1, ensure_ascii=False))
                print(f"  {i}/{len(todo)}  ({time.time() - t0:.0f}s)")
    ok = sum(1 for v in pages.values() if v["pages"])
    print(f"Sites with text: {ok}/{len(pages)}. Errors: {sum(1 for v in pages.values() if v['error'])}")


# ---------------- extract ----------------
SCHEMA = {
    "type": "object",
    "properties": {
        "is_home_service_provider": {"type": "boolean", "description": "False for suppliers, parts stores, directories, unrelated businesses"},
        "summary": {"type": "string", "description": "<= 40 words, only what the site says"},
        "job_tags": {"type": "array", "items": {"type": "string", "enum": list(JOBS)}},
        "services_text": {"type": "array", "items": {"type": "string"}, "description": "<= 25 short service phrases as the site words them"},
        "service_area": {"type": "array", "items": {"type": "string"}, "description": "towns, counties or ZIPs the site says it serves"},
        "emergency_service": {"type": "string", "enum": ["yes", "no", "not_stated"], "description": "site claims 24/7 or emergency service"},
        "license_numbers": {"type": "array", "items": {"type": "string"}, "description": "license numbers as written, e.g. 'NC Plumbing #12345'"},
        "years_in_business": {"type": "integer", "description": "0 if not stated"},
        "evidence": {"type": "array", "items": {"type": "string"}, "description": "<= 4 short verbatim quotes supporting the job tags and emergency claim"},
    },
    "required": ["is_home_service_provider", "summary", "job_tags", "services_text", "service_area", "emergency_service",
                 "license_numbers", "years_in_business", "evidence"],
    "additionalProperties": False,
}
JOB_LIST = "\n".join(f"- {k}: {d}" for k, (_, d) in JOBS.items())
SYSTEM = f"""You extract a factual profile of a home-services business from text scraped from its own website.
Only record what the text states; never infer services from the business name or category alone.
job_tags: choose from this list only the jobs the site says it does (a service page, service list or clear statement):
{JOB_LIST}
If the pages are empty, an error page, or about something else, return empty lists and say so in the summary."""


def extract_one(client, p: dict, pages: dict) -> tuple[dict, dict]:
    body = "\n\n".join(f"### {pg['url']}\n{pg['text']}" for pg in pages["pages"])
    msg = (f"Business: {p['name']} ({p.get('city')}). Listed under: {', '.join(TRADES[t]['label'] for t in p['trades'])}.\n\n"
           f"Website text:\n{body}")
    r = client.messages.create(model=EXTRACT_MODEL, max_tokens=4000, system=SYSTEM,
                               output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
                               messages=[{"role": "user", "content": msg}])
    if r.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"stop_reason={r.stop_reason}")
    prof = json.loads(next(b.text for b in r.content if b.type == "text"))
    prof.update(source_urls=[pg["url"] for pg in pages["pages"]], retrieved=pages["fetched"], model=EXTRACT_MODEL,
                site_chars=sum(len(pg["text"]) for pg in pages["pages"]))  # how much text the verdict rests on
    return prof, {"in": r.usage.input_tokens, "out": r.usage.output_tokens}


def extract(providers: list[dict], limit: int | None) -> None:
    import anthropic
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    client = anthropic.Anthropic()
    pages, profiles = load(PAGES), load(PROFILES)
    todo = [p for p in providers if pages.get(p["id"], {}).get("pages") and p["id"] not in profiles][:limit]
    print(f"Extracting {len(todo)} profiles with {EXTRACT_MODEL} ({len(profiles)} already done)")
    tok, fails, t0 = {"in": 0, "out": 0}, [], time.time()
    with cf.ThreadPoolExecutor(8) as ex:
        futs = {ex.submit(extract_one, client, p, pages[p["id"]]): p for p in todo}
        for i, f in enumerate(cf.as_completed(futs), 1):
            p = futs[f]
            try:
                prof, u = f.result()
                profiles[p["id"]] = prof
                tok["in"] += u["in"]
                tok["out"] += u["out"]
            except Exception as e:
                fails.append((p["name"], str(e)[:100]))
            if i % 20 == 0 or i == len(todo):
                PROFILES.write_text(json.dumps(profiles, indent=1, ensure_ascii=False))
    pin, pout = PRICE.get(EXTRACT_MODEL, (0, 0))
    cost = tok["in"] / 1e6 * pin + tok["out"] / 1e6 * pout
    print(f"Done in {time.time() - t0:.0f}s. Tokens in/out: {tok['in']:,}/{tok['out']:,} -> ${cost:.3f}"
          f" (${cost / max(1, len(todo) - len(fails)):.4f} per profile). Failures: {fails or 'none'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["crawl", "extract"])
    ap.add_argument("--limit", type=int, help="extract: only the first N (to measure cost)")
    ap.add_argument("--refresh", action="store_true", help="crawl: refetch sites already cached")
    args = ap.parse_args()
    providers = ProviderDirectory().providers
    crawl(providers, args.refresh) if args.stage == "crawl" else extract(providers, args.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
