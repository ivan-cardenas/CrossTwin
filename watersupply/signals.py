"""
Cross-model updates for the water supply chain (DPSIR / core/DAG.dot).

Dependency chain implemented here (source -> dependent):

    City population (save, or the Neighborhood->District->City cascade)
    PopulationProjection (CBS median forecast = the baseline of each year)
        -> ConsumptionCapita.total_consumption_m3_yr
        -> TotalWaterDemand -> SupplySecurity
        -> MeteredResidential -> OPEX
    ExtractionWater / ImportedWater
        -> TotalWaterProduction (also on its M2M source links)
        -> OPEX, SupplySecurity
    Watershed, AvailableFreshWater (which watershed a well's water belongs to),
    and the population of every city sharing a watershed (it sets each city's
    share of the watershed's extraction) -> SupplySecurity
    WaterTreatment, MeteredResidential, PipeNetwork -> OPEX
    PipeNetwork, UsersLocation -> CoverageWaterSupply
    NonRevenueWater -> ILI of the same-year Real-loss records

Conventions (see administrative/signals.py): every receiver has a dispatch_uid,
dependents are refreshed by re-saving them so their own save() logic (and the
next link in the chain) runs, and nothing here writes back to a model that
feeds the chain, so there are no loops. A failure while refreshing a dependent
is logged, never raised, so it cannot block the save that triggered it.

OPEX, ExtractionWater, MeteredResidential and ImportedWater carry no year, so
a change to them refreshes only the *latest* OPEX / SupplySecurity record of
each affected unit (older years are historical snapshots).
"""
import logging
import threading
from contextlib import contextmanager

from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from administrative.models import City, PopulationProjection
from administrative.population import DEFAULT_SCENARIO
from administrative.signals import city_population_changed

from .models import (
    AvailableFreshWater, ConsumptionCapita, CoverageWaterSupply, ExtractionWater,
    ImportedWater, MeteredResidential, NonRevenueWater, OPEX, PipeNetwork,
    SupplySecurity, TotalWaterDemand, TotalWaterProduction, UsersLocation,
    WaterTreatment, Watershed,
)

logger = logging.getLogger(__name__)


# ── helpers ──────────────────────────────────────────────────────────

def _resave(objects):
    """save() each object so its own derived fields and downstream signals run."""
    for obj in objects:
        try:
            obj.save()
        except ValidationError as exc:
            logger.warning("Could not refresh %s: %s", obj, exc)


def _refresh_latest_opex():
    _resave(OPEX.objects.order_by('-year', '-id')[:1])


def _refresh_latest_supply_security(city_ids=None):
    """Re-save the most recent SupplySecurity record of each given city (all if None)."""
    pending = getattr(_deferred, "security", None)
    if pending is not None:
        pending.update(City.objects.values_list('pk', flat=True) if city_ids is None else city_ids)
        return
    if city_ids is None:
        city_ids = City.objects.values_list('pk', flat=True)
    for city_id in city_ids:
        _resave(SupplySecurity.objects.filter(city_id=city_id).order_by('-year', '-id')[:1])


def _cities_in_watersheds(watershed_ids):
    """Cities overlapping the given watersheds: those that may receive their water."""
    city_ids = set()
    for watershed in Watershed.objects.filter(pk__in=watershed_ids).only('geom'):
        city_ids.update(City.objects.filter(geom__intersects=watershed.geom).values_list('pk', flat=True))
    return city_ids


def _watersheds_of_city(city_id):
    return Watershed.objects.filter(
        geom__intersects=City.objects.filter(pk=city_id).values('geom')[:1],
    ).values_list('pk', flat=True)


def _refresh_watershed_neighbours(city_id):
    """
    A city's population sets its share of the extraction of every watershed it
    lies in, so the other cities of those watersheds get a different share too.
    """
    _refresh_latest_supply_security(_cities_in_watersheds(list(_watersheds_of_city(city_id))) - {city_id})


# ── population -> consumption -> demand -> supply security ───────────

# Per-thread set of cities whose water refresh is postponed; None when not deferring.
_deferred = threading.local()


@contextmanager
def deferred_water_refresh():
    """
    Postpone the population -> water refresh until the block ends, then run it
    once per affected city. A CBS forecast import saves ~28 years x 3 variants
    per city; without this each median-forecast row would re-run the whole
    water chain of its city. Nested uses defer to the outermost one.
    """
    if getattr(_deferred, "pending", None) is not None:
        yield
        return

    _deferred.pending = set()
    _deferred.security = set()
    try:
        yield
    except BaseException:
        pending, security = _deferred.pending, _deferred.security
        _deferred.pending = _deferred.security = None
        try:
            _flush_water_refresh(pending, security)
        except Exception:
            # e.g. the transaction is already broken; don't mask the original error
            logger.exception("Deferred water refresh failed after an aborted block")
        raise
    else:
        pending, security = _deferred.pending, _deferred.security
        _deferred.pending = _deferred.security = None
        _flush_water_refresh(pending, security)


def _flush_water_refresh(city_ids, security_city_ids=()):
    for city_id in city_ids:
        _refresh_city_water(city_id)
    # cities whose chain was just re-run already have a fresh SupplySecurity
    _refresh_latest_supply_security(set(security_city_ids) - set(city_ids))


def _refresh_city_water(city_id):
    """
    Re-save the city's ConsumptionCapita records: that recalculates
    total_consumption_m3_yr with the new baseline population and, through the
    ConsumptionCapita receiver below, TotalWaterDemand and MeteredResidential.
    """
    pending = getattr(_deferred, "pending", None)
    if pending is not None:
        pending.add(city_id)
        return
    _resave(ConsumptionCapita.objects.filter(city_id=city_id))


@receiver(post_save, sender=City, dispatch_uid="water_city_saved")
def city_saved(sender, instance, raw=False, **kwargs):
    if not raw:
        _refresh_city_water(instance.pk)
        _refresh_watershed_neighbours(instance.pk)


@receiver(city_population_changed, dispatch_uid="water_city_population_changed")
def city_population_cascaded(sender, city_id, **kwargs):
    """
    The population cascade uses queryset.update(), which never fires post_save(City).
    Neighborhood populations also set each city's share of its watersheds' extraction.

    DAG edge: Total_Population -> Total_Water_Prod (watershed share) -> Supply_Security
    """
    _refresh_city_water(city_id)
    _refresh_watershed_neighbours(city_id)


@receiver(post_save, sender=PopulationProjection, dispatch_uid="water_projection_saved")
@receiver(post_delete, sender=PopulationProjection, dispatch_uid="water_projection_deleted")
def projection_changed(sender, instance, raw=False, **kwargs):
    """
    The stored chain uses the median forecast of each record's year as its
    population (watersupply/chain.py::baseline_population), so a new or
    corrected forecast is a population change. The low/high variants only feed
    the dashboard's what-if, which is computed per request.

    DAG edges: Population_Growth -> Total_Population -> Total_Water_Demand
    """
    if raw or instance.scenario != DEFAULT_SCENARIO:
        return
    _refresh_city_water(instance.city_id)


@receiver(post_save, sender=ConsumptionCapita, dispatch_uid="water_consumption_saved")
@receiver(post_delete, sender=ConsumptionCapita, dispatch_uid="water_consumption_deleted")
def consumption_saved(sender, instance, raw=False, **kwargs):
    """
    A year without its own record uses the closest earlier one
    (ConsumptionCapita.for_year), so a record can feed the demand of many
    years: refresh every demand record of the city.

    DAG edge: ConsumptionCapita -> Total_Water_Demand
    """
    if raw:
        return
    _resave(TotalWaterDemand.objects.filter(city_id=instance.city_id))
    _resave(MeteredResidential.objects.filter(
        userLocation__neighborhood__district__city_id=instance.city_id))


@receiver(post_save, sender=TotalWaterDemand, dispatch_uid="water_demand_saved")
def demand_saved(sender, instance, raw=False, **kwargs):
    if not raw:
        _resave(SupplySecurity.objects.filter(city_id=instance.city_id, year=instance.year))


# ── extraction / imported water -> production, OPEX, supply security ─

@receiver(post_save, sender=ExtractionWater, dispatch_uid="water_extraction_saved")
@receiver(post_delete, sender=ExtractionWater, dispatch_uid="water_extraction_deleted")
def extraction_changed(sender, instance, raw=False, **kwargs):
    if raw:
        return
    _resave(TotalWaterProduction.objects.filter(source=instance.source_id).distinct())
    _refresh_latest_opex()
    # The well's water is shared by every city of its watershed, wherever the well lies
    watershed_id = (
        AvailableFreshWater.objects.filter(pk=instance.source_id)
        .values_list('watershed_id', flat=True).first()
        or Watershed.objects.filter(geom__contains=instance.geom).values_list('pk', flat=True).first()
    )
    if watershed_id is not None:
        city_ids = _cities_in_watersheds([watershed_id])
    else:
        city_ids = City.objects.filter(geom__intersects=instance.geom).values_list('pk', flat=True)
    _refresh_latest_supply_security(list(city_ids))


@receiver(post_save, sender=Watershed, dispatch_uid="water_watershed_saved")
@receiver(post_delete, sender=Watershed, dispatch_uid="water_watershed_deleted")
@receiver(post_save, sender=AvailableFreshWater, dispatch_uid="water_freshwater_saved")
@receiver(post_delete, sender=AvailableFreshWater, dispatch_uid="water_freshwater_deleted")
def watershed_changed(sender, instance, raw=False, **kwargs):
    """
    Watersheds (and which watershed a source belongs to) decide which cities
    share a well's water. Rare edits, so every city's latest record is refreshed.

    DAG edge: Available_FW -> Total_Extraction -> Total_Water_Prod -> Supply_Security
    """
    if not raw:
        _refresh_latest_supply_security()


@receiver(post_save, sender=ImportedWater, dispatch_uid="water_imported_saved")
@receiver(post_delete, sender=ImportedWater, dispatch_uid="water_imported_deleted")
def imported_changed(sender, instance, raw=False, **kwargs):
    if raw:
        return
    if instance.pk:
        _resave(TotalWaterProduction.objects.filter(source_imported=instance.pk).distinct())
    _refresh_latest_opex()
    _refresh_latest_supply_security()  # imported water supplies every city


@receiver(m2m_changed, sender=TotalWaterProduction.source.through,
          dispatch_uid="water_production_sources_changed")
@receiver(m2m_changed, sender=TotalWaterProduction.source_imported.through,
          dispatch_uid="water_production_imported_changed")
def production_links_changed(sender, instance, action, reverse, pk_set, **kwargs):
    """Sources are attached after the row is created, so recalculate once they are."""
    if action not in ('post_add', 'post_remove', 'post_clear'):
        return
    if reverse:
        _resave(TotalWaterProduction.objects.filter(pk__in=pk_set or []))
    else:
        _resave([instance])


# ── other OPEX inputs ────────────────────────────────────────────────

@receiver(post_save, sender=MeteredResidential, dispatch_uid="water_metered_saved")
@receiver(post_delete, sender=MeteredResidential, dispatch_uid="water_metered_deleted")
def metered_changed(sender, instance, raw=False, **kwargs):
    if not raw:
        _refresh_latest_opex()


@receiver(post_save, sender=WaterTreatment, dispatch_uid="water_treatment_saved")
@receiver(post_delete, sender=WaterTreatment, dispatch_uid="water_treatment_deleted")
def treatment_changed(sender, instance, raw=False, **kwargs):
    if not raw:
        _resave(OPEX.objects.filter(year=instance.year))


# ── network -> coverage, OPEX ────────────────────────────────────────

@receiver(post_save, sender=PipeNetwork, dispatch_uid="water_pipe_saved")
@receiver(post_delete, sender=PipeNetwork, dispatch_uid="water_pipe_deleted")
def pipe_changed(sender, instance, raw=False, **kwargs):
    if raw:
        return
    _resave(CoverageWaterSupply.objects.filter(
        city__isnull=False, city__geom__intersects=instance.geom))
    _refresh_latest_opex()


@receiver(post_save, sender=UsersLocation, dispatch_uid="water_users_saved")
@receiver(post_delete, sender=UsersLocation, dispatch_uid="water_users_deleted")
def users_changed(sender, instance, raw=False, **kwargs):
    if not raw:
        _resave(CoverageWaterSupply.objects.filter(
            city__isnull=False, city__district__neighborhood=instance.neighborhood_id
        ).distinct())


# ── non-revenue water -> ILI of the whole year ───────────────────────

@receiver(post_save, sender=NonRevenueWater, dispatch_uid="water_nrw_saved")
@receiver(post_delete, sender=NonRevenueWater, dispatch_uid="water_nrw_deleted")
def nrw_changed(sender, instance, raw=False, **kwargs):
    """
    ILI = CARL / UARL over all Real-loss records of the year, so every Real record
    of that year shares it. NonRevenueWater.save() only computes its own row;
    bring the siblings in line (update(): no save(), so no signal loop).
    """
    if raw:
        return
    real = NonRevenueWater.objects.filter(year=instance.year, type=NonRevenueWater.LossesTypes.Real)
    carl = sum(r.loss_Quantity_m3 for r in real)
    uarl = sum(r.loss_Quantity_m3 * r.UnavoidableLossses_PCT / 100 for r in real)
    ili = round(carl / uarl, 2) if uarl > 0 else None
    real.update(ILI=ili, last_updated=timezone.now())
