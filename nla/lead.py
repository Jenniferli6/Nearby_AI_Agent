"""Lead schema and the definition of a *dispatchable* lead.

A lead is dispatchable when a real provider could act on it without calling back just to find out
what the job is:
  1. a trade from the taxonomy (routes it to the right kind of business)
  2. a concrete problem summary (what, where in the house, what's been tried)
  3. urgency + timing
  4. a ZIP inside the served area
  5. a reachable contact (name + valid US phone) with explicit consent to share
  6. the person can authorise the work (owner, or renter with landlord approval noted)
  7. at least one real matched provider for that trade
  8. the user confirmed the summary before submission
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .taxonomy import DURHAM_AREA_ZIPS, TRADES

Urgency = Literal["emergency", "within_24h", "within_few_days", "flexible"]
Authority = Literal["owner", "renter_landlord_approved", "renter_needs_approval", "property_manager", "unknown"]


class Lead(BaseModel):
    lead_id: str = Field(default_factory=lambda: "L-" + uuid.uuid4().hex[:8].upper())
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    trade: Optional[str] = None
    secondary_trade: Optional[str] = None
    problem_summary: Optional[str] = None
    user_facts: list[str] = Field(default_factory=list, description="Facts the user actually said, short, in their terms")
    tried_already: Optional[str] = None
    urgency: Optional[Urgency] = None
    availability: Optional[str] = None
    property_type: Optional[str] = None
    authority: Authority = "unknown"
    zip_code: Optional[str] = None
    address_hint: Optional[str] = None
    budget: Optional[str] = None
    safety_flags: list[str] = Field(default_factory=list)
    wants_pro: bool = Field(False, description="The user explicitly asked for a pro (in chat or with the app button)")

    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_pref: Optional[Literal["call", "text", "either"]] = None
    consent_to_share: bool = False
    user_confirmed_summary: bool = False

    matched_provider_ids: list[str] = Field(default_factory=list)
    status: Literal["draft", "submitted"] = "draft"

    def patch(self, **fields) -> list[str]:
        """Apply partial updates from the agent; returns list of fields that changed."""
        changed = []
        for k, v in fields.items():
            if v is None or k not in Lead.model_fields or k in ("lead_id", "created_at", "status"):
                continue
            if k in ("user_facts", "safety_flags"):
                v = [x for x in (v if isinstance(v, list) else [v]) if x]
                merged = getattr(self, k) + [x for x in v if x not in getattr(self, k)]
                if merged != getattr(self, k):
                    setattr(self, k, merged); changed.append(k)
                continue
            if k == "contact_phone":
                v = normalize_phone(v) or v
            if k == "zip_code":
                v = str(v).strip()[:5]
            if getattr(self, k) != v:
                setattr(self, k, v); changed.append(k)
        # Validate via pydantic round-trip (raises on bad literal values)
        Lead.model_validate(self.model_dump())
        return changed


def normalize_phone(p: str | None) -> str | None:
    if not p:
        return None
    digits = re.sub(r"\D", "", str(p))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10 or digits[0] in "01":
        return None
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"


def dispatch_gaps(lead: Lead, known_provider_ids: set[str] | None = None) -> list[str]:
    """Return the list of reasons the lead is NOT yet dispatchable (empty list == dispatchable)."""
    gaps = []
    if lead.trade not in TRADES:
        gaps.append("trade: not set to a known trade")
    if not lead.problem_summary or len(lead.problem_summary.split()) < 8:
        gaps.append("problem_summary: missing or too vague (need what/where/what's been tried)")
    if not lead.urgency:
        gaps.append("urgency: unknown")
    if not lead.zip_code or not re.fullmatch(r"\d{5}", lead.zip_code):
        gaps.append("zip_code: missing")
    elif lead.zip_code not in DURHAM_AREA_ZIPS:
        gaps.append(f"zip_code: {lead.zip_code} is outside the served Durham-area ZIPs")
    if not lead.contact_name:
        gaps.append("contact_name: missing")
    if not normalize_phone(lead.contact_phone):
        gaps.append("contact_phone: missing or not a valid US number")
    if not lead.consent_to_share:
        gaps.append("consent_to_share: user has not agreed to share contact with providers")
    if lead.authority == "unknown":
        gaps.append("authority: unknown whether they own the home or need landlord approval")
    if not lead.matched_provider_ids:
        gaps.append("matched_provider_ids: no providers matched yet (call search_providers)")
    elif known_provider_ids is not None and not set(lead.matched_provider_ids) <= known_provider_ids:
        gaps.append("matched_provider_ids: contains ids not returned by search_providers")
    if not lead.user_confirmed_summary:
        gaps.append("user_confirmed_summary: show the user the summary and get a yes before submitting")
    return gaps


def provider_facing_text(lead: Lead, provider_name: str, reveal_contact: bool = True) -> str:
    """What the provider would actually receive (SMS/email body).

    reveal_contact=False is the pro inbox before the pro accepts: the homeowner's phone and full name stay
    hidden until there is a match.
    """
    urg = {"emergency": "EMERGENCY - today", "within_24h": "within 24 hours",
           "within_few_days": "within a few days", "flexible": "flexible"}.get(lead.urgency or "", "?")
    auth = {"owner": "Homeowner", "renter_landlord_approved": "Renter (landlord approved)",
            "renter_needs_approval": "Renter - needs landlord approval", "property_manager": "Property manager"}.get(lead.authority, "Unknown")
    lines = [
        f"New {TRADES.get(lead.trade or '', {}).get('label', lead.trade)} request for {provider_name} [{lead.lead_id}]",
        f"Job: {lead.problem_summary}",
    ]
    if lead.tried_already:
        lines.append(f"Already tried: {lead.tried_already}")
    lines += [
        f"When: {urg}" + (f" (availability: {lead.availability})" if lead.availability else ""),
        f"Where: ZIP {lead.zip_code}" + (f", {lead.property_type}" if lead.property_type else ""),
        f"Decision maker: {auth}",
    ]
    if lead.budget:
        lines.append(f"Budget: {lead.budget}")
    if lead.safety_flags:
        lines.append("Safety notes: " + "; ".join(lead.safety_flags))
    how = contact_pref_text(lead.contact_pref)
    if reveal_contact:
        lines.append(f"Contact: {lead.contact_name}, {lead.contact_phone} ({how})")
    else:
        first = (lead.contact_name or "the homeowner").split()[0]
        lines.append(f"Contact: {first} ({how}). Phone shown once you accept.")
    return "\n".join(lines)


def contact_pref_text(pref: str | None) -> str:
    return {"call": "prefers a phone call", "text": "prefers a text message"}.get(pref or "", "a call or text is fine")
