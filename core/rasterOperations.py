import numpy as np
from scipy.interpolate import Rbf
from scipy.spatial import distance, KDTree
from django.contrib.gis.gdal import GDALRaster, SpatialReference
from django.contrib.gis.geos import Point
from django.conf import settings

import os
import tempfile
import rasterio
from rasterio.io import MemoryFile
from rio_cogeo.cogeo import cog_translate
from rio_cogeo.profiles import cog_profiles
from django.contrib.gis.db import models as gis_models
from django.db import connection


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


def export_raster_to_cog(instance, model_key):
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
            raise ValueError(f"No raster data for {model_key} id={instance.id}")
        
        raw_tiff_bytes = bytes(row[0])

    # --- Write temp file ---
    temp_tiff = tempfile.NamedTemporaryFile(suffix='.tif', delete=False)
    temp_tiff.write(raw_tiff_bytes)
    temp_tiff.close()

    # --- Convert to COG ---
    # Organize by model: cogs/urbanHeat/LandSurfaceTemp/id_3.tif
    app_label, model_name = model_key.split('.')
    cog_subdir = os.path.join(COG_DIRECTORY, app_label, model_name)
    os.makedirs(cog_subdir, exist_ok=True)
    
    cog_path = os.path.join(cog_subdir, f"id_{instance.name}.tif")
    
    output_profile = cog_profiles.get("deflate")
    
    cog_translate(
        input=temp_tiff.name,
        output=cog_path,
        profile=output_profile,
        overview_level=6,
        overview_resampling="nearest",
        use_cog_driver=True,
    )

    # --- Cleanup ---
    os.unlink(temp_tiff.name)
    
    print(f"✓ {model_key} id={instance.id} → {cog_path}")
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
            print(f"  ✓ Done: {raster_layer.name} → {path}\n")
        except Exception as e:
            print(f"  ✗ Failed: {raster_layer.name} → {e}\n")