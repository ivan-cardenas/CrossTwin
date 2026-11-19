"""
The heat model of a stored climate scenario run (weather.ClimateScenarioRun,
urban_heat.ScenarioHeat): ONE SOLWEIG run over the run's map view and hour
with the observed weather moved into the scenario (ScenarioHeat.met_scenario).
The current-climate values come from an observed run of the same hour that
covers the view (find_baseline, e.g. one the Thermal Comfort tool made), so
no second run is started; without one the current column stays empty.
The scenario ThermalComfortRun carries `climate_run`, so its rasters never
replace observed ones (pipeline.replace_covered) and the dashboards skip them.

queue_scenario_heat is called by urban_heat/signals.py only when a run is
created (a staff POST): the one place a post_save starts GPU work (see
pipeline.py).
"""
import logging

logger = logging.getLogger(__name__)

INSTALL_HINT = "SOLWEIG is not installed on the server: uv sync --extra solweig"


def queue_scenario_heat(heat):
    """Queue the scenario's SOLWEIG run of `heat` (a ScenarioHeat); records why not otherwise."""
    from urban_heat.models import ThermalComfortRun

    from . import pipeline

    run = heat.run
    params = run.parameters or {}
    if not params.get("run_heat", True):
        heat.status, heat.message = "skipped", "Heat model not requested for this run."
    elif not pipeline.solweig_available():
        heat.status, heat.message = "unavailable", INSTALL_HINT
    elif run.area is None or not run.bbox_wgs84 or run.analysis_datetime is None or not heat.met_scenario:
        heat.status, heat.message = "failed", "The run has no map view, hour or observed weather for the heat model."
    else:
        resolution = float(params.get("resolution") or 2.0)
        heat.thermal_run = ThermalComfortRun.objects.create(
            area=run.area, bbox_wgs84=run.bbox_wgs84, date_time=run.analysis_datetime,
            met=heat.met_scenario, resolution=resolution, climate_run=run)
        pipeline.start_run(heat.thermal_run)
        heat.status, heat.message = "queued", ""
    heat.save()
    return heat


# Overlap an observed run must share with the scenario's view, as a share of
# both areas, to serve as its current-climate comparison (means over different
# areas do not compare; a run's stored area is its raster extent, snapped to
# the grid, so it differs a little from the requested view).
BASELINE_MIN_COVER = 0.9


def find_baseline(run):
    """
    The latest finished observed SOLWEIG run (no climate run) of the same hour
    sharing at least BASELINE_MIN_COVER of both areas with the run's view: the
    current-climate comparison of a scenario run. None without one.
    """
    from urban_heat.models import ThermalComfortRun

    if run.area is None or run.analysis_datetime is None or not run.area.area:
        return None
    candidates = (ThermalComfortRun.objects
                  .filter(climate_run__isnull=True, status="done", mrt__isnull=False,
                          date_time=run.analysis_datetime, area__intersects=run.area)
                  .order_by("-finished", "-pk").defer("inputs", "stats")[:20])
    for candidate in candidates:
        overlap = candidate.area.intersection(run.area).area
        if min(overlap / run.area.area, overlap / candidate.area.area) >= BASELINE_MIN_COVER:
            return ThermalComfortRun.objects.get(pk=candidate.pk)
    return None


def baseline_wbgt_mean(thermal):
    """
    Mean WBGT (°C) of an observed run that stored none: chain.wbgt_outdoor_c
    from its Tmrt raster and its met. None when the raster or met is missing.
    """
    import numpy as np

    from urban_heat.calculations.chain import wbgt_outdoor_c

    met = thermal.met or {}
    if thermal.mrt is None or any(met.get(k) is None for k in ("ta_c", "rh_pct", "wind_ms")):
        return None
    band = thermal.mrt.raster.bands[0]
    tmrt = np.asarray(band.data(), dtype="float64")
    if band.nodata_value is not None:
        tmrt = np.where(tmrt == band.nodata_value, np.nan, tmrt)
    wbgt = wbgt_outdoor_c(met["ta_c"], met["rh_pct"], met["wind_ms"], tmrt)
    valid = wbgt[np.isfinite(wbgt)]
    return round(float(valid.mean()), 2) if valid.size else None
