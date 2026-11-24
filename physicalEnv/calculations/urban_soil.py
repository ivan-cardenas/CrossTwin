"""
Urban land as part of the soil map.

The BIS soil map (Bodemkaart 1:50 000) has no polygon under most built-up
land, so soil_landcover_composition() finds no soil there and those pieces
drop out of the infiltration (they are not even reported as unclassified).
fill_urban_soil_gaps() stores the missing ground as SoilArea rows of the
SoilType "Urban land" (soil.URBAN_SOIL_CODE): the built-up land-cover polygons
of the latest year, minus the soil map. Infiltration then reads them like any
other soil: group URBAN_SOIL_GROUP, with the sealed share still coming from
the land cover (soil.IMPERVIOUS_FRACTIONS).

DAG edges:  LandCover -> Infiltration
            Soil_Type -> Infiltration   (Urban land stands in for the missing soil)

Deterministic: the same land cover and soil map give the same rows, keyed by
a hash of the geometry (mapAreaID 'urban-<hash>'), so a rerun replaces them.
"""
import hashlib
import logging

from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.db import connection, transaction
from django.utils import timezone

from .soil import DRAINED_LAND_COVER, URBAN_SOIL_CODE, URBAN_SOIL_NAME

logger = logging.getLogger(__name__)

URBAN_AREA_PREFIX = "urban-"
MIN_GAP_M2 = 1.0   # drops slivers where an urban polygon edge meets a soil polygon edge


def get_urban_soil_type():
    from ..models import SoilType
    soil_type, _ = SoilType.objects.get_or_create(
        code=URBAN_SOIL_CODE, name=URBAN_SOIL_NAME,
        defaults={"unitCode": URBAN_SOIL_CODE, "unitName": URBAN_SOIL_NAME},
    )
    return soil_type


def urban_gap_geometries(region):
    """
    Polygons (storage CRS) of built-up land inside `region` that no soil-map
    polygon covers: land cover of a drained class (soil.DRAINED_LAND_COVER) in
    the latest land-cover year there, minus every SoilArea that is not itself
    an urban fill.
    """
    from ..models import LandCoverClasses, LandCoverVector, SoilArea, SoilType
    from ..signals import _area_sql

    landcover, classes = LandCoverVector._meta.db_table, LandCoverClasses._meta.db_table
    soil, soil_type = SoilArea._meta.db_table, SoilType._meta.db_table
    unit = "ST_GeomFromEWKB(%(geom)s)"
    urban_regex = r"\y(" + "|".join(DRAINED_LAND_COVER) + ")"
    sql = f"""
        WITH latest AS (
            SELECT MAX(l.year) AS year FROM "{landcover}" l
            WHERE l.geom && {unit} AND ST_Intersects(l.geom, {unit})
        ), urban AS (
            SELECT ST_Intersection(ST_UnaryUnion(ST_Collect(l.geom)), {unit}) AS geom
            FROM "{landcover}" l JOIN "{classes}" c ON c.id = l.land_cover_type_id
            WHERE l.geom && {unit} AND l.year = (SELECT year FROM latest)
              AND lower(c.class_name) ~ %(urban)s
        ), covered AS (
            SELECT ST_UnaryUnion(ST_Collect(s.geom)) AS geom
            FROM "{soil}" s JOIN "{soil_type}" t ON t.id = s.soil_type_id
            WHERE s.geom && {unit} AND t.code <> %(code)s
        ), gap AS (
            SELECT CASE WHEN covered.geom IS NULL THEN urban.geom
                        ELSE ST_Difference(urban.geom, covered.geom) END AS geom
            FROM urban CROSS JOIN covered
        )
        SELECT ST_AsEWKB(d.geom) FROM gap, LATERAL ST_Dump(gap.geom) d
        WHERE ST_GeometryType(d.geom) = 'ST_Polygon' AND {_area_sql("d.geom")} >= %(min)s
        ORDER BY ST_AsBinary(d.geom)
    """
    params = {"geom": bytes(region.ewkb), "urban": urban_regex, "code": URBAN_SOIL_CODE, "min": MIN_GAP_M2}
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return [GEOSGeometry(memoryview(bytes(row[0]))) for row in cursor.fetchall()]


def fill_urban_soil_gaps(region, refresh=True):
    """
    Replace the "Urban land" SoilAreas inside `region` (a geometry in the
    storage CRS) by the current gaps of the soil map under built-up land.
    Returns the number of areas stored. With refresh, the fresh-water sources
    that overlap the region are re-saved so their infiltration follows
    (the importer's finalizer passes False and refreshes itself).
    """
    from core.cache import bump_layer_version
    from watersupply.signals import refresh_freshwater

    from ..models import SoilArea, SoilType

    gaps = urban_gap_geometries(region)
    soil_type = get_urban_soil_type() if gaps else SoilType.objects.filter(code=URBAN_SOIL_CODE).first()
    now = timezone.now()
    rows = []
    for poly in gaps:
        if poly.srid is None:
            poly.srid = region.srid
        digest = hashlib.sha1(bytes(poly.wkb)).hexdigest()[:16]
        rows.append(SoilArea(mapAreaID=f"{URBAN_AREA_PREFIX}{digest}", soil_type=soil_type,
                             geom=MultiPolygon(poly, srid=poly.srid), last_updated=now))
    with transaction.atomic():
        if soil_type is not None:
            SoilArea.objects.filter(soil_type=soil_type, geom__intersects=region).delete()
        SoilArea.objects.bulk_create(rows, batch_size=500, ignore_conflicts=True)
    bump_layer_version(SoilArea)
    if refresh:
        refresh_freshwater(region)
    logger.info("Urban land: %d soil area(s) stored inside the region", len(rows))
    return len(rows)
