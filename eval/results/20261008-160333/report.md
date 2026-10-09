# Eval report - 2026-10-08 16:06
Agent model: `claude-sonnet-5-5` | simulator/judge: `claude-haiku-5-5` / `claude-haiku-5-5` | runs: 25

## Headline
- **Conversion** (dispatchable lead submitted, on scenarios where a lead is appropriate): **58% (11/19)**
- **Provider acceptance** (provider-judge would pay ~$50 and act): **100% (11/11)**, mean score 3.64/5
- False leads on no-lead scenarios (out of area/scope, DIY, refuses phone, gas leak): 0% (0/5)
- Median user turns to submitted lead: 6

## Lead quality checks (submitted leads)
- Correct trade: 100% (11/11)
- Urgency acceptable: 100% (11/11)
- ZIP correct: 100% (11/11)
- Phone correct: 100% (11/11)
- Providers real (in directory): 100% (11/11)
- Providers serve the trade: 100% (11/11)
- Leads/conversations with fabricated or contradictory facts: 20% (5/25)
- Safety scenarios (gas, burning outlet) handled correctly: 100% (2/2)

## Per scenario
| scenario | run | should lead | submitted | turns | ended | trade | accept | score | issues |
|---|---|---|---|---|---|---|---|---|---|
| basement_storm_standing | 0 | True | True | 7 | lead_submitted | water_damage_restoration | True | 4 |  |
| basement_seep_recurring | 0 | True | False | 6 | user_ended | waterproofing_foundation |  |  | urgency_ok |
| sump_pump_failed | 0 | True | False | 5 | user_ended | plumbing |  |  |  |
| ceiling_drip_shower | 0 | True | True | 6 | lead_submitted | plumbing | True | 3 |  |
| roof_leak_storm | 0 | True | True | 6 | lead_submitted | roofing | True | 4 |  |
| no_ac_heatwave | 0 | True | True | 5 | lead_submitted | hvac | True | 4 | fabricated |
| no_heat_winter | 0 | True | False | 8 | user_patience_exhausted | hvac |  |  | fabricated, contradiction |
| outlet_dead | 0 | True | False | 3 | user_ended | electrical |  |  |  |
| burning_outlet_safety | 0 | True | True | 5 | lead_submitted | electrical | True | 3 |  |
| gas_smell | 0 | False | False | 6 | user_patience_exhausted | None |  |  | trade_ok, contradiction |
| clogged_tub_renter_no_approval | 0 | True | True | 5 | lead_submitted | plumbing | True | 3 |  |
| chinese_tub | 0 | True | True | 5 | lead_submitted | plumbing | True | 4 |  |
| water_heater_leak | 0 | True | True | 7 | lead_submitted | plumbing | True | 4 | contradiction |
| washer_wont_drain | 0 | True | False | 4 | user_ended | appliance_repair |  |  | urgency_ok |
| handyman_list | 0 | True | False | 4 | user_ended | handyman |  |  | urgency_ok |
| termites | 0 | True | True | 7 | lead_submitted | pest_control | True | 4 |  |
| gutters_overflow | 0 | True | False | 5 | user_ended | gutters |  |  | urgency_ok, fabricated, contradiction |
| vague_impatient | 0 | True | False | 5 | user_patience_exhausted | plumbing |  |  |  |
| refuses_phone | 0 | False | False | 5 | user_ended | hvac |  |  | urgency_ok |
| outside_area | 0 | False | False | 3 | user_ended | plumbing |  |  | urgency_ok |
| diy_only | 0 | False | False | 7 | user_ended | plumbing |  |  |  |
| car_out_of_scope | 0 | False | False | 1 | user_ended | None |  |  |  |
| price_shopper | 0 | True | True | 5 | lead_submitted | plumbing | True | 4 |  |
| wrong_self_diagnosis | 0 | True | True | 6 | lead_submitted | handyman | True | 3 |  |
| diy_clog_fixed | 0 | False | False | 3 | user_ended | plumbing |  |  | urgency_ok |

## Provider-judge callback questions (what leads are still missing)
- **basement_storm_standing**: Is water still entering or rising, and has the storm stopped?; Is power on in the basement, and is the standing water near any outlets, panels, or appliances?; Is the water clean, or could it be gray or black water from sewage or surface runoff?
- **ceiling_drip_shower**: Is the leaking kitchen ceiling in the same unit as the upstairs shower, or in a unit below a different tenant's shower?; Is this a single-family rental or a multi-unit building, and who occupies the upstairs unit?; Is the shower a tub/shower combo or a stall, and is the leak most likely from the shower pan, drain, or supply line?
- **roof_leak_storm**: What is the exact street address for the property?; Is it one story? What is the roof pitch, and is the back slope safely accessible for a tarp?; Have you filed an insurance claim yet? If so, which carrier, and has an adjuster been assigned or scheduled?
- **no_ac_heatwave**: What is the full service address, and is there gate, lockbox, or pet access info?; Is the indoor air handler blower running, and is there ice or frost on the indoor coil or refrigerant lines?; Are there any error codes on the thermostat or outdoor unit, and what brand and model is the heat pump?
- **burning_outlet_safety**: Is the breaker or main confirmed off, and is there still any smell, smoke, sparking, or heat at the outlet right now? If there is smoke or flames, call 911 and leave the house first.; Has the bedroom outlet's breaker tripped, and is the outlet dead now?; Is the outlet the only affected one, or are other outlets, switches, or lights in the bedroom or nearby showing heat, flicker, buzzing, or discoloration?
- **clogged_tub_renter_no_approval**: Is the slow drain only in the tub, or are the sink, shower, or toilet also slow or gurgling?; Is there any backup, standing water, or sewage smell, and has any other drain been checked?; What is the building's age and type (single-family rental, duplex, apartment)?
- **chinese_tub**: Is the bathtub the only fixture backing up, or are the shower, sink, and toilet also slow? Does the bathroom sink or toilet gurgle?; Is it a tub/shower combo with a pop-up stopper or a trip lever, and is there an access panel for the drain?; Has any chemical drain cleaner been used? If so, which one, since that affects how I handle the auger work.
- **water_heater_leak**: Is the breaker off now? Have Ray shut power at the panel first, since water is near an electric heater. Which breaker controls it and is the puddle near any wiring?; What is the tank size (gallons), fuel type confirmed as 240V electric, and the brand/model/serial for a sizing and parts check?; Where is the heater located (attic, closet, garage, crawlspace) and what are the access and clearance conditions?
- **termites**: Can you send photos of the mud tubes and of any winged insects, or describe where you saw the insects and whether they were shedding wings?; What is the full property address, and is the crawl space accessible (height, obstructions, pets, locked hatch)?; Has the home had any prior termite treatment, bond, or warranty, and do you have the paperwork?
- **price_shopper**: Is the existing unit natural gas or propane, and is the gas line and flue/venting already compatible with a like-for-like swap?; Is it atmospheric (draft) venting or power-vent, and is the existing vent sized and pitched to code?; What is the make, model, and serial number of the current unit, and does the homeowner want the same brand or is an upgrade acceptable?
- **wrong_self_diagnosis**: Is the water entering from outside (window frame, sill, flashing, or siding) or condensing inside? Can they see daylight, cracks, or gaps around the frame?; Is it a single or double-hung window, and is the homeowner open to repair versus replacement?; How far does the soft drywall extend, and is the stain growing? Is there any visible mold, a musty smell, or sagging?

## Example: what a provider receives
```
New Water damage restoration request for Restoration 1 of Durham [L-8C3D5328]
Job: About 2 inches of standing water over half the basement, started last night after a storm. Water seems to enter along the bottom of the back wall; not from a pipe or appliance. Exact entry point unclear. Happened once before about 2 years ago, much less water.
When: EMERGENCY - today (availability: Today, as soon as possible)
Where: ZIP 27707, house with basement
Decision maker: Homeowner
Contact: Maria Lopez, (919) 555-0142 (prefers call)
```