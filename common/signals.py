from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum
from django.utils import timezone
from .models import Neighborhood, District, City, Province


def _recompute_population(model, pk, child_model, child_fk, parent_fk=None):
    """
    Recompute currentPopulation and populationDensity for a parent record
    by summing its children's currentPopulation.

    If parent_fk is given, returns (parent_model, parent_pk) so the caller
    can cascade further up the hierarchy.
    """
    total = child_model.objects.filter(**{child_fk: pk}).aggregate(
        total=Sum('currentPopulation')
    )['total'] or 0

    obj = model.objects.filter(pk=pk).first()
    if obj is None:
        return None

    obj.currentPopulation = total
    if obj.area_km2 and obj.area_km2 > 0:
        obj.populationDensity = total / obj.area_km2
    else:
        obj.populationDensity = None
    obj.last_updated = timezone.now()
    # Use update() to avoid triggering save() and infinite signal loops
    model.objects.filter(pk=pk).update(
        currentPopulation=obj.currentPopulation,
        populationDensity=obj.populationDensity,
        last_updated=obj.last_updated,
    )

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
