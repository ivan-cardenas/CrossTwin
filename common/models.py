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
    province = models.ForeignKey(Province, on_delete=models.CASCADE, help_text="Province code from common.Province")
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
    city = models.ForeignKey(City, on_delete=models.DO_NOTHING, help_text="City code from common.City")
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
    district = models.ForeignKey(District, on_delete=models.DO_NOTHING, help_text="City code from common.City", null=True, blank=True)
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
    
    class Meta:
        verbose_name = "Surface Material Properties"
        verbose_name_plural = "Surface Material Properties"
    
class WallMaterialProperties(models.Model):
    id = models.AutoField(primary_key=True)
    material_name = models.CharField(max_length=100, help_text="Name of the wall material (e.g., 'Brick', 'Wood', 'Insulated Panel', etc.)")
    thermal_conductivity = models.FloatField(help_text="Thermal conductivity in W/(m*K)")
    specific_heat_capacity = models.FloatField(help_text="Specific heat capacity in J/(kg*K)")
    density = models.FloatField(help_text="Density in kg/m3")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return self.material_name
    
    class Meta:
        verbose_name = "Wall Material Properties"
        verbose_name_plural = "Wall Material Properties"


class LandCoverVector(models.Model):
    id = models.AutoField(primary_key=True)
    city = models.ForeignKey(City, on_delete=models.DO_NOTHING, help_text="City code from common.City", null=True, blank=True)
    year = models.IntegerField()
    land_cover_type = models.ForeignKey(LandCoverClasses, on_delete=models.DO_NOTHING, help_text="Type of land cover (e.g., 'Urban', 'Forest', 'Agriculture', etc.)")
    land_use = models.CharField(max_length=100, help_text="Land use type (e.g., 'Residential', 'Commercial', 'Industrial', 'Park', etc.)")
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    percentage = models.FloatField(help_text="Percentage of the City covered by this land cover type") #TODO: Calculate this percentage based on the area of the geom and the total area of the Province. #TODO: Vegetation Coverage and Builtup Coverage as additional fields?
    material = models.ForeignKey(SurfaceMaterialProperties, on_delete=models.DO_NOTHING, help_text="Material properties of the land cover type")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.City} - {self.year}: {self.land_cover_type} ({self.percentage}%)"
    
class LandCoverRaster(models.Model):
    id = models.AutoField(primary_key=True)
    city = models.ForeignKey(City, on_delete=models.DO_NOTHING, help_text="City code from common.City", null=True, blank=True)
    year = models.IntegerField()
    date = models.DateTimeField(null=True, blank=True, help_text="Acquisition/generation date of the raster")
    source = models.CharField(max_length=100, null=True, blank=True, help_text="Data provider of the raster (e.g., 'PDOK', 'Sentinel-2', 'Google Earth Engine')")
    index = models.CharField(max_length=100, null=True, blank=True, help_text="Dataset or index represented by the raster (e.g., 'LGN2021', 'WORLDCOVER_2021_MAP', 'NDVI', 'lossyear')")
    resolution = models.FloatField(null=True, blank=True, help_text="Spatial resolution of the raster in meters")
    raster = models.RasterField(srid=CoordinateSystem, null=True, blank=True, help_text="Raster file containing land cover classification values")
    cog_path = models.CharField(max_length=500, null=True, blank=True, help_text="Path to the exported Cloud-Optimized GeoTIFF served by TiTiler")
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.city} - {self.year}: Land Cover Raster ({self.index or 'n/a'})"
    
class SatelliteImagery(models.Model):
    id = models.AutoField(primary_key=True)
    city = models.ForeignKey(City, on_delete=models.DO_NOTHING, help_text="City code from common.City", null=True, blank=True)
    year = models.IntegerField()
    date = models.DateTimeField(null=True, blank=True, help_text="Acquisition date/time of the satellite imagery")
    satellite_type = models.CharField(max_length=100, null=True, blank=True, help_text="Satellite or sensor that captured the imagery (e.g., 'Sentinel-2', 'Landsat', 'MODIS', etc.)")
    index = models.CharField(max_length=100, null=True, blank=True, help_text="Type of satellite imagery index/product (e.g., 'TrueColor', 'NDVI', 'EVI', 'NDWI', etc.)")
    resolution = models.FloatField(null=True, blank=True, help_text="Spatial resolution of the imagery in meters")
    raster = models.RasterField(srid=CoordinateSystem, null=True, blank=True, help_text="Raster file containing satellite imagery")
    cog_path = models.CharField(max_length=500, null=True, blank=True, help_text="Path to the exported Cloud-Optimized GeoTIFF served by TiTiler")
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.city} - {self.year}: {self.satellite_type or 'Satellite Imagery'} ({self.index or 'n/a'})"
    
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
    # Nothing queries dem_raster with server-side PostGIS raster SQL, so the
    # importer skips loading it into Postgres at all (see
    # importer/external_data.py::load_raster_into_target_model and
    # core/rasterOperations.py::export_geotiff_to_cog) — only cog_path gets
    # populated. Storing the raw raster as a RasterField blob is a large,
    # redundant write that can crash Postgres outright on city-scale imports
    # (0.5m AHN data covering a whole city easily reaches hundreds of MB).
    SKIP_RASTER_DB_STORAGE = True

    id = models.AutoField(primary_key=True)
    city = models.ForeignKey(City, on_delete=models.DO_NOTHING, help_text="City code from common.City", null=True, blank=True)
    year = models.IntegerField()
    date = models.DateTimeField(null=True, blank=True, help_text="Acquisition/generation date of the elevation model")
    source = models.CharField(max_length=100, null=True, blank=True, help_text="Data provider of the raster (e.g., 'AHN4 (PDOK)')")
    resolution = models.FloatField(null=True, blank=True, help_text="Spatial resolution of the raster in meters")
    dem_raster = models.RasterField(srid=CoordinateSystem, null=True, blank=True, help_text="Raster file containing elevation values")
    cog_path = models.CharField(max_length=500, null=True, blank=True, help_text="Path to the exported Cloud-Optimized GeoTIFF served by TiTiler")
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.city} - {self.year}: Digital Elevation Model"
    
class DigitalElevationModelWMS(models.Model):
    name = models.CharField(max_length=200)
    display_name = models.CharField(max_length=200)
    url = models.URLField(max_length=500, help_text="Base WMS endpoint URL")
    layers_param = models.CharField(max_length=200, help_text="WMS layers parameter")
    color = models.CharField(max_length=7, default="#272727")
    legend_url = models.URLField(max_length=500, blank=True, null=True)
    opacity = models.FloatField(default=0.7)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Digital Elevation Model WMS Layer"
        verbose_name_plural = "Digital Elevation Model WMS Layers"
        
    def __str__(self):
        return self.display_name
    
class DigitalSurfaceModel(models.Model):
    # See DigitalElevationModel.SKIP_RASTER_DB_STORAGE — same reasoning.
    SKIP_RASTER_DB_STORAGE = True

    id = models.AutoField(primary_key=True)
    city = models.ForeignKey(City, on_delete=models.DO_NOTHING, help_text="City code from common.City", null=True, blank=True)
    year = models.IntegerField()
    date = models.DateTimeField(null=True, blank=True, help_text="Acquisition/generation date of the surface model")
    source = models.CharField(max_length=100, null=True, blank=True, help_text="Data provider of the raster (e.g., 'AHN4 (PDOK)')")
    resolution = models.FloatField(null=True, blank=True, help_text="Spatial resolution of the raster in meters")
    dsm_raster = models.RasterField(srid=CoordinateSystem, null=True, blank=True, help_text="Raster file containing surface elevation values")
    cog_path = models.CharField(max_length=500, null=True, blank=True, help_text="Path to the exported Cloud-Optimized GeoTIFF served by TiTiler")
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.city} - {self.year}: Digital Surface Model"
    
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
    
class EnvironmentalCosts(models.Model):
    id = models.AutoField(primary_key=True)
    price_EUR_kg_CO2 = models.FloatField()
    price_EUR_price_EUR_droughtDamage_m3 = models.FloatField()
    
    
    def __str__(self):
        return f"{self.Province} - {self.year}: Environment Costs"