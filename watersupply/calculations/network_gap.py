"""
Urban area the pipe network does not reach (DAG edge CityArea -> Network).

The city's urban area is its urban land cover (the same classes as the
neighborhoods' urban_area: physicalEnv.signals.URBAN_AREA_KEYWORDS) of the
latest land-cover year up to the coverage record's year (else the earliest
later one). The part of it outside the network's service area
(CoverageWaterSupply.geom, the pipes buffered by buffer_m) is urban growth
that the network has not followed: it flags where the network should be
extended. It does not extend the network (the edge is partial).

    urban_km2    = Σ area(urban polygons of the city)
    uncovered_km2 = Σ area(urban polygon − service area)
"""
from collections import namedtuple

from django.db import connection

UrbanGap = namedtuple("UrbanGap", "landcover_year urban_km2 uncovered_km2")


def landcover_year(city_id, year):
    """Latest land-cover year of the city up to `year`, else its earliest later one, else None."""
    from physicalEnv.models import LandCoverVector

    years = LandCoverVector.objects.filter(city_id=city_id).values_list('year', flat=True)
    earlier = years.filter(year__lte=year).order_by('-year').first()
    return earlier if earlier is not None else years.order_by('year').first()


def urban_gap(city_id, year, service_area):
    """
    UrbanGap for the city's coverage record of `year` with service area
    `service_area` (a geometry in the storage CRS, or None = no network).
    None when the city has no land cover. One SQL statement.
    """
    from physicalEnv.models import LandCoverClasses, LandCoverVector
    from physicalEnv.signals import URBAN_AREA_KEYWORDS, _area_sql

    lc_year = landcover_year(city_id, year)
    if lc_year is None:
        return None
    area = _area_sql("l.geom")
    outside = _area_sql("ST_Difference(l.geom, s.geom)")
    sql = f"""
        WITH s AS (SELECT ST_GeomFromEWKB(%(service)s) AS geom)
        SELECT COALESCE(SUM({area}), 0),
               COALESCE(SUM(CASE
                   WHEN s.geom IS NULL OR NOT ST_Intersects(l.geom, s.geom) THEN {area}
                   WHEN ST_Within(l.geom, s.geom) THEN 0
                   ELSE {outside} END), 0)
          FROM "{LandCoverVector._meta.db_table}" l
          JOIN "{LandCoverClasses._meta.db_table}" c ON c.id = l.land_cover_type_id
          CROSS JOIN s
         WHERE l.city_id = %(city)s AND l.year = %(year)s
           AND c.class_name ILIKE ANY(%(patterns)s)
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, {
            "service": bytes(service_area.ewkb) if service_area is not None else None,
            "city": city_id,
            "year": lc_year,
            "patterns": [f"%{kw}%" for kw in URBAN_AREA_KEYWORDS],
        })
        urban_m2, uncovered_m2 = cursor.fetchone()
    return UrbanGap(lc_year, round(urban_m2 / 1e6, 4), round(uncovered_m2 / 1e6, 4))
