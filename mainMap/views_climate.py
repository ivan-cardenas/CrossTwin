"""
Stored KNMI'23 climate scenario runs of the map's Scenarios panel
(weather.ClimateScenarioRun and the results the other apps store for it).

    POST /api/climate/runs/                     create a run (staff)
    GET  /api/climate/runs/?level=&location=    the unit's runs (list partial)
    GET  /api/climate/runs/<id>/                one run's results (partial)
    POST /api/climate/runs/<id>/recalculate/    re-save the run: water, housing and the heat summary (staff)
    POST /api/climate/runs/<id>/heat/           rerun its heat model (one SOLWEIG run) (staff)
    POST /api/climate/runs/<id>/delete/         delete it with its results and rasters (staff)

Creating a run only writes the ClimateScenarioRun: the receivers of
watersupply, housing and urban_heat compute and store their own results
(DAG contract), the heat model in the background. The observed rows are
never changed.
"""
import json
import logging
from datetime import datetime

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

logger = logging.getLogger(__name__)

DEFAULT_RESOLUTION_M = 2.0

# Rows of a run's effects table: (section, label, unit, decimals, getter of (now, scenario)).
# Getters read the stored results; a row is left out when both values are None.
RUN_ROWS = (
    ("Urban heat", "Air temperature", "°C", 1, lambda r: _met(r, "ta_c")),
    ("Urban heat", "Relative humidity", "%", 0, lambda r: _met(r, "rh_pct")),
    ("Urban heat", "Wind speed", "m/s", 1, lambda r: _met(r, "wind_ms")),
    ("Urban heat", "Solar radiation", "W/m²", 0, lambda r: _met(r, "kdown_wm2")),
    ("Urban heat", "Mean radiant temperature", "°C", 1, lambda r: _heat(r, "tmrt")),
    ("Urban heat", "UTCI", "°C", 1, lambda r: _heat(r, "utci")),
    ("Urban heat", "PET", "°C", 1, lambda r: _heat(r, "pet")),
    ("Urban heat", "WBGT", "°C", 1, lambda r: _heat(r, "wbgt")),
    ("Water supply", "Population", "", 0, lambda r: _pair(r, "water", "baseline_population", "population")),
    ("Water supply", "Water demand", "m³/day", 0, lambda r: _pair(r, "water", "baseline_demand_m3_d", "demand_m3_d")),
    ("Water supply", "Supply security", "%", 1,
     lambda r: _pair(r, "water", "baseline_supply_security_pct", "supply_security_pct")),
    ("Water supply", "Groundwater recharge", "Mm³/yr", 2,
     lambda r: _pair(r, "water", "baseline_yield_Mm3_year", "yield_Mm3_year")),
    ("Water supply", "Extraction", "Mm³/yr", 2, lambda r: _pair(r, "water", "extraction_Mm3_year", "extraction_Mm3_year")),
    ("Housing", "Population", "", 0, lambda r: _pair(r, "housing", "baseline_population", "population")),
    ("Housing", "Homes needed", "", 0, lambda r: _pair(r, "housing", "baseline_dwellings_needed", "dwellings_needed")),
    ("Housing", "Housing stock", "", 0, lambda r: _pair(r, "housing", "stock_units", "stock_units")),
    ("Housing", "Homes to build", "", 0, lambda r: _gap(r)),
)


def _related(run, name):
    try:
        return getattr(run, name)
    except Exception:  # RelatedObjectDoesNotExist
        return None


def _results(run):
    return {"heat": _related(run, "heat"), "water": _related(run, "water_security"),
            "housing": _related(run, "housing_need")}


def _met(results, key):
    heat = results["heat"]
    if heat is None:
        return None, None
    return (heat.met_observed or {}).get(key), (heat.met_scenario or {}).get(key)


def _heat(results, name):
    heat = results["heat"]
    return (None, None) if heat is None else (getattr(heat, f"{name}_now"), getattr(heat, f"{name}_scenario"))


def _pair(results, part, now, scenario):
    obj = results[part]
    return (None, None) if obj is None else (getattr(obj, now), getattr(obj, scenario))


def _gap(results):
    housing = results["housing"]
    if housing is None or housing.stock_units is None:
        return None, None
    now = (housing.baseline_dwellings_needed - housing.stock_units
           if housing.baseline_dwellings_needed is not None else None)
    return now, housing.gap_units


def run_effect_rows(results):
    """Pure (given the result objects): the effects table rows of a stored run."""
    from .views import change_tone  # same row shape and colours as the what-if

    rows = []
    for section, label, unit, decimals, get in RUN_ROWS:
        now, future = get(results)
        if now is None and future is None:
            continue
        change = round(future - now, decimals) if now is not None and future is not None else None
        rows.append({
            "section": section, "label": label, "unit": unit, "decimals": decimals,
            "now": None if now is None else round(now, decimals),
            "future": None if future is None else round(future, decimals),
            "change": change,
            "tone": change_tone(label, now, change),
        })
    return rows


def heat_inputs_changed(heat):
    """
    Inputs of the heat model (land cover, soil, DSM, buildings) that changed
    after the run's SOLWEIG runs finished: the panel then suggests rerunning
    the heat model. [] when nothing changed or the heat model did not run.
    """
    from urban_heat.models import HeatInputChange

    runs = [r for r in (heat.thermal_baseline, heat.thermal_run) if r is not None] if heat else []
    finished = [r.finished or r.created for r in runs]
    if not finished:
        return []
    since = min(finished)
    return sorted(set(HeatInputChange.objects.filter(changed_at__gt=since).values_list("input", flat=True)))


def water_inputs_changed(run):
    """Whether a fresh-water source of the run was recomputed after the run (its soil, land cover or rain)."""
    from watersupply.models import AvailableFreshWater

    when = run.recalculated or run.created
    ids = run.freshwater.values_list("source_id", flat=True)
    return AvailableFreshWater.objects.filter(pk__in=ids, last_updated__gt=when).exists()


def _layers(heat):
    """Map layer entries (Tmrt, UTCI, PET, WBGT) of the scenario's SOLWEIG run, when done."""
    from .views import raster_layer_entry

    run = heat.thermal_run if heat else None
    if run is None or run.status != "done":
        return []
    return [raster_layer_entry(r) for r in (run.mrt, run.utci, run.pet, run.wbgt) if r is not None and r.cog_path]


def _run_context(request, run):
    from urban_heat.calculations.indicators import get_thermal_indices

    results = _results(run)
    heat = results["heat"]
    unit = run.unit()
    suhii = None
    if unit is not None and getattr(unit, "geom", None) is not None:
        try:
            suhii = (get_thermal_indices(unit) or {}).get("suhii")
        except Exception:
            logger.exception("SUHII of %s", unit)
    pending = heat is not None and heat.status == "queued"
    return {
        "run": run,
        "scenario": run.describe(),
        "results": results,
        "rows": run_effect_rows(results),
        "heat": heat,
        "heat_pending": pending,
        "heat_inputs_changed": heat_inputs_changed(heat),
        "water_stale": water_inputs_changed(run),
        "layers": [{"entry": e, "json": json.dumps(e)} for e in _layers(heat)],
        "suhii": suhii,
        "is_staff": request.user.is_staff,
    }


def _bad(message):
    return HttpResponseBadRequest(message, content_type="text/plain; charset=utf-8")


def _when(value, heat, bbox):
    """The observed hour (local, aware) of a run; the season's default day when empty."""
    from django.utils import timezone

    from urban_heat.solweig.pipeline import centre, local_timezone
    from weather.calculations import climate

    tz = local_timezone(*centre(bbox)) if bbox else timezone.get_current_timezone()
    if value:
        try:
            when = datetime.fromisoformat(value)
        except ValueError:
            raise ValueError("The date must be YYYY-MM-DDTHH:MM (local time).") from None
    else:
        when = datetime(*climate.default_analysis_date(heat, timezone.now().year - 1))
    when = when.astimezone(tz) if when.tzinfo else when.replace(tzinfo=tz)
    when = when.replace(minute=0, second=0, microsecond=0)
    if not climate.month_fits_heat_mode(when.month, heat):
        raise ValueError(f"The date must lie in {climate.season_for(heat, when.month)} for "
                         f"'{climate.HEAT_MODES[heat]}'.")
    return when


def climate_runs(request):
    """GET: the unit's runs; POST: create a run."""
    if request.method == "POST":
        return climate_run_create(request)
    return climate_run_list(request)


def _run_json(run):
    """Ids and status of a run's heat model, for the Thermal Comfort tool."""
    heat = _related(run, "heat")
    return {
        "id": run.pk, "label": run.describe()["short"], "heat_label": run.describe()["heat_label"],
        "heat_status": heat.status if heat else None, "heat_message": heat.message if heat else "",
        "thermal_run": heat.thermal_run_id if heat else None,
        "thermal_baseline": heat.thermal_baseline_id if heat else None,
        "detail_url": f"/api/climate/runs/{run.pk}/",
    }


@require_POST
def climate_run_create(request):
    """Create a stored scenario run for the selected unit (staff): see the module docstring."""
    from administrative.admin_units import city_of, resolve_admin_unit
    from administrative.calculations.population import population_params
    from weather.calculations import climate
    from weather.models import ClimateScenarioRun

    if not request.user.is_staff:
        return HttpResponseForbidden("Log in as a staff user to store a scenario run.")
    data = request.POST
    key = climate.normalize(data.get("climate"))
    if key == climate.CURRENT:
        return _bad("Choose a future scenario first (2050 or 2100).")
    heat = climate.normalize_heat(data.get("heat"))
    level, location = data.get("level") or "", data.get("location") or ""
    unit = resolve_admin_unit(level, location)
    run_heat = data.get("run_heat", "1") not in ("0", "false", "")
    if unit is None or city_of(unit) is None:
        if not run_heat:
            return _bad("Select a city, district or neighbourhood on the map first.")
        # The Thermal Comfort tool may run a scenario for the view alone: no water or housing results.
        level = location = ""
    pop_scenario, pop_growth = population_params(data)
    bbox = area = met = None
    try:
        resolution = float(data.get("resolution") or DEFAULT_RESOLUTION_M)
    except ValueError:
        return _bad("The cell size must be a number.")
    try:
        if data.get("bbox"):
            from urban_heat.solweig.views import _bbox
            bbox = _bbox(data.get("bbox"))
        when = _when(data.get("datetime"), heat, bbox)
        if run_heat:
            if bbox is None:
                return _bad("The heat model needs the map view (bbox).")
            area, met = _heat_inputs(bbox, when, resolution, data)
        # Who the scenario's PET is felt by (the Thermal Comfort tool's person pill;
        # absent = the PET reference person). The comparison run must be for the same person.
        from urban_heat.solweig.views import _person
        person = _person(data) if run_heat else None
    except Exception as e:  # BadRequest, SolweigError, MetError, ValueError: shown as-is
        return _bad(str(e))

    run = ClimateScenarioRun.objects.create(
        scenario=key, heat_mode=heat, unit_level=level, unit_name=location,
        area=area, bbox_wgs84=bbox, population_variant=pop_scenario, population_growth_pct=pop_growth,
        baseline_year=climate.CURRENT_POPULATION_YEAR, analysis_datetime=when,
        parameters={"resolution": resolution, "run_heat": run_heat, "met_observed": met,
                    "met_source": data.get("met_source") or "knmi", "person": person},
        created_by=request.user)
    print(f"[climate] Scenario run {run.pk}: {key} {heat} for {level or 'the map view'} {location} stored")
    if data.get("format") == "json":   # the Thermal Comfort tool polls the scenario's SOLWEIG run itself
        return JsonResponse(_run_json(run), status=201)
    response = render(request, "mainMap/partials/climate_run.html", _run_context(request, run))
    response["HX-Trigger"] = "climate-run-changed"
    return response


def _fill_missing_met(run):
    """
    A run stored while SOLWEIG was missing has no observed weather (_heat_inputs
    skips the fetch), so a rerun would fail at once. Fetch it now from the
    run's recorded source, view and hour, and store it in run.parameters with
    update() (no receivers: the rerun queues the heat model itself).
    """
    from weather.models import ClimateScenarioRun

    params = dict(run.parameters or {})
    if params.get("met_observed") or not params.get("run_heat", True):
        return
    if not run.bbox_wgs84 or run.analysis_datetime is None:
        raise ValueError("The run has no map view or hour for the heat model.")
    source = params.get("met_source") or "knmi"
    if source == "manual":
        raise ValueError("This run's weather was entered by hand and was not stored: start a new run.")
    resolution = float(params.get("resolution") or DEFAULT_RESOLUTION_M)
    area, met = _heat_inputs(list(run.bbox_wgs84), run.analysis_datetime, resolution, {"met_source": source})
    if met is None:
        return   # SOLWEIG still missing and no weather: queue_scenario_heat records why
    params["met_observed"] = met
    ClimateScenarioRun.objects.filter(pk=run.pk).update(parameters=params, area=area)
    run.parameters, run.area = params, area


def _heat_inputs(bbox, when, resolution, data):
    """(area, observed met dict) of the heat model: the SOLWEIG plan of the view and the hour's weather."""
    from datetime import timezone as tz

    from physicalEnv.calculations.svf import _storage_box, wgs84_to_storage
    from urban_heat.solweig import inputs, met as met_module, pipeline
    from urban_heat.solweig.views import DAY_FIELDS, MET_FIELDS, _number, _optional_number

    available = pipeline.solweig_available()
    if available:
        plan = inputs.plan(wgs84_to_storage(bbox), cell=resolution)   # refuse a too-large view now
    source = data.get("met_source") or "knmi"
    lon, lat = pipeline.centre(bbox)
    try:
        if source == "manual":
            met = met_module.Met(**{n: _number(data, n, d, lo, hi, u) for n, d, lo, hi, u in MET_FIELDS},
                                 **{n: _optional_number(data, n, lo, hi, u) for n, lo, hi, u in DAY_FIELDS},
                                 source=(data.get("met_label") or "manual")[:60])
        else:
            fetch = met_module.era5_hourly if source == "era5" else met_module.knmi_hourly
            met, _station = fetch(when.astimezone(tz.utc), lon, lat)
    except Exception:
        if available:
            raise
        # SOLWEIG missing: the run is stored anyway (its heat results say so);
        # a rerun fetches the weather again (_fill_missing_met).
        logger.warning("Weather of the scenario run's hour not fetched", exc_info=True)
        met = None
    if not available:
        # Keep the weather, so "Rerun heat simulation" works once SOLWEIG is installed.
        return _storage_box(wgs84_to_storage(bbox)), met.as_dict() if met else None
    return _storage_box(plan["covered"]), met.as_dict()


@require_GET
def climate_run_list(request):
    """The stored runs of a unit (newest first)."""
    from weather.models import ClimateScenarioRun

    runs = ClimateScenarioRun.objects.filter(
        unit_level=request.GET.get("level") or "", unit_name=request.GET.get("location") or "")[:20]
    return render(request, "mainMap/partials/climate_run_list.html",
                  {"runs": runs, "is_staff": request.user.is_staff})


@require_GET
def climate_run_detail(request, run_id):
    from weather.models import ClimateScenarioRun

    run = get_object_or_404(ClimateScenarioRun, pk=run_id)
    return render(request, "mainMap/partials/climate_run.html", _run_context(request, run))


@require_POST
def climate_run_recalculate(request, run_id):
    """Re-save the run: every receiver recomputes its results from today's data (not the heat model)."""
    from django.utils import timezone

    from weather.models import ClimateScenarioRun

    if not request.user.is_staff:
        return HttpResponseForbidden("Staff only.")
    run = get_object_or_404(ClimateScenarioRun, pk=run_id)
    run.recalculated = timezone.now()
    run.save()
    response = render(request, "mainMap/partials/climate_run.html", _run_context(request, run))
    response["HX-Trigger"] = "climate-run-changed"
    return response


def _delete_heat_outputs(run):
    """The run's SOLWEIG runs and their rasters (COG files go with the post_delete receiver)."""
    from urban_heat.models import PET, UTCI, MeanRadiantTemperature, ThermalComfortRun, WetBulbGlobeTemperature

    for model in (MeanRadiantTemperature, UTCI, PET, WetBulbGlobeTemperature):
        for row in model.objects.filter(climate_run=run).defer("raster"):
            row.delete()
    ThermalComfortRun.objects.filter(climate_run=run).delete()


@require_POST
def climate_run_heat(request, run_id):
    """Rerun the heat model of a run (after land cover, soil, DSM or building changes)."""
    from urban_heat.models import ScenarioHeat
    from urban_heat.solweig.scenario import queue_scenario_heat
    from weather.models import ClimateScenarioRun

    if not request.user.is_staff:
        return HttpResponseForbidden("Staff only.")
    run = get_object_or_404(ClimateScenarioRun, pk=run_id)
    if run.thermal_runs_active():
        return _bad("The heat model of this run is still running.")
    try:
        _fill_missing_met(run)
    except Exception as e:  # SolweigError, MetError, ValueError: shown as-is
        return _bad(str(e))
    _delete_heat_outputs(run)
    heat, _ = ScenarioHeat.objects.get_or_create(run=run)
    heat.thermal_baseline = heat.thermal_run = None
    for name in ("tmrt", "utci", "pet", "wbgt"):
        setattr(heat, f"{name}_now", None)
        setattr(heat, f"{name}_scenario", None)
    heat.status = "pending"
    heat.save()
    queue_scenario_heat(heat)
    response = render(request, "mainMap/partials/climate_run.html", _run_context(request, run))
    response["HX-Trigger"] = "climate-run-changed"
    return response


@require_POST
def climate_run_delete(request, run_id):
    from weather.models import ClimateScenarioRun

    if not request.user.is_staff:
        return HttpResponseForbidden("Staff only.")
    run = get_object_or_404(ClimateScenarioRun, pk=run_id)
    if run.thermal_runs_active():
        return _bad("Wait until the heat model of this run has finished.")
    keys = [entry.get("key") for entry in _layers(_related(run, "heat"))]
    _delete_heat_outputs(run)
    run.delete()
    response = HttpResponse("")
    response["HX-Trigger"] = json.dumps({"climate-run-changed": None, "climate-run-deleted": {"layers": keys}})
    return response
