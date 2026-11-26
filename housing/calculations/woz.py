"""
Neighborhood inputs of the WOZ value per m2 and the frozen accessibility baseline
(housing.WOZValue). Set-based SQL, one statement per quantity for all the given
neighborhoods. The ratio itself is housing/calculations/chain.py::woz_per_sqm.

The dwelling area is the BAG usable area of the *Residential function*
properties whose point lies inside the neighborhood: builtup.Property.livingArea,
else grossArea (the PDOK import stores the BAG oppervlakte in grossArea).
Areas outside [chain.MIN_DWELLING_AREA_SQM, chain.WOZ_AREA_MAX_SQM] are dropped,
as BAG holds placeholder values for some objects.

The baseline is the mean builtup.Accessibility score of the residential
buildings (those with at least one dwelling) whose centroid lies inside the
neighborhood, per mode. It is frozen: written when the WOZ row is imported or
when a staff run asks for it, never refreshed by a receiver, so a later
amenity change is measured against the state the price level belongs to.
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


def mean_accessibility(neighborhood_ids):
    """
    {neighborhood_id: {mode: (mean score, network snapshot, method)}} over the
    residential buildings of each neighborhood.
    """
    from builtup.models import Accessibility, Property
    from administrative.models import Neighborhood

    ids = list(neighborhood_ids)
    if not ids:
        return {}
    sql = f"""
        SELECT n.id, a.mode, AVG(a.score), MAX(a.network_snapshot), MAX(a.method)
        FROM {Neighborhood._meta.db_table} n
        JOIN {Accessibility._meta.db_table} a ON ST_Within(a.geom, n.geom)
        WHERE n.id = ANY(%s)
          AND EXISTS (
              SELECT 1 FROM {Property._meta.db_table} p
              WHERE p.building_id = a.building_id AND %s = ANY(p."usageFunction"))
        GROUP BY n.id, a.mode
    """
    result = {}
    with connection.cursor() as cursor:
        cursor.execute(sql, [ids, DWELLING])
        for nid, mode, mean, snapshot, method in cursor.fetchall():
            result.setdefault(nid, {})[mode] = (mean, snapshot, method)
    return result


def fill_areas(rows):
    """Set meanArea_sqm / areaDwellings on unsaved or stored WOZValue rows (one query for all)."""
    rows = list(rows)
    areas = mean_dwelling_area({row.neighborhood_id for row in rows})
    for row in rows:
        mean, count = areas.get(row.neighborhood_id, (None, None))
        row.meanArea_sqm = round(mean, 2) if mean is not None else None
        row.areaDwellings = count
    return rows


def freeze_baselines(rows, overwrite=False):
    """
    Write the mean accessibility of each row's neighborhood onto its baseline
    fields, once: a row that already has a baseline is kept unless `overwrite`.
    Rows are saved. Returns the rows written.
    """
    rows = [row for row in rows if overwrite or (row.baselineAccessWalk is None and row.baselineAccessBike is None)]
    access = mean_accessibility({row.neighborhood_id for row in rows})
    written = []
    for row in rows:
        modes = access.get(row.neighborhood_id)
        if not modes:
            continue
        walk, bike = modes.get("walk"), modes.get("bike")
        row.baselineAccessWalk = round(walk[0], 2) if walk else None
        row.baselineAccessBike = round(bike[0], 2) if bike else None
        snapshots = [m[1] for m in modes.values() if m[1]]
        row.baselineSnapshot = max(snapshots) if snapshots else None
        row.baselineMethod = next((m[2] for m in modes.values() if m[2]), "")
        row.save()
        written.append(row)
    return written
