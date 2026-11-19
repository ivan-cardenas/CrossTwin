"""
The person PET is felt by (urban_heat/solweig/pipeline.py::urban_pet): body,
activity, posture and clothing, and the values derived from them.

PET is the air temperature of a reference room at which *this* person would
have the same skin and core temperature as outdoors, so a PET map holds for one
person only. The Thermal Comfort tool's person pill (SolweigTool.js) sets the
person; the run stores it (`ThermalComfortRun.person`) and the heat dashboard's
PET card names it.

Clothing insulation is the sum of the garments' insulation values,
Icl = sum(Iclu,i) (ASHRAE 55-2020 §5.2.2.2, Table 5.2.2.2B; ISO 7730:2005
Annex C for the outdoor coats), the summation method both standards give for
ensembles (about ±20 %). Metabolic rates are ISO 8996 / ASHRAE 55 Table
5.2.1.2 values; 1.37 met (80 W of activity on top of the basal rate) is Höppe's
PET reference. Body surface area is DuBois & DuBois (1916), the area
pythermalcomfort's PET model uses.

Pure: no ORM, no clock. `STANDARD_PERSON` is the person of every run made
before persons could be chosen (run.person empty), so their results keep
their meaning.
"""

# 1 met = 58.15 W/m² (ISO 8996, ASHRAE 55).
W_PER_M2_PER_MET = 58.15

# Höppe (1999) PET reference person. pythermalcomfort's pet_steady defaults to
# a seated posture, which is what runs without a stored person used.
STANDARD_PERSON = {"met": 1.37, "clo": 0.9, "age": 35, "weight": 75, "height": 1.75,
                   "sex": "male", "position": "sitting"}

SEXES = ("male", "female")
POSITIONS = ("standing", "sitting")

# Accepted ranges (validated at the request; pythermalcomfort solves outside them but
# the PET equations were fitted to adults in this range).
LIMITS = {
    "age": (5, 100, "years"),
    "weight": (20.0, 200.0, "kg"),
    "height": (1.0, 2.2, "m"),
    "met": (0.8, 4.0, "met"),
    "clo": (0.0, 3.0, "clo"),
}

# key: (label, met, posture). ISO 8996:2021 / ASHRAE 55-2020 Table 5.2.1.2; the PET reference is Höppe (1999).
ACTIVITIES = {
    "seated": ("Seated, quiet", 1.0, "sitting"),
    "standing": ("Standing, relaxed", 1.2, "standing"),
    "reference": ("Light activity (PET reference, 80 W)", 1.37, "sitting"),
    "walk_slow": ("Walking 3.2 km/h", 2.0, "standing"),
    "walk": ("Walking 4.3 km/h", 2.6, "standing"),
    "walk_fast": ("Walking 6.4 km/h", 3.8, "standing"),
}

# key: (group, label, Iclu in clo). ASHRAE 55-2020 Table 5.2.2.2B, except the
# outdoor coats (ISO 7730:2005 Table C.2).
GARMENTS = {
    "briefs": ("Underwear", "Briefs / panties", 0.04),
    "bra": ("Underwear", "Bra", 0.01),
    "t_shirt": ("Underwear", "T-shirt", 0.08),
    "sleeveless_blouse": ("Tops", "Sleeveless blouse", 0.12),
    "short_sleeve_shirt": ("Tops", "Short-sleeve shirt", 0.19),
    "long_sleeve_shirt": ("Tops", "Long-sleeve shirt", 0.25),
    "sweatshirt": ("Tops", "Long-sleeve sweatshirt", 0.34),
    "short_shorts": ("Legs", "Short shorts", 0.06),
    "walking_shorts": ("Legs", "Walking shorts", 0.08),
    "trousers_thin": ("Legs", "Trousers, thin", 0.15),
    "trousers_thick": ("Legs", "Trousers, thick", 0.24),
    "skirt_thin": ("Legs", "Skirt, thin", 0.14),
    "skirt_thick": ("Legs", "Skirt, thick", 0.23),
    "dress_sleeveless": ("Dresses", "Sleeveless dress, thin", 0.23),
    "dress_short_sleeve": ("Dresses", "Short-sleeve dress, thin", 0.29),
    "sweater_thin": ("Layers", "Long-sleeve sweater, thin", 0.25),
    "sweater_thick": ("Layers", "Long-sleeve sweater, thick", 0.36),
    "jacket_thin": ("Layers", "Jacket, thin", 0.36),
    "jacket_thick": ("Layers", "Jacket, thick", 0.44),
    "down_jacket": ("Outdoor", "Down jacket", 0.55),
    "coat": ("Outdoor", "Coat", 0.60),
    "parka": ("Outdoor", "Parka", 0.70),
    "ankle_socks": ("Feet", "Ankle socks", 0.02),
    "calf_socks": ("Feet", "Calf-length socks", 0.03),
    "sandals": ("Feet", "Sandals", 0.02),
    "shoes": ("Feet", "Shoes", 0.02),
    "boots": ("Feet", "Boots", 0.10),
}

# Ready-made people. `garments` None = the clo is given (the PET reference).
PRESETS = {
    # The 'reference' activity is STANDARD_PERSON's met and posture.
    "standard": {"label": "PET reference person (Höppe 1999)", "garments": None, "clo": 0.9,
                 "age": 35, "sex": "male", "weight": 75, "height": 1.75, "activity": "reference"},
    "summer_walker": {"label": "Summer walker", "garments": ["briefs", "t_shirt", "walking_shorts", "sandals"],
                      "age": 35, "sex": "female", "weight": 60, "height": 1.65, "activity": "walk_slow"},
    "office": {"label": "Office worker, summer", "garments": ["briefs", "short_sleeve_shirt", "trousers_thin",
                                                               "calf_socks", "shoes"],
               "age": 40, "sex": "male", "weight": 80, "height": 1.80, "activity": "walk"},
    "older_seated": {"label": "Older person on a bench", "garments": ["briefs", "bra", "long_sleeve_shirt",
                                                                       "trousers_thin", "calf_socks", "shoes"],
                     "age": 75, "sex": "female", "weight": 65, "height": 1.62, "activity": "seated"},
    "child": {"label": "Child playing", "garments": ["briefs", "t_shirt", "short_shorts", "sandals"],
              "age": 8, "sex": "male", "weight": 26, "height": 1.28, "activity": "walk"},
    "winter": {"label": "Winter walker", "garments": ["briefs", "t_shirt", "long_sleeve_shirt", "trousers_thick",
                                                       "sweater_thick", "coat", "calf_socks", "boots"],
               "age": 35, "sex": "male", "weight": 75, "height": 1.75, "activity": "walk"},
}


class PersonError(ValueError):
    pass


def clothing_clo(garments):
    """Icl [clo] = sum of the garments' Iclu (ASHRAE 55-2020 §5.2.2.2). Unknown keys raise PersonError."""
    unknown = [g for g in garments if g not in GARMENTS]
    if unknown:
        raise PersonError(f"Unknown garment(s): {', '.join(unknown)}.")
    return round(sum(GARMENTS[g][2] for g in dict.fromkeys(garments)), 2)


def body_surface_area(weight_kg, height_m):
    """DuBois & DuBois (1916): A_Du [m²] = 0.203 W^0.425 H^0.725."""
    return 0.203 * weight_kg ** 0.425 * height_m ** 0.725


def resolve(data=None):
    """
    The person of a run from request values (a dict of strings or numbers).
    Missing values come from the preset (`preset`, default 'standard'), then
    from STANDARD_PERSON. `garments` (list, or comma-separated text) sets clo by
    summation and wins over a given `clo`; `activity` sets met and posture
    unless `met` / `position` are given. Raises PersonError on a bad value.

    Returns the stored dict: met, clo, age, sex, weight, height, position
    (the pet_steady keyword arguments) plus activity, garments and preset.
    """
    data = dict(data or {})
    preset_key = data.get("preset") or "standard"
    if preset_key not in PRESETS:
        raise PersonError(f"Unknown person preset: {preset_key}.")
    preset = PRESETS[preset_key]

    def pick(name):
        value = data.get(name)
        return preset.get(name, STANDARD_PERSON.get(name)) if value in (None, "") else value

    activity = pick("activity")
    if activity not in ACTIVITIES:
        raise PersonError(f"Unknown activity: {activity}.")
    _label, activity_met, activity_position = ACTIVITIES[activity]

    garments = data.get("garments", preset.get("garments"))
    if isinstance(garments, str):
        garments = [g for g in (s.strip() for s in garments.split(",")) if g]
    if garments:
        garments = list(dict.fromkeys(garments))
        clo = clothing_clo(garments)
    else:
        garments = None
        clo = pick("clo")

    person = {
        "met": activity_met if data.get("met") in (None, "") else data["met"],
        "clo": clo,
        "age": pick("age"),
        "weight": pick("weight"),
        "height": pick("height"),
        "sex": pick("sex"),
        "position": data.get("position") or activity_position,
    }
    for name, (low, high, unit) in LIMITS.items():
        try:
            value = float(person[name])
        except (TypeError, ValueError):
            raise PersonError(f"{name} must be a number ({unit}).") from None
        if not low <= value <= high:
            raise PersonError(f"{name} must be between {low:g} and {high:g} {unit}.")
        person[name] = round(value, 2)
    person["age"] = int(round(person["age"]))
    if person["sex"] not in SEXES:
        raise PersonError(f"sex must be one of {', '.join(SEXES)}.")
    if person["position"] not in POSITIONS:
        raise PersonError(f"position must be one of {', '.join(POSITIONS)}.")
    return {**person, "activity": activity, "garments": garments, "preset": preset_key}


def pet_kwargs(person=None):
    """The pet_steady keyword arguments of a stored person (None/{} = STANDARD_PERSON)."""
    person = person or STANDARD_PERSON
    return {key: person[key] for key in STANDARD_PERSON}


def describe(person=None):
    """
    Display values of a person: clo, met, body surface area, BMI, metabolic
    heat and a one-line label for annotations ("PET for: ..."). Pure.
    """
    person = person or {**STANDARD_PERSON, "activity": "reference", "garments": None, "preset": "standard"}
    a_du = body_surface_area(person["weight"], person["height"])
    activity = ACTIVITIES.get(person.get("activity"), (f"{person['met']:g} met", person["met"], person["position"]))
    garments = person.get("garments")
    clothing = (", ".join(GARMENTS[g][1].lower() for g in garments) if garments else "reference clothing")
    preset = PRESETS.get(person.get("preset") or "")
    # Edited after choosing a preset = a custom person.
    matches_preset = bool(preset) and resolve({"preset": person["preset"]}) == person
    body = (f"{person['age']} y {person['sex']}, {person['weight']:g} kg, {person['height']:.2f} m, "
            f"{activity[0].lower()} ({person['met']:g} met, {person['position']}), {person['clo']:.2f} clo")
    return {
        "clo": person["clo"],
        "met": person["met"],
        "body_surface_m2": round(a_du, 2),
        "bmi": round(person["weight"] / person["height"] ** 2, 1),
        "metabolic_w": round(person["met"] * W_PER_M2_PER_MET * a_du),
        "clothing": clothing,
        "preset_label": preset["label"] if matches_preset else "Custom person",
        "label": body,
        "short": f"{person['age']} y {person['sex']} · {activity[0].lower()} · {person['clo']:.2f} clo",
    }


def options():
    """Everything the person pill lists (activities, garments by group, presets, limits)."""
    groups = {}
    for key, (group, label, clo) in GARMENTS.items():
        groups.setdefault(group, []).append({"key": key, "label": label, "clo": clo})
    return {
        "activities": [{"key": k, "label": label, "met": met, "position": pos}
                       for k, (label, met, pos) in ACTIVITIES.items()],
        "garments": [{"group": g, "items": items} for g, items in groups.items()],
        "presets": [{"key": k, "label": p["label"]} for k, p in PRESETS.items()],
        "limits": {k: {"min": low, "max": high, "unit": unit} for k, (low, high, unit) in LIMITS.items()},
        "sexes": list(SEXES),
        "positions": list(POSITIONS),
    }
