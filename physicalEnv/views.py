"""
The map's SVF tool (core/static/js/SvfTool.js): sky-view factor for the area in view.

    GET  /physicalEnv/svf/info/?bbox=w,s,e,n[&radius=&resolution=]
         -> the DSM covering the view, the grid it would compute, and the
            stored SVF rows that already cover the view (Recalculate)
    POST /physicalEnv/svf/calculate/  bbox, [radius, resolution]
         -> computes and stores one SkyViewFactor over the view; returns its
            layer-catalog entry and the ids of the rows it replaced

Calculating writes a raster, so it is staff only, like map editing and the
LST tool. Synchronous: a few seconds for a neighbourhood at 0.5 m, up to about
a minute at the MAX_CELLS limit.
"""
import logging

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

logger = logging.getLogger(__name__)

MIN_RADIUS_M = 5.0
MAX_RADIUS_M = 300.0
MIN_RESOLUTION_M = 0.25
MAX_RESOLUTION_M = 50.0


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


def _number(data, name, default, low, high, unit="m"):
    raw = data.get(name)
    if raw in (None, ""):
        return default
    try:
        value = float(raw)
    except ValueError:
        raise BadRequest(f"{name} must be a number of metres.") from None
    if not low <= value <= high:
        raise BadRequest(f"{name} must be between {low:g} and {high:g} {unit}.")
    return value


def _params(data):
    from .svf import DEFAULT_RADIUS_M

    return {
        "bbox_wgs84": _bbox(data.get("bbox")),
        "radius_m": _number(data, "radius", DEFAULT_RADIUS_M, MIN_RADIUS_M, MAX_RADIUS_M),
        # Empty = the DSM's own cell size.
        "resolution": _number(data, "resolution", None, MIN_RESOLUTION_M, MAX_RESOLUTION_M),
    }


def _error(message, status=400):
    return JsonResponse({"error": message}, status=status)


def _dsm_json(dsm):
    return {"id": dsm.pk, "label": str(dsm), "source": dsm.source, "year": dsm.year}


def _existing_json(record):
    return {
        "id": record.pk,
        "date": record.date_time.isoformat() if record.date_time else None,
        "method": record.measurement_method,
        "resolution": record.resolution,
    }


def _run(view):
    """Map the tool's expected failures to 400 and anything else to 502."""
    from .svf import SVFError

    try:
        return view()
    except (BadRequest, SVFError) as e:
        return _error(str(e))
    except Exception as e:
        logger.exception("SVF tool failed")
        return _error(f"SVF calculation failed: {e}", status=502)


@require_GET
def svf_info(request):
    def view():
        from . import svf

        p = _params(request.GET)
        plan = svf.plan(svf.wgs84_to_storage(p["bbox_wgs84"]),
                        radius_m=p["radius_m"], resolution=p["resolution"])
        existing = svf.existing_svf(plan["dsm"], plan["covered"], cell=plan["cell"])
        return JsonResponse({
            "dsm": _dsm_json(plan["dsm"]),
            "coverage": plan["coverage"],
            "grid": {"width": plan["width"], "height": plan["height"], "resolution": plan["cell"]},
            "radius_m": plan["radius_m"],
            "read_cells": plan["read_cells"],
            "max_cells": svf.MAX_CELLS,
            "existing": [_existing_json(r) for r in existing[:5]],
            "can_calculate": request.user.is_staff,
        })

    return _run(view)


@require_POST
def svf_calculate(request):
    if not request.user.is_staff:
        return _error("Log in as a staff user (at /admin/) to calculate the SVF.", status=403)

    def view():
        from mainMap.views import raster_layer_entry

        from .svf import calculate_svf

        result = calculate_svf(**_params(request.POST))
        record = result.record
        return JsonResponse({
            "id": record.pk,
            "layer": raster_layer_entry(record) if record.cog_path else None,
            "replaced": result.replaced,
            "dsm": _dsm_json(result.dsm),
            "grid": {"width": result.width, "height": result.height, "resolution": result.cell},
            "radius_m": result.radius_m,
            "stats": {"min": result.min, "max": result.max, "mean": result.mean},
            "valid_fraction": result.valid_fraction,
        })

    return _run(view)
