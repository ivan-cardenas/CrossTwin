"""
Color scheme for LandCoverVector.land_cover_type (common.LandCoverClasses).

Unlike the raster colormaps in core/rasterStyles.py, LandCoverClasses rows
aren't a fixed enum — pdok_landcover_brt get_or_creates one per distinct
INSPIRE landCoverObservationClass value the first time it's seen (see
importer/external_catalog.py's __fk_lookup__ on that dataset), and other
sources could in principle add differently-worded classes. So instead of a
static id -> color table, KEYWORD_COLORS matches class_name substrings
against a conventional land-cover palette (loosely CORINE/ESA WorldCover
conventions: built-up = red/grey, crops = tan, grass = yellow-green, forest =
green shades, water = blue, bare/snow = light grey/white), and anything that
matches nothing gets a deterministic (hash-based, so it's stable across
requests/restarts) color from FALLBACK_PALETTE rather than always the same
color or a random one.
"""
import hashlib

# Ordered most-specific-first — first substring match wins. Keys are matched
# case-insensitively against LandCoverClasses.class_name.
KEYWORD_COLORS = [
    ("urban fabric", "#d13737"),
    ("industrial", "#b3589a"),
    ("commercial", "#c2749c"),
    ("transport", "#8c8c8c"),
    ("mine", "#a0522d"),
    ("dump", "#8b6f47"),
    ("construction", "#c9a66b"),
    ("artificial", "#b4b4b4"),
    ("arable", "#e8c468"),
    ("crop", "#e8c468"),
    ("permanent crop", "#d9a441"),
    ("vineyard", "#c68fbf"),
    ("pasture", "#c8d96f"),
    ("grassland", "#c8d96f"),
    ("heterogeneous agri", "#e0d090"),
    ("agri", "#e8c468"),
    ("broad-leaved forest", "#2e7d32"),
    ("broad leaved forest", "#2e7d32"),
    ("coniferous forest", "#1b4d2e"),
    ("mixed forest", "#4c8c4a"),
    ("forest", "#2e7d32"),
    ("woodland", "#2e7d32"),
    ("shrub", "#9caf5e"),
    ("heath", "#a89f68"),
    ("sclerophyllous", "#8a9a5b"),
    ("transitional woodland", "#7fa66b"),
    ("beach", "#e8dcb5"),
    ("dune", "#e8dcb5"),
    ("bare rock", "#bdb7ab"),
    ("sparse", "#cfc9ba"),
    ("burnt", "#6b5d52"),
    ("glacier", "#eaf4fb"),
    ("snow", "#eaf4fb"),
    ("wetland", "#7fb3b0"),
    ("marsh", "#7fb3b0"),
    ("peat", "#5f8f8a"),
    ("salt", "#cdd9d6"),
    ("water", "#2f7fbf"),
    ("sea", "#2f7fbf"),
    ("ocean", "#2f7fbf"),
]

# Deterministic fallback for a class_name that matches no keyword above.
FALLBACK_PALETTE = [
    "#3388ff", "#e74c3c", "#9b59b6", "#f39c12",
    "#1abc9c", "#e91e63", "#00bcd4", "#ff5722",
    "#607d8b", "#8bc34a", "#673ab7", "#795548",
]


def get_landcover_color(class_name: str) -> str:
    """Resolve a stable hex color for a LandCoverClasses.class_name value."""
    if not class_name:
        return FALLBACK_PALETTE[0]

    lowered = class_name.strip().lower()
    for keyword, color in KEYWORD_COLORS:
        if keyword in lowered:
            return color

    # Deterministic (not random / not insertion-order-dependent) so the same
    # unmatched class always gets the same fallback color across requests.
    digest = hashlib.md5(lowered.encode("utf-8")).hexdigest()
    return FALLBACK_PALETTE[int(digest, 16) % len(FALLBACK_PALETTE)]


def build_landcover_style_and_legend():
    """
    Build a Mapbox `match` fill-color expression plus a legend for every
    class_name actually present on common.LandCoverVector rows.

    Returns (style_layers, legend) where style_layers is the LAYER_STYLES
    'layers' list for common.LandCoverVector and legend is a list of
    {label, color} dicts sorted alphabetically for display.
    """
    from common.models import LandCoverVector

    class_names = sorted(
        LandCoverVector.objects
        .exclude(land_cover_type__isnull=True)
        .values_list("land_cover_type__class_name", flat=True)
        .distinct()
    )

    if not class_names:
        # No data imported yet — fall back to a flat color so the layer still
        # renders sensibly once features do show up.
        return (
            [
                {"type": "fill", "paint": {"fill-color": "#558b2f", "fill-opacity": 0.45}},
                {"type": "line", "paint": {"line-color": "#33691e", "line-width": 1}},
            ],
            [],
        )

    match_expr = ["match", ["get", "land_cover_type"]]
    legend = []
    for name in class_names:
        color = get_landcover_color(name)
        match_expr.extend([name, color])
        legend.append({"label": name, "color": color})
    match_expr.append("#9e9e9e")  # fallback for any value not in the list

    style_layers = [
        {"type": "fill", "paint": {"fill-color": match_expr, "fill-opacity": 0.55}},
        {"type": "line", "paint": {"line-color": "#33691e", "line-width": 0.5}},
    ]
    return style_layers, legend
