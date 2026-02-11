import os
from django.contrib.gis.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from common.models import Region, City, Neighborhood
from django.conf import settings

from core.rasterOperations import interpolate_raster

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
        verbose_name = "Weather Station"
        verbose_name_plural = "Weather Stations"
    
    def __str__(self):
        return self.name


class Meteorology(models.Model):
    """Time-series weather measurements from stations"""
    station = models.ForeignKey(
        WeatherStation, 
        on_delete=models.CASCADE, 
        related_name='measurements',
        help_text="Weather station that recorded this measurement"
    )
    date = models.DateTimeField(
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
        ordering = ['-date']
        unique_together = ['station', 'date']
        indexes = [
            models.Index(fields=['date', 'station']),
        ]
        verbose_name = "Weather Measurement"
        verbose_name_plural = "Weather Measurements"
    
    def __str__(self):
        return f"{self.station.name} - {self.date.strftime('%Y-%m-%d %H:%M')}"
    


class InterpolatedRasterBase(models.Model):
    name = models.CharField(
            max_length=200,
            help_text="Descriptive name for this layer"
        )
    date = models.DateField(
        null=True,
        help_text="Date of the weather data",
        db_index=True
    )
    raster = models.RasterField(
        srid=COORDINATE_SYSTEM,
        null=True,
        blank=True,
        help_text="Interpolated raster data (stored in PostGIS)"
    )
    region = models.ForeignKey(
        'common.Region',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Region this raster covers"
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
        'WeatherStation',
        blank=True,
        help_text="Weather stations used for interpolation"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Statistics and metadata"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
        ordering = ['-date']
        
    def _calculate_bounds_from_raster(self):
        """Calculate bounds polygon from the raster's extent"""
        if not self.raster:
            return None
        
        from django.contrib.gis.geos import Polygon
        
        # Get the raster's extent
        extent = self.raster.extent
        min_x, min_y, max_x, max_y = extent
        
        # Create polygon from bounding box
        bounds_polygon = Polygon.from_bbox((min_x, min_y, max_x, max_y))
        bounds_polygon.srid = COORDINATE_SYSTEM
        
        return bounds_polygon
    
    def _get_interpolation_bounds(self, bounds_geom=None):
        """Determine bounds for interpolation"""
        if bounds_geom:
            return bounds_geom.extent
        elif self.region:
            return self.region.geom.extent
        elif self.bounds:
            return self.bounds.extent
        else:
            # Use active weather stations with buffer
            from django.contrib.gis.geos import MultiPoint
            stations = WeatherStation.objects.filter(is_active=True)
            if not stations.exists():
                raise ValidationError("No bounds specified and no active weather stations")
            
            points = MultiPoint([s.geom for s in stations])
            buffered = points.convex_hull.buffer(5000)  # 5km buffer
            self.bounds = buffered
            return buffered.extent
    
    def _bounds_to_polygon(self, bounds):
        """Convert extent tuple to Polygon"""
        from django.contrib.gis.geos import Polygon
        min_x, min_y, max_x, max_y = bounds
        return Polygon.from_bbox((min_x, min_y, max_x, max_y))
    
    def _get_measurements_in_window(self, measurement_datetime, time_window_hours, field_name):
        """
        Get measurements within time window for a specific field
        
        Args:
            measurement_datetime: Center datetime
            time_window_hours: Hours around center to include
            field_name: Field to extract (e.g., 'precipitation_mm', 'temperature_C')
        
        Returns:
            QuerySet of WeatherMeasurement
        """
        from datetime import timedelta
        
        time_window = timedelta(hours=time_window_hours)
        
        # Build filter dynamically to exclude null values for the specific field
        filter_kwargs = {
            'date__gte': measurement_datetime - time_window,
            'date__lte': measurement_datetime + time_window,
            'station__is_active': True,
            f'{field_name}__isnull': False,
        }
        
        return Meteorology.objects.filter(
            **filter_kwargs
        ).select_related('station')
    
    def _extract_station_data(self, measurements, field_name):
        """
        Extract point data from measurements
        
        Args:
            measurements: QuerySet of WeatherMeasurement
            field_name: Field to extract values from
        
        Returns:
            tuple: (station_data list, stations_used list)
        """
        station_data = []
        stations_used = []
        
        for measurement in measurements:
            coord = measurement.station.geom
            value = getattr(measurement, field_name)
            
            station_data.append({
                'x': coord.x,
                'y': coord.y,
                'value': value
            })
            stations_used.append(measurement.station)
        
        return station_data, stations_used
    
    def generate_from_measurements(self, measurement_datetime=None, 
                                   bounds_geom=None, resolution=10, 
                                   method='idw', time_window_hours=1):
        """
        Generate raster by interpolating measurements
        Must be implemented by child classes to specify which field to interpolate
        """
        raise NotImplementedError("Child classes must implement generate_from_measurements")
    
    @classmethod
    def generate_for_region(cls, region, datetime, resolution=10, method='idw'):
        """
        Convenience method to generate raster for a region
        
        Args:
            region: Region model instance
            datetime: DateTime to interpolate for
            resolution: Cell size in meters
            method: Interpolation method
        
        Returns:
            Raster instance
        """
        raster = cls.objects.create(
            name=f"{cls._meta.verbose_name} - {region.name}",
            date=datetime,
            region=region
        )
        raster.generate_from_measurements(
            measurement_datetime=datetime,
            bounds_geom=region.geom,
            resolution=resolution,
            method=method
        )
        return raster
    
    def _get_field_name(self):
        """
        Override in child classes to specify which measurement field to use
        """
        raise NotImplementedError("Child classes must implement _get_field_name")
    
    def _get_metadata_keys(self):
        """
        Override in child classes to specify metadata keys
        Returns tuple: (min_key, max_key, mean_key, unit)
        """
        raise NotImplementedError("Child classes must implement _get_metadata_keys")
    
    def generate_from_measurements(self, measurement_datetime=None, 
                                   bounds_geom=None, resolution=10, 
                                   method='idw', time_window_hours=1):
        """
        Generic interpolation method - works for all child classes
        """
        from django.contrib.gis.gdal import GDALRaster
        import os
        
        if measurement_datetime is None:
            measurement_datetime = self.date
        
        # Get the field name from child class
        field_name = self._get_field_name()
        
        # Get measurements
        measurements = self._get_measurements_in_window(
            measurement_datetime, 
            time_window_hours, 
            field_name
        )
        
        if not measurements.exists():
            raise ValidationError(
                f"No {field_name} measurements found near {measurement_datetime}"
            )
        
        # Extract station data
        station_data, stations_used = self._extract_station_data(
            measurements, 
            field_name
        )
        
        # Determine bounds
        bounds = self._get_interpolation_bounds(bounds_geom)
        
        # Perform interpolation
        raster_path = interpolate_raster(
            input_points=station_data,
            bounds=bounds,
            resolution=resolution,
            method=method
        )
        
        try:
            # Load the raster into PostGIS
            gdal_raster = GDALRaster(raster_path)
            self.raster = gdal_raster
            
            # Get metadata keys from child class
            min_key, max_key, mean_key, unit = self._get_metadata_keys()
            
            # Store metadata
            self.resolution_m = resolution
            self.interpolation_method = method
            self.bounds = self._bounds_to_polygon(bounds)
            self.metadata = {
                'num_stations': len(station_data),
                'measurement_time': measurement_datetime.isoformat(),
                'bounds': bounds,
                min_key: float(gdal_raster.bands[0].min),
                max_key: float(gdal_raster.bands[0].max),
                mean_key: float(gdal_raster.bands[0].mean),
                'unit': unit
            }
            
            # Save the model
            self.save()
            
            # Link source stations
            self.source_stations.set(stations_used)
            
        finally:
            # Clean up temporary file
            if os.path.exists(raster_path):
                os.remove(raster_path)
        
        return self
    
    def save(self, *args, **kwargs):
        # Auto-calculate bounds from raster if not already set
        if self.raster and not self.bounds:
            self.bounds = self._calculate_bounds_from_raster()
        
        self.full_clean()  # Ensure validation is called before saving
        super().save(*args, **kwargs)
    
class PrecipitationRaster(InterpolatedRasterBase):
    """Interpolated precipitation raster layer"""
    
    class Meta:
        verbose_name = "Precipitation Raster"
        verbose_name_plural = "Precipitation Rasters"
        indexes = [models.Index(fields=['date'])]
    
    def __str__(self):
        return f"Precipitation - {self.date.strftime('%Y-%m-%d')}"
    
    def _get_field_name(self):
        return 'precipitation_mm'
    
    def _get_metadata_keys(self):
        return ('min_precipitation_mm', 'max_precipitation_mm', 
                'mean_precipitation_mm', 'mm')


class TemperatureRaster(InterpolatedRasterBase):
    """Interpolated air temperature raster layer"""
    
    class Meta:
        verbose_name = "Temperature Raster"
        verbose_name_plural = "Temperature Rasters"
        indexes = [models.Index(fields=['date'])]
    
    def __str__(self):
        return f"Temperature - {self.date.strftime('%Y-%m-%d')}"
    
    def _get_field_name(self):
        return 'temperature_C'
    
    def _get_metadata_keys(self):
        return ('min_temperature_C', 'max_temperature_C', 
                'mean_temperature_C', '°C')


class WindSpeedRaster(InterpolatedRasterBase):
    """Interpolated wind speed raster layer"""
    
    class Meta:
        verbose_name = "Wind Speed Raster"
        verbose_name_plural = "Wind Speed Rasters"
        indexes = [models.Index(fields=['date'])]
    
    def __str__(self):
        return f"Wind Speed - {self.date.strftime('%Y-%m-%d')}"
    
    def _get_field_name(self):
        return 'wind_speed_m_s'
    
    def _get_metadata_keys(self):
        return ('min_wind_speed_m_s', 'max_wind_speed_m_s', 
                'mean_wind_speed_m_s', 'm/s')


class HumidityRaster(InterpolatedRasterBase):
    """Interpolated relative humidity raster layer"""
    
    class Meta:
        verbose_name = "Humidity Raster"
        verbose_name_plural = "Humidity Rasters"
        indexes = [models.Index(fields=['date'])]
    
    def __str__(self):
        return f"Humidity - {self.date.strftime('%Y-%m-%d')}"
    
    def _get_field_name(self):
        return 'humidity_percent'
    
    def _get_metadata_keys(self):
        return ('min_humidity_percent', 'max_humidity_percent', 
                'mean_humidity_percent', '%')
        
