"""
Neighborhood input of the WOZ value per m2 (housing.WOZValue): the mean BAG dwelling area. Set-based SQL for all
the given neighborhoods. The ratio itself is housing/calculations/chain.py::woz_per_sqm.

The dwelling area is the BAG usable area of the *Residential function*
properties whose point lies inside the neighborhood: builtup.Property.livingArea,
else grossArea (the PDOK import stores the BAG oppervlakte in grossArea).
Areas outside [chain.MIN_DWELLING_AREA_SQM, chain.WOZ_AREA_MAX_SQM] are dropped,
as BAG holds placeholder values for some objects.
"""
from django.db import connection

from housing.calculations import chain

DWELLING = "Residential function"


def mean_dwelling_area(neighborhood_ids):
    """{neighborhood_id: (mean area m2, dwellings counted)} for the neighborhoods that have dwellings."""
    from builtup.models import Property
    from administrative.models import Neighborhood

    ids = list(neighborhood_ids)
    if not ids:
        return {}
    sql = f"""
        SELECT n.id, AVG(a.area), COUNT(*)
        FROM {Neighborhood._meta.db_table} n
        JOIN LATERAL (
            SELECT COALESCE(p."livingArea", p."grossArea") AS area
            FROM {Property._meta.db_table} p
            WHERE ST_Within(p.geom, n.geom)
              AND %s = ANY(p."usageFunction")
        ) a ON a.area BETWEEN %s AND %s
        WHERE n.id = ANY(%s)
        GROUP BY n.id
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, [DWELLING, chain.MIN_DWELLING_AREA_SQM, chain.WOZ_AREA_MAX_SQM, ids])
        return {nid: (mean, count) for nid, mean, count in cursor.fetchall()}


def fill_areas(rows):
    """Set meanArea_sqm / areaDwellings on unsaved or stored WOZValue rows (one query for all)."""
    rows = list(rows)
    areas = mean_dwelling_area({row.neighborhood_id for row in rows})
    for row in rows:
        mean, count = areas.get(row.neighborhood_id, (None, None))
        row.meanArea_sqm = round(mean, 2) if mean is not None else None
        row.areaDwellings = count
    return rows
