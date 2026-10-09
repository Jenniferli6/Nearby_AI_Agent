# Demo: Nearby's own example, end to end

This is an unedited transcript from the conversation eval (`eval/results/20261008-161818`, scenario `basement_storm_standing`).
The homeowner is simulated by Claude Haiku 5.5 from hidden facts: 2 inches of standing water, a finished basement, ZIP 27707, owner, wants someone today.
The agent is Claude Sonnet 5.5 with the hybrid ranker. The three providers are real Durham-area businesses; spot-check them in [data/PROVIDERS.md](data/PROVIDERS.md).

**What to look for:**
- Safety comes first.
- The agent says plainly that this needs a water-damage company today, and *asks* before searching ("Want me to find a 24/7 water-damage company now?").
- The matched providers come with reasons drawn from their own websites and listings.
- The summary is confirmed before anything is sent.

## Conversation

**Homeowner:** Water started coming into my basement last night after the storm. I don't know who to call.

**Nearby:** I'm sorry, that's stressful. First, don't walk into any standing water if outlets, cords, appliances or the electrical panel are near it. Only switch off power at the breaker if the panel is in a dry spot. If you can, photograph the water for insurance.  
  
Is there standing water right now? And does it seem to come through the walls or floor, or from a pipe or appliance?

**Homeowner:** Yes, about 2 inches of standing water covers about half the finished basement. It seems to come in along the bottom of the back wall, not from any pipe or appliance that I can see.

**Nearby:** This sounds like groundwater coming through the wall after heavy rain. With 2 inches over a finished floor, it needs a water-damage company today. Carpet and drywall can start growing mold within 24 to 48 hours. A plumber can't extract and dry it.  
  
Right now, lift furniture and any belongings off the wet floor. Take photos for insurance.  
  
Once the water is out, a waterproofing company can look at the wall so it doesn't happen again.  
  
Want me to find a 24/7 water-damage company now?

**Homeowner:** Yes, please find someone today. Can you also tell me if they'll call me, since I prefer calls? My number is 919-555-0142.

**Nearby:** I've noted your number and that you prefer calls. I'll ask the pros to phone you, but I can't promise when they'll call. What's your ZIP code?

**Homeowner:** Sorry, I'm stressed. It's 27707.

**Nearby:** No need to apologize. Here are three 24/7 water-damage companies near 27707:  
  
1. Restoration 1 of Durham, (919) 241-7311. Their website lists emergency standing-water removal and drywall drying. 4.9★ from 129 reviews.  
2. RestorePro Reconstruction, (919) 804-8827. Same services on their site. 4.8★ from 623 reviews.  
3. United Water Restoration Group of Triangle (Chapel Hill), (919) 341-2250. Same services on their site. 5★ from 60 reviews.  
  
This comes from public listings, and I haven't verified licenses or insurance.  
  
Do you own the home or rent? And what's your name? OK to share your name and number with these pros so they can call you?

**Homeowner:** I own the home. My name is Maria Lopez. Yes, you can share my name and number, 919-555-0142, so they can call me.

**Nearby:** Thanks, Maria. One optional thing so the pros arrive prepared: is water still coming in, and are any outlets, appliances or the furnace sitting in the water? If you don't know, that's fine.

**Homeowner:** I'm not sure if it's still coming in. I can see water along the back wall, but I haven't checked closely. The outlets are up higher, I think, and I don't see any appliances in the water. I don't know about the furnace, though.

**Nearby:** Please don't wade in to check the furnace. If it or any outlets turn out to be in the water, leave the power off or call the power company.  
  
Here's the request:  
  
Emergency: about 2 inches of standing water over half of a finished basement, since last night's storm. It seems to come in along the bottom of the back wall. No pipe or appliance source is visible. You're not sure if it's still coming in. Outlets look higher up. You don't know about the furnace.  
Owner: Maria Lopez, 27707, call 919-555-0142.  
It goes to all three companies above.  
  
Send this?

**Homeowner:** Almost. The outlets are higher up, I think, but I haven't really checked. Otherwise yes, please send it.

**Nearby:** Sent, Maria. Your request (lead L-6C54CA90) went to Restoration 1 of Durham, RestorePro Reconstruction, and United Water Restoration Group of Triangle. I asked them to call you at 919-555-0142. I can't say when they'll call. Since it's urgent, you can also call any of them directly using the numbers above.  
  
While you wait:  
- Keep the power off and stay out of the water if outlets or the furnace could be wet.  
- Move belongings up off the floor.  
- Take photos and video for insurance.  
- Ask the pros to check where the water is coming in, then look at waterproofing the back wall once it's dry.

## What the agent did

- Tool calls, in order: `update_lead`, `update_lead`, `update_lead`, `update_lead`, `search_providers`, `update_lead`, `update_lead`, `update_lead`, `submit_lead`
- `search_providers` ran only after the homeowner said yes to a pro (`wants_pro: True`).
- Routed to **water_damage_restoration**, urgency **emergency**, submitted in 7 user turns.

## What each provider receives

In the app, a pro's inbox shows this brief with the contact line hidden until they accept. This is the full version a pro sees after accepting:

```
New Water damage restoration request for Restoration 1 of Durham [L-6C54CA90]
Job: About 2 inches of standing water covering roughly half of a finished basement, started last night after a storm. Water seems to enter along the bottom of the back wall; no visible pipe or appliance source. Unsure if water is still coming in. Outlets might be higher up but not checked; no appliances seen in the water; unknown whether the furnace is affected. Owner prefers a phone call.
When: EMERGENCY - today
Where: ZIP 27707, house with basement
Decision maker: Homeowner
Contact: Maria Lopez, (919) 555-0142 (prefers call)
```

## Provider judge (an LLM acting as the business owner, reading only the message above)

- Would pay ~$50 for this lead and act on it: **yes**, score 4/5
- What it would still ask on the callback:
  - Is power to the basement shut off, and is any water near outlets, the panel, or the furnace? Do not enter if it is still energized.
  - Is the furnace or water heater gas or electric, and is it submerged or at risk?
  - Is water still entering? Has the rain stopped, and is the level rising, falling, or flat?
  - Is the water clean, or could it be gray or sewage (storm drain backup, groundwater)? That changes the category and the PPE and cleanup needed.
  - What is the exact square footage and depth, and what finished materials are affected (carpet, pad, drywall, subfloor, flooring, cabinets)?
  - Are there any contents to move or protect, and is there prior flooding or a known drainage problem at this address?
  - Is there an insurance claim? Does the homeowner want us to work directly with the adjuster and bill the carrier?
  - Can we access the property today, and what is the earliest arrival time? Does the homeowner know who controls the main water shutoff?
  - Has the homeowner already called other companies, and is there a deposit or payment expectation?
