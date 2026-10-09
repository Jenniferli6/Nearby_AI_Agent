"""Ranking eval: is the top 3 the right set of providers for each homeowner need?

  python eval/ranking/run_ranking_eval.py                  # all systems, labels any new (query, provider) pair
  python eval/ranking/run_ranking_eval.py --no-rerank      # skip the LLM-rerank system (no per-query LLM call)
  python eval/ranking/run_ranking_eval.py --human-sheet    # write human_labels.csv for 10 queries
  python eval/ranking/run_ranking_eval.py --agreement      # compare your filled-in labels with the judge's

How it works
  * queries.json: 47 needs as the agent would hold them after the conversation (trade, ZIP, emergency,
    the problem in the user's terms). Job tags come from an LLM tagger, as the agent's tool call would.
  * Every system returns its top 5 (one row per brand). Each (query, provider) pair the systems return
    is labeled 0-3 once by an LLM judge reading the provider's evidence (pooling, as in TREC); labels are
    cached in labels.json, so a new system only pays for the pairs no other system has returned.
  * Metrics: NDCG@3 (graded), P@3 (share of the top 3 labeled good or excellent), excellent@1, MRR@5,
    "no good option in top 3" rate, mean distance of the top 3, latency.

Caveat: the judge reads the same website profiles the ranker uses, so it can share the ranker's blind
spots. human_labels.csv exists to measure that.
"""
import argparse
import concurrent.futures as cf
import csv
import json
import math
import os
import pathlib
import statistics
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
import anthropic  # noqa: E402

from nla.providers import ProviderDirectory  # noqa: E402
from nla.ranking import CONFIGS, DURHAM_CENTER, JOBS, Need, Ranker, km, provider_point, zip_point  # noqa: E402
from nla.taxonomy import TRADES  # noqa: E402

JUDGE_MODEL = os.getenv("NLA_JUDGE_MODEL", "claude-sonnet-5-5")
TAGS, LABELS = HERE / "need_tags.json", HERE / "labels.json"
client = anthropic.Anthropic()


def load(p):
    return json.loads(p.read_text()) if p.exists() else {}


def structured(system: str, user: str, schema: dict, effort: str = "medium") -> dict:
    r = client.messages.create(model=JUDGE_MODEL, max_tokens=8000, system=system,
                               output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
                               messages=[{"role": "user", "content": user}])
    if r.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"stop_reason={r.stop_reason}")
    return json.loads(next(b.text for b in r.content if b.type == "text"))


# ---------- need tagging (stands in for the agent filling job_tags in its tool call) ----------
def tag_need(q: dict) -> list[str]:
    trades = {q["trade"], q.get("secondary_trade")}
    options = {k: d for k, (t, d) in JOBS.items() if t in trades}
    schema = {"type": "object", "additionalProperties": False, "required": ["job_tags"],
              "properties": {"job_tags": {"type": "array", "items": {"type": "string", "enum": list(options)}}}}
    out = structured("Pick the 1-2 specific jobs this homeowner needs done. Only tags that clearly apply.",
                     f"Need: {q['text']}\nJobs:\n" + "\n".join(f"- {k}: {d}" for k, d in options.items()), schema, "low")
    return out["job_tags"][:2]


# ---------- judge ----------
RUBRIC = """You grade how well each local provider fits ONE homeowner need, as an experienced dispatcher would.
3 = excellent: right trade AND their own website clearly says they do this specific job (or it is plainly their core
    specialty), within ~25 km; for an emergency, 24/7 or emergency service is stated.
2 = good: right trade, plausibly does this job (generic or unstated), serves the area; emergency availability may be unknown.
1 = weak: adjacent trade or specialty mismatch, mainly commercial, farther than ~30 km, or little sign of an active
    residential business.
0 = wrong: cannot do this job (wrong trade, supplier, not a service business) or clearly unsuitable.
Judge only from the evidence shown. Missing website text is not by itself a reason to grade below 2."""


def card(p: dict, q: dict) -> dict:
    pr = p.get("profile") or {}
    pt = provider_point(p)
    return {"id": p["id"], "name": p["name"], "listed_trades": [TRADES[t]["label"] for t in p["trades"]],
            "city": p.get("city"), "km_from_user": round(km(zip_point(q["zip"]) or DURHAM_CENTER, pt), 1) if pt else None,
            "google_rating": p.get("google_rating"), "google_reviews": p.get("google_reviews"),
            "open_24h_listing": p.get("emergency_24_7"),
            "website": ("no website text" if not pr else {"summary": pr.get("summary"), "services": pr.get("services_text", [])[:15],
                                                            "service_area": pr.get("service_area"),
                                                            "emergency_service": pr.get("emergency_service"),
                                                            "residential_home_service": pr.get("is_home_service_provider")})}


def label_query(q: dict, providers: list[dict]) -> dict:
    schema = {"type": "object", "additionalProperties": False, "required": ["labels"],
              "properties": {"labels": {"type": "array", "items": {
                  "type": "object", "additionalProperties": False, "required": ["id", "label", "reason"],
                  "properties": {"id": {"type": "string", "enum": [p["id"] for p in providers]},
                                 "label": {"type": "integer", "enum": [0, 1, 2, 3]}, "reason": {"type": "string"}}}}}}
    need = {"problem": q["text"], "trade_needed": TRADES[q["trade"]]["label"], "zip": q["zip"], "emergency": q["emergency"]}
    out = structured(RUBRIC, json.dumps({"need": need, "providers": [card(p, q) for p in providers]}, ensure_ascii=False), schema)
    return {x["id"]: {"label": x["label"], "reason": x["reason"]} for x in out["labels"]}


# ---------- metrics ----------
def dcg(rels):
    return sum((2 ** r - 1) / math.log2(i + 2) for i, r in enumerate(rels))


def metrics(ranked: list[str], lab: dict, q: dict, d: ProviderDirectory) -> dict:
    rels = [lab[i]["label"] for i in ranked]
    ideal = dcg(sorted((v["label"] for v in lab.values()), reverse=True)[:3]) or 1
    first_good = next((i + 1 for i, r in enumerate(rels[:5]) if r >= 2), None)
    dists = [km(zip_point(q["zip"]) or DURHAM_CENTER, provider_point(d.get(i))) for i in ranked[:3] if provider_point(d.get(i))]
    return {"ndcg3": dcg(rels[:3]) / ideal, "p3": sum(r >= 2 for r in rels[:3]) / 3, "exc1": float(bool(rels) and rels[0] == 3),
            "mrr5": 1 / first_good if first_good else 0.0, "no_good3": float(not any(r >= 2 for r in rels[:3])),
            "km3": statistics.mean(dists) if dists else None}


def run(args) -> None:
    queries = json.loads((HERE / "queries.json").read_text())
    tags = load(TAGS)
    todo = [q for q in queries if q["id"] not in tags]
    if todo:
        print(f"Tagging {len(todo)} needs with {JUDGE_MODEL}")
        with cf.ThreadPoolExecutor(8) as ex:
            for q, t in zip(todo, ex.map(tag_need, todo)):
                tags[q["id"]] = t
        TAGS.write_text(json.dumps(tags, indent=1))
    R = Ranker()
    d = R.dir
    systems = ["v0_baseline"] + [k for k in CONFIGS if not (args.no_rerank and "rerank" in k)]
    runs, lat = {s: {} for s in systems}, {s: [] for s in systems}
    for q in queries:
        need = Need(q["trade"], q["text"], tags[q["id"]], q.get("secondary_trade"), q["zip"], q["emergency"])
        for s in systems:
            t0 = time.perf_counter()
            res = d.search(q["trade"], q["zip"], q["emergency"], limit=5) if s == "v0_baseline" else R.rank(need, CONFIGS[s], limit=5)
            lat[s].append((time.perf_counter() - t0) * 1e3)
            runs[s][q["id"]] = [m.provider["id"] for m in res]
    # label every returned pair once
    labels = load(LABELS)
    need_lab = {q["id"]: sorted({pid for s in systems for pid in runs[s][q["id"]]} - set(labels.get(q["id"], {}))) for q in queries}
    need_lab = {k: v for k, v in need_lab.items() if v}
    if need_lab:
        print(f"Judging {sum(map(len, need_lab.values()))} new pairs across {len(need_lab)} queries with {JUDGE_MODEL}")
        qs = {q["id"]: q for q in queries}
        with cf.ThreadPoolExecutor(6) as ex:
            futs = {ex.submit(label_query, qs[qid], [d.get(p) for p in pids]): qid for qid, pids in need_lab.items()}
            for f in cf.as_completed(futs):
                labels.setdefault(futs[f], {}).update(f.result())
        LABELS.write_text(json.dumps(labels, indent=1, ensure_ascii=False))
    # score
    table, per_q = [], {}
    for s in systems:
        ms = [metrics(runs[s][q["id"]], labels[q["id"]], q, d) for q in queries]
        per_q[s] = {q["id"]: m for q, m in zip(queries, ms)}
        avg = {k: statistics.mean(m[k] for m in ms if m[k] is not None) for k in ms[0]}
        table.append((s, avg, statistics.median(lat[s]), sorted(lat[s])[int(0.95 * (len(lat[s]) - 1))]))
    write_report(queries, systems, table, per_q, runs, labels, tags, d)


def write_report(queries, systems, table, per_q, runs, labels, tags, d) -> None:
    L = [f"# Ranking eval - {time.strftime('%Y-%m-%d %H:%M')}",
         f"{len(queries)} needs, top 5 per system (one row per brand). Judge: `{JUDGE_MODEL}`, labels 0-3 "
         f"({sum(map(len, labels.values()))} labeled pairs). Good = label 2 or 3.", "",
         "| system | NDCG@3 | P@3 | excellent@1 | MRR@5 | no good in top 3 | mean km (top 3) | latency p50 / p95 |",
         "|---|---|---|---|---|---|---|---|"]
    for s, a, p50, p95 in table:
        L.append(f"| {s} | {a['ndcg3']:.3f} | {a['p3']:.2f} | {a['exc1']:.2f} | {a['mrr5']:.2f} | {a['no_good3']:.0%} | "
                 f"{a['km3']:.1f} | {p50:.0f} / {p95:.0f} ms |")
    best = max(table, key=lambda t: t[1]["ndcg3"])[0]
    L += ["", f"## Per trade, NDCG@3 (v0_baseline vs {best})", "", "| trade | n | v0 | best |", "|---|---|---|---|"]
    by_trade = {}
    for q in queries:
        by_trade.setdefault(q["trade"], []).append(q["id"])
    for t, ids in sorted(by_trade.items()):
        L.append(f"| {t} | {len(ids)} | {statistics.mean(per_q['v0_baseline'][i]['ndcg3'] for i in ids):.2f} | "
                 f"{statistics.mean(per_q[best][i]['ndcg3'] for i in ids):.2f} |")
    L += ["", f"## Where {best} is still weakest (lowest NDCG@3)", ""]
    for q in sorted(queries, key=lambda q: per_q[best][q["id"]]["ndcg3"])[:6]:
        L.append(f"- **{q['id']}** (tags {tags[q['id']]}): NDCG@3 {per_q[best][q['id']]['ndcg3']:.2f}")
        for pid in runs[best][q["id"]][:3]:
            lab = labels[q["id"]][pid]
            L.append(f"    - [{lab['label']}] {d.get(pid)['name']}: {lab['reason']}")
    out = HERE / "report.md"
    out.write_text("\n".join(L) + "\n")
    (HERE / "runs.json").write_text(json.dumps({"runs": runs, "per_query": per_q}, indent=1))
    print("\n".join(L[:5 + len(table)]))
    print(f"\nReport -> {out}")


# ---------- human labels ----------
HUMAN_IDS = ["basement_storm_standing", "sump_pump_failed", "basement_seep_recurring", "roof_leak_storm", "no_heat_winter",
             "water_heater_leak", "crawl_encapsulation", "panel_upgrade", "washer_leak", "termite_swarm"]


def human_sheet() -> None:
    queries = {q["id"]: q for q in json.loads((HERE / "queries.json").read_text())}
    labels, d = load(LABELS), ProviderDirectory()
    out = HERE / "human_labels.csv"
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["query_id", "need", "zip", "emergency", "provider_id", "provider", "km_from_user", "google_rating",
                    "open_24h_listing", "what_their_website_says", "website", "your_label_0_to_3"])
        for qid in HUMAN_IDS:
            q = queries[qid]
            for pid in sorted(labels[qid])[:8]:
                c = card(d.get(pid), q)
                site = c["website"] if isinstance(c["website"], str) else f"{c['website']['summary']} | services: {'; '.join(c['website']['services'][:8])}"
                w.writerow([qid, q["text"], q["zip"], q["emergency"], pid, c["name"], c["km_from_user"],
                            f"{c['google_rating']} ({c['google_reviews']})", c["open_24h_listing"], site, d.get(pid).get("website"), ""])
    print(f"Wrote {out}. Fill the last column with 0-3 using the rubric at the top of this script, then run --agreement.")


def agreement() -> None:
    labels = load(LABELS)
    pairs = []
    with (HERE / "human_labels.csv").open() as f:
        for r in csv.DictReader(f):
            if r["your_label_0_to_3"].strip():
                pairs.append((int(r["your_label_0_to_3"]), labels[r["query_id"]][r["provider_id"]]["label"]))
    if not pairs:
        print("No human labels filled in yet.")
        return
    n = len(pairs)
    exact = sum(h == j for h, j in pairs) / n
    within1 = sum(abs(h - j) <= 1 for h, j in pairs) / n
    good = sum((h >= 2) == (j >= 2) for h, j in pairs) / n
    # quadratic-weighted kappa
    W = lambda a, b: (a - b) ** 2 / 9
    hs, js = [h for h, _ in pairs], [j for _, j in pairs]
    obs = sum(W(h, j) for h, j in pairs) / n
    exp = sum(W(a, b) * hs.count(a) * js.count(b) for a in range(4) for b in range(4)) / n ** 2
    print(f"{n} pairs | exact {exact:.0%} | within 1 {within1:.0%} | same good/not-good call {good:.0%} | "
          f"weighted kappa {1 - obs / exp if exp else float('nan'):.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-rerank", action="store_true")
    ap.add_argument("--human-sheet", action="store_true")
    ap.add_argument("--agreement", action="store_true")
    a = ap.parse_args()
    human_sheet() if a.human_sheet else agreement() if a.agreement else run(a)
