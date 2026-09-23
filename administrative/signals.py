from django.db.models.signals import post_save, post_delete
from django.dispatch import Signal, receiver
from django.db.models import Sum, Avg, Min, Max
from django.utils import timezone
from .models import Neighborhood, District, City, Province

# Sent (with `city_id`) after the cascade below rewrites a City's population.
# The cascade uses queryset.update(), which does not fire post_save, so other
# apps (e.g. watersupply demand) listen to this instead of post_save(City).
city_population_changed = Signal()


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
    if not district_id:
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
    if not city_id:
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
    if not province_id:
        return

    _recompute_population(
        Province, province_id,
        child_model=City, child_fk='province_id',
    )
