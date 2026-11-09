"""
Tree heights from the DSM, for trees whose source gives none.

Most OpenStreetMap trees (osm_trees) carry no `height` tag, so the map would
draw every one of them as a default 10 m 3D model (mainMap/styles/treeStyles.py
scales the model by Tree.height_m). AHN's DSM has measured them: the crown top
is the highest DSM cell near the tree point, the ground is the DEM there (else
a minimum filter of the DSM, dsm_patches.ground_grid), and

    height_m = max(DSM within SAMPLE_RADIUS_M, outside buildings) - ground

A mapped point rarely sits exactly under the crown top, hence the radius.
Cells inside stored building footprints are skipped, so a street tree next to
a facade does not take the roof's height. Results below MIN_DETECTED_M (the
DSM shows no crown: a young tree, a tree planted after the survey, or a point
mapped beside its tree) or above MAX_TREE_HEIGHT_M (a mast or a crane) are not
written: height_m stays empty and the map keeps its default.

Only empty heights are filled; a height from the source always wins. The DSM
is read without the map editor's patches (the measured surface), tile by tile
(TILE_M), so memory follows the tile, not the city.

Called by the importer's bulk finalizer for nature.Tree (importer/batching.py)
and by `manage.py fill_tree_heights` for trees imported earlier. Writes with
bulk_update (no signals): the editor's Vegetation_Coverage -> DSM receivers
only react to editor changes anyway, and BulkWriter / the command bump the
layer cache.
"""
import logging
import math

logger = logging.getLogger(__name__)

SAMPLE_RADIUS_M = 2.0
MIN_DETECTED_M = 2.5      # = dsm_patches.MIN_CANOPY_M: lower is not a crown in the DSM
MAX_TREE_HEIGHT_M = 50.0  # = treeStyles.TREE_MAX_HEIGHT_M
TILE_M = 500.0


def sample_heights(surface, ground, blocked, origin, cell, points):
    """
    Height above ground of each point (x, y) on one grid, or None.

    surface, ground: float arrays of the same shape (NaN = nodata);
    blocked: bool array, True where a cell must not count (buildings) or None;
    origin: upper-left (x, y); cell: square cell size in metres.
    Pure numpy, no database.
    """
    import numpy as np

    rows, cols = surface.shape
    r = int(math.ceil(SAMPLE_RADIUS_M / cell))
    dy, dx = np.mgrid[-r:r + 1, -r:r + 1]
    disc = (dx * dx + dy * dy) * cell * cell <= SAMPLE_RADIUS_M ** 2

    heights = []
    for x, y in points:
        col = int((x - origin[0]) // cell)
        row = int((origin[1] - y) // cell)
        if not (0 <= row < rows and 0 <= col < cols) or not np.isfinite(ground[row, col]):
            heights.append(None)
            continue
        r0, r1 = max(row - r, 0), min(row + r + 1, rows)
        c0, c1 = max(col - r, 0), min(col + r + 1, cols)
        window = surface[r0:r1, c0:c1]
        ok = disc[r0 - row + r:r1 - row + r, c0 - col + r:c1 - col + r] & np.isfinite(window)
        if blocked is not None:
            ok &= ~blocked[r0:r1, c0:c1]
        if not ok.any():
            heights.append(None)
            continue
        h = float(window[ok].max() - ground[row, col])
        heights.append(round(h, 1) if MIN_DETECTED_M <= h <= MAX_TREE_HEIGHT_M else None)
    return heights


def _dsm_extents():
    """(DSM row, extent in the storage CRS) of every DSM, newest first; header reads once per call."""
    from . import svf
    from .models import DigitalSurfaceModel

    out = []
    for dsm in DigitalSurfaceModel.objects.order_by("-year", "-pk"):
        extent = svf.dsm_extent(dsm)
        if extent:
            out.append((dsm, extent))
    return out


def _covering(dsms, box):
    """The DSM that covers most of `box`, newest first on a tie (svf.dsm_for_view without re-reading headers)."""
    from .svf import _area, _intersection

    best, best_key = None, None
    for dsm, extent in dsms:
        covered = _intersection(box, extent)
        if covered is None:
            continue
        key = (round(_area(covered) / _area(box), 3), dsm.year)
        if best_key is None or key > best_key:
            best, best_key = dsm, key
    return best


def fill_from_dsm(trees):
    """
    Fill height_m of the trees in queryset `trees` that have none from the DSM.

    Returns the number of trees that got a height.
    """
    from .dsm_patches import GROUND_WINDOW_M, _building_mask, ground_grid
    from .svf import SVFError, load_dsm

    todo = list(trees.filter(height_m__isnull=True, geom__isnull=False).only("pk", "geom"))
    if not todo:
        return 0
    dsms = _dsm_extents()
    if not dsms:
        logger.info("Tree heights: no Digital Surface Model stored; %d trees keep the default", len(todo))
        return 0

    tiles = {}
    for tree in todo:
        tiles.setdefault((tree.geom.x // TILE_M, tree.geom.y // TILE_M), []).append(tree)

    # Half the ground window as halo, so the minimum filter sees real ground at the tile edge.
    pad = SAMPLE_RADIUS_M + GROUND_WINDOW_M / 2
    filled = []
    for group in tiles.values():
        xs = [t.geom.x for t in group]
        ys = [t.geom.y for t in group]
        box = (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)
        dsm = _covering(dsms, box)
        if dsm is None:
            continue
        try:
            surface, origin, cell, srid = load_dsm(dsm, box, patches=False)
            ground, _ = ground_grid(surface, origin, cell, srid)
            blocked = _building_mask(origin, cell, surface.shape)
        except (SVFError, OSError, ValueError) as exc:
            logger.warning("Tree heights: DSM %s unreadable around %s (%s)", dsm.pk, box, exc)
            continue
        for tree, h in zip(group, sample_heights(surface, ground, blocked, origin, cell,
                                                 [(t.geom.x, t.geom.y) for t in group])):
            if h is not None:
                tree.height_m = h
                filled.append(tree)

    if filled:
        type(filled[0]).objects.bulk_update(filled, ["height_m"], batch_size=1000)
    logger.info("Tree heights: %d of %d trees without a height measured from the DSM", len(filled), len(todo))
    return len(filled)
