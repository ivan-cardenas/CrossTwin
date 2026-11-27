"""
Postcode-area inputs of the WOZ value per m2 and the frozen accessibility baseline (housing.PostcodePrice), the
main fitting unit of the hedonic price model: a PC6 is a street section, so a municipality has hundreds of them
where it has a few dozen neighborhoods. Same logic as housing/calculations/woz.py, keyed on the postcode.

* The price level is CBS's mean WOZ value of the postcode area (administrative.Postcode6.meanWOZ_EUR, PDOK CBS
  postcode statistics) over the mean BAG usable area of the dwellings in it.
* The dwellings of a postcode area are the *Residential function* properties whose BAG postcode (builtup.Property
  .postalCode, spaces removed, upper case) is that code, not those inside the polygon: the BAG postcode is exact and
  needs no spatial join. Areas outside [chain.MIN_DWELLING_AREA_SQM, chain.WOZ_AREA_MAX_SQM] are dropped.
* The baseline is the mean builtup.Accessibility score of the buildings that hold such dwellings, per mode, and the
  mean value of each term of the price model (mode x amenity category, chain.term_values), frozen when the row is
  first written: freeze it before the amenities or the network are edited, because a later change is measured
  against it. A row frozen before the terms existed gets them once, at the next preparation.
* The WOZ value is used as published for its statistics year (the newest available); no valuation-date shift.
* The neighborhood and municipality of an area are those under its point on surface (the area can span several):
  they give the controls the postcode statistics lack (socio-economic status) and the municipality effects.
"""
from django.db import connection

from . import chain

DWELLING = "Residential function"
TERM_CHUNK = 2000   # buildings per query of mean_terms()
PC = "upper(replace(p.\"postalCode\", ' ', ''))"   # the BAG postcode as a PC6 code


def latest_year():
    """Newest statistics year with a postcode area that has a mean WOZ value; None without."""
    from administrative.models import Postcode6

    return (Postcode6.objects.filter(meanWOZ_EUR__isnull=False, dataYear__isnull=False)
            .order_by("-dataYear").values_list("dataYear", flat=True).first())


def mean_dwelling_area(codes):
    """{code: (mean area m2, dwellings counted)} for the postcode areas that have dwellings in the area range."""
    from builtup.models import Property

    codes = list(codes)
    if not codes:
        return {}
    sql = f"""
        SELECT pc, AVG(area), COUNT(*)
        FROM (
            SELECT {PC} AS pc, COALESCE(p."livingArea", p."grossArea") AS area
            FROM {Property._meta.db_table} p
            WHERE %s = ANY(p."usageFunction")
        ) d
        WHERE pc = ANY(%s) AND area BETWEEN %s AND %s
        GROUP BY pc
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, [DWELLING, codes, chain.MIN_DWELLING_AREA_SQM, chain.WOZ_AREA_MAX_SQM])
        return {pc: (mean, count) for pc, mean, count in cursor.fetchall()}


def mean_accessibility(codes):
    """{code: {mode: (mean score, network snapshot, method)}} over the buildings that hold the area's dwellings."""
    from builtup.models import Accessibility, Property

    codes = list(codes)
    if not codes:
        return {}
    sql = f"""
        SELECT x.pc, a.mode, AVG(a.score), MAX(a.network_snapshot), MAX(a.method)
        FROM (
            SELECT DISTINCT p.building_id, {PC} AS pc
            FROM {Property._meta.db_table} p
            WHERE %s = ANY(p."usageFunction")
        ) x
        JOIN {Accessibility._meta.db_table} a ON a.building_id = x.building_id
        WHERE x.pc = ANY(%s)
        GROUP BY x.pc, a.mode
    """
    result = {}
    with connection.cursor() as cursor:
        cursor.execute(sql, [DWELLING, codes])
        for pc, mode, mean, snapshot, method in cursor.fetchall():
            result.setdefault(pc, {})[mode] = (mean, snapshot, method)
    return result


def mean_terms(codes):
    """
    {code: {term: mean value 0-100}} of each price-model term over the buildings that hold the area's dwellings,
    from the stored distances to the amenities (chain.term_values). A building counts once per postcode area it
    holds dwellings of.
    """
    from collections import defaultdict

    from builtup.models import Accessibility, Property

    codes = list(codes)
    if not codes:
        return {}
    wanted = set(codes)
    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT DISTINCT p.building_id, {PC} AS pc FROM {Property._meta.db_table} p
            WHERE %s = ANY(p."usageFunction")""", [DWELLING])
        areas = defaultdict(list)
        for building, pc in cursor.fetchall():
            if pc in wanted:
                areas[building].append(pc)
    sums, counts = defaultdict(lambda: defaultdict(float)), defaultdict(lambda: defaultdict(int))
    building_ids = list(areas)
    for start in range(0, len(building_ids), TERM_CHUNK):
        chunk = building_ids[start:start + TERM_CHUNK]
        for building, mode, distances in (Accessibility.objects.filter(building_id__in=chunk)
                                          .values_list("building_id", "mode", "distances")):
            values = chain.term_values(distances, mode)
            for pc in areas[building]:
                for term, value in values.items():
                    sums[pc][term] += value
                    counts[pc][term] += 1
    return {pc: {term: total / counts[pc][term] for term, total in terms.items()} for pc, terms in sums.items()}


def building_controls(codes):
    """{code: {"constructionYear", "energyLabel"}}: means over the buildings that hold the area's dwellings."""
    from builtup.models import Building, Property

    from .price_model import CONSTRUCTION_YEAR_RANGE, ENERGY_ORDINAL

    codes = list(codes)
    if not codes:
        return {}
    wanted = set(codes)
    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT DISTINCT p.building_id, {PC} AS pc FROM {Property._meta.db_table} p
            WHERE %s = ANY(p."usageFunction")""", [DWELLING])
        pairs = {(b, pc) for b, pc in cursor.fetchall() if pc in wanted}
    attrs = {b: (year, label) for b, year, label in
             Building.objects.filter(pk__in={b for b, _ in pairs}).values_list("pk", "constructionYear", "energyLabel")}
    lo, hi = CONSTRUCTION_YEAR_RANGE
    years, labels = {}, {}
    for building, pc in pairs:
        year, label = attrs.get(building, (None, None))
        if year is not None and lo <= year <= hi:
            years.setdefault(pc, []).append(year)
        if label in ENERGY_ORDINAL:
            labels.setdefault(pc, []).append(ENERGY_ORDINAL[label])
    return {pc: {"constructionYear": sum(years[pc]) / len(years[pc]) if pc in years else None,
                 "energyLabel": sum(labels[pc]) / len(labels[pc]) if pc in labels else None} for pc in codes}


def anchors(codes):
    """{code: (neighborhood_id, city_id)} under each area's point on surface (None where there is none)."""
    from administrative.models import City, District, Neighborhood, Postcode6

    codes = list(codes)
    if not codes:
        return {}
    sql = f"""
        SELECT pc.code, n.id, d.city_id
        FROM {Postcode6._meta.db_table} pc
        LEFT JOIN LATERAL (
            SELECT id, district_id FROM {Neighborhood._meta.db_table} n
            WHERE ST_Contains(n.geom, ST_PointOnSurface(pc.geom)) LIMIT 1
        ) n ON TRUE
        LEFT JOIN {District._meta.db_table} d ON d.id = n.district_id
        WHERE pc.code = ANY(%s)
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, [codes])
        return {code: (hood, city) for code, hood, city in cursor.fetchall()}


def freeze_baselines(rows, overwrite=False):
    """
    Write the mean accessibility of each row's area onto its baseline fields, once: the mean score per mode and the
    mean value of each term. A field that already holds a baseline is kept unless `overwrite`; the terms are
    written separately, so a row frozen before they existed gets them without its scores changing. Rows are saved.
    Returns the rows written.
    """
    todo = [row for row in rows if overwrite or not row.baselineCategories
            or (row.baselineAccessWalk is None and row.baselineAccessBike is None)]
    codes = {row.postcode6 for row in todo}
    access = mean_accessibility(codes)
    terms = mean_terms(codes)
    written = []
    for row in todo:
        modes = access.get(row.postcode6)
        if not modes:
            continue
        if overwrite or (row.baselineAccessWalk is None and row.baselineAccessBike is None):
            walk, bike = modes.get("walk"), modes.get("bike")
            row.baselineAccessWalk = round(walk[0], 2) if walk else None
            row.baselineAccessBike = round(bike[0], 2) if bike else None
            snapshots = [m[1] for m in modes.values() if m[1]]
            row.baselineSnapshot = max(snapshots) if snapshots else None
            row.baselineMethod = next((m[2] for m in modes.values() if m[2]), "")
        if (overwrite or not row.baselineCategories) and terms.get(row.postcode6):
            row.baselineCategories = {term: round(value, 2) for term, value in terms[row.postcode6].items()}
        row.save()
        written.append(row)
    return written


def prepare(year=None, refreeze=False):
    """
    Write (or refresh) one housing.PostcodePrice per postcode area of the statistics year: the CBS figures, the BAG
    mean area, the derived WOZ per m2, the neighborhood and municipality under it, and the accessibility baseline
    (frozen once, or frozen again when `refreeze`). Returns the rows. Raises ValueError without postcode areas that have a mean WOZ value.
    """
    from administrative.models import Postcode6

    from housing.models import PostcodePrice

    year = year or latest_year()
    if year is None:
        raise ValueError("No postcode area (PC6) with a mean WOZ value is stored: import 'Postcode areas - PC6' (CBS) first.")
    areas = list(Postcode6.objects.filter(dataYear=year, meanWOZ_EUR__isnull=False))
    codes = [a.code for a in areas]
    sizes = mean_dwelling_area(codes)
    where = anchors(codes)
    stored = {row.postcode6: row for row in PostcodePrice.objects.filter(year=year, postcode6__in=codes)}
    rows = []
    for area in areas:
        mean, count = sizes.get(area.code, (None, None))
        hood, city = where.get(area.code, (None, None))
        row = stored.get(area.code) or PostcodePrice(postcode6=area.code, year=year)
        row.postcode4 = area.code[:4]
        row.avgWOZ_EUR = area.meanWOZ_EUR
        row.dwellings = area.dwellings
        row.multiFamilyShare_pct = (100.0 * area.multiFamilyDwellings / area.dwellings
                                    if area.dwellings and area.multiFamilyDwellings is not None else None)
        row.rentalShare_pct = area.rental_pct
        row.meanArea_sqm = round(mean, 2) if mean is not None else None
        row.areaDwellings = count
        row.neighborhood_id = hood
        row.city_id = city
        row.geom = area.geom
        row.save()
        rows.append(row)
    freeze_baselines(rows, overwrite=refreeze)
    return rows
