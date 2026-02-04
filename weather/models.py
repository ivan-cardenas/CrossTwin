from django.db import models

# Create your models here.
from django.contrib.gis.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from common.models import Region, City, Neighborhood
from django.conf import settings

COORDINATE_SYSTEM = settings.COORDINATE_SYSTEM

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
    
class WeatherStation(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200, help_text="Name of the weather station")
    geom = models.PointField(srid=COORDINATE_SYSTEM, help_text="Location of the weather station")
    elevation_m = models.FloatField(help_text="Elevation of the station in meters")
    installation_date = models.DateField(help_text="Date when the station was installed")
    precipitation_mm_day = models.FloatField(help_text="Precipitation in millimeters per day")
    date_time = models.DateTimeField(help_text="Date and time of the weather data")
    wind_speed_m_s = models.FloatField(help_text="Wind speed in meters per second")
    temperature_C = models.FloatField(help_text="Temperature in degrees Celsius")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return self.name