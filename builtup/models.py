from django.utils import timezone
from django.contrib.gis.db import models
from django.contrib.postgres.fields import ArrayField
from django.db.models import Sum
from administrative.models import City, Neighborhood
from physicalEnv.models import HILUCSLandUse, SurfaceMaterialProperties, WallMaterialProperties, roof_materials, street_materials
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
    surfaceMaterial = models.ForeignKey(SurfaceMaterialProperties, verbose_name="Surface Material", on_delete=models.DO_NOTHING, null=True, blank=True,
                                        limit_choices_to=street_materials,
                                        help_text="Road surface (Oke et al. 2017 Table 5.1)")
    classification = models.CharField(max_length=50, choices=[('primary', 'Primary'), ('secondary', 'Secondary'), ('residential', 'Residential')], help_text="Street classification (e.g., primary, secondary, residential)")
    width = models.FloatField(null=True, blank=True, help_text="Width of the street in meters. Leave empty to let the canyon aspect ratio use the measured facade-to-facade distance (builtup.StreetCanyon); a value typed here overrides it")
    geom = models.MultiLineStringField(srid=CoordinateSystem)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Street"
        verbose_name_plural = "Streets"


class StreetCanyon(models.Model):
    """
    The urban canyon of one street: height-to-width ratio H/W.

        H = mean of the building heights on the left and right of the street
            (area-weighted within builtup/canyon.py::SEARCH_M; open side = 0)
        W = Street.width when set, else the facade-to-facade distance,
            else a default per street classification

    Inputs from builtup/canyon.py::street_inputs, equations in builtup/chain.py.
    Refreshed by builtup/signals.py when the street or a building near it
    changes. Shown on the map along the street line.

    DAG edges: Buildings -> Canyon_Aspect, Streets -> Canyon_Aspect.
    """
    WIDTH_SOURCES = [("street", "Street width"), ("facade", "Facade-to-facade distance"), ("default", "Default for the street class")]

    street = models.OneToOneField(Street, on_delete=models.DO_NOTHING, related_name="canyon", help_text="The street this canyon belongs to")
    h_left_m = models.FloatField(default=0, help_text="Mean building height on the left of the street, m (0: no buildings)")
    h_right_m = models.FloatField(default=0, help_text="Mean building height on the right of the street, m (0: no buildings)")
    w_facade_m = models.FloatField(null=True, blank=True, help_text="Distance between the nearest facades on both sides, m (None: buildings on one side or none)")
    n_left = models.IntegerField(default=0, help_text="Buildings found on the left")
    n_right = models.IntegerField(default=0, help_text="Buildings found on the right")
    height_m = models.FloatField(default=0, help_text="Canyon height H, m")
    width_m = models.FloatField(null=True, blank=True, help_text="Canyon width W, m")
    width_source = models.CharField(max_length=10, choices=WIDTH_SOURCES, default="default", help_text="Where W comes from")
    aspect_ratio = models.FloatField(null=True, blank=True, help_text="H/W")
    updated = models.DateTimeField(auto_now=True)
    geom = models.MultiLineStringField(srid=CoordinateSystem, help_text="Copy of the street line")

    def __str__(self):
        ratio = f"{self.aspect_ratio:.2f}" if self.aspect_ratio is not None else "-"
        return f"Canyon of street {self.street_id} (H/W {ratio})"

    def apply(self, street, inputs):
        """Set every field from the street and its street_inputs() row (builtup/chain.py::canyon)."""
        from . import chain

        for name in ("h_left_m", "h_right_m", "w_facade_m", "n_left", "n_right"):
            setattr(self, name, inputs[name])
        for name, value in chain.canyon(inputs, street.width, street.classification).items():
            setattr(self, name, value)
        self.geom = street.geom

    def save(self, *args, **kwargs):
        """
        DAG edges: Buildings -> Canyon_Aspect, Streets -> Canyon_Aspect.
        Re-reads the street and the buildings around it every save.
        """
        from .canyon import street_inputs

        street = Street.objects.only("width", "classification", "geom").get(pk=self.street_id)
        self.apply(street, street_inputs([self.street_id])[self.street_id])
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Street Canyon"
        verbose_name_plural = "Street Canyons"

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
    roofMaterial = models.ForeignKey(SurfaceMaterialProperties, verbose_name="Roof Material", on_delete=models.DO_NOTHING, null=True, blank=True,
                                     limit_choices_to=roof_materials,
                                     help_text="Roof covering (Oke et al. 2017 Table 5.1); its albedo sets the roof share of the urban-fabric ring of a drawn building")
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
        # WFS delivers the BAG identificatie as a string ("0153100000212134");
        # receivers compare the pk as a number (physicalEnv.signals._is_editor_building).
        self.id = self._meta.pk.to_python(self.id)
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
    # Not derived in save(): builtup must not import housing. housing/signals.py
    # writes it (DAG edge Household_Size -> Property) for dwellings only.
    residents = models.FloatField(null=True, blank=True, help_text="Estimated residents: the city's average persons per home (CBS household size), for dwellings; set by housing/signals.py")
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


# ── Degree of Urbanisation (DAG node Degree_Urbanisation) ──────────────
# Method: docs/DEGREE_OF_URBANISATION.md. Grid classification: builtup/degurba.py;
# allocation and refresh: builtup/urbanisation.py; unit equations: builtup/chain.py.

RESOLUTION_CHOICES = [(100, "100 m (CrossTwin, local)"), (1000, "1 km (original DEGURBA)")]
L2_CHOICES = [(30, "Urban centre"), (23, "Dense urban cluster"), (22, "Semi-dense urban cluster"),
              (21, "Suburban or peri-urban"), (13, "Rural cluster"), (12, "Low density rural"),
              (11, "Very low density rural"), (10, "Water"), (0, "Outside the grid")]
L1_CHOICES = [(3, "Urban centre"), (2, "Urban cluster"), (1, "Rural"), (0, "Outside the grid")]


class PopulationAllocation(models.Model):
    """
    One neighborhood's share of one grid cell: the bookkeeping of the
    dasymetric allocation (people -> residential properties -> cells).

        p_d = P_n / N_n          every dwelling d of neighborhood n
                                 (P_n = currentPopulation, N_n = dwellings:
                                 builtup.Property with 'Residential function')
        P_cell = sum of p_d      dwellings whose point lies in the cell
        no dwellings, P_n > 0:   P_n x (area of n in the cell / area of n)

    Rows are replaced per neighborhood, so a change re-allocates only the
    neighborhoods it touches. Not a map layer (registry_hidden).
    """
    registry_hidden = True

    neighborhood = models.ForeignKey(Neighborhood, on_delete=models.CASCADE, related_name="population_allocation")
    resolution_m = models.IntegerField(choices=RESOLUTION_CHOICES)
    year = models.IntegerField()
    ix = models.IntegerField(help_text="Cell column: floor(x / resolution) in the grid CRS")
    iy = models.IntegerField(help_text="Cell row: floor(y / resolution) in the grid CRS")
    population = models.FloatField(default=0)
    dwellings = models.IntegerField(default=0)
    built_up_m2 = models.FloatField(default=0, help_text="Footprint area of the neighborhood's buildings inside the cell, m²")
    area_m2 = models.FloatField(default=0, help_text="Area of the neighborhood inside the cell, m²")
    by_area = models.BooleanField(default=False, help_text="Population spread by area (the neighborhood has no dwellings)")

    def __str__(self):
        return f"{self.neighborhood_id} {self.year} {self.resolution_m} m ({self.ix}, {self.iy}): {self.population:.1f}"

    class Meta:
        verbose_name = "Population Allocation"
        verbose_name_plural = "Population Allocations"
        constraints = [models.UniqueConstraint(fields=["neighborhood", "resolution_m", "year", "ix", "iy"],
                                               name="unique_population_allocation")]
        indexes = [models.Index(fields=["resolution_m", "year", "ix", "iy"])]


class UrbanisationCell(models.Model):
    """
    One grid cell of the Degree of Urbanisation, at 100 m (CrossTwin's local
    variant) or 1 km (the original method), for one population year.

    The map shows the current year through the proxies UrbanisationCellLocal
    (100 m) and UrbanisationCellOriginal (1 km); this concrete table is hidden.

    DAG edges: Total_Population -> Degree_Urbanisation,
               Buildings -> Degree_Urbanisation,
               LandCover -> Degree_Urbanisation.
    """
    registry_hidden = True

    resolution_m = models.IntegerField(choices=RESOLUTION_CHOICES)
    year = models.IntegerField()
    current = models.BooleanField(default=True, help_text="Cell of the latest classified year (the map layer)")
    ix = models.IntegerField()
    iy = models.IntegerField()
    cell_code = models.CharField(max_length=40, help_text="E<x>N<y> of the lower-left corner, in hm (100 m) or km (1 km), as the CBS square statistics")
    population = models.FloatField(default=0, help_text="People allocated to the cell")
    dwellings = models.IntegerField(default=0, help_text="Residential properties in the cell")
    density = models.FloatField(default=0, help_text="Density used by the classification, inh./km² (100 m: 3 x 3 window over settlement land; 1 km: cell land)")
    built_up_m2 = models.FloatField(default=0, help_text="Building footprint area inside the cell, m²")
    built_up_share = models.FloatField(default=0, help_text="Building footprint share of the density window")
    water_share = models.FloatField(default=0, help_text="Permanent water share of the cell (latest land cover)")
    settlement_share = models.FloatField(default=0, help_text="Settlement land-cover share of the cell (urban fabric, industry, roads, construction, urban green)")
    coverage = models.FloatField(default=1, help_text="Share of the cell inside imported neighborhoods")
    by_area = models.BooleanField(default=False, help_text="Part of the population was spread by area (a neighborhood without dwellings)")
    l2 = models.IntegerField(choices=L2_CHOICES, default=0, verbose_name="Class (level 2)")
    l1 = models.IntegerField(choices=L1_CHOICES, default=0, verbose_name="Class (level 1)")
    cluster_id = models.IntegerField(default=0, help_text="Centre / cluster this cell belongs to (0: none)")
    cluster_population = models.FloatField(default=0, help_text="Population of that centre / cluster")
    edge_effect = models.BooleanField(default=False, help_text="The cluster touches the edge of the imported area: its population may be understated")
    updated = models.DateTimeField(auto_now=True)
    geom = models.PolygonField(srid=CoordinateSystem)

    def __str__(self):
        return f"{self.cell_code} {self.year} ({self.resolution_m} m): {self.get_l2_display()}"

    class Meta:
        verbose_name = "Degree of Urbanisation Cell"
        verbose_name_plural = "Degree of Urbanisation Cells"
        constraints = [models.UniqueConstraint(fields=["resolution_m", "year", "ix", "iy"],
                                               name="unique_urbanisation_cell")]
        indexes = [models.Index(fields=["resolution_m", "current"])]


class _CurrentCells(models.Manager):
    resolution_m = None

    def get_queryset(self):
        return super().get_queryset().filter(current=True, resolution_m=self.resolution_m)


class _LocalCells(_CurrentCells):
    resolution_m = 100


class _OriginalCells(_CurrentCells):
    resolution_m = 1000


class UrbanisationCellLocal(UrbanisationCell):
    """Map layer: Degree of Urbanisation on 100 m cells (CrossTwin's local variant), latest year."""
    registry_hidden = False
    objects = _LocalCells()

    class Meta:
        proxy = True
        verbose_name = "Degree of Urbanisation (100 m)"
        verbose_name_plural = "Degree of Urbanisation (100 m)"


class UrbanisationCellOriginal(UrbanisationCell):
    """Map layer: Degree of Urbanisation on 1 km cells (original method, same data), latest year."""
    registry_hidden = False
    objects = _OriginalCells()

    class Meta:
        proxy = True
        verbose_name = "Degree of Urbanisation (1 km, original)"
        verbose_name_plural = "Degree of Urbanisation (1 km, original)"


class Urbanisation(models.Model):
    """
    Degree of Urbanisation of an admin unit (DAG node Degree_Urbanisation):
    its population per grid class, the share in urban centres / clusters, its
    level 1 / level 2 class and, for cities, the urbanisation rate.

    `unit_id` is the pk of the Neighborhood, District or City (`level`). The
    population per class comes from PopulationAllocation (exact per dwelling),
    so a District or City is the sum of its neighborhoods.
    """
    LEVELS = [("neighborhood", "Neighborhood"), ("district", "District"), ("city", "City")]
    UNIT_L1 = [(3, "City"), (2, "Town or semi-dense area"), (1, "Rural area")]
    UNIT_L2 = [(30, "City"), (23, "Dense town"), (22, "Semi-dense town"), (21, "Suburban or peri-urban area"),
               (13, "Village"), (12, "Dispersed rural area"), (11, "Mostly uninhabited area")]

    level = models.CharField(max_length=20, choices=LEVELS)
    unit_id = models.CharField(max_length=50)
    unit_name = models.CharField(max_length=100, blank=True, default="")
    resolution_m = models.IntegerField(choices=RESOLUTION_CHOICES)
    year = models.IntegerField()
    population = models.FloatField(default=0)
    pop_30 = models.FloatField(default=0, verbose_name="Population in urban centres")
    pop_23 = models.FloatField(default=0, verbose_name="Population in dense urban clusters")
    pop_22 = models.FloatField(default=0, verbose_name="Population in semi-dense urban clusters")
    pop_21 = models.FloatField(default=0, verbose_name="Population in suburban cells")
    pop_13 = models.FloatField(default=0, verbose_name="Population in rural clusters")
    pop_12 = models.FloatField(default=0, verbose_name="Population in low density rural cells")
    pop_11 = models.FloatField(default=0, verbose_name="Population in very low density rural cells")
    urban_centre_share = models.FloatField(null=True, blank=True, help_text="Share of the population in urban centres")
    urban_cluster_share = models.FloatField(null=True, blank=True, help_text="Share of the population in urban centres and clusters")
    urban_area_km2 = models.FloatField(default=0, help_text="Area of the unit in cells of class 21-30, km²")
    degurba_l1 = models.IntegerField(null=True, blank=True, choices=UNIT_L1)
    degurba_l2 = models.IntegerField(null=True, blank=True, choices=UNIT_L2)
    urbanization_rate_pct_yr = models.FloatField(null=True, blank=True, help_text="Growth of the urban area (cells 21-30) since the earliest stored year, %/yr (cities)")
    rate_base_year = models.IntegerField(null=True, blank=True)
    last_updated = models.DateTimeField(default=timezone.now)

    def save(self, *args, by_class=None, urban_area_m2=None, **kwargs):
        """
        DAG edges: Total_Population -> Degree_Urbanisation,
                   Buildings -> Degree_Urbanisation,
                   LandCover -> Degree_Urbanisation.
        Population per class from the unit's PopulationAllocation rows joined to
        the classified cells (builtup/urbanisation.py::unit_class_population);
        classes and rate from builtup/chain.py. The grid refresh passes
        `by_class` / `urban_area_m2` it already read for all units at once.
        """
        if by_class is None:
            from .urbanisation import unit_class_population

            by_class, urban_area_m2 = unit_class_population(self.level, self.unit_id, self.resolution_m, self.year)
        self.apply(by_class, urban_area_m2 or 0.0)
        super().save(*args, **kwargs)

    def apply(self, by_class, urban_area_m2):
        """Set every derived field from the population per class and the urban area (m²)."""
        from . import chain

        for code in (30, 23, 22, 21, 13, 12, 11):
            setattr(self, f"pop_{code}", by_class.get(code, 0.0))
        self.population = sum(by_class.values())
        l1, l2, shares = chain.classify_unit(by_class)
        self.degurba_l1, self.degurba_l2 = l1, l2
        self.urban_centre_share = shares.get(30, 0.0) if shares else None
        self.urban_cluster_share = sum(shares.get(k, 0.0) for k in chain.URBAN_L2) if shares else None
        self.urban_area_km2 = urban_area_m2 / 1e6
        self.urbanization_rate_pct_yr = self.rate_base_year = None
        if self.level == "city":
            base = (Urbanisation.objects.filter(level=self.level, unit_id=self.unit_id,
                                                resolution_m=self.resolution_m, year__lt=self.year)
                    .order_by("year").values("year", "urban_area_km2").first())
            if base:
                self.urbanization_rate_pct_yr = chain.urbanization_rate(
                    base["urban_area_km2"], base["year"], self.urban_area_km2, self.year)
                self.rate_base_year = base["year"]
        self.last_updated = timezone.now()

    def __str__(self):
        return f"{self.unit_name or self.unit_id} {self.year} ({self.resolution_m} m): {self.get_degurba_l2_display()}"

    class Meta:
        verbose_name = "Degree of Urbanisation"
        verbose_name_plural = "Degree of Urbanisation"
        constraints = [models.UniqueConstraint(fields=["level", "unit_id", "resolution_m", "year"],
                                               name="unique_urbanisation")]
