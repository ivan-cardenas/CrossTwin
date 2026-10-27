from django.utils import timezone
from django.contrib.gis.db import models
from django.contrib.postgres.fields import ArrayField
from django.db.models import Sum
from administrative.models import City, Neighborhood
from physicalEnv.models import HILUCSLandUse, SurfaceMaterialProperties, WallMaterialProperties
from Energy.models import EnergyEfficiencyLabels

from django.conf import settings

CoordinateSystem = settings.COORDINATE_SYSTEM


class ZoningArea(models.Model):
    id = models.AutoField(primary_key=True)
    neighborhood = models.ForeignKey(Neighborhood, verbose_name="Neighborhood", on_delete=models.DO_NOTHING)

    zone_type = models.ForeignKey(HILUCSLandUse, on_delete=models.DO_NOTHING, null=True, blank=True, related_name="zoning_areas", help_text="HILUCS land use of the zoning area (INSPIRE planned land use hilucsLandUse), where known")
    # Dutch legal plan instrument from INSPIRE Planned Land Use's
    # planTypeName codelist (e.g. 'bestemmingsplan', 'wijzigingsplan',
    # 'omgevingsvergunning') — populated by the pdok_landcover_kadaster
    # import.
    plan_type = models.CharField(max_length=100, null=True, blank=True, help_text="Dutch legal plan instrument (e.g. 'bestemmingsplan'), where the zoning geometry comes from a legal spatial plan")
    valid_from = models.DateField(null=True, blank=True, help_text="Date the legal plan took effect, where known")
    description = models.TextField(null=True, blank=True, help_text="Detailed description of the zoning area")
    area = models.FloatField(help_text="Area of the zoning area in square meters")
    benchmarkPrice_per_sqm = models.FloatField(null=True, blank=True, help_text="Benchmark price per square meter in EUR")
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    
    def __str__(self):
        return f"Zoning Area {self.id} ({self.zone_type})"
    
    def save(self, *args, **kwargs):
        if self.geom:
            self.area = self.geom.area
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Zoning Area"
        verbose_name_plural = "Zoning Areas"


class Street(models.Model):
    id = models.AutoField(primary_key=True)
    inspireID = models.CharField(max_length=100, unique=True, help_text="Unique identifier for the street from INSPIRE dataset", null=True, blank=True)
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
    sourceID = models.CharField(max_length=100, unique=True, null=True, blank=True, help_text="Identifier in the source dataset, e.g. 'osm:way/123' for OpenStreetMap")
    name = models.CharField(max_length=100, help_text="Name of the park")
    area = models.FloatField(help_text="Area of the park in square meters")
    vegetationType = models.CharField(max_length=100, null=True, blank=True, help_text="Type of vegetation in the park (e.g., grass, trees, shrubs), where known")
    neighborhood = models.ForeignKey(Neighborhood, on_delete=models.DO_NOTHING, null=True, blank=True, help_text="City code from administrative.City")
    geom = models.MultiPolygonField(srid=CoordinateSystem)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.geom:
            self.area = self.geom.area
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Park"
        verbose_name_plural = "Parks"
      
class Facility(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, help_text="Name of the facility")
    type = models.CharField(max_length=100, choices=[('school', 'School'), ('hospital', 'Hospital'), ('fire_station', 'Fire Station'), 
                                                     ('police_station', 'Police Station'), ('market', 'Market'), ('transportNode', 'Transport Node')], 
                            help_text="Type of facility")
    subtype = models.CharField(max_length=100, null=True, blank=True, help_text="Finer source category within the type, e.g. OSM amenity 'kindergarten' or 'clinic'")
    sourceID = models.CharField(max_length=100, unique=True, null=True, blank=True, help_text="Identifier in the source dataset, e.g. 'osm:node/123' for OpenStreetMap")
    neighborhood = models.ForeignKey(Neighborhood, on_delete=models.DO_NOTHING, null=True, blank=True, help_text="City code from administrative.City")
    geom = models.PointField(srid=CoordinateSystem)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Facility"
        verbose_name_plural = "Facilities"
    
    
class Building(models.Model):
    # BAG gebruiksdoel (usage function) values, per the Dutch Basisregistratie Adressen en Gebouwen.
    # "verblijfsobject" is deliberately excluded: it is the BAG object type these functions
    # attach to (the addressable unit), not itself a usage function.
    BAG_USAGE_FUNCTIONS = [
        ('woonfunctie', 'Residential function'),
        ('bijeenkomstfunctie', 'Meeting function'),
        ('celfunctie', 'Cell function'),
        ('gezondheidszorgfunctie', 'Healthcare function'),
        ('industriefunctie', 'Industrial function'),
        ('kantoorfunctie', 'Office function'),
        ('logiesfunctie', 'Lodging function'),
        ('onderwijsfunctie', 'Education function'),
        ('sportfunctie', 'Sport function'),
        ('winkelfunctie', 'Shop function'),
        ('overige gebruiksfunctie', 'Other usage function'),
    ]

    # Coarse bucket each BAG usage function rolls up into, for zoning/indicator aggregation.
    BAG_TO_BUILDING_TYPE = {
        'woonfunctie': 'residential',
        'winkelfunctie': 'commercial',
        'kantoorfunctie': 'commercial',
        'logiesfunctie': 'commercial',
        'overige gebruiksfunctie': 'commercial',
        'industriefunctie': 'industrial',
        'bijeenkomstfunctie': 'institutional',
        'gezondheidszorgfunctie': 'institutional',
        'onderwijsfunctie': 'institutional',
        'sportfunctie': 'institutional',
        'celfunctie': 'institutional',
    }

    id = models.BigIntegerField(primary_key=True, help_text="Unique identifier for the building (e.g., BAG ID)")
    name = models.CharField(max_length=100, help_text="Name or identifier of the building", null=True, blank=True)
    address = models.CharField(max_length=200, help_text="Address of the building", blank=True, null=True)
    neighborhood = models.ForeignKey(Neighborhood, verbose_name="Neighborhood", on_delete=models.DO_NOTHING, null=True, blank=True)
    ZoningArea = models.ForeignKey(ZoningArea, verbose_name="Zoning Area", on_delete=models.DO_NOTHING, null=True, blank=True)
    numberUnits = models.IntegerField(null=True, blank=True, help_text="Number of housing or commercial units in the building")
    usageFunction = ArrayField(
        models.CharField(max_length=100, choices=[(label, label) for _, label in BAG_USAGE_FUNCTIONS] + [("Undefined", "Undefined")]),
        null=True, blank=True, default=list,
        help_text="BAG gebruiksdoel (usage function(s)) of the building, where known, stored as human-readable labels; a Pand can have more than one, or 'Undefined' when BAG reports no usage function",
    )
    buildingType = models.CharField(max_length=100, choices=[('residential', 'Residential'), ('commercial', 'Commercial'), ('industrial', 'Industrial'), ('institutional', 'Institutional'), ('mixed', 'Mixed Use')], help_text="Coarse building category, derived from usageFunction when set; use 'mixed' for buildings combining multiple usage functions (e.g. a Pand with several Verblijfsobjecten)")
    roofMaterial = models.ForeignKey(SurfaceMaterialProperties, verbose_name="Roof Material", on_delete=models.DO_NOTHING, null=True, blank=True)
    wallMaterial = models.ForeignKey(WallMaterialProperties, verbose_name="Wall Material", on_delete=models.DO_NOTHING, null=True, blank=True)
    # Matches EnergyEfficiencyLabels.label's own choices so the two stay in sync;
    # plain CharFields (not FKs) because these are populated straight from WFS
    # property values by the generic importer (importer/external_data.py),
    # which assigns feature properties to model fields directly and has no
    # natural-key FK resolution.
    _ENERGY_LABEL_CHOICES = EnergyEfficiencyLabels._meta.get_field('label').choices
    energyLabel = models.CharField(max_length=10, choices=_ENERGY_LABEL_CHOICES, null=True, blank=True, help_text="Dominant registered energy label for this building (RVO EP-Online register, via RIVM's rvo_energielabels WFS)")
    energyLabelHighest = models.CharField(max_length=10, choices=_ENERGY_LABEL_CHOICES, null=True, blank=True, help_text="Best registered label among this building's units (RVO EP-Online register, via RIVM's rvo_energielabels WFS)")
    energyLabelLowest = models.CharField(max_length=10, choices=_ENERGY_LABEL_CHOICES, null=True, blank=True, help_text="Worst registered label among this building's units (RVO EP-Online register, via RIVM's rvo_energielabels WFS)")
    energyLabelCount = models.IntegerField(null=True, blank=True, help_text="Number of registered energy labels found for this building (RVO EP-Online register, via RIVM's rvo_energielabels WFS)")
    height_m = models.FloatField(help_text="Height of the building in meters", null=True, blank=True)
    area_sqm = models.FloatField(help_text="Footprint area of the building in square meters", null=True, blank=True)
    constructionYear = models.IntegerField(null=True, blank=True, help_text="Year the building was constructed")
    numberFloors = models.IntegerField(null=True, blank=True, help_text="Number of floors in the building")
    vacant= models.BooleanField(default=False, help_text="Is the building vacant?")
    vacancyRate = models.FloatField(null=True, blank=True, help_text="Vacancy rate in percentage (%)")
    # Climate-effect attributes from the Klimaateffectatlas WFS (importer
    # catalog kea_*, docs/KEA_WFS_MAPPING.md). Written by enrichment imports
    # onto existing BAG buildings; no save() derivation reads them.
    canopyCover_pct = models.FloatField(null=True, blank=True, help_text="Tree canopy cover around the building, % (KEA RMK_30percBKB_AHN4.perc_bkb); informs the Vegetation_Coverage DAG node")
    meetsCanopy30Rule = models.BooleanField(null=True, blank=True, help_text="Whether the 3-30-300 rule's 30% canopy cover is met around the building (KEA RMK_30percBKB_AHN4.bkb_30perc_gehaald)")
    facadeShadeScore = models.FloatField(null=True, blank=True, help_text="Shade on the facades of the building's block, 0-1 (KEA 'Schaduw op gebouwen'.SOG.Score)")
    floodDepth_p99_m = models.FloatField(null=True, blank=True, help_text="99th percentile water depth around the building in a 70 mm/h cloudburst, m (KEA nl_fcab_omgevingsscore_wateroverlast.waterdiepte_p99)")
    floodDepthClass = models.CharField(max_length=50, null=True, blank=True, help_text="Water depth class around the building, e.g. '10 tot 15 cm' (KEA nl_fcab_omgevingsscore_wateroverlast.waterdiepte_klasse)")
    connectivity = models.ManyToManyField(Facility, verbose_name="Connections to Facilities", blank=True, help_text="Facilities the property is connected to")  #TODO: Define connectivity index and calculation method
    last_updated = models.DateTimeField(default=timezone.now)
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    
    def save(self, *args, **kwargs):
        if self.usageFunction or self.usageFunction == "":
            self.usageFunction = bag_usage_labels(self.usageFunction)
            label_to_code = {label: code for code, label in self.BAG_USAGE_FUNCTIONS}
            building_types = {
                self.BAG_TO_BUILDING_TYPE[label_to_code[label]]
                for label in self.usageFunction if label in label_to_code
            }
            if len(building_types) > 1:
                self.buildingType = "mixed"
            elif building_types:
                self.buildingType = building_types.pop()
        if self.geom:
            self.area_sqm = self.geom.area
            self.neighborhood = Neighborhood.objects.filter(geom__contains=self.geom.centroid).first()

        # update_or_create() -- the importer's path for a building that already
        # exists -- saves with update_fields = the fields it was handed. Without
        # this, the fields derived above are computed and then never written.
        if kwargs.get("update_fields"):
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"buildingType", "area_sqm", "neighborhood"}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Building {self.id} ({self.buildingType})"

    class Meta:
        verbose_name = "Building"
        verbose_name_plural = "Buildings"


def bag_usage_labels(value):
    """
    BAG gebruiksdoel as a list of labels (Building.BAG_USAGE_FUNCTIONS).

    WFS delivers raw codes as one comma-separated string for multi-function
    objects (e.g. "winkelfunctie,woonfunctie"); a re-save hands back the stored
    list of labels. BAG reports some objects with an empty gebruiksdoel (empty
    string, not missing); it is kept visible as 'Undefined'.
    """
    if value == "":
        return ["Undefined"]
    if isinstance(value, str):
        value = [f.strip() for f in value.split(",") if f.strip()]
    code_to_label = dict(Building.BAG_USAGE_FUNCTIONS)
    return [code_to_label.get(f, f) for f in value]


class BuildingEnergyLabel(Building):
    """
    Proxy onto Building, filed under the Energy app so the energy-label
    fields (populated from RIVM's rvo_energielabels WFS, see
    importer/external_catalog.py's "rivm_energy_labels" entry) get their own
    entry in the Energy map/layer catalog without a second table or an
    import-time write to two places. Same rows, same columns, same save()
    logic as builtup.Building — this only changes which app_label/registry
    key the model is organized under (core/utils.py's build_model_registry
    keys models by app_label, not by the module they're defined in, so a
    proxy can live in builtup/models.py and still register as "Energy.*").
    """

    class Meta:
        proxy = True
        app_label = "Energy"
        verbose_name = "Building Energy Label"
        verbose_name_plural = "Building Energy Labels"


class Property(models.Model):
    # 64-bit: the PDOK import (pdok_properties) stores the BAG verblijfsobject
    # identificatie here, a 16-digit number beyond a 32-bit integer. Still
    # auto-numbered for properties created in the editor or admin.
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100, help_text="Name of the property")
    houseNumber = models.CharField(max_length=5, null=True, blank=True, help_text="House number of the property")
    building = models.ForeignKey(Building, verbose_name="Building", on_delete=models.DO_NOTHING)
    usageFunction = ArrayField(
        models.CharField(max_length=100, choices=[(label, label) for _, label in Building.BAG_USAGE_FUNCTIONS] + [("Undefined", "Undefined")]),
        null=True, blank=True, default=list,
        help_text="BAG gebruiksdoel (usage function(s)) of the property, where known, stored as human-readable labels",
    )
    grossArea = models.FloatField(help_text="Area of the property in square meters")
    livingArea = models.FloatField(help_text="Living area of the property in square meters", null=True, blank=True)
    greenVisibility = models.FloatField(help_text="Green visibility index of the property", null=True, blank=True)  #TODO: Define green visibility index and calculation method
    bedrooms = models.IntegerField(help_text="Number of bedrooms in the property", null=True, blank=True)
    bathrooms = models.IntegerField(help_text="Number of bathrooms in the property", null=True, blank=True)
    postalCode = models.CharField(max_length=10, help_text="Postal code of the property", null=True, blank=True) # TODO: This can be a ForeignKey to a PostalCode model of national postal codes, if such a model is created in the future.
    listingPrice_EUR = models.FloatField(help_text="Listing price of the property in EUR", null=True, blank=True)
    salePrice_EUR = models.FloatField(help_text="Sale price of the property in EUR", null=True, blank=True)
    unitaryPrice_EUR_per_sqm = models.FloatField(help_text="Unitary price in EUR per square meter", null=True, blank=True)
    last_updated = models.DateTimeField(default=timezone.now)
    geom = models.PointField(srid=CoordinateSystem)
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        self.last_updated = timezone.now()
        self.building = Building.objects.filter(geom__contains=self.geom).first()
        if self.usageFunction or self.usageFunction == "":
            self.usageFunction = bag_usage_labels(self.usageFunction)
        # Calculate unitary price
        if self.grossArea and self.listingPrice_EUR:
            self.unitaryPrice_EUR_per_sqm = self.listingPrice_EUR / self.grossArea
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Property"
        verbose_name_plural = "Properties"




class NeighborhoodClimateRisk(models.Model):
    """
    Climate risks to the building stock of a neighborhood, from the
    Klimaateffectatlas WFS (importer catalog kea_*, docs/KEA_WFS_MAPPING.md).
    One row per neighborhood; each KEA layer fills its own columns. Stored
    inputs only (no save() derivation, no DAG edge implemented).
    """
    id = models.AutoField(primary_key=True)
    neighborhood = models.OneToOneField(Neighborhood, verbose_name="Neighborhood", on_delete=models.DO_NOTHING, related_name="climate_risk")
    pileRotRisk_current_pct = models.FloatField(null=True, blank=True, help_text="Buildings at risk of wooden pile rot, current climate, % (KEA risicopaalrot_huidig)")
    pileRotRisk_2050low_pct = models.FloatField(null=True, blank=True, help_text="Buildings at risk of wooden pile rot, 2050 low scenario, % (KEA risicopaalrot_2050laag)")
    pileRotRisk_2050high_pct = models.FloatField(null=True, blank=True, help_text="Buildings at risk of wooden pile rot, 2050 high scenario, % (KEA risicopaalrot_2050hoog)")
    settlementRisk_2050low_pct = models.FloatField(null=True, blank=True, help_text="Buildings at risk of differential settlement, 2050 low scenario, % (KEA risicoverschilzetting_2050laag)")
    settlementRisk_2050high_pct = models.FloatField(null=True, blank=True, help_text="Buildings at risk of differential settlement, 2050 high scenario, % (KEA risicoverschilzetting_2050hoog)")
    dryFloors_pct = models.FloatField(null=True, blank=True, help_text="Share of floors that stay dry in an extremely unlikely flood, % (KEA droge_verdiepingen_extreem_kleine_kans)")
    source = models.CharField(max_length=100, default="Klimaateffectatlas", help_text="Data provider")
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Climate risk {self.neighborhood_id}"

    class Meta:
        verbose_name = "Neighborhood Climate Risk"
        verbose_name_plural = "Neighborhood Climate Risks"
