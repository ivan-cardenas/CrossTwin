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

Vegetation (DAG edge Vegetation_Coverage -> DSM) works the same way: a tree
(nature.Tree) or forest (nature.Forests) the editor adds, moves, resizes or
deletes gets one DSMVegetationPatch. Tall vegetation (more than MIN_CANOPY_M
above ground, outside building footprints) is cleared where it was removed,
and canopy is added where it was planted: a tree as a paraboloid crown of its
height, a forest as a flat DEFAULT_FOREST_CANOPY_M. Parks and green spaces
are not sources: their outlines do not record trees.

Order inside one window: building originals cleared, vegetation cleared,
vegetation added, buildings raised (so a tree may stand where a building was
demolished, and a new roof always wins over a crown).

DAG edges: Buildings -> DSM, Vegetation_Coverage -> DSM.
"""
import logging

from django.dispatch import Signal

logger = logging.getLogger(__name__)

# Same contract as landcover.landcover_rewriting / landcover_created.
dsm_patch_rewriting = Signal()
dsm_patch_created = Signal()

STOREY_HEIGHT_M = 3.0
# Cells this far above ground outside buildings count as tall vegetation
# (also SOLWEIG's Trees threshold, urban_heat/solweig/inputs.py).
MIN_CANOPY_M = 2.5
DEFAULT_TREE_HEIGHT_M = 10.0
CROWN_PER_HEIGHT = 0.6        # crown diameter / height when the crown is not mapped
CROWN_EDGE_FRACTION = 0.5     # paraboloid crown height at its edge, share of the top
DEFAULT_FOREST_CANOPY_M = 15.0
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


def tree_height(tree):
    """Height of a nature.Tree: height_m, else DEFAULT_TREE_HEIGHT_M."""
    return float(tree.height_m) if tree.height_m else DEFAULT_TREE_HEIGHT_M


def tree_crown(point, height_m=None, crown_diameter_m=None):
    """Crown disc of a tree at `point` (MultiPolygon, storage CRS): crownDiameter_m, else CROWN_PER_HEIGHT x height."""
    from django.contrib.gis.geos import MultiPolygon

    if point is None or point.empty:
        return None
    diameter = crown_diameter_m or CROWN_PER_HEIGHT * (height_m or DEFAULT_TREE_HEIGHT_M)
    disc = point.buffer(max(diameter, 1.0) / 2.0, quadsegs=8)
    return MultiPolygon(disc, srid=point.srid)


def record_vegetation_change(source, source_id, before, after, canopy_m):
    """
    Record an editor change of one tree or forest (DSMVegetationPatch).

    source:   "nature.Tree" or "nature.Forests"
    before:   its crown disc / polygon before this edit (None: just drawn)
    after:    its crown disc / polygon now (None: deleted)
    canopy_m: canopy height above ground now (None: deleted)
    """
    from .models import DSMVegetationPatch

    patch = DSMVegetationPatch.objects.filter(source=source, source_id=source_id).first()
    if patch is None:
        patch = DSMVegetationPatch.objects.create(
            source=source, source_id=source_id, original_geom=before, geom=after, canopy_m=canopy_m)
        dsm_patch_created.send(sender=DSMVegetationPatch, pks=[patch.pk])
        return patch
    dsm_patch_rewriting.send(sender=DSMVegetationPatch, pks=[patch.pk])
    if patch.original_geom is None and after is None:
        patch.delete()
        return None
    patch.geom, patch.canopy_m = after, canopy_m
    patch.save()
    return patch


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


def vegetation_patches_in(origin, cell, shape):
    from django.db.models import Q

    from .models import DSMVegetationPatch

    box = _box(origin, cell, shape)
    return list(DSMVegetationPatch.objects.filter(
        Q(geom__bboverlaps=box) | Q(original_geom__bboverlaps=box)).order_by("updated", "pk"))


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


def _building_mask(origin, cell, shape):
    """Cells inside any stored builtup.Building footprint (never cleared as vegetation)."""
    from builtup.models import Building

    return burn(Building.objects.filter(geom__bboverlaps=_box(origin, cell, shape))
                .values_list("geom", flat=True), origin, cell, shape)


def _difference(a, b):
    if a is None or a.empty:
        return None
    if b is None or b.empty:
        return a
    return a.difference(b)


def crown_heights(geom, canopy_m, origin, cell, shape):
    """
    Paraboloid crown over the disc `geom` on the grid: canopy x (1 - (r/R)^2),
    at least CROWN_EDGE_FRACTION x canopy inside the disc, NaN outside.
    """
    import math

    import numpy as np

    heights = np.full(shape, np.nan, dtype=np.float32)
    mask = burn([geom], origin, cell, shape)
    if not mask.any():
        return heights
    centre = geom.centroid
    radius = max(math.sqrt(geom.area / math.pi), cell)
    rows, cols = np.nonzero(mask)
    x = origin[0] + (cols + 0.5) * cell
    y = origin[1] - (rows + 0.5) * cell
    r2 = ((x - centre.x) ** 2 + (y - centre.y) ** 2) / radius ** 2
    heights[rows, cols] = canopy_m * np.clip(1.0 - r2, CROWN_EDGE_FRACTION, 1.0)
    return heights


def _apply_vegetation(out, ground, patches, origin, cell):
    """Clear the removed tall vegetation, then add the planted canopy (in place)."""
    import numpy as np

    shape = out.shape
    cleared = np.zeros(shape, dtype=bool)
    for p in patches:
        # a tree's whole old crown goes (moved or resized); a forest loses only what it gave up
        gone = p.original_geom if p.source == "nature.Tree" else _difference(p.original_geom, p.geom)
        if gone is not None and not gone.empty:
            cleared |= burn([gone], origin, cell, shape)
    if cleared.any():
        with np.errstate(invalid="ignore"):
            tall = np.isfinite(out) & np.isfinite(ground) & (out - ground > MIN_CANOPY_M)
        cleared &= tall & ~_building_mask(origin, cell, shape)
        out[cleared] = ground[cleared]

    for p in patches:
        if p.geom is None or p.geom.empty or not p.canopy_m:
            continue
        if p.source == "nature.Tree":
            heights = crown_heights(p.geom, p.canopy_m, origin, cell, shape)
        else:
            # only the new part of a forest: its old part keeps the measured canopy
            planted = _difference(p.geom, p.original_geom)
            if planted is None or planted.empty:
                continue
            heights = np.where(burn([planted], origin, cell, shape), np.float32(p.canopy_m), np.nan)
        mask = np.isfinite(heights) & np.isfinite(ground)
        out[mask] = np.fmax(out[mask], ground[mask] + heights[mask])


def apply_patches(height, origin, cell, srid, ground=None):
    """
    `height` (a DSM grid, storage CRS, upper-left `origin`) with the editor's
    building and vegetation changes applied. Returns the same array when no
    patch touches it. `ground` (same grid) is read only when a patch needs it.

    Order: building originals -> ground, vegetation cleared, vegetation added,
    current buildings raised.
    """
    import numpy as np

    buildings = patches_in(origin, cell, height.shape)
    vegetation = vegetation_patches_in(origin, cell, height.shape)
    if not buildings and not vegetation:
        return height
    if ground is None:
        ground, _ = ground_grid(height, origin, cell, srid)
    out = height.copy()
    if buildings:
        cleared = burn([p.original_footprint for p in buildings], origin, cell, height.shape)
        out[cleared] = ground[cleared]
    if vegetation:
        _apply_vegetation(out, ground, vegetation, origin, cell)
    for p in buildings:
        if p.footprint is None or not p.height_m:
            continue
        mask = burn([p.footprint], origin, cell, height.shape)
        base = ground[mask]
        base = base[np.isfinite(base)]
        if base.size:
            out[mask] = float(np.median(base)) + p.height_m
    logger.info("Applied %s building and %s vegetation patch(es) to a %s x %s DSM grid",
                len(buildings), len(vegetation), *height.shape[::-1])
    return out
