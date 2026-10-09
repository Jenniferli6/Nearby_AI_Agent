# Eval report - 2026-10-08 16:28
Agent model: `claude-sonnet-5-5` | simulator/judge: `claude-haiku-5-5` / `claude-haiku-5-5` | runs: 12

## Headline
- **Conversion** (dispatchable lead submitted, among homeowners who want a pro and can get a lead): **50% (2/4)**
- Open to DIY or a pro, and the DIY fix works: 100% (4/4) ended without a lead (helped to a fix), 0% (0/4) chose a pro
- **Provider acceptance** (provider-judge would pay ~$50 and act): **100% (2/2)**, mean score 3.50/5
- False leads on no-lead scenarios (out of area/scope, DIY, refuses phone, gas leak): 0% (0/4)
- Median user turns to submitted lead: 6

## Lead quality checks (submitted leads)
- Correct trade: 100% (2/2)
- Urgency acceptable: 100% (2/2)
- ZIP correct: 100% (2/2)
- Phone correct: 100% (2/2)
- Providers real (in directory): 100% (2/2)
- Providers serve the trade: 100% (2/2)
- Leads/conversations with fabricated or contradictory facts: 25% (3/12)
- Safety scenarios (gas, burning outlet) handled correctly: n/a

## Per scenario
| scenario | intent | run | should lead | submitted | turns | ended | trade | accept | score | issues |
|---|---|---|---|---|---|---|---|---|---|---|
| vague_impatient | wants_pro | 0 | True | False | 5 | user_patience_exhausted | plumbing |  |  |  |
| outside_area | wants_pro | 0 | False | False | 4 | user_ended | plumbing |  |  | urgency_ok |
| diy_only | diy | 0 | False | False | 3 | user_ended | plumbing |  |  | urgency_ok |
| car_out_of_scope | n/a | 0 | False | False | 2 | user_ended | None |  |  |  |
| price_shopper | wants_pro | 0 | True | True | 6 | lead_submitted | plumbing | True | 4 |  |
| wrong_self_diagnosis | wants_pro | 0 | True | True | 5 | lead_submitted | handyman | True | 3 | contradiction |
| diy_clog_fixed | diy | 0 | False | False | 3 | user_ended | plumbing |  |  | urgency_ok |
| open_washer_sock | open | 0 | None | False | 7 | user_ended | appliance_repair |  |  | urgency_ok |
| open_gutters_one_story | open | 0 | None | False | 6 | user_ended | gutters |  |  | urgency_ok |
| open_tub_slow | open | 0 | None | False | 4 | user_ended | plumbing |  |  | urgency_ok |
| open_outlet_gfci | open | 0 | None | False | 3 | user_ended | electrical |  |  | urgency_ok, fabricated |
| open_toilet_fails | open | 0 | True | False | 6 | user_ended | plumbing |  |  | urgency_ok, contradiction |

## Provider-judge callback questions (what leads are still missing)
- **price_shopper**: Is the current unit vented as atmospheric (draft hood and flue), power vent, or direct vent, and is the existing flue in good shape?; Is the gas line material and shutoff location accessible, and does it need upsizing or a new connection?; Do they want a like-for-like 50-gallon gas replacement or an upgrade such as a higher-efficiency, power-vent, or tankless unit?
- **wrong_self_diagnosis**: What is the exact property address, and is ZIP 27712 inside my service area?; Where is the damp spot relative to the window: sill, jamb, or head? How far below the sill does the wet wall extend?; Is there visible damage at the exterior: caulk gaps, cracked trim, failed flashing, or siding problems around the window?

## Example: what a provider receives
```
New Plumbing request for Shelton Plumbing Co [L-21914664]
Job: Planning ahead to replace a 50-gallon gas tank water heater, about 14 years old. Still works but is rusty. Located in a closet off the hallway (not garage or attic). Owner wants quotes from 2-3 pros; prefers text.
When: flexible
Where: ZIP 27707
Decision maker: Homeowner
Contact: Hugo Diaz, (919) 555-0172 (prefers text)
```