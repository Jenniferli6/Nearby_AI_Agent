# Eval report - 2026-10-08 15:02
Agent model: `claude-sonnet-5-5` | simulator/judge: `claude-haiku-5-5` / `claude-haiku-5-5` | runs: 25

## Headline
- **Conversion** (dispatchable lead submitted, on scenarios where a lead is appropriate): **68% (13/19)**
- **Provider acceptance** (provider-judge would pay ~$50 and act): **100% (13/13)**, mean score 3.54/5
- False leads on no-lead scenarios (out of area/scope, DIY, refuses phone, gas leak): 0% (0/5)
- Median user turns to submitted lead: 6

## Lead quality checks (submitted leads)
- Correct trade: 100% (13/13)
- Urgency acceptable: 100% (13/13)
- ZIP correct: 100% (13/13)
- Phone correct: 100% (13/13)
- Providers real (in directory): 100% (13/13)
- Providers serve the trade: 100% (13/13)
- Leads/conversations with fabricated or contradictory facts: 20% (5/25)
- Safety scenarios (gas, burning outlet) handled correctly: 100% (2/2)

## Per scenario
| scenario | run | should lead | submitted | turns | ended | trade | accept | score | issues |
|---|---|---|---|---|---|---|---|---|---|
| basement_storm_standing | 0 | True | True | 7 | lead_submitted | water_damage_restoration | True | 4 |  |
| basement_seep_recurring | 0 | True | True | 6 | lead_submitted | waterproofing_foundation | True | 3 |  |
| sump_pump_failed | 0 | True | False | 5 | user_ended | water_damage_restoration |  |  |  |
| ceiling_drip_shower | 0 | True | True | 6 | lead_submitted | plumbing | True | 4 |  |
| roof_leak_storm | 0 | True | True | 6 | lead_submitted | roofing | True | 4 | contradiction |
| no_ac_heatwave | 0 | True | True | 6 | lead_submitted | hvac | True | 4 |  |
| no_heat_winter | 0 | True | True | 7 | lead_submitted | hvac | True | 3 |  |
| outlet_dead | 0 | True | True | 6 | lead_submitted | electrical | True | 3 | fabricated |
| burning_outlet_safety | 0 | True | True | 6 | lead_submitted | electrical | True | 4 |  |
| gas_smell | 0 | False | False | 6 | user_patience_exhausted | None |  |  | trade_ok |
| clogged_tub_renter_no_approval | 0 | True | False | 7 | user_ended | plumbing |  |  |  |
| chinese_tub | 0 | True | True | 6 | lead_submitted | plumbing | True | 4 |  |
| water_heater_leak | 0 | True | True | 6 | lead_submitted | plumbing | True | 3 | contradiction |
| washer_wont_drain | 0 | True | False | 3 | user_ended | appliance_repair |  |  | urgency_ok, contradiction |
| handyman_list | 0 | True | True | 6 | lead_submitted | handyman | True | 4 |  |
| termites | 0 | True | True | 6 | lead_submitted | pest_control | True | 4 |  |
| gutters_overflow | 0 | True | False | 4 | user_ended | gutters |  |  | urgency_ok |
| vague_impatient | 0 | True | False | 4 | user_ended | plumbing |  |  |  |
| refuses_phone | 0 | False | False | 3 | user_ended | hvac |  |  | urgency_ok, fabricated |
| outside_area | 0 | False | False | 3 | user_ended | plumbing |  |  | urgency_ok |
| diy_only | 0 | False | False | 8 | user_patience_exhausted | plumbing |  |  |  |
| car_out_of_scope | 0 | False | False | 2 | user_ended | None |  |  |  |
| price_shopper | 0 | True | False | 4 | user_ended | plumbing |  |  |  |
| wrong_self_diagnosis | 0 | True | True | 7 | lead_submitted | roofing | True | 2 |  |
| diy_clog_fixed | 0 | False | False | 4 | user_ended | plumbing |  |  |  |

## Provider-judge callback questions (what leads are still missing)
- **basement_storm_standing**: How many square feet are affected, and how high up the walls does the water wick?; Is water still entering, and where is it coming from (foundation crack, window well, floor drain, sump pump failure)?; Does the basement have a sump pump, and is it running or failed?
- **basement_seep_recurring**: What is the crack's size and type (hairline vs. wider, stair-step, horizontal, or bowing wall)?; Is the wall shared with an adjoining townhouse, and who is responsible for it?; Does an HOA or shared-wall agreement require approval before any work?
- **ceiling_drip_shower**: Is there an upstairs bathroom directly above the stained kitchen ceiling, and does the drip happen only during showers or also when the tub, sink, or toilet runs?; Is the water clear or gray, and is it still actively dripping or only stained?; Is there an AC unit or air handler in an attic or closet above the kitchen, and could condensate be the source?
- **roof_leak_storm**: Is water actively entering now, or only when it rains? Has the ceiling stain grown since the storm?; What date did the storm hit, and has the insurance carrier been notified? Do you have a claim number or an adjuster visit scheduled?; Is there visible damage on other slopes, gutters, or flashing, or only the back slope?
- **no_ac_heatwave**: Is the thermostat actually in Cool mode, and is it set below the current indoor temperature? Is it a heat pump with a backup/emergency heat setting that might be engaged?; Is the outdoor unit running, and is the fan spinning? Is it making noise, or is there ice or frost on the lines or coil?; Did the homeowner check the air filter and the breaker or disconnect (usually at the outdoor unit) during the call, and what did they find?
- **no_heat_winter**: Did you replace the thermostat batteries, and does the thermostat call for heat with the setpoint above room temperature?; Is there a separate power switch or breaker for the furnace (such as an air handler disconnect or a switch in the attic, closet, or basement) and is it on?; Does the furnace control board show a flashing LED or error code, and what pattern is it showing?
- **outlet_dead**: Where is the main panel, and can I access it without moving anything? Is it a standard breaker panel or something older (Federal Pacific, Zinsco, fuses)?; Which breaker did she reset, and does the panel have AFCI breakers? Is the living room outlet on a breaker that is now in the middle position or off?; Is the living room outlet downstream of the bathroom GFCI or another GFCI (kitchen, garage, exterior)? Did she press the reset or test button on any other GFCI?
- **burning_outlet_safety**: Is there any active smoke, flames, sparking, or melting now? If so, tell them to leave the house and call 911 first.; Has the main breaker stayed off since it was switched off, and is the power to that bedroom circuit still off?; Is the lamp or any cord still plugged into the outlet, and is the cord damaged or discolored?
- **chinese_tub**: Is the tub the only fixture backing up, or do you hear gurgling or see water rising in the sink or toilet when the tub is used?; Does the tub have a pop-up stopper, and can it be removed or does it have an overflow plate that might be part of the clog?; Did the plunger attempt use a flange (toilet) plunger or a cup plunger, and was the tub filled with water and sealed during that attempt?
- **water_heater_leak**: Is the water heater gas or electric, and what is the tank size in gallons?; Can the homeowner send the brand, model, and serial number from the data plate so I can confirm the age and sizing?; Is the leak confirmed to come from the tank body, or could it be a fitting, drain valve, or T&P valve that might be repairable?
- **handyman_list**: Which interior door sticks, and on which edge does it rub: hinge side, latch side, or top? Is it a recent problem, and does it stick in humid weather?; Where is the drywall hole (wall, height, room), and what's behind it? Any sign of wiring, plumbing, or a stud, and is it from a doorknob impact?; What's the wall finish (paint, texture) and how many coats of paint will the patch need to match?
- **termites**: Can you confirm crawl space access (hatch size, any standing water, low clearance) and whether someone will be home?; Did the winged insects look like swarmers (straight antennae, equal-length wings, narrow waist) or flying ants? Can they send photos of the insects and the mud tubes?; Do you know of any prior termite treatment, bond, or warranty, and can you check closing paperwork or ask the previous owner or a prior company?
- **wrong_self_diagnosis**: Is there a roof section, valley, or roof-to-wall junction directly above this window, and does the water appear only in wind-driven rain?; Is the bedroom upstairs or on the ground floor? The lead says 'bedroom floor' but also 'upstairs,' and the stain is on the wall below the window, not the ceiling.; Which side of the house faces the wind, and has the window or exterior trim, caulk, or siding been replaced or repaired recently?

## Example: what a provider receives
```
New Water damage restoration request for Restoration 1 of Durham [L-F08850ED]
Job: Storm water started coming into the finished basement last night. About 2 inches of standing water over half the basement, carpet is soaked, and water is still seeping in along the bottom of the back wall. Similar but much smaller water entry happened once about 2 years ago. No appliances or outlets in the water; a couch and some boxes are in it. Electrical panel is upstairs in the garage, away from the water. Owner; needs someone today.
When: EMERGENCY - today (availability: Needs someone today)
Where: ZIP 27707, house with basement
Decision maker: Homeowner
Contact: Maria Lopez, (919) 555-0142 (prefers call)
```