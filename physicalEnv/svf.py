"""
Sky-view factor (SVF) from a Digital Surface Model, stored as an
urban_heat.SkyViewFactor raster.

Flow:

    physicalEnv.DigitalSurfaceModel
        -> the view (map bounds) plus a halo of one search radius, read as an
           elevation grid in the storage CRS (settings.COORDINATE_SYSTEM):
           a window of `dsm_raster` when it is stored in Postgres, otherwise a
           warped window of the row's COG (EPSG:4326, see
           core/rasterOperations.py::_reproject_and_cog) on a square grid
        -> sky_view_factor(): horizon search in `num_directions` azimuths up to
           `radius_m`, SVF = mean over the azimuths of 1 - sin(horizon angle)
        -> halo cropped off; SkyViewFactor row over the view (0..1, nodata
           -9999); its post_save exports the COG. Earlier rows of the same DSM
           inside the view are replaced (recalculation).

The horizon search is a port of the Relief Visualization Toolbox
(Zakšek et al. 2011; Kokalj et al. 2011, `rvt.vis.sky_view_factor`), received
as an ArcGIS script. Two changes from that script: the height difference is
divided by the cell size, so the slope is dimensionless (the script divided
metres by pixels, which is only right on a 1 m grid), and the shifted grids are
slices of one padded array instead of `np.roll` copies. NaN cells (DSM nodata)
are skipped as horizon candidates and stay NaN in the output.

DAG edge: DSM -> SVF. Computed on demand (`calculate_svf`: the map's SVF tool,
core/static/js/SvfTool.js + physicalEnv/views.py), not by a receiver: a DSM
import must not start a city-wide horizon search from a post_save.
"""
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

NODATA = -9999.0
METHOD_LABEL = "Horizon search (RVT)"
# Rows of the output computed at once. Each block holds the padded DSM block
# plus three float32 work arrays, so memory per block stays bounded no matter
# how large the DSM is.
BLOCK_ROWS = 1024
# Largest read window (view + halo) in cells: ~4000 x 4000. The height grid and
# the output are float32, so this keeps the two at ~64 MB each.
MAX_CELLS = 16_000_000
DEFAULT_RADIUS_M = 50.0
# SkyViewFactor.source starts with this + the DSM id, so a recalculation finds
# the rows of the same DSM.
SOURCE_PREFIX = "DSM "


def horizon_shift_vector(num_directions=16, radius_pixels=10, min_radius=1):
    """
    Pixel offsets visited by the horizon search, per azimuth.

    Returns {azimuth_deg: {"shift": [(d0, d1), ...], "distance": ndarray}}:
    for each azimuth the integer offsets along axis 0 / axis 1 of every cell
    on the search ray (deduplicated, sorted by distance) and their distance
    from the centre in pixels.
    """
    import numpy as np

    shift = {}
    angles = (2 * np.pi / num_directions) * np.arange(num_directions)
    x = np.cos(angles)
    y = np.sin(angles)
    angles = np.round(np.degrees(angles), decimals=1)

    # Sample the ray at 1/3 pixel so no cell along it is skipped; starting at
    # min_radius keeps the centre (0, 0) out.
    scale = 3.0
    radii = np.arange((radius_pixels - min_radius) * scale + 1) / scale + min_radius

    for i in range(num_directions):
        x_int = np.round(x[i] * radii, decimals=0)
        y_int = np.round(y[i] * radii, decimals=0)
        # Unique cells: a set of complex numbers dedups (x, y) pairs in one go.
        coord_complex = set(x_int + 1j * y_int)
        shift_pairs = np.array([(k.real, k.imag) for k in coord_complex]).astype(int)
        distance = np.sqrt(np.sum(shift_pairs ** 2, axis=1))
        sort_index = np.argsort(distance)
        shift[angles[i]] = {
            "shift": [(int(k[0]), int(k[1])) for k in shift_pairs[sort_index]],
            "distance": distance[sort_index],
        }
    return shift


def _svf_block(padded, pad, rows, cols, move, num_directions):
    """SVF of the `rows` x `cols` interior of `padded` (heights in cell units)."""
    import numpy as np

    centre = padded[pad:pad + rows, pad:pad + cols]
    svf = np.zeros((rows, cols), dtype=np.float32)
    for direction in move.values():
        max_slope = np.full((rows, cols), -1000.0, dtype=np.float32)
        for (d0, d1), radius in zip(direction["shift"], direction["distance"]):
            # np.roll(h, (d0, d1))[i, j] == h[i - d0, j - d1]
            neighbour = padded[pad - d0:pad - d0 + rows, pad - d1:pad - d1 + cols]
            # fmax ignores NaN, so a nodata neighbour is just not a horizon.
            np.fmax(max_slope, (neighbour - centre) / radius, out=max_slope)
        svf += 1.0 - np.sin(np.maximum(np.arctan(max_slope), 0.0))
    svf /= num_directions
    svf[np.isnan(centre)] = np.nan
    return svf


def sky_view_factor(height, cell_size, radius_pixels=10, min_radius=1,
                    num_directions=16, no_data=None, block_rows=BLOCK_ROWS):
    """
    Sky-view factor of a surface model.

    height:        2D array of elevations in metres (DSM).
    cell_size:     cell size in metres (square cells).
    radius_pixels: maximum horizon search distance, in cells.
    min_radius:    first cell searched, in cells (noise reduction).
    no_data:       value marking nodata cells (also any non-finite value).

    Returns a float32 array of the same shape: 1 = open sky, 0 = no sky,
    NaN at nodata. Pure numpy, no DB access.
    """
    import numpy as np

    height = np.array(height, dtype=np.float32)
    height[~np.isfinite(height)] = np.nan
    if no_data is not None:
        height[height == np.float32(no_data)] = np.nan
    # Heights in cell units, so (dz / distance_in_cells) is tan(elevation angle).
    height /= np.float32(cell_size)

    pad = int(radius_pixels)
    # Mirror the edges (like the RVT script) so border cells see a plausible
    # horizon instead of a cliff.
    padded = np.pad(height, pad, mode="symmetric")
    move = horizon_shift_vector(num_directions=num_directions,
                                radius_pixels=radius_pixels, min_radius=min_radius)

    n_rows, n_cols = height.shape
    out = np.empty((n_rows, n_cols), dtype=np.float32)
    for r0 in range(0, n_rows, block_rows):
        rows = min(block_rows, n_rows - r0)
        block = padded[r0:r0 + rows + 2 * pad]
        out[r0:r0 + rows] = _svf_block(block, pad, rows, n_cols, move, num_directions)
    return out


class SVFError(ValueError):
    """An expected failure the map tool shows as-is (no DSM, view too large...)."""


@dataclass
class SVFResult:
    record: object
    dsm: object
    replaced: list = field(default_factory=list)
    width: int = 0
    height: int = 0
    cell: float = 0.0
    radius_m: float = 0.0
    valid_fraction: float = 0.0
    mean: float = None
    min: float = None
    max: float = None


def _storage_srid():
    from django.conf import settings

    return int(settings.COORDINATE_SYSTEM)


def wgs84_to_storage(bbox_wgs84):
    """(west, south, east, north) in degrees -> (minx, miny, maxx, maxy) in the storage CRS."""
    from django.contrib.gis.geos import Polygon

    poly = Polygon.from_bbox(tuple(bbox_wgs84))
    poly.srid = 4326
    poly.transform(_storage_srid())
    return poly.extent


def dsm_extent(dsm):
    """Extent of a DSM row in the storage CRS (header reads only), or None."""
    if dsm.dsm_raster is not None:
        return tuple(dsm.dsm_raster.extent)
    if not dsm.cog_path:
        return None
    import rasterio
    from rasterio.warp import transform_bounds

    try:
        with rasterio.open(dsm.cog_path) as src:
            return transform_bounds(src.crs, f"EPSG:{_storage_srid()}", *src.bounds)
    except rasterio.RasterioIOError:
        logger.warning("DSM %s: cannot open COG %s", dsm.pk, dsm.cog_path)
        return None


def _intersection(a, b):
    box = (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))
    return box if box[2] > box[0] and box[3] > box[1] else None


def _area(box):
    return (box[2] - box[0]) * (box[3] - box[1]) if box else 0.0


def dsm_for_view(view):
    """
    The DSM that covers most of `view` (storage CRS), newest year first on a
    tie. Returns (dsm, the part of the view it covers) or (None, None).
    """
    from .models import DigitalSurfaceModel

    best, best_key = (None, None), None
    for dsm in DigitalSurfaceModel.objects.order_by("-year", "-pk"):
        extent = dsm_extent(dsm)
        covered = _intersection(view, extent) if extent else None
        if covered is None:
            continue
        key = (round(_area(covered) / _area(view), 3), dsm.year)
        if best_key is None or key > best_key:
            best, best_key = (dsm, covered), key
    return best


def source_cell_size(dsm):
    """The DSM's own cell size in metres (the COG is in degrees)."""
    if dsm.dsm_raster is not None:
        return abs(dsm.dsm_raster.scale[0])
    import rasterio
    from rasterio.warp import calculate_default_transform

    with rasterio.open(dsm.cog_path) as src:
        native, _, _ = calculate_default_transform(
            src.crs, f"EPSG:{_storage_srid()}", src.width, src.height, *src.bounds)
    return (abs(native.a) + abs(native.e)) / 2


def load_dsm(dsm, bbox, resolution=None):
    """
    Elevation grid of a DigitalSurfaceModel row inside `bbox`, in the storage CRS.

    Only the cells inside `bbox` are read: a window of the stored raster, or a
    warped window of the COG, so memory scales with the view, not the city.

    bbox:       (minx, miny, maxx, maxy) in settings.COORDINATE_SYSTEM.
    resolution: cell size in metres for the COG path (default: the source
                COG's own cell size, converted from degrees to metres).

    Returns (height ndarray float32 with NaN at nodata, origin (x, y) of the
    upper-left corner, cell size in metres, srid).
    """
    import numpy as np

    srid = _storage_srid()
    minx, miny, maxx, maxy = bbox

    if dsm.dsm_raster is not None:
        raster = dsm.dsm_raster
        x0, y0 = raster.origin
        sx, sy = raster.scale
        if abs(abs(sx) - abs(sy)) > 1e-6 * abs(sx):
            raise SVFError(f"DSM {dsm.pk} has non-square cells ({sx} x {sy}).")
        cell = abs(sx)
        c0 = max(int((minx - x0) // cell), 0)
        c1 = min(int(np.ceil((maxx - x0) / cell)), raster.width)
        r0 = max(int((y0 - maxy) // cell), 0)
        r1 = min(int(np.ceil((y0 - miny) / cell)), raster.height)
        if c1 <= c0 or r1 <= r0:
            raise SVFError("The view does not overlap the DSM.")
        band = raster.bands[0]
        data = band.data(offset=(c0, r0), size=(c1 - c0, r1 - r0)).astype(np.float32)
        if band.nodata_value is not None:
            data[data == np.float32(band.nodata_value)] = np.nan
        return data, (x0 + c0 * cell, y0 - r0 * cell), cell, srid

    if not dsm.cog_path:
        raise SVFError(f"DSM {dsm.pk} has neither a stored raster nor a COG.")

    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import from_origin
    from rasterio.vrt import WarpedVRT
    from rasterio.warp import transform_bounds

    cell = float(resolution or source_cell_size(dsm))
    if cell <= 0:
        raise SVFError(f"DSM {dsm.pk}: could not determine the cell size.")
    with rasterio.open(dsm.cog_path) as src:
        dst_crs = f"EPSG:{srid}"
        covered = _intersection(bbox, transform_bounds(src.crs, dst_crs, *src.bounds))
        if covered is None:
            raise SVFError("The view does not overlap the DSM.")
        minx, miny, maxx, maxy = covered
        # Snap to the cell size so repeated runs land on the same grid.
        minx, maxy = np.floor(minx / cell) * cell, np.ceil(maxy / cell) * cell
        width = int(np.ceil((maxx - minx) / cell))
        height = int(np.ceil((maxy - miny) / cell))
        transform = from_origin(minx, maxy, cell, cell)
        # Nearest keeps building edges sharp (the COG is nearest too). The VRT
        # only fetches the source tiles under this window.
        with WarpedVRT(src, crs=dst_crs, transform=transform, width=width,
                       height=height, resampling=Resampling.nearest) as vrt:
            data = vrt.read(1, masked=True).astype(np.float32).filled(np.nan)
    return data, (minx, maxy), cell, srid


def plan(view, *, dsm=None, radius_m=DEFAULT_RADIUS_M, resolution=None):
    """
    What a calculation over `view` (storage CRS) would read, without reading it.

    Returns a dict with the DSM, the covered view, the cell size, the radius in
    cells, the output size and the read window (view + one radius of halo, so
    cells at the view's edge see their real horizon). Raises SVFError when no
    DSM covers the view or the window exceeds MAX_CELLS.
    """
    import math

    if dsm is None:
        dsm, covered = dsm_for_view(view)
        if dsm is None:
            raise SVFError("No Digital Surface Model covers this view.")
    else:
        extent = dsm_extent(dsm)
        covered = _intersection(view, extent) if extent else None
        if covered is None:
            raise SVFError(f"DSM {dsm.pk} does not cover this view.")

    cell = float(resolution or source_cell_size(dsm))
    radius_pixels = max(int(round(radius_m / cell)), 2)
    halo = radius_pixels * cell
    window = (covered[0] - halo, covered[1] - halo, covered[2] + halo, covered[3] + halo)
    width = math.ceil((covered[2] - covered[0]) / cell)
    height = math.ceil((covered[3] - covered[1]) / cell)
    read_cells = math.ceil((window[2] - window[0]) / cell) * math.ceil((window[3] - window[1]) / cell)
    info = {
        "dsm": dsm, "covered": covered, "window": window, "cell": cell,
        "radius_pixels": radius_pixels, "radius_m": radius_pixels * cell,
        "width": width, "height": height, "read_cells": read_cells,
        "coverage": _area(covered) / _area(view),
    }
    if read_cells > MAX_CELLS:
        scale = math.sqrt(read_cells / MAX_CELLS)
        raise SVFError(
            f"This view needs {read_cells / 1e6:.0f} M cells at {cell:g} m (limit "
            f"{MAX_CELLS / 1e6:.0f} M): zoom in about {scale:.1f}x or use cells of "
            f"{cell * scale:.1f} m or more.")
    return info


def save_svf(svf, origin, cell, srid, dsm, radius_m, num_directions):
    import numpy as np
    from django.contrib.gis.gdal import GDALRaster

    from urban_heat.models import SkyViewFactor

    data = np.ascontiguousarray(np.where(np.isfinite(svf), svf, NODATA), dtype="float32")
    raster = GDALRaster({
        "srid": srid,
        "width": data.shape[1],
        "height": data.shape[0],
        "origin": origin,
        "scale": (cell, -cell),
        "datatype": 6,  # Float32
        "bands": [{"data": data, "nodata_value": NODATA}],
    })
    source = f"{SOURCE_PREFIX}{dsm.pk}: {dsm.source or 'unknown source'} {dsm.year}"
    return SkyViewFactor.objects.create(
        raster=raster,
        source=source[:100],
        measurement_method=f"{METHOD_LABEL}, {num_directions} dirs, r={radius_m:g} m"[:100],
        resolution=cell,
    )


def _svf_of_dsm(dsm):
    from urban_heat.models import SkyViewFactor

    return SkyViewFactor.objects.filter(source__startswith=f"{SOURCE_PREFIX}{dsm.pk}:")


def _storage_box(extent, pad=0.0):
    from django.contrib.gis.geos import Polygon

    box = Polygon.from_bbox((extent[0] - pad, extent[1] - pad, extent[2] + pad, extent[3] + pad))
    box.srid = _storage_srid()
    return box


def existing_svf(dsm, view, cell=0.0):
    """
    SVF rows of `dsm` whose extent contains `view` (storage CRS), newest first.
    `cell` is the tolerance: a stored grid is snapped to whole cells, so its
    edge can lie up to one cell inside the view it was computed for.
    """
    box = _storage_box(view, pad=-min(cell, (view[2] - view[0]) / 4, (view[3] - view[1]) / 4))
    return _svf_of_dsm(dsm).filter(raster__bbcontains=box).defer("raster").order_by("-pk")


def replace_covered(record, dsm, extent, cell):
    """
    Delete the other SVF rows of the same DSM that lie inside `extent` (a
    recalculation of that area), with their COG files. Returns their ids.
    """
    import os

    replaced = []
    inside = _svf_of_dsm(dsm).filter(raster__contained=_storage_box(extent, pad=cell / 2))
    for old in inside.exclude(pk=record.pk).defer("raster"):
        cog_path = old.cog_path
        replaced.append(old.pk)
        old.delete()
        if cog_path and os.path.exists(cog_path):
            try:
                os.unlink(cog_path)
            except OSError as e:
                logger.warning("Could not delete COG %s: %s", cog_path, e)
    return replaced


def calculate_svf(dsm=None, *, bbox=None, bbox_wgs84=None, radius_m=DEFAULT_RADIUS_M,
                  min_radius=1, num_directions=16, resolution=None):
    """
    Compute the sky-view factor over a view and store it.

    dsm:            a physicalEnv.DigitalSurfaceModel instance or pk; default:
                    the DSM covering most of the view.
    bbox:           the view as (minx, miny, maxx, maxy) in the storage CRS, or
    bbox_wgs84:     the view as (west, south, east, north) in degrees.
                    Without either, the whole DSM (subject to MAX_CELLS).
    radius_m:       horizon search distance in metres. Street canyons need
                    tens of metres (default DEFAULT_RADIUS_M).
    resolution:     cell size in metres when reading the DSM's COG (default:
                    the COG's own cell size).

    Only the view plus a halo of `radius_m` is read; the stored raster covers
    the view. A recalculation replaces earlier SVF rows of the same DSM that
    lie inside it.

    DAG edge: DSM -> SVF.
    """
    import numpy as np

    from .models import DigitalSurfaceModel

    if dsm is not None and not isinstance(dsm, DigitalSurfaceModel):
        dsm = DigitalSurfaceModel.objects.get(pk=dsm)
    if bbox is None and bbox_wgs84 is not None:
        bbox = wgs84_to_storage(bbox_wgs84)
    if bbox is None:
        if dsm is None:
            raise SVFError("Give a view (bbox) or a DSM.")
        bbox = dsm_extent(dsm)

    p = plan(bbox, dsm=dsm, radius_m=radius_m, resolution=resolution)
    dsm = p["dsm"]
    height, origin, cell, srid = load_dsm(dsm, p["window"], resolution=p["cell"])
    logger.info("SVF for DSM %s: read %s x %s cells of %g m, radius %g m, %s directions",
                dsm.pk, height.shape[1], height.shape[0], cell, p["radius_m"], num_directions)

    svf = sky_view_factor(height, cell, radius_pixels=p["radius_pixels"],
                          min_radius=min_radius, num_directions=num_directions)

    # Crop the halo off: keep the cells inside the covered view.
    cx0, _, _, cy1 = p["covered"]
    c0 = max(int(round((cx0 - origin[0]) / cell)), 0)
    r0 = max(int(round((origin[1] - cy1) / cell)), 0)
    svf = svf[r0:r0 + p["height"], c0:c0 + p["width"]]
    out_origin = (origin[0] + c0 * cell, origin[1] - r0 * cell)

    record = save_svf(svf, out_origin, cell, srid, dsm, p["radius_m"], num_directions)
    out_extent = (out_origin[0], out_origin[1] - svf.shape[0] * cell,
                  out_origin[0] + svf.shape[1] * cell, out_origin[1])
    replaced = replace_covered(record, dsm, out_extent, cell)

    valid = svf[np.isfinite(svf)]
    return SVFResult(
        record=record, dsm=dsm, replaced=replaced,
        width=svf.shape[1], height=svf.shape[0], cell=cell, radius_m=p["radius_m"],
        valid_fraction=float(valid.size / svf.size) if svf.size else 0.0,
        mean=float(valid.mean()) if valid.size else None,
        min=float(valid.min()) if valid.size else None,
        max=float(valid.max()) if valid.size else None,
    )
