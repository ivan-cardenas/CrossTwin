"""
Cross-model updates for the housing demand chain (DPSIR / core/DAG.dot).

Dependency chain implemented here (source -> dependent):

    City population (save, or the Neighborhood->District->City cascade)
    PopulationProjection (CBS median forecast)
    HouseholdSize (CBS persons per home, per city and year)
        -> HousingSupplyDemand.demand_units  (population / persons per home)
        -> Property.residents                (every dwelling holds that average)
    Property saved/created (a new dwelling)
        -> its own residents
    HousingProject completed with a generated layout (New_Units)
        -> builtup streets, buildings and dwellings (builtup/calculations/materialise.py)

Conventions (see administrative/signals.py and watersupply/signals.py): every
receiver has a dispatch_uid and skips raw saves, dependents are refreshed by
re-saving them so their own save() logic runs, and a failure while refreshing
is logged, never raised. Nothing here writes back to a model that feeds the
chain, so there are no loops. Property.residents of a whole city is written with
one queryset.update() (no signals), so the layer cache is bumped by hand.
"""
import logging
import threading
from contextlib import contextmanager

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from administrative.models import City, PopulationProjection
from administrative.calculations.population import DEFAULT_SCENARIO
from administrative.signals import city_population_changed
from builtup.models import Property
from builtup.signals import residents_changed
from core.cache import bump_layer_version

from .models import HouseholdSize, HousingProject, HousingSupplyDemand, ResidentialProperty

logger = logging.getLogger(__name__)

DWELLING = "Residential function"   # BAG woonfunctie label in Property.usageFunction

# Per-thread set of cities whose housing refresh is postponed; None when not deferring.
_deferred = threading.local()


# ── helpers ──────────────────────────────────────────────────────────

def _resave(objects):
    """save() each object so its own derived fields run; a bad record never blocks the source save."""
    for obj in objects:
        try:
            obj.save()
        except ValidationError as exc:
            logger.warning("Could not refresh %s: %s", obj, exc)


def _dwellings_of_city(city_id):
    return Property.objects.filter(
        usageFunction__contains=[DWELLING],
        building__neighborhood__district__city_id=city_id,
    )


def _set_city_residents(city_id):
    """
    Every dwelling of the city is occupied by the city's latest average household
    size (None without one). One set-based UPDATE, so no per-property signal.

    DAG edge: Household_Size -> Property
    """
    size = HouseholdSize.latest(city_id)
    changed = _dwellings_of_city(city_id).update(residents=size.average_size if size else None)
    if changed:
        bump_layer_version(Property, ResidentialProperty)
        residents_changed.send(sender=Property, city_id=city_id)


def _rederive_household_sizes(city_id):
    """
    Refill HouseholdSize.population / average_size from the stored forecast, for
    a forecast imported after the households (or corrected since). A queryset
    update(), not save(): re-saving would fire household_size_changed, which
    comes back here.

    DAG edge: Total_Population -> Household_Size
    """
    for row in HouseholdSize.objects.filter(city_id=city_id):
        population, size = row.derive()
        if (population, size) != (row.population, row.average_size):
            HouseholdSize.objects.filter(pk=row.pk).update(population=population, average_size=size)


def _refresh_city_housing(city_id):
    """Recompute the city's household sizes, its demand records and the residents of its dwellings."""
    pending = getattr(_deferred, "pending", None)
    if pending is not None:
        pending.add(city_id)
        return
    _rederive_household_sizes(city_id)
    _resave(HousingSupplyDemand.objects.filter(city_id=city_id))
    _set_city_residents(city_id)


@contextmanager
def deferred_housing_refresh():
    """
    Postpone the housing refresh until the block ends, then run it once per
    affected city. A CBS forecast import saves ~84 projection rows per city and a
    property import thousands of dwellings; without this each would redo the
    city's demand and the whole city's residents. Nested uses defer to the
    outermost one.
    """
    if getattr(_deferred, "pending", None) is not None:
        yield
        return

    _deferred.pending = set()
    try:
        yield
    except BaseException:
        pending, _deferred.pending = _deferred.pending, None
        try:
            _flush_housing_refresh(pending)
        except Exception:
            # e.g. the transaction is already broken; don't mask the original error
            logger.exception("Deferred housing refresh failed after an aborted block")
        raise
    else:
        pending, _deferred.pending = _deferred.pending, None
        _flush_housing_refresh(pending)


def _flush_housing_refresh(city_ids):
    for city_id in city_ids:
        _refresh_city_housing(city_id)


# ── population -> housing demand ─────────────────────────────────────

@receiver(post_save, sender=City, dispatch_uid="housing_city_saved")
def city_saved(sender, instance, raw=False, **kwargs):
    """DAG edge: Total_Population -> Housing_Demand"""
    if not raw:
        _refresh_city_housing(instance.pk)


@receiver(city_population_changed, dispatch_uid="housing_city_population_changed")
def city_population_cascaded(sender, city_id, **kwargs):
    """
    The population cascade uses queryset.update(), which never fires post_save(City).

    DAG edge: Total_Population -> Housing_Demand
    """
    _refresh_city_housing(city_id)


@receiver(post_save, sender=PopulationProjection, dispatch_uid="housing_projection_saved")
@receiver(post_delete, sender=PopulationProjection, dispatch_uid="housing_projection_deleted")
def projection_changed(sender, instance, raw=False, **kwargs):
    """
    The stored demand uses the median forecast of each record's year
    (housing/calculations/chain.py::baseline_population); low/high only feed the dashboard's what-if.

    DAG edges: Population_Growth -> Total_Population -> Housing_Demand
    """
    if raw or instance.scenario != DEFAULT_SCENARIO:
        return
    _refresh_city_housing(instance.city_id)


# ── household size -> demand, residents ──────────────────────────────

@receiver(post_save, sender=HouseholdSize, dispatch_uid="housing_household_size_saved")
@receiver(post_delete, sender=HouseholdSize, dispatch_uid="housing_household_size_deleted")
def household_size_changed(sender, instance, raw=False, **kwargs):
    """
    A year without its own record uses the closest one (HouseholdSize.for_year), so
    one record can feed the demand of many years: refresh the whole city.

    DAG edges: Household_Size -> Housing_Demand, Household_Size -> Property
    """
    if not raw:
        _refresh_city_housing(instance.city_id)


# ── a dwelling is saved -> its residents ─────────────────────────────

# The proxy sends post_save with itself as sender, so both classes are connected.
@receiver(post_save, sender=Property, dispatch_uid="housing_property_saved")
@receiver(post_save, sender=ResidentialProperty, dispatch_uid="housing_residential_property_saved")
def property_saved(sender, instance, raw=False, **kwargs):
    """
    A new or edited property gets the city's average only when it is a dwelling.
    Under a bulk import the city is queued instead and refreshed once.

    DAG edge: Household_Size -> Property
    """
    if raw:
        return
    city_id = (Property.objects.filter(pk=instance.pk)
               .values_list('building__neighborhood__district__city_id', flat=True).first())
    if city_id is None:
        return
    if getattr(_deferred, "pending", None) is not None:
        _deferred.pending.add(city_id)
        return
    size = HouseholdSize.latest(city_id) if DWELLING in (instance.usageFunction or []) else None
    residents = size.average_size if size else None
    if instance.residents != residents:
        Property.objects.filter(pk=instance.pk).update(residents=residents)
        instance.residents = residents
        bump_layer_version(Property, ResidentialProperty)
        residents_changed.send(sender=Property, city_id=city_id)


# ── New_Units -> Buildings ───────────────────────────────────────────

_LAYOUT_FIELDS = ("status", "generator_params", "geom", "project_name", "year_expected_completion")


@receiver(pre_save, sender=HousingProject, dispatch_uid="housing_project_presave")
def project_presave(sender, instance, raw=False, **kwargs):
    """Remember what the stored project's layout depends on, so post_save rebuilds only when it changed."""
    if raw or instance.pk is None:
        return
    instance._stored_layout = HousingProject.objects.filter(pk=instance.pk).values(*_LAYOUT_FIELDS).first()


def _layout_changed(instance):
    stored = getattr(instance, "_stored_layout", None)
    if stored is None:
        return True
    for name in _LAYOUT_FIELDS:
        old, new = stored[name], getattr(instance, name)
        if name == "geom":
            if (old is None) != (new is None) or (old is not None and not old.equals_exact(new, tolerance=1e-6)):
                return True
        elif old != new:
            return True
    return False


@receiver(post_save, sender=HousingProject, dispatch_uid="housing_project_saved")
def project_saved(sender, instance, created, raw=False, **kwargs):
    """
    DAG edge: New_Units -> Buildings. A completed housing project with a
    generated layout (generator_params) becomes streets, buildings and
    dwellings (builtup/calculations/materialise.py::materialise); a changed
    outline or parameters rebuild them; a project set back to planned, or
    whose layout was cleared, loses them (materialise.remove). The outcome is
    left on the instance (`_layout_result` / `_layout_error`) for the
    generator view; a failure is logged and never blocks the project's save.
    """
    from builtup.calculations import materialise

    if raw or not instance.geom:
        return
    stored = getattr(instance, "_stored_layout", None)
    was_built = bool(stored and stored["status"] == "completed" and stored["generator_params"])
    build = instance.status == "completed" and bool(instance.generator_params)
    if not build and not was_built:
        return
    if build and not created and not _layout_changed(instance):
        return
    try:
        with transaction.atomic():
            if build:
                instance._layout_result = materialise.materialise(
                    instance.pk, instance.geom, instance.generator_params,
                    name=instance.project_name, completion_year=instance.year_expected_completion)
            else:
                materialise.remove(instance.pk)
                instance._layout_result = None
    except Exception as exc:   # noqa: BLE001 - never block the project save
        logger.exception("Generated layout of housing project %s failed", instance.pk)
        instance._layout_error = str(exc)


@receiver(post_delete, sender=HousingProject, dispatch_uid="housing_project_deleted")
def project_deleted(sender, instance, **kwargs):
    """
    DAG edge: New_Units -> Buildings (inverse). Deleting a project deletes its
    generated streets, buildings and dwellings. Skipped while the editor's
    backup restore runs: it removes the journalled rows itself.
    """
    from builtup.calculations import materialise
    from core.editing import is_restoring

    if is_restoring():
        return
    try:
        with transaction.atomic():
            materialise.remove(instance.pk)
    except Exception:   # noqa: BLE001
        logger.exception("Removing the generated layout of housing project %s failed", instance.pk)
