"""The conversational lead agent: Claude + three tools (update_lead, search_providers, submit_lead).

State lives server-side in a Lead object; the model can only change it through tools, and
submission is gated by the deterministic `dispatch_gaps` check, so a lead can't be "submitted"
with missing contact, an unconfirmed summary, or a provider that wasn't returned by search.
"""
from __future__ import annotations

import json
import os
import pathlib
from typing import Any

from .lead import Lead, dispatch_gaps, provider_facing_text
from .providers import ProviderDirectory, public_view
from .ranking import CONFIGS, Need, RankConfig, Ranker
from .taxonomy import JOBS, ROUTING_PLAYBOOK, SAFETY_RULES, TRADES

DEFAULT_MODEL = os.getenv("NLA_MODEL", "claude-sonnet-5-5")
# Hybrid ranking by default. The LLM rerank scores higher in the ranking eval but adds ~3 s to the turn
# that shows providers, so it is opt-in: NLA_RERANK=1.
DEFAULT_RANK = CONFIGS["v5_hybrid+rerank" if os.getenv("NLA_RERANK") == "1" else "v4_hybrid"]
LEADS_DIR = pathlib.Path(__file__).resolve().parent.parent / "leads"
APP_NOTE = "[App event, not typed by the user] "  # prefix for app_notes; hidden from the transcript

TRADE_LINES = "\n".join(f"- {k}: {v['covers']}. Key detail: {v['key_detail']}." for k, v in TRADES.items())

SYSTEM_PROMPT = f"""You are Nearby, a home-repair assistant for Durham, NC. People arrive stressed and vague
("water in my basement, don't know who to call"). Your job: understand the problem well enough to
route it to the right kind of pro, give genuinely useful immediate guidance, and - if they want help -
produce a request a real local business would happily act on.

# How to run the conversation
1. SAFETY FIRST. If anything below applies, lead with the safety step in one or two sentences.
{SAFETY_RULES}
2. Be useful before asking for anything: in 1-2 sentences say what's likely going on and one thing they
   can do right now (e.g. move belongings off the floor, shut the water valve, photograph damage for insurance).
2b. A PRO ONLY WHEN THEY ASK. The person decides whether to hire someone, not you. Until they explicitly say they
   want a pro - in their own words ("can you find someone", "I'd rather get someone in", a clear "yes" to your offer)
   or by tapping "Find me a pro now" in the app - do not start pro intake (ZIP, ownership, contact), do not call
   search_providers, and do not talk as if it's decided ("To find the right people, I need..."). Instead, help:
   - Simple jobs people often fix themselves (slow or clogged drain, running toilet, GFCI outlet, dirty AC filter,
     tripped breaker): give 1-3 concrete safe steps, then ask ONE choice question: "Want to try that first, or would
     you rather I find a pro?"
   - If a DIY step didn't work: say what that tells you, offer the next safe step if there is one (or say plainly why
     it now likely needs a pro), and ask again: "Want to try that, or shall I find you a pro?" A failed attempt is
     not a request for a pro.
   - Emergencies and hazards (active flooding, gas, sparks, sewage, no heat in freezing weather): safety steps first,
     say clearly that this needs a pro today, and ask in the same message: "Want me to find a 24/7 company now?"
   When they say yes, call update_lead(wants_pro=true) and continue with intake. search_providers refuses to run
   before that. If they fix it themselves, that's a good outcome; don't push a lead. Record what they tried in tried_already.
3. Ask ONE question per turn - the single question that most changes who should come out
   (see routing playbook). Two short questions are OK only if they're naturally paired ("What's your ZIP, and do you own the home?").
4. Never ask what you can infer. "Last night", "flooding", "no heat in January" => urgency is obvious.
   A basement => it's a house. Record inferred values with update_lead.
   But do NOT guess urgency when it isn't obvious (a slow drip, a damp wall): ask "How soon do you need
   someone?" paired with another question. Never default to within_24h.
5. Order of intake (once they want a pro): routing detail -> urgency (if not obvious) -> ZIP -> call search_providers and show
   the 2-3 matches with a one-line reason each -> ownership (own / rent) -> name + best phone + call-or-text,
   asked together with explicit consent ("OK to share your name and number with these pros so they can contact you?").
   Ask for contact details only AFTER you've shown value (diagnosis + matched pros).
   Once, before asking for contact details, ask ONE combined "so the pro comes prepared" question covering
   the trade's key detail (see Trades below) that you don't already know - e.g. for HVAC "roughly how old is the
   system, and is the indoor fan still blowing?". Keep it optional ("if you know"). This is what providers
   otherwise have to call back about; put the answers in problem_summary.
6. Before submitting, show a short summary of the request in the user's own facts and ask "Send this?".
   Only after a clear yes: update_lead(user_confirmed_summary=true) then submit_lead.
7. Aim to get to a submitted lead in about 5-7 user turns. Don't pad.

# Routing
Trades (use these exact ids):
{TRADE_LINES}
Playbook for ambiguous cases:
{ROUTING_PLAYBOOK}
If the issue needs two trades (e.g. standing water now AND it seeps in every rain), set trade to the
urgent one and secondary_trade to the other, and say so.

# Honesty rules (non-negotiable)
- Only recommend providers returned by search_providers. Never invent a business, phone number, price quote, or availability.
- Provider info comes from public Google Business listings and each provider's own website; you have NOT verified
  licenses or insurance (a license number shown on a provider's site is their claim, not a verification). If asked, say so
  and tell them how to check (NC licensing boards: plumbing/HVAC at nclicensing.org, electrical at ncbeec.org,
  general contractors at nclbgc.org).
- If you give a price, give it only as a rough typical range, say it's not a quote, and that the pro will confirm on site.
- The problem_summary and user_facts must only contain things the user said or confirmed. Unknowns stay unknown - never fill gaps with guesses.
- safety_flags record only hazards the user confirmed (e.g. "water reached the furnace"). Your own precautions
  ("stay out of the water if it's near outlets") are advice, not facts about the home - don't log them as flags.
- If the ZIP is outside the Durham area, say we don't cover it yet; don't fake a match.
- Out of scope (cars, medical, legal, non-home): say briefly you only handle home services and don't create a lead.
- If they just want DIY help, help them properly; offer a pro once, don't push.
- If they decline to share a phone number, respect it: give them the matched pros' numbers so they can call directly.

# Style
Warm, calm, plain words, short (usually under 80 words). Reply in the user's language and stay in it
(including the summary). No markdown headers; simple line breaks and short lists are fine.

# Tools
- update_lead: call whenever you learn or infer something. Keep problem_summary current: concrete, 1-3 sentences, what/where/since when/what's been tried.
  The pro reads it, so write it as a plain job description ("Bathtub drains slowly; hair removed and plunged, still slow"),
  never "User said..." or "The homeowner...". The same goes for every field the pro sees (tried_already, availability,
  budget): plain facts, e.g. tried_already "Pulled hair from the stopper and plunged; still slow", not "User said they tried".
  Don't repeat what's tried in both problem_summary and tried_already; keep it in tried_already.
- search_providers: call once trade and ZIP are known (re-call if trade or the specific job changes). Pass job_tags:
  the 1-2 specific jobs from the list that match what the user described; they decide which pros rank first. It records the
  matched provider ids on the lead. Each match's "why" is grounded in its listing or website; you may paraphrase it, never add to it.
- submit_lead: only after explicit confirmation. If it returns gaps, fix them (usually by asking the user) and retry.
  The user chooses which matched pros get the request (all by default). If they name only some ("just send it to
  Chamberlain"), pass those provider_ids; never tell them it must go to all three. They may also untick pros in the app.
"""

TOOLS = [
    {
        "name": "update_lead",
        "description": "Record facts learned or reasonably inferred from the conversation. Only pass fields that changed. Returns the current lead and remaining dispatch gaps.",
        "input_schema": {
            "type": "object",
            "properties": {
                "trade": {"type": "string", "enum": list(TRADES)},
                "secondary_trade": {"type": "string", "enum": list(TRADES)},
                "problem_summary": {"type": "string"},
                "user_facts": {"type": "array", "items": {"type": "string"}, "description": "New facts the user stated, short phrases"},
                "tried_already": {"type": "string"},
                "urgency": {"type": "string", "enum": ["emergency", "within_24h", "within_few_days", "flexible"]},
                "availability": {"type": "string"},
                "property_type": {"type": "string"},
                "authority": {"type": "string", "enum": ["owner", "renter_landlord_approved", "renter_needs_approval", "property_manager", "unknown"]},
                "zip_code": {"type": "string"},
                "address_hint": {"type": "string"},
                "budget": {"type": "string"},
                "safety_flags": {"type": "array", "items": {"type": "string"}},
                "wants_pro": {"type": "boolean", "description": "true only after the user explicitly asked for a pro or said yes to your offer"},
                "contact_name": {"type": "string"},
                "contact_phone": {"type": "string"},
                "contact_pref": {"type": "string", "enum": ["call", "text", "either"]},
                "consent_to_share": {"type": "boolean"},
                "user_confirmed_summary": {"type": "boolean"},
            },
        },
    },
    {
        "name": "search_providers",
        "description": "Find real, publicly listed Durham-area providers for this need. Ranks by whether their own website says they do "
                       "the specific job, relevance to the problem description on the lead, review strength, distance, and 24/7 availability "
                       "for emergencies. Returns up to 3 matches with reasons. Stores their ids on the lead.",
        "input_schema": {
            "type": "object",
            "properties": {
                "trade": {"type": "string", "enum": list(TRADES)},
                "job_tags": {"type": "array", "items": {"type": "string", "enum": list(JOBS)},
                             "description": "1-2 specific jobs the user needs, e.g. ['sump_pump'] or ['water_extraction', 'structural_drying']"},
                "zip_code": {"type": "string"},
                "emergency": {"type": "boolean", "description": "true if it needs someone today (boosts 24/7 providers)"},
            },
            "required": ["trade"],
        },
    },
    {
        "name": "submit_lead",
        "description": "Submit the lead to the matched providers the user chose. Fails with a list of gaps if the lead is not dispatchable yet.",
        "input_schema": {"type": "object", "properties": {
            "provider_ids": {"type": "array", "items": {"type": "string"},
                             "description": "Only if the user wants some of the matched pros, not all: their provider_id values"}}},
    },
]


class LeadAgent:
    def __init__(self, client: Any = None, directory: ProviderDirectory | None = None,
                 model: str = DEFAULT_MODEL, save_leads: bool = True, max_tool_rounds: int = 8,
                 rank_config: RankConfig = DEFAULT_RANK, ranker: Ranker | None = None):
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        self.client = client
        self.dir = ranker.dir if ranker else directory or ProviderDirectory()
        self.ranker = ranker or Ranker(self.dir)
        self.rank_config = rank_config
        self.model = model
        self.save_leads = save_leads
        self.max_tool_rounds = max_tool_rounds
        self.lead = Lead()
        self.messages: list[dict] = []
        self.events: list[dict] = []  # tool calls, for UI/eval transparency
        self.returned_provider_ids: set[str] = set()
        self.last_matches: list[dict] = []
        self.dispatch_payloads: list[dict] = []
        self.usage = {"input_tokens": 0, "output_tokens": 0}
        self.app_notes: list[str] = []  # things the user did in the app (not in chat), told to the model on the next turn

    def usage_obj(self):
        from types import SimpleNamespace
        return SimpleNamespace(**self.usage)

    # ----- tools -----
    def _tool(self, name: str, args: dict) -> dict:
        if name == "update_lead":
            try:
                changed = self.lead.patch(**args)
            except Exception as e:
                return {"error": f"invalid update: {e}"}
            return {"changed": changed, "lead": self._lead_brief(), "dispatch_gaps": dispatch_gaps(self.lead, self.returned_provider_ids)}
        if name == "search_providers":
            trade = args.get("trade")
            zip_code = args.get("zip_code") or self.lead.zip_code
            emergency = bool(args.get("emergency", self.lead.urgency == "emergency"))
            if trade not in TRADES:
                return {"providers": [], "note": f"Unknown trade {trade!r}."}
            if not self.lead.wants_pro:
                return {"providers": [], "error": "The user hasn't asked for a pro. Help them and ask whether they want one; "
                                                  "after a clear yes, call update_lead(wants_pro=true), then search."}
            need = Need(trade=trade, zip_code=zip_code, emergency=emergency, secondary_trade=self.lead.secondary_trade,
                        job_tags=[t for t in args.get("job_tags", []) if t in JOBS][:2],
                        text=" ".join(filter(None, [self.lead.problem_summary, *self.lead.user_facts])))
            matches = self.ranker.rank(need, self.rank_config)
            views = [public_view(m) for m in matches]
            self.returned_provider_ids |= {v["provider_id"] for v in views}
            self.lead.matched_provider_ids = [v["provider_id"] for v in views]
            self.last_matches = views
            if not views:
                return {"providers": [], "note": "No providers on file for this trade. Tell the user honestly."}
            return {"providers": views, "note": "Show these by name with phone and a one-line reason drawn from 'why'. "
                                                "Data from public Google listings and the providers' own websites; licenses not verified."}
        if name == "submit_lead":
            if args.get("provider_ids"):
                self.select_providers(args["provider_ids"])
            gaps = dispatch_gaps(self.lead, self.returned_provider_ids)
            if gaps:
                return {"submitted": False, "dispatch_gaps": gaps}
            self.lead.status = "submitted"
            self.dispatch_payloads = [
                {"provider_id": pid, "provider_name": self.dir.get(pid)["name"], "provider_phone": self.dir.get(pid)["phone"],
                 "message": provider_facing_text(self.lead, self.dir.get(pid)["name"])}
                for pid in self.lead.matched_provider_ids]
            if self.save_leads:
                LEADS_DIR.mkdir(exist_ok=True)
                (LEADS_DIR / f"{self.lead.lead_id}.json").write_text(json.dumps(
                    {"lead": self.lead.model_dump(), "dispatch": self.dispatch_payloads, "transcript": self.transcript()}, indent=2, ensure_ascii=False))
            return {"submitted": True, "lead_id": self.lead.lead_id,
                    "sent_to": [d["provider_name"] for d in self.dispatch_payloads],
                    "note": "Tell the user it's sent, who it went to, that they'll be contacted by call/text, and give the lead id."}
        return {"error": f"unknown tool {name}"}

    def select_providers(self, provider_ids: list[str], from_app: bool = False) -> list[str]:
        """Narrow who receives the request to pros from the latest search (keeps the search order).

        from_app: the user ticked boxes in the app rather than saying it in chat, so tell the model next turn.
        """
        shown = [m["provider_id"] for m in self.last_matches]
        chosen = [p for p in shown if p in set(provider_ids)]
        if chosen and self.lead.status == "draft" and chosen != self.lead.matched_provider_ids:
            self.lead.matched_provider_ids = chosen
            if from_app:
                names = [m["name"] for m in self.last_matches if m["provider_id"] in chosen]
                self.app_notes.append(f"The user changed their selection in the app: the request will go only to {', '.join(names)}.")
        return self.lead.matched_provider_ids

    # ----- persistence: everything needed to resume a conversation after a restart -----
    def to_state(self) -> dict:
        return {"messages": self.messages, "lead": self.lead.model_dump(), "events": self.events,
                "returned_provider_ids": sorted(self.returned_provider_ids), "last_matches": self.last_matches,
                "dispatch_payloads": self.dispatch_payloads, "usage": self.usage, "app_notes": self.app_notes}

    def load_state(self, s: dict) -> "LeadAgent":
        self.messages, self.events = s["messages"], s.get("events", [])
        self.lead = Lead.model_validate(s["lead"])
        self.returned_provider_ids = set(s.get("returned_provider_ids", []))
        self.last_matches, self.dispatch_payloads = s.get("last_matches", []), s.get("dispatch_payloads", [])
        self.usage = s.get("usage", self.usage)
        self.app_notes = s.get("app_notes", [])
        return self

    def _lead_brief(self) -> dict:
        return {k: v for k, v in self.lead.model_dump().items() if v not in (None, [], False, "unknown") and k not in ("created_at",)}

    # ----- conversation -----
    def reply(self, user_text: str) -> str:
        last = self.messages[-1] if self.messages else None
        notes = [{"type": "text", "text": APP_NOTE + n} for n in self.app_notes]
        self.app_notes = []
        if last and last["role"] == "user" and isinstance(last["content"], list):
            # previous turn hit the tool-round cap; attach the new text to the pending tool results
            last["content"] += notes + [{"type": "text", "text": user_text}]
        else:
            self.messages.append({"role": "user", "content": notes + [{"type": "text", "text": user_text}] if notes else user_text})
        text_out = ""
        for _ in range(self.max_tool_rounds):
            resp = self.client.messages.create(model=self.model, max_tokens=1024, system=SYSTEM_PROMPT,
                                               tools=TOOLS, messages=self.messages)
            u = getattr(resp, "usage", None)
            if u is not None:
                self.usage["input_tokens"] += getattr(u, "input_tokens", 0) or 0
                self.usage["output_tokens"] += getattr(u, "output_tokens", 0) or 0
            # Keep every block exactly as returned (thinking blocks need their signature to be sent back);
            # only drop None-valued fields.
            content = [b.model_dump(exclude_none=True) if hasattr(b, "model_dump") else dict(b) for b in resp.content]
            self.messages.append({"role": "assistant", "content": content})
            texts = [b["text"] for b in content if b["type"] == "text"]
            if texts:
                text_out = "\n".join(t for t in texts if t.strip())
            tool_uses = [b for b in content if b["type"] == "tool_use"]
            if not tool_uses:
                break
            results = []
            for tu in tool_uses:
                out = self._tool(tu["name"], tu.get("input") or {})
                self.events.append({"tool": tu["name"], "input": tu.get("input"), "output": out})
                results.append({"type": "tool_result", "tool_use_id": tu["id"], "content": json.dumps(out, ensure_ascii=False)})
            self.messages.append({"role": "user", "content": results})
        return text_out

    def transcript(self) -> list[dict]:
        out = []
        for m in self.messages:
            if isinstance(m["content"], str):
                out.append({"role": m["role"], "text": m["content"]})
            else:
                t = " ".join(b.get("text", "") for b in m["content"]
                             if b.get("type") == "text" and not b.get("text", "").startswith(APP_NOTE)).strip()
                if t:
                    out.append({"role": m["role"], "text": t})
        return out
