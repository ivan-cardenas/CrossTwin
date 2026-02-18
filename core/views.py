from django.http import JsonResponse
from .utils import RASTER_REGISTRY
from django.conf import settings
from urllib.parse import quote
import requests


def get_raster_info(request, app_label, layer_name):
    """Return raster metadata including bounds."""
    
    registry_key = f"{app_label}.{layer_name}"
    model_class = RASTER_REGISTRY.get(registry_key)
    
    if not model_class:
        return JsonResponse({"error": f"'{registry_key}' not found"}, status=404)
    
    raster_id = request.GET.get('id')
    
    if raster_id:
        instance = model_class.objects.filter(id=raster_id).first()
    else:
        instance = model_class.objects.first()
    
    if not instance or not instance.cog_path:
        return JsonResponse({"error": "No raster data found"}, status=404)
   
    
    cog_url = f"file://{instance.cog_path}"
    encoded_url = quote(cog_url, safe="/:")
    
    try:
        info_url = f"{settings.TITILER_BASE_URL}/cog/info?url={encoded_url}"
        info = requests.get(info_url).json()
    
        return JsonResponse({
            "name": registry_key,
            "bounds": info['bounds'],
            "width": info['width'],
            "height": info['height'],
            "minzoom": info.get('minzoom', 0),
            "maxzoom": info.get('maxzoom', 24)
        })
    except Exception as e:
        return JsonResponse({"error": f"Failed to get raster info: {e}"}, status=500)

def get_raster_tiles(request, app_label, layer_name):
    """Return TiTiler tile URL for a given raster layer."""
    
    # Step 1: Get the model CLASS from registry
    registry_key = f"{app_label}.{layer_name}"
    model_class = RASTER_REGISTRY.get(registry_key)
    
    if not model_class:
        return JsonResponse({"error": f"'{registry_key}' not found in raster registry"}, status=404)
    

    # Get specific instance by ID, or fall back to first
    raster_id = request.GET.get('id')
    
    if raster_id:
        instance = model_class.objects.filter(id=raster_id).first()
    else:
        instance = model_class.objects.first()
    
    if not instance:
        return JsonResponse({"error": f"No data found for '{registry_key}'"}, status=404)
    
    if not instance.cog_path:
        return JsonResponse({"error": "COG not generated yet"}, status=404)
    
    # Step 3: Build the TiTiler tile URL
    cog_url = f"file://{instance.cog_path}"
    encoded_url = quote(cog_url, safe="/:") 
    
    tile_url = (
        f"{settings.TITILER_BASE_URL}/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}.png"
        f"?url={encoded_url}"
        f"&colormap_name={getattr(instance, 'colormap', 'viridis')}"
        f"&rescale={getattr(instance, 'rescale', '0,40')}"
    )
    
    
    return JsonResponse({
        "name": registry_key,
        "tile_url": tile_url,
    })




