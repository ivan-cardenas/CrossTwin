"""
Block-averaged raster grids for the map's 3D view (deck.gl columns).

A raster is read at its native resolution inside a window, cut into square
containers of ``block`` x ``block`` cells, and each container's mean (nodata
cells skipped) becomes one column whose height encodes the value.

Deterministic and pure apart from the file read: the window is aligned to
multiples of ``block`` in the raster's own pixel grid, so the same container
size always gives the same containers, however the view is panned.
"""
import math

# Hard limits (the response is JSON the browser draws as columns).
MAX_BLOCKS = 60_000          # columns per response
MAX_READ_CELLS = 64_000_000  # native cells read per request
MAX_BLOCK_CELLS = 200        # container side, in cells
M_PER_DEG = 111_320.0        # metres per degree of latitude (spherical approximation)


class BlockGridError(ValueError):
    """The request cannot be served (too large, no overlap); the message is user-facing."""


def block_mean(values, valid, block):
    """
    Mean of ``values`` over ``block`` x ``block`` containers, ignoring cells
    where ``valid`` is False. Returns (means, counts), both shaped
    (ceil(h / block), ceil(w / block)); a container with no valid cell has
    count 0 and mean NaN. Edge containers are partial.
    """
    import numpy as np

    h, w = values.shape
    rows, cols = -(-h // block), -(-w // block)
    pad = ((0, rows * block - h), (0, cols * block - w))
    data = np.pad(np.where(valid, values, 0.0).astype("float64"), pad)
    ok = np.pad(valid.astype("float64"), pad)
    sums = data.reshape(rows, block, cols, block).sum(axis=(1, 3))
    counts = ok.reshape(rows, block, cols, block).sum(axis=(1, 3))
    with np.errstate(invalid="ignore", divide="ignore"):
        means = np.where(counts > 0, sums / counts, np.nan)
    return means, counts


def ground_cell_size_m(crs, pixel_size, block, lat):
    """Ground side (metres) of one container: ``block`` cells of ``pixel_size`` CRS units."""
    side = block * abs(pixel_size)
    if crs.is_geographic:
        return side * M_PER_DEG * math.cos(math.radians(lat))
    if crs.to_epsg() == 3857:   # Web Mercator metres grow by 1/cos(lat) away from the equator
        return side * math.cos(math.radians(lat))
    return side * (crs.linear_units_factor[1] if crs.linear_units_factor else 1.0)


def raster_blocks(cog_path, block, bbox_wgs84=None):
    """
    Block means of band 1 of a COG.

    Returns {"lng": [...], "lat": [...], "value": [...], "cell_size_m", "block",
    "min", "max", "cells_per_block", "native_cell_m"} with one entry per container
    that holds at least one valid cell; ``bbox_wgs84`` = (west, south, east, north)
    limits the window (the whole raster when None). Raises BlockGridError.
    """
    import numpy as np
    import rasterio
    from rasterio.warp import transform, transform_bounds
    from rasterio.windows import Window, from_bounds

    block = int(block)
    if not 1 <= block <= MAX_BLOCK_CELLS:
        raise BlockGridError(f"Container size must be between 1 and {MAX_BLOCK_CELLS} cells.")

    with rasterio.open(cog_path) as src:
        full = Window(0, 0, src.width, src.height)
        if bbox_wgs84:
            bounds = transform_bounds("EPSG:4326", src.crs, *bbox_wgs84)
            win = from_bounds(*bounds, transform=src.transform)
            col0, row0 = math.floor(win.col_off), math.floor(win.row_off)
            col1, row1 = math.ceil(win.col_off + win.width), math.ceil(win.row_off + win.height)
        else:
            col0, row0, col1, row1 = 0, 0, src.width, src.height
        # Align to the block grid of the raster, then clip to the raster.
        col0, row0 = max(0, col0 // block * block), max(0, row0 // block * block)
        col1, row1 = min(src.width, col1), min(src.height, row1)
        if col1 <= col0 or row1 <= row0:
            raise BlockGridError("The raster does not cover this view.")
        window = Window(col0, row0, col1 - col0, row1 - row0).intersection(full)

        n_blocks = -(-int(window.height) // block) * -(-int(window.width) // block)
        if window.width * window.height > MAX_READ_CELLS or n_blocks > MAX_BLOCKS:
            raise BlockGridError(
                "Too many cells for this container size. Zoom in or increase the container size.")

        data = src.read(1, window=window, masked=True)
        values = np.ma.filled(data.astype("float64"), np.nan)
        valid = ~np.ma.getmaskarray(data) & np.isfinite(values)
        means, counts = block_mean(np.nan_to_num(values), valid, block)

        rows, cols = np.nonzero(counts > 0)
        # Container centre: middle of its (possibly partial) extent, in raster CRS.
        h_px, w_px = values.shape
        c_lo, c_hi = cols * block, np.minimum((cols + 1) * block, w_px)
        r_lo, r_hi = rows * block, np.minimum((rows + 1) * block, h_px)
        px = col0 + (c_lo + c_hi) / 2.0
        py = row0 + (r_lo + r_hi) / 2.0
        t = src.transform
        xs = t.c + px * t.a + py * t.b
        ys = t.f + px * t.d + py * t.e
        lngs, lats = transform(src.crs, "EPSG:4326", xs.tolist(), ys.tolist())
        mid_lat = float(np.mean(lats)) if len(lats) else 0.0
        picked = means[rows, cols]
        return {
            "lng": [round(v, 6) for v in lngs],
            "lat": [round(v, 6) for v in lats],
            "value": [round(float(v), 4) for v in picked],
            "min": float(picked.min()) if picked.size else None,
            "max": float(picked.max()) if picked.size else None,
            "block": block,
            "cell_size_m": ground_cell_size_m(src.crs, t.a, block, mid_lat),
            "native_cell_m": ground_cell_size_m(src.crs, t.a, 1, mid_lat),
        }
