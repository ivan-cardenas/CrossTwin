from django.utils import timezone
from django.contrib.gis.db import models
from django.db.models import Sum

from django.conf import settings

CoordinateSystem = settings.COORDINATE_SYSTEM

# Create your models here.
class Region(models.Model):
    id = models.AutoField(primary_key=True)
    regionName = models.CharField(max_length=100)
    currentPopulation = models.IntegerField(null=True, help_text="Total current population in the region", verbose_name="Current Population")
    populationDensity = models.FloatField(null=True, help_text="Population density in people per square kilometer", verbose_name="Population Density") # people/km2
    populationDate = models.DateField(null=True, help_text="Date of the population data", verbose_name="Population Date")
    area_km2 = models.FloatField(null=True, help_text="Area in square kilometers")
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    last_updated = models.DateTimeField(default=timezone.now)
    
    
    
    def save(self, *args, **kwargs):
        if self.currentPopulation is None:
            try:
                total = City.objects.filter(Region=self.id).aggregate(
                    total=Sum('currentPopulation')
                )['total']
                self.currentPopulation = total 
            except:
                self.currentPopulation = 0
                

        self.area_km2 = self.geom.area / 1e6  # Convert m2 to km2

        if self.area_km2 and self.area_km2 > 0:
            self.populationDensity = self.currentPopulation / float(self.area_km2)
        else:
            self.populationDensity = None
        self.last_updated = timezone.now()
        super().save(*args, **kwargs)
        

    def __str__(self):
        return self.regionName

    class Meta:
        verbose_name = "Region"
        verbose_name_plural = "Regions"
        
        
        
class City(models.Model):
    id = models.AutoField(primary_key=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, help_text="Region code from common.Region")
    cityName = models.CharField(max_length=100)
    currentPopulation = models.IntegerField(help_text="Total current population in the city") 
    area_km2 = models.FloatField(null=True, help_text="Area in square kilometers")
    populationDensity = models.FloatField(null=True, help_text="Population density in people per square kilometer") # people/km2
    populationDate = models.DateField(null=True)
    popGrowthRate = models.FloatField(null=True , help_text="Growth rate in % per year") # %
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    last_updated = models.DateTimeField(default=timezone.now)
    
    def save(self, *args, **kwargs):
        total = Neighborhood.objects.filter(city=self).aggregate(
            total=Sum('currentPopulation')
        )['total']
        self.currentPopulation = total or 0
        
        if self.area_km2 and self.area_km2 > 0:
            self.populationDensity = float (self.currentPopulation / self.area_km2)
        else:
            self.populationDensity = None
            
        self.last_updated = timezone.now()
        super.save(*args, **kwargs)
        
    def __str__(self):
        return f"{self.cityName} - {self.currentPopulation} inhabitants"
    
    class Meta:
        verbose_name = "City"
        verbose_name_plural = "Cities"
        
class Neighborhood(models.Model):
    id = models.AutoField(primary_key=True)
    city = models.ForeignKey(City, on_delete=models.DO_NOTHING, help_text="City code from common.City")
    neighborhoodName = models.CharField(max_length=100, help_text="Name of the neighborhood")
    currentPopulation = models.IntegerField(help_text="Current population in the neighborhood") 
    populationDate = models.DateField(null=True)
    area_km2 = models.FloatField(help_text="Area in square kilometers")
    populationDensity = models.FloatField(help_text="Population density in people per square kilometer") # people/km2
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    last_updated = models.DateTimeField(default=timezone.now)
    
    
    def __str__(self):
        return self.neighborhoodName
    
    class Meta:
        verbose_name = "Neighborhood"
        verbose_name_plural = "Neighborhoods"
    

class ElectricityCost(models.Model):
    id = models.AutoField(primary_key=True)
    region = models.ForeignKey(Region, on_delete=models.DO_NOTHING, help_text="Region code from common.Region")
    year = models.IntegerField()
    cost_EUR_kWh = models.FloatField(help_text="Cost in EUR per kilowatt-hour")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.region} - {self.year}: {self.cost_EUR_kWh} EUR/kWh"