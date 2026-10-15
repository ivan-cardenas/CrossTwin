"""
Google Earth Engine side of the LST calculation: find a Landsat scene and
download its inputs on a CrossTwin grid.

Earth Engine only *serves data* here; no LST equation runs on its servers.
One multi-band GeoTIFF is downloaded per scene, with every band on the target
grid (EPSG:28992, cells snapped to the CrossTwin NDVI layer's extent):

    B10         TIRS band 10 TOA brightness temperature, K   (LANDSAT/LC09/C02/T1_TOA)
    QA_PIXEL    Collection 2 Level-2 pixel quality bits       (LANDSAT/LC09/C02/T1_L2)
    EM13, EM14  ASTER GED emissivity, bands 13/14, 0-1        (NASA/ASTER_GED/AG100_003)
    ASTER_NDVI  ASTER GED mean NDVI, -1..1
    TPW_1/2     precipitable water of the two fields closest  (TPW_SOURCES)
                in time to the scene, mm

Selecting TOA thermal + Level-2 QA from the same `system:index` is what
Landsat_LST.js does with `combine()` on the two collections.

Authentication reuses the importer's GEEAuthManager (GEE_PROJECT_ID in .env).
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .coefficients import TPW_MISSING

logger = logging.getLogger(__name__)

COLLECTIONS = {
    "L8": {"toa": "LANDSAT/LC08/C02/T1_TOA", "sr": "LANDSAT/LC08/C02/T1_L2"},
    "L9": {"toa": "LANDSAT/LC09/C02/T1_TOA", "sr": "LANDSAT/LC09/C02/T1_L2"},
}
ASTER_GED = "NASA/ASTER_GED/AG100_003"


@dataclass(frozen=True)
class TpwSource:
    name: str
    asset: str
    band: str      # total precipitable water / column water vapour, kg/m² = mm
    step_ms: int   # time between fields


# Tried in order; the first with a field on the scene's UTC day is used.
# NCEP is what Ermida et al.'s code uses, so results up to its end match the
# published script. NCEP stopped updating on 2026-03-18 ("NCEP discontinued
# this dataset in March 2026"); ERA5 hourly covers later scenes (it runs
# ~5 days behind real time). Over Enschede the two differ by ~1-4 mm, mostly
# within one 6 mm SMW coefficient bin.
TPW_SOURCES = (
    TpwSource("NCEP", "NCEP_RE/surface_wv", "pr_wtr", 6 * 3600 * 1000),
    TpwSource("ERA5", "ECMWF/ERA5/HOURLY", "total_column_water_vapour", 3600 * 1000),
)

TIR_BAND = "B10"
# Sentinel written into masked pixels before download, turned into NaN after.
DOWNLOAD_NODATA = -9999.0
# getDownloadURL refuses requests above ~48 MB.
MAX_DOWNLOAD_BYTES = 48 * 1024 * 1024
DOWNLOAD_TIMEOUT = 300


class GEEError(RuntimeError):
    pass


@dataclass(frozen=True)
class Scene:
    scene_id: str        # system:index, e.g. LC09_197024_20240712
    acquired: datetime   # UTC
    cloud_cover: float   # scene-level CLOUD_COVER, %
    # Over the searched area only (find_scenes): share of it the scene covers,
    # and share of the covered part flagged cloud/cloud shadow. None if unknown.
    view_coverage: float = None
    view_cloud: float = None

    @property
    def time_ms(self):
        return int(self.acquired.timestamp() * 1000)

    @property
    def view_clear(self):
        """Share of the area with a clear pixel, None if not computed."""
        if self.view_coverage is None or self.view_cloud is None:
            return None
        return self.view_coverage * (1 - self.view_cloud)


# B10, QA_PIXEL, EM13, EM14, ASTER_NDVI and two NCEP fields.
DOWNLOAD_BANDS = 7


def download_bytes(grid, n_bands=DOWNLOAD_BANDS):
    return grid.width * grid.height * n_bands * 4


def check_download_size(grid, n_bands=DOWNLOAD_BANDS):
    size = download_bytes(grid, n_bands)
    if size > MAX_DOWNLOAD_BYTES:
        raise GEEError(
            f"The area is {grid.width}x{grid.height} cells at {grid.resolution:g} m "
            f"({size / 2**20:.0f} MB; Earth Engine allows ~48 MB). Zoom in or use a coarser resolution."
        )


def initialize():
    """Authenticate once per process, like the importer's GEE sources."""
    from django.conf import settings
    from importer.external_data import GEEAuthManager

    if GEEAuthManager.is_initialized():
        return
    ok, msg = GEEAuthManager.initialize(getattr(settings, "GEE_PROJECT_ID", None))
    if not ok:
        raise GEEError(msg)


def _collections(sensor):
    try:
        return COLLECTIONS[sensor]
    except KeyError:
        raise GEEError(f"Unknown sensor {sensor!r}; expected one of {sorted(COLLECTIONS)}") from None


def _to_utc(millis):
    return datetime.fromtimestamp(millis / 1000, tz=timezone.utc)


# Cell size of the per-scene cloud statistics over the area: coarse is enough
# for ranking scenes and keeps the one getInfo() fast.
VIEW_STATS_SCALE_M = 120


def find_scenes(sensor, date_from, date_to, bbox_wgs84, max_cloud=None):
    """
    Level-2 scenes over the bbox in [date_from, date_to), clearest first.

    CLOUD_COVER is for the whole 185 km scene, so each scene also gets its
    coverage of the bbox and its cloud/shadow share there (QA bits 3/4, the
    same bits the LST mask uses), all in one getInfo(). Scenes are ranked by
    the share of the bbox that would get an LST value.
    """
    import ee

    region = ee.Geometry.Rectangle(bbox_wgs84)
    col = ee.ImageCollection(_collections(sensor)["sr"]).filterDate(date_from, date_to).filterBounds(region)
    if max_cloud is not None:
        col = col.filter(ee.Filter.lte("CLOUD_COVER", max_cloud))

    def view_stats(img):
        qa = img.select("QA_PIXEL")
        cloud = qa.bitwiseAnd(1 << 3).Or(qa.bitwiseAnd(1 << 4)).neq(0).rename("cloud")
        # 1 inside the scene footprint, 0 outside (where QA is masked).
        cover = ee.Image.constant(1).updateMask(qa.mask()).unmask(0).rename("cover")
        stats = cloud.addBands(cover).reduceRegion(
            reducer=ee.Reducer.mean(), geometry=region, scale=VIEW_STATS_SCALE_M,
            maxPixels=1e8, bestEffort=True,
        )
        return ee.Feature(None, {
            "id": img.get("system:index"),
            "time": img.get("system:time_start"),
            "cloud_cover": img.get("CLOUD_COVER"),
            "view_cloud": stats.get("cloud"),
            "view_coverage": stats.get("cover"),
        })

    features = ee.FeatureCollection(col.map(view_stats)).getInfo()["features"]
    scenes = []
    for f in features:
        p = f["properties"]
        scenes.append(Scene(
            p["id"], _to_utc(p["time"]), float(p["cloud_cover"]),
            view_coverage=p.get("view_coverage"), view_cloud=p.get("view_cloud"),
        ))
    return sorted(scenes, key=lambda s: (-(s.view_clear or 0), s.cloud_cover, s.acquired))


def get_scene(sensor, scene_id):
    import ee

    img = ee.Image(f"{_collections(sensor)['sr']}/{scene_id}")
    try:
        info = ee.Dictionary({
            "time": img.get("system:time_start"),
            "cloud": img.get("CLOUD_COVER"),
        }).getInfo()
    except Exception as e:
        raise GEEError(f"Scene {scene_id} not found in {_collections(sensor)['sr']}: {e}") from e
    return Scene(scene_id, _to_utc(info["time"]), float(info["cloud"]))


def water_vapour_fields(scene):
    """
    (source, [(image, |dt| ms), ...]): the (up to) two fields of the scene's
    UTC day closest to it in time, from the first TPW_SOURCES entry that has
    any that day   (NCEP_TPW.js, with a fallback source).
    Raises GEEError when no source covers the day.
    """
    import ee

    day = scene.acquired.replace(hour=0, minute=0, second=0, microsecond=0)
    start, end = day.strftime("%Y-%m-%d"), (day + timedelta(days=1)).strftime("%Y-%m-%d")
    for source in TPW_SOURCES:
        col = ee.ImageCollection(source.asset).filterDate(start, end)
        info = ee.Dictionary({
            "ids": col.aggregate_array("system:index"),
            "times": col.aggregate_array("system:time_start"),
        }).getInfo()
        closest = sorted((abs(t - scene.time_ms), i) for i, t in zip(info["ids"], info["times"]))[:2]
        if closest:
            return source, [(ee.Image(f"{source.asset}/{i}").select(source.band), dist) for dist, i in closest]
    names = " or ".join(s.name for s in TPW_SOURCES)
    raise GEEError(
        f"No water-vapour data ({names}) for {scene.acquired:%Y-%m-%d} yet, so the LST cannot be "
        f"computed for scene {scene.scene_id}. NCEP ended in March 2026 and ERA5 runs about 5 days "
        f"behind: pick an older scene or try again in a few days."
    )


def fetch_scene_inputs(sensor, scene, grid):
    """
    Download the scene's inputs on `grid`.

    Returns (bands, tpw_fields, tpw_source): `bands` maps B10, QA_PIXEL,
    EM13, EM14, ASTER_NDVI to float64 arrays (NaN = masked); `tpw_fields` is
    the list of (array, |dt| ms) that smw.interpolate_tpw expects, from the
    TpwSource `tpw_source` (pass its step_ms along).
    """
    import ee
    import numpy as np
    import requests
    from rasterio.io import MemoryFile

    names = _collections(sensor)
    toa = ee.Image(f"{names['toa']}/{scene.scene_id}")
    sr = ee.Image(f"{names['sr']}/{scene.scene_id}")
    aster = ee.Image(ASTER_GED)

    # Continuous fields are resampled bilinearly when Earth Engine warps them
    # to RD New; the QA bits must stay nearest-neighbour.
    stack = ee.Image.cat([
        toa.select(TIR_BAND).resample("bilinear").rename("B10"),
        sr.select("QA_PIXEL").rename("QA_PIXEL"),
        aster.select("emissivity_band13").multiply(0.001).resample("bilinear").rename("EM13"),
        aster.select("emissivity_band14").multiply(0.001).resample("bilinear").rename("EM14"),
        aster.select("ndvi").multiply(0.01).resample("bilinear").rename("ASTER_NDVI"),
    ])
    tpw_source, tpw_images = water_vapour_fields(scene)
    for n, (img, _dist) in enumerate(tpw_images, start=1):
        stack = stack.addBands(img.rename(f"TPW_{n}"))
    logger.info("LST: water vapour from %s for %s", tpw_source.name, scene.scene_id)

    band_names = ["B10", "QA_PIXEL", "EM13", "EM14", "ASTER_NDVI"] + [f"TPW_{n}" for n in range(1, len(tpw_images) + 1)]
    check_download_size(grid, len(band_names))

    url = stack.toFloat().unmask(DOWNLOAD_NODATA).getDownloadURL({
        "name": scene.scene_id,
        "crs": f"EPSG:{grid.srid}",
        "crs_transform": grid.ee_crs_transform,
        "dimensions": f"{grid.width}x{grid.height}",
        "format": "GEO_TIFF",
    })
    response = requests.get(url, timeout=DOWNLOAD_TIMEOUT)
    response.raise_for_status()

    with MemoryFile(response.content) as mem, mem.open() as src:
        if (src.width, src.height) != (grid.width, grid.height):
            raise GEEError(f"Earth Engine returned {src.width}x{src.height}, expected {grid.width}x{grid.height}.")
        descriptions = list(src.descriptions)
        order = descriptions if all(descriptions) else band_names
        arrays = {}
        for index, name in enumerate(order, start=1):
            data = src.read(index).astype("float64")
            data[data == DOWNLOAD_NODATA] = np.nan
            arrays[name] = data

    tpw_fields = [(arrays.pop(f"TPW_{n}"), dist) for n, (_img, dist) in enumerate(tpw_images, start=1)]
    # A masked water-vapour cell is "no data", like a missing field: SMW masks TPW < 0.
    tpw_fields = [(np.where(np.isnan(a), TPW_MISSING, a), d) for a, d in tpw_fields]
    return arrays, tpw_fields, tpw_source
