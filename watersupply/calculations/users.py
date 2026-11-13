"""
Water supply users from the properties (DAG node NumberUsers = watersupply.UsersLocation).

A users location is each property (home): its users are the property's
inhabitants (builtup.Property.residents, the city's CBS persons per home,
written by housing/signals.py for dwellings). A neighborhood's UsersLocation
sums them:

    usersTotal       = Σ residents of the neighborhood's properties
    populationServed = Σ residents of the properties within buffer_m of a pipe

"Within buffer_m of any pipe" is the same as "inside the dissolved buffer of
the network" (CoverageWaterSupply.geom), but uses the pipes' GiST index and
needs no union.

DAG edges: Total_Population -> NumberUsers (residents)
           Coverage_WS_Area -> NumberUsers (the pipe buffer)
"""
from collections import namedtuple

from django.db import connection

# Service distance of a pipe when the city has no CoverageWaterSupply record
# (CrossTwin assumption; the same default as CoverageWaterSupply.buffer_m).
DEFAULT_SERVICE_BUFFER_M = 50.0

DWELLING = "Residential function"   # BAG woonfunctie label in Property.usageFunction

NeighborhoodUsers = namedtuple(
    "NeighborhoodUsers", "residents residents_served dwellings dwellings_served")


def service_buffer_m(city_id):
    """buffer_m of the city's latest CoverageWaterSupply record, else the default."""
    from watersupply.models import CoverageWaterSupply

    buffer_m = (CoverageWaterSupply.objects.filter(city_id=city_id)
                .order_by('-year', '-id').values_list('buffer_m', flat=True).first())
    return float(buffer_m) if buffer_m is not None else DEFAULT_SERVICE_BUFFER_M


def _tables():
    from builtup.models import Building, Property
    from watersupply.models import PipeNetwork

    return Property._meta.db_table, Building._meta.db_table, PipeNetwork._meta.db_table


def neighborhood_users(neighborhood_ids, buffer_m):
    """
    {neighborhood_id: NeighborhoodUsers} for the given neighborhoods (only those
    with at least one property). Residents are summed over every property that
    has them (dwellings); dwellings are counted by their BAG usage function.
    One SQL statement.
    """
    neighborhood_ids = [n for n in neighborhood_ids if n is not None]
    if not neighborhood_ids:
        return {}
    prop, building, pipe = _tables()
    sql = f"""
        SELECT b.neighborhood_id,
               COALESCE(SUM(p.residents), 0),
               COALESCE(SUM(p.residents) FILTER (WHERE s.served), 0),
               COUNT(*) FILTER (WHERE p."usageFunction" @> ARRAY[%s]::varchar[]),
               COUNT(*) FILTER (WHERE s.served AND p."usageFunction" @> ARRAY[%s]::varchar[])
          FROM {prop} p
          JOIN {building} b ON b.id = p.building_id
          CROSS JOIN LATERAL (
                SELECT EXISTS (SELECT 1 FROM {pipe} n
                                WHERE ST_DWithin(n.geom, p.geom, %s)) AS served
          ) s
         WHERE b.neighborhood_id = ANY(%s)
         GROUP BY b.neighborhood_id
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, [DWELLING, DWELLING, float(buffer_m), list(neighborhood_ids)])
        return {row[0]: NeighborhoodUsers(float(row[1]), float(row[2]), row[3], row[4])
                for row in cursor.fetchall()}


def neighborhoods_with_residents(neighborhood_ids):
    """The subset of the given neighborhoods that hold at least one property with residents."""
    from builtup.models import Property

    return set(
        Property.objects.filter(building__neighborhood_id__in=list(neighborhood_ids),
                                residents__isnull=False)
        .values_list('building__neighborhood_id', flat=True).distinct()
    )


def neighborhoods_near(geoms, distance_m):
    """Neighborhoods holding a property within distance_m of any of the geometries."""
    from django.db.models import Q

    from builtup.models import Property

    geoms = [g for g in geoms if g is not None]
    if not geoms:
        return set()
    near = Q()
    for geom in geoms:
        near |= Q(geom__dwithin=(geom, float(distance_m)))
    return set(
        Property.objects.filter(near, building__neighborhood_id__isnull=False)
        .values_list('building__neighborhood_id', flat=True).distinct()
    )


# Most unserved homes one map request returns (the map clusters them).
UNSERVED_MAX_FEATURES = 20_000


def unserved_properties(bbox_wgs84=None, limit=UNSERVED_MAX_FEATURES):
    """
    GeoJSON FeatureCollection (WGS84 points) of the properties with residents
    that no pipe reaches: no PipeNetwork within the service buffer of their
    city (service_buffer_m: the city's latest CoverageWaterSupply.buffer_m,
    else DEFAULT_SERVICE_BUFFER_M). The complement of populationServed, per home.
    Properties not linked to a neighborhood use the default buffer.
    `bbox_wgs84` = (minLng, minLat, maxLng, maxLat). One SQL statement.
    """
    from django.conf import settings

    from administrative.models import District, Neighborhood
    from watersupply.models import CoverageWaterSupply

    prop, building, pipe = _tables()
    params = [float(DEFAULT_SERVICE_BUFFER_M)]
    where = ["p.residents > 0"]
    if bbox_wgs84:
        where.append("p.geom && ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 4326), %s)")
        params += [*map(float, bbox_wgs84), int(settings.COORDINATE_SYSTEM)]
    params.append(int(limit))
    sql = f"""
        WITH buffers AS (
            SELECT DISTINCT ON (city_id) city_id, buffer_m
              FROM {CoverageWaterSupply._meta.db_table}
             WHERE city_id IS NOT NULL AND buffer_m IS NOT NULL
             ORDER BY city_id, year DESC, id DESC
        ), homes AS (
            SELECT p.id, p.geom, p.residents, b.neighborhood_id,
                   COALESCE(c.buffer_m, %s) AS buffer_m
              FROM {prop} p
              LEFT JOIN {building} b ON b.id = p.building_id
              LEFT JOIN {Neighborhood._meta.db_table} nb ON nb.id = b.neighborhood_id
              LEFT JOIN {District._meta.db_table} d ON d.id = nb.district_id
              LEFT JOIN buffers c ON c.city_id = d.city_id
             WHERE {" AND ".join(where)}
        )
        SELECT json_build_object(
                   'type', 'FeatureCollection',
                   'features', COALESCE(json_agg(json_build_object(
                       'type', 'Feature',
                       'geometry', ST_AsGeoJSON(ST_Transform(ST_PointOnSurface(h.geom), 4326), 6)::json,
                       'properties', json_build_object(
                           'id', h.id, 'residents', h.residents, 'buffer_m', h.buffer_m)
                   )), '[]'::json))::text
          FROM (SELECT * FROM homes h
                 WHERE NOT EXISTS (SELECT 1 FROM {pipe} n
                                    WHERE ST_DWithin(n.geom, h.geom, h.buffer_m))
                 LIMIT %s) h
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchone()[0]
