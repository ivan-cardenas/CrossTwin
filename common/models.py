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
    urbanizationRate = models.FloatField(null=True, help_text="Urbanization rate in % per year") # %
    urban_area = models.FloatField(null=True, help_text="Urban area in square kilometers")
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
    


    

class LandCoverClasses(models.Model):
    id = models.AutoField(primary_key=True)
    class_name = models.CharField(max_length=100, help_text="Name of the land cover class (e.g., 'Urban', 'Forest', 'Agriculture', etc.)")
    description = models.TextField(help_text="Detailed description of the land cover class")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return self.class_name
    
class SurfaceMaterialProperties(models.Model):
    id = models.AutoField(primary_key=True)
    material_name = models.CharField(max_length=100, help_text="Name of the material (e.g., 'Concrete', 'Asphalt', 'Grass', etc.)")
    albedo = models.FloatField(help_text="Albedo value (0-1) representing the reflectivity of the material")
    thermal_conductivity = models.FloatField(help_text="Thermal conductivity in W/(m*K)")
    specific_heat_capacity = models.FloatField(help_text="Specific heat capacity in J/(kg*K)")
    density = models.FloatField(help_text="Density in kg/m3")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return self.material_name
    
class WallMaterialProperties(models.Model):
    id = models.AutoField(primary_key=True)
    material_name = models.CharField(max_length=100, help_text="Name of the wall material (e.g., 'Brick', 'Wood', 'Insulated Panel', etc.)")
    thermal_conductivity = models.FloatField(help_text="Thermal conductivity in W/(m*K)")
    specific_heat_capacity = models.FloatField(help_text="Specific heat capacity in J/(kg*K)")
    density = models.FloatField(help_text="Density in kg/m3")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return self.material_name


class LandCoverVector(models.Model):
    id = models.AutoField(primary_key=True)
    region = models.ForeignKey(Region, on_delete=models.DO_NOTHING, help_text="Region code from common.Region")
    year = models.IntegerField()
    land_cover_type = models.ForeignKey(LandCoverClasses, on_delete=models.DO_NOTHING, help_text="Type of land cover (e.g., 'Urban', 'Forest', 'Agriculture', etc.)")
    land_use = models.CharField(max_length=100, help_text="Land use type (e.g., 'Residential', 'Commercial', 'Industrial', 'Park', etc.)")
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    percentage = models.FloatField(help_text="Percentage of the region covered by this land cover type") #TODO: Calculate this percentage based on the area of the geom and the total area of the region. #TODO: Vegetation Coverage and Builtup Coverage as additional fields?
    material = models.ForeignKey(SurfaceMaterialProperties, on_delete=models.DO_NOTHING, help_text="Material properties of the land cover type")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.region} - {self.year}: {self.land_cover_type} ({self.percentage}%)"
    
class LandCoverRaster(models.Model):
    id = models.AutoField(primary_key=True)
    region = models.ForeignKey(Region, on_delete=models.DO_NOTHING, help_text="Region code from common.Region")
    year = models.IntegerField()
    raster = models.RasterField(srid=CoordinateSystem, null=True, blank=True, help_text="Raster file containing land cover classification values")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.region} - {self.year}: Land Cover Raster"
    
class LandCoverWMS(models.Model):
    name = models.CharField(max_length=200)
    display_name = models.CharField(max_length=200)
    url = models.URLField(max_length=500, help_text="Base WMS endpoint URL")
    layers_param = models.CharField(max_length=200, help_text="WMS layers parameter")
    color = models.CharField(max_length=7, default='#4a90d9')
    legend_url = models.URLField(max_length=500, blank=True, null=True)
    opacity = models.FloatField(default=0.7)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Land Cover WMS Layer"
        verbose_name_plural = "Land Cover WMS Layers"
        
    def __str__(self):
        return self.display_name


class DigitalElevationModel(models.Model):
    id = models.AutoField(primary_key=True)
    region = models.ForeignKey(Region, on_delete=models.DO_NOTHING, help_text="Region code from common.Region")
    year = models.IntegerField()
    dem_raster = models.RasterField(srid=CoordinateSystem, null=True, blank=True, help_text="Raster file containing elevation values")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.region} - {self.year}: Digital Elevation Model"
    
class DigitalElevationModelWMS(models.Model):
    name = models.CharField(max_length=200)
    display_name = models.CharField(max_length=200)
    url = models.URLField(max_length=500, help_text="Base WMS endpoint URL")
    layers_param = models.CharField(max_length=200, help_text="WMS layers parameter")
    color = models.CharField(max_length=7, default='#4a90d9')
    legend_url = models.URLField(max_length=500, blank=True, null=True)
    opacity = models.FloatField(default=0.7)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Digital Elevation Model WMS Layer"
        verbose_name_plural = "Digital Elevation Model WMS Layers"
        
    def __str__(self):
        return self.display_name
    
class DigitalSurfaceModel(models.Model):
    id = models.AutoField(primary_key=True)
    region = models.ForeignKey(Region, on_delete=models.DO_NOTHING, help_text="Region code from common.Region")
    year = models.IntegerField()
    dsm_raster = models.RasterField(srid=CoordinateSystem, null=True, blank=True, help_text="Raster file containing surface elevation values")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.region} - {self.year}: Digital Surface Model"
    
class DigitalSurfaceModelWMS(models.Model):
    name = models.CharField(max_length=200)
    display_name = models.CharField(max_length=200)
    url = models.URLField(max_length=500, help_text="Base WMS endpoint URL")
    layers_param = models.CharField(max_length=200, help_text="WMS layers parameter")
    color = models.CharField(max_length=7, default='#4a90d9')
    legend_url = models.URLField(max_length=500, blank=True, null=True)
    opacity = models.FloatField(default=0.7)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Digital Surface Model WMS Layer"
        verbose_name_plural = "Digital Surface Model WMS Layers"
        
    def __str__(self):
        return self.display_name
    
