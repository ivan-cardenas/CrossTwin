"""
Neighbourhood generator: an outline (a housing project) -> streets, blocks,
plots and building footprints, in the style of procedural block subdivision
(Vanegas et al. 2012, "Procedural generation of parcels in urban modeling",
Computer Graphics Forum 31(2); Parish & Mueller 2001 for street patterns).

Pure geometry (shapely, no ORM). Variation comes from one random.Random(seed)
drawn in a fixed order, so the same outline and parameters (seed included)
give the same layout on any machine. The map's Neighbourhood generator
previews it as a what-if (builtup/views_generator.py::generator_preview, never
stored) and builtup/calculations/materialise.py stores it when the project
is completed.

Steps (`generate`), in a frame rotated so the outline's main axis is x:

    1. axis      angle of the longest edge of the outline's minimum rotated
                 rectangle (or params.angle_deg)
    2. streets   street_pattern: grid (ring street on the outline inset by
                 W/2 + evenly spaced lines every block length/depth), curved
                 (concentric rounded rings every block depth + W plus spokes
                 towards the centre) or radial (spokes from the centre at
                 equal angles plus mitred rings)
    3. blocks    outline minus the streets buffered by W/2
    4. plots and buildings per typology (TYPOLOGIES), styled by STYLES:
         row/semi/detached  plots along every block edge (edge-following:
                    plot_width wide, perpendicular inward, long edges first;
                    a plot overlapping earlier ones by > PLOT_OVERLAP is
                    dropped, which forms the block corners); row houses in
                    terraces of 4-8 with staggered fronts and rear
                    extensions, detached houses L-shaped and slightly turned
         perimeter  block ring of building_depth (corners chamfered by
                    chamfer_m), cut into segments of varied height, taller
                    corners (corner_accent_floors), a courtyard gate in some blocks
         slab       rows of slabs or point towers, spaced by the taller
                    neighbour's height x slab_spacing_ratio (45° daylight
                    rule), towers along a row by their height, an L wing on
                    some slabs of the last row, each block turned up to rotate_deg
    5. dwellings per building (dwelling_mode): one family home, or flats of
       unit_gfa_m2 gross floor area (chain.units_in); `auto` = one home for
       row/semi/detached of at most 2 floors, flats otherwise
    6. metrics   (chain.layout_metrics)

DAG edges (stored by materialise.py): New_Units -> Buildings (the
footprints), Streets -> Buildings (the footprints fill the blocks the street
layout leaves; the edge pointed from buildings to streets until 2026-11-12,
docs/DAG_REVISIONS.md).
"""
import math
import random
from dataclasses import dataclass, field

from shapely import affinity
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Point, Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import linemerge, unary_union

GENERATOR_VERSION = "2"

# Dutch storey height used across CrossTwin (physicalEnv/calculations/dsm_patches.py: 3 m per floor).
FLOOR_HEIGHT_M = 3.0
# Perimeter-block ring pieces of about this length become separate buildings (BAG panden).
SEGMENT_M = 30.0
# Longest slab before it is split with a SLAB_GAP_M passage.
SLAB_MAX_LENGTH_M = 60.0
SLAB_GAP_M = 10.0
# Smallest block kept (m²): smaller leftovers between streets stay open space.
MIN_BLOCK_M2 = 400.0
# A plot clipped by an irregular block edge is kept when it keeps this share of its full area.
MIN_PLOT_SHARE = 0.6
# A plot overlapping already placed plots by more than this share of its area is dropped (block corners).
PLOT_OVERLAP = 0.15
# Smallest building footprint kept (m²).
MIN_FOOTPRINT_M2 = 25.0
# Block edges are simplified by this tolerance (m) before plots are laid along them.
EDGE_SIMPLIFY_M = 1.0
# Rear extension (aanbouw) of a row house: depth and share of the house width.
EXTENSION_DEPTH_M = 3.0
EXTENSION_WIDTH_SHARE = 0.6
# A point tower is this many floors taller than the slabs of its style.
TOWER_EXTRA_FLOORS = 4
# Low-rise typologies stay low-rise when floors are fitted to a target.
LOW_RISE_MAX_FLOORS = 4
MAX_FLOORS = 20

# Defaults per typology. Dutch rules of thumb: terraced house 5.4 m wide and
# 10 m deep on a 25 m plot, 3 floors; detached/semi 2 floors; perimeter
# blocks 12 m deep, 4 floors; slabs 12 m deep, 6 floors, spaced by their
# height (45° daylight angle, slab_spacing_ratio = 1/tan 45° = 1).
# Apartments of 80 m² gross floor area (unit_gfa_m2).
COMMON = {
    "style": "plain",
    "angle_deg": None,
    "street_width": 8.0,
    "ring_street": True,
    "street_pattern": "grid",
    "block_length": 100.0,
    "front_setback": 3.0,
    "floor_height": FLOOR_HEIGHT_M,
    "unit_gfa_m2": 80.0,
    "dwelling_mode": "auto",
    "target_units": None,
    "variation": 0.5,
    "seed": 1,
}
TYPOLOGIES = {
    "row": {"plot_width": 5.4, "plot_depth": 25.0, "building_depth": 10.0, "floors": 3,
            "terrace_min": 4, "terrace_max": 8, "stagger_m": 1.5, "extension_share": 0.4},
    "semi": {"plot_width": 9.0, "plot_depth": 28.0, "building_depth": 10.0, "floors": 2, "side_setback": 3.0,
             "l_shape_share": 0.3, "turn_deg": 0.0},
    "detached": {"plot_width": 14.0, "plot_depth": 30.0, "building_depth": 10.0, "floors": 2,
                 "side_setback": 3.0, "front_setback": 5.0, "l_shape_share": 0.5, "turn_deg": 6.0},
    "perimeter": {"block_depth": 60.0, "building_depth": 12.0, "floors": 4, "front_setback": 0.0,
                  "chamfer_m": 0.0, "corner_accent_floors": 0, "gate_share": 0.3},
    "slab": {"block_length": 120.0, "block_depth": 90.0, "building_depth": 12.0, "floors": 6,
             "slab_spacing_ratio": 1.0, "front_setback": 5.0, "tower_share": 0.0, "tower_size": 18.0,
             "rotate_deg": 0.0, "l_wing_share": 0.3},
}
# Style presets: defaults on top of the typology's (a user value still wins). Every style
# starts at COMMON["variation"] (50 %); "plain" keeps the straight grid.
STYLES = {
    "plain": {},
    "vinex": {"typology": "row", "street_pattern": "curved"},
    "garden_city": {"typology": "detached", "street_pattern": "curved", "plot_width": 16.0, "plot_depth": 34.0,
                    "turn_deg": 10.0},
    "urban_block": {"typology": "perimeter", "street_pattern": "grid", "chamfer_m": 5.0,
                    "corner_accent_floors": 2},
    "modernist": {"typology": "slab", "street_pattern": "grid", "ring_street": False,
                  "tower_share": 0.4, "rotate_deg": 15.0},
}
STREET_PATTERNS = ("grid", "curved", "radial")
DWELLING_MODES = ("auto", "single", "stacked")
# Typologies laid out along the block edges, one plot per building.
LOW_RISE = {"row", "semi", "detached"}
CHOICES = {"style": STYLES, "street_pattern": STREET_PATTERNS, "dwelling_mode": DWELLING_MODES}


def resolve_params(params):
    """
    Typology defaults < style preset < the given values (None/'' ignored).
    Raises ValueError on bad input, citing the Bbl for too small dwellings.
    """
    from .regulations import min_unit_gfa_m2

    params = dict(params or {})
    style = params.get("style") or "plain"
    if style not in STYLES:
        raise ValueError(f"Unknown style {style!r}; choose one of {', '.join(STYLES)}")
    typology = params.get("typology") or STYLES[style].get("typology") or "row"
    if typology not in TYPOLOGIES:
        raise ValueError(f"Unknown typology {typology!r}; choose one of {', '.join(TYPOLOGIES)}")
    preset = {k: v for k, v in STYLES[style].items() if k != "typology"}
    resolved = {**COMMON, **TYPOLOGIES[typology], **preset, "typology": typology, "style": style}
    for key, value in params.items():
        if key not in resolved or key in ("typology", "style") or value is None or value == "":
            continue
        default = resolved[key]
        if key in CHOICES:
            if value not in CHOICES[key]:
                raise ValueError(f"Unknown {key} {value!r}; choose one of {', '.join(CHOICES[key])}")
            resolved[key] = value
        elif isinstance(default, bool):
            resolved[key] = value if isinstance(value, bool) else str(value).lower() in ("1", "true", "on", "yes")
        elif isinstance(default, int) and not isinstance(default, bool):
            resolved[key] = int(float(value))
        else:
            resolved[key] = float(value)
    if typology in LOW_RISE:
        resolved["block_depth"] = 2 * resolved["plot_depth"]
    for key in ("street_width", "block_length", "block_depth", "building_depth", "floor_height", "unit_gfa_m2"):
        if resolved[key] <= 0:
            raise ValueError(f"{key} must be positive")
    if resolved.get("plot_width") is not None and resolved["plot_width"] <= 0:
        raise ValueError("plot_width must be positive")
    smallest = min_unit_gfa_m2()
    if resolved["unit_gfa_m2"] < smallest:
        raise ValueError(f"A dwelling needs at least {smallest:.0f} m² gross floor area for the Bbl minimum of "
                         f"18 m² living space (Bbl art. 4.163); {resolved['unit_gfa_m2']:g} m² is too small.")
    resolved["variation"] = max(0.0, min(1.0, resolved["variation"]))
    resolved["floors"] = max(1, min(MAX_FLOORS, int(resolved["floors"])))
    resolved["generator_version"] = GENERATOR_VERSION
    return resolved


@dataclass
class Layout:
    """A generated layout in the outline's CRS (metres)."""
    params: dict
    streets: list = field(default_factory=list)     # LineString, one per street
    blocks: list = field(default_factory=list)      # Polygon
    plots: list = field(default_factory=list)       # Polygon
    buildings: list = field(default_factory=list)   # dict(geom, floors, height_m, units, typology)
    metrics: dict = field(default_factory=dict)


# ── geometry helpers ─────────────────────────────────────────────────

def main_angle(outline):
    """Angle (degrees) of the longest edge of the outline's minimum rotated rectangle."""
    rect = outline.minimum_rotated_rectangle
    coords = list(rect.exterior.coords) if rect.geom_type == "Polygon" else []
    if len(coords) < 3:
        return 0.0
    edges = [(coords[i], coords[i + 1]) for i in range(len(coords) - 1)]
    (x0, y0), (x1, y1) = max(edges, key=lambda e: math.dist(*e))
    angle = math.degrees(math.atan2(y1 - y0, x1 - x0))
    # Same axis either way; keep it in (-90, 90] so the layout does not flip.
    if angle <= -90:
        angle += 180
    elif angle > 90:
        angle -= 180
    return round(angle, 6)


def _polygons(geom):
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    if geom.geom_type in ("MultiPolygon", "GeometryCollection"):
        return [g for part in geom.geoms for g in _polygons(part)]
    return []


def _lines(geom):
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "LineString":
        return [geom]
    if geom.geom_type in ("MultiLineString", "GeometryCollection"):
        return [g for part in geom.geoms for g in _lines(part)]
    if geom.geom_type == "LinearRing":
        return [LineString(geom.coords)]
    return []


def _steps(start, end, first, step):
    """Positions first, first + step, ... strictly inside (start, end)."""
    out, x = [], first
    while x < end - 1e-9:
        if x > start + 1e-9:
            out.append(x)
        x += step
    return out


def _rings(poly):
    """Exterior and interior rings of a polygon as lines."""
    return [LineString(poly.exterior.coords)] + [LineString(r.coords) for r in poly.interiors]


# ── streets ──────────────────────────────────────────────────────────

def _grid_streets(local, p):
    sw = p["street_width"]
    inner = local.buffer(-sw / 2, join_style="mitre") if p["ring_street"] else local
    lines = []
    for poly in _polygons(inner):
        if p["ring_street"]:
            lines.extend(_rings(poly))
        minx, miny, maxx, maxy = poly.bounds
        # Space the grid evenly: as many blocks as fit at the requested size.
        for lo, hi, size, vertical in ((minx, maxx, p["block_length"], True), (miny, maxy, p["block_depth"], False)):
            span = hi - lo
            n = max(1, round((span + sw) / (size + sw))) if span > size else 1
            pitch = span / n
            for pos in _steps(lo, hi, lo + pitch, pitch):
                cut = LineString([(pos, miny - 1), (pos, maxy + 1)]) if vertical \
                    else LineString([(minx - 1, pos), (maxx + 1, pos)])
                lines.extend(_lines(cut.intersection(poly)))
    return lines


# Curved streets: ring corners are rounded with this share of the ring pitch as radius,
# and spokes bow sideways by this share of their length (alternating sides).
CURVE_RADIUS_SHARE = 0.6
SPOKE_BOW_SHARE = 0.12
SPOKE_SEGMENTS = 16


def _bowed(start, end, bow):
    """Quadratic Bézier from start to end whose middle is pushed sideways by `bow` metres."""
    (x0, y0), (x1, y1) = start, end
    length = math.hypot(x1 - x0, y1 - y0) or 1.0
    cx, cy = (x0 + x1) / 2 - (y1 - y0) / length * bow, (y0 + y1) / 2 + (x1 - x0) / length * bow
    pts = []
    for i in range(SPOKE_SEGMENTS + 1):
        t = i / SPOKE_SEGMENTS
        pts.append(((1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x1,
                    (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y1))
    return LineString(pts)


def _concentric_streets(local, p, rounded, spokes=True):
    """
    Rings every block depth + W inside the outline (rounded: corners with a
    radius of CURVE_RADIUS_SHARE x pitch) and, with `spokes`, streets from the
    ring street towards the centre every block length that stop at the
    innermost ring (its inside stays one central block; rounded: bowed).
    Rings thinner than half a block depth are dropped.
    """
    sw = p["street_width"]
    join = "round" if rounded else "mitre"
    pitch = p["block_depth"] + sw
    radius = pitch * CURVE_RADIUS_SHARE

    def smooth(geom):
        if not rounded or geom.is_empty:
            return geom
        rounded_geom = geom.buffer(-radius, join_style="round").buffer(radius, join_style="round")
        return rounded_geom if not rounded_geom.is_empty else geom

    first = smooth(local.buffer(-sw / 2, join_style=join))
    lines, rings, k = [], [], 0
    while True:
        ring_poly = smooth(first.buffer(-k * pitch, join_style=join)) if k else first
        polys = [g for g in _polygons(ring_poly)
                 if g.area >= MIN_BLOCK_M2 and _block_depth(g) >= p["block_depth"] / 2]
        if not polys:
            break
        if k or p["ring_street"]:
            for g in polys:
                lines.extend(_rings(g))
        rings.append(unary_union(polys))
        k += 1
    if not rings or not spokes:
        return lines
    outer, core = rings[0], rings[-1]
    centre = core.representative_point()
    perimeter = sum(g.exterior.length for g in _polygons(outer))
    n = max(3, round(perimeter / (p["block_length"] + sw)))
    longest = max((g.exterior for g in _polygons(outer)), key=lambda r: r.length)
    for i in range(n):
        start = longest.interpolate(i / n, normalized=True)
        spoke = _bowed((start.x, start.y), (centre.x, centre.y),
                       (1 if i % 2 else -1) * SPOKE_BOW_SHARE * start.distance(centre)) if rounded \
            else LineString([start, centre])
        clipped = spoke.intersection(outer)
        if len(rings) > 1:
            clipped = clipped.difference(core)      # the innermost ring stays one central block
        lines.extend(l for l in _lines(clipped) if l.length > p["block_depth"] / 4)
    return lines


def _radial_streets(local, p):
    """
    Spokes from the centre at equal angles plus mitred rings. A spoke ends at
    a central square of one block depth across, so blocks do not narrow to
    slivers at the centre.
    """
    sw = p["street_width"]
    lines = _concentric_streets(local, p, rounded=False, spokes=False)
    centre = local.representative_point()
    square = centre.buffer(p["block_depth"] / 2, join_style="mitre")
    lines.extend(_rings(square) if square.within(local) else [])
    outer = local.buffer(-sw / 2, join_style="mitre") if p["ring_street"] else local
    minx, miny, maxx, maxy = local.bounds
    reach = math.hypot(maxx - minx, maxy - miny)       # longer than any distance inside the outline
    n = max(4, round(outer.length / (p["block_length"] + sw)))
    for i in range(n):
        a = 2 * math.pi * i / n
        spoke = LineString([centre, (centre.x + reach * math.cos(a), centre.y + reach * math.sin(a))])
        lines.extend(_lines(spoke.intersection(outer).difference(square)))
    return lines


def _streets(local, p):
    """Street centre lines (rotated frame) for the street pattern."""
    pattern = p["street_pattern"]
    if pattern == "curved":
        lines = _concentric_streets(local, p, rounded=True)
    elif pattern == "radial":
        lines = _radial_streets(local, p)
    else:
        lines = _grid_streets(local, p)
    merged = linemerge(MultiLineString(lines)) if lines else None
    return [l for l in _lines(merged) if l.length > 1.0]


# ── low-rise: plots along the block edges ────────────────────────────

def _edges(block):
    """(start, unit along, inward normal, length) of each edge of the block's simplified exterior, long first."""
    ring = orient(block.simplify(EDGE_SIMPLIFY_M, preserve_topology=True), 1.0).exterior   # CCW: inside on the left
    coords = list(ring.coords)
    edges = []
    for idx in range(len(coords) - 1):
        (x0, y0), (x1, y1) = coords[idx][:2], coords[idx + 1][:2]
        length = math.hypot(x1 - x0, y1 - y0)
        if length < 1e-6:
            continue
        ux, uy = (x1 - x0) / length, (y1 - y0) / length
        edges.append(((x0, y0), (ux, uy), (-uy, ux), length, idx))
    edges.sort(key=lambda e: (-round(e[3], 6), e[4]))
    return edges


def _quad(origin, u, n, s0, s1, d0, d1):
    """Rectangle from s0 to s1 along u and d0 to d1 along n, from origin."""
    ox, oy = origin
    pts = [(ox + s * u[0] + d * n[0], oy + s * u[1] + d * n[1]) for s, d in ((s0, d0), (s1, d0), (s1, d1), (s0, d1))]
    return Polygon(pts)


def _block_depth(block):
    """Short side of the block's minimum rotated rectangle."""
    rect = block.minimum_rotated_rectangle
    coords = list(rect.exterior.coords) if rect.geom_type == "Polygon" else []
    if len(coords) < 4:
        return 0.0
    return min(math.dist(coords[0], coords[1]), math.dist(coords[1], coords[2]))


def _low_rise(block, p, rng):
    """Plots along every block edge and the building on each (row, semi, detached). Returns (plots, buildings)."""
    typology, var = p["typology"], p["variation"]
    pw, bd = p["plot_width"], p["building_depth"]
    depth = min(p["plot_depth"], _block_depth(block) / 2) if _block_depth(block) >= 1.6 * p["plot_depth"] \
        else min(p["plot_depth"], _block_depth(block))
    if depth < p["front_setback"] + bd * 0.6:
        return [], []
    plots, buildings, taken = [], [], []
    group = 2 if typology == "semi" else 1
    for origin, u, n, length, _idx in _edges(block):
        width = pw * group
        count = int(length // width)
        if count < 1:
            continue
        start = (length - count * width) / 2
        terrace_left, terrace_len, terrace = 0, 0, None
        for i in range(count):
            s0 = start + i * width
            cell = _quad(origin, u, n, s0, s0 + width, 0, depth)
            piece = cell.intersection(block)
            if piece.area < MIN_PLOT_SHARE * cell.area:
                terrace_left = 0
                continue
            overlap = sum(piece.intersection(t).area for t in taken if t.intersects(piece))
            if overlap > PLOT_OVERLAP * piece.area:
                terrace_left = 0
                continue
            own = piece.difference(unary_union(taken)) if taken else piece
            taken.append(piece)
            plots.append(own)

            if typology == "row":
                if terrace_left == 0:
                    # New terrace: length, front stagger and floors drawn once for it.
                    terrace_len = p["terrace_min"] + (rng.randint(0, p["terrace_max"] - p["terrace_min"]) if var else 2)
                    terrace = {"front": p["front_setback"] + rng.uniform(-1, 1) * p["stagger_m"] * var,
                               "floors": p["floors"] + (1 if rng.random() < 0.3 * var else 0)}
                    terrace_left = terrace_len + 1          # + the path after the terrace
                terrace_left -= 1
                if terrace_left == 0:
                    continue                                # path between terraces
                front = max(0.5, terrace["front"])
                house = _quad(origin, u, n, s0, s0 + width, front, front + bd)
                if rng.random() < p["extension_share"] * var:
                    ext_w = width * EXTENSION_WIDTH_SHARE
                    house = house.union(_quad(origin, u, n, s0, s0 + ext_w, front + bd - 0.01, front + bd + EXTENSION_DEPTH_M))
                buildings.append((house.intersection(own), terrace["floors"]))
            else:
                ss = min(p["side_setback"], width / 4)
                front = p["front_setback"] + (rng.uniform(0, 1) * 2 * var if var else 0)
                main = _quad(origin, u, n, s0 + ss, s0 + width - ss, front, front + bd)
                if rng.random() < p["l_shape_share"] * (var if var else 0):
                    # L shape: a wing behind one side of the house
                    wing_w = (width - 2 * ss) * 0.45
                    left = rng.random() < 0.5
                    a = s0 + ss if left else s0 + width - ss - wing_w
                    main = main.union(_quad(origin, u, n, a, a + wing_w, front + bd - 0.01, front + bd * 1.5))
                if p["turn_deg"] and var:
                    main = affinity.rotate(main, rng.uniform(-1, 1) * p["turn_deg"] * var, origin="centroid")
                if typology == "semi":
                    # Split at the shared wall in the middle of the pair
                    mid = s0 + width / 2
                    halves = [_quad(origin, u, n, s0 - 1, mid, -1, depth + 1), _quad(origin, u, n, mid, s0 + width + 1, -1, depth + 1)]
                    for half in halves:
                        buildings.append((main.intersection(half).intersection(own), p["floors"]))
                else:
                    buildings.append((main.intersection(own), p["floors"]))
    return plots, [(g, f, typology) for g, f in buildings]


# ── perimeter blocks ─────────────────────────────────────────────────

def _perimeter(block, p, rng):
    """The block ring building_depth deep (chamfered corners), cut into segments of varied height."""
    var = p["variation"]
    outer = block.buffer(-p["front_setback"], join_style="mitre") if p["front_setback"] else block
    if p["chamfer_m"] and not outer.is_empty:
        c = p["chamfer_m"]
        chamfered = outer.buffer(-c, join_style="mitre").buffer(c, join_style="bevel")
        if not chamfered.is_empty:
            outer = chamfered
    if outer.is_empty:
        return [block], []
    inner = outer.buffer(-p["building_depth"], join_style="mitre")
    ring = outer.difference(inner)
    seg = SEGMENT_M * (1 + rng.uniform(-0.3, 0.3) * var)
    minx, miny, maxx, maxy = ring.bounds
    nx, ny = max(1, math.ceil((maxx - minx) / seg)), max(1, math.ceil((maxy - miny) / seg))
    dx, dy = (maxx - minx) / nx, (maxy - miny) / ny
    pieces = []
    for i in range(nx):
        for j in range(ny):
            cell = box(minx + i * dx, miny + j * dy, minx + (i + 1) * dx, miny + (j + 1) * dy)
            pieces.extend(g for g in _polygons(ring.intersection(cell)) if g.area >= MIN_FOOTPRINT_M2)
    corners = [Point(c).buffer(p["building_depth"]) for g in _polygons(outer) for c in list(g.exterior.coords)[:-1]]
    is_corner = [any(piece.intersects(c) for c in corners) for piece in pieces]
    gate = None
    plain = [k for k, corner in enumerate(is_corner) if not corner]
    if len(plain) > 4 and rng.random() < p["gate_share"] * (var if var else 0):
        gate = plain[rng.randrange(len(plain))]
    out = []
    for k, piece in enumerate(pieces):
        if k == gate:
            continue                                            # courtyard gate
        floors = p["floors"]
        if var and rng.random() < var:
            floors += rng.choice((-1, 0, 1))
        if is_corner[k]:
            floors += p["corner_accent_floors"]
        out.append((piece, max(1, floors), "perimeter"))
    return [block], out


# ── slabs and towers ─────────────────────────────────────────────────

def _slabs(block, p, rng):
    """
    Rows of slabs or point towers (one kind per row, drawn with the RNG),
    each block turned by up to rotate_deg. Rows are spaced by the taller of
    two neighbours x slab_spacing_ratio (45° daylight angle), towers along a
    row by their own height; the last row's slabs may get an L wing pointing
    away from the others.
    """
    var = p["variation"]
    outer = block.buffer(-p["front_setback"], join_style="mitre") if p["front_setback"] else block
    if outer.is_empty:
        return [block], []
    turn = rng.uniform(-1, 1) * p["rotate_deg"] * var if p["rotate_deg"] and var else 0.0
    centre = outer.centroid
    frame = affinity.rotate(outer, -turn, origin=centre) if turn else outer
    minx, miny, maxx, maxy = frame.bounds
    bd, ratio, fh = p["building_depth"], p["slab_spacing_ratio"], p["floor_height"]
    size = p["tower_size"]
    tower_floors = min(MAX_FLOORS, p["floors"] + TOWER_EXTRA_FLOORS)

    # Rows bottom-up: (kind, y offset from the first row, depth, height)
    rows, y = [], 0.0
    while True:
        kind = "tower" if rng.random() < p["tower_share"] else "slab"
        depth, floors = (size, tower_floors) if kind == "tower" else (bd, p["floors"])
        if rows:
            prev = rows[-1]
            y = prev[1] + prev[2] + max(max(prev[3], floors) * fh * ratio, SLAB_GAP_M)
        if y + depth > maxy - miny:
            break
        rows.append((kind, y, depth, floors))
    if not rows:
        return [block], []
    used = rows[-1][1] + rows[-1][2]
    y0 = miny + ((maxy - miny) - used) / 2
    length = maxx - minx
    n = max(1, math.ceil((length + SLAB_GAP_M) / (SLAB_MAX_LENGTH_M + SLAB_GAP_M)))
    piece_len = (length - (n - 1) * SLAB_GAP_M) / n
    out = []
    for r, (kind, dy, depth, floors) in enumerate(rows):
        y = y0 + dy
        if kind == "tower":
            gap = max(floors * fh * ratio, SLAB_GAP_M)
            count = max(1, int((length + gap) // (size + gap)))
            spare = length - count * size - (count - 1) * gap
            for t in range(count):
                tx = minx + spare / 2 + t * (size + gap)
                out.append((box(tx, y, tx + size, y + size), floors, "tower"))
            continue
        for k in range(n):
            x0 = minx + k * (piece_len + SLAB_GAP_M)
            slab = box(x0, y, x0 + piece_len, y + bd)
            if r == len(rows) - 1 and var and rng.random() < p["l_wing_share"] * var:
                end = x0 if rng.random() < 0.5 else x0 + piece_len - bd
                slab = slab.union(box(end, y + bd - 0.01, end + bd, y + bd + bd * 1.5))
            out.append((slab, floors, "slab"))
    if turn:
        out = [(affinity.rotate(g, turn, origin=centre), f, t) for g, f, t in out]
    return [block], [(g.intersection(outer), f, t) for g, f, t in out]


# ── dwellings ────────────────────────────────────────────────────────

def dwellings(footprint_m2, floors, typology, p):
    """Dwellings in one building for the dwelling mode (see module docstring)."""
    from . import chain

    mode = p["dwelling_mode"]
    single = mode == "single" or (mode == "auto" and typology in LOW_RISE and floors <= 2)
    return 1 if single else chain.units_in(footprint_m2 * floors, p["unit_gfa_m2"])


def _place(blocks, p):
    """(plots, [(footprint, floors, typology)]) of every block, blocks in south-west to north-east order."""
    rng = random.Random(p["seed"])
    plots, buildings = [], []
    for block in sorted(blocks, key=lambda b: (round(b.bounds[1], 3), round(b.bounds[0], 3))):
        if p["typology"] in LOW_RISE:
            block_plots, block_buildings = _low_rise(block, p, rng)
        elif p["typology"] == "perimeter":
            block_plots, block_buildings = _perimeter(block, p, rng)
        else:
            block_plots, block_buildings = _slabs(block, p, rng)
        plots.extend(block_plots)
        for geom, floors, typology in block_buildings:
            buildings.extend((fp, floors, typology) for fp in _polygons(geom) if fp.area >= MIN_FOOTPRINT_M2)
    return plots, buildings


def generate(outline, params=None, buildable=None):
    """
    Layout for `outline` (a shapely Polygon/MultiPolygon in a metric CRS).
    `buildable` (default: the outline) is the part that may be built on
    (builtup/calculations/site.py cuts protected nature out); streets, blocks
    and buildings stay inside it. `params` overrides the defaults
    (resolve_params). Deterministic for the same params, seed included.
    """
    from . import chain

    p = resolve_params(params)
    outline = unary_union(_polygons(outline.buffer(0)))
    if outline.is_empty:
        raise ValueError("The outline is empty")
    site = outline if buildable is None else unary_union(_polygons(buildable.buffer(0)))
    angle = main_angle(outline) if p["angle_deg"] is None else float(p["angle_deg"])
    p["angle_deg"] = angle
    origin = outline.centroid
    local = affinity.rotate(site, -angle, origin=origin) if not site.is_empty else site

    streets = _streets(local, p) if not local.is_empty else []
    join = "round" if p["street_pattern"] == "curved" else "mitre"
    street_area = unary_union([s.buffer(p["street_width"] / 2, cap_style="flat", join_style=join) for s in streets]) \
        if streets else Polygon()
    blocks = [b for b in _polygons(local.difference(street_area)) if b.area >= MIN_BLOCK_M2] if not local.is_empty else []

    plots, placed = _place(blocks, p)
    if p["target_units"] and p["dwelling_mode"] != "single" and placed:
        # Fewest floors that hold the target (slab spacing grows with height,
        # so the footprint is re-placed per floor count).
        top = LOW_RISE_MAX_FLOORS if p["typology"] in LOW_RISE else MAX_FLOORS
        for floors in range(1, top + 1):
            trial = {**p, "floors": floors}
            trial_plots, trial_placed = _place(blocks, trial)
            units = sum(dwellings(g.area, f, t, trial) for g, f, t in trial_placed)
            if units >= p["target_units"] or floors == top:
                p["floors"], plots, placed = floors, trial_plots, trial_placed
                break

    back = lambda g: affinity.rotate(g, angle, origin=origin)
    buildings = [{
        "geom": back(fp),
        "floors": floors,
        "height_m": round(floors * p["floor_height"], 2),
        "units": dwellings(fp.area, floors, typology, p),
        "typology": typology,
    } for fp, floors, typology in placed]
    layout = Layout(
        params=p,
        streets=[back(s) for s in streets],
        blocks=[back(b) for b in blocks],
        plots=[back(pl) for pl in plots],
        buildings=buildings,
    )
    layout.metrics = chain.layout_metrics(
        site_m2=site.area,
        footprints_m2=[b["geom"].area for b in buildings],
        floors=[b["floors"] for b in buildings],
        units=[b["units"] for b in buildings],
        street_m2=street_area.intersection(local).area if streets else 0.0,
        street_length_m=sum(s.length for s in streets),
        target_units=p["target_units"],
    )
    layout.metrics["outline_m2"] = round(outline.area, 1)
    return layout


def as_multipolygon(geom):
    """Shapely polygon(s) as one MultiPolygon."""
    return MultiPolygon(_polygons(geom))
