from django.utils import timezone
from django.contrib.gis.db import models
from django.db.models import Sum

from django.conf import settings

CoordinateSystem = settings.COORDINATE_SYSTEM

# Create your models here.
class Province(models.Model):
    id = models.AutoField(primary_key=True)
    ProvinceName = models.CharField(max_length=100)
    currentPopulation = models.IntegerField(null=True, help_text="Total current population in the Province", verbose_name="Current Population")
    populationDensity = models.FloatField(null=True, help_text="Population density in people per square kilometer", verbose_name="Population Density") # people/km2
    populationDate = models.DateField(null=True, help_text="Date of the population data", verbose_name="Population Date")
    area_km2 = models.FloatField(null=True, help_text="Area in square kilometers")
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    last_updated = models.DateTimeField(default=timezone.now)



    def save(self, *args, **kwargs):
        if self.currentPopulation is None:
            try:
                # NOTE: pre-existing bug — `Province=` is a wrong-case kwarg
                # for the `city.province` field, so this always raises and
                # falls through to the except below. Left as-is (not in
                # scope for the administrative/physicalEnv app split).
                total = City.objects.filter(Province=self.id).aggregate(
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
        return self.ProvinceName

    class Meta:
        verbose_name = "Province"
        verbose_name_plural = "Provinces"



class City(models.Model):
    id = models.AutoField(primary_key=True)
    province = models.ForeignKey(Province, on_delete=models.CASCADE, help_text="Province code from administrative.Province")
    cityName = models.CharField(max_length=100, verbose_name="City Name", help_text="Name of the city")
    currentPopulation = models.IntegerField(help_text="Total current population in the city", verbose_name="Current Population")
    area_km2 = models.FloatField(null=True, help_text="Area in square kilometers")
    populationDensity = models.FloatField(null=True, help_text="Population density in people per square kilometer", verbose_name="Population Density") # people/km2
    populationDate = models.DateField(null=True)
    popGrowthRate = models.FloatField(null=True , help_text="Growth rate in % per year") # %
    urbanizationRate = models.FloatField(null=True, help_text="Urbanization rate in % per year") # %
    urban_area = models.FloatField(null=True, help_text="Urban area in square kilometers")
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    last_updated = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):

        if self.pk:
            total = District.objects.filter(city=self).aggregate(
                total=Sum('currentPopulation')
            )['total']
            self.currentPopulation = total or 0

        self.area_km2 = self.geom.area / 1e6  # Convert m2 to km2

        if self.area_km2 and self.area_km2 > 0 and self.currentPopulation is not None:
            self.populationDensity = float (self.currentPopulation / self.area_km2)
        else:
            self.populationDensity = None

        self.last_updated = timezone.now()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cityName} - {self.currentPopulation} inhabitants"

    class Meta:
        verbose_name = "City"
        verbose_name_plural = "Cities"

class District(models.Model):
    id = models.CharField(primary_key=True)
    city = models.ForeignKey(City, on_delete=models.DO_NOTHING, help_text="City code from administrative.City")
    districtName = models.CharField(max_length=100, help_text="Name of the district", verbose_name="District Name")
    currentPopulation = models.IntegerField(null=True, blank=True, help_text="Current population in the district")
    populationDate = models.DateField(null=True)
    area_km2 = models.FloatField(null=True, blank=True, help_text="Area in square kilometers")
    populationDensity = models.FloatField(null=True, blank=True, help_text="Population density in people per square kilometer", verbose_name="Population Density")
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    last_updated = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        self.area_km2 = self.geom.area / 1e6
        pop = self.currentPopulation or 0
        self.populationDensity = float(pop / self.area_km2) if self.area_km2 else 0.0
        self.last_updated = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.districtName

    class Meta:
        verbose_name = "District"
        verbose_name_plural = "Districts"

class Neighborhood(models.Model):
    id = models.CharField(primary_key=True)
    district = models.ForeignKey(District, on_delete=models.DO_NOTHING, help_text="City code from administrative.City", null=True, blank=True)
    neighborhoodName = models.CharField(max_length=100, help_text="Name of the neighborhood", verbose_name="Neighborhood Name")
    currentPopulation = models.IntegerField(null=True, blank=True, help_text="Current population in the neighborhood", verbose_name="Current Population")
    populationDate = models.DateField(null=True)
    area_km2 = models.FloatField(null=True, blank=True, help_text="Area in square kilometers")
    populationDensity = models.FloatField(null=True, blank=True, help_text="Population density in people per square kilometer", verbose_name="Population Density")
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    last_updated = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        self.area_km2 = self.geom.area / 1e6
        pop = self.currentPopulation or 0
        self.populationDensity = float(pop / self.area_km2) if self.area_km2 else 0.0
        self.last_updated = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.neighborhoodName

    class Meta:
        verbose_name = "Neighborhood"
        verbose_name_plural = "Neighborhoods"
