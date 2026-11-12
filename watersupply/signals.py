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
    SoilArea, SoilType, LandCoverVector, GroundwaterDepth (soil x land cover)
    and daily Meteorology (rain, reference ET)
        -> AvailableFreshWater infiltration rate, recharge depth and yield

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
from administrative.calculations.population import DEFAULT_SCENARIO
from administrative.signals import city_population_changed
from physicalEnv.calculations.landcover import landcover_created
from physicalEnv.models import GroundwaterDepth, LandCoverVector, SoilArea, SoilType
from weather.knmi import daily_water_balance_changed
from weather.models import Meteorology

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
    _deferred.freshwater = set()
    try:
        yield
    except BaseException:
        pending, security, freshwater = _deferred.pending, _deferred.security, _deferred.freshwater
        _deferred.pending = _deferred.security = _deferred.freshwater = None
        try:
            _flush_water_refresh(pending, security, freshwater)
        except Exception:
            # e.g. the transaction is already broken; don't mask the original error
            logger.exception("Deferred water refresh failed after an aborted block")
        raise
    else:
        pending, security, freshwater = _deferred.pending, _deferred.security, _deferred.freshwater
        _deferred.pending = _deferred.security = _deferred.freshwater = None
        _flush_water_refresh(pending, security, freshwater)


def _flush_water_refresh(city_ids, security_city_ids=(), freshwater_ids=()):
    security_city_ids = set(security_city_ids)
    if freshwater_ids:
        # Each source's post_save refreshes every city's supply security:
        # collect those requests and run them once with the others below.
        _deferred.security = set()
        try:
            _resave(AvailableFreshWater.objects.filter(pk__in=freshwater_ids))
        finally:
            security_city_ids |= _deferred.security
            _deferred.security = None
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
    population (watersupply/calculations/chain.py::baseline_population), so a new or
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


# ── soil, land cover, groundwater, meteorology -> available fresh water ─

def _skip_raw(raw):
    """
    Fixtures and backup loads skip the refresh, except the map editor's
    Restore: it rewrites land cover with raw saves (the urban-fabric ring of
    a building) inside deferred_cascades(), so the sources over it are
    re-derived once at the end.
    """
    if not raw:
        return False
    from core.editing import is_restoring
    return not is_restoring()


def refresh_freshwater(extent=None, pks=None):
    """
    Re-save the AvailableFreshWater sources overlapping `extent` (a geometry
    in the storage CRS) or with the given pks, so save() re-derives their
    infiltration rate, recharge depth and yield. Queued while
    deferred_water_refresh() is active. Also called by the importer's bulk
    finalizers (importer/batching.py), since bulk_create fires no post_save.
    """
    if pks is None:
        if extent is None:
            return
        pks = AvailableFreshWater.objects.filter(geom__intersects=extent).values_list('pk', flat=True)
    pks = set(pks)
    if not pks:
        return
    pending = getattr(_deferred, "freshwater", None)
    if pending is not None:
        pending.update(pks)
        return
    _flush_water_refresh((), (), pks)


def bbox_polygon(box, srid=None):
    """Polygon of an (xmin, ymin, xmax, ymax) extent in the storage CRS (None for None)."""
    from django.conf import settings
    from django.contrib.gis.geos import Polygon

    if not box:
        return None
    polygon = Polygon.from_bbox(box)
    polygon.srid = srid or settings.COORDINATE_SYSTEM
    return polygon


def _raster_extent(raster):
    if raster is None:
        return None
    try:
        return bbox_polygon(raster.extent, raster.srid)
    except Exception:  # an unreadable raster: nothing to locate
        return None


@receiver(post_save, sender=SoilArea, dispatch_uid="water_soilarea_saved")
@receiver(post_delete, sender=SoilArea, dispatch_uid="water_soilarea_deleted")
@receiver(post_save, sender=LandCoverVector, dispatch_uid="water_landcover_saved")
@receiver(post_delete, sender=LandCoverVector, dispatch_uid="water_landcover_deleted")
def soil_or_landcover_changed(sender, instance, raw=False, **kwargs):
    """
    DAG edges: LandCover -> Infiltration -> Available_FW
               Soil_Type -> Infiltration -> Available_FW
    """
    if not _skip_raw(raw):
        refresh_freshwater(instance.geom)


@receiver(post_save, sender=SoilType, dispatch_uid="water_soiltype_saved")
def soil_type_changed(sender, instance, created=False, raw=False, **kwargs):
    """A renamed soil type can change its hydrologic group. DAG edge: Soil_Type -> Infiltration"""
    from django.contrib.gis.db.models import Extent

    if created or _skip_raw(raw):
        return  # a new type has no areas yet
    box = SoilArea.objects.filter(soil_type=instance).aggregate(e=Extent('geom'))['e']
    refresh_freshwater(bbox_polygon(box))


@receiver(post_save, sender=GroundwaterDepth, dispatch_uid="water_groundwater_saved")
@receiver(post_delete, sender=GroundwaterDepth, dispatch_uid="water_groundwater_deleted")
def groundwater_changed(sender, instance, raw=False, **kwargs):
    """
    Shallow groundwater turns undrained soil into group D.
    DAG edge: Soil_Type -> Infiltration (groundwater rule)
    """
    if not _skip_raw(raw):
        refresh_freshwater(_raster_extent(instance.depth_raster))


@receiver(landcover_created, sender=LandCoverVector, dispatch_uid="water_landcover_created")
def landcover_rows_created(sender, pks, **kwargs):
    """Land cover inserted with raw SQL by the map editor (physicalEnv/calculations/landcover.py). DAG edge: LandCover -> Infiltration"""
    from django.contrib.gis.db.models import Extent

    box = LandCoverVector.objects.filter(pk__in=pks).aggregate(e=Extent('geom'))['e']
    refresh_freshwater(bbox_polygon(box))


def _sources_near_stations(station_ids):
    """
    Sources that may take their meteorology from one of these stations: those
    with one of them among the stations weather.calculations.water_balance would try.
    """
    from django.contrib.gis.db.models.functions import Distance

    from weather.models import WeatherStation
    from weather.calculations.water_balance import MAX_STATIONS

    station_ids = set(station_ids)
    daily = Meteorology.objects.filter(reference_et_mm__isnull=False).values('station_id')
    candidates = WeatherStation.objects.filter(pk__in=daily)
    pks = []
    for source in AvailableFreshWater.objects.only('pk', 'geom'):
        if source.geom is None:
            continue
        nearest = (candidates.annotate(d=Distance('geom', source.geom.point_on_surface))
                   .order_by('d').values_list('pk', flat=True)[:MAX_STATIONS])
        # a deleted station's rows are gone: it is no longer a candidate, so
        # refresh sources whose nearest candidates it could have displaced
        if station_ids & set(nearest) or len(nearest) < MAX_STATIONS:
            pks.append(source.pk)
    return pks


@receiver(daily_water_balance_changed, dispatch_uid="water_daily_balance_imported")
def daily_balance_imported(sender, station_ids, **kwargs):
    """Bulk KNMI daily import (weather/knmi.py::store_daily). DAG edge: Meteorology -> Available_FW"""
    refresh_freshwater(pks=_sources_near_stations(station_ids))


@receiver(post_save, sender=Meteorology, dispatch_uid="water_meteorology_saved")
@receiver(post_delete, sender=Meteorology, dispatch_uid="water_meteorology_deleted")
def meteorology_changed(sender, instance, raw=False, **kwargs):
    """
    A daily water-balance row (reference ET set) saved or deleted one at a time.
    DAG edge: Meteorology -> Available_FW
    """
    if raw or instance.reference_et_mm is None:
        return
    refresh_freshwater(pks=_sources_near_stations([instance.station_id]))
