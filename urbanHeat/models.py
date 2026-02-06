from django.contrib.gis.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from common.models import Region, City, Neighborhood
from django.conf import settings

# Create your models here.
class StressCategory(models.Model):
    id = models.AutoField(primary_key=True)
    category = models.CharField(max_length=50, null=True, blank=True, verbose_name="Stress Category", help_text="Thermal stress category (e.g., 'No Thermal Stress', 'Moderate Heat Stress', etc.)")
    description = models.TextField(null=True, blank=True, verbose_name="Category Description", help_text="Detailed description of the thermal stress category.")
    
    def __str__(self):
        return self.category if self.category else f"StressCategory {self.id}"
    
    class Meta:
        verbose_name_plural = "Stress Categories"
        verbose_name = "Stress Category"
        
    def clean(self):
        if not self.category:
            raise ValidationError("Stress category must have a name.")
        if not self.description:
            raise ValidationError("Stress category must have a description.")
        
        super().clean()
        
    def save(self, *args, **kwargs):
        self.full_clean()  # Ensure validation is called before saving
        super().save(*args, **kwargs)
    

class WMSLayer(models.Model):
    name = models.CharField(max_length=200)
    display_name = models.CharField(max_length=200)
    url = models.URLField(max_length=500, help_text="Base WMS endpoint URL")
    layers_param = models.CharField(max_length=200, help_text="WMS layers parameter")
    color = models.CharField(max_length=7, default='#4a90d9')
    legend_url = models.URLField(max_length=500, blank=True, null=True)
    opacity = models.FloatField(default=0.7)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "WMS Layer"
        verbose_name_plural = "WMS Layers"
        
    def __str__(self):
        return self.display_name



class MeanRadiantTemperature(models.Model):
    """Mean Radiant Temperature (MRT) measurements"""
    raster = models.RasterField(srid=settings.COORDINATE_SYSTEM, null=True, blank=True, verbose_name="Tmrt Raster", help_text="Raster file containing Mean Radiant Temperature values in degrees Celsius.")
    date_time = models.DateTimeField(default=timezone.now)
    #TODO: Add additional info such as measurement method, source, etc.
    
    def __str__(self):
        return f"MRT Measurement at {self.date_time.strftime('%Y-%m-%d %H:%M:%S')}"
    
class UTCI(models.Model):
    """Universal Thermal Climate Index (UTCI) measurements"""
    raster = models.RasterField(srid=settings.COORDINATE_SYSTEM, null=True, blank=True, verbose_name="UTCI Raster", help_text="Raster file containing Universal Thermal Climate Index values in degrees Celsius.")
    category = models.ChoicesField(choices=StressCategory.objects.all(), null=True, blank=True, verbose_name="UTCI Category", help_text="Thermal stress category based on UTCI values (e.g., 'No Thermal Stress', 'Moderate Heat Stress', etc.)")
    date_time = models.DateTimeField(default=timezone.now)
    #TODO: Add additional info such as measurement method, source, etc.
    
    def __str__(self):
        return f"UTCI Measurement at {self.date_time.strftime('%Y-%m-%d %H:%M:%S')}"
    
class SkyViewFactor(models.Model):
    """Sky View Factor (SVF) measurements"""
    raster = models.RasterField(srid=settings.COORDINATE_SYSTEM, null=True, blank=True, verbose_name="SVF Raster", help_text="Raster file containing Sky View Factor values (0 to 1).")
    date_time = models.DateTimeField(default=timezone.now)
    #TODO: Add additional info such as measurement method, source, etc.
    
    def __str__(self):
        return f"SVF Measurement at {self.date_time.strftime('%Y-%m-%d %H:%M:%S')}"
    
class PET(models.Model):
    """Physiological Equivalent Temperature (PET) measurements"""
    raster = models.RasterField(srid=settings.COORDINATE_SYSTEM, null=True, blank=True, verbose_name="PET Raster", help_text="Raster file containing Physiological Equivalent Temperature values in degrees Celsius.")
    category = models.ChoicesField(choices=StressCategory.objects.all(), null=True, blank=True, verbose_name="PET Category", help_text="Thermal comfort category based on PET values (e.g., 'Cold Stress', 'Comfortable', 'Heat Stress', etc.)")
    date_time = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"PET Measurement at {self.date_time.strftime('%Y-%m-%d %H:%M:%S')}"
        
class LandSurfaceTemperature(models.Model):
    """Land Surface Temperature (LST) measurements"""
    raster = models.RasterField(srid=settings.COORDINATE_SYSTEM, null=True, blank=True, verbose_name="LST Raster", help_text="Raster file containing Land Surface Temperature values in degrees Celsius.")
    date_time = models.DateTimeField(default=timezone.now)
    #TODO: Add additional info such as measurement method, source, etc.
    
    def __str__(self):      return f"LST Measurement at {self.date_time.strftime('%Y-%m-%d %H:%M:%S')}"
    
class SurfaceUrbanHeatIslandIntensity(models.Model):
    """Surface Urban Heat Island Intensity (SUHII)) measurements"""
    raster = models.RasterField(srid=settings.COORDINATE_SYSTEM, null=True, blank=True, verbose_name="SUHII Raster", help_text="Raster file containing Surface Urban Heat Island Intensity values in degrees Celsius.")
    category = models.ChoicesField(choices=StressCategory.objects.all(), null=True, blank=True, verbose_name="SUHII Category", help_text="Thermal stress category based on SUHII values (e.g., 'No Heat Island Effect', 'Moderate Heat Island Effect', etc.)")
    date_time = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"SUHII Measurement at {self.date_time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    