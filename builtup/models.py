from django.utils import timezone
from django.contrib.gis.db import models
from django.contrib.postgres.fields import ArrayField
from django.db.models import Sum
from common.models import City, Neighborhood, SurfaceMaterialProperties, WallMaterialProperties
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
    name = models.CharField(max_length=100, help_text="Name of the park")
    area = models.FloatField(help_text="Area of the park in square meters")
    vegetationType = models.CharField(max_length=100, help_text="Type of vegetation in the park (e.g., grass, trees, shrubs)")
    neighborhood = models.ForeignKey(Neighborhood, on_delete=models.DO_NOTHING, null=True, blank=True, help_text="City code from common.City")
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
    neighborhood = models.ForeignKey(Neighborhood, on_delete=models.DO_NOTHING, null=True, blank=True, help_text="City code from common.City")
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
    connectivity = models.ManyToManyField(Facility, verbose_name="Connections to Facilities", blank=True, help_text="Facilities the property is connected to")  #TODO: Define connectivity index and calculation method
    last_updated = models.DateTimeField(default=timezone.now)
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    
    def save(self, *args, **kwargs):
        if self.usageFunction == "":
            # BAG reports some Pand records with no gebruiksdoel at all (empty
            # string, not missing). An empty string can't be stored in the
            # ArrayField as-is, so treat it the same as "no data" but keep it
            # visible rather than silently dropping the building's function.
            self.usageFunction = "Undefined"
        if self.usageFunction:
            # WFS delivers a comma-separated string for multi-function buildings
            # (e.g. "winkelfunctie,woonfunctie"); a re-save of an already-converted
            # instance instead hands back a list of labels. Normalize both to a
            # list of raw BAG codes before deriving buildingType / labels from them.
            
            if isinstance(self.usageFunction, str):
                raw_functions = [f.strip() for f in self.usageFunction.split(",") if f.strip()]
            else:
                raw_functions = list(self.usageFunction)

            code_to_label = dict(self.BAG_USAGE_FUNCTIONS)
            label_to_code = {label: code for code, label in self.BAG_USAGE_FUNCTIONS}
            codes = [label_to_code.get(f, f) for f in raw_functions]

            building_types = {self.BAG_TO_BUILDING_TYPE[c] for c in codes if c in self.BAG_TO_BUILDING_TYPE}
            if len(building_types) > 1:
                self.buildingType = "mixed"
            elif building_types:
                self.buildingType = building_types.pop()

            self.usageFunction = [code_to_label.get(c, c) for c in codes]
        if self.geom:
            self.area_sqm = self.geom.area
            self.neighborhood = Neighborhood.objects.filter(geom__contains=self.geom.centroid).first()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Building {self.id} ({self.buildingType})"

    class Meta:
        verbose_name = "Building"
        verbose_name_plural = "Buildings"


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
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, help_text="Name of the property")
    building = models.ForeignKey(Building, verbose_name="Building", on_delete=models.DO_NOTHING)
    grossArea = models.FloatField(help_text="Area of the property in square meters")
    livingArea = models.FloatField(help_text="Living area of the property in square meters")
    greenVisibility = models.FloatField(help_text="Green visibility index of the property")  #TODO: Define green visibility index and calculation method
    bedrooms = models.IntegerField(help_text="Number of bedrooms in the property")
    bathrooms = models.IntegerField(help_text="Number of bathrooms in the property")
    
    listingPrice_EUR = models.FloatField(help_text="Listing price of the property in EUR")
    salePrice_EUR = models.FloatField(help_text="Sale price of the property in EUR")
    unitaryPrice_EUR_per_sqm = models.FloatField(help_text="Unitary price in EUR per square meter")
    last_updated = models.DateTimeField(default=timezone.now)
    geom = models.PointField(srid=CoordinateSystem)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Property"
        verbose_name_plural = "Properties"
    
