from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum, F, FloatField, Case, When, Value, ExpressionWrapper
from django.utils import timezone
from .models import Neighborhood, City, Province


def _safe_divide_expr(numerator_value):
    """Return an ExpressionWrapper(numerator / F('area_km2')) guarded by area>0."""
    return Case(
        When(area_km2__gt=0,
             then=ExpressionWrapper(
                 Value(numerator_value) / F('area_km2'),
                 output_field=FloatField()
             )),
        default=Value(None),
        output_field=FloatField()
    )

@receiver(post_save, sender=Neighborhood, dispatch_uid="neigh_upsert_to_city_Province")
@receiver(post_delete, sender=Neighborhood, dispatch_uid="neigh_delete_to_city_Province")
def neighborhood_changed_update_city_and_Province(sender, instance, **kwargs):
    """
    Single signal function:
      - recompute City totals/density when a Neighborhood is created/updated/deleted
      - then recompute Province totals/density based on its Cities
    """
    city_id = instance.city_id
    if not city_id:
        return

    # 1) Recompute CITY totals from its neighborhoods
    city_total = Neighborhood.objects.filter(city_id=city_id).aggregate(
        total=Sum('currentPopulation')
    )['total'] or 0

    City.objects.filter(id=city_id).update(
        currentPopulation=city_total,
        populationDensity=_safe_divide_expr(city_total),
        last_updated=timezone.now()
    )

    # 2) Recompute Province totals from its cities
    province_id = City.objects.filter(id=city_id).values_list('province_id', flat=True).first()
    if province_id:
        province_total = City.objects.filter(province_id=province_id).aggregate(
            total=Sum('currentPopulation')
        )['total'] or 0

        Province.objects.filter(id=province_id).update(
            currentPopulation=province_total,
            populationDensity=_safe_divide_expr(province_total),
            last_updated=timezone.now()
        )
        
@receiver(post_save, sender=City, dispatch_uid="city_upsert_to_Province")
@receiver(post_delete, sender=City, dispatch_uid="city_delete_to_Province")
def city_changed_update_Province(sender, instance, **kwargs):
    """
    Single signal function:
      - recompute Province totals/density when a City is created/updated/deleted
    """
    province_id = instance.province_id
    if not province_id:
        return

    # 1) Recompute Province totals from its cities
    province_total = City.objects.filter(province_id=province_id).aggregate(
        total=Sum('currentPopulation')
    )['total'] or 0

    Province.objects.filter(id=province_id).update(
        currentPopulation=province_total,
        populationDensity=_safe_divide_expr(province_total),
        last_updated=timezone.now()
    )