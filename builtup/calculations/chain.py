"""
Pure equations of the street canyon (no ORM queries).

    H   = (H_left + H_right) / 2         an open side counts as 0 (Oke's
                                         symmetric canyon: buildings on one
                                         side only give half the height)
    W   = Street.width                   when typed in (> 0), else
          facade gap                     distance street -> nearest facade on
                                         the left + on the right, else
          DEFAULT_WIDTH_M[class]         per street classification
    H/W = H / W                          None when W <= 0

Used by builtup.StreetCanyon.save() (one street) and
builtup.signals.refresh_canyons() (many streets at once), so both paths
share one equation. The side heights and facade gap come from
builtup/calculations/canyon.py::street_inputs.

DAG edges: Buildings -> Canyon_Aspect, Streets -> Canyon_Aspect.
(The accessibility equations at the end of this module carry their own edges.)
"""

import math

DEFAULT_WIDTH_M = {"residential": 8.0, "secondary": 12.0, "primary": 20.0}
FALLBACK_WIDTH_M = 10.0


def canyon_height(h_left, h_right):
    """Mean of the two side heights in metres; a side without buildings is 0."""
    return ((h_left or 0.0) + (h_right or 0.0)) / 2.0


def canyon_width(street_width, facade_gap, classification):
    """(W in metres, source): 'street' (typed width), 'facade' (measured) or 'default'."""
    if street_width is not None and street_width > 0:
        return float(street_width), "street"
    if facade_gap is not None and facade_gap > 0:
        return float(facade_gap), "facade"
    return DEFAULT_WIDTH_M.get(classification, FALLBACK_WIDTH_M), "default"


def aspect_ratio(height_m, width_m):
    """H/W, or None when the width is not positive."""
    if not width_m or width_m <= 0:
        return None
    return height_m / width_m


def canyon(inputs, street_width, classification):
    """
    All derived canyon fields from the street_inputs() row `inputs`
    (h_left_m, h_right_m, w_facade_m) and the street's own width/class.
    """
    h = canyon_height(inputs.get("h_left_m"), inputs.get("h_right_m"))
    w, source = canyon_width(street_width, inputs.get("w_facade_m"), classification)
    return {"height_m": h, "width_m": w, "width_source": source, "aspect_ratio": aspect_ratio(h, w)}


# ── Degree of Urbanisation (DAG node Degree_Urbanisation) ──────────────
#
# Unit classification and urbanisation rate. The grid classification is
# builtup/calculations/degurba.py; these two equations serve both Urbanisation.save()
# (stored) and the dashboard's what-if (views._build_indicators).
#
#   L1 of a unit:  city (3)  if  P_30 / P >= 1/2
#                  town (2)  if  (P_30 + P_23 + P_22 + P_21) / P >= 1/2
#                  rural (1) otherwise
#   L2 of a unit:  30 for a city; else the class with the largest population
#                  share within the unit's L1 group (towns: 23, 22, 21;
#                  rural: 13, 12, 11), ties to the denser class (†, see
#                  docs/DEGREE_OF_URBANISATION.md)
#   rate (%/yr) =  ((A_1 / A_0) ** (1 / (t_1 - t_0)) - 1) x 100,
#                  A = urban area (cells 21-30) in km², t = year

UNIT_L2_GROUPS = {2: (23, 22, 21), 1: (13, 12, 11)}
URBAN_L2 = (21, 22, 23, 30)
CLUSTER_L2 = (21, 22, 23)


def classify_unit(pop_by_l2):
    """(l1, l2, shares) of an admin unit from its population per grid class {l2: people}."""
    total = sum(v for v in pop_by_l2.values() if v)
    if not total:
        return None, None, {}
    shares = {k: (v or 0) / total for k, v in pop_by_l2.items()}
    centre = shares.get(30, 0.0)
    cluster = centre + sum(shares.get(k, 0.0) for k in CLUSTER_L2)
    if centre >= 0.5:
        return 3, 30, shares
    l1 = 2 if cluster >= 0.5 else 1
    group = UNIT_L2_GROUPS[l1]
    # max() keeps the first of equal values: the group is ordered dense -> sparse.
    l2 = max(group, key=lambda k: shares.get(k, 0.0))
    return l1, l2, shares


def urbanization_rate(area_0, year_0, area_1, year_1):
    """Compound annual growth of the urban area in %/yr; None without two usable years."""
    if not area_0 or area_1 is None or year_1 is None or year_0 is None or year_1 <= year_0:
        return None
    return ((area_1 / area_0) ** (1.0 / (year_1 - year_0)) - 1.0) * 100.0


# ── Neighbourhood generator (builtup/calculations/generative.py) ─────────
#
#   units  = floor(GFA / unit_gfa)                apartments (≥ 1 per building)
#   floors = fewest in [1, 20] whose units reach the target (generative.generate)
#   FAR    = Σ GFA / site area                    (floor area ratio, FSI)
#   GSI    = Σ footprint / site area              (ground space index)
#   density = units / (site area / 10 000)        dwellings per hectare
# (Berghauser Pont & Haupt 2010, Spacematrix: FSI, GSI.)

def units_in(gfa_m2, unit_gfa_m2):
    """Dwellings in a building of that gross floor area: whole units, at least one."""
    if not unit_gfa_m2 or unit_gfa_m2 <= 0:
        return 1
    return max(1, int(gfa_m2 // unit_gfa_m2))


def layout_metrics(site_m2, footprints_m2, floors, units, street_m2, street_length_m, target_units=None):
    """Spacematrix-style metrics of a generated layout (areas in m², lengths in m)."""
    footprint = float(sum(footprints_m2))
    gfa = float(sum(a * f for a, f in zip(footprints_m2, floors)))
    total_units = int(sum(units))
    site = float(site_m2) if site_m2 else 0.0
    return {
        "buildings": len(footprints_m2),
        "units": total_units,
        "target_units": target_units,
        "units_vs_target": (total_units - target_units) if target_units else None,
        "footprint_m2": round(footprint, 1),
        "gfa_m2": round(gfa, 1),
        "site_m2": round(site, 1),
        "far": round(gfa / site, 3) if site else None,
        "gsi": round(footprint / site, 3) if site else None,
        "street_m2": round(float(street_m2), 1),
        "street_share": round(street_m2 / site, 3) if site else None,
        "street_length_m": round(float(street_length_m), 1),
        "density_units_ha": round(total_units / (site / 10_000), 1) if site else None,
        "dwellings_per_building": round(total_units / len(units), 2) if units else None,
        "max_dwellings_per_building": max(units) if units else None,
        "single_family": sum(1 for u in units if u == 1),
        "multi_family": sum(1 for u in units if u > 1),
    }


# ── Network accessibility (DAG node Accessibility) ───────────────────────
#
# Per building and travel mode, from the network distance d (m) to the k
# nearest amenities of each category c (pandana nearest_pois over the OSM
# walk / bike graph, builtup/calculations/accessibility.py):
#
#   f(d)  = 1                          d <= D0     (full value close by)
#           exp(-lambda (d - D0))      D0 < d <= D_max
#           0                          d > D_max   (not reachable)
#   lambda = -ln(F_AT_CUTOFF) / (D_max - D0)       so f(D_max) = F_AT_CUTOFF
#   a_c   = sum_k omega_k f(d_ck) / sum_k omega_k     category value, 0..1
#   score = 100 sum_c w_c a_c / sum_c w_c             0..100
#
# A new amenity can only shorten a distance, so f and hence the score never
# fall when an amenity is added (monotone), which is what drives the price
# edge Accessibility -> Property. The shape (full value inside a short walk,
# smooth decay to a cut-off, diminishing weight on further amenities of one
# category) follows the Walk Score methodology (Walk Score 2011) and the
# 15-minute-city catchments (Moreno et al. 2021, Smart Cities 4(1)); the
# numbers are named v1 choices, not estimates, and are stored with the result
# (ACCESS_METHOD).
#
# DAG edges: Facilities -> Accessibility, Streets -> Accessibility,
#            Green_Area -> Accessibility

ACCESS_METHOD = "network-decay walk/bike v3"
MODES = ("walk", "bike")
# Speeds (m/s) turn a catchment in minutes into metres: 4.8 km/h walking, 15 km/h cycling.
SPEED_MPS = {"walk": 4.8 / 3.6, "bike": 15.0 / 3.6}
# Walk: D0 = 5 min, D_max = 20 min (Moreno et al. 2021 use 15 min as the target).
# Bike: D0 = 800 m (3 min), D_max = 3.2 km (13 min), twice the walking cut-off. The cycling cut-off is deliberately bounded:
# it is also the reach of a refresh (builtup/signals.py), so a single edit on the map
# recomputes the buildings within 3.2 km, not the whole city.
FULL_VALUE_M = {"walk": 400.0, "bike": 800.0}
CUTOFF_M = {"walk": 1600.0, "bike": 3200.0}
F_AT_CUTOFF = 0.05

# Amenities of one category closer than this to each other count as one destination (a bus stop on each
# side of a street is one stop, not two): accessibility.merge_close_points. Parks are not merged: their
# points are entrances along one edge, already spaced PARK_ACCESS_SPACING_M apart.
POI_MERGE_M = 50.0
MERGE_EXEMPT = ("park",)

# category -> (weight w_c, omega_k for the 1st, 2nd, ... nearest). The keys are
# Facility.type values plus "park" (nature.GreenSpaces). Weights are
# equal-ish with daily needs (food, health, transit, green) above occasional ones.
CATEGORIES = {
    "supermarket": (3.0, (1.0,)),
    "shop": (1.0, (1.0, 0.5, 0.25)),
    "pharmacy": (1.5, (1.0,)),
    "clinic_gp": (2.0, (1.0,)),
    "hospital": (1.0, (1.0,)),
    "school": (2.0, (1.0, 0.5)),
    "childcare": (1.5, (1.0, 0.5)),
    "library": (0.5, (1.0,)),
    "sport": (1.0, (1.0,)),
    "bus_stop": (2.0, (1.0, 0.5)),
    "tram_metro_stop": (2.0, (1.0,)),
    "train_station": (2.0, (1.0,)),
    "park": (3.0, (1.0,)),
}


def _params_hash():
    """Short hash of every constant that shapes a score, so changing one without bumping ACCESS_METHOD shows."""
    import hashlib
    import json

    payload = json.dumps([SPEED_MPS, FULL_VALUE_M, CUTOFF_M, F_AT_CUTOFF, CATEGORIES, POI_MERGE_M, MERGE_EXEMPT], sort_keys=True)
    return hashlib.sha1(payload.encode()).hexdigest()[:8]


# Stored in Accessibility.method: the equation version plus the hash of its constants.
METHOD_STAMP = f"{ACCESS_METHOD} {_params_hash()}"


def decay_rate(mode):
    """lambda of the exponential tail for the mode (1/m)."""
    return -math.log(F_AT_CUTOFF) / (CUTOFF_M[mode] - FULL_VALUE_M[mode])


def distance_decay(d_m, mode):
    """f(d): 1 inside D0, exponential tail to D_max, 0 beyond or when unreachable (None)."""
    if d_m is None or d_m < 0 or d_m > CUTOFF_M[mode]:
        return 0.0
    if d_m <= FULL_VALUE_M[mode]:
        return 1.0
    return math.exp(-decay_rate(mode) * (d_m - FULL_VALUE_M[mode]))


def category_value(distances_m, mode, omegas):
    """a_c from the sorted distances to the nearest amenities of one category; missing ones count 0."""
    total = sum(omegas)
    if not total:
        return 0.0
    got = 0.0
    for i, omega in enumerate(omegas):
        d = distances_m[i] if distances_m is not None and i < len(distances_m) else None
        got += omega * distance_decay(d, mode)
    return got / total


def accessibility_score(distances_by_category, mode, categories=None):
    """
    Score 0..100 from {category: [d_1, d_2, ...]} in metres (None / missing = unreachable).
    `categories` overrides CATEGORIES (name -> (weight, omegas)) for what-ifs.
    """
    categories = CATEGORIES if categories is None else categories
    weight_sum = sum(w for w, _ in categories.values())
    if not weight_sum:
        return 0.0
    total = sum(
        w * category_value(distances_by_category.get(name), mode, omegas)
        for name, (w, omegas) in categories.items()
    )
    return 100.0 * total / weight_sum


def access_minutes(d_m, mode):
    """Travel time in minutes for a network distance (display only)."""
    return None if d_m is None else d_m / SPEED_MPS[mode] / 60.0
