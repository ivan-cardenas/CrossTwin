from django.contrib.gis.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from administrative.models import City, Neighborhood
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
    source = models.CharField(max_length=100, null=True, blank=True, help_text="Origin of the raster (e.g., 'SOLWEIG model output')")
    measurement_method = models.CharField(max_length=100, null=True, blank=True, help_text="Method used to derive the values (e.g., 'SOLWEIG', 'field measurement')")
    resolution = models.FloatField(null=True, blank=True, help_text="Spatial resolution of the raster in meters")
    cog_path = models.CharField(max_length=500, null=True, blank=True, help_text="Path to the exported Cloud-Optimized GeoTIFF served by TiTiler")
    climate_run = models.ForeignKey("weather.ClimateScenarioRun", on_delete=models.CASCADE, null=True, blank=True, related_name="+", help_text="Stored climate scenario run this result belongs to; empty = observed")

    def __str__(self):
        return f"MRT Measurement at {self.date_time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    class Meta:
        verbose_name = "Mean Radiant Temperature"
        verbose_name_plural = "Mean Radiant Temperature"
    
class UTCI(models.Model):
    """Universal Thermal Climate Index (UTCI) measurements"""
    raster = models.RasterField(srid=settings.COORDINATE_SYSTEM, null=True, blank=True, verbose_name="UTCI Raster", help_text="Raster file containing Universal Thermal Climate Index values in degrees Celsius.")
    category = models.ForeignKey(StressCategory, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="UTCI Category", help_text="Thermal stress category based on UTCI values (e.g., 'No Thermal Stress', 'Moderate Heat Stress', etc.)")
    date_time = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=100, null=True, blank=True, help_text="Origin of the raster (e.g., 'SOLWEIG model output')")
    measurement_method = models.CharField(max_length=100, null=True, blank=True, help_text="Method used to derive the values (e.g., 'SOLWEIG', 'field measurement')")
    resolution = models.FloatField(null=True, blank=True, help_text="Spatial resolution of the raster in meters")
    cog_path = models.CharField(max_length=500, null=True, blank=True, help_text="Path to the exported Cloud-Optimized GeoTIFF served by TiTiler")
    climate_run = models.ForeignKey("weather.ClimateScenarioRun", on_delete=models.CASCADE, null=True, blank=True, related_name="+", help_text="Stored climate scenario run this result belongs to; empty = observed")

    def __str__(self):
        return f"UTCI Measurement at {self.date_time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    class Meta:
        verbose_name = "Universal Thermal Climate Index"
        verbose_name_plural = "Universal Thermal Climate Index Measurements"
    
class WetBulbGlobeTemperature(models.Model):
    """Wet Bulb Globe Temperature (WBGT) - heat-stress measure combining air temperature,
    humidity, wind and radiation. Imported from the KNMI Data Platform (see
    importer/external_data.py::KNMIImporter)."""
    raster = models.RasterField(srid=settings.COORDINATE_SYSTEM, null=True, blank=True, verbose_name="WBGT Raster", help_text="Raster file containing Wet Bulb Globe Temperature values in degrees Celsius.")
    date_time = models.DateTimeField(default=timezone.now, help_text="Time the values are valid for (parsed from the KNMI file name)")
    source = models.CharField(max_length=100, null=True, blank=True, help_text="Origin of the raster (e.g., 'KNMI Data Platform')")
    measurement_method = models.CharField(max_length=100, null=True, blank=True, help_text="Method used to derive the values (e.g., 'KNMI WBGT analysis')")
    resolution = models.FloatField(null=True, blank=True, help_text="Spatial resolution of the raster in meters")
    cog_path = models.CharField(max_length=500, null=True, blank=True, help_text="Path to the exported Cloud-Optimized GeoTIFF served by TiTiler")
    climate_run = models.ForeignKey("weather.ClimateScenarioRun", on_delete=models.CASCADE, null=True, blank=True, related_name="+", help_text="Stored climate scenario run this result belongs to; empty = observed")

    def __str__(self):
        return f"WBGT Measurement at {self.date_time.strftime('%Y-%m-%d %H:%M:%S')}"

    class Meta:
        verbose_name = "Wet Bulb Globe Temperature"
        verbose_name_plural = "Wet Bulb Globe Temperature Measurements"


class SkyViewFactor(models.Model):
    """Sky View Factor (SVF) measurements"""
    raster = models.RasterField(srid=settings.COORDINATE_SYSTEM, null=True, blank=True, verbose_name="SVF Raster", help_text="Raster file containing Sky View Factor values (0 to 1).")
    date_time = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=100, null=True, blank=True, help_text="Origin of the raster (e.g., 'SOLWEIG model output')")
    measurement_method = models.CharField(max_length=100, null=True, blank=True, help_text="Method used to derive the values (e.g., 'SOLWEIG', 'field measurement')")
    resolution = models.FloatField(null=True, blank=True, help_text="Spatial resolution of the raster in meters")
    cog_path = models.CharField(max_length=500, null=True, blank=True, help_text="Path to the exported Cloud-Optimized GeoTIFF served by TiTiler")

    def __str__(self):
        return f"SVF Measurement at {self.date_time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    class Meta:
        verbose_name = "Sky View Factor"
        verbose_name_plural = "Sky View Factor"
    
class PET(models.Model):
    """Physiological Equivalent Temperature (PET) measurements"""
    raster = models.RasterField(srid=settings.COORDINATE_SYSTEM, null=True, blank=True, verbose_name="PET Raster", help_text="Raster file containing Physiological Equivalent Temperature values in degrees Celsius.")
    category = models.ForeignKey(StressCategory, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="PET Category", help_text="Thermal comfort category based on PET values (e.g., 'Cold Stress', 'Comfortable', 'Heat Stress', etc.)")
    date_time = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=100, null=True, blank=True, help_text="Origin of the raster (e.g., 'SOLWEIG model output')")
    measurement_method = models.CharField(max_length=100, null=True, blank=True, help_text="Method used to derive the values (e.g., 'SOLWEIG', 'field measurement')")
    resolution = models.FloatField(null=True, blank=True, help_text="Spatial resolution of the raster in meters")
    cog_path = models.CharField(max_length=500, null=True, blank=True, help_text="Path to the exported Cloud-Optimized GeoTIFF served by TiTiler")
    climate_run = models.ForeignKey("weather.ClimateScenarioRun", on_delete=models.CASCADE, null=True, blank=True, related_name="+", help_text="Stored climate scenario run this result belongs to; empty = observed")

    def __str__(self):
        return f"PET Measurement at {self.date_time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    class Meta:
        verbose_name = "Physiological Equivalent Temperature"
        verbose_name_plural = "Physiological Equivalent Temperature"
        
class LandSurfaceTemperature(models.Model):
    """Land Surface Temperature (LST) measurements"""
    raster = models.RasterField(srid=settings.COORDINATE_SYSTEM, null=True, blank=True, verbose_name="LST Raster", help_text="Raster file containing Land Surface Temperature values in degrees Celsius.")
    date_time = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=100, null=True, blank=True, help_text="Origin of the raster (e.g., 'Landsat 8/9', 'Sentinel-3', 'MODIS')")
    satellite_type = models.CharField(max_length=100, null=True, blank=True, help_text="Satellite or sensor that captured the thermal imagery (e.g., 'Landsat', 'Sentinel', 'MODIS', etc.)")
    measurement_method = models.CharField(max_length=100, null=True, blank=True, help_text="Method used to derive LST (e.g., 'Split-Window Algorithm', 'Single-Channel Algorithm')")
    resolution = models.FloatField(null=True, blank=True, help_text="Spatial resolution of the raster in meters")
    cog_path = models.CharField(max_length=500, null=True, blank=True, help_text="Path to the exported Cloud-Optimized GeoTIFF served by TiTiler")

    def __str__(self):
        return f"LST Measurement at {self.date_time.strftime('%Y-%m-%d %H:%M:%S')}"
    
class SurfaceUrbanHeatIslandIntensity(models.Model):
    """Surface Urban Heat Island Intensity (SUHII)) measurements"""
    raster = models.RasterField(srid=settings.COORDINATE_SYSTEM, null=True, blank=True, verbose_name="SUHII Raster", help_text="Raster file containing Surface Urban Heat Island Intensity values in degrees Celsius.")
    category = models.ForeignKey(StressCategory, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="SUHII Category", help_text="Thermal stress category based on SUHII values (e.g., 'No Heat Island Effect', 'Moderate Heat Island Effect', etc.)")
    date_time = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=100, null=True, blank=True, help_text="Origin of the raster (e.g., derived from LandSurfaceTemperature)")
    measurement_method = models.CharField(max_length=100, null=True, blank=True, help_text="Method used to compute SUHII (e.g., 'urban-rural LST differential')")
    resolution = models.FloatField(null=True, blank=True, help_text="Spatial resolution of the raster in meters")
    cog_path = models.CharField(max_length=500, null=True, blank=True, help_text="Path to the exported Cloud-Optimized GeoTIFF served by TiTiler")

    def __str__(self):
        return f"SUHII Measurement at {self.date_time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    class Meta:
        verbose_name = "Surface Urban Heat Island Intensity"
        verbose_name_plural = "Surface Urban Heat Island Intensity"
    

class NatureBasedSolutionPolygon(models.Model):
    """Nature-Based Solutions (NBS) for urban heat mitigation"""
    name = models.CharField(max_length=200, verbose_name="NBS Name", help_text="Name of the nature-based solution (e.g., 'Green Roof', 'Urban Tree Canopy', etc.)")
    description = models.TextField(verbose_name="NBS Description", help_text="Detailed description of the nature-based solution and its benefits for urban heat mitigation.")
    area = models.FloatField(verbose_name="NBS Area", help_text="Area of the nature-based solution in square meters.")
    geom = models.MultiPolygonField(srid=settings.COORDINATE_SYSTEM, verbose_name="NBS Geometry", help_text="Geometry of the nature-based solution (e.g., 'Green Roof', 'Urban Tree Canopy', etc.)")
    image = models.ImageField(upload_to='nbs_images/', null=True, blank=True, verbose_name="NBS Image", help_text="Optional image illustrating the nature-based solution.")
    
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Nature-Based Solution Polygon"
        verbose_name_plural = "Nature-Based Solution Polygons"
        
class NatureBasedSolutionPoint(models.Model):
    """Nature-Based Solutions (NBS) for urban heat mitigation"""
    name = models.CharField(max_length=200, verbose_name="NBS Name", help_text="Name of the nature-based solution (e.g., 'Green Roof', 'Urban Tree Canopy', etc.)")
    description = models.TextField(verbose_name="NBS Description", help_text="Detailed description of the nature-based solution and its benefits for urban heat mitigation.")
    geom = models.PointField(srid=settings.COORDINATE_SYSTEM, verbose_name="NBS Geometry", help_text="Location of the nature-based solution (e.g., 'Green Roof', 'Urban Tree Canopy', etc.)")
    image = models.ImageField(upload_to='nbs_images/', null=True, blank=True, verbose_name="NBS Image", help_text="Optional image illustrating the nature-based solution.")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Nature-Based Solution Point"
        verbose_name_plural = "Nature-Based Solution Points"

class NeighborhoodHeat(models.Model):
    """
    Heat and shade indicators per neighborhood, from the Klimaateffectatlas
    WFS (importer catalog kea_*, docs/KEA_WFS_MAPPING.md). One row per
    neighborhood; each KEA layer fills its own columns. The PET means are a
    vector summary of the PET node of core/DAG.dot (the PET raster model
    holds the full field); canopy cover informs Vegetation_Coverage. Stored
    inputs only, no DAG edge implemented.
    """
    id = models.BigAutoField(primary_key=True)
    neighborhood = models.OneToOneField(Neighborhood, verbose_name="Neighborhood", on_delete=models.DO_NOTHING, related_name="heat")
    petMean_2012_C = models.FloatField(null=True, blank=True, help_text="Mean perceived temperature (PET) on a hot day, 2012 surface model, °C (KEA GevoelstemperatuurBuurt_2012)")
    petMean_2022_C = models.FloatField(null=True, blank=True, help_text="Mean perceived temperature (PET) on a hot day, 2022 surface model, °C (KEA GevoelstemperatuurBuurt_2022)")
    heatClass_2022 = models.IntegerField(null=True, blank=True, help_text="RIVM PET class of the 2022 mean (KEA GevoelstemperatuurBuurt_2022.RIVMClass)")
    coolingIndoor_pct = models.FloatField(null=True, blank=True, help_text="Residents who can find cooling indoors, % (KEA SchaduwOpGebouwen_VerkoelingBinnen)")
    coolingOutdoor_pct = models.FloatField(null=True, blank=True, help_text="Residents who can find cooling outdoors, % (KEA SchaduwOpGebouwen_VerkoelingBinnen)")
    canopyCover_pct = models.FloatField(null=True, blank=True, help_text="Tree canopy cover of the land area, AHN4, % (KEA RMK_BuurtAggregaties)")
    shadeTotal_pct = models.FloatField(null=True, blank=True, help_text="Shaded land area, AHN4, % (KEA RMK_BuurtAggregaties)")
    shadeGreen_pct = models.FloatField(null=True, blank=True, help_text="Land area shaded by trees, AHN4, % (KEA RMK_BuurtAggregaties)")
    shadeGrey_pct = models.FloatField(null=True, blank=True, help_text="Land area shaded by buildings, AHN4, % (KEA RMK_BuurtAggregaties)")
    source = models.CharField(max_length=100, default="Klimaateffectatlas", help_text="Data provider")
    geom = models.MultiPolygonField(srid=settings.COORDINATE_SYSTEM)
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Heat {self.neighborhood_id}"

    class Meta:
        verbose_name = "Neighborhood Heat"
        verbose_name_plural = "Neighborhood Heat"


class ThermalComfortRun(models.Model):
    """
    One SOLWEIG thermal-comfort calculation for a map view and hour
    (urban_heat/solweig/, docs/THERMAL_COMFORT.md): the job the map's tool
    polls while it runs in the background, then the provenance of the Tmrt,
    UTCI and PET rasters it stored. Not a map layer (registry_hidden).
    """
    registry_hidden = True

    STATUS_CHOICES = [("queued", "Queued"), ("running", "Running"), ("done", "Done"), ("failed", "Failed")]

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="queued")
    message = models.TextField(blank=True, default="", help_text="Progress, or the error of a failed run")
    area = models.PolygonField(srid=settings.COORDINATE_SYSTEM, help_text="The view the results cover (storage CRS)")
    bbox_wgs84 = models.JSONField(help_text="The requested view: [west, south, east, north]")
    date_time = models.DateTimeField(help_text="Analysed hour (local, aware)")
    met = models.JSONField(help_text="Meteorological inputs: ta_c, rh_pct, wind_ms, wind_dir_deg, kdown_wm2, pressure_kpa, source; day values for PET: tmax_c, tmin_c, kdown_day_wm2, wind_day_ms")
    resolution = models.FloatField(help_text="Cell size in metres")
    device = models.CharField(max_length=20, blank=True, default="", help_text="'cuda' or 'cpu'")
    inputs = models.JSONField(default=dict, blank=True, help_text="DSM/DEM ids, building patches, land cover, sun position")
    stats = models.JSONField(default=dict, blank=True)
    mrt = models.ForeignKey(MeanRadiantTemperature, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    utci = models.ForeignKey(UTCI, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    pet = models.ForeignKey(PET, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    wbgt = models.ForeignKey(WetBulbGlobeTemperature, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
                             help_text="WBGT from Tmrt and the met (scenario runs only)")
    climate_run = models.ForeignKey("weather.ClimateScenarioRun", on_delete=models.CASCADE, null=True, blank=True,
                                    related_name="+", help_text="Climate scenario run that started it; empty = the map's tool")
    created = models.DateTimeField(auto_now_add=True)
    finished = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"SOLWEIG run {self.pk} ({self.status}) for {self.date_time:%Y-%m-%d %H:%M}"



class ScenarioHeat(models.Model):
    """
    Heat stress of a stored KNMI'23 climate scenario run
    (weather.ClimateScenarioRun): one SOLWEIG run over the run's map view and
    hour with the observed weather moved into the scenario (`thermal_run`,
    climate.apply_to_weather / apply_to_day_values), giving Tmrt, UTCI, PET
    and WBGT rasters tagged with the run. The current-climate column reuses an
    observed SOLWEIG run of the same hour that covers the view
    (`thermal_baseline`, e.g. from the Thermal Comfort tool) when there is
    one: no second run is started. The observed met and the shifted met are
    kept for reproducibility.

    LST is not calculated: it depends on the surface reflectance a satellite
    measures. SUHII (LST-based) stays the observed raster: a uniform climate
    shift leaves the urban-rural difference unchanged.
    Created by urban_heat/signals.py. Not a map layer.
    """
    registry_hidden = True

    STATUS_CHOICES = [("pending", "Pending"), ("queued", "Queued"), ("done", "Done"),
                      ("failed", "Failed"), ("unavailable", "SOLWEIG not installed"), ("skipped", "Not requested")]

    run = models.OneToOneField("weather.ClimateScenarioRun", on_delete=models.CASCADE, related_name="heat")
    thermal_baseline = models.ForeignKey(ThermalComfortRun, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    thermal_run = models.ForeignKey(ThermalComfortRun, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    met_observed = models.JSONField(null=True, blank=True, help_text="Observed met of the hour (SOLWEIG Met fields)")
    met_scenario = models.JSONField(null=True, blank=True, help_text="The same met moved into the scenario")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    message = models.TextField(blank=True, default="")
    # Means over the view: baseline (observed weather) and scenario.
    tmrt_now = models.FloatField(null=True, blank=True)
    tmrt_scenario = models.FloatField(null=True, blank=True)
    utci_now = models.FloatField(null=True, blank=True)
    utci_scenario = models.FloatField(null=True, blank=True)
    pet_now = models.FloatField(null=True, blank=True)
    pet_scenario = models.FloatField(null=True, blank=True)
    wbgt_now = models.FloatField(null=True, blank=True)
    wbgt_scenario = models.FloatField(null=True, blank=True)
    last_updated = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Scenario Heat"
        verbose_name_plural = "Scenario Heat"

    def save(self, *args, **kwargs):
        """
        DAG edges: Climate_Change -> Meteorology -> Tmrt, UTCI, PET, WBGT
        met_scenario = the run's observed hour (run.parameters['met_observed'])
        moved into the scenario: climate.apply_to_weather for the hour,
        climate.apply_to_day_values for PET's day values.
        The scenario means come from `thermal_run`, the current ones from the
        latest finished observed run of the same hour covering the view
        (scenario.find_baseline; WBGT from its Tmrt when it stored none); the
        status is that of `thermal_run`. Missing runs keep the stored values.
        """
        from weather.calculations import climate

        from .solweig.scenario import baseline_wbgt_mean, find_baseline

        run = self.run
        observed = (run.parameters or {}).get("met_observed")
        if observed:
            month = run.analysis_datetime.month if run.analysis_datetime else None
            shifted = climate.apply_to_weather(observed, run.scenario, month, run.heat_mode, run.station)
            shifted = climate.apply_to_day_values(shifted, run.scenario, run.heat_mode, month, run.station)
            shifted["source"] = f"KNMI23 {run.scenario} {run.heat_mode} on {observed.get('source', '')}"[:60]
            self.met_observed, self.met_scenario = observed, shifted
        if self.thermal_baseline is None and self.thermal_run is not None:
            self.thermal_baseline = find_baseline(run)
        thermal = self.thermal_run
        if thermal is not None:
            if thermal.status == "failed":
                self.status, self.message = "failed", thermal.message
            elif thermal.status == "done":
                self.status, self.message = "done", ""
            elif self.status not in ("unavailable", "skipped"):
                self.status = "queued"
        for prefix, run in (("now", self.thermal_baseline), ("scenario", self.thermal_run)):
            stats = (run.stats or {}) if run is not None and run.status == "done" else {}
            for name, key in (("tmrt", "tmrt"), ("utci", "utci"), ("pet", "pet"), ("wbgt", "wbgt")):
                mean = (stats.get(key) or {}).get("mean")
                if mean is not None:
                    setattr(self, f"{name}_{prefix}", mean)
        if self.wbgt_now is None and self.thermal_baseline is not None:
            self.wbgt_now = baseline_wbgt_mean(self.thermal_baseline)
        self.last_updated = timezone.now()
        super().save(*args, **kwargs)


class HeatInputChange(models.Model):
    """
    When an input of the heat model last changed (land cover, soil, the DSM,
    buildings): the Scenarios panel suggests rerunning a scenario's heat model
    when its SOLWEIG runs are older (urban_heat/signals.py writes it, at most
    once a minute per input, also after bulk imports). Bookkeeping, not a
    DAG node or map layer.
    """
    registry_hidden = True

    input = models.CharField(max_length=40, unique=True)
    changed_at = models.DateTimeField()

    class Meta:
        verbose_name = "Heat Model Input Change"
        verbose_name_plural = "Heat Model Input Changes"

    def __str__(self):
        return f"{self.input} changed {self.changed_at:%Y-%m-%d %H:%M}"
