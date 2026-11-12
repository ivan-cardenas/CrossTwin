"""
Building heights from the DSM, for buildings whose source gives none.

BAG panden (pdok_buildings) carry no height, so every downstream use
(the map's 3D extrusion, Buildings -> Canyon_Aspect, Buildings -> DSM for
edited buildings, SOLWEIG's wall heights) would fall back to floors x 3 m or
a default. AHN's DSM has measured them:

    height_m = P70(DSM cells inside the footprint) - median(ground under the footprint)

The 70th percentile is the roof height 3DBAG publishes for LoD1.2 (b3_h_70p):
above the eaves of a pitched roof, below chimneys and antennas. Ground is the
DEM on the same grid, else a minimum filter of the DSM
(dsm_patches.ground_grid). Results below MIN_BUILDING_HEIGHT_M (a footprint
the DSM does not show: demolished, built after the survey, or a carport) or
above MAX_BUILDING_HEIGHT_M are not written.

Only empty heights are filled; a height from the source always wins. The DSM
is read without the map editor's patches (the measured surface), tile by tile
(TILE_M), so memory follows the tile, not the city.

Called by the importer after a builtup.Building import (importer/
external_data.py::_fill_building_heights), and after a DSM import for the
stored buildings under it that still have none (fill_under_dsm, from
external_data.py::_heights_after_dsm), so the import order does not matter.
Writes with bulk_update (no signals): the import runs inside
deferred_cascades(), whose canyon refresh (Buildings -> Canyon_Aspect) runs
after this and reads the new heights; the caller bumps the layer cache.
"""
import logging

logger = logging.getLogger(__name__)

ROOF_PERCENTILE = 70
MIN_BUILDING_HEIGHT_M = 2.0
MAX_BUILDING_HEIGHT_M = 350.0
TILE_M = 500.0


def footprint_heights(surface, ground, labels, count):
    """
    Height above ground of each footprint on one grid, or None.

    surface, ground: float arrays of the same shape (NaN = nodata);
    labels: int array, 0 = no footprint, i + 1 = footprint i;
    count: number of footprints. Pure numpy, no database.
    """
    import numpy as np

    flat = labels.ravel()
    inside = np.flatnonzero(flat)
    order = inside[np.argsort(flat[inside], kind="stable")]
    bounds = np.searchsorted(flat[order], np.arange(1, count + 2))
    s, g = surface.ravel(), ground.ravel()

    heights = []
    for i in range(count):
        cells = order[bounds[i]:bounds[i + 1]]
        roof, base = s[cells], g[cells]
        roof, base = roof[np.isfinite(roof)], base[np.isfinite(base)]
        if not roof.size or not base.size:
            heights.append(None)
            continue
        h = float(np.percentile(roof, ROOF_PERCENTILE) - np.median(base))
        heights.append(round(h, 1) if MIN_BUILDING_HEIGHT_M <= h <= MAX_BUILDING_HEIGHT_M else None)
    return heights


def _label(geoms, origin, cell, shape):
    """Int32 grid: i + 1 where the cell centre lies in geoms[i] (a later footprint wins an overlap)."""
    import json

    import numpy as np
    from rasterio.features import rasterize
    from rasterio.transform import from_origin

    shapes = [(json.loads(g.json), i + 1) for i, g in enumerate(geoms)]
    if not shapes:
        return np.zeros(shape, dtype=np.int32)
    return rasterize(shapes, out_shape=shape, transform=from_origin(origin[0], origin[1], cell, cell),
                     fill=0, dtype="int32")


def fill_from_dsm(buildings):
    """
    Fill height_m of the buildings in queryset `buildings` that have none from the DSM.

    Returns the number of buildings that got a height.
    """
    return len(_fill(buildings))


def fill_under_dsm(dsm):
    """
    Fill height_m of the stored buildings without one inside the extent of `dsm`
    (just imported), then refresh the street canyons around them
    (Buildings -> Canyon_Aspect; bulk_update fires no post_save) and the
    building layer cache. Returns the number of buildings that got a height.
    """
    from django.contrib.gis.geos import Polygon

    from builtup.models import Building
    from builtup.signals import schedule_footprints
    from core.cache import bump_layer_version

    from .svf import _storage_srid, dsm_extent

    extent = dsm_extent(dsm)
    if not extent:
        return 0
    box = Polygon.from_bbox(extent)
    box.srid = _storage_srid()
    filled = _fill(Building.objects.filter(geom__bboverlaps=box))
    if filled:
        schedule_footprints([b.geom for b in filled])
        bump_layer_version(Building)
    return len(filled)


def _fill(buildings):
    """fill_from_dsm's work; returns the buildings that got a height."""
    from .dsm_patches import GROUND_WINDOW_M, ground_grid
    from .svf import SVFError, load_dsm
    from .tree_heights import _covering, _dsm_extents

    todo = list(buildings.filter(height_m__isnull=True, geom__isnull=False).only("pk", "geom"))
    if not todo:
        return []
    dsms = _dsm_extents()
    if not dsms:
        logger.info("Building heights: no Digital Surface Model stored; %d buildings keep no height", len(todo))
        return []

    tiles = {}
    for building in todo:
        c = building.geom.centroid
        tiles.setdefault((c.x // TILE_M, c.y // TILE_M), []).append(building)

    # Half the ground window as halo, so the minimum filter sees real ground at the tile edge.
    pad = GROUND_WINDOW_M / 2
    filled = []
    for group in tiles.values():
        extents = [b.geom.extent for b in group]
        box = (min(e[0] for e in extents) - pad, min(e[1] for e in extents) - pad,
               max(e[2] for e in extents) + pad, max(e[3] for e in extents) + pad)
        dsm = _covering(dsms, box)
        if dsm is None:
            continue
        try:
            surface, origin, cell, srid = load_dsm(dsm, box, patches=False)
            ground, _ = ground_grid(surface, origin, cell, srid)
            labels = _label([b.geom for b in group], origin, cell, surface.shape)
        except (SVFError, OSError, ValueError) as exc:
            logger.warning("Building heights: DSM %s unreadable around %s (%s)", dsm.pk, box, exc)
            continue
        for building, h in zip(group, footprint_heights(surface, ground, labels, len(group))):
            if h is not None:
                building.height_m = h
                filled.append(building)

    if filled:
        type(filled[0]).objects.bulk_update(filled, ["height_m"], batch_size=1000)
    logger.info("Building heights: %d of %d buildings without a height measured from the DSM", len(filled), len(todo))
    return filled
