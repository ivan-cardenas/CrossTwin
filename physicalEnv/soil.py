"""
Soil hydrology: hydrologic soil groups of the Dutch soil map (Bodemkaart
1:50 000) and infiltration by the SCS Curve Number method (USDA NRCS TR-55).

DAG edges:  LandCover  -> Infiltration
            Soil_Type  -> Infiltration   (texture; D over shallow groundwater unless drained)

Everything here except soil_landcover_composition() is pure Python, so the
dashboard can re-run the SCS equations for any rain depth without querying.
"""
import re

from django.db import connection

# ── Hydrologic soil groups ───────────────────────────────────────────

# Group -> final (minimum) infiltration rate range in mm/h (None = no upper
# bound), typical texture and runoff potential (USDA NRCS, NEH 630 ch. 7).
SOIL_GROUPS = {
    'A': {'min_mm_h': 7.6, 'max_mm_h': None, 'texture': 'Sand, gravel', 'runoff': 'Low'},
    'B': {'min_mm_h': 3.8, 'max_mm_h': 7.6, 'texture': 'Loam, silt loam', 'runoff': 'Moderate'},
    'C': {'min_mm_h': 1.3, 'max_mm_h': 3.8, 'texture': 'Clay loam', 'runoff': 'Moderately high'},
    'D': {'min_mm_h': 0.0, 'max_mm_h': 1.3, 'texture': 'Clay, peat', 'runoff': 'High'},
}
SOIL_GROUP_ORDER = 'ABCD'

# NEH 630 ch. 7: a water table within 60 cm of the surface makes a soil group
# D whatever its texture. Applied where the season's groundwater level
# (physicalEnv.GroundwaterDepth) is shallower than this.
SHALLOW_GROUNDWATER_CM = 60

# Season of the infiltration what-if -> groundwater statistic it reads:
# mean highest (winter) or mean lowest (summer) groundwater level.
SEASONS = {
    'wet': {'statistic': 'GHG', 'label': 'Wet season (GHG)'},
    'dry': {'statistic': 'GLG', 'label': 'Dry season (GLG)'},
}
DEFAULT_SEASON = 'wet'

# Land covers that are drained (sewers, drains, raised and paved ground).
# NEH 630 gives a soil with a shallow water table a dual group (A/D, B/D,
# C/D): the texture group where it is drained, D only where it is not. So
# these keep their texture group under shallow groundwater; their
# imperviousness is already in their curve numbers. BIS Nederland leaves
# most built-up cells without a GHG/GLG value anyway (85 % in Enschede).
# Water bodies and wetlands need no rule: their curve number is 100/98 for
# every soil group.
DRAINED_LAND_COVER = ("urban fabric", "industrial", "commercial", "road", "rail", "port area", "airport")


def _matches(name, keywords):
    """Any keyword at a word start of `name`: "road" must not match "broad-leaved forest"."""
    return any(re.search(r"\b" + re.escape(k), name) for k in keywords)


def is_drained(land_cover_class):
    """True for built-up and paved land-cover classes (DRAINED_LAND_COVER)."""
    return bool(land_cover_class) and _matches(land_cover_class.lower(), DRAINED_LAND_COVER)

# Texture words of the Dutch soil names -> group. A name can describe several
# layers ("Koopveengronden op zand", "zavel en lichte klei"); the most
# restrictive one sets the group, as in NEH 630 (the least transmissive layer
# limits infiltration).
_GROUP_PATTERNS = [
    # D: peat, peaty layers, (heavy) clay, unripened tidal mud, boulder clay
    ('D', r"veen"),                      # *veengronden, broekveen, veenkoloniaal dek, ...
    ('D', r"moer"),                      # moerige (peaty) layers, moerpodzol
    ('D', r"(?<!lichte )\bklei\b"),       # klei, zware klei (not lichte klei)
    ('D', r"kleidek|kleigronden|potklei|keileem|kleefaarde"),
    ('D', r"slikvaag|drechtvaag|liedeerd"),   # tidal mud; clay on peat
    # C: light clay ~ clay loam; knip clay has a dense, slowly permeable horizon
    ('C', r"lichte klei"),
    ('C', r"knip"),
    # B: zavel (8-25 % lutum: sandy/silt loam), loess and loam
    ('B', r"zavel"),
    ('B', r"\bleem\b"),                  # siltige/zandige leem (not leemarm, keileem)
    # A: sand and gravel, loamy sand included (zwak/sterk lemig zand)
    ('A', r"\bzand\b|\bgrind\b"),
]


def classify_soil_group(name):
    """Hydrologic soil group 'A'-'D' of a Dutch soil map name, or None if it names no texture."""
    if not name:
        return None
    text = name.lower()
    # "geen zand beginnend ondieper dan 0.8 m" says there is *no* sand
    text = re.sub(r"geen zand", "", text)
    groups = [group for group, pattern in _GROUP_PATTERNS if re.search(pattern, text)]
    return max(groups, key=SOIL_GROUP_ORDER.index) if groups else None


# ── SCS Curve Number (TR-55, antecedent moisture condition II) ───────

# CORINE land-cover class (LandCoverClasses.class_name, matched by keyword,
# first match wins) -> curve numbers for soil groups A, B, C, D and the TR-55
# cover type they are taken from.
CURVE_NUMBERS = [
    (("water course", "water bodies", "sea and ocean", "lagoon", "estuar"),
     (100, 100, 100, 100), "open water (all rain becomes runoff)"),
    (("marsh", "peat bog", "saline", "intertidal", "wetland"),
     (98, 98, 98, 98), "saturated wetland, treated as impervious"),
    (("green urban", "sport", "leisure"),
     (39, 61, 74, 80), "open space, good condition (grass cover > 75 %)"),
    (("discontinuous urban fabric",),
     (77, 85, 90, 92), "residential, 1/8 acre or less (65 % impervious)"),
    (("continuous urban fabric",),
     (89, 92, 94, 95), "commercial and business (85 % impervious)"),
    (("urban fabric",),
     (77, 85, 90, 92), "residential, 1/8 acre or less (65 % impervious)"),
    (("industrial", "commercial", "port area", "airport"),
     (81, 88, 91, 93), "industrial (72 % impervious)"),
    (("road", "rail"),
     (83, 89, 92, 93), "paved roads with open ditches, incl. right-of-way"),
    (("mineral extraction", "dump", "construction"),
     (77, 86, 91, 94), "newly graded areas (pervious, no vegetation)"),
    (("arable", "irrigated", "rice"),
     (67, 78, 85, 89), "row crops, straight row, good condition"),
    (("vineyard", "fruit", "olive"),
     (32, 58, 72, 79), "woods-grass combination (orchard), good condition"),
    (("natural grassland",),
     (30, 58, 71, 78), "meadow, continuous grass, protected from grazing"),
    (("pasture", "meadow"),
     (39, 61, 74, 80), "pasture, good condition"),
    (("complex cultivation", "agricultur", "agro-forestry", "annual crops"),
     (63, 75, 83, 87), "small grain, straight row, good condition"),
    (("forest",),
     (30, 55, 70, 77), "woods, good condition"),
    (("moor", "heath"),
     (30, 48, 65, 73), "brush, good condition"),
    (("sclerophyllous", "transitional woodland"),
     (35, 56, 70, 77), "brush, fair condition"),
    (("beach", "dune", "bare rock", "sparsely vegetated", "burnt"),
     (77, 86, 91, 94), "fallow, bare soil"),
]


def curve_number(land_cover_class, soil_group):
    """TR-55 curve number for a land-cover class name and soil group, or None if either is unknown."""
    if not land_cover_class or soil_group not in SOIL_GROUPS:
        return None
    name = land_cover_class.lower()
    for keywords, numbers, _cover in CURVE_NUMBERS:
        if _matches(name, keywords):
            return numbers[SOIL_GROUP_ORDER.index(soil_group)]
    return None


def scs_runoff_mm(rain_mm, cn, ia_ratio=0.2):
    """
    SCS direct runoff Q (mm) of a rain depth P (mm):
        S  = 25400 / CN - 254          potential maximum retention (mm)
        Ia = 0.2 S                      initial abstraction
        Q  = (P - Ia)^2 / (P - Ia + S)  for P > Ia, else 0
    """
    if rain_mm <= 0:
        return 0.0
    if cn >= 100:
        return float(rain_mm)
    s = 25400 / cn - 254
    ia = ia_ratio * s
    return (rain_mm - ia) ** 2 / (rain_mm - ia + s) if rain_mm > ia else 0.0


def infiltration_coefficient(rain_mm, cn):
    """Share of the rain that does not run off, (P - Q) / P, by the SCS method."""
    if rain_mm <= 0:
        return None
    return 1 - scs_runoff_mm(rain_mm, cn) / rain_mm


def summarize_infiltration(composition, rain_mm):
    """
    Area-weighted SCS result for a set of soil-group x land-cover pieces.

    composition: [(soil_group, land_cover_class, area_m2), ...]
    Runoff is computed per piece and then weighted by area; averaging the
    curve numbers first would overstate infiltration (Q is non-linear in CN).
    Pieces without a soil group or a known curve number are left out and
    reported as unclassified_m2.
    """
    classified = rain_m3 = infiltrated_m3 = cn_area = 0.0
    unclassified = 0.0
    for soil_group, land_cover_class, area_m2 in composition:
        cn = curve_number(land_cover_class, soil_group)
        if cn is None:
            unclassified += area_m2
            continue
        classified += area_m2
        cn_area += cn * area_m2
        rain_m3 += rain_mm / 1000 * area_m2
        infiltrated_m3 += (rain_mm - scs_runoff_mm(rain_mm, cn)) / 1000 * area_m2
    return {
        'rain_mm': rain_mm,
        'classified_m2': classified,
        'unclassified_m2': unclassified,
        'curve_number': round(cn_area / classified, 1) if classified else None,
        'infiltration_coefficient': infiltrated_m3 / rain_m3 if rain_m3 else None,
        'infiltrated_m3': infiltrated_m3,
        'runoff_m3': rain_m3 - infiltrated_m3,
    }


# ── Spatial composition (DB) ─────────────────────────────────────────

def soil_landcover_composition(geom, statistic='GHG'):
    """
    Area (m²) of every soil group x land-cover class combination inside
    `geom`, from SoilArea and the most recent LandCoverVector year there.

    Where an imported groundwater raster of `statistic` (GroundwaterDepth:
    GHG for the wet season, GLG for the dry one, see SEASONS) is shallower
    than SHALLOW_GROUNDWATER_CM, the piece counts as group D whatever its
    texture (NEH 630), except on drained land covers (is_drained), which keep
    their texture group. Cells without a value (255; most built-up land and
    water) count as not shallow. The cells are reclassified to shallow/deep
    and merged into polygons before they are intersected, so each piece is
    split once, not per 50 m cell.

    Returns (composition, by_group, shallow_m2, drained_shallow_m2):
      composition  [(soil_group, class_name, area_m2), ...], group after the
                   groundwater rule
      by_group     {soil_group: area_m2} of the soil map alone (texture),
                   regardless of land cover
      shallow_m2   area moved to D by shallow groundwater (undrained land)
      drained_shallow_m2  area over shallow groundwater that kept its texture
                   group because its land cover is drained
    """
    from .models import GroundwaterDepth, LandCoverClasses, LandCoverVector, SoilArea, SoilType
    from .signals import _area_sql

    soil, soil_type = SoilArea._meta.db_table, SoilType._meta.db_table
    landcover, classes = LandCoverVector._meta.db_table, LandCoverClasses._meta.db_table
    groundwater = GroundwaterDepth._meta.db_table
    unit = "ST_GeomFromEWKB(%(geom)s)"

    pieces_sql = f"""
        WITH latest AS (
            SELECT MAX(l.year) AS year FROM "{landcover}" l
            WHERE l.geom && {unit} AND ST_Intersects(l.geom, {unit})
        ), shallow AS (
            -- groundwater cells shallower than the threshold, as one (multi)polygon
            SELECT ST_Union(dump.geom) AS geom
            FROM (
                SELECT (ST_DumpAsPolygons(
                    ST_Reclass(ST_Clip(g.depth_raster, {unit}), 1, %(reclass)s, '8BUI', 255)
                )).*
                FROM "{groundwater}" g
                WHERE g.statistic = %(statistic)s AND ST_Intersects(g.depth_raster, {unit})
            ) dump
            WHERE dump.val = 1
        ), pieces AS (
            SELECT t."soilGroup" AS soil_group, c.class_name,
                   ST_Intersection(ST_Intersection(s.geom, l.geom), {unit}) AS geom
            FROM "{soil}" s
            JOIN "{soil_type}" t ON t.id = s.soil_type_id
            JOIN "{landcover}" l ON l.geom && s.geom AND ST_Intersects(l.geom, s.geom)
            JOIN "{classes}" c ON c.id = l.land_cover_type_id
            WHERE s.geom && {unit} AND ST_Intersects(s.geom, {unit})
              AND l.geom && {unit}
              AND l.year = (SELECT year FROM latest)
        ), split AS (
            SELECT p.soil_group, p.class_name,
                   {_area_sql("p.geom")} AS total_m2,
                   COALESCE({_area_sql("ST_Intersection(p.geom, sh.geom)")}, 0) AS shallow_m2
            FROM pieces p CROSS JOIN shallow sh
        )
        SELECT soil_group, class_name, SUM(total_m2 - shallow_m2), SUM(shallow_m2)
        FROM split
        GROUP BY 1, 2
    """
    groups_sql = f"""
        SELECT t."soilGroup", SUM({_area_sql(f"ST_Intersection(s.geom, {unit})")})
        FROM "{soil}" s
        JOIN "{soil_type}" t ON t.id = s.soil_type_id
        WHERE s.geom && {unit} AND ST_Intersects(s.geom, {unit})
        GROUP BY 1
    """
    n = SHALLOW_GROUNDWATER_CM
    params = {
        "geom": bytes(geom.ewkb),
        "reclass": f"[0-{n}):1, [{n}-254]:0",   # 255 stays nodata
        "statistic": statistic,
    }
    composition, shallow_total, drained_shallow = [], 0.0, 0.0
    with connection.cursor() as cursor:
        cursor.execute(pieces_sql, params)
        for group, class_name, deep_m2, shallow_m2 in cursor.fetchall():
            deep_m2, shallow_m2 = float(deep_m2 or 0), float(shallow_m2 or 0)
            if shallow_m2 > 0 and is_drained(class_name):
                # drained: the dual group's texture letter applies (NEH 630)
                deep_m2 += shallow_m2
                drained_shallow += shallow_m2
                shallow_m2 = 0.0
            if deep_m2 > 0:
                composition.append((group, class_name, deep_m2))
            if shallow_m2 > 0:
                composition.append(("D", class_name, shallow_m2))
                shallow_total += shallow_m2
        cursor.execute(groups_sql, {"geom": params["geom"]})
        by_group = {g: float(a or 0) for g, a in cursor.fetchall()}
    return composition, by_group, shallow_total, drained_shallow
