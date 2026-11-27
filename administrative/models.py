from django.utils import timezone
from django.contrib.gis.db import models
from django.db.models import Sum

from django.conf import settings

CoordinateSystem = settings.COORDINATE_SYSTEM

# Create your models here.
class Province(models.Model):
    id = models.AutoField(primary_key=True)
    ProvinceName = models.CharField(max_length=100)
    currentPopulation = models.IntegerField(null=True, help_text="Total current population in the Province", verbose_name="Current Population")
    populationDensity = models.FloatField(null=True, help_text="Population density in people per square kilometer", verbose_name="Population Density") # people/km2
    populationDate = models.DateField(null=True, help_text="Date of the population data", verbose_name="Population Date")
    area_km2 = models.FloatField(null=True, help_text="Area in square kilometers")
    urban_area = models.FloatField(null=True, help_text="Urban area in square kilometers")
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    last_updated = models.DateTimeField(default=timezone.now)



    def save(self, *args, **kwargs):
        if self.currentPopulation is None:
            # Sum of its cities; a brand-new Province (no pk yet) has none.
            total = None
            if self.pk:
                total = City.objects.filter(province=self.pk).aggregate(
                    total=Sum('currentPopulation')
                )['total']
            self.currentPopulation = total or 0


        self.area_km2 = self.geom.area / 1e6  # Convert m2 to km2

        if self.area_km2 and self.area_km2 > 0:
            self.populationDensity = self.currentPopulation / float(self.area_km2)
        else:
            self.populationDensity = None
        self.last_updated = timezone.now()
        super().save(*args, **kwargs)


    def __str__(self):
        return self.ProvinceName

    class Meta:
        verbose_name = "Province"
        verbose_name_plural = "Provinces"

class City(models.Model):
    id = models.AutoField(primary_key=True)
    province = models.ForeignKey(Province, on_delete=models.CASCADE, help_text="Province code from administrative.Province")
    cityName = models.CharField(max_length=100, verbose_name="City Name", help_text="Name of the city")
    currentPopulation = models.IntegerField(help_text="Total current population in the city", verbose_name="Current Population", null=True)
    area_km2 = models.FloatField(null=True, help_text="Area in square kilometers")
    populationDensity = models.FloatField(null=True, help_text="Population density in people per square kilometer", verbose_name="Population Density") # people/km2
    populationDate = models.DateField(null=True)
    popGrowthRate = models.FloatField(null=True , help_text="Growth rate in % per year") # %
    urbanizationRate = models.FloatField(null=True, help_text="Growth of the urban area (Degree of Urbanisation classes 21-30, 100 m grid) in % per year, between the earliest and latest stored CrossTwin years; written by builtup/calculations/urbanisation.py::mirror_city_rates") # %
    urban_area = models.FloatField(null=True, help_text="Urban area in square kilometers")
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    last_updated = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):

        if self.pk:
            total = District.objects.filter(city=self).aggregate(
                total=Sum('currentPopulation')
            )['total']
            # The districts are the source of truth *when they report a
            # population*. A city that has none (e.g. one only imported from CBS)
            # keeps its own value instead of being reset to 0 on every save.
            if total:
                self.currentPopulation = total

        self.area_km2 = self.geom.area / 1e6  # Convert m2 to km2

        if self.area_km2 and self.area_km2 > 0 and self.currentPopulation is not None:
            self.populationDensity = float (self.currentPopulation / self.area_km2)
        else:
            self.populationDensity = None

        if self.pk:
            # Local import: population.py imports City from this module.
            from .calculations.population import annual_growth_rate
            rate = annual_growth_rate(self)
            if rate is not None:
                self.popGrowthRate = rate

        self.last_updated = timezone.now()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cityName} - {self.currentPopulation} inhabitants"

    class Meta:
        verbose_name = "City"
        verbose_name_plural = "Cities"

class District(models.Model):
    id = models.CharField(primary_key=True)
    city = models.ForeignKey(City, on_delete=models.DO_NOTHING, help_text="City code from administrative.City")
    districtName = models.CharField(max_length=100, help_text="Name of the district", verbose_name="District Name")
    currentPopulation = models.IntegerField(null=True, blank=True, help_text="Current population in the district")
    populationDate = models.DateField(null=True)
    area_km2 = models.FloatField(null=True, blank=True, help_text="Area in square kilometers")
    populationDensity = models.FloatField(null=True, blank=True, help_text="Population density in people per square kilometer", verbose_name="Population Density")
    urban_area = models.FloatField(null=True, help_text="Urban area in square kilometers")
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    last_updated = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        self.area_km2 = self.geom.area / 1e6
        pop = self.currentPopulation or 0
        self.populationDensity = float(pop / self.area_km2) if self.area_km2 else 0.0
        self.last_updated = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.districtName

    class Meta:
        verbose_name = "District"
        verbose_name_plural = "Districts"

class Neighborhood(models.Model):
    id = models.CharField(primary_key=True)
    district = models.ForeignKey(District, on_delete=models.DO_NOTHING, help_text="City code from administrative.City", null=True, blank=True)
    neighborhoodName = models.CharField(max_length=100, help_text="Name of the neighborhood", verbose_name="Neighborhood Name")
    currentPopulation = models.IntegerField(null=True, blank=True, help_text="Current population in the neighborhood", verbose_name="Current Population")
    populationDate = models.DateField(null=True)
    households = models.IntegerField(null=True, blank=True, help_text="Private households (CBS Wijken en Buurten, aantalHuishoudens)")
    onePersonHouseholds_pct = models.FloatField(null=True, blank=True, help_text="One-person households, % of the households (CBS Wijken en Buurten, percentageEenpersoonshuishoudens)")
    area_km2 = models.FloatField(null=True, blank=True, help_text="Area in square kilometers")
    populationDensity = models.FloatField(null=True, blank=True, help_text="Population density in people per square kilometer", verbose_name="Population Density")
    urban_area = models.FloatField(null=True, help_text="Urban area in square kilometers")
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    last_updated = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        self.area_km2 = self.geom.area / 1e6
        pop = self.currentPopulation or 0
        self.populationDensity = float(pop / self.area_km2) if self.area_km2 else 0.0
        self.last_updated = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.neighborhoodName

    class Meta:
        verbose_name = "Neighborhood"
        verbose_name_plural = "Neighborhoods"


class _PostcodeArea(models.Model):
    """
    Common fields of a CBS postcode area (the PDOK "CBS Postcode statistieken" layers): the number and
    the figures CBS publishes per area. Postcode areas cut across municipalities and neighborhoods, so
    they are not part of the Province > City > District > Neighborhood chain: nothing cascades into or
    out of them, and a unit's population is the CBS figure as published (no cascade writes it).

    CBS leaves out a figure it cannot publish without identifying people (-99997 and kin): that is
    stored as null, never as 0. meanWOZ_EUR is CBS's "gemiddelde WOZ-waarde" (published in 1 000 EUR).
    """
    code = models.CharField(primary_key=True, max_length=6, help_text="Postcode number (PC4) or postcode (PC6, e.g. 2611AG)")
    currentPopulation = models.IntegerField(null=True, blank=True, help_text="Inhabitants (CBS aantalInwoners)")
    households = models.IntegerField(null=True, blank=True, help_text="Private households (CBS aantalPartHuishoudens)")
    avgHouseholdSize = models.FloatField(null=True, blank=True, help_text="Persons per household (CBS gemiddeldeHuishoudensgrootte)")
    dwellings = models.IntegerField(null=True, blank=True, help_text="Dwellings (CBS aantalWoningen)")
    multiFamilyDwellings = models.IntegerField(null=True, blank=True, help_text="Multi-family dwellings (CBS aantalMeergezinsWoningen)")
    vacantDwellings = models.IntegerField(null=True, blank=True, help_text="Dwellings not occupied (CBS aantalNietBewoondeWoningen)")
    ownerOccupied_pct = models.FloatField(null=True, blank=True, help_text="Owner-occupied dwellings, % (CBS percentageKoopwoningen)")
    rental_pct = models.FloatField(null=True, blank=True, help_text="Rental dwellings, % (CBS percentageHuurwoningen)")
    meanWOZ_EUR = models.FloatField(null=True, blank=True, help_text="Mean WOZ value of the dwellings, EUR (CBS gemiddeldeWozWaardeWoning, published x 1 000 EUR)")
    dataYear = models.IntegerField(null=True, blank=True, help_text="Year of the CBS postcode statistics the figures come from")
    source = models.CharField(max_length=100, default="CBS Postcode statistieken (PDOK)", help_text="Data provider")
    area_km2 = models.FloatField(null=True, blank=True, help_text="Area in square kilometers")
    populationDensity = models.FloatField(null=True, blank=True, help_text="Inhabitants per square kilometer")
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    last_updated = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        self.code = str(self.code).strip().upper()
        self.area_km2 = self.geom.area / 1e6
        self.populationDensity = (self.currentPopulation or 0) / self.area_km2 if self.area_km2 else 0.0
        self.last_updated = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.code

    class Meta:
        abstract = True


class Postcode4(_PostcodeArea):
    """A four-digit postcode area (PC4, e.g. 2611): about 4 000 in the Netherlands, 1-10 km2 in a city."""

    class Meta:
        verbose_name = "Postcode area (PC4)"
        verbose_name_plural = "Postcode areas (PC4)"


class Postcode6(_PostcodeArea):
    """
    A six-character postcode area (PC6, e.g. 2611AG): a street section, about 460 000 in the Netherlands.
    `postcode4` is the first four characters, written by save(), so the two levels join without a
    foreign key (a PC6 can be imported before its PC4).
    """
    postcode4 = models.CharField(max_length=4, db_index=True, editable=False, help_text="PC4 the postcode belongs to; derived from the code")

    def save(self, *args, **kwargs):
        self.code = str(self.code).strip().upper()
        self.postcode4 = self.code[:4]
        if kwargs.get("update_fields"):
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"postcode4"}
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Postcode area (PC6)"
        verbose_name_plural = "Postcode areas (PC6)"


class PopulationProjection(models.Model):
    """
    Projected total population of a City for one year and forecast variant.

    Loaded from CBS table 85173NED ("Regionale prognose 2023-2050"), which is
    published per gemeente; City.pk is the gemeente number. Districts,
    Neighborhoods and the Province are derived from these city values (see
    administrative/calculations/population.py), so nothing is stored below or above the city.

    DAG edge: Population_Growth -> Total_Population
    """

    class Scenario(models.TextChoices):
        PROGNOSE = 'prognose', 'CBS forecast (median)'
        LOW = 'low', 'Lower bound of the 67% interval'
        HIGH = 'high', 'Upper bound of the 67% interval'

    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='population_projections', help_text="City code from administrative.City")
    year = models.IntegerField()
    scenario = models.CharField(max_length=10, choices=Scenario.choices, default=Scenario.PROGNOSE)
    population = models.IntegerField(help_text="Projected population on 1 January of the year")
    source = models.CharField(max_length=100, blank=True, default="CBS 85173NED")
    last_updated = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        self.last_updated = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.city} {self.year} ({self.scenario}): {self.population}"

    class Meta:
        verbose_name = "Population Projection"
        verbose_name_plural = "Population Projections"
        ordering = ['city', 'scenario', 'year']
        constraints = [
            models.UniqueConstraint(fields=['city', 'year', 'scenario'], name='unique_population_projection'),
        ]
