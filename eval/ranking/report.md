# Ranking eval - 2026-10-08 14:52
47 needs, top 5 per system (one row per brand). Judge: `claude-haiku-5-5`, labels 0-3 (517 labeled pairs). Good = label 2 or 3.

| system | NDCG@3 | P@3 | excellent@1 | MRR@5 | no good in top 3 | mean km (top 3) | latency p50 / p95 |
|---|---|---|---|---|---|---|---|
| v0_baseline | 0.510 | 0.70 | 0.23 | 0.79 | 2% | 13.8 | 0 / 1 ms |
| v1_distance_bayes | 0.679 | 0.87 | 0.53 | 0.94 | 2% | 9.3 | 1 / 1 ms |
| v2_+tags | 0.789 | 0.93 | 0.64 | 0.97 | 0% | 10.2 | 1 / 1 ms |
| v3_+bm25 | 0.856 | 0.98 | 0.77 | 1.00 | 0% | 11.2 | 3 / 5 ms |
| v3_+embed | 0.875 | 0.96 | 0.81 | 0.97 | 0% | 10.7 | 18 / 26 ms |
| v4_hybrid | 0.878 | 0.98 | 0.79 | 0.99 | 0% | 11.0 | 12 / 15 ms |
| v5_hybrid+rerank | 0.954 | 1.00 | 0.94 | 1.00 | 0% | 9.5 | 3155 / 3954 ms |

## Per trade, NDCG@3 (v0_baseline vs v5_hybrid+rerank)

| trade | n | v0 | best |
|---|---|---|---|
| appliance_repair | 4 | 0.33 | 1.00 |
| electrical | 6 | 0.38 | 1.00 |
| gutters | 3 | 0.43 | 0.91 |
| handyman | 2 | 0.65 | 0.85 |
| hvac | 6 | 0.90 | 1.00 |
| pest_control | 5 | 0.46 | 1.00 |
| plumbing | 9 | 0.43 | 0.87 |
| roofing | 4 | 0.62 | 0.92 |
| water_damage_restoration | 4 | 0.73 | 1.00 |
| waterproofing_foundation | 4 | 0.20 | 0.97 |

## Where v5_hybrid+rerank is still weakest (lowest NDCG@3)

- **ceiling_drip_shower** (tags ['pipe_leak', 'faucet_fixture']): NDCG@3 0.56
    - [2] Bar D Plumbing: Durham plumber within about 5 km with residential plumbing, drain, and fixture work and a stated 24/7 line, but no explicit shower or ceiling-leak service is listed.
    - [2] Brown Brothers Plumbing & Heating: Established residential plumbing company about 8 km away that says it handles clogs and backups, but no specific shower or ceiling-leak work is named.
    - [3] Jordan Plumbing and Maintenance, LLC: Durham plumber about 9 km away that lists leak detection, tub and shower service, and 24/7 emergency plumbing, all closely matching this leak-from-shower problem.
- **water_heater_leak** (tags ['water_heater']): NDCG@3 0.69
    - [2] Shelton Plumbing Co: Family-owned Durham plumber about 1 km away with water heater repairs, installations and upgrades, and 24/7 emergency service; replacement is implied but not explicitly stated.
    - [3] Bar D Plumbing: Explicitly offers water heater installation and replacement, gas water heaters, 24/7 hours, about 19 km away, residential service.
    - [2] Brown Brothers Plumbing & Heating: Plumbing company in Durham listing hot water heaters, residential service and emergency service, about 17 km away, but water heater replacement is not explicitly stated.
- **gutter_guards** (tags ['gutter_guards']): NDCG@3 0.73
    - [2] Triangle Home Detailing: Offers gutter guard installation and gutter cleaning for residential homes in Durham, 15.7 km away; primarily an exterior cleaning company, so gutter guard install is a secondary service.
    - [3] Ever Clean Gutter Systems: Specialist in patented clog-free gutter guard systems with free evaluation and lifetime warranty; Durham 15.2 km away, residential.
    - [3] HomeCraft: Gutters trade; website sells and installs micro-mesh gutter guards, residential, Durham, 15.7 km away. Strong match for clog prevention.
- **flat_roof_porch** (tags ['roof_leak', 'flat_roof']): NDCG@3 0.83
    - [3] Simply Roofing: Durham roofer 4.7 km away that explicitly lists EPDM roofing, flat roofing, roof repair, and emergency roofing services.
    - [2] American Craftsmen Of NC: Durham roofing company 4.2 km away offering roofing and gutters, but no flat roof or EPDM work is stated.
    - [3] Premier Roofing Sheetmetal & Construction LLC: Durham roofer 4.5 km away that lists flat roofs, roof leaks, flashing, and emergency repairs.
- **drywall_door** (tags ['drywall', 'doors_windows']): NDCG@3 0.83
    - [3] Mr. Handyman of Chapel Hill and West Durham: Locally owned handyman 11 km away that explicitly lists drywall patching and repair, and has a 24-hour listing.
    - [2] Triangle Services - Handyman & Appliance Repair: Handyman that explicitly lists drywall hole and patch repair, texture matching and door work, serving Raleigh and Durham, though distance is unknown.
    - [3] Gary The Handyman: Handyman 17.5 km away whose site explicitly lists sheetrock, drywall, painting, and window and door work, serving Durham.
- **tankless_upgrade** (tags ['water_heater']): NDCG@3 0.87
    - [3] Bar D Plumbing: Explicitly lists tankless water heater install and replacement, residential service, 24/7 hours, and Durham-area service within about 16.5 km.
    - [3] After Hours Plumbing & Pump Service, Inc.: Explicitly lists tankless water heaters and water heater installation for residential customers, with emergency service, about 12 km away.
    - [2] PlumbV Inc.: Plumbing business listing tankless water heater installation and 24/7 emergency repairs in Durham and Chapel Hill, though the website text belongs to a differently named company and distance is unknown.
