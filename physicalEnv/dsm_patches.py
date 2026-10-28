"""
Buildings -> DSM: map-editor building changes as an overlay on the DSM.

A DSM is a city-wide COG (AHN, 0.5 m); rewriting it for every edited building
would be slow and could not be undone. Instead each building the editor
creates, reshapes, re-heights or deletes gets one DSMBuildingPatch row, and
every analysis that reads the DSM (svf.load_dsm: the SVF tool and the SOLWEIG
thermal-comfort tool) applies the patches inside its window:

    1. original footprint (before the first edit)  -> ground level
    2. current footprint                           -> ground + height_m
                                                      (flat roof on the median
                                                      ground under the footprint)

Ground is the DEM on the same grid, or, without a DEM, a minimum filter of the
DSM (GROUND_WINDOW_M), which drops buildings narrower than the window.

Only editor changes are recorded (core.editing.is_editor_change()): BAG imports
already match AHN's measured roofs. Patches are journalled for the editor's
backup (dsm_patch_rewriting / dsm_patch_created, mainMap/signals.py), so
Restore puts them back with the buildings. Every change of a patch, Restore
included, appends a DSMEdit with the area it touched: results calculated
before it there are stale (urban_heat/solweig/pipeline.py::stale_results).

DAG edge: Buildings -> DSM.
"""
import logging

from django.dispatch import Signal

logger = logging.getLogger(__name__)

# Same contract as landcover.landcover_rewriting / landcover_created.
dsm_patch_rewriting = Signal()
dsm_patch_created = Signal()

STOREY_HEIGHT_M = 3.0
# Minimum filter window for the ground estimate without a DEM: wider than
# most buildings, narrow enough to follow the terrain.
GROUND_WINDOW_M = 40.0


def building_height(building):
    """Height above ground of a builtup.Building: height_m, else floors x STOREY_HEIGHT_M, else None."""
    if building.height_m:
        return float(building.height_m)
    if building.numberFloors:
        return building.numberFloors * STOREY_HEIGHT_M
    return None


def record_change(building_id, before, after, height_m):
    """
    Record an editor change of one building.

    before:   its footprint before this edit (None: it was just drawn)
    after:    its footprint now (None: deleted)
    height_m: its height above ground now
    """
    from .models import DSMBuildingPatch

    patch = DSMBuildingPatch.objects.filter(building_id=building_id).first()
    if patch is None:
        patch = DSMBuildingPatch.objects.create(
            building_id=building_id, original_footprint=before, footprint=after, height_m=height_m)
        dsm_patch_created.send(sender=DSMBuildingPatch, pks=[patch.pk])
        return patch
    dsm_patch_rewriting.send(sender=DSMBuildingPatch, pks=[patch.pk])
    if patch.original_footprint is None and after is None:
        # Drawn and deleted again: nothing left to patch.
        patch.delete()
        return None
    patch.footprint, patch.height_m = after, height_m
    patch.save()
    return patch


def _box(origin, cell, shape):
    from django.conf import settings
    from django.contrib.gis.geos import Polygon

    x0, y0 = origin
    box = Polygon.from_bbox((x0, y0 - shape[0] * cell, x0 + shape[1] * cell, y0))
    box.srid = int(settings.COORDINATE_SYSTEM)
    return box


def patches_in(origin, cell, shape):
    from django.db.models import Q

    from .models import DSMBuildingPatch

    box = _box(origin, cell, shape)
    return list(DSMBuildingPatch.objects.filter(
        Q(footprint__bboverlaps=box) | Q(original_footprint__bboverlaps=box)).order_by("updated", "pk"))


def estimate_ground(height, cell):
    """Ground from a DSM grid: minimum filter over GROUND_WINDOW_M, NaN kept."""
    import numpy as np
    from scipy.ndimage import minimum_filter

    size = max(int(round(GROUND_WINDOW_M / cell)) | 1, 3)
    filled = np.where(np.isfinite(height), height, np.inf)
    ground = minimum_filter(filled, size=size, mode="nearest")
    ground[~np.isfinite(ground)] = np.nan
    return ground.astype(np.float32)


def ground_grid(height, origin, cell, srid):
    """
    Ground elevation on the grid of `height`: the DEM covering it (read on the
    exact same transform), else estimate_ground(). Returns (ground, label).
    """
    from . import svf
    from .models import DigitalElevationModel

    extent = (origin[0], origin[1] - height.shape[0] * cell, origin[0] + height.shape[1] * cell, origin[1])
    dem, _ = svf.dsm_for_view(extent, model=DigitalElevationModel)
    if dem is not None and dem.cog_path:
        try:
            ground = svf.read_cog_on_grid(dem.cog_path, origin, cell, height.shape, srid)
            return ground, f"DEM {dem.pk}"
        except Exception:
            logger.exception("DEM %s: could not read %s; estimating ground from the DSM", dem.pk, dem.cog_path)
    return estimate_ground(height, cell), "ground estimated from DSM"


def burn(geoms, origin, cell, shape):
    """Boolean mask of the cells whose centre lies in any of `geoms` (GEOS)."""
    import json

    import numpy as np
    from rasterio.features import rasterize
    from rasterio.transform import from_origin

    shapes = [(json.loads(g.json), 1) for g in geoms if g is not None and not g.empty]
    if not shapes:
        return np.zeros(shape, dtype=bool)
    return rasterize(shapes, out_shape=shape, transform=from_origin(origin[0], origin[1], cell, cell),
                     fill=0, dtype="uint8").astype(bool)


def apply_patches(height, origin, cell, srid, ground=None):
    """
    `height` (a DSM grid, storage CRS, upper-left `origin`) with the editor's
    building changes applied. Returns the same array when no patch touches it.
    `ground` (same grid) is read only when a patch needs it.
    """
    import numpy as np

    patches = patches_in(origin, cell, height.shape)
    if not patches:
        return height
    if ground is None:
        ground, _ = ground_grid(height, origin, cell, srid)
    out = height.copy()
    cleared = burn([p.original_footprint for p in patches], origin, cell, height.shape)
    out[cleared] = ground[cleared]
    for p in patches:
        if p.footprint is None or not p.height_m:
            continue
        mask = burn([p.footprint], origin, cell, height.shape)
        base = ground[mask]
        base = base[np.isfinite(base)]
        if base.size:
            out[mask] = float(np.median(base)) + p.height_m
    logger.info("Applied %s building patch(es) to a %s x %s DSM grid", len(patches), *height.shape[::-1])
    return out
