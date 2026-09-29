import logging
import threading
from contextlib import contextmanager

from django.db import connection
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Max, Q
from django.utils import timezone

from core.cache import bump_layer_version
from .models import LandCoverClasses, LandCoverVector
from administrative.models import Neighborhood, District, City, Province
# Reused from administrative's own population cascade rather than
# duplicated -- see administrative/signals.py for the shared aggregation
# logic this re-enters after writing Neighborhood.urban_area below.
from administrative.signals import _recompute_population

logger = logging.getLogger(__name__)

URBAN_AREA_KEYWORDS = ["urban fabric", "road", "rail", "transport"]

# Per-thread set of city ids whose recompute is postponed; None when not deferring.
_deferred = threading.local()


def _urban_area_filter():
    """Q object: land_cover_type.class_name case-insensitively contains
    any of URBAN_AREA_KEYWORDS. class_name is a free-form lookup value
    populated at import time (see importer/external_catalog.py's
    pdok_landcover_brt entry), not a fixed enum, so substring matching is
    used rather than exact equality -- matching the same convention as
    core/landCoverStyles.py's KEYWORD_COLORS. The set-based SQL in
    _recompute_neighborhood_urban_area applies the same rule as
    `class_name ILIKE ANY(...)`."""
    q = Q()
    for kw in URBAN_AREA_KEYWORDS:
        q |= Q(land_cover_type__class_name__icontains=kw)
    return q


def _area_sql(expr):
    """ST_Area in m²: planar for a projected storage CRS (RD New), geography for a geodetic one."""
    if LandCoverVector._meta.get_field("geom").geodetic(connection):
        return f"ST_Area(({expr})::geography)"
    return f"ST_Area({expr})"


def _recompute_neighborhood_urban_area(city_id):
    """
    Recompute urban_area for every Neighborhood under city_id, from the
    most recent LandCoverVector year available for that city, then
    manually re-enter administrative/signals.py's population/urban_area
    cascade. The UPDATE below does not fire post_save, so nothing else will
    push this change up to District/City/Province.

    One set-based statement for all neighborhoods of the city (instead of an
    Intersection aggregate + UPDATE per neighborhood). Land-cover polygons
    that lie entirely inside a neighborhood contribute their own area; only
    the ones crossing its boundary are clipped with ST_Intersection. The
    cascade then runs once per district and once for the city and province,
    not once per district all the way up. See docs/PERFORMANCE.md §2.
    """
    latest_year = LandCoverVector.objects.filter(city_id=city_id).aggregate(
        latest=Max('year')
    )['latest']
    # No LandCoverVector rows left for this city (e.g. the last one was just
    # deleted) -- don't bail out early, still recompute so existing
    # Neighborhoods reset to 0.0 instead of keeping a stale value. A NULL
    # year matches no land cover, so every neighborhood gets 0.

    neighborhoods = Neighborhood._meta.db_table
    districts = District._meta.db_table
    landcover = LandCoverVector._meta.db_table
    classes = LandCoverClasses._meta.db_table
    area_inside = _area_sql("l.geom")
    area_clipped = _area_sql("ST_Intersection(l.geom, h.geom)")

    sql = f"""
        WITH hood AS (
            SELECT n.id, n.district_id, n.geom
            FROM "{neighborhoods}" n
            JOIN "{districts}" d ON d.id = n.district_id
            WHERE d.city_id = %(city)s
        ), urban AS (
            SELECT h.id,
                   SUM(CASE WHEN ST_Within(l.geom, h.geom) THEN {area_inside}
                            ELSE {area_clipped} END) AS area_m2
            FROM hood h
            JOIN "{landcover}" l ON l.geom && h.geom AND ST_Intersects(l.geom, h.geom)
            JOIN "{classes}" c ON c.id = l.land_cover_type_id
            WHERE l.city_id = %(city)s
              AND l.year = %(year)s
              AND c.class_name ILIKE ANY(%(patterns)s)
            GROUP BY h.id
        )
        UPDATE "{neighborhoods}" n
        SET urban_area = COALESCE(urban.area_m2, 0) / 1e6,
            last_updated = %(now)s
        FROM hood
        LEFT JOIN urban ON urban.id = hood.id
        WHERE n.id = hood.id
        RETURNING hood.district_id
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, {
            "city": city_id,
            "year": latest_year,
            "patterns": [f"%{kw}%" for kw in URBAN_AREA_KEYWORDS],
            "now": timezone.now(),
        })
        district_ids = {row[0] for row in cursor.fetchall()}

    if not district_ids:
        return
    bump_layer_version(Neighborhood)

    city_pk = None
    for district_id in district_ids:
        city_pk = _recompute_population(
            District, district_id,
            child_model=Neighborhood, child_fk='district_id', parent_fk='city_id',
        ) or city_pk
    if not city_pk:
        return
    province_pk = _recompute_population(
        City, city_pk,
        child_model=District, child_fk='city_id', parent_fk='province_id',
    )
    if province_pk:
        _recompute_population(Province, province_pk, child_model=City, child_fk='province_id')


@contextmanager
def deferred_urban_area():
    """
    Postpone the urban-area recompute until the block ends, then run it once
    per affected city. A bulk land-cover import otherwise re-runs the whole
    per-city recompute for every polygon it saves (N polygons x M
    neighborhoods of work). Nested uses defer to the outermost one.
    """
    if getattr(_deferred, "cities", None) is not None:
        yield
        return

    _deferred.cities = set()
    try:
        yield
    except BaseException:
        cities, _deferred.cities = _deferred.cities, None
        try:
            for city_id in cities:
                _recompute_neighborhood_urban_area(city_id)
        except Exception:
            # e.g. the transaction is already broken; don't mask the original error
            logger.exception("Deferred urban-area recompute failed after an aborted block")
        raise
    else:
        cities, _deferred.cities = _deferred.cities, None
        for city_id in cities:
            _recompute_neighborhood_urban_area(city_id)


def schedule_urban_area_recompute(city_id):
    """Recompute a city's urban area now, or at the end of the enclosing deferred_urban_area()."""
    if not city_id:
        return
    cities = getattr(_deferred, "cities", None)
    if cities is not None:
        cities.add(city_id)
    else:
        _recompute_neighborhood_urban_area(city_id)


@receiver(post_save, sender=LandCoverVector, dispatch_uid="landcover_save_to_neighborhood_urban_area")
@receiver(post_delete, sender=LandCoverVector, dispatch_uid="landcover_delete_to_neighborhood_urban_area")
def landcover_changed(sender, instance, **kwargs):
    # Bulk imports wrap their writes in deferred_urban_area() (see
    # importer/batching.py), so this recomputes once per city per import
    # instead of once per saved polygon.
    schedule_urban_area_recompute(instance.city_id)
