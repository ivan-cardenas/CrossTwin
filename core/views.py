# common/views.py
from django.http import HttpResponse
from django.contrib.gis.gdal import GDALRaster
from .utils import MODEL_REGISTRY
from django.contrib.gis.db import connection
import mercantile

def raster_tile(request, layer_id, z, x, y):
    """Serve XYZ tiles from PostGIS raster data."""
    # Get tile bounds in EPSG:3857 (Web Mercator)
    bounds = mercantile.xy_bounds(x, y, z)
    if layer_id not in MODEL_REGISTRY:
        return HttpResponse(status=404)

    table = MODEL_REGISTRY[layer_id]._meta.db_table
    
    
    # Use PostGIS to clip and render the raster as PNG
    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT ST_AsPNG(
                ST_Resize(
                    ST_Clip(
                        ST_Transform(rast, 3857),
                        ST_MakeEnvelope(%s, %s, %s, %s, 3857)
                    ),
                    256, 256
                )
            )
            FROM {table}
            WHERE ST_Intersects(
                ST_Transform(rast, 3857),
                ST_MakeEnvelope(%s, %s, %s, %s, 3857)
            )
        """, [bounds.left, bounds.bottom, bounds.right, bounds.top] * 2)
        
        row = cursor.fetchone()
        if row and row[0]:
            return HttpResponse(row[0], content_type='image/png')
    
    # Return transparent tile if no data
    return HttpResponse(status=204)
