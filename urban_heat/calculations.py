from django.db.models import Sum, Avg, Count, Max, Min, Q
from django.contrib.gis.db.models.functions import Area, Intersection
from django.db import connection

from .models import (
    MeanRadiantTemperature, UTCI, WetBulbGlobeTemperature, SkyViewFactor, PET,
    LandSurfaceTemperature, SurfaceUrbanHeatIslandIntensity,
    NatureBasedSolutionPolygon, NatureBasedSolutionPoint,
    StressCategory,
)
from physicalEnv.models import LandCoverVector, DigitalSurfaceModel
from builtup.models import Park, Building, Street
from weather.models import Meteorology


# ── Vegetation & Green Area ──────────────────────────────────────────

# Land-cover classes counted as green (substring match on class_name, like
# physicalEnv.signals.URBAN_AREA_KEYWORDS for urban fabric).
GREEN_LANDCOVER_KEYWORDS = ['forest', 'grass', 'green', 'vegetation', 'tree', 'park', 'nature']


def calculate_green_area(adminUnit):
    """Green area inside the unit, in km²: parks and green land cover merged.

    DAG edges:  LandCover → Green_Area

    Every polygon is first clipped to the unit (one lying entirely within it
    is kept whole, only boundary-crossing ones go through ST_Intersection),
    so nothing that lies outside the unit counts. Land cover uses each city's
    most recent year, like the neighborhood urban area (physicalEnv/signals.py).
    LandCoverVector.percentage is not used: it is a share of the province and
    means nothing for a smaller unit.

    The two layers overlap (a park is usually also a green land-cover polygon,
    and OSM parks can overlap each other), so they are merged before measuring:

        parks           = |∪ parks ∩ unit|
        total green     = |∪ (parks + green land cover) ∩ unit|
        green land cover = total green − parks   (green land outside the parks)

    so parks + green land cover = total, and no square metre counts twice.
    """
    from physicalEnv.models import LandCoverClasses
    from physicalEnv.signals import _area_sql

    geom = adminUnit.geom
    if geom is None:
        return {'park_area_km2': 0.0, 'green_lc_km2': 0.0, 'total_green_km2': 0.0}

    parks = Park._meta.db_table
    landcover = LandCoverVector._meta.db_table
    classes = LandCoverClasses._meta.db_table
    # ST_CollectionExtract(…, 3): a clip can leave slivers of lines/points on
    # the boundary; keep only the polygon part so the union stays areal.
    clip = "CASE WHEN ST_Within({g}, u.geom) THEN {g} ELSE ST_CollectionExtract(ST_Intersection({g}, u.geom), 3) END"
    sql = f"""
        WITH unit AS (SELECT ST_GeomFromEWKB(%(geom)s) AS geom),
        park_parts AS (
            SELECT {clip.format(g='p.geom')} AS g
            FROM "{parks}" p, unit u
            WHERE p.geom && u.geom AND ST_Intersects(p.geom, u.geom)
        ),
        green_parts AS (
            SELECT {clip.format(g='l.geom')} AS g
            FROM "{landcover}" l
            JOIN "{classes}" c ON c.id = l.land_cover_type_id, unit u
            WHERE l.geom && u.geom AND ST_Intersects(l.geom, u.geom)
              AND c.class_name ILIKE ANY(%(patterns)s)
              AND l.year = (SELECT MAX(l2.year) FROM "{landcover}" l2 WHERE l2.city_id = l.city_id)
        ),
        park_union AS (SELECT ST_UnaryUnion(ST_Collect(g)) AS g FROM park_parts),
        all_union AS (
            SELECT ST_UnaryUnion(ST_Collect(g)) AS g
            FROM (SELECT g FROM park_union UNION ALL SELECT g FROM green_parts) parts
        )
        SELECT COALESCE((SELECT {_area_sql('g')} FROM park_union), 0),
               COALESCE((SELECT {_area_sql('g')} FROM all_union), 0)
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, {
            'geom': bytes(geom.ewkb),
            'patterns': [f'%{kw}%' for kw in GREEN_LANDCOVER_KEYWORDS],
        })
        park_m2, total_m2 = cursor.fetchone()
    # the union can be a hair smaller than the parks alone through rounding
    total_m2 = max(total_m2, park_m2)

    return {
        'park_area_km2': round(park_m2 / 1e6, 3),
        'green_lc_km2': round((total_m2 - park_m2) / 1e6, 3),
        'total_green_km2': round(total_m2 / 1e6, 3),
    }


def calculate_vegetation_coverage(adminUnit):
    """Vegetation coverage as percentage of the administrative unit's area.

    DAG edges:  Green_Area → Vegetation_Coverage
                Vegetation_Coverage → DSM
    """
    green = calculate_green_area(adminUnit)
    adminUnit_area = adminUnit.area_km2 or 0
    if adminUnit_area > 0:
        pct = round(green['total_green_km2'] / adminUnit_area * 100, 1)
    else:
        pct = 0
    return {
        **green,
        'vegetation_coverage_pct': pct,
    }


# ── Urban Morphology ─────────────────────────────────────────────────

def calculate_urban_morphology(adminUnit):
    """Building and street statistics relevant to canyon geometry.

    DAG edges:  Buildings → Canyon_Aspect, Streets → Canyon_Aspect (read from
                the stored builtup.StreetCanyon rows, builtup/signals.py)

    The aspect ratio is the mean H/W of the stored street canyons inside the
    unit, each weighted by the length of its street inside the unit. Without
    stored canyons it falls back to the old proxy
    avg building height / avg street width (aspect_ratio_source = 'proxy').
    """
    buildings = Building.objects.filter(geom__intersects=adminUnit.geom)
    streets = Street.objects.filter(geom__intersects=adminUnit.geom)

    bldg_agg = buildings.aggregate(
        count=Count('id'),
        avg_height=Avg('height_m'),
        max_height=Max('height_m'),
        total_footprint=Sum('area_sqm'),
    )

    street_agg = streets.aggregate(
        count=Count('id'),
        avg_width=Avg('width'),
    )

    canyons = calculate_canyon_aspect(adminUnit)
    if canyons['canyon_streets']:
        aspect, source = canyons['aspect_ratio'], 'stored'
    else:
        aspect = round((bldg_agg['avg_height'] or 0) / (street_agg['avg_width'] or 1), 2)
        source = 'proxy'

    return {
        'building_count': bldg_agg['count'] or 0,
        'avg_building_height_m': round(bldg_agg['avg_height'] or 0, 1),
        'max_building_height_m': round(bldg_agg['max_height'] or 0, 1),
        'total_footprint_km2': round((bldg_agg['total_footprint'] or 0) / 1e6, 3),
        'street_count': street_agg['count'] or 0,
        'avg_street_width_m': canyons['avg_width_m'] if source == 'stored' else round(street_agg['avg_width'] or 0, 1),
        'aspect_ratio': aspect,
        'aspect_ratio_source': source,
        **{k: v for k, v in canyons.items() if k != 'aspect_ratio'},
    }


def calculate_canyon_aspect(adminUnit):
    """Length-weighted H/W of the stored street canyons inside the unit.

    DAG edges:  Buildings → Canyon_Aspect, Streets → Canyon_Aspect

        H/W(unit) = Σ (H/W_i × L_i) / Σ L_i     L_i = length of street i inside the unit

    plus the share of that length in Oke's classes: open (< 0.5),
    regular (0.5–2) and deep (≥ 2). Canyons without a ratio are left out.
    """
    from builtup.models import StreetCanyon

    empty = {'canyon_streets': 0, 'aspect_ratio': 0, 'avg_width_m': 0,
             'canyon_open_pct': 0, 'canyon_deep_pct': 0}
    geom = adminUnit.geom
    if geom is None:
        return empty
    table = StreetCanyon._meta.db_table
    sql = f"""
        WITH unit AS (SELECT ST_GeomFromEWKB(%(geom)s) AS geom),
        c AS (
            SELECT k.aspect_ratio AS r, k.width_m AS w,
                   CASE WHEN ST_Within(k.geom, u.geom) THEN ST_Length(k.geom)
                        ELSE ST_Length(ST_Intersection(k.geom, u.geom)) END AS l
            FROM "{table}" k, unit u
            WHERE k.geom && u.geom AND ST_Intersects(k.geom, u.geom) AND k.aspect_ratio IS NOT NULL
        )
        SELECT COUNT(*), SUM(r * l) / NULLIF(SUM(l), 0), SUM(w * l) / NULLIF(SUM(l), 0),
               SUM(l) FILTER (WHERE r < 0.5) / NULLIF(SUM(l), 0),
               SUM(l) FILTER (WHERE r >= 2) / NULLIF(SUM(l), 0)
        FROM c WHERE l > 0
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, {'geom': bytes(geom.ewkb)})
        n, ratio, width, open_share, deep_share = cursor.fetchone()
    if not n:
        return empty
    return {
        'canyon_streets': n,
        'aspect_ratio': round(ratio or 0, 2),
        'avg_width_m': round(width or 0, 1),
        'canyon_open_pct': round((open_share or 0) * 100, 1),
        'canyon_deep_pct': round((deep_share or 0) * 100, 1),
    }


# ── Thermal Index Statistics (raster) ────────────────────────────────

def _raster_stats_sql(table, raster_col, geom_wkt, srid):
    """Get min/max/mean/stddev from a raster clipped to a geometry."""
    sql = f"""
        SELECT
            (stats).min,
            (stats).max,
            (stats).mean,
            (stats).stddev,
            (stats).count
        FROM (
            SELECT ST_SummaryStats(
                ST_Clip(r.{raster_col}, ST_GeomFromText(%s, %s))
            ) AS stats
            FROM {table} r
            WHERE ST_Intersects(r.{raster_col}, ST_GeomFromText(%s, %s))
            ORDER BY r.date_time DESC
            LIMIT 1
        ) sub
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, [geom_wkt, srid, geom_wkt, srid])
        row = cursor.fetchone()
    if row and row[0] is not None:
        return {
            'min': round(row[0], 2),
            'max': round(row[1], 2),
            'mean': round(row[2], 2),
            'stddev': round(row[3], 2),
            'count': row[4],
        }
    return None


def get_thermal_indices(adminUnit):
    """Aggregate raster statistics for all thermal indices.

    DAG edges:  Meteorology → Tmrt, PET, UTCI
                DSM → SVF → Tmrt, PET
                Tmrt → PET, UTCI

    WBGT is not a DAG node: it is an observed measure imported from KNMI
    (importer KNMIImporter), read here as-is like the other rasters.
    """
    geom_wkt = adminUnit.geom.wkt
    srid = adminUnit.geom.srid

    indices = {}

    # LST (Land Surface Temperature)
    indices['lst'] = _raster_stats_sql(
        'urban_heat_landsurfacetemperature', 'raster', geom_wkt, srid
    )

    # Tmrt (Mean Radiant Temperature)
    indices['tmrt'] = _raster_stats_sql(
        'urban_heat_meanradianttemperature', 'raster', geom_wkt, srid
    )

    # PET (Physiological Equivalent Temperature)
    indices['pet'] = _raster_stats_sql(
        'urban_heat_pet', 'raster', geom_wkt, srid
    )

    # UTCI (Universal Thermal Climate Index)
    indices['utci'] = _raster_stats_sql(
        'urban_heat_utci', 'raster', geom_wkt, srid
    )

    # WBGT (Wet Bulb Globe Temperature, latest KNMI import)
    indices['wbgt'] = _raster_stats_sql(
        WetBulbGlobeTemperature._meta.db_table, 'raster', geom_wkt, srid
    )

    # SVF (Sky View Factor)
    indices['svf'] = _raster_stats_sql(
        'urban_heat_skyviewfactor', 'raster', geom_wkt, srid
    )

    # SUHII (Surface Urban Heat Island Intensity)
    indices['suhii'] = _raster_stats_sql(
        'urban_heat_surfaceurbanheatislandintensity', 'raster', geom_wkt, srid
    )

    return indices


# ── Stress Category Classification ──────────────────────────────────

def classify_pet(value):
    """Classify PET value into thermal stress category."""
    if value is None:
        return None
    if value < 4:
        return 'Very Cold Stress'
    elif value < 8:
        return 'Cold Stress'
    elif value < 13:
        return 'Slight Cold Stress'
    elif value < 18:
        return 'No Thermal Stress (cool)'
    elif value < 23:
        return 'Comfortable'
    elif value < 29:
        return 'No Thermal Stress (warm)'
    elif value < 35:
        return 'Slight Heat Stress'
    elif value < 41:
        return 'Moderate Heat Stress'
    else:
        return 'Extreme Heat Stress'


def classify_utci(value):
    """Classify UTCI value into thermal stress category."""
    if value is None:
        return None
    if value < -40:
        return 'Extreme Cold Stress'
    elif value < -27:
        return 'Very Strong Cold Stress'
    elif value < -13:
        return 'Strong Cold Stress'
    elif value < 0:
        return 'Moderate Cold Stress'
    elif value < 9:
        return 'Slight Cold Stress'
    elif value < 26:
        return 'No Thermal Stress'
    elif value < 32:
        return 'Moderate Heat Stress'
    elif value < 38:
        return 'Strong Heat Stress'
    elif value < 46:
        return 'Very Strong Heat Stress'
    else:
        return 'Extreme Heat Stress'


# (upper bound in °C, exclusive · label · gauge colour). PROVISIONAL bands
# (~25/28/30/33 °C, the commonly used WBGT steps): confirm against the
# standard the project follows before treating the labels as authoritative.
WBGT_BANDS = [
    (25, 'No Heat Stress', '#22c55e'),
    (28, 'Moderate Heat Stress', '#eab308'),
    (30, 'Strong Heat Stress', '#f97316'),
    (33, 'Very Strong Heat Stress', '#ef4444'),
    (float('inf'), 'Extreme Heat Stress', '#b91c1c'),
]


def _wbgt_band(value):
    return next(band for band in WBGT_BANDS if value < band[0])


def classify_wbgt(value):
    """Classify a WBGT value (°C) into a heat-stress category."""
    if value is None:
        return None
    return _wbgt_band(value)[1]


def wbgt_color(value):
    """Gauge colour matching classify_wbgt (None when there is no value)."""
    if value is None:
        return None
    return _wbgt_band(value)[2]


# ── Nature-Based Solutions ───────────────────────────────────────────

def calculate_nbs_coverage(adminUnit):
    """NBS coverage area and count.

    DAG edges:  UTCI → NBS
                PET  → NBS
    """
    polygons = NatureBasedSolutionPolygon.objects.filter(
        geom__intersects=adminUnit.geom,
    )
    points = NatureBasedSolutionPoint.objects.filter(
        geom__intersects=adminUnit.geom,
    )

    nbs_area = polygons.aggregate(total=Sum('area'))['total'] or 0

    return {
        'polygon_count': polygons.count(),
        'point_count': points.count(),
        'total_count': polygons.count() + points.count(),
        'total_area_km2': round(nbs_area / 1e6, 4),
        'total_area_m2': round(nbs_area, 1),
    }


# ── Meteorology Summary ─────────────────────────────────────────────

def get_latest_meteorology(adminUnit):
    """Latest meteorological reading within the administrative unit.

    Only hourly/instant readings (Meteorology.PERIOD_HOUR): daily rows hold
    24 h means (radiation about half the midday value, temperature below the
    afternoon's), which would understate heat stress if read as a reading.

    DAG edges:  Climate_Change     → Meteorology
                Anthropogenic_Heat → Meteorology
                Canyon_Aspect      → Meteorology
    """
    record = (
        Meteorology.objects
        .filter(station__geom__intersects=adminUnit.geom, station__is_active=True,
                period=Meteorology.PERIOD_HOUR)
        .order_by('-date')
        .first()
    )
    if not record:
        return None

    return {
        'temperature_C': record.temperature_C,
        'humidity_pct': record.humidity_percent,
        'wind_speed_m_s': record.wind_speed_m_s,
        'precipitation_mm': record.precipitation_mm,
        'solar_radiation_W_m2': record.solar_radiation_W_m2,
        'datetime': record.date,
    }
