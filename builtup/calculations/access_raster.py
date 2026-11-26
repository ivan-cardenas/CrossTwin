"""
Accessibility as a raster (map view of builtup.Accessibility): a smooth 0-100 surface from the stored
building scores, one builtup.AccessibilityRaster row per mode. Display only: no DAG edge reads it.

Per cell the mean score of the buildings inside it is taken, then spread with a Gaussian kernel
(normalised convolution: sum(score) / sum(count) after smoothing both), so empty cells between
buildings take the score of their surroundings and one building does not make a single square.
Cells further than MASK_M from any scored building stay empty (no value is invented over fields
or water). Deterministic: no random numbers, grid aligned to multiples of the cell size.

The COG is written by the post_save receiver of core/signals.py when the row is saved.
numpy / scipy are imported inside the functions.
"""
import logging
import math

from builtup.calculations import chain

logger = logging.getLogger(__name__)

CELL_M = 10.0            # raster cell (display choice; about one building width)
SIGMA_M = 50.0           # Gaussian smoothing radius (1 sigma)
MASK_M = 75.0            # cells further than this from a scored building stay empty
MAX_CELLS = 40_000_000   # a larger extent gets a coarser cell instead of exhausting memory
NODATA = -9999.0
INDEX = {"walk": "ACCESS_WALK", "bike": "ACCESS_BIKE"}   # AccessibilityRaster.index; style in mainMap/styles/rasterStyles.py


def smooth_grid(x, y, score, cell=CELL_M, sigma=SIGMA_M, mask=MASK_M):
    """
    (data, origin_x, origin_y, cell) of the smoothed score surface: float32 array (row 0 = north),
    NODATA where empty, and the north-west corner of the grid. x, y, score: equal-length sequences.
    The cell grows (by whole multiples) when the extent would exceed MAX_CELLS.
    """
    import numpy as np
    from scipy import ndimage

    x, y, score = (np.asarray(v, dtype="float64") for v in (x, y, score))
    pad = mask + 3 * sigma
    span_x, span_y = float(x.max() - x.min()) + 2 * pad, float(y.max() - y.min()) + 2 * pad
    cell = float(cell)
    if span_x * span_y / cell ** 2 > MAX_CELLS:
        cell *= math.ceil(math.sqrt(span_x * span_y / cell ** 2 / MAX_CELLS))
    x0 = math.floor((x.min() - pad) / cell) * cell
    y1 = math.ceil((y.max() + pad) / cell) * cell
    width = int(math.ceil((x.max() + pad - x0) / cell))
    height = int(math.ceil((y1 - (y.min() - pad)) / cell))
    col = np.clip(((x - x0) // cell).astype(int), 0, width - 1)
    row = np.clip(((y1 - y) // cell).astype(int), 0, height - 1)
    sums = np.zeros((height, width))
    counts = np.zeros((height, width))
    np.add.at(sums, (row, col), score)
    np.add.at(counts, (row, col), 1.0)
    s_cells = sigma / cell
    weight = ndimage.gaussian_filter(counts, s_cells, truncate=3.0)
    value = ndimage.gaussian_filter(sums, s_cells, truncate=3.0)
    near = ndimage.distance_transform_edt(counts == 0) * cell <= mask
    data = np.full((height, width), NODATA, dtype="float32")
    ok = near & (weight > 1e-9)
    data[ok] = np.clip(value[ok] / weight[ok], 0.0, 100.0)
    return data, x0, y1, cell


def _points(mode):
    import numpy as np
    from django.db import connection

    from builtup.models import Accessibility

    with connection.cursor() as cursor:
        cursor.execute(f"SELECT ST_X(geom), ST_Y(geom), score FROM {Accessibility._meta.db_table} WHERE mode = %s", [mode])
        rows = cursor.fetchall()
    return np.array(rows, dtype="float64").reshape(-1, 3)


def rebuild(modes=chain.MODES):
    """
    Rebuild builtup.AccessibilityRaster for `modes` from the stored building scores. The row of a mode is
    updated in place, so its layer key stays; saving it re-exports the COG. A mode without scores loses its
    row. Returns {mode: raster id or None}.
    """
    from django.conf import settings
    from django.contrib.gis.gdal import GDALRaster
    from django.utils import timezone

    from builtup.models import AccessibilityRaster

    result = {}
    for mode in modes:
        points = _points(mode)
        row = AccessibilityRaster.objects.filter(index=INDEX[mode]).order_by("pk").first()
        if not len(points):
            if row is not None:
                row.delete()
            result[mode] = None
            continue
        data, x0, y1, cell = smooth_grid(points[:, 0], points[:, 1], points[:, 2])
        raster = GDALRaster({
            "srid": int(settings.COORDINATE_SYSTEM), "width": data.shape[1], "height": data.shape[0],
            "origin": (x0, y1), "scale": (cell, -cell), "datatype": 6,
            "bands": [{"data": data, "nodata_value": NODATA}],
        })
        row = row or AccessibilityRaster(index=INDEX[mode])
        row.raster = raster
        row.date_time = timezone.now()
        row.source = f"CrossTwin network accessibility ({chain.METHOD_STAMP})"[:100]
        row.measurement_method = (f"mean building score per {cell:g} m cell, Gaussian sigma {SIGMA_M:g} m, "
                                  f"masked beyond {MASK_M:g} m")[:100]
        row.resolution = cell
        row.save()
        result[mode] = row.pk
    return result
