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
"""

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
