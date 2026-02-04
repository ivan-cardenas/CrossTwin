from django.contrib.gis.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from common.models import Region, City, Neighborhood
from django.conf import settings

from .rasterOperations import interpolate_raster

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
    is_active = models.BooleanField(default=True, help_text="Whether the station is currently operational")
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class WeatherMeasurement(models.Model):
    """Time-series weather measurements from stations"""
    station = models.ForeignKey(
        WeatherStation, 
        on_delete=models.CASCADE, 
        related_name='measurements',
        help_text="Weather station that recorded this measurement"
    )
    date_time = models.DateTimeField(
        help_text="Date and time of the weather data",
        db_index=True
    )
    precipitation_mm = models.FloatField(
        null=True, blank=True,
        help_text="Precipitation in millimeters"
    )
    wind_speed_m_s = models.FloatField(
        null=True, blank=True,
        help_text="Wind speed in meters per second"
    )
    temperature_C = models.FloatField(
        null=True, blank=True,
        help_text="Air temperature in degrees Celsius"
    )
    solar_radiation_W_m2 = models.FloatField(
        null=True, blank=True,
        help_text="Solar radiation in Watts per square meter"
    )
    humidity_percent = models.FloatField(
        null=True, blank=True,
        help_text="Relative humidity in percentage"
    )
    vapor_pressure_hPa = models.FloatField(
        null=True, blank=True,
        help_text="Vapor pressure in hectopascals"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date_time']
        unique_together = ['station', 'date_time']
        indexes = [
            models.Index(fields=['date_time', 'station']),
        ]
    
    def __str__(self):
        return f"{self.station.name} - {self.date_time.strftime('%Y-%m-%d %H:%M')}"


class TmrtRaster(models.Model):
    """Mean Radiant Temperature raster layer"""
    name = models.CharField(
        max_length=200, 
        help_text="Descriptive name for this Tmrt layer"
    )
    raster = models.RasterField(
        srid=COORDINATE_SYSTEM, 
        help_text="Mean Radiant Temperature raster data",
        null=True,  # Allow null for interpolation
        blank=True
    )
    date_time = models.DateTimeField(
        help_text="Date and time this raster represents",
        db_index=True
    )
    region = models.ForeignKey(
        Region,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Region this raster covers (optional)"
    )
    bounds = models.PolygonField(
        srid=COORDINATE_SYSTEM,
        null=True,
        blank=True,
        help_text="Bounding box of this raster"
    )
    resolution_m = models.FloatField(
        default=10,
        help_text="Raster resolution in meters"
    )
    interpolation_method = models.CharField(
        max_length=50,
        choices=[
            ('idw', 'Inverse Distance Weighting'),
            ('kriging', 'Kriging'),
            ('spline', 'Spline'),
        ],
        default='idw',
        help_text="Spatial interpolation method used"
    )
    source_stations = models.ManyToManyField(
        WeatherStation,
        blank=True,
        help_text="Weather stations used for interpolation"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (min/max values, etc.)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date_time']
        verbose_name = "Tmrt Raster"
        verbose_name_plural = "Tmrt Rasters"
    
    def __str__(self):
        return f"{self.name} - {self.date_time.strftime('%Y-%m-%d %H:%M')}"
    
    def generate_from_measurements(self, measurement_datetime=None, bounds_geom=None, resolution=10, method='idw'):
        """
        Generate raster by interpolating weather measurements
        
        Args:
            measurement_datetime: DateTime to interpolate for (defaults to self.date_time)
            bounds_geom: Geometry to use as bounds (polygon or region)
            resolution: Cell size in meters
            method: Interpolation method
        """
        if measurement_datetime is None:
            measurement_datetime = self.date_time
        
        # Get measurements from around this time (e.g., within 1 hour)
        from datetime import timedelta
        time_window = timedelta(hours=1)
        
        measurements = WeatherMeasurement.objects.filter(
            date_time__gte=measurement_datetime - time_window,
            date_time__lte=measurement_datetime + time_window,
            station__is_active=True
        ).select_related('station')
        
        if not measurements.exists():
            raise ValidationError(f"No measurements found near {measurement_datetime}")
        
        # Prepare data for interpolation
        station_data = []
        stations_used = []
        
        for measurement in measurements:
            # Calculate Tmrt from weather variables
            # This is a simplified example - actual Tmrt calculation is complex
            # You'd need a proper formula considering solar radiation, temperature, wind, etc.
            tmrt_value = self._calculate_tmrt(
                temperature=measurement.temperature_C,
                solar_radiation=measurement.solar_radiation_W_m2,
                wind_speed=measurement.wind_speed_m_s
            )
            
            coord = measurement.station.geom
            station_data.append({
                'x': coord.x,
                'y': coord.y,
                'value': tmrt_value
            })
            stations_used.append(measurement.station)
        
        # Determine bounds
        if bounds_geom:
            bounds = bounds_geom.extent  # (min_x, min_y, max_x, max_y)
        elif self.region:
            bounds = self.region.geom.extent
        elif self.bounds:
            bounds = self.bounds.extent
        else:
            # Use convex hull of stations with buffer
            from django.contrib.gis.geos import MultiPoint
            points = MultiPoint([s.geom for s in WeatherStation.objects.filter(is_active=True)])
            buffered = points.convex_hull.buffer(1000)  # 1km buffer
            bounds = buffered.extent
            self.bounds = buffered
        
        # Perform interpolation
        raster_path = interpolate_raster(
            input_points=station_data,
            bounds=bounds,
            resolution=resolution,
            method=method
        )
        
        # Load the raster
        from django.contrib.gis.gdal import GDALRaster
        with open(raster_path, 'rb') as f:
            self.raster = f.read()
        
        # Store metadata
        self.resolution_m = resolution
        self.interpolation_method = method
        self.metadata = {
            'num_stations': len(station_data),
            'measurement_time': measurement_datetime.isoformat(),
            'bounds': bounds,
        }
        
        # Save and link stations
        self.save()
        self.source_stations.set(stations_used)
        
        return self
    
    def _calculate_tmrt(self, temperature, solar_radiation, wind_speed):
        """
        Calculate Mean Radiant Temperature from weather variables
        This is a simplified placeholder - use proper formula
        """
        if None in [temperature, solar_radiation, wind_speed]:
            return temperature  # Fallback
        
        # Simplified calculation - replace with proper Tmrt formula
        # Real Tmrt considers: solar radiation, surface temperatures, 
        # view factors, long-wave radiation, etc.
        return temperature + (solar_radiation / 100) - (wind_speed * 0.5)