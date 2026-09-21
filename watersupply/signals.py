"""
Cross-model updates for the water supply chain (DPSIR / core/DAG.dot).

Dependency chain implemented here (source -> dependent):

    City population (save, or the Neighborhood->District->City cascade)
        -> ConsumptionCapita.total_consumption_m3_yr
        -> TotalWaterDemand -> SupplySecurity
        -> MeteredResidential -> OPEX
    ExtractionWater / ImportedWater
        -> TotalWaterProduction (also on its M2M source links)
        -> OPEX, SupplySecurity
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

from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from administrative.models import City
from administrative.signals import city_population_changed

from .models import (
    ConsumptionCapita, CoverageWaterSupply, ExtractionWater, ImportedWater,
    MeteredResidential, NonRevenueWater, OPEX, PipeNetwork, SupplySecurity,
    TotalWaterDemand, TotalWaterProduction, UsersLocation, WaterTreatment,
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
    if city_ids is None:
        city_ids = City.objects.values_list('pk', flat=True)
    for city_id in city_ids:
        _resave(SupplySecurity.objects.filter(city_id=city_id).order_by('-year', '-id')[:1])


# ── population -> consumption -> demand -> supply security ───────────

def _refresh_city_water(city_id):
    """
    Re-save the city's ConsumptionCapita records: that recalculates
    total_consumption_m3_yr with the new population and, through the
    ConsumptionCapita receiver below, TotalWaterDemand and MeteredResidential.
    """
    _resave(ConsumptionCapita.objects.filter(city_id=city_id))


@receiver(post_save, sender=City, dispatch_uid="water_city_saved")
def city_saved(sender, instance, raw=False, **kwargs):
    if not raw:
        _refresh_city_water(instance.pk)


@receiver(city_population_changed, dispatch_uid="water_city_population_changed")
def city_population_cascaded(sender, city_id, **kwargs):
    # The population cascade uses queryset.update(), which never fires post_save(City).
    _refresh_city_water(city_id)


@receiver(post_save, sender=ConsumptionCapita, dispatch_uid="water_consumption_saved")
def consumption_saved(sender, instance, raw=False, **kwargs):
    if raw:
        return
    _resave(TotalWaterDemand.objects.filter(city_id=instance.city_id, year=instance.year))
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
    city_ids = City.objects.filter(geom__intersects=instance.geom).values_list('pk', flat=True)
    _refresh_latest_supply_security(list(city_ids))


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
