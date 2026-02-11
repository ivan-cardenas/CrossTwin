# common/views.py
from django.http import HttpResponse
from django.contrib.gis.gdal import GDALRaster
from io import BytesIO
from PIL import Image
import numpy as np
from .utils import MODEL_REGISTRY

def serve_raster_tile(request, layer_name, z, x, y):
    """
    Serve raster tiles in XYZ format (/{z}/{x}/{y}.png)
    """
    model = MODEL_REGISTRY.get(layer_name)
    if not model:
        return HttpResponse(status=404)
    
    # Calculate bounding box for this tile
    tile_bbox = get_tile_bbox(int(z), int(x), int(y))
    
    # Query rasters that intersect this tile
    from django.contrib.gis.geos import Polygon
    bbox_poly = Polygon.from_bbox(tile_bbox)
    
    rasters = model.objects.filter(raster__intersects=bbox_poly)
    
    if not rasters.exists():
        # Return transparent tile
        return HttpResponse(status=204)
    
    # Merge and render rasters for this tile
    tile_image = render_rasters_to_tile(rasters, tile_bbox, 256, 256)
    
    # Return as PNG
    buffer = BytesIO()
    tile_image.save(buffer, format='PNG')
    buffer.seek(0)
    
    return HttpResponse(buffer.getvalue(), content_type='image/png')


def get_tile_bbox(z, x, y):
    """Convert XYZ tile coordinates to WGS84 bounding box"""
    from math import pi, atan, sinh
    
    def num2deg(xtile, ytile, zoom):
        n = 2.0 ** zoom
        lon_deg = xtile / n * 360.0 - 180.0
        lat_rad = atan(sinh(pi * (1 - 2 * ytile / n)))
        lat_deg = lat_rad * 180.0 / pi
        return (lat_deg, lon_deg)
    
    nw = num2deg(x, y, z)
    se = num2deg(x + 1, y + 1, z)
    
    return (nw[1], se[0], se[1], nw[0])  # (minx, miny, maxx, maxy)


def render_rasters_to_tile(rasters, bbox, width, height):
    """Render rasters to a tile image with colormap"""
    # Create empty array for tile
    tile_array = np.zeros((height, width), dtype=np.float32)
    tile_array[:] = np.nan
    
    for raster_obj in rasters:
        gdal_raster = GDALRaster(raster_obj.raster)
        
        # Warp raster to tile bbox and resolution
        # This is simplified - you'll need proper resampling
        band = gdal_raster.bands[0]
        data = band.data()
        
        # Overlay onto tile_array
        # ... implement proper spatial alignment ...
    
    # Apply colormap (example for temperature/elevation)
    from matplotlib import cm
    import matplotlib.pyplot as plt
    
    # Normalize values
    valid_data = tile_array[~np.isnan(tile_array)]
    if len(valid_data) == 0:
        return Image.new('RGBA', (width, height), (0, 0, 0, 0))
    
    vmin, vmax = np.nanmin(tile_array), np.nanmax(tile_array)
    normalized = (tile_array - vmin) / (vmax - vmin)
    
    # Apply colormap
    cmap = cm.get_cmap('viridis')  # or 'coolwarm', 'RdYlBu_r', etc.
    rgba = cmap(normalized)
    rgba[np.isnan(tile_array)] = [0, 0, 0, 0]  # Transparent for no-data
    
    # Convert to PIL Image
    rgba_uint8 = (rgba * 255).astype(np.uint8)
    return Image.fromarray(rgba_uint8, mode='RGBA')