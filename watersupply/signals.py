from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum, F, FloatField, Case, When, Value, ExpressionWrapper
from django.utils import timezone
from .models import ConsumptionCapita
from common.models import City


@receiver(post_save, sender=City)
def update_consumption_on_population_change(sender, instance, **kwargs):
    """
    Recalculate total_consumption_m3_d for all records of this city
    whenever the population changes.
    """
    ConsumptionCapita.objects.filter(city=instance).update(
        total_consumption_m3_yr=ExpressionWrapper(
            F("consumption_capita_L_d") / 1000.0 * F("city__population")*365,
            output_field=FloatField(),
        ),
        
        last_updated=timezone.now(),
    )
    
