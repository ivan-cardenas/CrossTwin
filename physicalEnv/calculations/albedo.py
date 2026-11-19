"""
Surface albedo of land-cover polygons.

Two sources, in order of preference (LandCoverVector.effective_albedo):

1. Measured: the zonal mean of a Sentinel-2 shortwave broadband albedo
   raster (SatelliteImagery with index ALBEDO, computed on the Copernicus
   openEO backend from L2A surface reflectance, see ALBEDO_COEFFICIENTS)
   over the polygon, written by measure(). DAG edge RS_Imagery -> LandCover
   (partial: albedo is an attribute of the land cover; the classification
   itself still comes from the land-cover import).
2. Default: the albedo of the polygon's `material`, which a pre_save
   receiver (physicalEnv/signals.py) takes from its class's
   `default_material` (default_material_for(), keyword table below).

A polygon drawn or reshaped in the map editor was never observed by a
satellite: an editor geometry change clears its measured albedo, an
editor building ring gets an estimate (roof + paving, ring_albedo()), and
measure() skips editor polygons.
"""
from django.db import connection

from core.cache import bump_layer_version

# Sentinel-2 L2A bands (surface reflectance, DN / 10000) -> weight of the
# narrow-to-broadband conversion of Bonafoni & Sekertekin (2020), "Albedo
# Retrieval From Sentinel-2 by New Narrow-to-Broadband Conversion
# Coefficients", IEEE GRSL 17(9), 1618-1622. The weights sum to 1; check them
# against the paper's table before relying on absolute values (RMSE ~0.02
# against SURFRAD stations in the paper).
ALBEDO_COEFFICIENTS = {
    "B02": 0.2266,
    "B03": 0.1236,
    "B04": 0.1573,
    "B08": 0.3417,
    "B11": 0.1170,
    "B12": 0.0338,
}
ALBEDO_INDEX = "ALBEDO"
MIN_PIXELS = 3

# Material codes of Oke et al. (2017) Table 5.1, seeded by migration
# physicalEnv 0013 (SurfaceMaterialProperties.code).
ASPHALT = "road_asphalt"
CONCRETE = "road_concrete"
ROOF_TILE = "roof_tile_clay"
BITUMEN_ROOF = "roof_tar_gravel_bitumen"
URBAN = "urban_snow_free"
SUBURBAN = "suburban_snow_free"
GRASS = "grass"
CROPS = "crops"
WETLANDS = "wetlands"
ORCHARDS = "orchards"
DECIDUOUS = "forest_deciduous"
CONIFEROUS = "forest_coniferous"
BARE_SOIL = "soil_dark_wet"        # Dutch bare ground is mostly dark and moist
SAND = "desert_sands"
WATER = "water_high_sun"

# Class-name keywords (matched at word starts, physicalEnv/calculations/soil.py::_matches)
# -> material code. First match wins, so specific words come first.
CLASS_MATERIALS = (
    (CONIFEROUS, ("coniferous",)),
    (ORCHARDS, ("orchard", "fruit")),
    (DECIDUOUS, ("broad-leaved", "broad leaved", "deciduous", "forest", "wood", "tree")),
    (WETLANDS, ("marsh", "bog", "wetland", "peat")),
    (WATER, ("water", "sea", "lagoon", "estuar", "lake", "river", "canal")),
    (SAND, ("beach", "dune", "sand")),
    (BARE_SOIL, ("bare", "rock", "burnt", "construction", "dump", "mine")),
    (CROPS, ("arable", "crop", "agricult", "vineyard")),
    (GRASS, ("grass", "pasture", "green", "sport", "leisure", "park", "heath", "shrub",
             "meadow", "natural", "vegetat")),
    (ASPHALT, ("road", "rail", "transport", "airport", "parking", "paved")),
    (SUBURBAN, ("discontinuous",)),
    (URBAN, ("urban", "built", "industrial", "commercial", "fabric", "residential", "port")),
)


def material_code_for(class_name):
    """Material code for a land-cover class name, or None when no keyword matches."""
    from .soil import _matches

    name = (class_name or "").lower()
    for code, keywords in CLASS_MATERIALS:
        if _matches(name, keywords):
            return code
    return None


def material(code):
    """The SurfaceMaterialProperties row with that code, or None (not seeded)."""
    from ..models import SurfaceMaterialProperties

    if not code:
        return None
    return SurfaceMaterialProperties.objects.filter(code=code).first()


def default_material_for(class_name):
    return material(material_code_for(class_name))


def ring_albedo(ring_area, footprint_area, roof_material=None):
    """
    Area-weighted albedo of an editor building's urban-fabric ring: the
    footprint at the roof's albedo (bitumen roof when unknown), the rest at
    paving albedo. None when the materials are not seeded.
    """
    roof = roof_material or material(BITUMEN_ROOF)
    paving = material(CONCRETE)
    if roof is None or paving is None or not ring_area:
        return None
    footprint_area = min(max(footprint_area, 0.0), ring_area)
    return (footprint_area * roof.albedo + (ring_area - footprint_area) * paving.albedo) / ring_area


def measure(imagery, city_id=None, only_missing=False):
    """
    Zonal mean of an ALBEDO raster over the latest-year land-cover polygons
    it covers (DAG edge RS_Imagery -> LandCover), in one UPDATE:

        albedo_P = mean{ a(x) : x pixel of the raster in P, a(x) valid }

    kept only with at least MIN_PIXELS valid pixels and 0 <= mean <= 1.
    Skips editor polygons (source_building / source_park / source_street / source_project), which the scene
    never saw, and polygons measured on a newer scene. `city_id` limits it
    to one city, `only_missing` to polygons without an albedo (bulk imports).
    Returns the number of polygons written.
    """
    from ..models import LandCoverVector, SatelliteImagery

    if imagery.raster is None:
        return 0
    scene_date = imagery.date.date() if imagery.date else None
    label = f"Sentinel-2 {scene_date}" if scene_date else f"{imagery.satellite_type or 'Satellite'} {imagery.year}"
    lcv = LandCoverVector._meta.db_table
    img = SatelliteImagery._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            WITH latest AS (
                SELECT city_id, max(year) AS year FROM "{lcv}" GROUP BY city_id
            ), stats AS (
                SELECT l.id, (ST_SummaryStats(ST_Clip(r.raster, 1, l.geom, true), 1, true)).*
                FROM "{lcv}" l
                JOIN latest y ON y.city_id IS NOT DISTINCT FROM l.city_id AND y.year = l.year
                JOIN "{img}" r ON r.id = %(img)s
                WHERE l.geom && ST_Envelope(r.raster)
                  AND ST_Intersects(l.geom, ST_ConvexHull(r.raster))
                  AND l.source_building IS NULL AND l.source_park IS NULL AND l.source_street IS NULL AND l.source_project IS NULL
                  AND (%(city)s::int IS NULL OR l.city_id = %(city)s)
                  AND (NOT %(missing)s OR l.albedo IS NULL)
                  AND (l.albedo_date IS NULL OR %(date)s::date IS NULL OR l.albedo_date <= %(date)s)
            )
            UPDATE "{lcv}" l
            SET albedo = s.mean, albedo_source = %(label)s, albedo_date = %(date)s
            FROM stats s
            WHERE l.id = s.id AND s.count >= %(min)s
              AND s.mean >= 0 AND s.mean <= 1          -- also drops NaN (greater than any number in PostgreSQL)
            """,
            {"img": imagery.pk, "city": city_id, "missing": only_missing, "date": scene_date,
             "label": label[:100], "min": MIN_PIXELS},
        )
        written = cursor.rowcount
    if written:
        bump_layer_version(LandCoverVector)
    return written


def measure_missing(city_id):
    """
    Albedo for a city's polygons without one, from the newest ALBEDO raster
    first (bulk land-cover imports: the albedo raster may have been imported
    before the land cover). Returns the number of polygons written.
    """
    from ..models import SatelliteImagery

    written = 0
    rasters = (SatelliteImagery.objects.filter(index__iexact=ALBEDO_INDEX, raster__isnull=False)
               .order_by("-date", "-pk"))
    for imagery in rasters:
        written += measure(imagery, city_id=city_id, only_missing=True)
    return written


def set_default_materials(city_id):
    """material = the class's default material for a city's polygons without one (bulk imports)."""
    from ..models import LandCoverClasses, LandCoverVector

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            UPDATE "{LandCoverVector._meta.db_table}" l
            SET material_id = c.default_material_id
            FROM "{LandCoverClasses._meta.db_table}" c
            WHERE l.land_cover_type_id = c.id AND l.city_id = %(city)s
              AND l.material_id IS NULL AND c.default_material_id IS NOT NULL
            """,
            {"city": city_id},
        )
        written = cursor.rowcount
    if written:
        bump_layer_version(LandCoverVector)
    return written
