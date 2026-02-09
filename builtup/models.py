from django.utils import timezone
from django.contrib.gis.db import models
from django.db.models import Sum
from common.models import Region, City, Neighborhood, SurfaceMaterialProperties, WallMaterialProperties
from Energy.models import EnergyEfficiencyLabels

from django.conf import settings

CoordinateSystem = settings.COORDINATE_SYSTEM


class ZoningArea(models.Model):
    id = models.AutoField(primary_key=True)
    neighborhood = models.ForeignKey(Neighborhood, verbose_name="Neighborhood", on_delete=models.DO_NOTHING)
    zone_type = models.CharField(max_length=100, choices=[('residential', 'Residential'), ('commercial', 'Commercial'), ('industrial', 'Industrial'), ('mixed', 'Mixed Use')], help_text="Type of zoning area")
    description = models.TextField(null=True, blank=True, help_text="Detailed description of the zoning area")
    area = models.FloatField(help_text="Area of the zoning area in square meters")
    benchmarkPrice_per_sqm = models.FloatField(null=True, blank=True, help_text="Benchmark price per square meter in EUR")
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    
    def __str__(self):
        return f"Zoning Area {self.id} ({self.zone_type})"
    
    class Meta:
        verbose_name = "Zoning Area"
        verbose_name_plural = "Zoning Areas"

class Building(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, help_text="Name or identifier of the building")
    address = models.CharField(max_length=200, help_text="Address of the building")
    neighborhood = models.ForeignKey(Neighborhood, verbose_name="Neighborhood", on_delete=models.DO_NOTHING)
    ZoningArea = models.ForeignKey(ZoningArea, verbose_name="Zoning Area", on_delete=models.DO_NOTHING, null=True, blank=True)
    buildingType = models.CharField(max_length=100, choices=[('residential', 'Residential'), ('commercial', 'Commercial'), ('industrial', 'Industrial')], help_text="Type of building (e.g., residential, commercial, industrial)")
    roofMaterial = models.ForeignKey(SurfaceMaterialProperties, verbose_name="Roof Material", on_delete=models.DO_NOTHING, null=True, blank=True)
    wallMaterial = models.ForeignKey(WallMaterialProperties, verbose_name="Wall Material", on_delete=models.DO_NOTHING, null=True, blank=True)
    energyLabel = models.ForeignKey(EnergyEfficiencyLabels, verbose_name="Energy Label", on_delete=models.DO_NOTHING, null=True, blank=True)
    height = models.FloatField(help_text="Height of the building in meters")
    area = models.FloatField(help_text="Footprint area of the building in square meters")
    constructionYear = models.IntegerField(null=True, blank=True, help_text="Year the building was constructed")
    numberFloors = models.IntegerField(null=True, blank=True, help_text="Number of floors in the building")
    numberUnits = models.IntegerField(null=True, blank=True, help_text="Number of housing or commercial units in the building")
    vacant= models.BooleanField(default=False, help_text="Is the building vacant?")
    vacancyRate = models.FloatField(null=True, blank=True, help_text="Vacancy rate in percentage (%)")
    last_updated = models.DateTimeField(default=timezone.now)
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    
    def __str__(self):
        return f"Building {self.id} ({self.buildingType})"
    
    class Meta:
        verbose_name = "Building"
        verbose_name_plural = "Buildings"
        
class Street(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, help_text="Name of the street")
    surfaceMaterial = models.ForeignKey(SurfaceMaterialProperties, verbose_name="Surface Material", on_delete=models.DO_NOTHING, null=True, blank=True)
    classification = models.CharField(max_length=50, choices=[('primary', 'Primary'), ('secondary', 'Secondary'), ('residential', 'Residential')], help_text="Street classification (e.g., primary, secondary, residential)")
    width = models.FloatField(help_text="Width of the street in meters")
    geom = models.LineStringField(srid=CoordinateSystem)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Street"
        verbose_name_plural = "Streets"
        
class Park(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, help_text="Name of the park")
    area = models.FloatField(help_text="Area of the park in square meters")
    vegetationType = models.CharField(max_length=100, help_text="Type of vegetation in the park (e.g., grass, trees, shrubs)")
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Park"
        verbose_name_plural = "Parks"
        
        

        

        
class Facility(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, help_text="Name of the facility")
    type = models.CharField(max_length=100, choices=[('school', 'School'), ('hospital', 'Hospital'), ('fire_station', 'Fire Station'), 
                                                     ('police_station', 'Police Station'), ('market', 'Market'), ('transportNode', 'Transport Node')], 
                            help_text="Type of facility")
    geom = models.PointField(srid=CoordinateSystem)
    
    def __str__(self):
        return self.name
    
class Property(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, help_text="Name of the property")
    building = models.ForeignKey(Building, verbose_name="Building", on_delete=models.DO_NOTHING)
    grossArea = models.FloatField(help_text="Area of the property in square meters")
    livingArea = models.FloatField(help_text="Living area of the property in square meters")
    greenVisibility = models.FloatField(help_text="Green visibility index of the property")  #TODO: Define green visibility index and calculation method
    bedrooms = models.IntegerField(help_text="Number of bedrooms in the property")
    bathrooms = models.IntegerField(help_text="Number of bathrooms in the property")
    connectivity = models.FloatField(help_text="Connectivity index of the property")  #TODO: Define connectivity index and calculation method
    listingPrice_EUR = models.FloatField(help_text="Listing price of the property in EUR")
    salePrice_EUR = models.FloatField(help_text="Sale price of the property in EUR")
    unitaryPrice_EUR_per_sqm = models.FloatField(help_text="Unitary price in EUR per square meter")
    last_updated = models.DateTimeField(default=timezone.now)
    geom = models.PointField(srid=CoordinateSystem)
    
    def __str__(self):
        return self.name
    
