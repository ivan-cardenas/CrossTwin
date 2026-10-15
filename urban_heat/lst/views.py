"""
The map's LST tool (core/static/js/LstTool.js): LST for the area in view.

    GET  /urban_heat/lst/scenes/?bbox=w,s,e,n[&from=&to=&sensor=&resolution=]
         -> the NDVI layers and grid of the view, and its Landsat scenes, clearest first
    POST /urban_heat/lst/calculate/  bbox, [scene, from, to, sensor, resolution, use_ndvi]
         -> computes and stores one LandSurfaceTemperature; returns its layer-catalog entry

Calculating writes a raster and spends Earth Engine quota, so it is staff
only, like map editing. Both calls are synchronous: a city-sized view takes
roughly 10-60 s, mostly the Earth Engine download.
"""
import logging
from datetime import date

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

logger = logging.getLogger(__name__)

MIN_RESOLUTION_M = 10.0
MAX_RESOLUTION_M = 1000.0


class BadRequest(ValueError):
    pass


def _bbox(value):
    try:
        west, south, east, north = (float(v) for v in (value or "").split(","))
    except ValueError:
        raise BadRequest("bbox must be west,south,east,north in degrees.") from None
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise BadRequest("bbox is not a valid west,south,east,north box.")
    return [west, south, east, north]


def _date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise BadRequest(f"Invalid date {value!r}; use YYYY-MM-DD.") from None


def _params(data):
    from .pipeline import SENSOR_LABELS

    sensor = data.get("sensor") or "L9"
    if sensor not in SENSOR_LABELS:
        raise BadRequest(f"sensor must be one of {sorted(SENSOR_LABELS)}.")
    try:
        resolution = float(data.get("resolution") or 30)
    except ValueError:
        raise BadRequest("resolution must be a number of metres.") from None
    if not MIN_RESOLUTION_M <= resolution <= MAX_RESOLUTION_M:
        raise BadRequest(f"resolution must be between {MIN_RESOLUTION_M:g} and {MAX_RESOLUTION_M:g} m.")
    date_from, date_to = _date(data.get("from")), _date(data.get("to"))
    if date_from and date_to and date_from >= date_to:
        raise BadRequest("'from' must be before 'to'.")
    return {
        "bbox_wgs84": _bbox(data.get("bbox")),
        "sensor": sensor,
        "resolution": resolution,
        "date_from": date_from,
        "date_to": date_to,
    }


def _error(message, status=400):
    return JsonResponse({"error": message}, status=status)


def _scene_json(scene):
    return {
        "id": scene.scene_id,
        "acquired": scene.acquired.isoformat(),
        "cloud_cover": scene.cloud_cover,
        "view_coverage": scene.view_coverage,
        "view_cloud": scene.view_cloud,
        "view_clear": scene.view_clear,
    }


def _grid_json(grid):
    return {"width": grid.width, "height": grid.height, "resolution": grid.resolution}


def _ndvi_json(layer):
    return {
        "id": layer.pk,
        "label": str(layer),
        "date": layer.date.date().isoformat() if layer.date else None,
        "year": layer.year,
    }


def _run(view):
    """Map the pipeline's expected failures to 400 and anything else to 502."""
    from .gee import GEEError
    from .pipeline import LSTError

    try:
        return view()
    except BadRequest as e:
        return _error(str(e))
    except (LSTError, GEEError) as e:
        return _error(str(e))
    except Exception as e:
        logger.exception("LST tool failed")
        return _error(f"LST calculation failed: {e}", status=502)


@require_GET
def lst_scenes(request):
    def view():
        from . import gee
        from .pipeline import resolve_inputs, search_window

        p = _params(request.GET)
        layers, grid = resolve_inputs(bbox_wgs84=p["bbox_wgs84"], resolution=p["resolution"])
        date_from, date_to = search_window(layers, p["date_from"], p["date_to"])
        gee.initialize()
        scenes = gee.find_scenes(p["sensor"], str(date_from), str(date_to), grid.wgs84_bbox())
        return JsonResponse({
            "window": {"from": date_from.isoformat(), "to": date_to.isoformat()},
            "ndvi": [_ndvi_json(layer) for layer in layers],
            "grid": _grid_json(grid),
            "scenes": [_scene_json(s) for s in scenes],
            "can_calculate": request.user.is_staff,
        })

    return _run(view)


@require_POST
def lst_calculate(request):
    if not request.user.is_staff:
        return _error("Log in as a staff user (at /admin/) to calculate LST.", status=403)

    def view():
        from mainMap.views import raster_layer_entry

        from .pipeline import calculate_lst

        p = _params(request.POST)
        result = calculate_lst(
            **p,
            scene_id=request.POST.get("scene") or None,
            use_ndvi=request.POST.get("use_ndvi", "1") != "0",
        )
        record = result.record
        return JsonResponse({
            "id": record.pk,
            "layer": raster_layer_entry(record) if record.cog_path else None,
            "replaced": result.replaced,
            "scene": _scene_json(result.scene),
            "ndvi": [_ndvi_json(layer) for layer in result.ndvi_layers],
            "grid": _grid_json(result.grid),
            "stats": result.stats(),
            "valid_fraction": result.valid_fraction,
            "tpw_source": result.tpw_source,
        })

    return _run(view)
