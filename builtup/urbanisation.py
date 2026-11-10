"""
Degree of Urbanisation: allocation, grid upkeep and refresh (DAG node
Degree_Urbanisation). Method and decisions: docs/DEGREE_OF_URBANISATION.md.

Pipeline (refresh()):

1. allocate(neighborhood_ids, year)   people -> residential properties -> cells,
                                      one set-based SQL statement per resolution
                                      (PopulationAllocation rows of those neighborhoods)
2. sync_cells(year, resolution)       UrbanisationCell rows = the cells holding any
                                      allocation; population, dwellings, built-up
                                      and coverage summed from the allocation
3. landcover_shares(...)              water and settlement shares of the cells
                                      from the latest land-cover year
4. classify_grid(year, resolution)    builtup/degurba.py over the whole grid
                                      (a new block can merge distant clusters)
5. refresh_units(year)                one Urbanisation row per neighborhood,
                                      district and city (save() equations), then
                                      City.urbanizationRate mirrored

Both resolutions run every time: 100 m (CrossTwin's local variant) and 1 km
(the original method on the same data), for the sensitivity comparison.

Automatic upkeep: builtup/signals.py schedules neighborhoods (population,
dwellings, buildings) and land-cover changes here. Nothing runs before the grid
was built once from the map's Degree of Urbanisation card (rebuild()), so
imports and tests that never use it pay nothing.
"""
import logging
import threading
import time
from contextlib import contextmanager

from django.conf import settings
from django.db import connection, transaction
from django.dispatch import Signal

logger = logging.getLogger(__name__)

RESOLUTIONS = (100, 1000)
LOCAL_RESOLUTION = 100

# Land-cover classes counted as settlement land (matched case-insensitively
# inside the class name, as physicalEnv/soil.py does). Anything else (fields,
# forest, heath, water) is open land.
SETTLEMENT_KEYWORDS = ("urban", "industrial", "commercial", "road", "rail", "port area", "airport",
                       "construction", "sport", "leisure", "built")
WATER_KEYWORDS = ("water", "sea and ocean", "estuar", "lagoon")
SETTLEMENT_SHARE = 0.5   # a cell is settlement land from this share of settlement classes

# Sent with year=... after the grid (both resolutions) was reclassified.
urbanisation_grid_changed = Signal()


# ── Console progress ([degurba] lines, like the [cog] export logs) ───────
# Everything runs on the CPU: allocation and land-cover overlays in PostGIS,
# the grid classification in numpy / scipy.ndimage. No GPU is used.

def _log(message):
    print(f"[degurba] {message}", flush=True)


@contextmanager
def _step(label):
    """Print a step's start and its duration."""
    _log(f"{label} ...")
    started = time.perf_counter()
    yield
    _log(f"  {label}: {time.perf_counter() - started:.2f} s")


# ── Grid ────────────────────────────────────────────────────────────

def storage_srid():
    return int(settings.COORDINATE_SYSTEM)


def grid_srid():
    """The storage CRS when it is projected in metres (EPSG:28992), else EPSG:3035 (LAEA Europe)."""
    from django.contrib.gis.gdal import SpatialReference

    srs = SpatialReference(storage_srid())
    if srs.projected and abs((srs.linear_units or 1.0) - 1.0) < 1e-9:
        return storage_srid()
    return 3035


def _tx(expr):
    g = grid_srid()
    return expr if g == storage_srid() else f"ST_Transform({expr}, {g})"


def _from_grid(expr):
    g = grid_srid()
    return expr if g == storage_srid() else f"ST_Transform({expr}, {storage_srid()})"


def cell_code(ix, iy, resolution_m):
    """E<x>N<y>: lower-left corner in hm (100 m cells) or km (1 km cells), as the CBS square statistics."""
    unit = 100 if resolution_m < 1000 else 1000
    return f"E{ix * resolution_m // unit}N{iy * resolution_m // unit}"


def _tables():
    from administrative.models import District, Neighborhood

    from .models import Building, PopulationAllocation, Property, UrbanisationCell

    return {
        "hood": Neighborhood._meta.db_table, "district": District._meta.db_table,
        "prop": Property._meta.db_table, "bld": Building._meta.db_table,
        "alloc": PopulationAllocation._meta.db_table, "cell": UrbanisationCell._meta.db_table,
    }


def current_year():
    """The population year: latest Neighborhood.populationDate, else the latest classified year, else today."""
    from django.db.models import Max
    from django.utils import timezone

    from administrative.models import Neighborhood

    from .models import UrbanisationCell

    latest = Neighborhood.objects.aggregate(d=Max("populationDate"))["d"]
    if latest:
        return latest.year
    stored = UrbanisationCell.objects.aggregate(y=Max("year"))["y"]
    return stored or timezone.now().year


def is_built():
    """True once the grid was built from the UI; until then signals do nothing."""
    from .models import PopulationAllocation

    return PopulationAllocation.objects.exists()


# ── 1. Allocation ──────────────────────────────────────────────────

def allocate(neighborhood_ids, year):
    """
    Replace the PopulationAllocation rows of these neighborhoods for `year`,
    at every resolution. Each neighborhood's population is split equally over
    its residential properties (one share per dwelling, never per building);
    a neighborhood without dwellings is spread by area (by_area). Buildings
    count by their point on surface; their footprint is cut by the cells.
    """
    from .models import PopulationAllocation

    ids = sorted({str(i) for i in neighborhood_ids})
    if not ids:
        return
    PopulationAllocation.objects.filter(neighborhood_id__in=ids, year=year).delete()
    t = _tables()
    for r in RESOLUTIONS:
        sql = f"""
            WITH hood AS (
                SELECT n.id, n.geom, {_tx('n.geom')} AS tg,
                       COALESCE(n."currentPopulation", 0)::float AS pop
                FROM "{t['hood']}" n WHERE n.id = ANY(%(ids)s)
            ), dwelling AS (
                SELECT DISTINCT ON (p.id) h.id AS nid, {_tx('p.geom')} AS g
                FROM hood h
                JOIN "{t['prop']}" p ON p.geom && h.geom AND ST_Intersects(h.geom, p.geom)
                WHERE p."usageFunction" @> ARRAY['Residential function']::varchar[]
                ORDER BY p.id, h.id
            ), dw AS (
                SELECT nid, floor(ST_X(g) / %(r)s)::int AS ix, floor(ST_Y(g) / %(r)s)::int AS iy,
                       count(*)::int AS n
                FROM dwelling GROUP BY 1, 2, 3
            ), ntot AS (
                SELECT nid, sum(n)::int AS total FROM dw GROUP BY nid
            ), cells AS (
                SELECT * FROM (
                    SELECT h.id AS nid, c.i AS ix, c.j AS iy, ST_Area(ST_Intersection(h.tg, c.geom)) AS area
                    FROM hood h, ST_SquareGrid(%(r)s, h.tg) c
                    WHERE ST_Intersects(h.tg, c.geom)
                ) touched WHERE area > 0
            ), harea AS (
                SELECT nid, sum(area) AS a FROM cells GROUP BY nid
            ), building AS (
                SELECT DISTINCT ON (b.id) h.id AS nid, {_tx('b.geom')} AS g
                FROM hood h
                JOIN "{t['bld']}" b ON b.geom && h.geom AND ST_Intersects(h.geom, ST_PointOnSurface(b.geom))
                ORDER BY b.id, h.id
            ), bc AS (
                SELECT b.nid, c.i AS ix, c.j AS iy, sum(ST_Area(ST_Intersection(b.g, c.geom))) AS m2
                FROM building b, ST_SquareGrid(%(r)s, b.g) c
                WHERE ST_Intersects(b.g, c.geom) AND NOT ST_Touches(b.g, c.geom)
                GROUP BY 1, 2, 3
            ), keys AS (
                SELECT nid, ix, iy FROM cells
                UNION SELECT nid, ix, iy FROM dw
                UNION SELECT nid, ix, iy FROM bc
            )
            INSERT INTO "{t['alloc']}"
                (neighborhood_id, resolution_m, year, ix, iy, population, dwellings, built_up_m2, area_m2, by_area)
            SELECT k.nid, %(r)s, %(year)s, k.ix, k.iy,
                   CASE WHEN COALESCE(t.total, 0) > 0 THEN h.pop * COALESCE(dw.n, 0) / t.total
                        WHEN COALESCE(ha.a, 0) > 0 THEN h.pop * COALESCE(c.area, 0) / ha.a
                        ELSE 0 END,
                   COALESCE(dw.n, 0), COALESCE(bc.m2, 0), COALESCE(c.area, 0),
                   COALESCE(t.total, 0) = 0 AND h.pop > 0
            FROM keys k
            JOIN hood h ON h.id = k.nid
            LEFT JOIN cells c ON c.nid = k.nid AND c.ix = k.ix AND c.iy = k.iy
            LEFT JOIN dw ON dw.nid = k.nid AND dw.ix = k.ix AND dw.iy = k.iy
            LEFT JOIN bc ON bc.nid = k.nid AND bc.ix = k.ix AND bc.iy = k.iy
            LEFT JOIN ntot t ON t.nid = k.nid
            LEFT JOIN harea ha ON ha.nid = k.nid
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, {"ids": ids, "r": r, "year": year})
            rows = cursor.rowcount
            if rows > 500:
                cursor.execute(f'ANALYZE "{t["alloc"]}"')
        totals = PopulationAllocation.objects.filter(neighborhood_id__in=ids, year=year, resolution_m=r)
        by_area = totals.filter(by_area=True).values("neighborhood").distinct().count()
        from django.db.models import Sum
        agg = totals.aggregate(p=Sum("population"), d=Sum("dwellings"))
        _log(f"  {r} m: {rows} allocation row(s), {agg['p'] or 0:,.0f} people over {agg['d'] or 0:,} dwellings"
             + (f", {by_area} neighborhood(s) without dwellings spread by area" if by_area else ""))


# ── 2. Cells ───────────────────────────────────────────────────────

def sync_cells(year, resolution_m):
    """
    Upsert one UrbanisationCell per cell holding allocation rows (sums of
    population, dwellings, built-up m², coverage) and delete cells left
    without any. Returns the ids of the cells created, which still need
    their land-cover shares.
    """
    t = _tables()
    r = int(resolution_m)
    envelope = _from_grid(f"ST_MakeEnvelope(a.ix * {r}, a.iy * {r}, (a.ix + 1) * {r}, (a.iy + 1) * {r}, {grid_srid()})")
    code_unit = 100 if r < 1000 else 1000
    with connection.cursor() as cursor:
        cursor.execute(f"""
            DELETE FROM "{t['cell']}" c
            WHERE c.resolution_m = %(r)s AND c.year = %(year)s
              AND NOT EXISTS (SELECT 1 FROM "{t['alloc']}" a
                              WHERE a.resolution_m = c.resolution_m AND a.year = c.year
                                AND a.ix = c.ix AND a.iy = c.iy)
        """, {"r": r, "year": year})
        if cursor.rowcount:
            _log(f"  {cursor.rowcount} cell(s) without people or buildings removed")
        cursor.execute(f"""
            WITH a AS (
                SELECT ix, iy, sum(population) AS pop, sum(dwellings)::int AS dw,
                       sum(built_up_m2) AS built, sum(area_m2) AS area, bool_or(by_area) AS by_area
                FROM "{t['alloc']}" WHERE resolution_m = %(r)s AND year = %(year)s
                GROUP BY ix, iy
            )
            INSERT INTO "{t['cell']}"
                (resolution_m, year, current, ix, iy, cell_code, population, dwellings, density,
                 built_up_m2, built_up_share, water_share, settlement_share, coverage, by_area,
                 l2, l1, cluster_id, cluster_population, edge_effect, updated, geom)
            SELECT %(r)s, %(year)s, FALSE, a.ix, a.iy,
                   'E' || (a.ix * %(r)s / {code_unit}) || 'N' || (a.iy * %(r)s / {code_unit}),
                   a.pop, a.dw, 0, a.built, 0, 0, 0, LEAST(a.area / (%(r)s::float * %(r)s), 1), a.by_area,
                   0, 0, 0, 0, FALSE, now(), {envelope}
            FROM a
            ON CONFLICT (resolution_m, year, ix, iy) DO UPDATE SET
                population = EXCLUDED.population, dwellings = EXCLUDED.dwellings,
                built_up_m2 = EXCLUDED.built_up_m2, coverage = EXCLUDED.coverage,
                by_area = EXCLUDED.by_area, updated = now()
            RETURNING id, (xmax = 0) AS inserted
        """, {"r": r, "year": year})
        created = [row[0] for row in cursor.fetchall() if row[1]]
        if len(created) > 500:
            # Fresh rows have no planner statistics: without them the next
            # queries (land cover, units) are planned for one row.
            cursor.execute(f'ANALYZE "{t["cell"]}"')
        return created


# ── 3. Land cover ──────────────────────────────────────────────────

def landcover_shares(year, resolution_m, cell_ids=None):
    """
    Water and settlement shares of the cells (all of the year's grid, or
    `cell_ids`) from each city's latest land-cover year:

        share_k = area(cell ∩ polygons of class group k) / area(cell)
    """
    from physicalEnv.models import LandCoverClasses, LandCoverVector

    t = _tables()
    lc, classes = LandCoverVector._meta.db_table, LandCoverClasses._meta.db_table
    params = {"r": int(resolution_m), "year": year,
              "water": [f"%{k}%" for k in WATER_KEYWORDS],
              "settle": [f"%{k}%" for k in SETTLEMENT_KEYWORDS]}
    only = ""
    if cell_ids is not None:
        if not cell_ids:
            return
        only = "AND c.id = ANY(%(ids)s)"
        params["ids"] = list(cell_ids)
    # Driven from the (few) relevant land-cover polygons of each city's latest
    # year, materialized once; each one finds its cells through the cell GiST
    # index. The earlier form, driven from the cells with a LEFT JOIN on the
    # aggregate, was planned as nested loops that re-ran the aggregate per cell
    # whenever the freshly inserted cells had no statistics yet (minutes for
    # 6 000 cells).
    with connection.cursor() as cursor:
        cursor.execute(f"""
            UPDATE "{t['cell']}" c SET water_share = 0, settlement_share = 0
            WHERE c.resolution_m = %(r)s AND c.year = %(year)s {only}
        """, params)
        # Land-cover years can be partial updates (each survey year covering
        # only the areas that changed), so each cell reads the most recent
        # survey year that touches it, not the city's latest year overall.
        cursor.execute(f"""
            WITH poly AS MATERIALIZED (
                SELECT l.geom, l.year,
                       k.class_name ILIKE ANY(%(water)s) AS is_water,
                       k.class_name ILIKE ANY(%(settle)s) AND NOT k.class_name ILIKE ANY(%(water)s) AS is_settle
                FROM "{lc}" l
                JOIN "{classes}" k ON k.id = l.land_cover_type_id
            ), piece AS MATERIALIZED (
                SELECT c.id, p.year, p.is_water, p.is_settle, a.m2
                FROM poly p
                JOIN "{t['cell']}" c ON c.geom && p.geom AND ST_Intersects(c.geom, p.geom)
                CROSS JOIN LATERAL (
                    SELECT CASE WHEN ST_CoveredBy(c.geom, p.geom) THEN ST_Area(c.geom)
                                ELSE ST_Area(ST_Intersection(c.geom, p.geom)) END AS m2
                ) a
                WHERE c.resolution_m = %(r)s AND c.year = %(year)s {only}
            ), newest AS (
                SELECT id, max(year) AS y FROM piece GROUP BY id
            ), shares AS MATERIALIZED (
                SELECT pc.id,
                       sum(CASE WHEN pc.is_water THEN pc.m2 ELSE 0 END) AS water,
                       sum(CASE WHEN pc.is_settle THEN pc.m2 ELSE 0 END) AS settle
                FROM piece pc JOIN newest n ON n.id = pc.id AND n.y = pc.year
                GROUP BY pc.id
            )
            UPDATE "{t['cell']}" c
            SET water_share = LEAST(s.water / NULLIF(ST_Area(c.geom), 0), 1),
                settlement_share = LEAST(s.settle / NULLIF(ST_Area(c.geom), 0), 1)
            FROM shares s
            WHERE c.id = s.id
        """, params)
        _log(f"  {cursor.rowcount} cell(s) covered by land cover (newest survey year per cell)")


# ── 4. Classification ──────────────────────────────────────────────

def load_grid(year, resolution_m):
    """(ids, ix0, iy0, arrays) of the year's cells as dense 2-D numpy arrays (row = iy - iy0)."""
    import numpy as np

    from .models import UrbanisationCell

    rows = list(UrbanisationCell.objects.filter(year=year, resolution_m=resolution_m).values_list(
        "id", "ix", "iy", "population", "built_up_m2", "water_share", "settlement_share", "coverage", "dwellings"))
    if not rows:
        return None
    a = np.array([r[1:] for r in rows], dtype=float)
    ix0, iy0 = int(a[:, 0].min()), int(a[:, 1].min())
    shape = (int(a[:, 1].max()) - iy0 + 1, int(a[:, 0].max()) - ix0 + 1)
    cols = (a[:, 1].astype(int) - iy0, a[:, 0].astype(int) - ix0)
    grids = {}
    for k, name in enumerate(("pop", "built_m2", "water_share", "settlement_share", "coverage", "dwellings"), start=2):
        g = np.zeros(shape)
        g[cols] = a[:, k]
        grids[name] = g
    ids = np.zeros(shape, dtype=np.int64)
    ids[cols] = [r[0] for r in rows]
    return ids, cols, grids


def classify_grid(year, resolution_m, window_cells=None, masked=None, write=True):
    """Run builtup/degurba.py over the year's whole grid and store each cell's class. Returns the result dict."""
    from . import degurba

    loaded = load_grid(year, resolution_m)
    if loaded is None:
        return None
    ids, cols, g = loaded
    window, mask = degurba.variant(resolution_m)
    window = window if window_cells is None else window_cells
    mask = mask if masked is None else masked
    settlement = g["settlement_share"] >= SETTLEMENT_SHARE
    occupied = g["dwellings"] > 0
    _log(f"  grid {g['pop'].shape[1]} x {g['pop'].shape[0]} ({len(cols[0])} stored cells), "
         f"window {window} x {window}, {'settlement-masked' if mask else 'gross'} density, "
         f"{int(settlement.sum())} settlement cell(s) from land cover, {int(occupied.sum())} with dwellings, "
         f"{int((settlement | occupied).sum())} in the settlement mask")
    result = degurba.classify(g["pop"], g["built_m2"], g["water_share"], settlement, coverage=g["coverage"],
                              resolution_m=resolution_m, window_cells=window_cells, masked=masked,
                              occupied=occupied)
    l2 = result["l2"][cols]
    counts = ", ".join(f"{code} {degurba.L2_CLASSES[code]}: {int((l2 == code).sum())}"
                       for code in sorted(degurba.L2_CLASSES, reverse=True) if (l2 == code).any())
    _log(f"  classes: {counts or 'none'}")
    if result["edge_effect"][cols].any():
        _log(f"  {int(result['edge_effect'][cols].sum())} cell(s) in clusters touching the edge of the imported area")
    if write:
        t = _tables()
        values = [ids[cols].tolist()] + [result[k][cols].tolist() for k in (
            "l2", "l1", "density", "built_up_share", "cluster_id", "cluster_population", "edge_effect")]
        with connection.cursor() as cursor:
            cursor.execute(f"""
                UPDATE "{t['cell']}" c
                SET l2 = v.l2, l1 = v.l1, density = v.density, built_up_share = v.bshare,
                    cluster_id = v.cid, cluster_population = v.cpop, edge_effect = v.edge, updated = now()
                FROM unnest(%s::bigint[], %s::int[], %s::int[], %s::float[], %s::float[], %s::int[],
                            %s::float[], %s::bool[]) AS v(id, l2, l1, density, bshare, cid, cpop, edge)
                WHERE c.id = v.id
            """, values)
    return result


def mark_current(resolution_m):
    """current = the cell belongs to the latest classified year (the map layers show only those)."""
    t = _tables()
    with connection.cursor() as cursor:
        cursor.execute(f"""
            UPDATE "{t['cell']}" SET current = (year = (SELECT max(year) FROM "{t['cell']}" WHERE resolution_m = %(r)s))
            WHERE resolution_m = %(r)s
        """, {"r": int(resolution_m)})


# ── 5. Units ───────────────────────────────────────────────────────

_UNIT_COLUMN = {"neighborhood": "n.id", "district": "n.district_id", "city": "d.city_id"}


def _class_population_sql(level, only_unit=False):
    t = _tables()
    col = _UNIT_COLUMN[level]
    where = f"AND {col}::text = %(unit)s" if only_unit else f"AND {col} IS NOT NULL"
    return f"""
        SELECT {col}::text AS unit, c.l2, sum(a.population),
               sum(CASE WHEN c.l2 IN (21, 22, 23, 30) THEN a.area_m2 ELSE 0 END)
        FROM "{t['alloc']}" a
        JOIN "{t['cell']}" c ON c.resolution_m = a.resolution_m AND c.year = a.year
                             AND c.ix = a.ix AND c.iy = a.iy
        JOIN "{t['hood']}" n ON n.id = a.neighborhood_id
        LEFT JOIN "{t['district']}" d ON d.id = n.district_id
        WHERE a.resolution_m = %(r)s AND a.year = %(year)s {where}
        GROUP BY 1, 2
    """


def _collect(rows):
    out = {}
    for unit, l2, pop, urban in rows:
        by_class, area = out.setdefault(unit, ({}, [0.0]))
        if pop:
            by_class[int(l2)] = by_class.get(int(l2), 0.0) + float(pop)
        area[0] += float(urban or 0)
    return {u: (b, a[0]) for u, (b, a) in out.items()}


def unit_class_population(level, unit_id, resolution_m, year):
    """({l2: people}, urban area m²) of one unit: used by Urbanisation.save()."""
    with connection.cursor() as cursor:
        cursor.execute(_class_population_sql(level, only_unit=True),
                       {"r": int(resolution_m), "year": year, "unit": str(unit_id)})
        data = _collect(cursor.fetchall())
    return data.get(str(unit_id), ({}, 0.0))


def _unit_names(level, ids):
    from administrative.models import City, District, Neighborhood

    model, field = {"neighborhood": (Neighborhood, "neighborhoodName"), "district": (District, "districtName"),
                    "city": (City, "cityName")}[level]
    return {str(pk): name for pk, name in model.objects.filter(pk__in=ids).values_list("pk", field)}


def refresh_units(year):
    """
    Re-save one Urbanisation row per neighborhood, district and city that
    holds allocation rows, at both resolutions (rows of units without any
    are deleted), then mirror the cities' 100 m rate onto City.urbanizationRate.
    """
    from .models import Urbanisation

    for r in RESOLUTIONS:
        for level in ("neighborhood", "district", "city"):
            with connection.cursor() as cursor:
                cursor.execute(_class_population_sql(level), {"r": r, "year": year})
                data = _collect(cursor.fetchall())
            Urbanisation.objects.filter(level=level, resolution_m=r, year=year).exclude(unit_id__in=list(data)).delete()
            existing = {u.unit_id: u for u in Urbanisation.objects.filter(level=level, resolution_m=r, year=year)}
            names = _unit_names(level, list(data))
            for unit, (by_class, urban_m2) in data.items():
                row = existing.get(unit) or Urbanisation(level=level, unit_id=unit, resolution_m=r, year=year)
                row.unit_name = names.get(unit, row.unit_name)
                try:
                    row.save(by_class=by_class, urban_area_m2=urban_m2)
                except Exception:
                    logger.exception("Urbanisation of %s %s could not be saved", level, unit)
                    continue
                if level == "city":
                    rate = (f"{row.urbanization_rate_pct_yr:+.2f} %/yr since {row.rate_base_year}"
                            if row.urbanization_rate_pct_yr is not None else "no rate (one year stored)")
                    _log(f"  {r} m city {row.unit_name or unit}: {row.get_degurba_l2_display() or '-'}, "
                         f"{row.population:,.0f} people, {row.urban_area_km2:.2f} km2 urban, {rate}")
            _log(f"  {r} m: {len(data)} {level} row(s) saved")
    mirror_city_rates()


def mirror_city_rates():
    """City.urbanizationRate = the latest 100 m city rate (update(): administrative must not import builtup)."""
    from administrative.models import City

    from .models import Urbanisation

    latest = {}
    for unit, year, rate in (Urbanisation.objects.filter(level="city", resolution_m=LOCAL_RESOLUTION)
                             .order_by("year").values_list("unit_id", "year", "urbanization_rate_pct_yr")):
        latest[unit] = rate
    for unit, rate in latest.items():
        City.objects.filter(pk=unit).update(urbanizationRate=rate)


# ── Orchestration ──────────────────────────────────────────────────

def _cells_over(year, resolution_m, geoms):
    """Ids of the year's cells overlapping any of `geoms` (storage CRS)."""
    from django.contrib.gis.geos import GeometryCollection

    from .models import UrbanisationCell

    geoms = [g for g in geoms if g is not None and not g.empty]
    if not geoms:
        return []
    area = GeometryCollection(*geoms, srid=geoms[0].srid).envelope if len(geoms) > 1 else geoms[0]
    return list(UrbanisationCell.objects.filter(year=year, resolution_m=resolution_m, geom__intersects=area)
                .values_list("pk", flat=True))


def refresh(neighborhood_ids=(), landcover=False, year=None, full=False):
    """
    Bring the grid of `year` (default current_year()) up to date: re-allocate
    `neighborhood_ids` (all neighborhoods with full=True or when the year has
    no allocation yet), sync and classify both grids, refresh the units.
    `landcover=True` re-reads the land-cover shares of every cell, a list of
    geometries those of the cells under them. Runs in a
    savepoint; errors are logged, never raised (a save must not fail because
    of a derived layer). Returns a summary dict or None on failure.
    """
    from administrative.models import Neighborhood

    from .models import PopulationAllocation

    year = year or current_year()
    started = time.perf_counter()
    try:
        with transaction.atomic():
            ids = set(neighborhood_ids)
            if full or not PopulationAllocation.objects.filter(year=year).exists():
                ids = set(Neighborhood.objects.values_list("pk", flat=True))
                landcover = True
            scope = "full rebuild" if full else ("all neighborhoods (new year)" if landcover is True and not neighborhood_ids else "incremental")
            _log(f"refresh {year}: {scope}, {len(ids)} neighborhood(s) to allocate, "
                 f"land cover: {'all cells' if landcover is True else (f'{len(landcover)} changed area(s)' if landcover else 'new cells only')}")
            with _step("allocate people -> residential properties -> cells"):
                allocate(ids, year)
            summary = {"year": year, "neighborhoods": len(ids)}
            for r in RESOLUTIONS:
                with _step(f"{r} m: upsert cells"):
                    created = sync_cells(year, r)
                    _log(f"  {len(created)} new cell(s)")
                with _step(f"{r} m: land-cover shares"):
                    if landcover is True:
                        landcover_shares(year, r)
                    else:
                        landcover_shares(year, r, sorted(set(created) | set(_cells_over(year, r, landcover or []))))
                with _step(f"{r} m: classify the whole grid (numpy/scipy, CPU)"):
                    result = classify_grid(year, r)
                mark_current(r)
                summary[r] = None if result is None else int((result["l2"] > 0).sum())
            with _step("units: neighborhoods, districts, cities (Urbanisation.save)"):
                refresh_units(year)
        _bump()
        urbanisation_grid_changed.send(sender=None, year=year)
        _log(f"refresh {year} done in {time.perf_counter() - started:.1f} s: "
             f"{summary.get(100)} cells at 100 m, {summary.get(1000)} at 1 km")
        return summary
    except Exception:
        _log(f"refresh {year} FAILED after {time.perf_counter() - started:.1f} s (see the traceback below)")
        logger.exception("Degree of Urbanisation refresh failed")
        return None


def rebuild(year=None):
    """Full build from the UI: every neighborhood, every land-cover share."""
    return refresh(year=year, full=True)


def _bump():
    from core.cache import bump_layer_version

    from .models import UrbanisationCell, UrbanisationCellLocal, UrbanisationCellOriginal

    bump_layer_version(UrbanisationCell, UrbanisationCellLocal, UrbanisationCellOriginal)


# ── Deferral (bulk imports) ────────────────────────────────────────

_deferred = threading.local()


@contextmanager
def deferred_urbanisation_refresh():
    """
    Collect scheduled neighborhoods and land-cover changes and refresh once
    when the block ends (registered in importer/batching.py::deferred_cascades).
    Nested uses defer to the outermost one; the flush also runs if the block raises.
    """
    if getattr(_deferred, "ids", None) is not None:
        yield
        return
    _deferred.ids, _deferred.landcover = set(), []
    try:
        yield
    finally:
        ids, landcover = _deferred.ids, _deferred.landcover
        _deferred.ids = _deferred.landcover = None
        if (ids or landcover) and is_built():
            # Many land-cover changes (an import): re-read every cell once.
            _log(f"import finished: {len(ids)} neighborhood(s) and {len(landcover)} land-cover change(s) collected")
            refresh(ids, landcover=True if len(landcover) > 50 else landcover)


def schedule(neighborhood_ids=(), landcover=()):
    """
    Refresh now, or when the enclosing deferral ends. `landcover` = changed
    land-cover geometries. A no-op until the grid was built once.
    """
    ids = {i for i in neighborhood_ids if i is not None}
    landcover = list(landcover or [])
    if not ids and not landcover:
        return
    if getattr(_deferred, "ids", None) is not None:
        _deferred.ids |= ids
        _deferred.landcover.extend(landcover)
        return
    if not is_built():
        return
    _log(f"change detected: neighborhood(s) {sorted(ids) or '-'}"
         + (f", {len(landcover)} land-cover area(s)" if landcover else ""))
    refresh(ids, landcover=landcover)


def neighborhoods_at(geoms):
    """Neighborhood ids containing these points / footprints (point on surface)."""
    from administrative.models import Neighborhood

    ids = set()
    for g in geoms:
        if g is None or g.empty:
            continue
        point = g if g.geom_type == "Point" else g.point_on_surface
        ids |= set(Neighborhood.objects.filter(geom__intersects=point).values_list("pk", flat=True))
    return ids


# ── Status (map card) ──────────────────────────────────────────────

def status():
    """What the map's Degree of Urbanisation card shows: year, grid sizes, class counts, cities."""
    from django.db.models import Count, Max, Sum

    from .models import L2_CHOICES, PopulationAllocation, Urbanisation, UrbanisationCell

    labels = dict(L2_CHOICES)
    built = is_built()
    year = current_year()
    stored = UrbanisationCell.objects.filter(current=True).aggregate(y=Max("year"), t=Max("updated"))
    out = {"built": built, "population_year": year, "year": stored["y"], "updated": stored["t"],
           "stale_year": bool(built and stored["y"] and stored["y"] != year), "resolutions": {}}
    if not built:
        return out
    for r in RESOLUTIONS:
        cells = UrbanisationCell.objects.filter(current=True, resolution_m=r)
        totals = cells.aggregate(n=Count("id"), pop=Sum("population"), dw=Sum("dwellings"))
        classes = {row["l2"]: row["n"] for row in cells.values("l2").annotate(n=Count("id"))}
        out["resolutions"][r] = {
            "cells": totals["n"], "population": round(totals["pop"] or 0),
            "dwellings": totals["dw"] or 0,
            "classes": [{"l2": k, "label": labels.get(k, str(k)), "cells": classes[k]}
                        for k in sorted(classes, reverse=True) if k],
            "edge_clusters": cells.filter(edge_effect=True).values("cluster_id").distinct().count(),
            "layer": f"builtup.{'UrbanisationCellLocal' if r == LOCAL_RESOLUTION else 'UrbanisationCellOriginal'}",
        }
    out["area_allocated"] = (PopulationAllocation.objects.filter(year=stored["y"], by_area=True)
                             .values("neighborhood").distinct().count())
    cities = {}
    for row in Urbanisation.objects.filter(level="city", year=stored["y"]).order_by("unit_name"):
        c = cities.setdefault(row.unit_id, {"name": row.unit_name, "population": round(row.population)})
        c[str(row.resolution_m)] = {"class": row.get_degurba_l2_display(), "l2": row.degurba_l2,
                                    "urban_area_km2": round(row.urban_area_km2, 2),
                                    "rate": row.urbanization_rate_pct_yr, "base_year": row.rate_base_year}
    out["cities"] = list(cities.values())
    return out


# ── Dashboard (stored baseline + population what-if) ─────────────────

def _unit_filter(unit):
    """(level key for Urbanisation rows or None, Q on PopulationAllocation for the unit's neighborhoods)."""
    from django.db.models import Q

    from administrative.models import City, District, Neighborhood, Province

    if isinstance(unit, Neighborhood):
        return "neighborhood", Q(neighborhood_id=unit.pk)
    if isinstance(unit, District):
        return "district", Q(neighborhood__district_id=unit.pk)
    if isinstance(unit, City):
        return "city", Q(neighborhood__district__city_id=unit.pk)
    if isinstance(unit, Province):
        return None, Q(neighborhood__district__city__province_id=unit.pk)
    return None, Q(pk__in=[])


def city_factors(year, stored_year, scenario, growth_adjust_pct):
    """
    {city_id: f} with f = P(city, year, scenario, growth) / P(city, stored_year, median, 0):
    the what-if population as a deviation from the stored baseline year
    (f = 1 with the default controls in the stored year).
    """
    from administrative.models import City
    from administrative.population import DEFAULT_SCENARIO, get_population

    factors = {}
    for city in City.objects.all():
        base = get_population(city, stored_year, DEFAULT_SCENARIO, 0.0)
        target = get_population(city, year, scenario, growth_adjust_pct)
        factors[city.pk] = (target / base) if base else 1.0
    return factors


def whatif_unit(unit, factors, stored_year, resolution_m=LOCAL_RESOLUTION):
    """
    ({l2: people}, urban area m²) of `unit` with every neighborhood's allocation
    scaled by its city's factor, the whole grid reclassified in memory
    (builtup/degurba.py). Writes nothing (a what-if).
    """
    import numpy as np

    from . import degurba
    from .models import PopulationAllocation, UrbanisationCell

    _, unit_q = _unit_filter(unit)
    cells = list(UrbanisationCell.objects.filter(year=stored_year, resolution_m=resolution_m).values_list(
        "ix", "iy", "built_up_m2", "water_share", "settlement_share", "coverage", "dwellings"))
    if not cells:
        return {}, 0.0
    alloc = list(PopulationAllocation.objects.filter(year=stored_year, resolution_m=resolution_m).values_list(
        "ix", "iy", "population", "area_m2", "neighborhood__district__city_id", "neighborhood_id"))
    in_unit = set(PopulationAllocation.objects.filter(unit_q, year=stored_year, resolution_m=resolution_m)
                  .values_list("neighborhood_id", flat=True).distinct())
    c = np.array([row[:2] for row in cells], dtype=int)
    ix0, iy0 = c[:, 0].min(), c[:, 1].min()
    shape = (c[:, 1].max() - iy0 + 1, c[:, 0].max() - ix0 + 1)
    pos = (c[:, 1] - iy0, c[:, 0] - ix0)
    grids = {}
    for k, name in enumerate(("built", "water", "settle", "coverage", "dwellings"), start=2):
        g = np.zeros(shape)
        g[pos] = [row[k] for row in cells]
        grids[name] = g
    pop = np.zeros(shape)
    for ix, iy, p, _, city_id, _ in alloc:
        pop[iy - iy0, ix - ix0] += p * factors.get(city_id, 1.0)
    started = time.perf_counter()
    result = degurba.classify(pop, grids["built"], grids["water"], grids["settle"] >= SETTLEMENT_SHARE,
                              coverage=grids["coverage"], resolution_m=resolution_m,
                              occupied=grids["dwellings"] > 0)
    scaled = {k: round(v, 3) for k, v in factors.items() if abs(v - 1.0) > 1e-9}
    _log(f"what-if {unit}: population x {scaled or 1.0} (city factors), {shape[1]} x {shape[0]} grid "
         f"reclassified in memory in {time.perf_counter() - started:.2f} s, nothing written")
    by_class, urban_m2 = {}, 0.0
    for ix, iy, p, area, city_id, nid in alloc:
        if nid not in in_unit:
            continue
        l2 = int(result["l2"][iy - iy0, ix - ix0])
        by_class[l2] = by_class.get(l2, 0.0) + p * factors.get(city_id, 1.0)
        if l2 in (21, 22, 23, 30):
            urban_m2 += area
    return by_class, urban_m2


def dashboard(unit, year, scenario, growth_adjust_pct):
    """
    Degree of Urbanisation card of the built-up dashboard: the stored rows
    (default controls) or the in-memory what-if when the population dock moves
    the population away from the stored baseline. None before the grid exists.
    """
    from django.db.models import Max

    from . import chain
    from .models import Urbanisation, UrbanisationCell

    stored_year = (UrbanisationCell.objects.filter(resolution_m=LOCAL_RESOLUTION, current=True)
                   .aggregate(y=Max("year"))["y"])
    if stored_year is None:
        return None
    level, unit_q = _unit_filter(unit)
    rows = {}
    if level:
        rows = {r.resolution_m: r for r in Urbanisation.objects.filter(
            level=level, unit_id=str(unit.pk), year=stored_year)}
    series = []
    if level:
        series = list(Urbanisation.objects.filter(level=level, unit_id=str(unit.pk), resolution_m=LOCAL_RESOLUTION)
                      .order_by("year").values("year", "urban_area_km2", "urban_cluster_share"))

    factors = city_factors(year, stored_year, scenario, growth_adjust_pct)
    whatif = any(abs(f - 1.0) > 1e-9 for f in factors.values())
    stored = rows.get(LOCAL_RESOLUTION)
    if stored is not None and not whatif:
        by_class = {k: getattr(stored, f"pop_{k}") for k in (30, 23, 22, 21, 13, 12, 11)}
        urban_m2 = stored.urban_area_km2 * 1e6
    else:
        by_class, urban_m2 = whatif_unit(unit, factors, stored_year)
    l1, l2, shares = chain.classify_unit(by_class)
    original = rows.get(1000)
    labels = dict(Urbanisation.UNIT_L2)
    return {
        "stored_year": stored_year, "year": year, "whatif": whatif,
        "l1": l1, "l2": l2, "label": labels.get(l2, "–"),
        "population": sum(by_class.values()),
        "shares": [{"l2": k, "pct": round(shares.get(k, 0.0) * 100, 1)} for k in (30, 23, 22, 21, 13, 12, 11)],
        "urban_centre_pct": round(shares.get(30, 0.0) * 100, 1) if shares else None,
        "urban_cluster_pct": round(sum(shares.get(k, 0.0) for k in chain.URBAN_L2) * 100, 1) if shares else None,
        "urban_area_km2": round(urban_m2 / 1e6, 2),
        "rate": stored.urbanization_rate_pct_yr if stored else None,
        "rate_base_year": stored.rate_base_year if stored else None,
        "original_label": original.get_degurba_l2_display() if original and original.degurba_l2 else None,
        "series": series,
    }
