"""
The map's thermal comfort tool (core/static/js/SolweigTool.js): SOLWEIG
Tmrt, UTCI and PET for the area in view and one hour.

    GET  /urban_heat/solweig/info/?bbox=w,s,e,n&datetime=YYYY-MM-DDTHH:MM[&resolution=]
         -> DSM, grid, cell count and limit, sun position at the view centre,
            device, stale results
    GET  /urban_heat/solweig/met/?bbox=&datetime=&source=knmi|era5
         -> the met values of the nearest KNMI station or ERA5, to prefill the form
    POST /urban_heat/solweig/calculate/  bbox, datetime, resolution, ta_c, rh_pct,
         wind_ms, wind_dir_deg, kdown_wm2, pressure_kpa, source
         -> starts a ThermalComfortRun in the background; returns its id
    GET  /urban_heat/solweig/runs/<id>/
         -> status; when done, the layer-catalog entries of Tmrt, UTCI and PET
    GET  /urban_heat/solweig/stale/?bbox=
         -> SVF and thermal-comfort results that building edits made stale

Calculating writes rasters and occupies the GPU, so it is staff only.
"""
import logging
from datetime import datetime

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .pipeline import centre, local_timezone

logger = logging.getLogger(__name__)

MIN_RESOLUTION_M = 0.5
MAX_RESOLUTION_M = 10.0
INSTALL_HINT = "SOLWEIG is not installed on the server: uv sync --extra solweig"

# Met inputs: (name, default, low, high, unit). Validated at this trust boundary.
MET_FIELDS = (
    ("ta_c", None, -40.0, 50.0, "°C"),
    ("rh_pct", None, 0.0, 100.0, "%"),
    ("wind_ms", None, 0.0, 40.0, "m/s"),
    ("wind_dir_deg", -999.0, -999.0, 360.0, "°"),
    ("kdown_wm2", None, 0.0, 1400.0, "W/m²"),
    ("pressure_kpa", 101.3, 85.0, 110.0, "kPa"),
)


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
        if default is None:
            raise BadRequest(f"{name} is required.")
        return default
    try:
        value = float(raw)
    except ValueError:
        raise BadRequest(f"{name} must be a number ({unit}).") from None
    if not low <= value <= high:
        raise BadRequest(f"{name} must be between {low:g} and {high:g} {unit}.")
    return value


def _when(value, bbox):
    """The analysed hour: local time at the view centre (as SOLWEIG reads it), on the whole hour."""
    try:
        when = datetime.fromisoformat(value or "")
    except ValueError:
        raise BadRequest("datetime must be YYYY-MM-DDTHH:MM (local time).") from None
    tz = local_timezone(*centre(bbox))
    when = when.astimezone(tz) if when.tzinfo else when.replace(tzinfo=tz)
    return when.replace(minute=0, second=0, microsecond=0)


def _error(message, status=400):
    return JsonResponse({"error": message}, status=status)


def _run(view):
    """Map the tool's expected failures to 400 and anything else to 502."""
    from .inputs import SolweigError
    from .met import MetError

    try:
        return view()
    except (BadRequest, SolweigError, MetError) as e:
        return _error(str(e))
    except Exception as e:
        logger.exception("SOLWEIG tool failed")
        return _error(f"SOLWEIG tool failed: {e}", status=502)


def _resolution(data):
    from .inputs import DEFAULT_CELL_M

    return _number(data, "resolution", DEFAULT_CELL_M, MIN_RESOLUTION_M, MAX_RESOLUTION_M)


@require_GET
def solweig_info(request):
    def view():
        from physicalEnv.svf import wgs84_to_storage

        from . import inputs, pipeline

        bbox = _bbox(request.GET.get("bbox"))
        when = _when(request.GET.get("datetime"), bbox) if request.GET.get("datetime") else None
        view_box = wgs84_to_storage(bbox)
        available = pipeline.solweig_available()
        device = pipeline.device() if available else None
        body = {
            "available": available,
            "install_hint": None if available else INSTALL_HINT,
            "device": device,
            "max_cells": inputs.MAX_CELLS,
            "halo_m": inputs.HALO_M,
            "sun": pipeline.sun_position(when, *centre(bbox)) if when and available else None,
            "stale": pipeline.stale_results(view_box),
            "can_calculate": request.user.is_staff and available,
        }
        try:
            p = inputs.plan(view_box, cell=_resolution(request.GET))
        except inputs.SolweigError as e:
            body.update({"dsm": None, "error": str(e)})
            return JsonResponse(body)
        body.update({
            "dsm": {"id": p["dsm"].pk, "label": str(p["dsm"])},
            "coverage": p["coverage"],
            "grid": {"width": p["width"], "height": p["height"], "resolution": p["cell"]},
            "read_cells": p["read_cells"],
            "estimate_s": round(p["read_cells"] * inputs.MS_PER_CELL.get(device or "cpu", 12.0) / 1000),
        })
        return JsonResponse(body)

    return _run(view)


@require_GET
def solweig_met(request):
    def view():
        from . import met

        bbox = _bbox(request.GET.get("bbox"))
        when = _when(request.GET.get("datetime"), bbox)
        source = request.GET.get("source")
        if source not in ("knmi", "era5"):
            raise BadRequest("source must be knmi or era5.")
        fetch = met.knmi_hourly if source == "knmi" else met.era5_hourly
        values, station = fetch(when, *centre(bbox))
        return JsonResponse({"met": values.as_dict(), "station": station})

    return _run(view)


def _run_json(run):
    from mainMap.views import raster_layer_entry

    from .pipeline import run_state

    status, message = run_state(run)
    layers = [raster_layer_entry(r) for r in (run.mrt, run.utci, run.pet)
              if status == "done" and r is not None and r.cog_path]
    return {
        "id": run.pk, "status": status, "message": message, "device": run.device,
        "date_time": run.date_time.isoformat(), "met": run.met,
        "inputs": run.inputs, "stats": run.stats, "layers": layers,
    }


@require_POST
def solweig_calculate(request):
    if not request.user.is_staff:
        return _error("Log in as a staff user to calculate thermal comfort.", status=403)

    def view():
        from django.db import transaction

        from physicalEnv.svf import _storage_box, wgs84_to_storage

        from urban_heat.models import ThermalComfortRun

        from . import inputs, pipeline
        from .met import Met

        if not pipeline.solweig_available():
            return _error(INSTALL_HINT, status=503)
        data = request.POST
        bbox = _bbox(data.get("bbox"))
        when = _when(data.get("datetime"), bbox)
        resolution = _resolution(data)
        met = Met(**{name: _number(data, name, default, low, high, unit)
                     for name, default, low, high, unit in MET_FIELDS},
                  source=(data.get("source") or "manual")[:60])
        p = inputs.plan(wgs84_to_storage(bbox), cell=resolution)  # refuse a too-large view now
        with transaction.atomic():
            run = ThermalComfortRun.objects.create(
                area=_storage_box(p["covered"]), bbox_wgs84=bbox, date_time=when, met=met.as_dict(), resolution=resolution)
            pipeline.start_run(run)
        return JsonResponse(_run_json(run), status=202)

    return _run(view)


@require_GET
def solweig_run(request, run_id):
    from django.shortcuts import get_object_or_404

    from urban_heat.models import ThermalComfortRun

    run = get_object_or_404(ThermalComfortRun.objects.select_related("mrt", "utci", "pet"), pk=run_id)
    return JsonResponse(_run_json(run))


@require_GET
def solweig_stale(request):
    def view():
        from physicalEnv.svf import wgs84_to_storage

        from .pipeline import stale_results

        return JsonResponse(stale_results(wgs84_to_storage(_bbox(request.GET.get("bbox")))))

    return _run(view)
