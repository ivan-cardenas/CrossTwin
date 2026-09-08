import numpy as np
from scipy.interpolate import Rbf
from scipy.spatial import distance, KDTree
from django.contrib.gis.gdal import GDALRaster, SpatialReference
from django.contrib.gis.geos import Point
from django.conf import settings

import os
import re
import tempfile
import rasterio
from rasterio.io import MemoryFile
from rio_cogeo.cogeo import cog_translate
from rio_cogeo.profiles import cog_profiles
from django.contrib.gis.db import models as gis_models
from django.db import connection
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.io import MemoryFile

import tempfile
import os


# Where COG files will be stored
COG_DIRECTORY = os.path.join(settings.BASE_DIR, 'cogs')
# Make sure the directory exists
os.makedirs(COG_DIRECTORY, exist_ok=True)


def get_raster_field_name(model):
    """Find the name of the RasterField on a model."""
    for field in model._meta.get_fields():
        if isinstance(field, gis_models.RasterField):
            return field.name
    raise ValueError(f"No RasterField found on {model.__name__}")


def interpolate_raster(input_points, values, bounds, resolution, method='linear'):
    """
    Interpolates raster data using Radial Basis Function (RBF) interpolation.
    
    Parameters:
    - input_points: List of tuples (x, y) representing the coordinates of input points.
    - values: List of values corresponding to each input point.
    - grid_x: 1D array of x-coordinates for the output grid.
    - grid_y: 1D array of y-coordinates for the output grid.
    - resolution: Resolution of the output raster.
    - method: Interpolation method ('linear', 'cubic', 'quintic', etc.).
    
    Returns:
    - A 2D numpy array representing the interpolated raster.
    """
    if resolution <= 0:
        raise ValueError("Resolution must be a positive number.")       
    
    min_x, min_y, max_x, max_y = bounds
    
    x_coords = np.arange(min_x, max_x, resolution)
    y_coords = np.arange(min_y, max_y, resolution)
    grid_x, grid_y = np.meshgrid(x_coords, y_coords)
    
    point_x = np.array([p['geom'].x for p in input_points])
    point_y = np.array([p['geom'].y for p in input_points])
    point_values = np.array([p[values] for p in input_points])
    
    if method == 'linear':
        rbf = Rbf(point_x, point_y, point_values, function='linear')
        grid_values = rbf(grid_x, grid_y)
    
    if method == 'idw':
        tree = KDTree(np.c_[point_x, point_y])
        grid_values = np.zeros(grid_x.shape)
        for i in range(grid_x.shape[0]):
            for j in range(grid_x.shape[1]):
                dist, idx = tree.query([grid_x[i, j], grid_y[i, j]], k=len(point_x))
                weights = 1 / (dist + 1e-10)
                weights /= weights.sum()
                grid_values[i, j] = np.sum(weights * point_values[idx])
                
    elif method == 'kriging':
        rbf = Rbf(point_x, point_y, point_values, function='gaussian')
        grid_values = rbf(grid_x, grid_y)
    
    # Create temporary GeoTIFF
    temp_file = tempfile.NamedTemporaryFile(suffix='.tif', delete=False)
    temp_path = temp_file.name
    temp_file.close()
    
    # Create GDAL raster
    driver = GDALRaster({
        'width': len(x_coords),
        'height': len(y_coords),
        'srid': settings.COORDINATE_SYSTEM,
        'origin': (min_x, max_y),  # Top-left corner
        'scale': (resolution, -resolution),  # Negative Y for north-up
        'bands': [{
            'data': grid_values,
            'nodata_value': -9999
        }]
    })
    
    # Save to file
    driver.name = temp_path
    
    return temp_path, driver


def _cog_filename(instance):
    """
    Build a COG filename from whatever satellite/process metadata the raster
    model carries, e.g. NDVI_Sentinel2_20260908_42.tif, so files on disk are
    identifiable by what produced them instead of just a class name and id.
    Falls back to the model's class name for models with no such metadata
    (e.g. weather's interpolated rasters). The trailing id always stays, since
    two records can share the same index/source/date (re-imports, different
    cities on the same day) and must not overwrite each other's COG.
    """
    parts = []

    index = getattr(instance, 'index', None)
    if index:
        parts.append(str(index))

    provenance = getattr(instance, 'satellite_type', None) or getattr(instance, 'source', None)
    if provenance:
        parts.append(str(provenance))

    date_value = getattr(instance, 'date', None) or getattr(instance, 'date_time', None)
    if date_value:
        parts.append(date_value.strftime('%Y%m%d'))
    elif getattr(instance, 'year', None):
        parts.append(str(instance.year))

    if not parts:
        parts.append(instance.__class__.__name__)

    safe_parts = [p for p in (re.sub(r'[^A-Za-z0-9]+', '', str(part)) for part in parts) if p]
    safe_parts.append(str(instance.id))
    return "_".join(safe_parts) + ".tif"


def _reproject_and_cog(source_tiff_path, instance):
    """
    Reproject a local GeoTIFF to EPSG:4326 and convert it to a COG on disk,
    saving the result path onto `instance.cog_path`. Shared by
    export_raster_to_cog (source: bytes read back out of Postgres) and
    export_geotiff_to_cog (source: a file already on disk that was never
    loaded into Postgres at all) so both paths produce identically processed
    COGs regardless of where the source raster came from.
    """
    # Transform to EPSG:4326 (what the COG's header below declares, and what
    # TiTiler/core/views.py::get_raster_info expects bounds to be in). This
    # used to pass dst_crs='EPSG:3857' to reproject() below while everything
    # else here — the computed transform, width/height, and the output
    # file's own 'crs' tag — targeted EPSG:4326, a leftover mismatch from an
    # earlier rename. That silently corrupted every COG's georeferencing:
    # pixels got warped into Web Mercator meters while the file claimed to
    # be WGS84 degrees, so consumers reading the (false) CRS tag placed the
    # data nowhere near where it actually was.
    temp_4326 = tempfile.NamedTemporaryFile(suffix='_4326.tif', delete=False)
    temp_4326.close()

    with rasterio.open(source_tiff_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs,
            'EPSG:4326',
            src.width,
            src.height,
            *src.bounds
        )

        # Update metadata for the reprojected raster
        kwargs = src.meta.copy()
        kwargs.update({
            'crs': 'EPSG:4326',
            'transform': transform,
            'width': width,
            'height': height
        })

        # Reproject and write to temp file
        with rasterio.open(temp_4326.name, 'w', **kwargs) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs='EPSG:4326',
                    resampling=Resampling.nearest
                )

    # --- Convert to COG ---
    # Organize by model: cogs/urbanHeat/LandSurfaceTemp/id_3.tif
    app_label = instance.__class__._meta.app_label

    cog_subdir = os.path.join(COG_DIRECTORY, app_label)
    os.makedirs(cog_subdir, exist_ok=True)

    cog_path = os.path.join(cog_subdir, _cog_filename(instance))

    output_profile = cog_profiles.get("DEFLATE")

    cog_translate(
        source=temp_4326.name,
        dst_path=cog_path,
        dst_kwargs=output_profile,
        overview_level=6,
        overview_resampling="nearest",
        use_cog_driver=True,
    )

    os.unlink(temp_4326.name)

    # --- Save COG path to the database ---
    instance.cog_path = cog_path.replace("\\", "/")
    instance.save(update_fields=['cog_path'])

    return cog_path


def export_raster_to_cog(instance):
    """
    Export any model instance with a RasterField to a COG.

    instance:  the model instance (e.g. a LandSurfaceTemp object)
    model_key: registry key like "urbanHeat.LandSurfaceTemp"
    """
    model = instance.__class__
    table_name = model._meta.db_table
    raster_field = get_raster_field_name(model)

    # --- Read raster bytes from PostGIS ---
    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT ST_AsGDALRaster({raster_field}, 'GTiff')
            FROM {table_name}
            WHERE id = %s;
        """, [instance.id])

        row = cursor.fetchone()
        if row is None or row[0] is None:
            raise ValueError(f"No raster data for {instance.__class__.__name__} id={instance.id}")

        raw_tiff_bytes = bytes(row[0])

    # --- Write temp file ---
    temp_tiff = tempfile.NamedTemporaryFile(suffix='.tif', delete=False)
    temp_tiff.write(raw_tiff_bytes)
    temp_tiff.close()

    try:
        cog_path = _reproject_and_cog(temp_tiff.name, instance)
    finally:
        os.unlink(temp_tiff.name)

    print(f"[export_raster_to_cog] {instance.__class__.__name__} id={instance.id} -> {cog_path}")
    return cog_path


def export_geotiff_to_cog(source_tiff_path, instance):
    """
    Convert a GeoTIFF already on disk directly to a COG, without ever loading
    it into Postgres. Used for models flagged `SKIP_RASTER_DB_STORAGE = True`
    (e.g. common.DigitalElevationModel/DigitalSurfaceModel) where nothing
    queries the raster with server-side PostGIS raster SQL, so storing the
    raw raster as a RasterField blob is a large, purely redundant write —
    the actual failure mode for city-scale imports (a multi-hundred-MB
    mosaic sent as a single query parameter can crash the Postgres backend
    outright rather than erroring cleanly).
    """
    cog_path = _reproject_and_cog(source_tiff_path, instance)
    print(f"[export_geotiff_to_cog] {instance.__class__.__name__} id={instance.id} -> {cog_path}")
    return cog_path

def export_all_rasters():
    """Export all rasters that don't have a COG yet."""
    from core.utils import RASTER_REGISTRY as RasterLayer
    
    # Only export rasters that haven't been converted yet
    print(f"Checking for rasters to export...")
    print(f"{RasterLayer}")
    pending = RasterLayer.objects.filter(cog_path__isnull=True)
    
    print(f"Found {pending.count()} rasters to export\n")
    
    for raster_layer in pending:
        try:
            path = export_raster_to_cog(raster_layer)
            print(f"  Done: {raster_layer.name} -> {path}\n")
        except Exception as e:
            print(f"  Failed: {raster_layer.name} -> {e}\n")