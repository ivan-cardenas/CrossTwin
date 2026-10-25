"""
LST from Landsat 9 + CrossTwin's NDVI layer, stored as a LandSurfaceTemperature raster.

Flow (Landsat_LST.js, with CrossTwin's NDVI in place of the Landsat NDVI):

    NDVI layers (physicalEnv.LandCoverRaster, index "NDVI", Sentinel-2 10 m)
        -> grid: the map view clipped to the NDVI coverage (or one layer's
           extent), snapped to `resolution` (30 m = Landsat), EPSG:28992
        -> NDVI averaged onto the grid; several layers are merged newest first
    Earth Engine (gee.py): Landsat B10 + QA, ASTER GED, NCEP TPW on the same grid
        -> smw.land_surface_temperature()
        -> LandSurfaceTemperature row (°C, nodata -9999); its post_save exports the COG

Recalculating with the same scene replaces the earlier LST rows of that scene
whose extent the new grid fully covers; partly overlapping ones are kept.

DAG edges: RS_Imagery -> LST, LandCover -> LST. LST is computed on demand
(the map's LST tool, or `manage.py calculate_lst`), not by a receiver: a new
NDVI row must not start an Earth Engine download from a post_save.
"""
import logging
import os
from dataclasses import dataclass, field
from datetime import date, timedelta

from .gee import Scene
from .grid import Grid

logger = logging.getLogger(__name__)

NODATA = -9999.0
# NDVI and Landsat scene should show the same vegetation state.
DEFAULT_WINDOW_DAYS = 30
SENSOR_LABELS = {"L8": "Landsat 8", "L9": "Landsat 9"}
METHOD_LABEL = "Statistical Mono-Window (Ermida et al. 2020)"
SOURCE_PREFIX = "GEE "


class LSTError(RuntimeError):
    pass


@dataclass
class LSTResult:
    scene: Scene
    grid: Grid
    ndvi_layers: list     # LandCoverRaster rows used (grid source, and FVC unless use_ndvi=False)
    lst_c: object         # 2-D float array, NaN = masked
    valid_fraction: float
    record: object = None  # the saved LandSurfaceTemperature, None for a dry run
    replaced: list = field(default_factory=list)  # ids of the LST rows it replaced
    tpw_source: str = None  # water-vapour dataset used (NCEP, or ERA5 after March 2026)

    def stats(self):
        import numpy as np

        valid = self.lst_c[np.isfinite(self.lst_c)]
        return {
            "min": float(valid.min()),
            "mean": float(valid.mean()),
            "max": float(valid.max()),
        }


def _ndvi_queryset():
    from django.db.models import F
    from physicalEnv.models import LandCoverRaster

    return LandCoverRaster.objects.filter(index__iexact="NDVI", raster__isnull=False).order_by(
        F("date").desc(nulls_last=True), "-year", "-id"
    )


def ndvi_layer(city=None, ndvi_id=None):
    """The NDVI raster to use: by id, else the most recent one of the city (or any city)."""
    qs = _ndvi_queryset()
    if ndvi_id is not None:
        record = qs.filter(pk=ndvi_id).first()
        if record is None:
            raise LSTError(f"No NDVI LandCoverRaster with id {ndvi_id}.")
        return record
    if city is not None:
        qs = qs.filter(city=city)
    record = qs.first()
    if record is None:
        where = f" for {city}" if city is not None else ""
        raise LSTError(
            f"No NDVI layer{where}. Import 'NDVI (Vegetation Index)' from Retrieve Data from APIs first."
        )
    return record


def _view_polygon(bbox_wgs84):
    """The [west, south, east, north] WGS84 box as a polygon in the storage CRS."""
    from django.conf import settings
    from django.contrib.gis.geos import Polygon

    poly = Polygon.from_bbox(tuple(float(v) for v in bbox_wgs84))
    poly.srid = 4326
    poly.transform(settings.COORDINATE_SYSTEM)
    return poly


def ndvi_layers_in(bbox_wgs84):
    """NDVI layers overlapping the view, newest first."""
    layers = list(_ndvi_queryset().filter(raster__bboverlaps=_view_polygon(bbox_wgs84)))
    if not layers:
        raise LSTError(
            "No NDVI layer in this view. Import 'NDVI (Vegetation Index)' for this area "
            "from Retrieve Data from APIs first."
        )
    return layers


def grid_for(raster, resolution):
    return Grid.covering(raster.srs.srid, *raster.extent, resolution)


def view_grid(bbox_wgs84, layers, resolution):
    """Grid over the part of the view the NDVI layers cover (LST is empty elsewhere)."""
    from django.contrib.gis.geos import Polygon

    view = _view_polygon(bbox_wgs84)
    coverage = None
    for layer in layers:
        extent = Polygon.from_bbox(layer.raster.extent)
        extent.srid = layer.raster.srs.srid
        coverage = extent if coverage is None else coverage.union(extent)
    area = view.intersection(coverage)
    if area.empty:
        raise LSTError("The NDVI layers do not cover this view.")
    return Grid.covering(view.srid, *area.extent, resolution)


def resample_to_grid(raster, grid):
    """Band 1 of a GDALRaster averaged onto `grid` (NaN outside it / at nodata)."""
    import numpy as np
    from affine import Affine
    from rasterio.warp import Resampling, reproject

    band = raster.bands[0]
    src = np.asarray(band.data(), dtype="float64").reshape(raster.height, raster.width)
    if band.nodata_value is not None:
        src[src == band.nodata_value] = np.nan
    dst = np.full((grid.height, grid.width), np.nan)
    reproject(
        source=src,
        destination=dst,
        src_transform=Affine.from_gdal(*raster.geotransform),
        src_crs=f"EPSG:{raster.srs.srid}",
        src_nodata=np.nan,
        dst_transform=Affine.from_gdal(*grid.gdal_transform),
        dst_crs=f"EPSG:{grid.srid}",
        dst_nodata=np.nan,
        resampling=Resampling.average,
    )
    return dst


def ndvi_mosaic(layers, grid):
    """NDVI on the grid; where layers overlap, the first (newest) one wins."""
    import numpy as np

    mosaic = np.full((grid.height, grid.width), np.nan)
    for layer in layers:
        values = resample_to_grid(layer.raster, grid)
        gap = np.isnan(mosaic)
        mosaic[gap] = values[gap]
        if not np.isnan(mosaic).any():
            break
    return mosaic


def default_window(ndvi):
    """[from, to) around the NDVI acquisition; summer of its year when it has no date."""
    if ndvi.date:
        day = ndvi.date.date()
        return day - timedelta(days=DEFAULT_WINDOW_DAYS), day + timedelta(days=DEFAULT_WINDOW_DAYS + 1)
    return date(ndvi.year, 6, 1), date(ndvi.year, 9, 1)


def _source_label(scene, layers):
    ids = ",".join(str(layer.pk) for layer in layers[:6]) + ("…" if len(layers) > 6 else "")
    return f"{SOURCE_PREFIX}{scene.scene_id} + NDVI #{ids}"[:100]


def save_lst(lst_c, grid, scene, layers, sensor, tpw_source=None):
    import numpy as np
    from django.contrib.gis.gdal import GDALRaster

    from urban_heat.models import LandSurfaceTemperature

    data = np.ascontiguousarray(np.where(np.isfinite(lst_c), lst_c, NODATA), dtype="float32")
    raster = GDALRaster({
        "srid": grid.srid,
        "width": grid.width,
        "height": grid.height,
        "origin": (grid.x0, grid.y0),
        "scale": (grid.resolution, -grid.resolution),
        "datatype": 6,  # Float32
        "bands": [{"data": data, "nodata_value": NODATA}],
    })
    return LandSurfaceTemperature.objects.create(
        raster=raster,
        date_time=scene.acquired,
        source=_source_label(scene, layers),
        satellite_type=SENSOR_LABELS.get(sensor, sensor),
        measurement_method=f"{METHOD_LABEL}, TPW {tpw_source}" if tpw_source else METHOD_LABEL,
        resolution=grid.resolution,
    )


def replace_covered(record, scene, grid):
    """
    Delete the other LST rows of the same scene that lie inside `grid`
    (a recalculation of that area), with their COG files. Returns their ids.
    """
    from urban_heat.models import LandSurfaceTemperature

    gx0, gy0, gx1, gy1 = grid.extent
    tol = grid.resolution / 2
    replaced = []
    candidates = LandSurfaceTemperature.objects.filter(
        source__startswith=f"{SOURCE_PREFIX}{scene.scene_id} "
    ).exclude(pk=record.pk)
    for old in candidates:
        if old.raster is None:
            continue
        x0, y0, x1, y1 = old.raster.extent
        if x0 >= gx0 - tol and y0 >= gy0 - tol and x1 <= gx1 + tol and y1 <= gy1 + tol:
            cog_path = old.cog_path
            replaced.append(old.pk)
            old.delete()
            if cog_path and os.path.exists(cog_path):
                try:
                    os.unlink(cog_path)
                except OSError as e:
                    logger.warning("Could not delete COG %s: %s", cog_path, e)
    return replaced


def resolve_inputs(*, ndvi=None, city=None, bbox_wgs84=None, resolution=30.0):
    """The NDVI layers and grid of a run: a map view, or one NDVI layer's extent."""
    from . import gee

    if bbox_wgs84 is not None:
        layers = ndvi_layers_in(bbox_wgs84)
        grid = view_grid(bbox_wgs84, layers, resolution)
    else:
        layers = [ndvi or ndvi_layer(city)]
        grid = grid_for(layers[0].raster, resolution)
    try:
        gee.check_download_size(grid)
    except gee.GEEError as e:
        raise LSTError(str(e)) from e
    return layers, grid


def search_window(layers, date_from=None, date_to=None):
    if date_from is None or date_to is None:
        default_from, default_to = default_window(layers[0])
        date_from, date_to = date_from or default_from, date_to or default_to
    return date_from, date_to


def calculate_lst(
    *,
    ndvi=None,
    city=None,
    bbox_wgs84=None,
    date_from=None,
    date_to=None,
    scene_id=None,
    sensor="L9",
    resolution=30.0,
    max_cloud=None,
    use_ndvi=True,
    save=True,
):
    """
    Compute one LST raster and (unless save=False) store it.

    bbox_wgs84  [west, south, east, north] of the map view: every NDVI layer
                overlapping it is used, the grid is the view clipped to them.
    ndvi        otherwise, this LandCoverRaster (default ndvi_layer(city)).
    date_*      search window for the scene ([from, to)); default ±30 days around the newest NDVI.
    scene_id    a specific Landsat scene (system:index); default the clearest over the area.
    use_ndvi    False = emissivity straight from ASTER (the NDVI layers then only set the grid).
    """
    import numpy as np

    from . import gee, smw

    layers, grid = resolve_inputs(ndvi=ndvi, city=city, bbox_wgs84=bbox_wgs84, resolution=resolution)

    gee.initialize()
    if scene_id:
        scene = gee.get_scene(sensor, scene_id)
    else:
        date_from, date_to = search_window(layers, date_from, date_to)
        scenes = gee.find_scenes(sensor, str(date_from), str(date_to), grid.wgs84_bbox(), max_cloud)
        if not scenes:
            raise LSTError(f"No {SENSOR_LABELS.get(sensor, sensor)} scene between {date_from} and {date_to}.")
        scene = scenes[0]
    logger.info("LST: scene %s (%s, %.0f%% cloud), grid %dx%d @ %g m",
                scene.scene_id, scene.acquired, scene.cloud_cover, grid.width, grid.height, grid.resolution)

    bands, tpw_fields, tpw_source = gee.fetch_scene_inputs(sensor, scene, grid)
    out = smw.land_surface_temperature(
        brightness_temperature_k=bands["B10"],
        qa_pixel=bands["QA_PIXEL"],
        aster_em13=bands["EM13"],
        aster_em14=bands["EM14"],
        aster_ndvi=bands["ASTER_NDVI"],
        tpw=smw.interpolate_tpw(tpw_fields, tpw_source.step_ms),
        ndvi=ndvi_mosaic(layers, grid) if use_ndvi else None,
        sensor=sensor,
    )
    lst_c = out["LST_C"]
    valid_fraction = float(np.isfinite(lst_c).mean())
    if valid_fraction == 0:
        raise LSTError(f"Scene {scene.scene_id} has no clear pixel over the NDVI layer (clouds or cloud shadow there): pick a clearer scene.")

    result = LSTResult(scene, grid, layers, lst_c, valid_fraction, tpw_source=tpw_source.name)
    if save:
        from django.db import transaction

        with transaction.atomic():
            result.record = save_lst(lst_c, grid, scene, layers, sensor, tpw_source.name)
            result.replaced = replace_covered(result.record, scene, grid)
    return result
