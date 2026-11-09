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
builtup/canyon.py::street_inputs.

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
