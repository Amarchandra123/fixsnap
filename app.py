"""FixSnap - single-file MCP server (Hugging Face Spaces deploy).

Same 5 tools as the full server in ../server, packaged as one file.
Runs on the keyword adapter by default; set OPENAI_API_KEY for real vision.
"""

import json
import os
import re
import uuid
import urllib.error
import urllib.request
from datetime import datetime, timezone

# Disable FastMCP's PyPI version check on startup (can abort in sandbox/prod).
import fastmcp.utilities.version_check as _vc

_vc.check_for_newer_version = lambda *a, **k: None

from fastmcp import FastMCP

GUIDES = json.loads(r"""[{"can_diy_diagnose":true,"can_diy_fix":"partial","category":"moisture","clarifying_questions":["Is there a bathroom or roof directly above the stain?","Does the stain get darker or grow after rain?","Is the spot damp to the touch right now?"],"difficulty":"medium","diy_cost":[15,40],"id":"ceiling-water-stain","keywords":["ceiling","stain","brown","yellow","water stain","roof","discoloration","spot on ceiling"],"likely_causes":["Roof leak above the stain","Plumbing leak from bathroom above","Condensation from uninsulated duct","Ice dam (cold climates)"],"parts":["Oil-based stain-blocking primer","Ceiling paint"],"pro_cost":[200,600],"safety_warnings":["Do not cut into a sagging, water-logged ceiling section \u2014 it can collapse.","If water is actively dripping near light fixtures, turn off the breaker for that circuit."],"severity":"urgent","steps":["Determine if the leak is active: press a paper towel to the stain; check again after rain or after running upstairs plumbing.","If a bathroom is above, run each fixture (shower, toilet, sink) one at a time and watch for new dampness.","For roof leaks, inspect the attic above the stain during rain with a flashlight; look for wet decking or drip trails.","Once the source is fixed and the area is fully dry (2-3 dry days), seal the stain with oil-based stain-blocking primer.","Repaint with matching ceiling paint."],"symptoms":["Brown or yellowish ring/spot on ceiling","Stain grows after rain","Paint bubbling or peeling around stain","Musty smell in room"],"time_minutes":[60,180],"title":"Brown water stain on ceiling","tools":["Flashlight","Ladder","Moisture meter (optional, ~$25)"]},{"can_diy_diagnose":true,"can_diy_fix":"partial","category":"hvac","clarifying_questions":["When did you last change the air filter?","Is there ice visible on the copper lines at the indoor or outdoor unit?","Is the outdoor unit's fan spinning?"],"difficulty":"easy","diy_cost":[10,30],"id":"ac-blowing-warm","keywords":["ac","air conditioner","warm air","not cooling","hot air","hvac","thermostat"],"likely_causes":["Clogged air filter choking airflow","Thermostat set wrong or miscalibrated","Low refrigerant from a leak","Dirty condenser coils","Failed capacitor or contactor"],"parts":["Air filter ($10-25)"],"pro_cost":[150,500],"safety_warnings":["Turn off power at the breaker before touching anything inside the units.","Refrigerant handling requires an EPA-licensed technician \u2014 never attempt a recharge yourself."],"severity":"urgent","steps":["Check thermostat: set to COOL, fan to AUTO, setpoint at least 3 degrees below room temp.","Replace a dirty air filter; if coils iced over, turn AC off and run fan-only for 2-4 hours to thaw.","Clear debris, grass, and leaves from around the outdoor condenser (2 ft clearance); gently rinse coils with a hose.","Check the breaker for the outdoor unit; reset once if tripped.","If still warm after these steps, call a technician \u2014 likely refrigerant leak or electrical component failure."],"symptoms":["Vents blow room-temperature or warm air","AC runs constantly but house won't cool","Ice on indoor or outdoor unit lines","Thermostat set to cool but temp not dropping"],"time_minutes":[20,60],"title":"AC blowing warm air","tools":["Replacement air filter (correct size)","Garden hose"]},{"can_diy_diagnose":true,"can_diy_fix":true,"category":"plumbing","clarifying_questions":["Is the buildup on hot-water fixtures, cold, or both?","Do you notice spots on dishes or a film on glassware?","Has water flow from the showerhead decreased?"],"difficulty":"easy","diy_cost":[3,15],"id":"hard-water-limescale","keywords":["limescale","hard water","white crust","calcium","faucet","showerhead","mineral"],"likely_causes":["Hard water with high calcium/magnesium","No water softener installed","Aging aerators clogged with mineral deposits"],"parts":["Replacement aerators ($5-10, optional)"],"pro_cost":[100,250],"safety_warnings":["Do not use vinegar on natural stone (marble, granite) \u2014 it etches the surface."],"severity":"minor","steps":["Soak a cloth in white vinegar and wrap it around the fixture for 30-60 minutes, or fill a bag with vinegar and tie it over a showerhead.","Scrub with an old toothbrush; rinse thoroughly.","Unscrew faucet aerators and soak them in vinegar, then reinstall.","For persistent whole-house hard water, get a water hardness test strip and consider a softener."],"symptoms":["White chalky buildup on faucets and showerheads","Spots on dishes and glass after washing","Reduced water flow from showerhead","Stiff faucet handles"],"time_minutes":[30,90],"title":"White crusty limescale on faucets and fixtures","tools":["White vinegar","Plastic bag and rubber band","Old toothbrush","Adjustable wrench"]},{"can_diy_diagnose":true,"can_diy_fix":true,"category":"plumbing","clarifying_questions":["If you lift the tank lid, is water flowing into the overflow tube?","Does jiggling the handle stop it temporarily?","How old is the toilet?"],"difficulty":"easy","diy_cost":[5,20],"id":"running-toilet","keywords":["toilet","running","toilet keeps running","water running","tank","flapper","fill valve"],"likely_causes":["Worn flapper not sealing","Fill valve not shutting off","Chain too short or tangled","Water level set too high, draining into overflow tube"],"parts":["Flapper ($5-10)","Universal fill valve ($12-18, if needed)","Food coloring for dye test"],"pro_cost":[120,250],"safety_warnings":["Turn off the supply valve behind the toilet before replacing internal parts."],"severity":"minor","steps":["Remove the tank lid and observe: water flowing into the overflow tube means the fill valve or water level is the issue.","Do the dye test: add food coloring to the tank, wait 15 minutes without flushing. Color in the bowl = leaking flapper.","Replace the flapper (match size: 2 in or 3 in) if it is warped or doesn't seal; adjust or replace the chain so it has slight slack.","Adjust the fill valve so water stops about 1 inch below the top of the overflow tube.","If the fill valve hisses or won't shut off, replace it \u2014 a universal fill valve costs under $15."],"symptoms":["Water runs continuously into the bowl","Tank refills every few minutes on its own","Hissing sound from the tank","Higher water bill"],"time_minutes":[20,45],"title":"Toilet running constantly","tools":["Sponge and bucket","Adjustable wrench"]},{"can_diy_diagnose":true,"can_diy_fix":"partial","category":"plumbing","clarifying_questions":["How old is the water heater? (check the serial label)","Is the rumbling new or long-standing?","Is there any water pooling at the base of the tank?"],"difficulty":"medium","diy_cost":[0,40],"id":"water-heater-rumbling","keywords":["water heater","rumbling","popping","no hot water","sediment","hot water runs out"],"likely_causes":["Sediment buildup on the tank bottom","Failing heating element (electric) or thermocouple (gas)","Thermostat set too low or failed","Tank corrosion / end of life (8-12 years)"],"parts":["Heating element ($20-40, if electric and failed)"],"pro_cost":[200,1800],"safety_warnings":["Water pooling at the tank base means the tank is failing \u2014 it can burst and flood. Shut off water and call a plumber promptly.","Gas water heaters: if you smell gas, leave the house and call the gas company \u2014 do not troubleshoot."],"severity":"urgent","steps":["Check the age on the serial label. Over 10 years with rumbling: plan for replacement rather than repair.","Flush sediment: turn off power/gas and cold water supply, attach a hose to the drain valve, and drain until water runs clear.","For electric heaters with no hot water: after turning off the breaker, test the heating elements with a multimeter.","Set thermostat to 120F (49C) \u2014 hotter wastes energy and risks scalding.","If the tank leaks from the body (not a fitting), it must be replaced \u2014 no repair is reliable."],"symptoms":["Rumbling, popping, or banging from the tank","Hot water runs out faster than it used to","Rusty or cloudy hot water","Water leaking at the tank base"],"time_minutes":[45,120],"title":"Water heater rumbling / running out of hot water","tools":["Garden hose","Bucket","Multimeter (for electric units)"]},{"can_diy_diagnose":true,"can_diy_fix":true,"category":"appliances","clarifying_questions":["Does it hum, or is it completely silent?","Did it stop after something hard went down (bone, pit, utensil)?","Is the reset button on the bottom popped out?"],"difficulty":"easy","diy_cost":[0,0],"id":"garbage-disposal-humming","keywords":["garbage disposal","disposal","humming","jammed","sink","kitchen"],"likely_causes":["Jam: object wedged between impellers","Tripped overload / reset button","Tripped GFCI outlet or breaker","Motor burned out (old unit)"],"parts":[],"pro_cost":[120,350],"safety_warnings":["NEVER put your hand inside a disposal, even when it seems dead. Always unplug it or switch off the breaker first."],"severity":"minor","steps":["Turn the switch OFF, then unplug the disposal (or switch off its breaker).","Press the red reset button on the bottom of the unit.","Insert the hex wrench (usually taped under the sink or in the manual) into the bottom socket and work it back and forth to free the jam.","Shine a flashlight inside and remove the lodged object with tongs or pliers \u2014 never fingers.","Restore power and test with cold water running. If it hums then goes silent again, the motor is likely shot."],"symptoms":["Disposal hums when switched on but blades don't spin","Disposal completely dead (no sound)","Water backing up in the sink","Reset button popped out"],"time_minutes":[15,30],"title":"Garbage disposal humming but not grinding","tools":["Hex/Allen wrench (1/4 in, usually supplied)","Flashlight","Tongs or pliers"]},{"can_diy_diagnose":true,"can_diy_fix":false,"category":"electrical","clarifying_questions":["Does it trip immediately when reset, or after some time?","What was running when it tripped (space heater, hair dryer, AC)?","Any burning smell or scorch marks on outlets?"],"difficulty":"pro-only","diy_cost":[0,0],"id":"tripping-breaker","keywords":["breaker","tripping","circuit breaker","power out","outlet dead","electrical","sparking","burning smell"],"likely_causes":["Overloaded circuit (too many high-draw devices)","Short circuit in wiring or an appliance","Ground fault","Failing breaker"],"parts":[],"pro_cost":[150,450],"safety_warnings":["If you smell burning or see scorch marks, turn off the main breaker and call an electrician immediately - this is a fire risk.","Never replace a breaker with a higher amperage one; the wiring is rated for the original size.","Repeatedly resetting a tripping breaker without finding the cause is dangerous."],"severity":"emergency","steps":["Unplug everything on the dead circuit, then reset the breaker ONCE.","If it holds, plug items back in one at a time to find the culprit; move high-draw devices to different circuits.","If it trips immediately with everything unplugged, stop - the fault is in the wiring.","Call a licensed electrician. Tell them whether it trips instantly (likely short) or under load (likely overload)."],"symptoms":["Breaker trips repeatedly","Breaker trips the moment you reset it","Burning smell near outlets or panel","Scorch marks on outlet covers","Lights flicker before the trip"],"time_minutes":[0,0],"title":"Circuit breaker keeps tripping","tools":[]},{"can_diy_diagnose":true,"can_diy_fix":true,"category":"appliances","clarifying_questions":["When did you last clean the lint filter and the vent?","Is the outside vent flap opening when the dryer runs?","Does the dryer get hot at all?"],"difficulty":"easy","diy_cost":[0,25],"id":"dryer-two-cycles","keywords":["dryer","clothes not drying","two cycles","lint","vent","takes long to dry"],"likely_causes":["Clogged dryer vent duct (fire hazard)","Lint filter or internal lint buildup","Failed heating element or thermal fuse","Dryer overloaded"],"parts":["Vent cleaning brush kit ($15-25, optional)"],"pro_cost":[100,250],"safety_warnings":["A clogged dryer vent is one of the leading causes of house fires. Clean it at least yearly.","Unplug the dryer (or turn off the breaker, and shut off gas for gas dryers) before pulling it out or opening panels."],"severity":"urgent","steps":["Clean the lint filter thoroughly; wash it with soap and water if fabric softener residue coats it.","Pull the dryer out, detach the vent duct, and vacuum/shake out all lint.","Go outside: confirm the vent flap opens freely during a cycle and exhaust air feels strong.","Check that the duct is rigid metal or flexible metal - replace white vinyl or foil accordion duct, which traps lint.","If airflow is strong but no heat, the thermal fuse or heating element likely failed - that's a pro or confident-DIY part replacement."],"symptoms":["Clothes need two cycles to dry","Dryer exterior very hot to the touch","Burning smell during drying","Vent flap outside barely opens","Dryer runs but produces no heat"],"time_minutes":[30,60],"title":"Dryer needs two cycles to dry clothes","tools":["Vacuum with hose attachment","Screwdriver"]},{"can_diy_diagnose":true,"can_diy_fix":true,"category":"plumbing","clarifying_questions":["Bathroom sink, kitchen sink, or tub?","Does it drain slowly or is it fully stopped?","Have you tried a plunger yet?"],"difficulty":"easy","diy_cost":[0,15],"id":"clogged-drain","keywords":["clogged","drain","slow drain","sink clogged","tub","standing water"],"likely_causes":["Hair and soap buildup (bathroom)","Grease and food (kitchen)","Foreign object lodged in trap","Vent stack blockage (multiple fixtures slow)"],"parts":["Drain snake / hair removal tool ($5-15)"],"pro_cost":[100,300],"safety_warnings":["Do not use chemical drain cleaners on a fully stopped drain - caustic water can splash back. Enzyme cleaners are safer for maintenance.","If multiple fixtures back up at once, the main line may be blocked - call a plumber, don't keep plunging."],"severity":"minor","steps":["Remove and clean the drain stopper; pull out hair with a plastic drain snake tool.","Try a plunger with enough water to cover the cup; seal the overflow with a wet rag for better pressure.","For kitchen sinks, pour a kettle of near-boiling water followed by dish soap to cut grease (not on PVC pipes - use hot tap water instead).","If still slow, remove and clean the P-trap under the sink with a bucket underneath.","Still clogged after the trap? The blockage is deeper - use a 25-ft hand auger or call a pro."],"symptoms":["Water drains slowly","Standing water in sink or tub","Gurgling sounds from the drain","Bad odor from the drain"],"time_minutes":[20,60],"title":"Clogged or slow bathroom/kitchen drain","tools":["Plunger","Plastic drain snake","Bucket","Adjustable wrench"]},{"can_diy_diagnose":true,"can_diy_fix":"partial","category":"appliances","clarifying_questions":["Is the fridge warm but the freezer still cold?","Can you hear the compressor running?","When did you last clean the condenser coils?"],"difficulty":"medium","diy_cost":[0,30],"id":"fridge-not-cooling","keywords":["refrigerator","fridge","not cooling","warm fridge","freezer","compressor"],"likely_causes":["Dirty condenser coils","Blocked air vents inside from overpacking","Failed evaporator fan","Faulty thermostat or defrost system","Refrigerant leak (rare)"],"parts":["Appliance thermometer ($8, optional)"],"pro_cost":[150,400],"safety_warnings":["Unplug the fridge before cleaning coils or accessing the compressor area."],"severity":"urgent","steps":["Check the temperature with a thermometer: fridge should be 37-40F, freezer 0F.","Pull the fridge out and vacuum the condenser coils (front grille or back panel) - dirty coils are the #1 cause.","Make sure interior vents aren't blocked by food; leave space for air circulation.","Listen: if the compressor never runs, check the thermostat setting and the start relay.","If coils are clean, vents clear, and it's still warm after 24 hours, call a technician."],"symptoms":["Fridge section warm, freezer may still be cold","Compressor runs constantly","Food spoiling faster than normal","Frost buildup in the freezer"],"time_minutes":[30,60],"title":"Refrigerator not cooling properly","tools":["Vacuum with brush attachment","Coil brush ($10, optional)"]}]""")
BY_ID = {g["id"]: g for g in GUIDES}
_words = lambda t: set(re.findall(r"[a-z0-9]+", t.lower()))

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

def diagnose(notes):
    matches = match(notes)
    if not matches:
        return None, 0.0, ["What room is the problem in?", "What do you see, hear, or smell?", "When did it start, and is it getting worse?"]
    g, s = matches[0]
    conf = round(min(0.35 + s * 0.5, 0.85), 3)
    return g, conf, (g.get("clarifying_questions", [])[:3] if conf < 0.5 else [])

VISION_MODEL = os.environ.get("FIXSNAP_VISION_MODEL", "gpt-4o-mini")


def vision_describe(notes, image_url=None, image_base64=None, mime_type="image/jpeg"):
    """Read the photo with a vision model when OPENAI_API_KEY is set.

    Returns a short plain-language description of the visible problem, or None
    to fall back to keyword matching. Never raises: no key, a bad image, or an
    API error all just return None.
    """
    key = os.environ.get("OPENAI_API_KEY")
    if not key or not (image_url or image_base64):
        return None
    if image_base64:
        url = image_base64
        if not url.startswith("data:"):
            url = "data:" + (mime_type or "image/jpeg") + ";base64," + url
    else:
        url = image_url
    prompt = (
        "You are the vision module of FixSnap, a home-repair assistant. "
        "Look at this photo and describe, in 2-4 plain sentences, the home problem visible: "
        "which fixture or area it is, visible symptoms (water, stains, rust, damage, leaks, scorching), "
        "and any safety hazard. Use simple symptom words a repair guide would use."
        + ((" The user added these notes: " + notes) if notes else "")
    )
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
        "max_tokens": 220,
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = (data["choices"][0]["message"]["content"] or "").strip()
        return text or None
    except Exception:
        return None


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

@mcp.tool
def diagnose_home_problem(notes: str, room: str = "", image_url: str | None = None, image_base64: str | None = None, mime_type: str = "image/jpeg") -> dict:
    """Diagnose a home problem from a photo and/or written notes."""
    vision_text = vision_describe(notes, image_url, image_base64, mime_type)
    combined = ((vision_text or "") + " " + (notes or "")).strip()
    guide, conf, questions = diagnose(combined)
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

@mcp.tool
def get_fix_guide(guide_id: str) -> dict:
    """Return the full step-by-step repair guide for a diagnosed issue."""
    g = BY_ID.get(guide_id)
    return g if g else {"error": "Unknown guide_id. Call browse_guides to list valid ids."}

@mcp.tool
def estimate_costs(guide_id: str, zip_code: str | None = None) -> dict:
    """Estimate DIY parts cost vs a fair professional price for an issue."""
    g = BY_ID.get(guide_id)
    if not g:
        return {"error": "Unknown guide_id."}
    d, p = g.get("diy_cost", [0, 0]), g.get("pro_cost", [0, 0])
    return {"issue": g["title"], "diy_parts_estimate_usd": {"low": d[0], "high": d[1]},
            "fair_pro_price_usd": {"low": p[0], "high": p[1]}, "zip_code": zip_code,
            "note": "DIY covers parts only. Pro range is a US national ballpark - get 2-3 local quotes.",
            "estimated_at": datetime.now(timezone.utc).isoformat()}

@mcp.tool
def log_outcome(scan_id: str, fixed: bool, method: str = "", notes: str = "") -> dict:
    """Log whether the suggested fix worked."""
    with open(OUTCOMES, "a", encoding="utf-8") as f:
        f.write(json.dumps({"scan_id": scan_id, "fixed": fixed, "method": method, "notes": notes,
                            "logged_at": datetime.now(timezone.utc).isoformat()}) + "\n")
    return {"ok": True, "scan_id": scan_id, "message": "Outcome logged. Thank you!"}

@mcp.tool
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
