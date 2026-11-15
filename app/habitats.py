"""
Crew environments ("habitats") from the challenge brief, with their design atmospheres.
Values match assets/js/data.js (MISSION_ENVIRONMENTS) so both backends rank against the same targets.
Sources: NASA Space Apps 2026 "Flame in Freefall" challenge text (Moon Base: >=30% O2 at <=10.2 psi;
spacesuit: 100% O2 at 4.3 psi) and NASA exploration atmosphere studies.
"""

HABITATS = [
    {"id": "spacecraft", "label": "Spacecraft", "examples": "Crew capsules in transit (Orion, Artemis)", "o2": 21.0, "pressure": 101.3, "gravity": 0.0,
     "flow": 10.0, "volume": "small",
     "note": "Sea-level air in a sealed, ventilated cabin far from rescue; the Artemis II crew heard a smoke alarm about 80,000 miles from home."},
    {"id": "station", "label": "Space station", "examples": "ISS, Gateway", "o2": 21.0, "pressure": 101.3, "gravity": 0.0, "flow": 10.0, "volume": "large",
     "note": "Long-duration microgravity with forced ventilation; a fire from an oxygen generator failure occurred aboard Mir."},
    {"id": "moonbase", "label": "Lunar surface base", "examples": "Moon Base", "o2": 30.0, "pressure": 70.3, "gravity": 0.165, "flow": 5.0, "volume": "large",
     "note": "Expected >=30% O2 at <=10.2 psi to shorten spacesuit pre-breathing: more than 40% more oxygen than Earth's atmosphere."},
    {"id": "rover", "label": "Pressurized rover", "examples": "Lunar pressurized rover", "o2": 30.0, "pressure": 70.3, "gravity": 0.165, "flow": 10.0,
     "volume": "small", "note": "Same intermediate atmosphere as the Moon Base in a small, crowded volume where a fire escalates fast."},
    {"id": "marsbase", "label": "Martian surface base", "examples": "Future Mars habitats", "o2": 30.0, "pressure": 70.3, "gravity": 0.38, "flow": 5.0,
     "volume": "large", "note": "Atmosphere not yet defined; assumed here to match the lunar intermediate atmosphere."},
    {"id": "spacesuit", "label": "Spacesuit & airlock", "examples": "EVA suits, pre-breathe", "o2": 100.0, "pressure": 29.6, "gravity": 0.165, "flow": 0.0,
     "volume": "small", "note": "100% oxygen at 4.3 psi; astronauts pre-breathe pure oxygen to avoid the bends."},
]
BY_ID = {h["id"]: h for h in HABITATS}

# NASA fire-safety pillars, and which PSI investigations address each (curated; matches assets/js/data.js PROFILES).
PILLARS = {
    "prevention": "Material flammability, ignition and spread: keep a fire from starting or growing.",
    "detection": "Smoke and fire signatures: find a fire early without false alarms.",
    "suppression": "Extinguishing agents, dilution and cleanup after a fire.",
}
PILLAR_OF = {
    "PSI-10": ["detection", "prevention"], "PSI-20": ["prevention"], "PSI-21": ["prevention", "detection"], "PSI-22": ["suppression", "detection"],
    "PSI-23": ["prevention"], "PSI-25": ["prevention"], "PSI-26": ["prevention", "suppression"], "PSI-39": ["detection", "prevention"],
    "PSI-47": ["detection"], "PSI-60": ["detection"], "PSI-62": ["prevention"], "PSI-68": ["suppression", "prevention"],
    "PSI-69": ["suppression", "detection"], "PSI-98": ["prevention"], "PSI-99": ["prevention"], "PSI-100": ["prevention", "detection"],
    "PSI-101": ["detection"], "PSI-102": ["detection"], "PSI-106": ["prevention"], "PSI-107": ["detection"], "PSI-115": ["detection"],
    "PSI-117": ["prevention"], "PSI-142": ["prevention"], "PSI-159": ["prevention", "detection"],
}
LARGE_SCALE = {"PSI-98", "PSI-99", "PSI-100"}          # Saffire: spacecraft-scale fires aboard Cygnus
PARTIAL_GRAVITY_PROXY = {"PSI-22"}                     # ACME E-FIELD Flames: electric-field body forces mimic buoyancy
