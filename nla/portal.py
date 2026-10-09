"""Homeowner and pro portals: what's stored (SQLite) and the rules that connect the two sides.

  conversations  one row per chat; the agent's full state, so a chat resumes after a server restart
  requests       one row per submitted lead (status: open / closed)
  deliveries     one row per (lead, pro): sent -> viewed -> accepted | declined (+ reason)
  pro_accounts   a pro's claimed or newly registered listing; layered over the provider directory

Privacy rule: a pro sees the job brief when a lead reaches them, but the homeowner's full name and phone
only after that pro accepts. The pro API never returns the raw lead before that. A pro's own phone is
public (it's on their Google listing), so homeowners always see it.

Decline reasons are the real lead-quality signal (a stand-in for "transaction-backed reputation"):
they say whether the lead or the match was wrong, which an LLM judge can only guess at.
"""
from __future__ import annotations

import json
import os
import pathlib
import sqlite3
import threading
import time
import uuid

from .lead import Lead, contact_pref_text, provider_facing_text
from .providers import ProviderDirectory
from .ranking import zip_point
from .taxonomy import JOBS, TRADES

DB_PATH = pathlib.Path(os.getenv("NLA_DB", pathlib.Path(__file__).resolve().parent.parent / "data" / "app.db"))

LICENSE_BOARDS = {
    "plumbing_hvac": "NC Board of Examiners of Plumbing, Heating & Fire Sprinkler Contractors",
    "electrical": "NC Board of Examiners of Electrical Contractors",
    "general_contractor": "NC Licensing Board for General Contractors",
    "pest": "NC Structural Pest Control & Pesticides Division",
    "none": "No state license needed for my work",
}
DECLINE_REASONS = {"not_my_trade": "Not my trade", "too_far": "Too far away", "too_small": "Job too small",
                   "fully_booked": "Fully booked", "not_enough_info": "Not enough information", "other": "Other"}
# What the homeowner sees for each pro (decline reasons stay with Nearby)
OWNER_DELIVERY = {"sent": "Sent, waiting", "viewed": "Viewed your request", "accepted": "Accepted: they have your number",
                  "declined": "Not available"}

SCHEMA = """
create table if not exists conversations (id text primary key, owner text, title text, created_at real, updated_at real, state text);
create table if not exists requests (lead_id text primary key, conversation_id text, owner text, status text, created_at real, lead text);
create table if not exists deliveries (lead_id text, provider_id text, status text, reason text, updated_at real,
                                       primary key (lead_id, provider_id));
create table if not exists pro_accounts (provider_id text primary key, data text, created_at real, updated_at real);
"""


def request_status(deliveries: list[dict], closed: bool) -> str:
    if closed:
        return "closed"
    s = [d["status"] for d in deliveries]
    if "accepted" in s:
        return "matched"
    if s and all(x == "declined" for x in s):
        return "no_match"
    return "viewed" if "viewed" in s else "sent"


class Portal:
    def __init__(self, path: pathlib.Path | str = DB_PATH):
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.db.executescript(SCHEMA)

    def _q(self, sql: str, args: tuple = (), one: bool = False):
        with self.lock:
            cur = self.db.execute(sql, args)
            self.db.commit()
            rows = [dict(r) for r in cur.fetchall()]
        return (rows[0] if rows else None) if one else rows

    # ---------- conversations ----------
    def save_conversation(self, cid: str, owner: str, title: str, state: dict) -> None:
        now = time.time()
        self._q("insert into conversations values (?,?,?,?,?,?) on conflict(id) do update set "
                "title=excluded.title, updated_at=excluded.updated_at, state=excluded.state",
                (cid, owner, title, now, now, json.dumps(state, ensure_ascii=False)))

    def conversation(self, cid: str) -> dict | None:
        row = self._q("select * from conversations where id=?", (cid,), one=True)
        if row:
            row["state"] = json.loads(row["state"])
        return row

    def conversations(self, owner: str) -> list[dict]:
        rows = self._q("select id, title, updated_at, json_extract(state, '$.lead.status') as lead_status, "
                       "json_extract(state, '$.lead.lead_id') as lead_id from conversations where owner=? "
                       "order by updated_at desc", (owner,))
        for r in rows:
            req = self._q("select * from requests where lead_id=?", (r["lead_id"],), one=True)
            r["status"] = self._status(req) if req else ("draft" if r["lead_status"] == "draft" else r["lead_status"])
        return rows

    # ---------- requests & deliveries ----------
    def record_submission(self, cid: str, owner: str, lead: dict, provider_ids: list[str]) -> None:
        if self._q("select 1 from requests where lead_id=?", (lead["lead_id"],), one=True):
            return
        now = time.time()
        self._q("insert into requests values (?,?,?,?,?,?)", (lead["lead_id"], cid, owner, "open", now, json.dumps(lead)))
        for pid in provider_ids:
            self._q("insert or ignore into deliveries values (?,?,?,?,?)", (lead["lead_id"], pid, "sent", None, now))

    def _deliveries(self, lead_id: str) -> list[dict]:
        return self._q("select * from deliveries where lead_id=?", (lead_id,))

    def _status(self, req: dict) -> str:
        return request_status(self._deliveries(req["lead_id"]), req["status"] == "closed")

    def requests_for_owner(self, owner: str, directory: ProviderDirectory) -> list[dict]:
        out = []
        for req in self._q("select * from requests where owner=? order by created_at desc", (owner,)):
            lead = json.loads(req["lead"])
            pros = []
            for d in self._deliveries(req["lead_id"]):
                p = directory.get(d["provider_id"]) or {"name": d["provider_id"], "phone": ""}
                pros.append({"provider_id": d["provider_id"], "name": p["name"], "phone": p["phone"],
                             "status": d["status"], "label": OWNER_DELIVERY[d["status"]]})
            out.append({"lead_id": req["lead_id"], "conversation_id": req["conversation_id"], "created_at": req["created_at"],
                        "status": self._status(req), "trade": TRADES.get(lead.get("trade"), {}).get("label"),
                        "summary": lead.get("problem_summary"), "urgency": lead.get("urgency"), "zip": lead.get("zip_code"),
                        "pros": pros})
        return out

    def close_request(self, lead_id: str, owner: str) -> None:
        self._q("update requests set status='closed' where lead_id=? and owner=?", (lead_id, owner))

    # ---------- pro side ----------
    def save_account(self, provider_id: str | None, data: dict) -> str:
        pid = provider_id or "pro-" + uuid.uuid4().hex[:10]
        now = time.time()
        self._q("insert into pro_accounts values (?,?,?,?) on conflict(provider_id) do update set data=excluded.data, "
                "updated_at=excluded.updated_at", (pid, json.dumps(data, ensure_ascii=False), now, now))
        return pid

    def account(self, pid: str) -> dict | None:
        row = self._q("select * from pro_accounts where provider_id=?", (pid,), one=True)
        return json.loads(row["data"]) if row else None

    def accounts(self) -> dict[str, dict]:
        return {r["provider_id"]: json.loads(r["data"]) for r in self._q("select * from pro_accounts order by updated_at desc")}

    def leads_for_pro(self, pid: str, provider_name: str) -> list[dict]:
        out = []
        rows = self._q("select d.status, d.reason, d.updated_at, r.lead, r.created_at, r.status as req_status from deliveries d "
                       "join requests r on r.lead_id=d.lead_id where d.provider_id=? order by r.created_at desc", (pid,))
        for r in rows:
            lead = Lead.model_validate(json.loads(r["lead"]))
            accepted = r["status"] == "accepted"
            item = {"lead_id": lead.lead_id, "status": r["status"], "reason": r["reason"], "received_at": r["created_at"],
                    "homeowner_closed": r["req_status"] == "closed", "trade": TRADES.get(lead.trade or "", {}).get("label"),
                    "urgency": lead.urgency, "zip": lead.zip_code,
                    "brief": provider_facing_text(lead, provider_name, reveal_contact=accepted)}
            if accepted:  # matched: now the pro gets the contact
                item["contact"] = {"name": lead.contact_name, "phone": lead.contact_phone, "prefers": contact_pref_text(lead.contact_pref)}
            out.append(item)
        return out

    def set_delivery(self, lead_id: str, pid: str, status: str, reason: str | None = None) -> str:
        """Returns "ok", or why not: "not_found", "closed" (the homeowner closed the request), "already_answered".

        Enforced here, not just in the page: a pro can't accept a closed request (accepting reveals the
        homeowner's contact), and an answer is final, so accept-after-decline can't reveal it either.
        """
        cur = self._q("select d.status, r.status as req_status from deliveries d join requests r on r.lead_id=d.lead_id "
                      "where d.lead_id=? and d.provider_id=?", (lead_id, pid), one=True)
        if not cur:
            return "not_found"
        if status == "viewed" and cur["status"] != "sent":
            return "ok"  # viewing never downgrades an answer
        if status in ("accepted", "declined"):
            if cur["status"] == status:
                return "ok"  # same answer twice (a double click)
            if cur["status"] in ("accepted", "declined"):
                return "already_answered"
            if cur["req_status"] == "closed":
                return "closed"
        self._q("update deliveries set status=?, reason=?, updated_at=? where lead_id=? and provider_id=?",
                (status, reason, time.time(), lead_id, pid))
        return "ok"

    def decline_stats(self) -> dict[str, int]:
        return {r["reason"]: r["n"] for r in self._q("select reason, count(*) n from deliveries where status='declined' group by reason")}


# ---------- pro accounts layered over the directory ----------
def apply_accounts(directory: ProviderDirectory, accounts: dict[str, dict]) -> ProviderDirectory:
    """A claimed listing's confirmed details override the scraped ones; a new registration becomes a provider.

    What the business says about itself (trades, jobs, hours, radius, license) is marked as self-reported;
    the license stays "submitted, not verified" until checked against the state board.
    """
    for pid, a in accounts.items():
        p = directory.get(pid)
        if p is None:
            pt = zip_point(a.get("zip"))
            p = {"id": pid, "name": a["name"], "phone": a["phone"], "trades": a.get("trades") or ["handyman"],
                 "city": a.get("city") or "Durham", "address": a.get("address"), "website": a.get("website"),
                 "lat": pt[0] if pt else None, "lng": pt[1] if pt else None, "google_rating": None, "google_reviews": None,
                 "emergency_24_7": None, "source_url": None, "data_source": "self_registered", "notes": "",
                 "maps_url": "https://www.google.com/maps/search/?api=1&query=" + f"{a['name']} {a.get('address') or ''}".replace(" ", "+"),
                 "profile": {"is_home_service_provider": True, "summary": "", "job_tags": [], "services_text": [],
                             "service_area": [], "emergency_service": "not_stated", "license_numbers": [], "site_chars": 0}}
            directory.providers.append(p)
            directory._by_id[pid] = p
        for k in ("name", "phone", "address", "website"):
            if a.get(k):
                p[k] = a[k]
        if a.get("trades"):
            p["trades"] = [t for t in a["trades"] if t in TRADES] or p["trades"]
        prof = dict(p.get("profile") or {"is_home_service_provider": True, "site_chars": 0})
        if a.get("job_tags") is not None:
            prof["job_tags"] = [t for t in a["job_tags"] if t in JOBS]
        if a.get("description"):
            prof["summary"] = a["description"]
        prof["is_home_service_provider"] = True  # the business confirmed it serves homeowners
        p["profile"] = prof
        if a.get("open_24_7") in (True, False):
            p["emergency_24_7"] = a["open_24_7"]
        if a.get("service_radius_km"):
            p["service_radius_km"] = float(a["service_radius_km"])
        if a.get("license_number"):
            p["license_number"] = a["license_number"]
            p["license_board"] = LICENSE_BOARDS.get(a.get("license_board", ""), a.get("license_board"))
        p["claimed"] = True
    return directory
