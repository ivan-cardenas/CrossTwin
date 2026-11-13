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
DEFAULT_SERVICE_BUFFER_M = 500.0

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
