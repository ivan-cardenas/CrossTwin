import logging
import threading
from contextlib import contextmanager

from django.db.models.signals import post_save, post_delete
from django.dispatch import Signal, receiver
from django.db.models import Sum, Avg, Min, Max
from django.utils import timezone

from core.cache import bump_layer_version
from .models import Neighborhood, District, City, Province

logger = logging.getLogger(__name__)

# Sent (with `city_id`) after the cascade below rewrites a City's population.
# The cascade uses queryset.update(), which does not fire post_save, so other
# apps (e.g. watersupply demand) listen to this instead of post_save(City).
city_population_changed = Signal()

# Per-thread set of parents whose cascade is postponed; None when not deferring.
_deferred = threading.local()


@contextmanager
def deferred_population_cascade():
    """
    Postpone the District -> City -> Province cascade until the block ends,
    then run it once per affected parent. Without this a bulk import re-runs
    the whole cascade (plus the city_population_changed fan-out into
    watersupply) for every Neighborhood it saves. Nested uses defer to the
    outermost one. See docs/PERFORMANCE.md §3/§11.
    """
    if getattr(_deferred, "pending", None) is not None:
        yield
        return

    _deferred.pending = {"district": set(), "city": set(), "province": set()}
    try:
        yield
    except BaseException:
        pending, _deferred.pending = _deferred.pending, None
        try:
            _flush_population_cascade(pending)
        except Exception:
            # e.g. the transaction is already broken; don't mask the original error
            logger.exception("Deferred population cascade failed after an aborted block")
        raise
    else:
        pending, _deferred.pending = _deferred.pending, None
        _flush_population_cascade(pending)


def _defer(level, pk):
    """Queue `pk` for the pending cascade and return True, or False when not deferring."""
    pending = getattr(_deferred, "pending", None)
    if pending is None:
        return False
    pending[level].add(pk)
    return True


def _flush_population_cascade(pending):
    """Bottom-up: each district once, then each resulting city once, then each province once."""
    cities = set(pending["city"])
    provinces = set(pending["province"])
    for district_id in pending["district"]:
        city_id = _recompute_population(
            District, district_id,
            child_model=Neighborhood, child_fk='district_id', parent_fk='city_id',
        )
        if city_id:
            cities.add(city_id)
    for city_id in cities:
        province_id = _recompute_population(
            City, city_id,
            child_model=District, child_fk='city_id', parent_fk='province_id',
        )
        if province_id:
            provinces.add(province_id)
    for province_id in provinces:
        _recompute_population(Province, province_id, child_model=City, child_fk='province_id')


def _recompute_population(model, pk, child_model, child_fk, parent_fk=None):
    """
    Recompute currentPopulation, populationDensity and urban_area for a
    parent record by summing its children's currentPopulation / urban_area.

    If parent_fk is given, returns (parent_model, parent_pk) so the caller
    can cascade further up the hierarchy.
    """
    totals = child_model.objects.filter(**{child_fk: pk}).aggregate(
        total=Sum('currentPopulation'),
        urban_area_total=Sum('urban_area'),
    )
    total = totals['total'] or 0
    # Unlike population, leave this None (unknown) rather than coercing to 0
    # when no child has a value yet -- "no urban_area data" isn't the same
    # as "0 km2 urban", whereas 0 population is a legitimate value.
    urban_area_total = totals['urban_area_total']

    obj = model.objects.filter(pk=pk).first()
    if obj is None:
        return None

    obj.populationDate = child_model.objects.filter(**{child_fk: pk}).aggregate(
        populationDate=Max('populationDate')
    )['populationDate']

    obj.currentPopulation = total
    obj.urban_area = urban_area_total
    if obj.area_km2 and obj.area_km2 > 0:
        obj.populationDensity = total / obj.area_km2
    else:
        obj.populationDensity = None
    obj.last_updated = timezone.now()
    # Use update() to avoid triggering save() and infinite signal loops
    model.objects.filter(pk=pk).update(
        currentPopulation=obj.currentPopulation,
        populationDensity=obj.populationDensity,
        urban_area=obj.urban_area,
        last_updated=obj.last_updated,
        populationDate=obj.populationDate,
    )
    # update() bypasses post_save, so the map's cached GeoJSON has to be told
    bump_layer_version(model)

    if model is City:
        city_population_changed.send(sender=City, city_id=pk)

    if parent_fk:
        return getattr(obj, parent_fk)
    return None


# ── Neighborhood changed → update District ────────────────────────────
@receiver(post_save, sender=Neighborhood, dispatch_uid="neigh_save_to_district")
@receiver(post_delete, sender=Neighborhood, dispatch_uid="neigh_delete_to_district")
def neighborhood_changed(sender, instance, **kwargs):
    district_id = instance.district_id
    if not district_id or _defer("district", district_id):
        return

    # District ← sum of its Neighborhoods
    city_id = _recompute_population(
        District, district_id,
        child_model=Neighborhood, child_fk='district_id',
        parent_fk='city_id',
    )

    if not city_id:
        return

    # City ← sum of its Districts
    province_id = _recompute_population(
        City, city_id,
        child_model=District, child_fk='city_id',
        parent_fk='province_id',
    )

    if not province_id:
        return

    # Province ← sum of its Cities
    _recompute_population(
        Province, province_id,
        child_model=City, child_fk='province_id',
    )


# ── District changed → update City → Province ─────────────────────────
@receiver(post_save, sender=District, dispatch_uid="district_save_to_city")
@receiver(post_delete, sender=District, dispatch_uid="district_delete_to_city")
def district_changed(sender, instance, **kwargs):
    city_id = instance.city_id
    if not city_id or _defer("city", city_id):
        return

    province_id = _recompute_population(
        City, city_id,
        child_model=District, child_fk='city_id',
        parent_fk='province_id',
    )

    if not province_id:
        return

    _recompute_population(
        Province, province_id,
        child_model=City, child_fk='province_id',
    )


# ── City changed → update Province ────────────────────────────────────
@receiver(post_save, sender=City, dispatch_uid="city_save_to_province")
@receiver(post_delete, sender=City, dispatch_uid="city_delete_to_province")
def city_changed(sender, instance, **kwargs):
    province_id = instance.province_id
    if not province_id or _defer("province", province_id):
        return

    _recompute_population(
        Province, province_id,
        child_model=City, child_fk='province_id',
    )
