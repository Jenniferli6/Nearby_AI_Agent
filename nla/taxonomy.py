"""Trade taxonomy: what each trade covers, and the ONE question that best separates it from neighbours.

The agent routes a vague problem ("water in my basement") to a trade. The routing cues and
disambiguation questions here are injected into the system prompt so routing is consistent and
auditable rather than left entirely to the model.
"""

TRADES: dict[str, dict] = {
    "plumbing": {
        "label": "Plumbing",
        "covers": "leaks from pipes/fixtures, clogged drains & sewer lines, water heaters, toilets, faucets, sump pump repair/replacement, burst pipes",
        "key_detail": "which fixture/pipe, still leaking or shut off; for water heaters & sump pumps: type and rough age",
    },
    "water_damage_restoration": {
        "label": "Water damage restoration",
        "covers": "standing water removal, drying out flooded rooms/basements, wet drywall/carpet, mold after water, sewage cleanup",
        "key_detail": "still coming in or stopped, rough depth and area, finished (carpet/drywall) or unfinished, any appliances/outlets in the water",
    },
    "waterproofing_foundation": {
        "label": "Basement waterproofing & foundation",
        "covers": "water seeping through basement walls/floor or crawl space when it rains, recurring dampness, sump pump installation, foundation cracks",
        "key_detail": "how often (every heavy rain?), where it enters (wall crack, floor joint, window well), finished or unfinished space",
    },
    "roofing": {
        "label": "Roofing",
        "covers": "roof leaks, missing/damaged shingles, storm damage to roof, flashing",
        "key_detail": "still leaking inside, how much visible damage, one or two stories, planning an insurance claim",
    },
    "gutters": {
        "label": "Gutters",
        "covers": "clogged/overflowing gutters, detached gutters, downspouts dumping water next to the foundation",
        "key_detail": "overflowing vs detached vs downspout placement",
    },
    "hvac": {
        "label": "Heating & air conditioning",
        "covers": "no heat, no cooling, AC blowing warm, furnace/heat pump issues, thermostat, condensate leaks from AC unit",
        "key_detail": "system type and rough age, what it does (blower running? outdoor unit on? error lights), thermostat/filter checked",
    },
    "electrical": {
        "label": "Electrical",
        "covers": "dead outlets, tripping breakers, flickering lights, panel issues, new circuits, burning smell from outlets",
        "key_detail": "one outlet vs a circuit vs whole house, what was already reset, any scorching/burning smell",
    },
    "appliance_repair": {
        "label": "Appliance repair",
        "covers": "washer, dryer, refrigerator, dishwasher, oven/range not working",
        "key_detail": "which appliance, brand if known, symptom",
    },
    "handyman": {
        "label": "Handyman",
        "covers": "small repairs: drywall patches, doors, fixtures, assembly, caulking, multi-item punch lists",
        "key_detail": "list of items, rough size of each",
    },
    "pest_control": {
        "label": "Pest control",
        "covers": "insects, termites, rodents, wildlife in attic",
        "key_detail": "what pest, where seen, how long",
    },
}

# Specific jobs inside each trade. Both sides are tagged with this list: a provider from its own
# website (data/build_profiles.py), a homeowner's need from the conversation. A tag match is the
# strongest relevance signal: "sump pump repair" should reach plumbers who say they do sump pumps.
JOBS: dict[str, tuple[str, str]] = {
    # tag: (trade, description)
    "drain_clog": ("plumbing", "clogged or slow sink, tub, shower or floor drain"),
    "sewer_line": ("plumbing", "main sewer line backup, camera inspection, sewer line repair or replacement"),
    "toilet_repair": ("plumbing", "running, leaking, clogged or broken toilet; toilet replacement"),
    "faucet_fixture": ("plumbing", "leaky faucet, fixture or shower valve repair or install"),
    "pipe_leak": ("plumbing", "leaking or burst pipe, pipe repair or repiping"),
    "water_heater": ("plumbing", "water heater repair or replacement, tank or tankless, no hot water"),
    "sump_pump": ("plumbing", "sump pump repair, replacement or installation; battery backup"),
    "water_line": ("plumbing", "main water line leak or replacement, low water pressure, shutoff valve"),
    "gas_line": ("plumbing", "gas line install or repair for appliances"),
    "water_extraction": ("water_damage_restoration", "emergency removal of standing water from flooded rooms or basements"),
    "structural_drying": ("water_damage_restoration", "drying wet drywall, carpet, subfloor with fans and dehumidifiers"),
    "mold_remediation": ("water_damage_restoration", "mold inspection and removal after water damage"),
    "sewage_cleanup": ("water_damage_restoration", "cleanup and sanitizing after sewage backup"),
    "storm_flood_cleanup": ("water_damage_restoration", "storm or flood damage cleanup and board-up"),
    "basement_waterproofing": ("waterproofing_foundation", "stopping water seeping through basement walls or floor, interior drains"),
    "crawl_space": ("waterproofing_foundation", "crawl space encapsulation, vapor barrier, crawl space drainage or dehumidifier"),
    "foundation_repair": ("waterproofing_foundation", "foundation cracks, settling, piers, wall bracing"),
    "yard_drainage": ("waterproofing_foundation", "French drains, grading, yard drainage that sends water to the house"),
    "roof_leak": ("roofing", "roof leak repair, flashing, chimney or vent leaks"),
    "roof_replacement": ("roofing", "full roof replacement or new roof"),
    "storm_roof_damage": ("roofing", "storm or hail damage, missing shingles, emergency tarping, insurance claims"),
    "flat_roof": ("roofing", "flat or low-slope roof, TPO, EPDM, metal roofing"),
    "gutter_cleaning": ("gutters", "gutter cleaning, clogged or overflowing gutters"),
    "gutter_install_repair": ("gutters", "gutter repair, reattaching, new gutters, downspout extensions"),
    "gutter_guards": ("gutters", "gutter guards or leaf protection"),
    "ac_repair": ("hvac", "air conditioner not cooling, blowing warm air, AC repair"),
    "heating_repair": ("hvac", "furnace or heat pump not heating, no heat"),
    "hvac_install": ("hvac", "new AC, furnace or heat pump installation or replacement"),
    "hvac_maintenance": ("hvac", "tune-up, maintenance plan, filter and coil cleaning"),
    "ductwork": ("hvac", "duct repair, duct cleaning, airflow problems"),
    "mini_split": ("hvac", "ductless mini-split install or repair"),
    "outlet_switch": ("electrical", "dead outlet, GFCI, switches, adding outlets"),
    "panel_breaker": ("electrical", "breaker tripping, panel upgrade or replacement"),
    "lighting_fan": ("electrical", "light fixtures, ceiling fans, flickering lights"),
    "ev_charger": ("electrical", "EV charger installation"),
    "generator": ("electrical", "standby generator install or service"),
    "wiring_repair": ("electrical", "wiring problems, burning smell, rewiring, code corrections"),
    "washer_dryer": ("appliance_repair", "washing machine or dryer repair"),
    "refrigerator": ("appliance_repair", "refrigerator, freezer or ice maker repair"),
    "dishwasher": ("appliance_repair", "dishwasher repair"),
    "oven_range": ("appliance_repair", "oven, stove, range or cooktop repair"),
    "drywall": ("handyman", "drywall patching, holes, water-stain repair, painting touch-ups"),
    "doors_windows": ("handyman", "sticking doors, door install, window repair, locks"),
    "carpentry_trim": ("handyman", "trim, small carpentry, deck boards, shelving"),
    "assembly_mounting": ("handyman", "furniture assembly, TV mounting, hanging items"),
    "general_odd_jobs": ("handyman", "punch lists of small repairs, caulking, minor fixes"),
    "termites": ("pest_control", "termite inspection and treatment"),
    "rodents": ("pest_control", "mice or rats, exclusion and trapping"),
    "insects": ("pest_control", "ants, roaches, spiders, general insect control"),
    "mosquito": ("pest_control", "mosquito or tick yard treatment"),
    "wildlife_removal": ("pest_control", "raccoons, squirrels, bats or snakes in attic or crawl space"),
    "bed_bugs": ("pest_control", "bed bug treatment"),
}


# Disambiguation playbook for the most common ambiguous intents. The agent uses these to pick the
# single highest-information question instead of interrogating the user.
ROUTING_PLAYBOOK = """
- Water in basement/crawl space:
    * Standing water NOW, or wet carpet/drywall  -> water_damage_restoration first (they extract & dry; a plumber won't).
    * Water coming from a pipe, water heater, or the sump pump failed/ran nonstop -> plumbing.
    * Seeps in through walls/floor every heavy rain, no standing water now -> waterproofing_foundation.
    * Best first question: "Is there standing water right now, and does it seem to come from a pipe/appliance or in through the walls/floor when it rains?"
- Water stain/drip from ceiling:
    * Only after showers/fixture use upstairs -> plumbing.  * Only when it rains -> roofing.  * Under an AC unit/attic air handler -> hvac.
- Water pooling outside next to the house -> gutters (overflow/downspouts) unless it's coming up through the ground (plumbing: possible main line leak).
- "Outlet stopped working" -> electrical (suggest checking breaker/GFCI first).
- Several unrelated small fixes -> handyman.
"""

# Situations where the agent must give safety guidance BEFORE anything else.
SAFETY_RULES = """
- Smell of gas / rotten eggs: tell them to leave the house now, don't flip switches, and call 911 or the gas utility (Enbridge Gas North Carolina, 24/7: 1-877-776-2427) from a safe distance. Do not continue lead intake until they're safe.
- Standing water that may reach outlets, extension cords, appliances, or the electrical panel: don't walk into the water; shut off power at the breaker only if the panel is in a dry area; otherwise call the power company or 911.
- Sparks, burning smell from outlets/panel, or smoke: turn off the breaker if safe, call 911 if there's smoke or heat.
- CO alarm going off: get everyone out, call 911.
- Sewage backup: avoid contact; keep kids/pets away.
Mark the lead urgency 'emergency' in these cases.
"""

DURHAM_AREA_ZIPS = {
    # Durham
    "27701", "27702", "27703", "27704", "27705", "27706", "27707", "27708", "27709", "27710",
    "27711", "27712", "27713", "27715", "27717", "27722",
    # Adjacent towns commonly served by Durham providers
    "27514", "27516", "27517", "27510", "27560", "27278", "27503", "27572", "27519", "27513",
}
