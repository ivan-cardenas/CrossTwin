from django.utils import timezone
from django.contrib.gis.db import models

from django.conf import settings

CoordinateSystem = settings.COORDINATE_SYSTEM


def material_choices(field_kind):
    """limit_choices_to of a material FK: the categories that fit the field, plus uncategorised rows."""
    return (models.Q(category__in=MATERIAL_CATEGORIES_FOR[field_kind])
            | models.Q(category__isnull=True) | models.Q(category=""))


# Named functions (not lambdas): limit_choices_to callables end up in migrations.
def land_cover_materials():
    return material_choices("land_cover")


def roof_materials():
    return material_choices("roof")


def street_materials():
    return material_choices("street")


class LandCoverClasses(models.Model):
    id = models.AutoField(primary_key=True)
    class_name = models.CharField(max_length=100, help_text="Name of the land cover class (e.g., 'Urban', 'Forest', 'Agriculture', etc.)")
    description = models.TextField(help_text="Detailed description of the land cover class")
    default_material = models.ForeignKey(
        "SurfaceMaterialProperties", on_delete=models.DO_NOTHING, null=True, blank=True,
        limit_choices_to=land_cover_materials,
        help_text="Surface material (and albedo) assumed for polygons of this class without a measured albedo; "
                  "derived from the class name on save (physicalEnv/albedo.py)")
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.class_name

    def save(self, *args, **kwargs):
        if self.default_material_id is None:
            from .albedo import default_material_for
            self.default_material = default_material_for(self.class_name)
        super().save(*args, **kwargs)

class HILUCSLandUse(models.Model):
    """
    INSPIRE HILUCS land-use classification
    (http://inspire.ec.europa.eu/codelist/HILUCSValue), stored once and
    referenced by FK so land-use rows carry a smallint instead of the URI.
    The 98 registry values are loaded by migration 0003; physicalEnv/hilucs.py
    turns a HILUCS URI into its code.
    """
    id = models.SmallAutoField(primary_key=True)
    code = models.CharField(max_length=10, unique=True, help_text="Hierarchical HILUCS code, e.g. '6.3.2'")
    label = models.CharField(max_length=200, help_text="Registry label, e.g. 'water areas not in other economic use'")
    description = models.TextField(blank=True, help_text="Registry definition of the class")

    def __str__(self):
        return f"{self.code} {self.label}"

    class Meta:
        ordering = ["code"]
        verbose_name = "HILUCS Land Use"
        verbose_name_plural = "HILUCS Land Uses"


class SoilType(models.Model):
    """
    A soil unit of the Dutch soil map (Bodemkaart 1:50 000, BIS Nederland),
    stored once and referenced by SoilArea. save() derives the hydrologic
    soil group from the soil name and its infiltration rate range from the
    group (physicalEnv/soil.py).
    """
    SOIL_GROUP_CHOICES = [
        ('A', 'A: sand, gravel (low runoff)'),
        ('B', 'B: loam, silt loam (moderate runoff)'),
        ('C', 'C: clay loam (moderately high runoff)'),
        ('D', 'D: clay, peat (high runoff)'),
    ]

    id = models.SmallAutoField(primary_key=True)
    code = models.CharField(max_length=20, help_text="Soil code of the soil map, e.g. 'Hn21'")
    name = models.CharField(max_length=200, help_text="Soil name of the soil map, e.g. 'Veldpodzolgronden; leemarm en zwak lemig fijn zand'")
    unitCode = models.CharField(max_length=20, null=True, blank=True, help_text="Main soil unit of the map legend (first_soilcode), e.g. 'Hn21' for 'Hn21/Hd21'; colours the soil map (mainMap/styles/soilStyles.py)")
    unitName = models.CharField(max_length=200, null=True, blank=True, help_text="Legend name of the main soil unit (first_soilname)")
    soilGroup = models.CharField(max_length=1, choices=SOIL_GROUP_CHOICES, null=True, blank=True, help_text="Hydrologic soil group (SCS), derived from the soil name's texture")
    infiltrationMin_mm_h = models.FloatField(null=True, blank=True, help_text="Lower bound of the final infiltration rate of the soil group, mm/h")
    infiltrationMax_mm_h = models.FloatField(null=True, blank=True, help_text="Upper bound of the final infiltration rate of the soil group, mm/h (empty for group A: no upper bound)")

    def save(self, *args, **kwargs):
        from .soil import SOIL_GROUPS, classify_soil_group
        self.soilGroup = classify_soil_group(self.name)
        rates = SOIL_GROUPS.get(self.soilGroup, {})
        self.infiltrationMin_mm_h = rates.get('min_mm_h')
        self.infiltrationMax_mm_h = rates.get('max_mm_h')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} {self.name}"

    class Meta:
        # one code appears with two names in the 2025 map (zVp)
        constraints = [models.UniqueConstraint(fields=['code', 'name'], name='unique_soil_code_name')]
        ordering = ['code']
        verbose_name = "Soil Type"
        verbose_name_plural = "Soil Types"


class SoilArea(models.Model):
    """A polygon of the Dutch soil map, typed by SoilType."""
    id = models.AutoField(primary_key=True)
    mapAreaID = models.CharField(max_length=100, unique=True, help_text="maparea_id of the soil map, e.g. 'V2025-1..soilarea.0000016921'")
    soil_type = models.ForeignKey(SoilType, on_delete=models.DO_NOTHING, related_name='areas')
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.mapAreaID} ({self.soil_type_id})"

    class Meta:
        verbose_name = "Soil Area"
        verbose_name_plural = "Soil Areas"


class SurfaceMaterialProperties(models.Model):
    """
    A surface and its shortwave albedo. The rows seeded by migration 0013 are
    Table 5.1 of Oke et al. (2017), Urban Climates (albedo of individual
    urban and natural materials and of urban areas, given as a range or an
    average); `albedo` is the table's average where it gives one, else the
    midpoint of the range. They are the options of every material field
    (land cover, roofs, streets) in the importer and the map editor;
    `category` limits each field to the surfaces that fit it
    (MATERIAL_CATEGORIES_FOR). Rows can be imported by `code` or name.
    """
    NATURAL = "Natural surfaces"
    URBAN = "Urban surface materials"
    URBAN_AREAS = "Urban areas"

    CATEGORY_CHOICES = [
        ("bare_ground", "Bare ground"),
        ("low_vegetation", "Low vegetation"),
        ("forests", "Forests"),
        ("water", "Water"),
        ("snow_ice", "Snow and ice"),
        ("roads", "Roads"),
        ("walls", "Walls"),
        ("roofs", "Roofs"),
        ("windows", "Windows"),
        ("paints", "Paints"),
        ("metals", "Metals"),
        ("urban_areas", "Urban areas"),
    ]
    GROUPS = {
        "bare_ground": NATURAL, "low_vegetation": NATURAL, "forests": NATURAL, "water": NATURAL,
        "snow_ice": NATURAL, "roads": URBAN, "walls": URBAN, "roofs": URBAN, "windows": URBAN,
        "paints": URBAN, "metals": URBAN, "urban_areas": URBAN_AREAS,
    }

    id = models.AutoField(primary_key=True)
    code = models.SlugField(max_length=60, unique=True, null=True, blank=True, help_text="Stable key for imports, e.g. 'roof_tile_clay'")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, null=True, blank=True, help_text="Group of Oke et al. (2017) Table 5.1; limits which fields offer this material")
    material_name = models.CharField(max_length=100, help_text="Name of the material (e.g., 'Concrete', 'Asphalt', 'Grass', etc.)")
    albedo = models.FloatField(help_text="Typical albedo (0-1): the table's average, else the midpoint of the range")
    albedo_min = models.FloatField(null=True, blank=True, help_text="Lower end of the albedo range")
    albedo_max = models.FloatField(null=True, blank=True, help_text="Upper end of the albedo range")
    note = models.CharField(max_length=200, blank=True, default="", help_text="Conditions behind the range (e.g. 'fresh -> weathered')")
    source = models.CharField(max_length=200, blank=True, default="", help_text="Reference of the values")
    thermal_conductivity = models.FloatField(null=True, blank=True, help_text="Thermal conductivity in W/(m*K)")
    specific_heat_capacity = models.FloatField(null=True, blank=True, help_text="Specific heat capacity in J/(kg*K)")
    density = models.FloatField(null=True, blank=True, help_text="Density in kg/m3")
    last_updated = models.DateTimeField(default=timezone.now)

    def albedo_label(self):
        if self.albedo_min is not None and self.albedo_max is not None and self.albedo_min != self.albedo_max:
            return f"α {self.albedo_min:.2f}–{self.albedo_max:.2f}"
        return f"α {self.albedo:.2f}"

    def __str__(self):
        group = self.get_category_display() if self.category else None
        name = f"{group}: {self.material_name}" if group else self.material_name
        return f"{name} ({self.albedo_label()})"

    @classmethod
    def lookup(cls, value):
        """
        The material an imported value names: its code, its name
        (case-insensitive; 'Category: Name' when a name is used in several
        categories, e.g. 'Walls: Concrete'), or its id. None when nothing matches.
        """
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        found = cls.objects.filter(code__iexact=text).first()
        if found:
            return found
        if ":" in text:
            group, _, name = text.partition(":")
            labels = {label.lower(): key for key, label in cls.CATEGORY_CHOICES}
            key = labels.get(group.strip().lower())
            if key:
                found = cls.objects.filter(category=key, material_name__iexact=name.strip()).first()
                if found:
                    return found
        found = cls.objects.filter(material_name__iexact=text).order_by("pk").first()
        if found:
            return found
        return cls.objects.filter(pk=int(text)).first() if text.isdigit() else None

    class Meta:
        verbose_name = "Surface Material Properties"
        verbose_name_plural = "Surface Material Properties"
        ordering = ["category", "material_name"]


# Which material categories each material field offers (importer and map
# editor choices, via limit_choices_to). Walls have their own model
# (WallMaterialProperties), but their albedos are listed for reference.
MATERIAL_CATEGORIES_FOR = {
    "land_cover": ["bare_ground", "low_vegetation", "forests", "water", "snow_ice", "roads", "urban_areas"],
    "roof": ["roofs", "paints", "metals"],
    "street": ["roads"],
}

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
    city = models.ForeignKey("administrative.City", on_delete=models.DO_NOTHING, help_text="City code from administrative.City", null=True, blank=True)
    year = models.IntegerField()
    land_cover_type = models.ForeignKey(LandCoverClasses, on_delete=models.DO_NOTHING, help_text="Type of land cover (e.g., 'Urban', 'Forest', 'Agriculture', etc.)")
    land_use = models.CharField(max_length=100, help_text="Land use type (e.g., 'Residential', 'Commercial', 'Industrial', 'Park', etc.)")
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    # This polygon's area as a percentage of its City's area_km2, derived on
    # every save by physicalEnv/signals.py::landcover_percentage (pre_save,
    # not save(): the model is bulk-written) and set-based by
    # landcover.refresh_percentages for bulk imports and changed city
    # boundaries. Null when the row has no city.
    # #TODO: Vegetation Coverage and Builtup Coverage as additional fields?
    percentage = models.FloatField(null=True, blank=True, help_text="Percentage of the City covered by this polygon (derived from its area and the City's area)")
    # Nullable: not every land-cover source can tell us a surface material.
    # PDOK's BRT Bodemgebruik WFS (pdok_landcover_brt) only classifies land
    # cover (landCoverObservationClass), it carries no material/albedo/
    # thermal-property data, so those rows leave this unset rather than
    # guessing a material.
    material = models.ForeignKey(SurfaceMaterialProperties, on_delete=models.DO_NOTHING, null=True, blank=True,
                                 limit_choices_to=land_cover_materials,
                                 help_text="Surface material (Oke et al. 2017 Table 5.1); its albedo applies when no albedo was measured")
    # Set on the urban-fabric ring around a building drawn in the map editor
    # (physicalEnv/landcover.py): moving or deleting that building releases
    # this ring. Plain id, not an FK: builtup already depends on physicalEnv.
    source_building = models.BigIntegerField(null=True, blank=True, db_index=True, help_text="Editor building whose 10 m urban-fabric buffer this polygon is")
    # Set on the green-area polygon of a park drawn in the map editor
    # (physicalEnv/landcover.py::green_area); released like a building ring.
    source_park = models.IntegerField(null=True, blank=True, db_index=True, help_text="Editor park whose outline this green-area polygon is")
    # Measured (Sentinel-2 broadband albedo, zonal mean: physicalEnv/albedo.py::measure)
    # or estimated for editor polygons (building roof + paving). Empty: the
    # class default through `material` applies (effective_albedo).
    albedo = models.FloatField(null=True, blank=True, help_text="Shortwave broadband albedo (0-1) measured over this polygon, or estimated for editor polygons")
    albedo_source = models.CharField(max_length=100, null=True, blank=True, help_text="Where albedo comes from, e.g. 'Sentinel-2 2025-07-14' or 'editor: building -12'")
    albedo_date = models.DateField(null=True, blank=True, help_text="Acquisition date of the imagery albedo was measured on")
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.city} - {self.year}: {self.land_cover_type} ({self.percentage}%)"

    @property
    def effective_albedo(self):
        """Measured or estimated albedo, else the albedo of the polygon's material (class default)."""
        if self.albedo is not None:
            return self.albedo
        return self.material.albedo if self.material_id else None


class UrbanFabricCut(models.Model):
    """
    A piece an editor building's urban-fabric ring (or an editor park's green
    area) cut out of another land-cover polygon (physicalEnv/landcover.py).
    Releasing the ring (the building or park moved or was deleted) gives each
    piece back to `target`, or recreates `target` with the attributes copied
    here when it was swallowed whole. Exactly one owner is set. Not a map
    layer (registry_hidden).
    """
    registry_hidden = True

    owner_building = models.BigIntegerField(null=True, blank=True, db_index=True, help_text="Editor building whose ring took this piece")
    owner_park = models.IntegerField(null=True, blank=True, db_index=True, help_text="Editor park whose green area took this piece")
    target = models.IntegerField(db_index=True, help_text="Id of the LandCoverVector row the piece was cut from")
    city = models.ForeignKey("administrative.City", on_delete=models.DO_NOTHING, null=True, blank=True)
    year = models.IntegerField()
    land_cover_type = models.ForeignKey(LandCoverClasses, on_delete=models.DO_NOTHING)
    land_use = models.CharField(max_length=100)
    material = models.ForeignKey(SurfaceMaterialProperties, on_delete=models.DO_NOTHING, null=True, blank=True)
    source_building = models.BigIntegerField(null=True, blank=True, db_index=True, help_text="The target's own source_building (set when the target is another ring)")
    source_park = models.IntegerField(null=True, blank=True, db_index=True, help_text="The target's own source_park (set when the target is a park's green area)")
    albedo = models.FloatField(null=True, blank=True)
    albedo_source = models.CharField(max_length=100, null=True, blank=True)
    albedo_date = models.DateField(null=True, blank=True)
    geom = models.MultiPolygonField(srid=CoordinateSystem)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(owner_building__isnull=False, owner_park__isnull=True)
                           | models.Q(owner_building__isnull=True, owner_park__isnull=False)),
                name="urbanfabriccut_one_owner",
            ),
        ]

    def __str__(self):
        owner = f"building {self.owner_building}" if self.owner_building is not None else f"park {self.owner_park}"
        return f"Cut of land cover {self.target} by {owner}"


class DSMBuildingPatch(models.Model):
    """
    A map-editor change of one building, applied on top of every DSM when it is
    read for analysis (physicalEnv/dsm_patches.py::apply_patches): the original
    footprint goes back to ground level, then the current footprint is raised
    to ground + height_m. The DSM COG itself is never rewritten. Not a map
    layer (registry_hidden).

    DAG edge: Buildings -> DSM.
    """
    registry_hidden = True

    building_id = models.BigIntegerField(unique=True, help_text="Id of the edited builtup.Building")
    original_footprint = models.MultiPolygonField(srid=CoordinateSystem, null=True, blank=True, help_text="Footprint before the first edit (None: drawn in the editor)")
    footprint = models.MultiPolygonField(srid=CoordinateSystem, null=True, blank=True, help_text="Current footprint (None: deleted)")
    height_m = models.FloatField(null=True, blank=True, help_text="Height above ground; None: the footprint is only cleared")
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"DSM patch for building {self.building_id}"


class DSMVegetationPatch(models.Model):
    """
    A map-editor change of one tree (nature.Tree: its crown disc) or forest
    (nature.Forests: its polygon), applied on top of every DSM when it is read
    for analysis (physicalEnv/dsm_patches.py::apply_patches):

        tree    original crown -> tall vegetation cleared to ground, then the
                current crown is raised to ground + a paraboloid of canopy_m
        forest  original minus current polygon -> tall vegetation cleared,
                current minus original polygon -> ground + canopy_m (flat)

    Building footprints are never cleared. The DSM COG itself is never
    rewritten. Not a map layer (registry_hidden).

    DAG edge: Vegetation_Coverage -> DSM.
    """
    registry_hidden = True
    SOURCES = [("nature.Tree", "Tree"), ("nature.Forests", "Forest")]

    source = models.CharField(max_length=40, choices=SOURCES, help_text="Model of the edited vegetation")
    source_id = models.BigIntegerField(help_text="Id of the edited tree or forest")
    original_geom = models.MultiPolygonField(srid=CoordinateSystem, null=True, blank=True, help_text="Crown disc or polygon before the first edit (None: drawn in the editor)")
    geom = models.MultiPolygonField(srid=CoordinateSystem, null=True, blank=True, help_text="Current crown disc or polygon (None: deleted)")
    canopy_m = models.FloatField(null=True, blank=True, help_text="Canopy height above ground; None: only cleared")
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["source", "source_id"], name="unique_vegetation_patch")]

    def __str__(self):
        return f"DSM patch for {self.source} {self.source_id}"


class DSMEdit(models.Model):
    """
    Append-only log of the areas where the DSM overlay changed (a patch saved,
    restored or deleted). SVF and thermal-comfort results calculated before an
    edit that overlaps them are stale (dsm_patches.stale_results).
    """
    registry_hidden = True

    area = models.PolygonField(srid=CoordinateSystem, help_text="Bounding box of the old and new footprint")
    at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"DSM edit at {self.at:%Y-%m-%d %H:%M}"

class LandCoverRaster(models.Model):
    id = models.AutoField(primary_key=True)
    city = models.ForeignKey("administrative.City", on_delete=models.DO_NOTHING, help_text="City code from administrative.City", null=True, blank=True)
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
    city = models.ForeignKey("administrative.City", on_delete=models.DO_NOTHING, help_text="City code from administrative.City", null=True, blank=True)
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
    city = models.ForeignKey("administrative.City", on_delete=models.DO_NOTHING, help_text="City code from administrative.City", null=True, blank=True)
    year = models.IntegerField()
    date = models.DateTimeField(null=True, blank=True, help_text="Acquisition/generation date of the elevation model")
    source = models.CharField(max_length=100, null=True, blank=True, help_text="Data provider of the raster (e.g., 'AHN4 (PDOK)')")
    resolution = models.FloatField(null=True, blank=True, help_text="Spatial resolution of the raster in meters")
    dem_raster = models.RasterField(srid=CoordinateSystem, null=True, blank=True, help_text="Raster file containing elevation values")
    cog_path = models.CharField(max_length=500, null=True, blank=True, help_text="Path to the exported Cloud-Optimized GeoTIFF served by TiTiler")
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.city} - {self.year}: Digital Elevation Model"

class GroundwaterDepth(models.Model):
    """
    Groundwater depth statistic (GHG/GLG/GVG) of the BIS Nederland
    groundwater model, 50 m cells in cm below ground level. Values are
    capped at 254 (= 254 cm or deeper); 255 is nodata. Kept in Postgres (no
    SKIP_RASTER_DB_STORAGE): physicalEnv/soil.py reads GHG with PostGIS
    raster SQL to mark shallow groundwater for the SCS soil groups.
    """
    STATISTIC_CHOICES = [
        ('GHG', 'GHG: mean highest groundwater level'),
        ('GLG', 'GLG: mean lowest groundwater level'),
        ('GVG', 'GVG: mean spring groundwater level'),
    ]

    id = models.AutoField(primary_key=True)
    city = models.ForeignKey("administrative.City", on_delete=models.DO_NOTHING, help_text="City code from administrative.City", null=True, blank=True)
    year = models.IntegerField()
    statistic = models.CharField(max_length=3, choices=STATISTIC_CHOICES, help_text="Which groundwater level statistic the raster holds")
    source = models.CharField(max_length=100, null=True, blank=True, help_text="Data provider of the raster (e.g., 'BIS Nederland')")
    resolution = models.FloatField(null=True, blank=True, help_text="Spatial resolution of the raster in meters")
    depth_raster = models.RasterField(srid=CoordinateSystem, null=True, blank=True, help_text="Groundwater depth in cm below ground level (254 = 254 cm or deeper, 255 = nodata)")
    cog_path = models.CharField(max_length=500, null=True, blank=True, help_text="Path to the exported Cloud-Optimized GeoTIFF served by TiTiler")
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.city} - {self.year}: {self.statistic}"

    class Meta:
        verbose_name = "Groundwater Depth"
        verbose_name_plural = "Groundwater Depths"


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
    city = models.ForeignKey("administrative.City", on_delete=models.DO_NOTHING, help_text="City code from administrative.City", null=True, blank=True)
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
    price_EUR_droughtDamage_m3 = models.FloatField()
    last_updated = models.DateTimeField(default=timezone.now)


    def __str__(self):
        return f"Environmental costs ({self.last_updated:%Y-%m-%d}): {self.price_EUR_kg_CO2} EUR/kg CO2, {self.price_EUR_droughtDamage_m3} EUR/m3 drought"

    @classmethod
    def current(cls):
        """The most recent cost record (the model has no province/year), or None."""
        return cls.objects.order_by('-last_updated', '-id').first()
