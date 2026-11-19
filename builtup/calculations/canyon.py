"""
Inputs of the street canyon, for many streets in one SQL statement.

Each street line is split into pieces of at most SEGMENT_M (after trimming
END_TRIM_M off both ends of every part, so the buildings of a crossing street
don't count), and each piece gets a single-sided buffer of SEARCH_M on its left
and its right (ST_Buffer 'side=left|right'). Per piece and side:

    h_side   = mean building height inside the buffer, weighted by the
               footprint area inside it; height = height_m, else
               numberFloors x STOREY_HEIGHT_M (dsm_patches.building_height),
               buildings with neither are skipped; no building: 0
    d_side   = distance from the piece to the nearest footprint on that side

and per street (pieces weighted by their length):

    h_left_m, h_right_m  = length-weighted mean of h_side
    w_facade_m           = length-weighted mean of d_left + d_right over the
                           pieces with buildings on both sides, else None
    n_left, n_right      = distinct buildings found on each side

The equations that turn these into H, W and H/W live in builtup/calculations/chain.py.

DAG edges: Buildings -> Canyon_Aspect, Streets -> Canyon_Aspect.
"""
from django.db import connection

SEARCH_M = 30.0
SEGMENT_M = 100.0
END_TRIM_M = 10.0
STOREY_HEIGHT_M = 3.0  # = physicalEnv.calculations.dsm_patches.STOREY_HEIGHT_M


def _sql():
    from ..models import Building, Street

    streets = Street._meta.db_table
    buildings = Building._meta.db_table
    return f"""
        WITH parts AS (
            SELECT s.id, d.path[1] AS part, d.geom AS g, ST_Length(d.geom) AS len
            FROM "{streets}" s, LATERAL ST_Dump(s.geom) d
            WHERE s.id = ANY(%(ids)s) AND ST_Length(d.geom) > 0
        ),
        trimmed AS (
            -- trim the ends only where the part stays long enough to keep
            SELECT id, part,
                   CASE WHEN len > 3 * %(trim)s
                        THEN ST_LineSubstring(g, %(trim)s / len, 1 - %(trim)s / len) ELSE g END AS g
            FROM parts
        ),
        pieces AS (
            SELECT id, part, ST_Length(g) AS len, g,
                   GREATEST(CEIL(ST_Length(g) / %(seg)s), 1)::int AS n
            FROM trimmed
        ),
        seg AS (
            SELECT p.id, p.part, i AS piece, p.len / p.n AS len,
                   ST_LineSubstring(p.g, i::float8 / p.n, (i + 1)::float8 / p.n) AS g
            FROM pieces p, generate_series(0, p.n - 1) i
        ),
        sides AS (
            SELECT seg.id, seg.part, seg.piece, seg.len, seg.g, side.name AS side,
                   ST_Buffer(seg.g, %(search)s, 'side=' || side.name) AS buf
            FROM seg CROSS JOIN (VALUES ('left'), ('right')) AS side(name)
        ),
        hits AS (
            SELECT sd.id, sd.part, sd.piece, sd.side, b.id AS building_id,
                   ST_Area(ST_Intersection(b.geom, sd.buf)) AS a,
                   NULLIF(COALESCE(b.height_m, b."numberFloors" * %(storey)s), 0) AS h,
                   ST_Distance(b.geom, sd.g) AS dist
            FROM sides sd
            JOIN "{buildings}" b ON b.geom && sd.buf AND ST_Intersects(b.geom, sd.buf)
        ),
        per_side AS (
            SELECT sd.id, sd.part, sd.piece, sd.len, sd.side,
                   COALESCE(SUM(hh.a * hh.h) FILTER (WHERE hh.h IS NOT NULL)
                            / NULLIF(SUM(hh.a) FILTER (WHERE hh.h IS NOT NULL), 0), 0) AS h,
                   MIN(hh.dist) AS dist
            FROM sides sd
            LEFT JOIN hits hh ON hh.id = sd.id AND hh.part = sd.part
                             AND hh.piece = sd.piece AND hh.side = sd.side
            GROUP BY sd.id, sd.part, sd.piece, sd.len, sd.side
        ),
        per_piece AS (
            SELECT l.id, l.len, l.h AS h_left, r.h AS h_right,
                   CASE WHEN l.dist IS NOT NULL AND r.dist IS NOT NULL THEN l.dist + r.dist END AS gap
            FROM per_side l
            JOIN per_side r ON r.id = l.id AND r.part = l.part AND r.piece = l.piece AND r.side = 'right'
            WHERE l.side = 'left'
        ),
        counts AS (
            SELECT id,
                   COUNT(DISTINCT building_id) FILTER (WHERE side = 'left') AS n_left,
                   COUNT(DISTINCT building_id) FILTER (WHERE side = 'right') AS n_right
            FROM hits GROUP BY id
        )
        SELECT pp.id,
               SUM(pp.h_left * pp.len) / NULLIF(SUM(pp.len), 0),
               SUM(pp.h_right * pp.len) / NULLIF(SUM(pp.len), 0),
               SUM(pp.gap * pp.len) FILTER (WHERE pp.gap IS NOT NULL)
                   / NULLIF(SUM(pp.len) FILTER (WHERE pp.gap IS NOT NULL), 0),
               COALESCE(MAX(c.n_left), 0), COALESCE(MAX(c.n_right), 0)
        FROM per_piece pp LEFT JOIN counts c ON c.id = pp.id
        GROUP BY pp.id
    """


EMPTY = {"h_left_m": 0.0, "h_right_m": 0.0, "w_facade_m": None, "n_left": 0, "n_right": 0}


def street_inputs(street_ids):
    """{street id: {h_left_m, h_right_m, w_facade_m, n_left, n_right}}; streets without length get EMPTY."""
    ids = [int(i) for i in street_ids]
    if not ids:
        return {}
    with connection.cursor() as cursor:
        cursor.execute(_sql(), {"ids": ids, "trim": END_TRIM_M, "seg": SEGMENT_M,
                                "search": SEARCH_M, "storey": STOREY_HEIGHT_M})
        rows = cursor.fetchall()
    out = {i: dict(EMPTY) for i in ids}
    for sid, h_left, h_right, gap, n_left, n_right in rows:
        out[sid] = {"h_left_m": float(h_left or 0.0), "h_right_m": float(h_right or 0.0),
                    "w_facade_m": float(gap) if gap is not None else None,
                    "n_left": int(n_left), "n_right": int(n_right)}
    return out


def streets_near(geoms):
    """Ids of the streets whose side buffers can reach any of `geoms` (footprints, storage CRS)."""
    from django.contrib.gis.measure import D
    from django.db.models import Q

    from ..models import Street

    q = Q()
    for g in geoms:
        if g is not None and not g.empty:
            q |= Q(geom__dwithin=(g, D(m=SEARCH_M)))
    if not q:
        return []
    return list(Street.objects.filter(q).values_list("pk", flat=True))
