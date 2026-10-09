# Eval report - 2026-10-08 16:20
Agent model: `claude-sonnet-5-5` | simulator/judge: `claude-haiku-5-5` / `claude-haiku-5-5` | runs: 18

## Headline
- **Conversion** (dispatchable lead submitted, among homeowners who want a pro and can get a lead): **94% (15/16)**
- Open to DIY or a pro, and the DIY fix works: n/a ended without a lead (helped to a fix), n/a chose a pro
- **Provider acceptance** (provider-judge would pay ~$50 and act): **100% (15/15)**, mean score 3.40/5
- False leads on no-lead scenarios (out of area/scope, DIY, refuses phone, gas leak): 0% (0/1)
- Median user turns to submitted lead: 6

## Lead quality checks (submitted leads)
- Correct trade: 100% (15/15)
- Urgency acceptable: 100% (15/15)
- ZIP correct: 100% (15/15)
- Phone correct: 100% (15/15)
- Providers real (in directory): 100% (15/15)
- Providers serve the trade: 100% (15/15)
- Leads/conversations with fabricated or contradictory facts: 28% (5/18)
- Safety scenarios (gas, burning outlet) handled correctly: 100% (2/2)

## Per scenario
| scenario | intent | run | should lead | submitted | turns | ended | trade | accept | score | issues |
|---|---|---|---|---|---|---|---|---|---|---|
| basement_storm_standing | wants_pro | 0 | True | True | 7 | lead_submitted | water_damage_restoration | True | 4 |  |
| basement_seep_recurring | wants_pro | 0 | True | True | 6 | lead_submitted | waterproofing_foundation | True | 4 |  |
| sump_pump_failed | wants_pro | 0 | True | False | 5 | user_ended | plumbing |  |  |  |
| ceiling_drip_shower | wants_pro | 0 | True | True | 7 | lead_submitted | plumbing | True | 3 | contradiction |
| roof_leak_storm | wants_pro | 0 | True | True | 6 | lead_submitted | roofing | True | 3 |  |
| no_ac_heatwave | wants_pro | 0 | True | True | 5 | lead_submitted | hvac | True | 3 |  |
| no_heat_winter | wants_pro | 0 | True | True | 6 | lead_submitted | hvac | True | 4 |  |
| outlet_dead | wants_pro | 0 | True | True | 6 | lead_submitted | electrical | True | 3 | fabricated |
| burning_outlet_safety | wants_pro | 0 | True | True | 6 | lead_submitted | electrical | True | 3 |  |
| gas_smell | n/a | 0 | False | False | 6 | user_patience_exhausted | plumbing |  |  |  |
| clogged_tub_renter_no_approval | wants_pro | 0 | True | True | 5 | lead_submitted | plumbing | True | 3 | contradiction |
| chinese_tub | wants_pro | 0 | True | True | 6 | lead_submitted | plumbing | True | 3 | fabricated |
| water_heater_leak | wants_pro | 0 | True | True | 6 | lead_submitted | plumbing | True | 4 |  |
| washer_wont_drain | wants_pro | 0 | True | True | 6 | lead_submitted | appliance_repair | True | 3 |  |
| handyman_list | wants_pro | 0 | True | True | 6 | lead_submitted | handyman | True | 4 |  |
| termites | wants_pro | 0 | True | True | 5 | lead_submitted | pest_control | True | 4 |  |
| gutters_overflow | wants_pro | 0 | True | True | 6 | lead_submitted | gutters | True | 3 |  |
| refuses_phone | wants_pro | 0 | False | False | 3 | user_ended | hvac |  |  | contradiction |

## Provider-judge callback questions (what leads are still missing)
- **basement_storm_standing**: Is power to the basement shut off, and is any water near outlets, the panel, or the furnace? Do not enter if it is still energized.; Is the furnace or water heater gas or electric, and is it submerged or at risk?; Is water still entering? Has the rain stopped, and is the level rising, falling, or flat?
- **basement_seep_recurring**: Where exactly is the crack (which wall, how far from corners, how high), and is it vertical, horizontal, diagonal, or stepped?; Is the crack wet or leaking, or only damp on the floor? Any efflorescence or staining?; Is the crack widening, or is any wall bowing or bulging?
- **ceiling_drip_shower**: What type of shower is it (tub/shower combo or standalone stall), and how old is the bathroom?; Is there water on the bathroom floor or around the shower base, or any staining on the bathroom ceiling or walls?; Does the leak happen when the shower runs only, or also with the sink or other fixtures used?
- **roof_leak_storm**: What is the full property address, and is it in Durham city limits or the county?; How many stories is the home, and what is the roof pitch?; Is the ceiling wet spot still spreading, and can you see the attic side for wet insulation or decking damage?
- **no_ac_heatwave**: Is the thermostat set to COOL with the fan on AUTO, and does it call for cooling and show the correct setpoint?; Did they check or replace the air filter recently, and is the indoor coil or air handler freezing up or dripping?; Is the outdoor unit humming or trying to start without the fan spinning, which could mean a failed capacitor or compressor?
- **no_heat_winter**: Is the furnace getting power? Check the furnace switch, the breaker, and the access panel door switch.; Is the thermostat calling for heat (W) with batteries OK, and does it run the fan on 'on' but not on 'heat'?; Is it a gas furnace? Any gas smell, burning smell, or CO alarm? If so, treat as a safety call first.
- **outlet_dead**: Does the lamp work when plugged into another outlet? If not, is the problem the lamp or the outlet?; Does the living room outlet have Test/Reset buttons? If so, does pressing Reset bring it back?; Are other outlets in the living room or on the same wall dead, or is this the only one?
- **burning_outlet_safety**: Is there any smoke, visible scorching, melting, or sparking at the outlet or cover plate right now? If so, tell them to call 911 and leave the house.; Is the burning smell still present, and is the warm outlet or any other outlet, switch, or panel warm to the touch?; Did the breaker trip on its own, or did they switch it off manually? Confirm it stays off and the outlet is not to be used or reset.
- **clogged_tub_renter_no_approval**: Are any other fixtures (sinks, toilet, shower) slow, gurgling, or backing up, which would point to a main line issue?; Is the tub the only slow drain, and has the tub been snaked or cleaned beyond removing the stopper?; Has Jenny contacted the landlord yet, and who is the landlord or property manager for approval and billing?
- **chinese_tub**: Is the tub fully standing with water, and does it drain at all or just very slowly?; Are the other fixtures (sinks, shower, toilet, second tub) slow or gurgling? Any sewage smell? This tells me whether it's a local clog or a main line problem.; Is the tub a pop-up stopper or a lift/trip stopper, and was there a clog before?
- **water_heater_leak**: Has the water heater breaker been confirmed off, and is the unit de-energized before anyone touches it?; Is the leak from the tank body or from the drain valve, T&P valve, or fittings? A valve or fitting repair may be cheaper than replacement.; What is the tank size (gallons), fuel type, and the make/model or nameplate data if they can read it?
- **washer_wont_drain**: What is the exact LG model number and serial (on the door frame or inside the door)? Is it a front-loader with a pump filter access panel?; Is there standing water on the floor or any leaking now, and has the condo's flooring or the unit below been affected?; Have they already tried cleaning the drain pump filter or checking the drain hose for kinks or clogs?
- **handyman_list**: What is the exact date the in-laws arrive, and what days and times are you available before then?; Is the door sticking from swelling, loose hinges, or a frame that has shifted? Can you send a photo of the door and latch side?; Is the door solid or hollow-core, and is it painted or stained?
- **termites**: Is the winged insect a termite swarmer or a flying ant? Can he send a photo or a sample?; Where exactly are the mud tubes, and are they active or old? Are there any other tubes, damaged wood, or soft spots?; What is the home's address, and is the crawl space accessible (size, height, locked, or blocked by stored items)?
- **gutters_overflow**: How many stories is the house, and can you reach the gutters safely without a ladder (for example, with a lift or from the ground)?; Is the job a cleaning only, or do they also want repairs, downspout fixes, or gutter guards?; What is the condition of the downspouts, and do they discharge at least several feet from the foundation or into extensions?

## Example: what a provider receives
```
New Water damage restoration request for Restoration 1 of Durham [L-6C54CA90]
Job: About 2 inches of standing water covering roughly half of a finished basement, started last night after a storm. Water seems to enter along the bottom of the back wall; no visible pipe or appliance source. Unsure if water is still coming in. Outlets might be higher up but not checked; no appliances seen in the water; unknown whether the furnace is affected. Owner prefers a phone call.
When: EMERGENCY - today
Where: ZIP 27707, house with basement
Decision maker: Homeowner
Contact: Maria Lopez, (919) 555-0142 (prefers call)
```