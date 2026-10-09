"""Evaluate the agent on the two metrics Nearby cares about.

  python eval/run_eval.py                 # all scenarios
  python eval/run_eval.py --only basement_storm_standing --repeats 3

Each scenario: a simulated homeowner (LLM with hidden facts + patience budget) talks to the agent.
Then:
  * CONVERSION  - did a dispatchable lead get submitted? (deterministic: submit_lead passed the gate)
  * LEAD QUALITY
      - deterministic checks vs hidden facts: trade acceptable, urgency acceptable, ZIP & phone correct,
        providers real and serve that trade
      - provider-judge LLM: reads ONLY what the provider would receive and decides "would I take this lead
        at ~$50?" (accept + 1-5 score + callback-needed questions)
      - faithfulness judge: compares the lead against hidden facts and flags anything invented
  * BEHAVIOUR on no-lead scenarios (out of area, out of scope, DIY, refuses phone, gas leak): no false leads
Results -> eval/results/<timestamp>/{results.json,report.md}
"""
from __future__ import annotations

import argparse, json, os, pathlib, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import anthropic
from nla.agent import LeadAgent
from nla.lead import normalize_phone
from nla.providers import ProviderDirectory
from nla.ranking import Ranker
from nla.taxonomy import JOBS

SIM_MODEL = os.getenv("NLA_SIM_MODEL", os.getenv("NLA_MODEL", "claude-sonnet-5-5"))
JUDGE_MODEL = os.getenv("NLA_JUDGE_MODEL", SIM_MODEL)
client = anthropic.Anthropic()
DIR = ProviderDirectory()
RANKER = Ranker(DIR)  # shared, so the text index and embeddings load once
RANKER.index.warm()  # before the worker threads start


def serves_trade(p: dict, trade: str) -> bool:
    """Listed under the trade, or its own website says it does a job in that trade."""
    return trade in p["trades"] or any(JOBS[t][0] == trade for t in (p.get("profile") or {}).get("job_tags", []) if t in JOBS)


import threading
USAGE = {"input_tokens": 0, "output_tokens": 0}
_lock = threading.Lock()


def add_usage(u):
    if u is None:
        return
    with _lock:
        USAGE["input_tokens"] += getattr(u, "input_tokens", 0) or 0
        USAGE["output_tokens"] += getattr(u, "output_tokens", 0) or 0


def llm(model, system, messages, max_tokens=2000):
    """max_tokens is generous on purpose: if the model thinks first, a small cap leaves no room for the answer
    (that caused empty simulator replies / judge parse errors in the first run)."""
    for attempt in range(4):
        try:
            r = client.messages.create(model=model, max_tokens=max_tokens, system=system, messages=messages)
            add_usage(getattr(r, "usage", None))
            text = "".join(b.text for b in r.content if b.type == "text").strip()
            if text or attempt == 3:
                return text
        except anthropic.BadRequestError as e:
            if "credit balance" in str(e):
                raise SystemExit("Out of API credit - stopping eval.") from e
            raise
        except anthropic.APIError:
            if attempt == 3:
                raise
        time.sleep(2 ** attempt * 2)


SIM_SYSTEM = """You are role-playing a homeowner chatting with a home-repair assistant. Stay in character.
What you know (only reveal a fact when asked or when it's natural; don't dump everything at once):
{facts}
Your style: {style}.
Rules: write only your next chat message (1-2 short sentences). Answer what was asked. If the assistant asks
something you don't know, say you're not sure. If it asks for confirmation of a correct summary and you want help, say yes.
If the summary contains something wrong, correct it. If you are done (help received, or you decided not to proceed),
or you're annoyed by too many questions, reply exactly: [END]"""


# Whether this homeowner wants a pro is part of the scenario, not left to the simulator: the agent only offers a pro
# when asked, so an unstated intent makes "no lead" ambiguous (a correct DIY outcome, or a lost lead?).
INTENT_TEXT = {
    "wants_pro": "You want a pro to handle this. If the assistant offers DIY steps or a pro, say you'd rather have a pro, "
                 "then answer its other questions normally.",
    "open": "You're open to fixing it yourself if it sounds easy and safe. Follow the facts above for what happens when you try; "
            "you only want a pro if the DIY steps don't work or sound risky.",
}


def simulate(sc: dict) -> dict:
    agent = LeadAgent(ranker=RANKER, save_leads=False)
    user_msg = sc["opening"]
    turns, ended_by = 0, "max_turns"
    t0 = time.time()
    while True:
        turns += 1
        reply = agent.reply(user_msg)
        if agent.lead.status == "submitted":
            ended_by = "lead_submitted"
            break
        if turns >= sc.get("patience", 8):
            ended_by = "user_patience_exhausted"
            break
        # Rebuild history from the simulator's point of view (roles flipped, same-role turns merged).
        sim_history_msgs = [{"role": "user", "content": "(conversation start)"}]
        for m in agent.transcript():
            role = "assistant" if m["role"] == "user" else "user"
            if sim_history_msgs[-1]["role"] == role:
                sim_history_msgs[-1]["content"] += "\n" + m["text"]
            else:
                sim_history_msgs.append({"role": role, "content": m["text"]})
        if sim_history_msgs[-1]["role"] != "user":
            sim_history_msgs.append({"role": "user", "content": "(no reply)"})
        facts = (sc["facts"] + " " + INTENT_TEXT.get(sc.get("intent"), "")).strip()
        user_msg = llm(SIM_MODEL, SIM_SYSTEM.format(facts=facts, style=sc["style"]), sim_history_msgs)
        if "[END]" in user_msg or not user_msg:
            ended_by = "user_ended"
            break
    add_usage(agent.usage_obj())
    return {"agent": agent, "turns": turns, "ended_by": ended_by, "seconds": round(time.time() - t0, 1)}


PROVIDER_JUDGE = """You are the owner of a {trade_label} business in Durham, NC. Leads cost you about $50 each.
Here is a lead exactly as it arrived on your phone:
---
{message}
---
Would you pay for and act on this lead? Respond with JSON only:
{{"accept": true/false, "score": 1-5, "right_trade_for_me": true/false,
  "callback_questions": ["questions you'd still have to ask before quoting/scheduling"], "reason": "one sentence"}}
Score guide: 5 = I know exactly what to bring and when; 3 = workable but I need a call to scope it; 1 = junk/unclear/not my trade."""

FAITHFUL_JUDGE = """Compare a lead created by an assistant against the ground-truth facts of what the homeowner knows.
GROUND TRUTH: {facts}
TRANSCRIPT:
{transcript}
LEAD:
{lead}
The assistant's policy (do NOT count these as fabrication):
- It infers urgency from obvious cues ("last night", "standing water", "no heat in January", "need someone today" with
  active damage -> emergency) and property type from obvious cues (a basement -> a house).
- When no lead is appropriate (out of scope, out of area, DIY only, safety-first exit), the lead stays mostly empty. Empty
  or null fields are omissions, not contradictions.
Count as fabricated: facts the user never stated or confirmed, the assistant's own suggestions recorded as things the user
did or saw, and safety flags for hazards the user did not confirm.
Respond with JSON only: {{"fabricated": ["claims in the lead not supported by the transcript"],
 "contradictions": ["lead claims that contradict ground truth or the transcript"],
 "safety_handled": true/false/null  (null if no safety issue; true if a safety issue existed and the assistant gave correct safety guidance early),
 "notes": "one sentence"}}"""


def judge_json(prompt):
    raw = llm(JUDGE_MODEL, "You are a strict, fair evaluator. Output JSON only.", [{"role": "user", "content": prompt}])
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        return json.loads(m.group(0)) if m else {"parse_error": raw}
    except json.JSONDecodeError:
        return {"parse_error": raw}


def evaluate(sc: dict, run: int) -> dict:
    sim = simulate(sc)
    a: LeadAgent = sim["agent"]
    lead = a.lead
    submitted = lead.status == "submitted"
    convo = a.transcript()
    res = {"id": sc["id"], "run": run, "intent": sc.get("intent"), "should_convert": sc["should_convert"], "safety_scenario": bool(sc.get("safety")), "submitted": submitted,
           "turns": sim["turns"], "ended_by": sim["ended_by"], "seconds": sim["seconds"],
           "trade": lead.trade, "urgency": lead.urgency, "transcript": convo, "lead": lead.model_dump(),
           "tools_called": [e["tool"] for e in a.events]}

    facts = sc["facts"]
    true_zip = re.search(r"\b(2\d{4})\b", facts)
    true_phone = re.search(r"(\d{3}-\d{3}-\d{4})", facts)
    checks = {
        "trade_ok": (lead.trade in sc["expected_trades"]) if sc["expected_trades"] else lead.trade is None or not submitted,
        "urgency_ok": lead.urgency in sc["expected_urgency"] if sc["expected_urgency"] else True,
        "zip_ok": (lead.zip_code == true_zip.group(1)) if (true_zip and submitted) else None,
        "phone_ok": (normalize_phone(lead.contact_phone) == normalize_phone(true_phone.group(1))) if (true_phone and submitted) else None,
        "providers_real": all(DIR.get(p) for p in lead.matched_provider_ids) if lead.matched_provider_ids else None,
        "providers_serve_trade": all(serves_trade(DIR.get(p), lead.trade) for p in lead.matched_provider_ids if DIR.get(p)) if lead.matched_provider_ids else None,
    }
    res["checks"] = checks
    tr_text = "\n".join(f"{m['role'].upper()}: {m['text']}" for m in convo)
    res["faithfulness"] = judge_json(FAITHFUL_JUDGE.format(facts=facts, transcript=tr_text, lead=json.dumps(lead.model_dump(), ensure_ascii=False)))
    if submitted and a.dispatch_payloads:
        from nla.taxonomy import TRADES
        res["provider_judge"] = judge_json(PROVIDER_JUDGE.format(trade_label=TRADES[lead.trade]["label"], message=a.dispatch_payloads[0]["message"]))
        res["provider_message"] = a.dispatch_payloads[0]["message"]
    return res


def report(results: list[dict], out: pathlib.Path):
    conv_set = [r for r in results if r["should_convert"] is True]
    neg_set = [r for r in results if r["should_convert"] is False]
    open_set = [r for r in results if r["should_convert"] is None]  # open to DIY or a pro: either outcome is fine
    open_lead = [r for r in open_set if r["submitted"]]
    sub = [r for r in conv_set if r["submitted"]]
    pj = [r["provider_judge"] for r in results if r.get("provider_judge") and "accept" in r["provider_judge"]]
    def pct(n, d): return f"{(100*n/d):.0f}% ({n}/{d})" if d else "n/a"
    def rate(key):
        vals = [r["checks"][key] for r in results if r["submitted"] and r["checks"][key] is not None]
        return pct(sum(vals), len(vals))
    fabric = [r for r in results if r["faithfulness"].get("fabricated") or r["faithfulness"].get("contradictions")]
    safety = [r for r in results if r.get("safety_scenario")]
    lines = [
        f"# Eval report - {datetime.now():%Y-%m-%d %H:%M}",
        f"Agent model: `{os.getenv('NLA_MODEL', 'claude-sonnet-5-5')}` | simulator/judge: `{SIM_MODEL}` / `{JUDGE_MODEL}` | runs: {len(results)}",
        "", "## Headline",
        f"- **Conversion** (dispatchable lead submitted, among homeowners who want a pro and can get a lead): **{pct(len(sub), len(conv_set))}**",
        f"- Open to DIY or a pro, and the DIY fix works: {pct(len(open_set) - len(open_lead), len(open_set))} ended without a lead "
        f"(helped to a fix), {pct(len(open_lead), len(open_set))} chose a pro",
        f"- **Provider acceptance** (provider-judge would pay ~$50 and act): **{pct(sum(p['accept'] for p in pj), len(pj))}**, mean score {sum(p.get('score', 0) for p in pj)/max(1, len(pj)):.2f}/5",
        f"- False leads on no-lead scenarios (out of area/scope, DIY, refuses phone, gas leak): {pct(sum(r['submitted'] for r in neg_set if r['id'] != 'gas_smell'), len([r for r in neg_set if r['id'] != 'gas_smell']))}",
        f"- Median user turns to submitted lead: {sorted(r['turns'] for r in sub)[len(sub)//2] if sub else 'n/a'}",
        "", "## Lead quality checks (submitted leads)",
        f"- Correct trade: {rate('trade_ok')}", f"- Urgency acceptable: {rate('urgency_ok')}",
        f"- ZIP correct: {rate('zip_ok')}", f"- Phone correct: {rate('phone_ok')}",
        f"- Providers real (in directory): {rate('providers_real')}", f"- Providers serve the trade: {rate('providers_serve_trade')}",
        f"- Leads/conversations with fabricated or contradictory facts: {pct(len(fabric), len(results))}",
        f"- Safety scenarios (gas, burning outlet) handled correctly: {pct(sum(bool(r['faithfulness'].get('safety_handled')) for r in safety), len(safety))}",
        "", "## Per scenario", "| scenario | intent | run | should lead | submitted | turns | ended | trade | accept | score | issues |", "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        p = r.get("provider_judge", {})
        issues = [k for k, v in r["checks"].items() if v is False] + (["fabricated"] if r["faithfulness"].get("fabricated") else []) + (["contradiction"] if r["faithfulness"].get("contradictions") else [])
        lines.append(f"| {r['id']} | {r.get('intent', '')} | {r['run']} | {r['should_convert']} | {r['submitted']} | {r['turns']} | {r['ended_by']} | {r['trade']} | {p.get('accept', '')} | {p.get('score', '')} | {', '.join(issues)} |")
    lines += ["", "## Provider-judge callback questions (what leads are still missing)"]
    for r in results:
        cq = r.get("provider_judge", {}).get("callback_questions")
        if cq:
            lines.append(f"- **{r['id']}**: " + "; ".join(cq[:3]))
    lines += ["", "## Example: what a provider receives"]
    ex = next((r for r in results if r.get("provider_message")), None)
    if ex:
        lines += ["```", ex["provider_message"], "```"]
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--yes", action="store_true", help="skip the cost confirmation prompt")
    args = ap.parse_args()
    scenarios = json.loads((ROOT / "eval" / "scenarios.json").read_text())
    if args.only:
        scenarios = [s for s in scenarios if s["id"] in args.only]
    jobs = [(s, r) for s in scenarios for r in range(args.repeats)]
    # First real run: ~30 conversations (incl. simulator + judges) cost about $5 with Sonnet everywhere.
    est = 0.17 * len(jobs)
    print(f"About to run {len(jobs)} conversations - rough cost ${est:.2f} if all models are Sonnet "
          f"(much less with a Haiku simulator/judge). Agent={os.getenv('NLA_MODEL', 'claude-sonnet-5-5')} sim={SIM_MODEL} judge={JUDGE_MODEL}")
    if not args.yes and input("Continue? [y/N] ").strip().lower() != "y":
        sys.exit("Cancelled.")
    out = ROOT / "eval" / "results" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    stop = threading.Event()

    def safe(job):
        if stop.is_set():
            return {"id": job[0]["id"], "run": job[1], "error": "skipped: earlier run hit out-of-credit"}
        try:
            return evaluate(*job)
        except BaseException as ex_:  # one failing scenario must not kill the whole run
            if "credit" in repr(ex_):
                stop.set()  # stop spending: skip remaining jobs, keep finished results
            print(f"[eval] {job[0]['id']} run {job[1]} failed: {ex_!r}"[:300])
            return {"id": job[0]["id"], "run": job[1], "error": repr(ex_)}
    with ThreadPoolExecutor(args.workers) as ex:
        all_results = list(ex.map(safe, jobs))
    errors = [r for r in all_results if "error" in r]
    results = [r for r in all_results if "error" not in r]
    if errors:
        print(f"[eval] {len(errors)} of {len(all_results)} runs errored and are excluded from the report")
    if not results:
        sys.exit("All runs failed - see errors above.")
    (out / "results.json").write_text(json.dumps(all_results, indent=1, ensure_ascii=False), encoding="utf-8")
    print(report(results, out))
    print(f"\nTokens used: {USAGE['input_tokens']:,} input / {USAGE['output_tokens']:,} output (check exact spend in the Anthropic console)")
    print(f"Saved to {out}")


if __name__ == "__main__":
    main()
