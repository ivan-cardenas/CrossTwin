from django.db.models import Sum, Avg, Count, Max, Min, Q
from django.contrib.gis.db.models.functions import Area, Intersection
from django.db import connection

from .models import (
    MeanRadiantTemperature, UTCI, SkyViewFactor, PET,
    LandSurfaceTemperature, SurfaceUrbanHeatIslandIntensity,
    NatureBasedSolutionPolygon, NatureBasedSolutionPoint,
    StressCategory,
)
from common.models import Province, LandCoverVector, DigitalSurfaceModel
from builtup.models import Park, Building, Street
from weather.models import Meteorology


# ── Vegetation & Green Area ──────────────────────────────────────────

def calculate_green_area(province):
    """Total green area (parks + green land cover) in km².

    DAG edges:  LandCover → Green_Area
    """
    # Parks within province
    park_area_m2 = (
        Park.objects
        .filter(geom__intersects=province.geom)
        .aggregate(total=Sum('area'))['total'] or 0
    )

    # Green land cover classes (forest, grass, vegetation-related)
    green_keywords = ['forest', 'grass', 'green', 'vegetation', 'tree', 'park', 'nature']
    green_filter = Q()
    for kw in green_keywords:
        green_filter |= Q(land_cover_type__class_name__icontains=kw)

    green_lc_pct = (
        LandCoverVector.objects
        .filter(green_filter, Province=province)
        .aggregate(total=Sum('percentage'))['total'] or 0
    )

    province_area_km2 = province.area_km2 or 0
    green_lc_km2 = province_area_km2 * green_lc_pct / 100

    return {
        'park_area_km2': round(park_area_m2 / 1e6, 3),
        'green_lc_km2': round(green_lc_km2, 3),
        'total_green_km2': round(park_area_m2 / 1e6 + green_lc_km2, 3),
    }


def calculate_vegetation_coverage(province):
    """Vegetation coverage as percentage of province area.

    DAG edges:  Green_Area → Vegetation_Coverage
                Vegetation_Coverage → DSM
    """
    green = calculate_green_area(province)
    province_area = province.area_km2 or 0
    if province_area > 0:
        pct = round(green['total_green_km2'] / province_area * 100, 1)
    else:
        pct = 0
    return {
        **green,
        'vegetation_coverage_pct': pct,
    }


# ── Urban Morphology ─────────────────────────────────────────────────

def calculate_urban_morphology(province):
    """Building and street statistics relevant to canyon geometry.

    DAG edges:  Buildings → DSM, Canyon_Aspect
                Streets   → Canyon_Aspect
    """
    buildings = Building.objects.filter(geom__intersects=province.geom)
    streets = Street.objects.filter(geom__intersects=province.geom)

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

    return {
        'building_count': bldg_agg['count'] or 0,
        'avg_building_height_m': round(bldg_agg['avg_height'] or 0, 1),
        'max_building_height_m': round(bldg_agg['max_height'] or 0, 1),
        'total_footprint_km2': round((bldg_agg['total_footprint'] or 0) / 1e6, 3),
        'street_count': street_agg['count'] or 0,
        'avg_street_width_m': round(street_agg['avg_width'] or 0, 1),
        # Aspect ratio proxy: avg_height / avg_width (H/W)
        'aspect_ratio': round(
            (bldg_agg['avg_height'] or 0) / (street_agg['avg_width'] or 1), 2
        ),
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


def get_thermal_indices(province):
    """Aggregate raster statistics for all thermal indices.

    DAG edges:  Meteorology → Tmrt, PET, UTCI
                DSM → SVF → Tmrt, PET
                LST → PET
                Tmrt → PET, UTCI
    """
    geom_wkt = province.geom.wkt
    srid = province.geom.srid

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


# ── Nature-Based Solutions ───────────────────────────────────────────

def calculate_nbs_coverage(province):
    """NBS coverage area and count.

    DAG edges:  UTCI → NBS
                PET  → NBS
    """
    polygons = NatureBasedSolutionPolygon.objects.filter(
        geom__intersects=province.geom,
    )
    points = NatureBasedSolutionPoint.objects.filter(
        geom__intersects=province.geom,
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

def get_latest_meteorology(province):
    """Latest meteorological measurements within the province.

    DAG edges:  Climate_Change     → Meteorology
                Anthropogenic_Heat → Meteorology
                Canyon_Aspect      → Meteorology
    """
    record = (
        Meteorology.objects
        .filter(station__geom__intersects=province.geom, station__is_active=True)
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
