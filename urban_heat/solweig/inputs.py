"""
CrossTwin layers -> the SOLWEIG input rasters of one view, on one grid.

    window   = the view + HALO_M on every side (shadows of buildings just
               outside the view still fall into it); cropped off afterwards
    DSM      = physicalEnv.DigitalSurfaceModel over the window, with the map
               editor's building changes applied (svf.load_dsm ->
               dsm_patches.apply_patches; DAG edge Buildings -> DSM)
    ground   = DEM on the same grid, else a minimum filter of the DSM
    Building_DSM = DSM inside builtup.Building footprints, ground elsewhere
    Trees        = DSM - ground outside buildings where above MIN_CANOPY_M
                   (AHN's DSM contains the vegetation), else 0
    Landcover    = latest-year LandCoverVector in SOLWEIG's classes
                   (1 paved, 2 buildings, 5 grass, 6 bare soil, 7 water;
                   solweig_gpu/landcoverclasses_2016a.txt), buildings burned last

All rasters are float32 GeoTIFFs in the storage CRS (projected, as SOLWEIG
needs), with no nodata: SOLWEIG has no nodata handling.
"""
import logging
import math
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

HALO_M = 50.0
DEFAULT_CELL_M = 1.0
# Read window (view + halo) in cells. SOLWEIG-GPU took ~1.2 ms per cell on an
# RTX 4050 (6 GB) with the SVF uncached, ~0.6 ms with it cached; the shadow
# matrices of 1 M cells take ~2 GB of GPU memory.
MAX_CELLS = 1_000_000
MS_PER_CELL = {"cuda": 1.2, "cpu": 12.0}
MIN_CANOPY_M = 2.5

PAVED, BUILDING, GRASS, BARE, WATER = 1, 2, 5, 6, 7
# Land-cover class name keywords (matched at word starts, physicalEnv/soil.py::_matches)
# -> SOLWEIG class; anything else is paved.
LANDCOVER_KEYWORDS = (
    (WATER, ("water", "sea", "lagoon", "estuar", "marsh", "bog", "lake", "river", "canal")),
    (GRASS, ("pasture", "forest", "grass", "green", "sport", "leisure", "agricult", "arable", "crop",
             "vineyard", "orchard", "heath", "shrub", "meadow", "park", "vegetat", "wood", "natural")),
    (BARE, ("bare", "beach", "dune", "sand", "rock", "burnt", "construction", "dump", "mine")),
)


class SolweigError(ValueError):
    """An expected failure the map tool shows as-is (no DSM, view too large...)."""


def umep_class(land_cover_type):
    from physicalEnv.soil import _matches

    name = (land_cover_type or "").lower()
    for code, keywords in LANDCOVER_KEYWORDS:
        if _matches(name, keywords):
            return code
    return PAVED


def plan(view, cell=None):
    """
    What a run over `view` (storage CRS) would read: the DSM, the covered view,
    the window with its halo, the cell size and the cell count. Raises
    SolweigError without a DSM or above MAX_CELLS.
    """
    from physicalEnv import svf

    cell = float(cell or DEFAULT_CELL_M)
    try:
        p = svf.plan(view, radius_m=HALO_M, resolution=cell)
    except svf.SVFError as e:
        raise SolweigError(str(e)) from None
    if p["read_cells"] > MAX_CELLS:
        scale = math.sqrt(p["read_cells"] / MAX_CELLS)
        raise SolweigError(
            f"This view needs {p['read_cells'] / 1e6:.1f} M cells at {cell:g} m with its {HALO_M:g} m "
            f"halo (limit {MAX_CELLS / 1e6:g} M): zoom in about {scale:.1f}x or use {cell * scale:.1f} m cells.")
    return p


@dataclass
class Inputs:
    origin: tuple
    cell: float
    shape: tuple
    srid: int
    crop: tuple  # (row0, col0, rows, cols) of the view inside the window
    key: str  # hash of the arrays that the SVF depends on (work-dir name)
    labels: dict = field(default_factory=dict)
    arrays: dict = field(default_factory=dict)

    @property
    def view_origin(self):
        r0, c0, _, _ = self.crop
        return self.origin[0] + c0 * self.cell, self.origin[1] - r0 * self.cell


def _footprints(origin, cell, shape):
    from builtup.models import Building
    from physicalEnv.dsm_patches import _box

    return list(Building.objects.filter(geom__bboverlaps=_box(origin, cell, shape))
                .values_list("geom", flat=True))


def landcover_grid(origin, cell, shape, buildings):
    """SOLWEIG land-cover classes on the grid, or None without land-cover polygons."""
    import json

    import numpy as np
    from django.db.models import Max
    from rasterio.features import rasterize
    from rasterio.transform import from_origin

    from physicalEnv.dsm_patches import _box
    from physicalEnv.models import LandCoverVector

    box = _box(origin, cell, shape)
    polygons = LandCoverVector.objects.filter(geom__bboverlaps=box)
    year = polygons.aggregate(y=Max("year"))["y"]
    if year is None:
        return None
    shapes = [(json.loads(geom.json), umep_class(name)) for geom, name in
              polygons.filter(year=year).values_list("geom", "land_cover_type__class_name")]
    grid = rasterize(shapes, out_shape=shape, transform=from_origin(origin[0], origin[1], cell, cell),
                     fill=PAVED, dtype="float32")
    grid[buildings] = BUILDING
    return grid


def build(p):
    """
    The input arrays of plan `p` (see the module docstring). Returns Inputs
    with arrays Building_DSM, DEM, Trees and (when there is land cover)
    Landcover, all on the window grid.
    """
    import hashlib

    import numpy as np

    from physicalEnv import dsm_patches, svf

    height, origin, cell, srid = svf.load_dsm(p["dsm"], p["window"], resolution=p["cell"])
    ground, ground_label = dsm_patches.ground_grid(height, origin, cell, srid)
    fallback = float(np.nanmedian(ground)) if np.isfinite(ground).any() else 0.0
    ground = np.where(np.isfinite(ground), ground, fallback).astype(np.float32)
    height = np.where(np.isfinite(height), height, ground).astype(np.float32)

    buildings = dsm_patches.burn(_footprints(origin, cell, height.shape), origin, cell, height.shape)
    building_dsm = np.where(buildings, np.maximum(height, ground), ground).astype(np.float32)
    canopy = height - ground
    trees = np.where(~buildings & (canopy > MIN_CANOPY_M), canopy, 0.0).astype(np.float32)
    arrays = {"Building_DSM": building_dsm, "DEM": ground, "Trees": trees}
    landcover = landcover_grid(origin, cell, height.shape, buildings)
    if landcover is not None:
        arrays["Landcover"] = landcover

    cx0, _, _, cy1 = p["covered"]
    c0 = max(int(round((cx0 - origin[0]) / cell)), 0)
    r0 = max(int(round((origin[1] - cy1) / cell)), 0)
    crop = (r0, c0, min(p["height"], height.shape[0] - r0), min(p["width"], height.shape[1] - c0))

    digest = hashlib.sha1()
    for name in ("Building_DSM", "DEM", "Trees"):
        digest.update(arrays[name].tobytes())
    digest.update(repr((origin, cell, height.shape)).encode())
    labels = {
        "dsm": p["dsm"].pk,
        "ground": ground_label,
        "buildings": int(buildings.sum()),
        "landcover": landcover is not None,
    }
    return Inputs(origin=origin, cell=cell, shape=height.shape, srid=srid, crop=crop,
                  key=digest.hexdigest()[:16], labels=labels, arrays=arrays)


def write_tiles(inputs, preprocess_dir):
    """
    Write the arrays as SOLWEIG's single tile 0_0 (<dir>/<Name>/<Name>_0_0.tif).
    solweig_gpu.preprocess() would do the tiling, but it calls exit(1) on bad
    input, which would end the Django process.
    """
    import os

    import rasterio
    from rasterio.transform import from_origin

    transform = from_origin(inputs.origin[0], inputs.origin[1], inputs.cell, inputs.cell)
    for name, array in inputs.arrays.items():
        folder = os.path.join(preprocess_dir, name)
        os.makedirs(folder, exist_ok=True)
        with rasterio.open(os.path.join(folder, f"{name}_0_0.tif"), "w", driver="GTiff",
                           width=array.shape[1], height=array.shape[0], count=1, dtype="float32",
                           crs=f"EPSG:{inputs.srid}", transform=transform) as dst:
            dst.write(array, 1)
