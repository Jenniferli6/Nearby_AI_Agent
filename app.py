"""Web app: homeowner chat at /, pro portal at /pro.

    python -m uvicorn app:app --port 8000

    http://localhost:8000          homeowner app
    http://localhost:8000/pro      pro portal
    http://localhost:8000/?debug=1 developer view: the homeowner app plus a card showing the lead JSON and the
                                   dispatch checks still failing, updated every turn (hidden from homeowners)

Homeowners are identified by a random id kept in the browser and pros pick their business: demo-level, no real login.
"""
import re
import threading
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from nla.agent import LeadAgent
from nla.lead import dispatch_gaps
from nla.portal import DECLINE_REASONS, LICENSE_BOARDS, Portal, apply_accounts
from nla.providers import ProviderDirectory, brand_key
from nla.ranking import Ranker
from nla.taxonomy import JOBS, TRADES

app = FastAPI()
app.mount("/static", StaticFiles(directory="web"), name="static")
PORTAL = Portal()
AGENTS: dict[str, LeadAgent] = {}
LOCK = threading.Lock()


def build_ranker(previous: Ranker | None = None) -> Ranker:
    r = Ranker(apply_accounts(ProviderDirectory(), PORTAL.accounts()), reuse_model_from=previous)
    r.index.warm()
    return r


STATE = {"ranker": build_ranker()}  # rebuilt when a pro claims or edits a listing

# Homeowner-facing wording for what a draft request still needs
GAP_TEXT = {"trade": "what kind of pro you need", "problem_summary": "a clear description of the problem",
            "urgency": "how soon you need someone", "zip_code": "your ZIP code", "contact_name": "your name",
            "contact_phone": "a phone number", "consent_to_share": "your OK to share your contact with the pros",
            "authority": "whether you own or rent", "matched_provider_ids": "matched pros",
            "user_confirmed_summary": "your final OK to send"}


def page(name: str) -> str:
    return open(f"web/{name}", encoding="utf-8").read()


@app.get("/", response_class=HTMLResponse)
def homeowner_page():
    return page("index.html")


@app.get("/pro", response_class=HTMLResponse)
def pro_page():
    return page("pro.html")


@app.get("/api/meta")
def meta():
    return {"trades": {k: v["label"] for k, v in TRADES.items()},
            "jobs": {t: [{"tag": k, "label": d} for k, (tt, d) in JOBS.items() if tt == t] for t in TRADES},
            "license_boards": LICENSE_BOARDS, "decline_reasons": DECLINE_REASONS}


# ---------------- homeowner ----------------
class ChatIn(BaseModel):
    owner: str
    text: str
    conversation_id: str | None = None
    wants_pro: bool = False  # sent by the "Find me a pro now" button: an explicit request, recorded before the model replies


class SelectIn(BaseModel):
    owner: str
    provider_ids: list[str]


class OwnerIn(BaseModel):
    owner: str


def agent_for(cid: str, owner: str, create: bool = False) -> LeadAgent:
    with LOCK:
        if cid in AGENTS:
            row = PORTAL.conversation(cid)
            if row and row["owner"] != owner:
                raise HTTPException(403)
            return AGENTS[cid]
        row = PORTAL.conversation(cid)
        if row is None and not create:
            raise HTTPException(404)
        if row and row["owner"] != owner:
            raise HTTPException(403)
        a = LeadAgent(ranker=STATE["ranker"])
        if row:
            a.load_state(row["state"])
        AGENTS[cid] = a
        return a


def title_for(a: LeadAgent) -> str:
    if a.lead.trade:
        what = (a.lead.problem_summary or "").split(".")[0][:48].rstrip(" ,;:-")
        return TRADES[a.lead.trade]["label"] + (f" · {what}" if what else "")
    first = next((m["text"] for m in a.transcript() if m["role"] == "user"), "New conversation")
    return first[:56]


def view(cid: str, owner: str, a: LeadAgent) -> dict:
    gaps = dispatch_gaps(a.lead, a.returned_provider_ids)
    request = next((r for r in PORTAL.requests_for_owner(owner, a.dir) if r["lead_id"] == a.lead.lead_id), None)
    return {"conversation_id": cid, "title": title_for(a), "transcript": a.transcript(), "lead": a.lead.model_dump(),
            "gaps": gaps, "missing": [GAP_TEXT.get(g.split(":")[0], g) for g in gaps],
            "matches": [dict(m, selected=m["provider_id"] in a.lead.matched_provider_ids) for m in a.last_matches],
            "request": request}


@app.post("/api/chat")
def chat(m: ChatIn):
    cid = m.conversation_id or uuid.uuid4().hex
    a = agent_for(cid, m.owner, create=True)
    if m.wants_pro:
        a.lead.wants_pro = True
    reply = a.reply(m.text)
    if a.lead.status == "submitted":
        PORTAL.record_submission(cid, m.owner, a.lead.model_dump(), a.lead.matched_provider_ids)
    PORTAL.save_conversation(cid, m.owner, title_for(a), a.to_state())
    return dict(view(cid, m.owner, a), reply=reply)


@app.get("/api/conversations")
def conversations(owner: str):
    return PORTAL.conversations(owner)


@app.get("/api/conversations/{cid}")
def conversation(cid: str, owner: str):
    return view(cid, owner, agent_for(cid, owner))


@app.post("/api/conversations/{cid}/select")
def select(cid: str, s: SelectIn):
    a = agent_for(cid, s.owner)
    a.select_providers(s.provider_ids, from_app=True)
    PORTAL.save_conversation(cid, s.owner, title_for(a), a.to_state())
    return view(cid, s.owner, a)


@app.get("/api/requests")
def requests(owner: str):
    sent = PORTAL.requests_for_owner(owner, STATE["ranker"].dir)
    drafts = []
    for c in PORTAL.conversations(owner):
        if c["status"] != "draft":
            continue
        a = agent_for(c["id"], owner)
        if a.lead.matched_provider_ids:  # got as far as matching pros, never sent: "finish your request"
            gaps = dispatch_gaps(a.lead, a.returned_provider_ids)
            drafts.append({"conversation_id": c["id"], "title": c["title"], "updated_at": c["updated_at"],
                           "summary": a.lead.problem_summary, "missing": [GAP_TEXT.get(g.split(":")[0], g) for g in gaps],
                           "pros": [m["name"] for m in a.last_matches if m["provider_id"] in a.lead.matched_provider_ids]})
    return {"requests": sent, "drafts": drafts}


@app.post("/api/requests/{lead_id}/close")
def close(lead_id: str, o: OwnerIn):
    PORTAL.close_request(lead_id, o.owner)
    return {"ok": True}


# ---------------- pro ----------------
class ClaimIn(BaseModel):
    provider_id: str | None = None
    name: str
    phone: str
    address: str | None = None
    zip: str | None = None
    website: str | None = None
    contact_name: str | None = None
    email: str | None = None
    trades: list[str]
    job_tags: list[str] = []
    description: str | None = None
    open_24_7: bool | None = None
    service_radius_km: float | None = None
    license_number: str | None = None
    license_board: str | None = None
    insured: bool | None = None


class LeadAction(BaseModel):
    action: str  # view | accept | decline
    reason: str | None = None


def listing(pid: str) -> dict:
    p = STATE["ranker"].dir.get(pid)
    if p is None:
        raise HTTPException(404)
    return p


@app.get("/api/pro/search")
def pro_search(q: str):
    """Find your business: by phone (any listed number) or by name."""
    d, digits = STATE["ranker"].dir, re.sub(r"\D", "", q)[-10:]
    claimed = PORTAL.accounts()
    hits = []
    for p in d.providers:
        phones = [re.sub(r"\D", "", x)[-10:] for x in [p.get("phone") or ""] + p.get("alt_phones", [])]
        if len(digits) >= 7 and any(digits in x for x in phones):
            hits.append((0, p))
        elif len(q.strip()) >= 3 and brand_key(q) and brand_key(q) in brand_key(p["name"]):
            hits.append((1, p))
    hits.sort(key=lambda h: (h[0], -(h[1].get("google_reviews") or 0)))
    return [{"provider_id": p["id"], "name": p["name"], "phone": p["phone"], "city": p.get("city"), "address": p.get("address"),
             "trades": [TRADES[t]["label"] for t in p["trades"]], "rating": p.get("google_rating"),
             "reviews": p.get("google_reviews"), "claimed": p["id"] in claimed} for _, p in hits[:8]]


@app.get("/api/pro/accounts")
def pro_accounts():
    return [{"provider_id": pid, "name": a["name"]} for pid, a in PORTAL.accounts().items()]


@app.get("/api/pro/{pid}")
def pro_listing(pid: str):
    p, a = listing(pid), PORTAL.account(pid) or {}
    pr = p.get("profile") or {}
    zips = re.findall(r"\b(\d{5})\b", p.get("address") or "")
    form = {"provider_id": pid, "name": p["name"], "phone": p["phone"], "address": p.get("address"), "zip": zips[-1] if zips else "",
            "website": p.get("website"), "trades": p["trades"], "job_tags": pr.get("job_tags", []), "description": pr.get("summary", ""),
            "open_24_7": p.get("emergency_24_7"), "service_radius_km": p.get("service_radius_km"),
            "license_number": p.get("license_number") or (pr.get("license_numbers") or [""])[0], "license_board": "",
            "insured": None, "contact_name": "", "email": ""}
    form.update({k: v for k, v in a.items() if v not in (None, "")})
    return {"form": form, "claimed": bool(a), "rating": p.get("google_rating"), "reviews": p.get("google_reviews"),
            "source": p.get("data_source"), "website_evidence": pr.get("evidence", [])}


@app.post("/api/pro/claim")
def pro_claim(c: ClaimIn):
    if not c.trades:
        raise HTTPException(400, "Pick at least one trade")
    if c.provider_id:
        listing(c.provider_id)
    pid = PORTAL.save_account(c.provider_id, c.model_dump(exclude={"provider_id"}))
    with LOCK:
        STATE["ranker"] = build_ranker(STATE["ranker"])  # their confirmed details count in matching right away
    return {"provider_id": pid}


@app.get("/api/pro/{pid}/leads")
def pro_leads(pid: str):
    return {"leads": PORTAL.leads_for_pro(pid, listing(pid)["name"]), "decline_reasons": DECLINE_REASONS}


@app.post("/api/pro/{pid}/leads/{lead_id}")
def pro_lead_action(pid: str, lead_id: str, x: LeadAction):
    status = {"view": "viewed", "accept": "accepted", "decline": "declined"}.get(x.action)
    if status is None or (status == "declined" and x.reason not in DECLINE_REASONS):
        raise HTTPException(400, "action must be view, accept, or decline with a reason")
    result = PORTAL.set_delivery(lead_id, pid, status, x.reason if status == "declined" else None)
    if result == "not_found":
        raise HTTPException(404)
    if result == "closed":
        raise HTTPException(409, "The homeowner closed this request.")
    if result == "already_answered":
        raise HTTPException(409, "You already answered this lead.")
    return {"ok": True}
