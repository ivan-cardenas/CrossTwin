from django.http import JsonResponse
from .utils import RASTER_REGISTRY, without_raster_data
from mainMap.styles.rasterStyles import resolve_raster_style, colormap_legend_stops, discrete_colormap_param
from django.conf import settings
from urllib.parse import quote
import requests


def displayed_cog_path(instance):
    """
    The COG the map shows for a raster row: a DSM's edited copy (the map
    editor's building/vegetation changes burnt in, physicalEnv/calculations/dsm_edited.py)
    when it exists, else cog_path.
    """
    import os

    edited = getattr(instance, "edited_cog_path", None)
    return edited if edited and os.path.exists(edited) else instance.cog_path


def _cog_version(path):
    """
    The COG file's mtime in ms: added to tile URLs as `v=` so the browser may
    cache tiles for good (tiler.py sends `immutable` for versioned URLs); a
    rewritten COG gets a new URL. 0 when the file is missing.
    """
    import os

    try:
        return int(os.path.getmtime(path) * 1000)
    except OSError:
        return 0


def _titiler_info(path):
    """TiTiler's /cog/info of a COG, cached per file version (it never changes for one)."""
    from django.core.cache import cache

    key = f"titiler-info:{path}:{_cog_version(path)}"
    info = cache.get(key)
    if info is None:
        encoded_url = quote(f"file://{path}", safe="/:")
        # info.geojson, not info: its bbox is always WGS84 (what Mapbox needs),
        # while info's bounds are in the COG's own CRS (EPSG:3857 since COG_CRS).
        response = requests.get(f"{settings.TITILER_BASE_URL}/cog/info.geojson?url={encoded_url}", timeout=30)
        response.raise_for_status()
        feature = response.json()
        info = {**feature["properties"], "bounds": feature["bbox"]}
        cache.set(key, info, 24 * 3600)
    return info


def get_raster_info(request, app_label, layer_name):
    """Return raster metadata including bounds."""
    
    registry_key = f"{app_label}.{layer_name}"
    model_class = RASTER_REGISTRY.get(registry_key)
    
    if not model_class:
        return JsonResponse({"error": f"'{registry_key}' not found"}, status=404)
    
    raster_id = request.GET.get('id')
    
    if raster_id:
        instance = without_raster_data(model_class.objects.filter(id=raster_id)).first()
    else:
        instance = without_raster_data(model_class.objects.all()).first()
    
    if not instance or not instance.cog_path:
        return JsonResponse({"error": "No raster data found"}, status=404)
   
    
    try:
        info = _titiler_info(displayed_cog_path(instance))

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
        instance = without_raster_data(model_class.objects.filter(id=raster_id)).first()
    else:
        instance = without_raster_data(model_class.objects.all()).first()
    
    if not instance:
        return JsonResponse({"error": f"No data found for '{registry_key}'"}, status=404)
    
    if not instance.cog_path:
        return JsonResponse({"error": "COG not generated yet"}, status=404)
    
    # Step 3: Build the TiTiler tile URL
    cog_path = displayed_cog_path(instance)
    encoded_url = quote(f"file://{cog_path}", safe="/:")

    style = resolve_raster_style(instance, registry_key)

    tile_url = (
        f"{settings.TITILER_BASE_URL}/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}.png"
        f"?url={encoded_url}&v={_cog_version(cog_path)}"
    )

    # TiTiler defaults to nearest-neighbour resampling (blocky at high zoom);
    # only override it where mainMap/styles/rasterStyles.py's RESAMPLING_OVERRIDES asks
    # for smoother interpolation, e.g. HRSL's 30m population pixels. The
    # query param is `resampling` on the wire (RIOResampling's FastAPI
    # alias), not the Python field name `resampling_method`.
    if style["resampling"]:
        tile_url += f"&resampling={style['resampling']}"

    # rescale applies whenever the raster's values aren't already in a
    # directly-displayable 0-255 range — including multi-band RGB composites
    # (e.g. Sentinel-2 true color, which downloads as float reflectance-like
    # values in the thousands) that have no colormap at all. A colormap-only
    # legend only makes sense for single-band data, so it's built separately.
    if style["rescale"]:
        vmin, vmax = style["rescale"]
        tile_url += f"&rescale={vmin},{vmax}"

    legend = None
    if style.get("discrete"):
        # Fixed colour per class value (e.g. GHSL GHS-SMOD): no rescale, no named colormap.
        classes = style["discrete"]
        tile_url += f"&colormap={quote(discrete_colormap_param(classes))}"
        legend = {
            "label": style["label"], "unit": style["unit"],
            "min": min(classes), "max": max(classes), "categorical": True,
            "stops": [{"value": value, "color": color} for value, color in sorted(classes.items())],
        }
    elif style["colormap"]:
        tile_url += f"&colormap_name={style['colormap']}"
        if style["rescale"]:
            legend = {
                "label": style["label"],
                "unit": style["unit"],
                "min": vmin,
                "max": vmax,
                "categorical": style["categorical"],
                "stops": colormap_legend_stops(style["colormap"], style["rescale"]),
            }

    return JsonResponse({
        "name": registry_key,
        "tile_url": tile_url,
        "legend": legend,
    })






def console_feed(request):
    """
    The server's recent console lines for the map loader (core/console.py).
    `?after=<seq>` returns the lines after that seq; without it only the seq
    to start from. Lines can hold paths and URLs, so only in DEBUG or for staff.
    """
    from . import console

    if not (settings.DEBUG or request.user.is_staff):
        return JsonResponse({"error": "forbidden"}, status=403)
    after = request.GET.get("after")
    try:
        after = int(after) if after not in (None, "") else None
    except ValueError:
        return JsonResponse({"error": "after must be an integer"}, status=400)
    lines, last = console.since(after)
    return JsonResponse({"lines": lines, "last": last})
