"""FixSnap - single-file MCP server (Hugging Face Spaces deploy).

Same 5 tools as the full server in ../server, packaged as one file.
Runs on the keyword adapter by default; set OPENAI_API_KEY for real vision.
"""

import base64
import json
import os
import re
import time
import uuid
import urllib.error
import urllib.request
from urllib.parse import quote_plus
from datetime import datetime, timezone

# Disable FastMCP's PyPI version check on startup (can abort in sandbox/prod).
import fastmcp.utilities.version_check as _vc

_vc.check_for_newer_version = lambda *a, **k: None

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from starlette.responses import PlainTextResponse

GUIDES = json.loads(r"""[{"can_diy_diagnose":true,"can_diy_fix":"partial","category":"moisture","clarifying_questions":["Is there a bathroom or roof directly above the stain?","Does the stain get darker or grow after rain?","Is the spot damp to the touch right now?"],"difficulty":"medium","diy_cost":[15,40],"id":"ceiling-water-stain","keywords":["ceiling","stain","brown","yellow","water stain","roof","discoloration","spot on ceiling"],"likely_causes":["Roof leak above the stain","Plumbing leak from bathroom above","Condensation from uninsulated duct","Ice dam (cold climates)"],"parts":["Oil-based stain-blocking primer","Ceiling paint"],"pro_cost":[200,600],"safety_warnings":["Do not cut into a sagging, water-logged ceiling section \u2014 it can collapse.","If water is actively dripping near light fixtures, turn off the breaker for that circuit."],"severity":"urgent","steps":["Determine if the leak is active: press a paper towel to the stain; check again after rain or after running upstairs plumbing.","If a bathroom is above, run each fixture (shower, toilet, sink) one at a time and watch for new dampness.","For roof leaks, inspect the attic above the stain during rain with a flashlight; look for wet decking or drip trails.","Once the source is fixed and the area is fully dry (2-3 dry days), seal the stain with oil-based stain-blocking primer.","Repaint with matching ceiling paint."],"symptoms":["Brown or yellowish ring/spot on ceiling","Stain grows after rain","Paint bubbling or peeling around stain","Musty smell in room"],"time_minutes":[60,180],"title":"Brown water stain on ceiling","tools":["Flashlight","Ladder","Moisture meter (optional, ~$25)"]},{"can_diy_diagnose":true,"can_diy_fix":"partial","category":"hvac","clarifying_questions":["When did you last change the air filter?","Is there ice visible on the copper lines at the indoor or outdoor unit?","Is the outdoor unit's fan spinning?"],"difficulty":"easy","diy_cost":[10,30],"id":"ac-blowing-warm","keywords":["ac","air conditioner","warm air","not cooling","hot air","hvac","thermostat","filter","air filter","dirty filter","clogged filter","furnace filter"],"likely_causes":["Clogged air filter choking airflow","Thermostat set wrong or miscalibrated","Low refrigerant from a leak","Dirty condenser coils","Failed capacitor or contactor"],"parts":["Air filter ($10-25)"],"pro_cost":[150,500],"safety_warnings":["Turn off power at the breaker before touching anything inside the units.","Refrigerant handling requires an EPA-licensed technician \u2014 never attempt a recharge yourself."],"severity":"urgent","steps":["Check thermostat: set to COOL, fan to AUTO, setpoint at least 3 degrees below room temp.","Replace a dirty air filter; if coils iced over, turn AC off and run fan-only for 2-4 hours to thaw.","Clear debris, grass, and leaves from around the outdoor condenser (2 ft clearance); gently rinse coils with a hose.","Check the breaker for the outdoor unit; reset once if tripped.","If still warm after these steps, call a technician \u2014 likely refrigerant leak or electrical component failure."],"symptoms":["Vents blow room-temperature or warm air","AC runs constantly but house won't cool","Ice on indoor or outdoor unit lines","Thermostat set to cool but temp not dropping","Dirty or clogged air filter restricting airflow"],"time_minutes":[20,60],"title":"AC blowing warm air","tools":["Replacement air filter (correct size)","Garden hose"]},{"can_diy_diagnose":true,"can_diy_fix":true,"category":"plumbing","clarifying_questions":["Is the buildup on hot-water fixtures, cold, or both?","Do you notice spots on dishes or a film on glassware?","Has water flow from the showerhead decreased?"],"difficulty":"easy","diy_cost":[3,15],"id":"hard-water-limescale","keywords":["limescale","hard water","white crust","calcium","faucet","showerhead","mineral"],"likely_causes":["Hard water with high calcium/magnesium","No water softener installed","Aging aerators clogged with mineral deposits"],"parts":["Replacement aerators ($5-10, optional)"],"pro_cost":[100,250],"safety_warnings":["Do not use vinegar on natural stone (marble, granite) \u2014 it etches the surface."],"severity":"minor","steps":["Soak a cloth in white vinegar and wrap it around the fixture for 30-60 minutes, or fill a bag with vinegar and tie it over a showerhead.","Scrub with an old toothbrush; rinse thoroughly.","Unscrew faucet aerators and soak them in vinegar, then reinstall.","For persistent whole-house hard water, get a water hardness test strip and consider a softener."],"symptoms":["White chalky buildup on faucets and showerheads","Spots on dishes and glass after washing","Reduced water flow from showerhead","Stiff faucet handles"],"time_minutes":[30,90],"title":"White crusty limescale on faucets and fixtures","tools":["White vinegar","Plastic bag and rubber band","Old toothbrush","Adjustable wrench"]},{"can_diy_diagnose":true,"can_diy_fix":"partial","category":"walls-ceilings","clarifying_questions":["How wide is the crack \u2014 hairline, or can you fit a coin in it?","Are doors or windows sticking?","Did the crack appear suddenly or grow over months?"],"difficulty":"easy","diy_cost":[10,30],"id":"drywall-cracks","keywords":["crack","drywall","wall crack","door frame","foundation","settling","ceiling crack"],"likely_causes":["Normal seasonal settling and wood shrinkage","Foundation movement (expansive clay soil)","Poor drywall taping","Structural overload"],"parts":["Primer and paint"],"pro_cost":[150,400],"safety_warnings":["Cracks wider than 1/4 inch, horizontal foundation cracks, or cracks with one side higher than the other need a structural engineer \u2014 do not just patch them."],"severity":"minor","steps":["Measure the crack width. Hairline (<1/16 in): cosmetic \u2014 fill with paintable caulk or spackle, sand, prime, paint.","For cracks up to 1/8 in: use fiberglass mesh tape + joint compound, feather the edges, sand, prime, paint.","Monitor: mark the crack ends with pencil and date; check monthly whether it grows.","If the crack is wide, growing, or doors are sticking, get a foundation inspection before repairing cosmetically."],"symptoms":["Thin hairline cracks at door/window corners","Diagonal crack running from a door frame","Crack wider than 1/8 inch","Doors sticking or not latching","Cracks with vertical displacement"],"time_minutes":[45,120],"title":"Cracks in drywall or around door frames","tools":["Putty knife","Sandpaper (120 grit)","Fiberglass mesh tape","Joint compound"]},{"can_diy_diagnose":true,"can_diy_fix":true,"category":"plumbing","clarifying_questions":["If you lift the tank lid, is water flowing into the overflow tube?","Does jiggling the handle stop it temporarily?","How old is the toilet?"],"difficulty":"easy","diy_cost":[5,20],"id":"running-toilet","keywords":["toilet","running","toilet keeps running","water running","tank","flapper","fill valve"],"likely_causes":["Worn flapper not sealing","Fill valve not shutting off","Chain too short or tangled","Water level set too high, draining into overflow tube"],"parts":["Flapper ($5-10)","Universal fill valve ($12-18, if needed)","Food coloring for dye test"],"pro_cost":[120,250],"safety_warnings":["Turn off the supply valve behind the toilet before replacing internal parts."],"severity":"minor","steps":["Remove the tank lid and observe: water flowing into the overflow tube means the fill valve or water level is the issue.","Do the dye test: add food coloring to the tank, wait 15 minutes without flushing. Color in the bowl = leaking flapper.","Replace the flapper (match size: 2 in or 3 in) if it is warped or doesn't seal; adjust or replace the chain so it has slight slack.","Adjust the fill valve so water stops about 1 inch below the top of the overflow tube.","If the fill valve hisses or won't shut off, replace it \u2014 a universal fill valve costs under $15."],"symptoms":["Water runs continuously into the bowl","Tank refills every few minutes on its own","Hissing sound from the tank","Higher water bill"],"time_minutes":[20,45],"title":"Toilet running constantly","tools":["Sponge and bucket","Adjustable wrench"]},{"can_diy_diagnose":true,"can_diy_fix":"partial","category":"plumbing","clarifying_questions":["How old is the water heater? (check the serial label)","Is the rumbling new or long-standing?","Is there any water pooling at the base of the tank?"],"difficulty":"medium","diy_cost":[0,40],"id":"water-heater-rumbling","keywords":["water heater","rumbling","popping","no hot water","sediment","hot water runs out"],"likely_causes":["Sediment buildup on the tank bottom","Failing heating element (electric) or thermocouple (gas)","Thermostat set too low or failed","Tank corrosion / end of life (8-12 years)"],"parts":["Heating element ($20-40, if electric and failed)"],"pro_cost":[200,1800],"safety_warnings":["Water pooling at the tank base means the tank is failing \u2014 it can burst and flood. Shut off water and call a plumber promptly.","Gas water heaters: if you smell gas, leave the house and call the gas company \u2014 do not troubleshoot."],"severity":"urgent","steps":["Check the age on the serial label. Over 10 years with rumbling: plan for replacement rather than repair.","Flush sediment: turn off power/gas and cold water supply, attach a hose to the drain valve, and drain until water runs clear.","For electric heaters with no hot water: after turning off the breaker, test the heating elements with a multimeter.","Set thermostat to 120F (49C) \u2014 hotter wastes energy and risks scalding.","If the tank leaks from the body (not a fitting), it must be replaced \u2014 no repair is reliable."],"symptoms":["Rumbling, popping, or banging from the tank","Hot water runs out faster than it used to","Rusty or cloudy hot water","Water leaking at the tank base"],"time_minutes":[45,120],"title":"Water heater rumbling / running out of hot water","tools":["Garden hose","Bucket","Multimeter (for electric units)"]},{"can_diy_diagnose":true,"can_diy_fix":true,"category":"appliances","clarifying_questions":["Does it hum, or is it completely silent?","Did it stop after something hard went down (bone, pit, utensil)?","Is the reset button on the bottom popped out?"],"difficulty":"easy","diy_cost":[0,0],"id":"garbage-disposal-humming","keywords":["garbage disposal","disposal","humming","jammed","sink","kitchen"],"likely_causes":["Jam: object wedged between impellers","Tripped overload / reset button","Tripped GFCI outlet or breaker","Motor burned out (old unit)"],"parts":[],"pro_cost":[120,350],"safety_warnings":["NEVER put your hand inside a disposal, even when it seems dead. Always unplug it or switch off the breaker first."],"severity":"minor","steps":["Turn the switch OFF, then unplug the disposal (or switch off its breaker).","Press the red reset button on the bottom of the unit.","Insert the hex wrench (usually taped under the sink or in the manual) into the bottom socket and work it back and forth to free the jam.","Shine a flashlight inside and remove the lodged object with tongs or pliers \u2014 never fingers.","Restore power and test with cold water running. If it hums then goes silent again, the motor is likely shot."],"symptoms":["Disposal hums when switched on but blades don't spin","Disposal completely dead (no sound)","Water backing up in the sink","Reset button popped out"],"time_minutes":[15,30],"title":"Garbage disposal humming but not grinding","tools":["Hex/Allen wrench (1/4 in, usually supplied)","Flashlight","Tongs or pliers"]},{"can_diy_diagnose":true,"can_diy_fix":"partial","category":"moisture","clarifying_questions":["Which room smells strongest?","Is there a bathroom, kitchen, or exterior wall adjacent?","Do you see any discoloration on walls, ceilings, or baseboards?"],"difficulty":"medium","diy_cost":[25,50],"id":"musty-smell-after-rain","keywords":["musty","smell","mold","damp","after rain","odor","mildew","hidden moisture"],"likely_causes":["Hidden leak behind wall or under floor","Poor ventilation trapping humidity","HVAC drain line clogged","Past water event that never fully dried"],"parts":["Concrobium or detergent for small mold cleanup"],"pro_cost":[300,1500],"safety_warnings":["Large mold patches (>10 sq ft) or mold inside HVAC should be handled by a remediation professional.","Do not just paint over mold \u2014 it keeps growing underneath."],"severity":"urgent","steps":["Pinpoint the source: sniff along baseboards, under sinks, and around the HVAC air handler.","Check the AC condensate drain line for clogs \u2014 a backed-up line is a top cause of musty smells.","Use a $25 moisture meter on suspect walls; readings consistently above 16-20% mean active moisture.","Small surface mold (<10 sq ft) on hard surfaces: scrub with detergent, dry fully, fix the moisture source.","If you can't find the source or the meter shows widespread dampness, call a water-damage specialist before it spreads."],"symptoms":["Musty or earthy smell, worse after rain","Smell localized to one room or wall","Allergy symptoms indoors","Visible dark spots on walls or baseboards"],"time_minutes":[30,90],"title":"Musty smell after rain / suspected hidden moisture","tools":["Moisture meter (~$25)","Flashlight"]},{"can_diy_diagnose":true,"can_diy_fix":false,"category":"electrical","clarifying_questions":["Does it trip immediately when reset, or after some time?","What was running when it tripped (space heater, hair dryer, AC)?","Any burning smell or scorch marks on outlets?"],"difficulty":"pro-only","diy_cost":[0,0],"id":"tripping-breaker","keywords":["breaker","tripping","circuit breaker","power out","outlet dead","electrical","sparking","burning smell"],"likely_causes":["Overloaded circuit (too many high-draw devices)","Short circuit in wiring or an appliance","Ground fault","Failing breaker"],"parts":[],"pro_cost":[150,450],"safety_warnings":["If you smell burning or see scorch marks, turn off the main breaker and call an electrician immediately - this is a fire risk.","Never replace a breaker with a higher amperage one; the wiring is rated for the original size.","Repeatedly resetting a tripping breaker without finding the cause is dangerous."],"severity":"emergency","steps":["Unplug everything on the dead circuit, then reset the breaker ONCE.","If it holds, plug items back in one at a time to find the culprit; move high-draw devices to different circuits.","If it trips immediately with everything unplugged, stop - the fault is in the wiring.","Call a licensed electrician. Tell them whether it trips instantly (likely short) or under load (likely overload)."],"symptoms":["Breaker trips repeatedly","Breaker trips the moment you reset it","Burning smell near outlets or panel","Scorch marks on outlet covers","Lights flicker before the trip"],"time_minutes":[0,0],"title":"Circuit breaker keeps tripping","tools":[]},{"can_diy_diagnose":true,"can_diy_fix":true,"category":"appliances","clarifying_questions":["When did you last clean the lint filter and the vent?","Is the outside vent flap opening when the dryer runs?","Does the dryer get hot at all?"],"difficulty":"easy","diy_cost":[0,25],"id":"dryer-two-cycles","keywords":["dryer","clothes not drying","two cycles","lint","vent","takes long to dry"],"likely_causes":["Clogged dryer vent duct (fire hazard)","Lint filter or internal lint buildup","Failed heating element or thermal fuse","Dryer overloaded"],"parts":["Vent cleaning brush kit ($15-25, optional)"],"pro_cost":[100,250],"safety_warnings":["A clogged dryer vent is one of the leading causes of house fires. Clean it at least yearly.","Unplug the dryer (or turn off the breaker, and shut off gas for gas dryers) before pulling it out or opening panels."],"severity":"urgent","steps":["Clean the lint filter thoroughly; wash it with soap and water if fabric softener residue coats it.","Pull the dryer out, detach the vent duct, and vacuum/shake out all lint.","Go outside: confirm the vent flap opens freely during a cycle and exhaust air feels strong.","Check that the duct is rigid metal or flexible metal - replace white vinyl or foil accordion duct, which traps lint.","If airflow is strong but no heat, the thermal fuse or heating element likely failed - that's a pro or confident-DIY part replacement."],"symptoms":["Clothes need two cycles to dry","Dryer exterior very hot to the touch","Burning smell during drying","Vent flap outside barely opens","Dryer runs but produces no heat"],"time_minutes":[30,60],"title":"Dryer needs two cycles to dry clothes","tools":["Vacuum with hose attachment","Screwdriver"]},{"can_diy_diagnose":true,"can_diy_fix":true,"category":"plumbing","clarifying_questions":["Hot side, cold side, or both dripping?","Is the drip from the spout or the base/handle?","What type of faucet is it (single-handle, two-handle, touchless)?"],"difficulty":"easy","diy_cost":[3,25],"id":"leaky-faucet","keywords":["faucet","dripping","leak","drip","tap","sink"],"likely_causes":["Worn cartridge (single-handle faucets)","Worn rubber washers or O-rings","Corroded valve seat","Loose packing nut"],"parts":["Replacement cartridge or washer kit ($3-15)"],"pro_cost":[120,250],"safety_warnings":["Turn off the hot and cold supply valves under the sink before disassembling the faucet."],"severity":"minor","steps":["Turn off the water supply valves under the sink and plug the drain.","Remove the handle (look for a set screw under a cap) and the retaining nut.","Pull the cartridge/stem; take it to the hardware store to match the exact replacement.","Inspect the valve seat for corrosion; smooth rough spots with a seat wrench if needed.","Reassemble, turn water back on slowly, and check for leaks."],"symptoms":["Steady drip from the spout","Drip worsens over time","Handle needs to be cranked hard to stop the drip","Water pooling around the faucet base"],"time_minutes":[30,60],"title":"Dripping faucet","tools":["Adjustable wrench","Screwdriver set","Plumber's grease (optional)"]},{"can_diy_diagnose":true,"can_diy_fix":true,"category":"plumbing","clarifying_questions":["Bathroom sink, kitchen sink, or tub?","Does it drain slowly or is it fully stopped?","Have you tried a plunger yet?"],"difficulty":"easy","diy_cost":[0,15],"id":"clogged-drain","keywords":["clogged","drain","slow drain","sink clogged","tub","standing water"],"likely_causes":["Hair and soap buildup (bathroom)","Grease and food (kitchen)","Foreign object lodged in trap","Vent stack blockage (multiple fixtures slow)"],"parts":["Drain snake / hair removal tool ($5-15)"],"pro_cost":[100,300],"safety_warnings":["Do not use chemical drain cleaners on a fully stopped drain - caustic water can splash back. Enzyme cleaners are safer for maintenance.","If multiple fixtures back up at once, the main line may be blocked - call a plumber, don't keep plunging."],"severity":"minor","steps":["Remove and clean the drain stopper; pull out hair with a plastic drain snake tool.","Try a plunger with enough water to cover the cup; seal the overflow with a wet rag for better pressure.","For kitchen sinks, pour a kettle of near-boiling water followed by dish soap to cut grease (not on PVC pipes - use hot tap water instead).","If still slow, remove and clean the P-trap under the sink with a bucket underneath.","Still clogged after the trap? The blockage is deeper - use a 25-ft hand auger or call a pro."],"symptoms":["Water drains slowly","Standing water in sink or tub","Gurgling sounds from the drain","Bad odor from the drain"],"time_minutes":[20,60],"title":"Clogged or slow bathroom/kitchen drain","tools":["Plunger","Plastic drain snake","Bucket","Adjustable wrench"]},{"can_diy_diagnose":true,"can_diy_fix":true,"category":"electrical","clarifying_questions":["Is it one outlet or several in the same area?","Is the dead outlet in a kitchen, bathroom, garage, or outdoors?","Did it die after using a high-power device?"],"difficulty":"easy","diy_cost":[0,0],"id":"dead-outlet-gfci","keywords":["outlet","dead outlet","no power","gfci","gfi","reset button","plug not working"],"likely_causes":["Tripped GFCI outlet upstream","Tripped breaker","Loose wire connection","Failed outlet"],"parts":[],"pro_cost":[100,200],"safety_warnings":["If the outlet is warm, sparking, or smells burnt, stop and call an electrician.","Do not open the outlet box unless you know how to verify power is off with a tester."],"severity":"minor","steps":["Check kitchens, bathrooms, garage, and outdoors for a GFCI outlet with a tripped RESET button - one GFCI often protects several downstream outlets. Press RESET.","Check the breaker panel for a tripped breaker.","Test the outlet with a different device to rule out the device itself.","If GFCI won't reset or the breaker trips again, call an electrician - likely a ground fault or wiring issue."],"symptoms":["Outlet has no power","Devices work in other outlets","A GFCI outlet nearby has its red/orange light on","Outlet died after a storm or power surge"],"time_minutes":[10,20],"title":"Dead outlet (check GFCI first)","tools":["Phone charger or lamp (to test)"]},{"can_diy_diagnose":true,"can_diy_fix":true,"category":"appliances","clarifying_questions":["Is water standing in the bottom of the dishwasher?","Does the garbage disposal run (they often share a drain)?","When did you last clean the filter?"],"difficulty":"easy","diy_cost":[0,10],"id":"dishwasher-not-draining","keywords":["dishwasher","not draining","water in dishwasher","standing water","dishes dirty"],"likely_causes":["Clogged filter","Blocked drain hose or air gap","Garbage disposal knockout plug still in place (new installs)","Failed drain pump"],"parts":[],"pro_cost":[120,280],"safety_warnings":["Turn off the breaker before reaching under the dishwasher or touching the drain pump."],"severity":"minor","steps":["Remove the bottom rack; twist out and rinse the cylindrical filter assembly - this fixes most cases.","Check the air gap (chrome cap on the sink) for gunk; clean it out.","Inspect the drain hose under the sink for kinks; make sure it loops up high before connecting to the disposal.","New disposal install? The knockout plug inside the disposal's dishwasher inlet must be punched out.","Run a cycle with a cup of white vinegar on the top rack to clear residue."],"symptoms":["Standing water in the dishwasher bottom","Dishes come out dirty or gritty","Bad smell from the dishwasher","Dishwasher won't advance past wash cycle"],"time_minutes":[20,45],"title":"Dishwasher not draining","tools":["Sponge and towels","Screwdriver"]},{"can_diy_diagnose":true,"can_diy_fix":"partial","category":"appliances","clarifying_questions":["Is the fridge warm but the freezer still cold?","Can you hear the compressor running?","When did you last clean the condenser coils?"],"difficulty":"medium","diy_cost":[0,30],"id":"fridge-not-cooling","keywords":["refrigerator","fridge","not cooling","warm fridge","freezer","compressor"],"likely_causes":["Dirty condenser coils","Blocked air vents inside from overpacking","Failed evaporator fan","Faulty thermostat or defrost system","Refrigerant leak (rare)"],"parts":["Appliance thermometer ($8, optional)"],"pro_cost":[150,400],"safety_warnings":["Unplug the fridge before cleaning coils or accessing the compressor area."],"severity":"urgent","steps":["Check the temperature with a thermometer: fridge should be 37-40F, freezer 0F.","Pull the fridge out and vacuum the condenser coils (front grille or back panel) - dirty coils are the #1 cause.","Make sure interior vents aren't blocked by food; leave space for air circulation.","Listen: if the compressor never runs, check the thermostat setting and the start relay.","If coils are clean, vents clear, and it's still warm after 24 hours, call a technician."],"symptoms":["Fridge section warm, freezer may still be cold","Compressor runs constantly","Food spoiling faster than normal","Frost buildup in the freezer"],"time_minutes":[30,60],"title":"Refrigerator not cooling properly","tools":["Vacuum with brush attachment","Coil brush ($10, optional)"]},{"can_diy_diagnose":true,"can_diy_fix":true,"category":"appliances","clarifying_questions":["Top-load or front-load?","Does it make a humming noise when it should drain?","Any error code on the display?"],"difficulty":"easy","diy_cost":[0,15],"id":"washer-not-draining","keywords":["washing machine","washer","not draining","not spinning","water left","laundry"],"likely_causes":["Clogged drain pump filter","Kinked or clogged drain hose","Unbalanced load triggering shutdown","Failed lid switch / door lock","Failed drain pump"],"parts":[],"pro_cost":[120,300],"safety_warnings":["Unplug the washer before accessing the drain pump filter; have towels ready - water will spill."],"severity":"minor","steps":["Redistribute the load and run a drain/spin cycle - unbalanced loads are the most common cause.","Front-loaders: open the small access panel at the bottom front, unscrew the drain pump filter, and clear debris.","Check the drain hose behind the machine for kinks; make sure it's not shoved more than 6 inches into the standpipe.","Top-loaders: confirm the lid closes firmly - a worn lid switch stops the spin cycle.","If the pump hums but doesn't move water, the pump itself likely needs replacement."],"symptoms":["Water left in the drum after the cycle","Washer won't spin","Humming during drain cycle","Error code on display"],"time_minutes":[20,45],"title":"Washing machine not draining or spinning","tools":["Towels and shallow pan","Pliers"]},{"can_diy_diagnose":true,"can_diy_fix":true,"category":"safety","clarifying_questions":["Is it a single chirp every 30-60 seconds, or a full alarm?","How old is the detector? (check the manufacture date on the back)","Did it start after cooking, steam, or a battery change?"],"difficulty":"easy","diy_cost":[5,30],"id":"smoke-detector-chirping","keywords":["smoke detector","chirping","beeping","alarm","carbon monoxide","co detector"],"likely_causes":["Low battery","Expired detector (10-year life)","Dust in the sensor chamber","End-of-life warning signal"],"parts":["9V or AA batteries, or a new 10-year sealed detector ($25-30)"],"pro_cost":[80,150],"safety_warnings":["Never disable a smoke or CO detector - chirping means it needs attention, not silence.","If a CO detector alarms continuously, leave the house and call emergency services."],"severity":"minor","steps":["Replace the battery even if it seems recent - weak batteries chirp intermittently.","Vacuum the detector vents gently to clear dust.","Check the manufacture date: detectors expire after 10 years (CO detectors after 5-7). Replace if expired.","Distinguish the pattern: 3 beeps = smoke alarm event; 4 beeps = CO alarm event; 1 chirp per minute = low battery or end of life.","For hardwired units, the chirp may come from a backup battery - replace it too."],"symptoms":["Single chirp every 30-60 seconds","Full alarm with no smoke present","Detector older than 10 years","Chirping continues after battery change"],"time_minutes":[10,20],"title":"Smoke detector chirping","tools":["Step ladder","Vacuum with brush attachment"]},{"can_diy_diagnose":true,"can_diy_fix":"partial","category":"hvac","clarifying_questions":["Gas, electric, or heat pump?","Is the thermostat calling for heat (set above room temp)?","Any error code blinking on the furnace?"],"difficulty":"medium","diy_cost":[0,25],"id":"furnace-not-igniting","keywords":["furnace","no heat","not igniting","heater","blowing cold","pilot light","flame sensor"],"likely_causes":["Dirty flame sensor","Thermostat issue or dead batteries","Tripped breaker or switched-off furnace switch","Clogged air filter","Failed ignitor"],"parts":["Fine sandpaper or emery cloth for flame sensor"],"pro_cost":[150,400],"safety_warnings":["If you smell gas, do NOT troubleshoot - leave the house and call the gas company.","Never bypass safety switches or sensors on a furnace."],"severity":"urgent","steps":["Check the thermostat: heat mode, setpoint above room temp, fresh batteries.","Confirm the furnace power switch (looks like a light switch near the unit) is ON and the breaker isn't tripped.","Replace a dirty air filter - restricted airflow can trip safety limits.","The flame sensor (thin metal rod in front of the burners) gets coated in soot: with power OFF, remove it and gently clean with fine sandpaper.","If the ignitor glows but burners never light, or there's any gas smell, stop and call a technician."],"symptoms":["Furnace runs but blows cold air","Furnace tries to start then shuts off","Clicking sound with no ignition","Thermostat calls for heat but nothing happens"],"time_minutes":[20,45],"title":"Furnace not igniting / blowing cold air","tools":["Screwdriver","Fine sandpaper"]},{"can_diy_diagnose":true,"can_diy_fix":true,"category":"doors-windows","clarifying_questions":["Interior or exterior door?","Does it squeak along the whole swing or just at one point?","Any visible rust on the hinges?"],"difficulty":"easy","diy_cost":[0,8],"id":"squeaky-door","keywords":["squeaky","door","squeak","hinge","creaking"],"likely_causes":["Dry hinge pins","Dirt buildup in hinge knuckles","Misaligned hinge from loose screws"],"parts":["Silicone spray or white lithium grease ($5-8)"],"pro_cost":[75,150],"safety_warnings":[],"severity":"cosmetic","steps":["Spray a small amount of silicone lubricant into each hinge knuckle while moving the door back and forth.","For stubborn squeaks, tap the hinge pin up with a nail and hammer, wipe it clean, coat with petroleum jelly, and tap back in.","Tighten any loose hinge screws; if a screw spins freely, replace it with a 3-inch screw that bites into the stud.","Wipe excess lubricant to avoid drips on the floor."],"symptoms":["Squeaking when opening or closing","Creaking at a specific point in the swing","Visible rust on hinges"],"time_minutes":[10,20],"title":"Squeaky door hinges","tools":["Silicone spray lubricant","Hammer and nail (optional)"]},{"can_diy_diagnose":true,"can_diy_fix":true,"category":"walls-ceilings","clarifying_questions":["Interior or exterior wall?","Is the area damp or near plumbing?","Did the peeling start after a repaint?"],"difficulty":"easy","diy_cost":[15,50],"id":"peeling-paint","keywords":["peeling paint","paint bubbling","paint flaking","blistering","wall paint"],"likely_causes":["Moisture behind the paint film","Painting over dirty or glossy surface without primer","Incompatible paint layers (oil over latex without prep)","High humidity during application"],"parts":["Primer (stain-blocking if moisture was involved)","Matching paint"],"pro_cost":[200,600],"safety_warnings":["Homes built before 1978 may have lead paint - test before scraping large areas.","Fix any moisture source first; repainting over active dampness will peel again."],"severity":"minor","steps":["Rule out moisture: if the wall is damp, find and fix the water source first (see water stain guide).","Scrape off all loose and peeling paint with a putty knife; sand the edges smooth.","Wash the area with TSP substitute or degreaser; let dry fully.","Prime bare spots with a quality primer (oil-based stain blocker if there was a stain).","Repaint with two thin coats rather than one thick coat."],"symptoms":["Paint peeling in sheets or chips","Bubbles/blisters under the paint surface","Peeling concentrated near windows or bathrooms","Paint curling at edges"],"time_minutes":[60,180],"title":"Peeling or bubbling paint","tools":["Putty knife / paint scraper","Sandpaper","Primer and brush"]},{"can_diy_diagnose":true,"can_diy_fix":true,"category":"plumbing","clarifying_questions":["Tub, shower, or sink?","Is water leaking onto the floor, or just looks bad?","How old is the existing caulk?"],"difficulty":"easy","diy_cost":[8,20],"id":"tub-caulk-failure","keywords":["caulk","caulking","tub","shower","grout","mold","sealant"],"likely_causes":["Aged caulk shrinking and cracking","Wrong caulk type used (not 100% silicone in wet areas)","Movement between tub and wall"],"parts":["100% silicone caulk, kitchen/bath grade ($8-12)","Painter's tape"],"pro_cost":[100,250],"safety_warnings":["Let old caulk dry fully and the area be bone-dry before recaulking, or mold grows underneath."],"severity":"minor","steps":["Remove ALL old caulk with a caulk removal tool or utility knife - new caulk won't bond to old.","Clean the joint with rubbing alcohol and let it dry completely.","Apply painter's tape on both sides of the joint for clean lines.","Cut the caulk tube tip small, apply a steady bead, and smooth with a wet finger.","Remove tape immediately, then let cure 24 hours before using the shower."],"symptoms":["Caulk cracked, peeling, or missing in spots","Black mold in the caulk line","Water pooling where tub meets wall","Musty smell near the tub"],"time_minutes":[45,90],"title":"Failed caulk around tub or shower","tools":["Caulk gun","Caulk removal tool or utility knife","Rubbing alcohol"]},{"can_diy_diagnose":true,"can_diy_fix":true,"category":"plumbing","clarifying_questions":["Does the water rise in the bowl but not overflow?","Do other drains in the house also run slow?","Anything unusual flushed recently?"],"difficulty":"easy","diy_cost":[0,15],"id":"toilet-clogged","keywords":["toilet clogged","toilet won't flush","plunger","overflow","blocked toilet"],"likely_causes":["Too much paper or non-flushable item","Partial blockage in the trap","Main line issue (multiple fixtures affected)"],"parts":[],"pro_cost":[120,300],"safety_warnings":["Turn off the supply valve behind the toilet if water keeps rising toward the rim.","Never use chemical drain cleaner in a toilet - it can crack porcelain and splash dangerously."],"severity":"minor","steps":["Stop flushing - one more flush can cause an overflow.","Use a flange plunger (the kind with the extra rubber flap): seal it over the drain hole and plunge vigorously 10-15 times.","If the plunger fails, use a toilet auger: feed it into the drain, crank to break up or hook the blockage.","If multiple fixtures are backing up, the main sewer line is likely blocked - call a plumber.","Prevent repeats: only flush waste and toilet paper; 'flushable' wipes are not flushable."],"symptoms":["Bowl fills but won't drain","Water rises close to the rim","Gurgling from tub or sink when toilet flushes","Slow flush that eventually goes down"],"time_minutes":[15,30],"title":"Clogged toilet","tools":["Flange plunger","Toilet auger ($15, optional)"]},{"can_diy_diagnose":true,"can_diy_fix":true,"category":"appliances","clarifying_questions":["Is the freezer temperature at 0F?","When did the ice maker stop?","Is the water line to the fridge connected and the valve open?"],"difficulty":"easy","diy_cost":[0,40],"id":"ice-maker-not-working","keywords":["ice maker","no ice","fridge ice","water dispenser","freezer"],"likely_causes":["Freezer not cold enough (above 10F)","Water supply valve closed or line kinked","Clogged water filter","Frozen fill tube","Failed ice maker module"],"parts":["Replacement water filter ($20-40, if due)"],"pro_cost":[120,300],"safety_warnings":["Unplug the fridge before removing the ice maker module."],"severity":"minor","steps":["Confirm the freezer is at 0F - ice makers won't cycle above about 10F.","Check that the ice maker's on/off arm or switch is in the ON position.","Verify the saddle valve / water line behind the fridge is open and not kinked.","Replace the water filter if it's past due - low flow starves the ice maker.","If the fill tube is frozen, thaw it with a hair dryer on low; if the module itself is dead, replacement modules run $50-100 and swap in with a few screws."],"symptoms":["No ice production","Ice cubes smaller than normal","Water dispenser also weak or dead","Ice maker arm stuck in the off position"],"time_minutes":[20,40],"title":"Ice maker not making ice","tools":["Hair dryer (low heat)","Adjustable wrench"]},{"can_diy_diagnose":true,"can_diy_fix":"partial","category":"electrical","clarifying_questions":["One switch or the whole room?","Does the breaker for that room hold?","Any recent work done on that switch or fixture?"],"difficulty":"medium","diy_cost":[3,15],"id":"light-switch-not-working","keywords":["light switch","switch not working","light won't turn on","bulb","fixture"],"likely_causes":["Burned-out bulb","Failed switch","Tripped breaker","Loose wire on the switch","Failed light fixture"],"parts":["Replacement switch ($3-8)","Light bulbs"],"pro_cost":[100,200],"safety_warnings":["Turn off the breaker before removing a switch cover - not just the switch itself.","If you see scorched wires or melted insulation, stop and call an electrician."],"severity":"minor","steps":["Rule out the bulb first: try a known-good bulb.","Check the breaker panel.","With the breaker OFF, remove the switch cover and check for loose wire connections; tighten terminal screws.","If wiring looks fine, replace the switch itself - it's a $5 part and a 15-minute job: photograph the wiring before disconnecting.","If the new switch doesn't fix it, the fault is in the fixture or wiring - call an electrician."],"symptoms":["Light won't turn on at all","Switch feels loose or crackles","Light flickers when switch is touched","One switch dead while others in the room work"],"time_minutes":[15,30],"title":"Light switch not working","tools":["Screwdriver","Non-contact voltage tester ($15, recommended)"]}]""")
BY_ID = {g["id"]: g for g in GUIDES}

AMAZON_TAG = os.environ.get("FIXSNAP_AMAZON_TAG", "").strip()

def _clean_part_name(part):
    name = re.sub(r"\s*\([^)]*\)", "", str(part)).strip()
    return name or str(part).strip()

def _part_links(guide):
    links = []
    for part in guide.get("parts", []):
        name = _clean_part_name(part)
        url = "https://www.amazon.com/s?k=" + quote_plus(name)
        if AMAZON_TAG:
            url += "&tag=" + quote_plus(AMAZON_TAG)
        links.append({"name": name, "buy_search_url": url})
    return links
def _stem(w):
    if len(w) > 4 and w.endswith("ing"):
        w = w[:-3]
    elif len(w) > 3 and w.endswith("ed"):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("es"):
        w = w[:-2]
    elif len(w) > 2 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "aeiou":
        w = w[:-1]
    return w


def _words(t):
    return {_stem(w) for w in re.findall(r"[a-z0-9]+", (t or "").lower())}

def match(text, top_n=3):
    hay = _words(text or "")
    if not hay:
        return []
    scored = []
    for g in GUIDES:
        kw = _words(" ".join(g.get("keywords", [])))
        raw = 3.0 * len(hay & kw) + 2.0 * len(hay & _words(g.get("title", ""))) + 1.0 * len(hay & _words(" ".join(g.get("symptoms", []))))
        s = round(min(raw / (max(len(kw), 1) * 3.0), 1.0), 3)
        if s > 0:
            scored.append((g, s))
    scored.sort(key=lambda p: p[1], reverse=True)
    return scored[:top_n]

FIRE_SIGNS = {_stem(w) for w in ("scorch", "scorched", "charring", "charred", "melted", "melting", "sparking", "sparks", "smoke", "burn", "burned", "burnt", "burning", "blackened")}
ELECTRIC_CTX = {_stem(w) for w in ("outlet", "socket", "wiring", "wire", "breaker", "switch", "plug", "electrical", "circuit")}


def safety_override(text):
    """Visible fire/electrical damage always escalates to the pro-only
    electrical guide, whatever any matcher prefers."""
    words = _words(text)
    if words & FIRE_SIGNS and words & ELECTRIC_CTX:
        return BY_ID["tripping-breaker"]
    return None


def diagnose(notes):
    override = safety_override(notes)
    if override is not None:
        return override, 0.62, []
    matches = match(notes)
    if not matches:
        return None, 0.0, ["What room is the problem in?", "What do you see, hear, or smell?", "When did it start, and is it getting worse?"]
    g, s = matches[0]
    conf = round(min(0.35 + s * 0.5, 0.85), 3)
    return g, conf, (g.get("clarifying_questions", [])[:3] if conf < 0.5 else [])

VISION_MODEL = os.environ.get("FIXSNAP_VISION_MODEL", "gpt-4o-mini")
VISION_PROVIDER = os.environ.get("FIXSNAP_VISION_PROVIDER", "openai").strip().lower()
GEMINI_MODEL = os.environ.get("FIXSNAP_GEMINI_MODEL", "gemini-3.5-flash-lite")


GUIDE_CHOICES = "\n".join(
    "- " + g["id"] + ": " + g["title"] + " (what it looks like: " + "; ".join(g.get("symptoms", [])[:2]) + ")"
    for g in GUIDES
)


def _parse_vision(text):
    t = (text or "").strip()
    body = t
    if body.startswith("```"):
        body = body.strip("`")
        if body.lower().startswith("json"):
            body = body[4:]
    try:
        obj = json.loads(body)
        desc = str(obj.get("description") or "").strip()
        gid = str(obj.get("guide_id") or "").strip()
        return (desc or None), (gid if gid in BY_ID else None)
    except Exception:
        pass
    m = re.search(r'"guide_id"\s*:\s*"([^"]+)"', t)
    gid = m.group(1) if m and m.group(1) in BY_ID else None
    return (t or None), gid


def _vision_openai(prompt, url):
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    payload = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": url}},
                ],
            }
        ],
        "max_tokens": 300,
        "temperature": 0,
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            text = (data["choices"][0]["message"]["content"] or "").strip()
            if text:
                return text
        except Exception:
            pass
        if attempt < 2:
            time.sleep(1.5 * (attempt + 1))
    return None


def _vision_gemini(prompt, image_base64=None, mime_type="image/jpeg", image_url=None):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    raw = None
    if image_base64:
        raw = image_base64
        if raw.startswith("data:"):
            raw = raw.split(",", 1)[-1]
    elif image_url:
        try:
            with urllib.request.urlopen(image_url, timeout=20) as resp:
                raw = base64.b64encode(resp.read()).decode("utf-8")
        except Exception:
            return None
    if not raw:
        return None
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime_type or "image/jpeg", "data": raw}},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 300,
            "responseMimeType": "application/json",
        },
    }
    req = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models/" + GEMINI_MODEL + ":generateContent",
        data=json.dumps(payload).encode("utf-8"),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
            if text:
                return text
        except Exception:
            pass
        if attempt < 2:
            time.sleep(1.5 * (attempt + 1))
    return None


def vision_analyze(notes, image_url=None, image_base64=None, mime_type="image/jpeg"):
    """Read the photo with the configured vision provider.

    Provider is picked by FIXSNAP_VISION_PROVIDER ("openai" default, or
    "gemini" with GEMINI_API_KEY). Returns (description, guide_id) or
    (None, None) on any failure so the caller falls back to keyword matching.
    """
    if not (image_url or image_base64):
        return None, None
    if image_base64:
        url = image_base64
        if not url.startswith("data:"):
            url = "data:" + (mime_type or "image/jpeg") + ";base64," + url
    else:
        url = image_url
    prompt = (
        "You are the vision module of FixSnap, a home-repair assistant. "
        "Look at this photo. First describe, in 2-3 plain sentences, the home problem visible: "
        "which fixture or area it is, visible symptoms, and any safety hazard. "
        "Then choose the single best-matching repair guide from this list, by its id:\n"
        + GUIDE_CHOICES
        + "\nChoose the guide that matches the visible PROBLEM or symptom, not just an object that appears in the photo. "
        "If you see burn marks, scorching, melting, or sparking on any electrical item, choose tripping-breaker. "
        "If the problem is not clearly one of the listed guides, use \"none\" - do not pick the closest-sounding match. "
        "Respond with ONLY a JSON object: {\"description\": \"...\", \"guide_id\": \"...\"}."
        + ((" The user added these notes: " + notes) if notes else "")
    )
    text = None
    if VISION_PROVIDER == "gemini":
        text = _vision_gemini(prompt, image_base64=image_base64, mime_type=mime_type, image_url=image_url)
        if not text:
            text = _vision_openai(prompt, url)
    else:
        text = _vision_openai(prompt, url)
        if not text:
            text = _vision_gemini(prompt, image_base64=image_base64, mime_type=mime_type, image_url=image_url)
    if text:
        desc, gid = _parse_vision(text)
        if desc:
            return desc, gid
    return None, None


mcp = FastMCP(
    name="FixSnap",
    instructions=(
        "FixSnap diagnoses home problems from a photo and short notes. "
        "Always call diagnose_home_problem first when a user describes a home issue. "
        "Never invent repairs outside the returned guide. For gas, sparking/burning "
        "electrical, or structural damage, recommend a licensed professional - never DIY."
    ),
)

OUTCOMES = "/tmp/outcomes.jsonl"  # ephemeral on Spaces; use a DB for production

@mcp.custom_route("/.well-known/openai-apps-challenge", methods=["GET"], include_in_schema=False)
async def openai_apps_challenge(request):
    token = os.environ.get("OPENAI_APPS_CHALLENGE_TOKEN", "").strip()
    if not token:
        return PlainTextResponse("not configured", status_code=404)
    return PlainTextResponse(token)

@mcp.tool(title="Diagnose a home problem", annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=False, open_world_hint=True))
def diagnose_home_problem(notes: str = "", room: str = "", image_url: str | None = None, image_base64: str | None = None, mime_type: str = "image/jpeg") -> dict:
    """Diagnose a home problem from a photo and/or written notes."""
    vision_text, vision_gid = vision_analyze(notes, image_url, image_base64, mime_type)
    combined = ((vision_text or "") + " " + (notes or "")).strip()
    guide, conf, questions = diagnose(combined)
    if vision_gid and safety_override(combined) is None:
        # The vision model's own library pick beats the keyword matcher,
        # unless the electrical-fire safety override already fired.
        keywords = match(combined)
        guide = BY_ID[vision_gid]
        conf = 0.8 if keywords and keywords[0][0]["id"] == vision_gid else 0.66
        questions = []
    elif vision_text and (image_url or image_base64) and safety_override(combined) is None:
        # The vision model read the photo and picked no guide. Trust that
        # abstention: the photo description alone must not be keyword-matched
        # into a forced diagnosis (a cracked tile floor is not drywall).
        # The user's own notes may still carry a diagnosis on their own.
        note_guide, note_conf, note_questions = diagnose(notes or "")
        if note_guide is not None and note_conf >= 0.55:
            guide, conf, questions = note_guide, note_conf, note_questions
        else:
            guide, conf, questions = None, 0.0, ["What room is the problem in?", "What do you see, hear, or smell?", "When did it start, and is it getting worse?"]
    scan_id = uuid.uuid4().hex[:12]
    if guide is None:
        observed = ("Photo analysis: " + vision_text) if vision_text else "No symptoms described that match the guide library."
        return {"scan_id": scan_id, "likely_issue": None, "guide_id": None, "confidence": 0.0,
                "severity": "unknown", "can_diy_fix": False, "safety_warnings": [],
                "observed": observed,
                "clarifying_questions": questions,
                "next_step": "Answer the clarifying questions, then call diagnose_home_problem again."}
    if vision_text:
        observed = "Photo analysis: " + vision_text
    elif image_url or image_base64:
        observed = "Matched '" + guide["title"] + "' from described symptoms and the uploaded photo (demo mode: photo not machine-read)."
    else:
        observed = "Matched '" + guide["title"] + "' from described symptoms."
    return {"scan_id": scan_id, "likely_issue": guide["title"], "guide_id": guide["id"],
            "confidence": conf, "severity": guide["severity"], "can_diy_fix": guide["can_diy_fix"],
            "safety_warnings": guide.get("safety_warnings", []),
            "observed": observed,
            "likely_causes": guide.get("likely_causes", [])[:4],
            "clarifying_questions": questions,
            "next_step": "Call get_fix_guide with this guide_id for the step-by-step repair, or estimate_costs for DIY vs pro pricing."}

@mcp.tool(title="Get a step-by-step fix guide", annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False))
def get_fix_guide(guide_id: str) -> dict:
    """Return the full step-by-step repair guide for a diagnosed issue."""
    g = BY_ID.get(guide_id)
    return g if g else {"error": "Unknown guide_id. Call browse_guides to list valid ids."}

@mcp.tool(title="Estimate DIY vs pro cost", annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False))
def estimate_costs(guide_id: str, zip_code: str | None = None) -> dict:
    """Estimate DIY parts cost vs a fair professional price for an issue."""
    g = BY_ID.get(guide_id)
    if not g:
        return {"error": "Unknown guide_id."}
    d, p = g.get("diy_cost", [0, 0]), g.get("pro_cost", [0, 0])
    return {"issue": g["title"], "diy_parts_estimate_usd": {"low": d[0], "high": d[1]},
            "fair_pro_price_usd": {"low": p[0], "high": p[1]}, "parts_needed": _part_links(g), "zip_code": zip_code,
            "note": "DIY covers parts only. Pro range is a US national ballpark - get 2-3 local quotes.",
            "estimated_at": datetime.now(timezone.utc).isoformat()}

@mcp.tool(title="Log repair outcome", annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False))
def log_outcome(scan_id: str, fixed: bool, method: str = "", notes: str = "") -> dict:
    """Log whether the suggested fix worked."""
    with open(OUTCOMES, "a", encoding="utf-8") as f:
        f.write(json.dumps({"scan_id": scan_id, "fixed": fixed, "method": method, "notes": notes,
                            "logged_at": datetime.now(timezone.utc).isoformat()}) + "\n")
    return {"ok": True, "scan_id": scan_id, "message": "Outcome logged. Thank you!"}

@mcp.tool(title="Browse repair guides", annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False))
def browse_guides(category: str | None = None) -> dict:
    """List available repair guides, optionally filtered by category."""
    gs = [g for g in GUIDES if not category or g["category"] == category.lower()]
    return {"count": len(gs), "categories": sorted({g["category"] for g in GUIDES}),
            "guides": [{"id": g["id"], "title": g["title"], "category": g["category"]} for g in gs]}

@mcp.resource("fixsnap://guides")
def guides_resource() -> str:
    """The full curated FixSnap guide catalog."""
    return json.dumps(GUIDES, indent=2)

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", "7860")), path="/mcp")
