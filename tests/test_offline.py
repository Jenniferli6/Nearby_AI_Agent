"""Offline tests (no API key needed): lead gating, provider search, and the agent tool loop with a scripted fake model.
Run:  python -m pytest -q   (or  python tests/test_offline.py)
"""
import json, os, pathlib, sys, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from nla import places_budget
from nla.agent import LeadAgent
from nla.lead import Lead, dispatch_gaps, normalize_phone
from nla.providers import DATA, ProviderDirectory
from nla.ranking import CONFIGS, Need, Ranker
from nla.taxonomy import TRADES

D = ProviderDirectory(paths=(DATA,))  # seed only, so results don't depend on an optional Places build
OFFLINE_RANK = CONFIGS["v3_+bm25"]  # keyword relevance only: no embedding model download in tests


def test_seed_data_is_complete():
    assert len(D.providers) >= 40
    for p in D.providers:
        assert normalize_phone(p["phone"]), p["name"]
        assert p["source_url"].startswith("https://")
        assert all(t in TRADES for t in p["trades"])
    for t in TRADES:
        assert any(t in p["trades"] for p in D.providers), f"no providers for {t}"


def test_emergency_search_prefers_24_7_restoration():
    m = D.search("water_damage_restoration", "27705", emergency=True)
    assert len(m) == 3 and all(x.provider["emergency_24_7"] for x in m)


def test_places_file_merges_duplicates_into_seed_row():
    extra = pathlib.Path(tempfile.mkdtemp()) / "places.json"
    extra.write_text(json.dumps([
        # same phone as the seed's SERVPRO of South Durham, which has no rating and no location
        dict(id="gp-dup", name="SERVPRO of South Durham", trades=["water_damage_restoration", "roofing"], phone="919-596-1242",
             google_rating=4.7, google_reviews=195, lat=35.95, lng=-78.85, emergency_24_7=False, data_source="google_places"),
        dict(id="gp-new", name="New Durham Plumber", trades=["plumbing"], phone="(919) 555-0100", emergency_24_7=None)]))
    d = ProviderDirectory(paths=(DATA, extra))
    assert d.get("gp-new") and not d.get("gp-dup")
    assert len(d.providers) == len(D.providers) + 1
    s = d.get("servpro-of-south-durham")
    assert (s["google_rating"], s["google_reviews"], s["lat"]) == (4.7, 195, 35.95)  # fresher Google fields
    assert s["trades"] == ["water_damage_restoration", "roofing"]                    # seed primary trade kept
    assert s["emergency_24_7"] is True                                                # researched True survives
    assert s["data_source"] == "web_research+google_places"


def test_entity_matching_by_name_and_address_and_one_row_per_brand():
    rows = [
        dict(id="seed-rr", name="Roto-Rooter Plumbing & Water Cleanup (Durham)", trades=["plumbing"], phone="(919) 598-0255",
             city="Durham", address="331 W Main St #307, Durham, NC 27701", google_rating=4.9, google_reviews=2238),
        # same business, Google listing with a tracking number: same house number + ZIP -> merged
        dict(id="gp-rr", name="Roto-Rooter Plumbing & Water Cleanup", trades=["plumbing"], phone="(919) 813-4000", city="Durham",
             address="331 W Main St #307, Durham, NC 27701, USA", google_rating=4.9, google_reviews=2278, place_id="A"),
        # same brand, different branch -> separate row, but never shown next to the Durham one
        dict(id="gp-rr-ch", name="Roto-Rooter Plumbing & Water Cleanup", trades=["plumbing"], phone="(919) 968-8204", city="Durham",
             address="3329 Durham-Chapel Hill Blvd Suite 200G, Durham, NC 27707, USA", google_rating=4.9, google_reviews=1186),
        dict(id="gp-other", name="Bar D Plumbing", trades=["plumbing"], phone="(984) 339-1491", city="Durham", google_rating=4.9, google_reviews=847),
    ]
    f = pathlib.Path(tempfile.mkdtemp()) / "p.json"
    f.write_text(json.dumps(rows))
    d = ProviderDirectory(paths=(f,))
    assert {p["id"] for p in d.providers} == {"seed-rr", "gp-rr-ch", "gp-other"}
    rr = d.get("seed-rr")
    assert rr["google_reviews"] == 2278 and rr["alt_phones"] == ["(919) 813-4000"] and rr["phone"] == "(919) 598-0255"
    assert [m.provider["id"] for m in d.search("plumbing")] == ["seed-rr", "gp-other"]


def test_unknown_24_7_gets_no_boost_or_penalty():
    pros = [dict(id=i, name=i, trades=["plumbing"], phone=f"919555010{n}", city="Durham", google_rating=4.8,
                 google_reviews=100, emergency_24_7=e) for n, (i, e) in enumerate([("yes", True), ("no", False), ("unk", None)])]
    f = pathlib.Path(tempfile.mkdtemp()) / "p.json"
    f.write_text(json.dumps(pros))
    m = {x.provider["id"]: x for x in ProviderDirectory(paths=(f,)).search("plumbing", emergency=True)}
    assert m["yes"].score == m["no"].score + 3 and m["no"].score == m["unk"].score
    assert "24/7 availability unknown" in m["unk"].reasons


def test_places_budget_refuses_past_cap():
    old_usage, old_cap = places_budget.USAGE, os.environ.get("NLA_PLACES_MONTHLY_CAP")
    places_budget.USAGE = pathlib.Path(tempfile.mkdtemp()) / "usage.json"
    os.environ["NLA_PLACES_MONTHLY_CAP"] = "2"
    try:
        places_budget.spend(); places_budget.spend()
        try:
            places_budget.spend()
            raise AssertionError("third call should be refused")
        except places_budget.BudgetExceeded:
            pass
        assert places_budget.used() == 2 and places_budget.remaining() == 0
    finally:
        places_budget.USAGE = old_usage
        if old_cap is None:
            os.environ.pop("NLA_PLACES_MONTHLY_CAP", None)
        else:
            os.environ["NLA_PLACES_MONTHLY_CAP"] = old_cap


def test_ranker_prefers_providers_whose_site_states_the_job():
    r = Ranker()
    if not any(p.get("profile") for p in r.dir.providers):
        return  # website profiles not built (data/build_profiles.py)
    need = Need("plumbing", "sump pump hums but won't pump, water on basement floor", ["sump_pump"], zip_code="27705", emergency=True)
    top = r.rank(need, CONFIGS["v2_+tags"])
    assert top and all("sump_pump" in (m.provider.get("profile") or {}).get("job_tags", []) for m in top)
    assert all(any("website says they do" in w for w in m.reasons) for m in top)
    # suppliers / commercial-only businesses confirmed by their own site never appear
    for t in ("gutters", "appliance_repair", "electrical"):
        for m in r.rank(Need(t, zip_code="27705"), CONFIGS["v2_+tags"], limit=10):
            pr = m.provider.get("profile") or {}
            assert pr.get("is_home_service_provider", True) or m.provider.get("site_chars", 0) < 1000


def test_phone_normalisation():
    assert normalize_phone("919.555.0101") == "(919) 555-0101"
    assert normalize_phone("+1 919 555 0101") == "(919) 555-0101"
    assert normalize_phone("12345") is None


def test_gating():
    lead = Lead()
    assert len(dispatch_gaps(lead)) >= 8
    lead.patch(trade="plumbing", problem_summary="Kitchen sink drain fully clogged since yesterday, plunger did not help",
               urgency="within_24h", zip_code="27705", contact_name="Jen", contact_phone="919-555-0101",
               consent_to_share=True, authority="owner", user_confirmed_summary=True)
    assert dispatch_gaps(lead) == ["matched_provider_ids: no providers matched yet (call search_providers)"]
    lead.zip_code = "10001"
    assert any("outside" in g for g in dispatch_gaps(lead))


# ---------- fake Anthropic client ----------
class _B(dict):
    def model_dump(self, **kw): return dict(self)

class _R:
    def __init__(self, content): self.content = [_B(c) for c in content]

class FakeClient:
    """Replays a scripted sequence of assistant turns."""
    def __init__(self, script): self.script = list(script); self.messages = self
    def create(self, **kw): return _R(self.script.pop(0))

def tu(i, name, inp): return {"type": "tool_use", "id": f"t{i}", "name": name, "input": inp}
def tx(t): return {"type": "text", "text": t}


def test_agent_loop_end_to_end(tmp_path=None):
    script = [
        [tu(1, "update_lead", {"trade": "water_damage_restoration", "urgency": "emergency", "user_facts": ["water in basement after storm"], "wants_pro": True}),],
        [tx("Is there standing water right now?")],
        [tu(2, "update_lead", {"zip_code": "27705", "problem_summary": "About 2 inches of standing water across finished basement after last night's storm, carpet soaked"}),
         tu(3, "search_providers", {"trade": "water_damage_restoration", "emergency": True})],
        [tx("Here are 3 24/7 restoration companies...")],
        [tu(4, "submit_lead", {})],                       # premature submit -> must be rejected
        [tx("Before I send this, can I get your name and phone?")],
        [tu(5, "update_lead", {"contact_name": "Jennifer", "contact_phone": "9195550101", "contact_pref": "call",
                               "consent_to_share": True, "authority": "owner", "user_confirmed_summary": True}),
         tu(6, "submit_lead", {})],
        [tx("Sent!")],
    ]
    a = LeadAgent(client=FakeClient(script), directory=D, save_leads=False, rank_config=OFFLINE_RANK)
    a.reply("Water started coming into my basement last night after the storm. I don't know who to call.")
    a.reply("yes about 2 inches, 27705")
    a.reply("ok send it")
    rejected = [e for e in a.events if e["tool"] == "submit_lead"][0]["output"]
    assert rejected["submitted"] is False and rejected["dispatch_gaps"]
    assert a.reply("Jennifer 919 555 0101, I own it, yes send") == "Sent!"
    assert a.lead.status == "submitted" and len(a.dispatch_payloads) == 3
    assert "EMERGENCY" in a.dispatch_payloads[0]["message"]
    print(a.dispatch_payloads[0]["message"])


def test_no_provider_search_until_user_asks_for_a_pro():
    script = [[tu(1, "update_lead", {"trade": "plumbing", "zip_code": "27705"}), tu(2, "search_providers", {"trade": "plumbing"})],
              [tx("Want to try a hand auger first, or shall I find you a pro?")]]
    a = LeadAgent(client=FakeClient(script), directory=D, save_leads=False, rank_config=OFFLINE_RANK)
    a.reply("tub still slow after I cleared the hair")
    out = [e for e in a.events if e["tool"] == "search_providers"][0]["output"]
    assert out["providers"] == [] and "hasn't asked for a pro" in out["error"]
    assert a.last_matches == [] and a.lead.matched_provider_ids == []


def test_thinking_blocks_round_trip_intact():
    """Regression: thinking blocks must be sent back with their signature (API 400 otherwise)."""
    seen = []
    class Spy(FakeClient):
        def create(self, **kw):
            seen.append(kw["messages"]); return super().create(**kw)
    script = [[{"type": "thinking", "thinking": "need trade", "signature": "SIG123"},
               tu(1, "update_lead", {"trade": "plumbing"})],
              [tx("What's leaking?")]]
    a = LeadAgent(client=Spy(script), directory=D, save_leads=False, rank_config=OFFLINE_RANK)
    a.reply("sink leaking")
    sent_back = seen[1][1]["content"][0]
    assert sent_back == {"type": "thinking", "thinking": "need trade", "signature": "SIG123"}


def test_portal_privacy_status_and_overlays():
    from nla.lead import Lead
    from nla.portal import Portal, apply_accounts
    portal = Portal(pathlib.Path(tempfile.mkdtemp()) / "app.db")
    lead = Lead(trade="plumbing", problem_summary="Sump pump hums but does not pump, water on the basement floor",
                urgency="emergency", zip_code="27705", contact_name="Maria Lopez", contact_phone="(919) 555-0142",
                contact_pref="call", consent_to_share=True, authority="owner", user_confirmed_summary=True,
                matched_provider_ids=["a", "b"], status="submitted")
    portal.record_submission("c1", "owner1", lead.model_dump(), ["a", "b"])
    portal.record_submission("c1", "owner1", lead.model_dump(), ["a", "b"])  # idempotent
    inbox = portal.leads_for_pro("a", "Pro A")
    assert len(inbox) == 1 and "contact" not in inbox[0]
    assert "555-0142" not in inbox[0]["brief"] and "Lopez" not in inbox[0]["brief"]   # hidden before a match
    d = ProviderDirectory(paths=(DATA,))
    assert portal.requests_for_owner("owner1", d)[0]["status"] == "sent"
    portal.set_delivery(lead.lead_id, "a", "viewed")
    assert portal.requests_for_owner("owner1", d)[0]["status"] == "viewed"
    portal.set_delivery(lead.lead_id, "b", "declined", "too_far")
    portal.set_delivery(lead.lead_id, "a", "accepted")
    portal.set_delivery(lead.lead_id, "a", "viewed")  # re-opening never downgrades an answer
    req = portal.requests_for_owner("owner1", d)[0]
    assert req["status"] == "matched" and {p["label"] for p in req["pros"]} == {"Accepted: they have your number", "Not available"}
    a = portal.leads_for_pro("a", "Pro A")[0]
    assert a["contact"]["phone"] == "(919) 555-0142" and "555-0142" in a["brief"]   # revealed after accepting
    assert portal.decline_stats() == {"too_far": 1}
    assert portal.requests_for_owner("someone_else", d) == []
    # an answer is final: a pro who declined can't accept later and get the contact
    assert portal.set_delivery(lead.lead_id, "b", "accepted") == "already_answered"
    assert "contact" not in portal.leads_for_pro("b", "Pro B")[0]
    # a closed request can't be accepted, so a pro who hadn't answered never sees the contact
    lead2 = Lead.model_validate(dict(lead.model_dump(), lead_id="L-CLOSED01"))
    portal.record_submission("c2", "owner1", lead2.model_dump(), ["a"])
    portal.close_request(lead2.lead_id, "owner1")
    assert portal.set_delivery(lead2.lead_id, "a", "accepted") == "closed"
    assert "contact" not in next(x for x in portal.leads_for_pro("a", "Pro A") if x["lead_id"] == lead2.lead_id)
    assert portal.set_delivery("L-NOPE", "a", "accepted") == "not_found"
    # claimed listing overrides + a brand-new registration joins the directory
    portal.save_account("servpro-of-south-durham", {"name": "SERVPRO of South Durham", "phone": "(919) 596-1242",
                        "trades": ["water_damage_restoration"], "job_tags": ["water_extraction", "mold_remediation"],
                        "open_24_7": True, "service_radius_km": 25, "license_number": "GC-12345", "license_board": "general_contractor"})
    new_id = portal.save_account(None, {"name": "Bull City Drains", "phone": "(919) 555-0199", "zip": "27701",
                                        "trades": ["plumbing"], "job_tags": ["drain_clog"]})
    d2 = apply_accounts(ProviderDirectory(paths=(DATA,)), portal.accounts())
    s = d2.get("servpro-of-south-durham")
    assert s["claimed"] and s["service_radius_km"] == 25 and s["profile"]["job_tags"] == ["water_extraction", "mold_remediation"]
    n = d2.get(new_id)
    assert n and n["lat"] and n["data_source"] == "self_registered"
    ranked = {m.provider["id"]: m for m in Ranker(d2).rank(Need("plumbing", "kitchen drain clogged", ["drain_clog"], zip_code="27701"),
                                                            CONFIGS["v2_+tags"], limit=100)}
    assert new_id in ranked and any("the business says it does" in w for w in ranked[new_id].reasons)  # eligible; self-reported jobs count, labeled as such


def test_agent_state_round_trip_and_provider_choice():
    script = [[tu(1, "update_lead", {"trade": "plumbing", "zip_code": "27705", "problem_summary": "Kitchen sink fully clogged since yesterday, plunger did not help", "wants_pro": True}),
               tu(2, "search_providers", {"trade": "plumbing", "job_tags": ["drain_clog"]})], [tx("Here are three plumbers.")]]
    a = LeadAgent(client=FakeClient(script), directory=D, save_leads=False, rank_config=OFFLINE_RANK)
    a.reply("sink clogged in 27705")
    shown = [m["provider_id"] for m in a.last_matches]
    assert len(shown) == 3 and a.lead.matched_provider_ids == shown
    assert a.select_providers([shown[1], "not-a-shown-id"]) == [shown[1]]   # only pros from the search
    b = LeadAgent(client=FakeClient([]), directory=D, save_leads=False, rank_config=OFFLINE_RANK).load_state(json.loads(json.dumps(a.to_state())))
    assert b.lead.matched_provider_ids == [shown[1]] and b.transcript() == a.transcript() and b.returned_provider_ids == a.returned_provider_ids


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("PASS", name)