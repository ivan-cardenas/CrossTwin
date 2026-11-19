"""
Buildings -> DSM, Vegetation_Coverage -> DSM: the editor's patches written
into the surface height raster the map shows.

dsm_patches.py keeps the edits as an overlay (DSMBuildingPatch,
DSMVegetationPatch) that every analysis applies when it reads the DSM
(svf.load_dsm). This module burns the same overlay into a copy of the DSM's
COG, `DigitalSurfaceModel.edited_cog_path`, so the DSM layer on the map
changes as soon as a building or tree is edited, before any SVF or thermal
comfort recalculation:

    edit saved -> patch row -> DSMEdit (area)        (physicalEnv/signals.py)
               -> on commit: queued for the background worker thread
                  (one per process; edits arriving while it writes are
                  coalesced into its next pass), which runs refresh_pending():
                    for each DSM the new DSMEdits overlap:
                      copy of the edited COG (or of cog_path the first time)
                      each area: cog_path read on a storage-CRS grid
                                 -> dsm_patches.apply_patches
                                 -> changed cells warped back onto the COG's
                                    own grid and written there
                      -> new COG (overviews rebuilt), versioned file name
                         so map tiles are not served from a browser cache

Each area is recomputed from the measured COG plus *all* patches, so an
edit that is moved, deleted or restored puts the measured surface back.
`edited_upto` is the last DSMEdit id written in; a failed or rolled-back
refresh is caught up by the next one. cog_path itself is never rewritten:
analyses keep reading it with the patches applied on their own grid
(no double resampling), which gives the same surface.

The save no longer waits for the rewrite; the map polls busy() through
/physicalEnv/dsm/edited/status/ and reloads the DSM tiles when it is done.
The cost is GDAL's compression and overview build, CPU work that a GPU does
not speed up; it runs multithreaded (NUM_THREADS=ALL_CPUS). Tests set
DSM_EDIT_BACKGROUND = False (a thread cannot see a TestCase's transaction).
"""
import logging
import os
import threading

from core.background import BackgroundWorker

logger = logging.getLogger(__name__)

_lock = threading.Lock()
# Cells added around each edited area: nearest-neighbour warping between the
# storage CRS and EPSG:4326 can move an edge by a cell.
PAD_CELLS = 3


def _background():
    from django.conf import settings

    return getattr(settings, "DSM_EDIT_BACKGROUND", True)


def _job(items):
    """One worker pass: every queued DSM id (None = all DSMs) once."""
    pks = set(items)
    if None in pks:
        refresh_pending()
    else:
        for pk in sorted(pks):
            refresh_pending(pk)


# core/background.py: one coalescing thread per process.
_worker = BackgroundWorker("dsm-edited", lambda items: _job(items))


def schedule_refresh(dsm_pk=None):
    """Refresh the edited COGs when the current transaction commits (at once outside one), in the background."""
    from django.db import transaction

    transaction.on_commit(lambda: enqueue(dsm_pk))


def enqueue(dsm_pk=None):
    """Queue a refresh for the worker thread (synchronous without DSM_EDIT_BACKGROUND)."""
    if not _background():
        refresh_pending(dsm_pk)
        return
    _worker.submit(dsm_pk)


def busy():
    """True while edits are queued or being written into an edited COG (this process)."""
    return _worker.busy()


def refresh_pending(dsm_pk=None):
    """Bring every DSM's (or one DSM's) edited COG up to the latest DSMEdit. Never raises."""
    from ..models import DigitalSurfaceModel

    rows = DigitalSurfaceModel.objects.exclude(cog_path__isnull=True).exclude(cog_path="")
    if dsm_pk is not None:
        rows = rows.filter(pk=dsm_pk)
    for dsm in rows.defer("dsm_raster"):
        try:
            refresh_edited_cog(dsm)
        except Exception:
            logger.exception("DSM %s: could not write the editor's changes into its COG", dsm.pk)


def _patch_extents():
    from ..models import DSMBuildingPatch, DSMVegetationPatch

    extents = []
    for model, fields in ((DSMBuildingPatch, ("original_footprint", "footprint")),
                          (DSMVegetationPatch, ("original_geom", "geom"))):
        for row in model.objects.values_list(*fields):
            extents += [g.extent for g in row if g is not None and not g.empty]
    return extents


def _usable(path):
    return bool(path) and os.path.exists(path)


def refresh_edited_cog(dsm):
    """
    Write the DSMEdits after `dsm.edited_upto` into `dsm`'s edited COG (all
    patches when it has none yet). Returns the edited COG path, or None when
    no edit touches the DSM.
    """
    from django.db.models import Max

    from . import svf
    from ..models import DigitalSurfaceModel, DSMEdit

    with _lock:
        dsm.refresh_from_db(fields=["cog_path", "edited_cog_path", "edited_upto"])
        if not _usable(dsm.cog_path):
            return None
        last = DSMEdit.objects.aggregate(last=Max("pk"))["last"] or 0
        incremental = _usable(dsm.edited_cog_path) and dsm.edited_upto is not None
        if incremental:
            if dsm.edited_upto >= last:
                return dsm.edited_cog_path
            areas = [e.extent for e in DSMEdit.objects.filter(pk__gt=dsm.edited_upto, pk__lte=last)
                     .values_list("area", flat=True)]
        else:
            areas = _patch_extents()

        extent = svf.dsm_extent(dsm)
        areas = [a for a in areas if extent and svf._intersection(a, extent)]
        if not areas:
            DigitalSurfaceModel.objects.filter(pk=dsm.pk).update(edited_upto=last)
            return dsm.edited_cog_path if incremental else None

        old = dsm.edited_cog_path
        new = write_edited_cog(dsm, areas, base_path=old if incremental else dsm.cog_path)
        DigitalSurfaceModel.objects.filter(pk=dsm.pk).update(edited_cog_path=new, edited_upto=last)
        if old and old != new and os.path.exists(old):
            try:
                os.unlink(old)
            except OSError as e:   # Windows: TiTiler may still hold it open
                logger.warning("Could not delete the previous edited DSM %s: %s", old, e)
        logger.info("DSM %s: %s edited area(s) written into %s", dsm.pk, len(areas), new)
        return new


def edited_cog_name(cog_path):
    import time

    stem, _ = os.path.splitext(cog_path)
    return f"{stem}_edited_{int(time.time() * 1000)}.tif".replace("\\", "/")


def write_edited_cog(dsm, areas, base_path):
    """
    A new COG: `base_path` (the previous edited COG, or the measured one) with
    every area in `areas` (storage-CRS extents) recomputed as cog_path +
    patches. Returns its path.
    """
    import shutil
    import tempfile

    import rasterio
    from rio_cogeo.cogeo import cog_translate
    from rio_cogeo.profiles import cog_profiles

    from . import svf

    srid = svf._storage_srid()
    cell = svf.source_cell_size(dsm)
    fd, work = tempfile.mkstemp(suffix="_dsm_edit.tif")
    os.close(fd)
    try:
        # The copy is a COG; it is only a work file, cog_translate rebuilds the layout.
        shutil.copyfile(base_path, work)
        with rasterio.open(dsm.cog_path) as measured, rasterio.open(work, "r+", IGNORE_COG_LAYOUT_BREAK="YES") as out:
            if (out.transform, out.shape) != (measured.transform, measured.shape):
                raise ValueError(f"{base_path} is not on the grid of {dsm.cog_path}")
            for area in areas:
                patch_window(dsm.cog_path, measured, out, area, cell, srid)
        new = edited_cog_name(dsm.cog_path)
        profile = cog_profiles.get("DEFLATE")
        profile.update(NUM_THREADS="ALL_CPUS")   # multithreaded compression
        with rasterio.Env(GDAL_NUM_THREADS="ALL_CPUS"):
            cog_translate(work, new, profile, overview_level=6,
                          overview_resampling="nearest", use_cog_driver=True, quiet=True)
        return new
    finally:
        try:
            os.unlink(work)
        except OSError:
            pass


def cog_window(src, bounds):
    """The integer window of `src` covering `bounds` (src CRS), clipped to it, or None."""
    import math

    from rasterio.windows import Window

    inv = ~src.transform
    cols, rows = zip(*(inv * (x, y) for x in (bounds[0], bounds[2]) for y in (bounds[1], bounds[3])))
    c0, r0 = max(int(math.floor(min(cols))), 0), max(int(math.floor(min(rows))), 0)
    c1, r1 = min(int(math.ceil(max(cols))), src.width), min(int(math.ceil(max(rows))), src.height)
    if c1 <= c0 or r1 <= r0:
        return None
    return Window(c0, r0, c1 - c0, r1 - r0)


def patch_window(cog_path, measured, out, area, cell, srid):
    """
    Recompute one edited area of `out` (same grid as `measured`, the COG at
    `cog_path`): the measured surface on a storage-CRS grid, patched, and the
    cells the patches changed warped back onto the COG's grid. Other cells
    get the measured value, so a reverted edit disappears.
    """
    import math

    import numpy as np
    from rasterio.enums import Resampling
    from rasterio.transform import from_origin
    from rasterio.warp import reproject, transform_bounds
    from rasterio.windows import bounds as window_bounds

    from .dsm_patches import apply_patches
    from .svf import read_cog_on_grid

    storage = f"EPSG:{srid}"
    pad = PAD_CELLS * cell
    padded = (area[0] - pad, area[1] - pad, area[2] + pad, area[3] + pad)
    win = cog_window(measured, transform_bounds(storage, measured.crs, *padded))
    if win is None:
        return

    # The storage-CRS grid over the window, snapped to whole cells like svf._read_dsm.
    gx0, gy0, gx1, gy1 = transform_bounds(measured.crs, storage, *window_bounds(win, measured.transform))
    gx0, gy1 = math.floor(gx0 / cell) * cell, math.ceil(gy1 / cell) * cell
    shape = (max(math.ceil((gy1 - gy0) / cell), 1), max(math.ceil((gx1 - gx0) / cell), 1))
    base = read_cog_on_grid(cog_path, (gx0, gy1), cell, shape, srid)
    patched = apply_patches(base, (gx0, gy1), cell, srid)

    with np.errstate(invalid="ignore"):
        changed = np.isfinite(patched) & ~((patched == base) | (np.isnan(patched) & np.isnan(base)))

    grid = from_origin(gx0, gy1, cell, cell)
    win_shape = (int(win.height), int(win.width))
    win_transform = measured.window_transform(win)
    values = np.full(win_shape, np.nan, dtype=np.float32)
    mask = np.zeros(win_shape, dtype=np.uint8)
    if changed.any():
        reproject(patched.astype(np.float32), values, src_transform=grid, src_crs=storage,
                  dst_transform=win_transform, dst_crs=measured.crs, resampling=Resampling.nearest,
                  src_nodata=np.nan, dst_nodata=np.nan)
        reproject(changed.astype(np.uint8), mask, src_transform=grid, src_crs=storage,
                  dst_transform=win_transform, dst_crs=measured.crs, resampling=Resampling.nearest,
                  src_nodata=None, dst_nodata=0)

    original = measured.read(1, window=win)
    use = mask.astype(bool) & np.isfinite(values)
    result = np.where(use, values, original).astype(original.dtype)
    out.write(result, 1, window=win)
