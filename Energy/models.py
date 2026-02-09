from django.contrib.gis.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from common.models import Region, City, Neighborhood
from django.conf import settings

COORDINATE_SYSTEM = settings.COORDINATE_SYSTEM

# Create your models here.

class ElectricityCost(models.Model):
    id = models.AutoField(primary_key=True)
    region = models.ForeignKey(Region, on_delete=models.DO_NOTHING, help_text="Region code from common.Region")
    year = models.IntegerField()
    cost_EUR_kWh = models.FloatField(help_text="Cost in EUR per kilowatt-hour")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.region} - {self.year}: {self.cost_EUR_kWh} EUR/kWh"
    
    class Meta:
        verbose_name = "Electricity Cost"
        verbose_name_plural = "Electricity Costs"
        
class EnergyEfficiencyLabels(models.Model):
    id = models.AutoField(primary_key=True)
    label = models.CharField(max_length=10, choices=[('A+++', 'A+++'),('A++', 'A++'), ('A+', 'A+'), ('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D'), ('E', 'E'), ('F', 'F'), ('G', 'G')],
                             help_text="Energy efficiency label (e.g., A++, A+, B, C, etc.)")
    description = models.TextField(help_text="Detailed description of the energy efficiency label.") #TODO: Populate with standard descriptions and connect to labels.
    
    def __str__(self):
        return self.label
    
    class Meta:
        verbose_name = "Energy Label"
        verbose_name_plural = "Energy Labels"