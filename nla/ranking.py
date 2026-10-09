"""Provider retrieval and ranking for one homeowner need.

  need ──► candidates (trade, or a website-stated job match; drop confirmed non-residential businesses)
       ──► features (job-tag match, hybrid text relevance, review-adjusted rating, volume, distance,
                     emergency fit, license listed)
       ──► weighted score ──► optional LLM rerank of the top 10 ──► one row per brand ──► top k
       ──► reasons a user can check: every reason names its source

Every stage can be switched off through RankConfig, so eval/ranking/run_ranking_eval.py measures what
each one adds. Unknown values are neutral by design: a provider with no website text is not punished
for it, and no data source is a ranking signal in itself.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import pathlib
import re
import threading
import time
from dataclasses import dataclass, field

from .providers import Match, ProviderDirectory, brand_key
from .taxonomy import JOBS, TRADES

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
DURHAM_CENTER = (35.994, -78.8986)
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
_EMBED_LOCK = threading.RLock()  # re-entrant: vecs() may load the model while holding it


@dataclass
class Need:
    trade: str
    text: str = ""                          # the problem in the user's terms: summary + facts
    job_tags: list[str] = field(default_factory=list)
    secondary_trade: str | None = None
    zip_code: str | None = None
    emergency: bool = False


@dataclass
class RankConfig:
    name: str = "full"
    tags: bool = True          # job-tag match against the provider's website profile
    bm25: bool = True          # keyword relevance
    embed: bool = True         # semantic relevance
    distance: bool = True
    bayes: bool = True         # review-count-adjusted rating instead of raw stars
    rerank: bool = False       # LLM rerank of the top 10
    max_km: float = 60.0
    weights: dict = field(default_factory=lambda: dict(
        trade=2.0, tags=2.5, text=1.5, quality=2.0, volume=1.0, distance=1.5, emergency=2.5, license=0.3))


CONFIGS = {
    "v1_distance_bayes": RankConfig("v1_distance_bayes", tags=False, bm25=False, embed=False),
    "v2_+tags": RankConfig("v2_+tags", bm25=False, embed=False),
    "v3_+bm25": RankConfig("v3_+bm25", embed=False),
    "v3_+embed": RankConfig("v3_+embed", bm25=False),
    "v4_hybrid": RankConfig("v4_hybrid"),
    "v5_hybrid+rerank": RankConfig("v5_hybrid+rerank", rerank=True),
}


# ---------------- geography ----------------
_ZIPS: dict | None = None


def zip_point(z: str | None) -> tuple[float, float] | None:
    global _ZIPS
    if _ZIPS is None:
        _ZIPS = json.loads((DATA / "zip_centroids.json").read_text())["zips"]
    return tuple(_ZIPS[z]) if z and z in _ZIPS else None


def provider_point(p: dict) -> tuple[float, float] | None:
    if p.get("lat") is not None:
        return p["lat"], p["lng"]
    zips = re.findall(r"\b(\d{5})\b", p.get("address") or "")
    return zip_point(zips[-1]) if zips else None


def km(a, b) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


# ---------------- provider text ----------------
def provider_doc(p: dict) -> str:
    pr = p.get("profile") or {}
    parts = [p["name"], ", ".join(TRADES[t]["label"] for t in p["trades"]), pr.get("summary", ""),
             "; ".join(pr.get("services_text", [])), "; ".join(JOBS[t][1] for t in pr.get("job_tags", []) if t in JOBS),
             p.get("notes") or ""]
    return ". ".join(x for x in parts if x)


def tokens(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


class TextIndex:
    """BM25 + embeddings over provider documents. Embeddings are cached on disk by document hash."""

    def __init__(self, providers: list[dict]):
        from rank_bm25 import BM25Okapi

        self.ids = [p["id"] for p in providers]
        self.docs = [provider_doc(p) for p in providers]
        self.bm25 = BM25Okapi([tokens(d) for d in self.docs])
        self._vecs = None
        self._model = None

    def _embedder(self):
        with _EMBED_LOCK:  # concurrent first loads race inside the model downloader
            if self._model is None:
                from fastembed import TextEmbedding
                cache = os.getenv("FASTEMBED_CACHE_PATH", str(pathlib.Path.home() / ".cache" / "fastembed"))
                self._model = TextEmbedding(EMBED_MODEL, cache_dir=cache)
        return self._model

    def vecs(self):
        """Document vectors, cached on disk per document hash (only new or changed documents are embedded)."""
        import numpy as np

        with _EMBED_LOCK:
            if self._vecs is not None:
                return self._vecs
            cache = DATA / "provider_embeddings.npz"
            hashes = [hashlib.sha1(d.encode()).hexdigest()[:16] for d in self.docs]
            known = {}
            if cache.exists():
                z = np.load(cache, allow_pickle=False)
                known = dict(zip(z["hashes"].tolist(), z["vecs"]))
            missing = [(h, d) for h, d in zip(hashes, self.docs) if h not in known]
            if missing:
                new = self._embedder().passage_embed([d for _, d in missing])
                known.update({h: np.asarray(v, dtype="float32") for (h, _), v in zip(missing, new)})
                np.savez(cache, hashes=np.array(list(known)), vecs=np.stack(list(known.values())))
            self._vecs = np.stack([known[h] for h in hashes])
        return self._vecs

    def warm(self) -> None:
        """Load the embedding model and document vectors now instead of on the first search."""
        self._embedder()
        self.vecs()

    def bm25_scores(self, query: str) -> dict[str, float]:
        return dict(zip(self.ids, self.bm25.get_scores(tokens(query))))

    def embed_scores(self, query: str) -> dict[str, float]:
        import numpy as np

        q = np.array(list(self._embedder().query_embed([query]))[0], dtype="float32")
        v = self.vecs()
        sims = v @ q / (np.linalg.norm(v, axis=1) * np.linalg.norm(q) + 1e-9)
        return dict(zip(self.ids, sims.tolist()))


def rrf(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    """Reciprocal rank fusion: robust to BM25 and cosine scores living on different scales."""
    out: dict[str, float] = {}
    for r in rankings:
        for i, pid in enumerate(r):
            out[pid] = out.get(pid, 0.0) + 1.0 / (k + i + 1)
    return out


# ---------------- ranker ----------------
class Ranker:
    def __init__(self, directory: ProviderDirectory | None = None, reuse_model_from: "Ranker | None" = None):
        self.dir = directory or ProviderDirectory()
        self.index = TextIndex(self.dir.providers)
        if reuse_model_from is not None:  # rebuilding after a pro edits their listing: skip reloading the model
            self.index._model = reuse_model_from.index._model
        self.last_timing: dict[str, float] = {}

    def candidates(self, need: Need, cfg: RankConfig) -> list[dict]:
        trades = {need.trade, need.secondary_trade} - {None}
        tags = set(need.job_tags)
        out = []
        for p in self.dir.providers:
            pr = p.get("profile") or {}
            if pr and not pr.get("is_home_service_provider", True) and p.get("site_chars", 0) >= 1000:
                continue  # its own website says it's a supplier, school or commercial-only contractor
            if trades & set(p["trades"]) or (cfg.tags and tags & set(pr.get("job_tags", []))):
                out.append(p)
        return out

    def features(self, p: dict, need: Need, cfg: RankConfig, text_rel: dict[str, float]) -> tuple[dict, list[str]]:
        pr = p.get("profile") or {}
        f, why = {}, []
        # trade fit
        if p["trades"][0] == need.trade:
            f["trade"] = 1.0
            why.append(f"{TRADES[need.trade]['label'].lower()} is their core trade")
        elif need.trade in p["trades"]:
            f["trade"] = 0.6
            why.append(f"lists {TRADES[need.trade]['label'].lower()} among their services")
        else:
            f["trade"] = 0.4
            why.append("their website lists this job")
        # job-tag match (website-stated); unknown when we have no website text
        if cfg.tags and need.job_tags:
            if pr.get("job_tags"):
                hit = [t for t in need.job_tags if t in pr["job_tags"]]
                f["tags"] = len(hit) / len(need.job_tags)
                if hit:
                    src = "the business says it does " if p.get("claimed") else "their website says they do "
                    why.append(src + ", ".join(JOBS[t][1].split(",")[0] for t in hit))
            else:
                f["tags"] = 0.25
        # text relevance
        if p["id"] in text_rel:
            f["text"] = text_rel[p["id"]]
        # quality
        r, n = p.get("google_rating"), p.get("google_reviews") or 0
        if r:
            q = (25 * 4.5 + n * r) / (25 + n) if cfg.bayes else r
            f["quality"] = min(1.0, max(0.0, (q - 4.0) / 1.0))
            f["volume"] = min(1.0, math.log10(1 + n) / 3.5)
            why.append(f"{r}★ from {n:,} Google reviews")
        else:
            f["quality"], f["volume"] = 0.5, 0.0
            why.append("no review data")
        # distance (unknown -> neutral)
        user = zip_point(need.zip_code) or DURHAM_CENTER
        pt = provider_point(p)
        if cfg.distance:
            if pt:
                d = km(user, pt)
                f["distance"] = max(0.0, 1 - d / 40)
                f["_km"] = d
                why.append(f"{d:.0f} km from {need.zip_code or 'central Durham'}")
            else:
                f["distance"] = 0.5
        else:
            f["distance"] = 1.0 if "durham" in (p.get("city") or "").lower() else 0.0
        # emergency fit: Google 24h hours, the seed's researched flag, or the site's own claim
        if need.emergency:
            site = pr.get("emergency_service")
            if p.get("emergency_24_7") or site == "yes":
                f["emergency"] = 1.0
                why.append("listed as open 24/7" if p.get("emergency_24_7") else "their website says they offer emergency service")
            else:
                f["emergency"] = 0.0
                why.append("24/7 availability unknown" if p.get("emergency_24_7") is None and site != "no" else "not listed as 24/7")
        if p.get("license_number"):
            f["license"] = 1.0
            why.append(f"license {p['license_number']} submitted by the business, not yet verified with the state")
        elif pr.get("license_numbers"):
            f["license"] = 1.0
            why.append(f"license number on their website ({pr['license_numbers'][0]}), not yet verified with the state")
        return f, why

    def rank(self, need: Need, cfg: RankConfig | None = None, limit: int = 3) -> list[Match]:
        cfg = cfg or RankConfig()
        t0 = time.perf_counter()
        pool = self.candidates(need, cfg)
        if cfg.distance:
            user = zip_point(need.zip_code) or DURHAM_CENTER
            pool = [p for p in pool if not provider_point(p)
                    or km(user, provider_point(p)) <= min(cfg.max_km, p.get("service_radius_km") or cfg.max_km)]
        t1 = time.perf_counter()
        query = " ".join([need.text] + [JOBS[t][1] for t in need.job_tags if t in JOBS])
        rankings = []
        ids = {p["id"] for p in pool}
        if cfg.bm25 and query.strip():
            s = self.index.bm25_scores(query)
            rankings.append(sorted(ids, key=lambda i: -s[i]))
        if cfg.embed and query.strip():
            s = self.index.embed_scores(query)
            rankings.append(sorted(ids, key=lambda i: -s[i]))
        fused = rrf(rankings) if rankings else {}
        if fused:
            lo, hi = min(fused.values()), max(fused.values())
            fused = {k: (v - lo) / (hi - lo or 1) for k, v in fused.items()}
        t2 = time.perf_counter()
        scored = []
        for p in pool:
            f, why = self.features(p, need, cfg, fused)
            s = sum(cfg.weights.get(k, 0) * v for k, v in f.items() if not k.startswith("_"))
            scored.append(Match(p, round(s, 3), why))
        scored.sort(key=lambda m: -m.score)
        if cfg.rerank:
            scored = llm_rerank(need, scored[:10]) + scored[10:]
        t3 = time.perf_counter()
        out, brands = [], set()
        for m in scored:
            b = brand_key(m.provider["name"])
            if b not in brands:
                brands.add(b)
                out.append(m)
            if len(out) == limit:
                break
        self.last_timing = {"candidates_ms": (t1 - t0) * 1e3, "text_ms": (t2 - t1) * 1e3,
                            "score_rerank_ms": (t3 - t2) * 1e3, "total_ms": (time.perf_counter() - t0) * 1e3, "pool": len(pool)}
        return out


# ---------------- LLM rerank ----------------
RERANK_MODEL = os.getenv("NLA_RERANK_MODEL", "claude-sonnet-5-5")
RERANK_SYSTEM = """You order local home-service providers for one homeowner's job, best first.
Judge only from the evidence given: whether they do this specific job (their own website), whether the
trade is right, distance, emergency availability when it's urgent, and review strength.
Prefer a provider whose site clearly states the job over one that only matches the trade."""


def evidence_card(m: Match) -> dict:
    p, pr = m.provider, m.provider.get("profile") or {}
    return {"id": p["id"], "name": p["name"], "trades": p["trades"], "reasons": m.reasons,
            "site_summary": pr.get("summary", "no website text"), "site_services": pr.get("services_text", [])[:12],
            "site_job_tags": pr.get("job_tags", []), "service_area": pr.get("service_area", [])}


def llm_rerank(need: Need, top: list[Match]) -> list[Match]:
    import anthropic

    if len(top) < 2:
        return top
    schema = {"type": "object", "additionalProperties": False, "required": ["order"],
              "properties": {"order": {"type": "array", "items": {"type": "string", "enum": [m.provider["id"] for m in top]}}}}
    msg = json.dumps({"need": {"trade": need.trade, "problem": need.text, "jobs": need.job_tags, "zip": need.zip_code,
                               "emergency": need.emergency},
                      "providers": [evidence_card(m) for m in top]}, ensure_ascii=False)
    r = anthropic.Anthropic().messages.create(
        model=RERANK_MODEL, max_tokens=2000, system=RERANK_SYSTEM,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": msg}])
    if r.stop_reason in ("refusal", "max_tokens"):
        return top  # keep the feature ranking rather than fail the search
    order = json.loads(next(b.text for b in r.content if b.type == "text"))["order"]
    by_id = {m.provider["id"]: m for m in top}
    seen = [by_id[i] for i in dict.fromkeys(order) if i in by_id]
    return seen + [m for m in top if m not in seen]
