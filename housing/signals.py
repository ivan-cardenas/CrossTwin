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
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from administrative.models import City, PopulationProjection
from administrative.population import DEFAULT_SCENARIO
from administrative.signals import city_population_changed
from builtup.models import Property
from core.cache import bump_layer_version

from .models import HouseholdSize, HousingSupplyDemand, ResidentialProperty

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
    (housing/chain.py::baseline_population); low/high only feed the dashboard's what-if.

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
