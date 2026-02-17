# common/views.py
from django.http import HttpResponse, JsonResponse
from django.contrib.gis.gdal import GDALRaster
from .utils import MODEL_REGISTRY, RASTER_REGISTRY
from django.conf import settings
from urllib.parse import quote

def get_raster_tiles(request, raster_id):
    """Return TiTiler title URL for a given RasterLayer"""
    
    raster = RASTER_REGISTRY.get(raster_id)
    if not raster.cog_path:
        return JsonResponse({"error: COG not generated yet"}, status=404)
    
    cog_url = f'file://{raster.cog_path}'
    uncoded_url = quote(cog_url, safe='/:')
    
    
    tile_url = (
        f'{settings.TILER_URL}/cog/tiles/{{z}}/{{x}}/{{y}}.png'
        f'?url={uncoded_url}'
        f'&colormap={raster.colormap}'
        f'&rescale={raster.rescale}'
    )
    
    return JsonResponse({
        'name': raster.name,
        'tile_url': tile_url
    })




