from django.db import models
from django.utils import timezone



# Create your models here.
class ConsumptionCapita(models.Model):
    region = models.CharField(max_length=100)
    year = models.IntegerField()
    consumption_per_capita = models.FloatField()
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.region} - {self.year}: {self.consumption_per_capita} L/person/day"