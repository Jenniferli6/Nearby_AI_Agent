"""Builds data/providers_durham.json from manually researched, publicly listed businesses.

Every row was taken from a public web page on 2026-10-08 (source_url).
Google rating / review counts come from lantern.llc, which republishes Google Business Profile
ratings. data/build_places.py can add Google Places results in a separate file (see nla/providers.py).
"""
import json, re, pathlib

L_PLUMB = "https://lantern.llc/nc/durham/home-services/plumbing"
L_HVAC = "https://lantern.llc/nc/durham/home-services/hvac"
L_ROOF = "https://lantern.llc/nc/durham/home-services/roofing"
L_ELEC = "https://lantern.llc/nc/durham/home-services/electricians"
L_HANDY = "https://lantern.llc/nc/durham/home-services/handyman"
L_PEST = "https://lantern.llc/nc/durham/home-services/pest-control"

# (name, trades, city, phone, rating, reviews, address, website, emergency_24_7, source_url, notes)
ROWS = [
  # --- Water damage restoration / flood cleanup
  ("SERVPRO of South Durham", ["water_damage_restoration"], "Durham", "(919) 596-1242", None, None,
   "607 Ellis Road 50A, Durham, NC 27703", "servpro.com", True,
   "https://servpro.com/locations/nc/servpro-of-south-durham/contact", "Water, storm, mold, sewage cleanup; board-up and roof tarping."),
  ("SERVPRO of North Durham", ["water_damage_restoration"], "Durham", "(919) 467-0880", None, None,
   "2303 Hwy 70 E Suite D, Durham, NC 27703", "servpro.com", True,
   "https://www.servpro.com/locations/nc/servpro-of-north-durham/contact", "24/7 emergency water/fire/mold."),
  ("1-800 WATER DAMAGE of N.W. Triangle Area", ["water_damage_restoration"], "Durham", "(919) 589-1300", None, None,
   "Durham, NC 27713", "1800waterdamage.com", True,
   "https://1800waterdamage.com/nw-triangle-area/durham", "Water extraction, flood restoration, sewage cleanup, mold."),
  ("Roto-Rooter Plumbing & Water Cleanup (Durham)", ["plumbing", "water_damage_restoration", "waterproofing_foundation"], "Durham", "(919) 598-0255", 4.9, 2238,
   "331 W Main St #307, Durham, NC 27701", "rotorooter.com/durhamnc", True,
   "https://www.rotorooter.com/durhamnc/water-damage-restoration/", "Plumbing + drains + sump pumps + basement flood cleanup, 24/7. Rating from " + L_PLUMB),
  # --- Waterproofing / foundation / crawl space
  ("Carolina Basement Systems", ["waterproofing_foundation"], "Raleigh (serves Durham)", "(800) 638-7048", 4.1, 90,
   "4701 Trademark Drive, Raleigh, NC 27610", "basementsystems.com", False,
   "https://www.basementsystems.com/crawl-space/north-carolina/4103-carolina-basement-systems.html",
   "Basement waterproofing, crawl space, sump pumps, foundation repair; lists Durham in service area. Rating from Angi."),
  # --- Plumbing
  ("Brown Brothers Plumbing & Heating", ["plumbing"], "Durham", "(919) 220-2554", 4.9, 1418, None, "bbph.com", False, L_PLUMB, ""),
  ("Streamline Services Plumbing, HVAC & Electrical", ["plumbing", "hvac", "electrical", "waterproofing_foundation"], "Durham", "(919) 234-5438", 4.9, 4373, None, None, False, L_PLUMB, "Multi-trade; Angi also lists them for basement waterproofing."),
  ("JD Service Now", ["plumbing", "electrical", "hvac"], "Durham", "(919) 339-1601", 4.9, 5333, None, None, False, L_PLUMB, "Multi-trade."),
  ("Harmon Plumbing", ["plumbing"], "Durham", "(984) 205-1790", 5.0, 251, None, None, False, L_PLUMB, ""),
  ("Zoom Drain", ["plumbing"], "Durham", "(919) 999-8234", 5.0, 225, None, None, False, L_PLUMB, "Drain and sewer specialist."),
  ("Bar D Plumbing", ["plumbing"], "Durham", "(984) 339-1491", 4.9, 730, None, None, False, L_PLUMB, ""),
  ("Shelton Plumbing Co", ["plumbing"], "Durham", "(919) 599-1437", 4.9, 199, None, None, False, L_PLUMB, ""),
  ("PlumbV Inc.", ["plumbing"], "Durham", "(919) 378-0292", 4.8, 1053, None, "plumbv.com", False, L_PLUMB, ""),
  ("Acme Plumbing Co.", ["plumbing"], "Durham", "(919) 688-1348", 4.7, 287, None, None, False, L_PLUMB, ""),
  ("Mr. Rooter Plumbing of Durham North", ["plumbing"], "Durham", "(984) 203-6026", 4.9, 43, None, None, False, L_PLUMB, ""),
  ("Waterheater 4u", ["plumbing"], "Durham", "(919) 434-0043", 4.9, 59, None, None, False, L_PLUMB, "Water heater specialist."),
  # --- HVAC
  ("Alternative Aire Inc", ["hvac"], "Durham", "(919) 404-9040", 4.9, 1004, None, None, False, L_HVAC, ""),
  ("Air Innovations Heating and Cooling, LLC", ["hvac"], "Durham", "(919) 620-6715", 4.9, 161, None, None, False, L_HVAC, ""),
  ("Green Horizon One Hour Heating & Air Conditioning", ["hvac", "plumbing"], "Durham", "(919) 321-9985", 4.8, 901, None, None, False, L_HVAC, ""),
  ("Happy Home Services", ["hvac", "plumbing"], "Durham", "(919) 378-0197", 4.8, 2131, None, None, False, L_HVAC, ""),
  ("Boer Brothers Heating & Cooling", ["hvac"], "Chapel Hill", "(919) 929-9886", 4.9, 1329, None, None, False, L_HVAC, ""),
  ("All Weather Heating & Cooling Inc.", ["hvac", "electrical"], "Durham", "(919) 967-9775", 4.8, 249, None, None, False, L_HVAC, ""),
  # --- Electrical
  ("Bud Matthews Services", ["electrical", "plumbing", "hvac", "handyman"], "Chapel Hill", "(919) 929-0203", 4.8, 681, None, None, False, L_ELEC, ""),
  ("Touchstone Electric Raleigh", ["electrical"], "Morrisville", "(919) 670-4015", 4.9, 549, None, None, False, L_ELEC, ""),
  ("Triad Electrical Services", ["electrical"], "Cary", "(919) 590-5034", 5.0, 905, None, None, False, L_ELEC, ""),
  # --- Roofing
  ("MJ's Roofing & Remodeling", ["roofing"], "Durham", "(919) 295-0404", 4.9, 73, None, None, False, L_ROOF, ""),
  ("WJM Roofing", ["roofing"], "Durham", "(919) 495-1283", 4.9, 45, None, None, False, L_ROOF, ""),
  ("Boxer Roofing", ["roofing"], "Durham", "(919) 730-1735", 4.9, 39, None, None, False, L_ROOF, ""),
  ("Feazel Roofing", ["roofing", "gutters"], "Durham", "(984) 377-7663", 4.7, 602, None, None, False, L_ROOF, ""),
  ("ARAC Roof It Forward", ["roofing"], "Durham", "(919) 794-7333", 4.7, 83, None, None, False, L_ROOF, ""),
  ("Pickard Roofing Company, Inc.", ["roofing"], "Durham", "(919) 682-5702", 4.5, 46, None, None, False, L_ROOF, ""),
  ("Carolina United Roofing & Construction LLC", ["roofing"], "Chapel Hill", "(919) 260-3803", 5.0, 197, None, None, False, L_ROOF, ""),
  ("Your Local Roofing and Gutter Specialist", ["roofing", "gutters"], "Carrboro", "(919) 912-4315", 4.8, 36, None, None, False, L_ROOF, ""),
  # --- Handyman / gutters
  ("Mr. Handyman of Chapel Hill and West Durham", ["handyman", "gutters"], "Durham", "(919) 336-0198", 4.9, 269,
   "Durham, NC 27713", "mrhandyman.com/chapel-hill-west-durham", False, L_HANDY, "Also does gutter cleaning (mrhandyman.com)."),
  ("Home Repair Lab", ["handyman"], "Durham", "(919) 321-7465", 5.0, 48, None, None, False, L_HANDY, ""),
  ("MoHandymen LLC", ["handyman"], "Durham", "(919) 695-3243", 4.9, 53, None, None, False, L_HANDY, ""),
  ("Do it All Dave's LLC", ["handyman"], "Durham", "(984) 234-9709", 4.8, 45, None, None, False, L_HANDY, ""),
  ("Housing Solutions, Inc.", ["handyman"], "Hillsborough", "(919) 296-9073", 5.0, 72, None, None, False, L_HANDY, ""),
  # --- Appliance
  ("Mr. Appliance of Durham-Chapel Hill", ["appliance_repair"], "Durham", "(919) 626-3670", None, None, None, "mrappliance.com/durham", False,
   "https://www.mrappliance.com/durham", ""),
  ("Triangle Services - Handyman & Appliance Repair", ["appliance_repair", "handyman"], "Raleigh", "(919) 229-9534", 4.9, 172, None, "tsrdu.com", False, L_HANDY, ""),
  # --- Pest
  ("Aruza Pest Control", ["pest_control"], "Apex", "(919) 759-6912", 4.9, 6162, None, None, False, L_PEST, "Serves the Triangle."),
  ("Triangle Pest Control", ["pest_control"], "Apex", "(919) 341-1531", 4.9, 4600, None, None, False, L_PEST, ""),
  ("Go-Forth Pest Control", ["pest_control"], "Raleigh", "(919) 747-4668", 4.9, 2030, None, None, False, L_PEST, ""),
]

def slug(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:48]

out = []
for (name, trades, city, phone, rating, reviews, addr, web, e247, src, notes) in ROWS:
    out.append(dict(id=slug(name), name=name, trades=trades, city=city, phone=phone,
                    google_rating=rating, google_reviews=reviews, address=addr, website=web,
                    # only True was researched (from the company's own page); False here just means "not checked"
                    emergency_24_7=True if e247 else None, source_url=src, notes=notes,
                    maps_url="https://www.google.com/maps/search/?api=1&query=" + (name + " " + (addr or city + " NC")).replace(" ", "+"),
                    retrieved="2026-10-08", data_source="web_research"))
p = pathlib.Path(__file__).with_name("providers_durham.json")
p.write_text(json.dumps(out, indent=1))
print(len(out), "providers ->", p)
