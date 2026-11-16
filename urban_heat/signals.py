"""
Receivers of the urban heat module (core/DAG.dot), for stored climate
scenario runs (weather.ClimateScenarioRun):

    ClimateScenarioRun saved -> ScenarioHeat (observed + scenario met);
        created -> its scenario SOLWEIG run is queued (solweig/scenario.py)
    ThermalComfortRun of a run done / failed -> ScenarioHeat means
    scenario raster deleted -> its COG file removed
    land cover, soil, DSM, buildings changed -> HeatInputChange (the panel
        then suggests rerunning a scenario's heat model)

Every receiver has a dispatch_uid and skips raw saves; failures are logged,
never raised. Scenario runs are never bulk-written, so nothing is deferred.
"""
import logging
import os

from django.core.exceptions import ValidationError
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import (
    PET, UTCI, HeatInputChange, MeanRadiantTemperature, ScenarioHeat, ThermalComfortRun,
    WetBulbGlobeTemperature,
)

logger = logging.getLogger(__name__)


def _resave(objects):
    """save() each object so its own derived fields and downstream signals run."""
    for obj in objects:
        try:
            obj.save()
        except ValidationError as exc:
            logger.warning("Could not refresh %s: %s", obj, exc)


@receiver(post_save, sender="weather.ClimateScenarioRun", dispatch_uid="heat_climate_run_saved")
def climate_run_saved(sender, instance, created=False, raw=False, **kwargs):
    """
    DAG edge: Climate_Change -> Meteorology (-> Tmrt, UTCI, PET, WBGT via SOLWEIG)
    Re-saves the run's ScenarioHeat (its save() moves the observed hour into
    the scenario). Only a new run queues the heat model: "Recalculate"
    never restarts GPU work; "Rerun heat model" does that explicitly.
    """
    from .solweig.scenario import queue_scenario_heat

    if raw or instance.status == "failed":
        return
    heat, _ = ScenarioHeat.objects.get_or_create(run=instance)
    _resave([heat])
    if created:
        try:
            queue_scenario_heat(heat)
        except Exception:
            logger.exception("Could not queue the heat model of climate run %s", instance.pk)


@receiver(post_save, sender=ThermalComfortRun, dispatch_uid="heat_thermal_run_saved")
def thermal_run_saved(sender, instance, raw=False, **kwargs):
    """DAG edges: Tmrt, UTCI, PET, WBGT -> ScenarioHeat (means of a finished scenario SOLWEIG run)."""
    if raw or instance.climate_run_id is None or instance.status not in ("done", "failed"):
        return
    _resave(ScenarioHeat.objects.filter(run_id=instance.climate_run_id))


def _drop_cog(sender, instance, **kwargs):
    """A scenario raster deleted with its run: remove its COG file too."""
    path = getattr(instance, "cog_path", None)
    if getattr(instance, "climate_run_id", None) and path and os.path.exists(path):
        try:
            os.unlink(path)
        except OSError as e:
            logger.warning("Could not delete COG %s: %s", path, e)


for _model in (MeanRadiantTemperature, UTCI, PET, WetBulbGlobeTemperature):
    post_delete.connect(_drop_cog, sender=_model, weak=False,
                        dispatch_uid=f"heat_scenario_cog_deleted_{_model.__name__}")


# ── Heat model inputs changed (the "rerun the heat model" marker) ─────

# Seconds between two writes of the same input's marker: a bulk import of
# thousands of rows writes it about once, not once per row.
MARK_EVERY_S = 60
_last_mark = {}


def mark_heat_input_changed(name):
    """Record that a heat-model input (land cover, soil, DSM, buildings) changed now."""
    now = timezone.now()
    last = _last_mark.get(name)
    if last is not None and (now - last).total_seconds() < MARK_EVERY_S:
        return
    _last_mark[name] = now
    try:
        HeatInputChange.objects.update_or_create(input=name, defaults={"changed_at": now})
    except Exception:
        logger.exception("Could not record the change of %s", name)


_INPUTS = {
    "physicalEnv.LandCoverVector": "land cover",
    "physicalEnv.SoilArea": "soil",
    "physicalEnv.SoilType": "soil",
    "physicalEnv.DigitalSurfaceModel": "DSM",
    "physicalEnv.DSMEdit": "DSM",
    "builtup.Building": "buildings",
}


def _input_changed(sender, raw=False, **kwargs):
    if raw:
        return
    mark_heat_input_changed(_INPUTS[sender._meta.label])


for _label in _INPUTS:
    post_save.connect(_input_changed, sender=_label, weak=False, dispatch_uid=f"heat_input_saved_{_label}")
    post_delete.connect(_input_changed, sender=_label, weak=False, dispatch_uid=f"heat_input_deleted_{_label}")
