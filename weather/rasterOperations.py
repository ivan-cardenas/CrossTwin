import numpy as np
from scipy.interpolate import Rbf
from scipy.spatial import distance, KDTree
from django.contrib.gis.gdal import GDALRaster, SpatialReference
from django.contrib.gis.geos import Point
from django.conf import settings

import tempfile
import os

def interpolate_raster(input_points, values, bounds, resolution=10, method='linear'):
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