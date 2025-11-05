from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum, F, FloatField, Case, When, Value, ExpressionWrapper
from django.utils import timezone
from .models import Neighborhood, City, Region


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

@receiver(post_save, sender=Neighborhood, dispatch_uid="neigh_upsert_to_city_region")
@receiver(post_delete, sender=Neighborhood, dispatch_uid="neigh_delete_to_city_region")
def neighborhood_changed_update_city_and_region(sender, instance, **kwargs):
    """
    Single signal function:
      - recompute City totals/density when a Neighborhood is created/updated/deleted
      - then recompute Region totals/density based on its Cities
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

    # 2) Recompute REGION totals from its cities
    region_id = City.objects.filter(id=city_id).values_list('region_id', flat=True).first()
    if region_id:
        region_total = City.objects.filter(region_id=region_id).aggregate(
            total=Sum('currentPopulation')
        )['total'] or 0

        Region.objects.filter(id=region_id).update(
            currentPopulation=region_total,
            populationDensity=_safe_divide_expr(region_total),
            last_updated=timezone.now()
        )