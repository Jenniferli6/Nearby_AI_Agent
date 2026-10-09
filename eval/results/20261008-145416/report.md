# Eval report - 2026-10-08 14:57
Agent model: `claude-sonnet-5-5` | simulator/judge: `claude-haiku-5-5` / `claude-haiku-5-5` | runs: 23

## Headline
- **Conversion** (dispatchable lead submitted, on scenarios where a lead is appropriate): **71% (12/17)**
- **Provider acceptance** (provider-judge would pay ~$50 and act): **100% (12/12)**, mean score 3.50/5
- False leads on no-lead scenarios (out of area/scope, DIY, refuses phone, gas leak): 0% (0/5)
- Median user turns to submitted lead: 6

## Lead quality checks (submitted leads)
- Correct trade: 100% (12/12)
- Urgency acceptable: 100% (12/12)
- ZIP correct: 100% (12/12)
- Phone correct: 100% (12/12)
- Providers real (in directory): 100% (12/12)
- Providers serve the trade: 100% (12/12)
- Leads/conversations with fabricated or contradictory facts: 74% (17/23)
- Safety scenarios (gas, burning outlet) handled correctly: 100% (2/2)

## Per scenario
| scenario | run | should lead | submitted | turns | ended | trade | accept | score | issues |
|---|---|---|---|---|---|---|---|---|---|
| basement_storm_standing | 0 | True | True | 6 | lead_submitted | water_damage_restoration | True | 4 | fabricated |
| basement_seep_recurring | 0 | True | True | 6 | lead_submitted | waterproofing_foundation | True | 3 | fabricated |
| sump_pump_failed | 0 | True | True | 5 | lead_submitted | water_damage_restoration | True | 4 | fabricated |
| no_ac_heatwave | 0 | True | True | 5 | lead_submitted | hvac | True | 4 | fabricated |
| no_heat_winter | 0 | True | False | 8 | user_patience_exhausted | hvac |  |  | fabricated, contradiction |
| outlet_dead | 0 | True | False | 6 | user_ended | electrical |  |  | fabricated, contradiction |
| burning_outlet_safety | 0 | True | True | 5 | lead_submitted | electrical | True | 4 |  |
| gas_smell | 0 | False | False | 6 | user_patience_exhausted | None |  |  | trade_ok, contradiction |
| clogged_tub_renter_no_approval | 0 | True | True | 6 | lead_submitted | plumbing | True | 3 |  |
| chinese_tub | 0 | True | True | 6 | lead_submitted | plumbing | True | 4 | fabricated, contradiction |
| water_heater_leak | 0 | True | True | 6 | lead_submitted | plumbing | True | 3 | fabricated, contradiction |
| washer_wont_drain | 0 | True | False | 8 | user_patience_exhausted | appliance_repair |  |  | urgency_ok, fabricated, contradiction |
| handyman_list | 0 | True | False | 4 | user_ended | handyman |  |  | contradiction |
| termites | 0 | True | True | 6 | lead_submitted | pest_control | True | 3 |  |
| gutters_overflow | 0 | True | True | 6 | lead_submitted | gutters | True | 3 | fabricated |
| vague_impatient | 0 | True | False | 5 | user_patience_exhausted | plumbing |  |  | fabricated, contradiction |
| refuses_phone | 0 | False | False | 4 | user_ended | hvac |  |  | urgency_ok, contradiction |
| outside_area | 0 | False | False | 2 | user_ended | plumbing |  |  | urgency_ok, fabricated, contradiction |
| diy_only | 0 | False | False | 3 | user_ended | None |  |  | trade_ok, urgency_ok, contradiction |
| car_out_of_scope | 0 | False | False | 2 | user_ended | None |  |  | contradiction |
| price_shopper | 0 | True | True | 5 | lead_submitted | plumbing | True | 4 |  |
| wrong_self_diagnosis | 0 | True | True | 7 | lead_submitted | handyman | True | 3 |  |
| diy_clog_fixed | 0 | False | False | 4 | user_ended | plumbing |  |  | urgency_ok |

## Provider-judge callback questions (what leads are still missing)
- **basement_storm_standing**: Is water still entering the basement, and has the rain stopped?; Is the standing water surface runoff, groundwater, or sewage? Is any of it contaminated, or does it smell like sewage?; Is power on in the basement? Are any outlets, appliances, water heater, furnace, or HVAC wet or in the water?
- **basement_seep_recurring**: Is the basement finished (drywall, carpet, stored items), and how much flooring or contents would need moving?; How wide is the wall crack, and is it vertical, horizontal, or stepped? Is it wet, leaking, or showing bowing or movement?; How long has the damp patch and musty smell existed, and does the water seem to come through the crack, the floor joint, or the wall surface?
- **sump_pump_failed**: Has the power to the sump pump and the outlet near the water been shut off at the breaker, and has a licensed electrician confirmed it's safe to enter? Do not quote or dispatch until this is settled.; Is the water from groundwater or a sewer/backup source? Is it clean, gray, or black water, and is there a sewage smell?; How large is the affected area, and is the basement finished? What materials are wet (drywall, carpet, pad, stored items, appliances, HVAC, electrical panel)?
- **no_ac_heatwave**: Is the system set to cool or heat, and is the indoor blower running when the thermostat calls for cooling?; Did the thermostat, filter, or breaker checks change anything? Was a breaker tripped or a filter badly clogged?; Is the compressor running, or only the outdoor fan? Any buzzing, clicking, burning smell, or ice on the indoor coil or refrigerant lines?
- **burning_outlet_safety**: Is the outlet still warm now, and does a non-contact voltage tester show power at the outlet with the breaker off? If so, the breaker may be mislabeled or the circuit may be shared.; Are there scorch marks, discoloration, buzzing, or flickering lights at the outlet, faceplate, or nearby switches?; Which breaker did you turn off, and what else is on that circuit?
- **clogged_tub_renter_no_approval**: Are the sink, shower, and toilet also slow? If so, this could be a main line issue, not a tub clog.; Is there gurgling or backup when other fixtures drain?; What is the full street address to confirm the ZIP and the service area?
- **chinese_tub**: Is the tub draining at all (slow vs. standing water), and does the stopper or trip lever work?; Are the sink and toilet actually draining normally, or is there gurgling, slow drains, or any sewage smell? This determines whether it's a single-fixture clog or a main line issue.; Is there any backup in the shower, floor drain, or laundry, or any sewage in the yard?
- **water_heater_leak**: Is the breaker for the water heater confirmed off at the panel, and is the tank still leaking or has the puddle stopped?; What is the tank size (gallons), make and model, and is the unit confirmed electric, not gas or tankless?; Is the leak coming from the tank body or from a fitting, drain valve, or T&P valve? Can they send a photo?
- **termites**: Where is the crawl space access hatch, and what is its clearance height?; Which pier has the mud tubes, and is it wood, concrete, or block? Are the tubes on the pier or on other framing nearby?; Did the winged bugs look like swarmers (shed wings, straight antennae, uniform wings), and where were they found: inside the house, on windows, or outside near the foundation?
- **gutters_overflow**: How many stories is the house, and can you confirm it from the front and back?; Is the roof reachable for a safe cleaning from a ladder or would it need a lift or a crew?; Which side(s) of the house have the overflow and pooling, and are the downspouts clogged, disconnected, or draining too close to the foundation?
- **price_shopper**: Confirm the existing unit is a 50-gallon natural gas or propane model and note the make/model or serial to check the nameplate BTU rating.; What type of venting does it have (atmospheric draft or power vent), and is the flue in good condition?; Is the utility closet accessible for a standard tank, and is there enough clearance and room for the new unit?
- **wrong_self_diagnosis**: Is the lead's header 'The Aluminum Company of North Carolina' a referral from a window company, and am I being routed a job that a window installer would normally take?; Are there photos of the window frame, sill, wall, and floor?; Is the water coming through the window frame/sill, or around the exterior siding, flashing, or trim?

## Example: what a provider receives
```
New Water damage restoration request for Restoration 1 of Durham [L-5F5984FF]
Job: Water started coming into the finished basement last night after a storm. About 2 inches of standing water over half the basement, seeping in along the bottom of the back wall (not from a pipe or appliance). Carpet is soaked and some boxes are wet. Electrical panel is upstairs in the garage, away from the water. Similar water entry happened once before about 2 years ago, but much smaller. Homeowner; needs someone today.
When: EMERGENCY - today (availability: Needs someone today)
Where: ZIP 27707, house with basement
Decision maker: Homeowner
Contact: Maria Lopez, (919) 555-0142 (prefers call)
```