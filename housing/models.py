from django.contrib.gis.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings

from builtup.models import Property
from .calculations import chain

COORDINATE_SYSTEM = settings.COORDINATE_SYSTEM
AFFORDABILITY_STRESS_LEVELS = [('low', 'Low'), ('moderate', 'Moderate'), ('high', 'High')] #TODO: check if these are the right thresholds for the affordability stress levels,
                                                                            #  or if we should use different thresholds based on the literature


class HouseholdSize(models.Model):
    """
    Average number of persons per private household (= per occupied home) of a
    City and year. Only the households are imported (CBS 86291NED, catalog
    CBS_Households; City.pk is the gemeente number). The population is not a
    second import: it is the median forecast already stored in
    administrative.PopulationProjection (CBS_PopulationForecast) for that city
    and year, and `average_size` = population / households. Both are derived in
    `save()` and re-derived by housing/signals.py when a forecast arrives later,
    so the two imports can run in either order. Years without a forecast
    (before 2023) have no average; a manually entered `population` is kept
    for them.

    Feeds the dashboard's "persons per home" slider, `HousingSupplyDemand`
    (demand = population / average_size) and `builtup.Property.residents`
    (each dwelling is occupied by this average); see housing/signals.py.

    DAG edges: Total_Population -> Household_Size (ratio)
    """
    id = models.AutoField(primary_key=True)
    city = models.ForeignKey("administrative.City", verbose_name="City", on_delete=models.DO_NOTHING)
    year = models.IntegerField(help_text="Year (1 January) of the household data")
    households = models.IntegerField(null=True, blank=True, help_text="Private households (CBS 86291NED)")
    onePersonHouseholds = models.IntegerField(null=True, blank=True, help_text="One-person households (CBS 86291NED, GrootteVanHetHuishouden 1011400, catalog CBS_OnePersonHouseholds)")
    population = models.IntegerField(null=True, blank=True, help_text="Population of the year: the median forecast of PopulationProjection when there is one (derived), else as entered")
    average_size = models.FloatField(null=True, blank=True, help_text="Average persons per household = population / households (derived)")
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Household size {self.year} for {self.city_id}: {self.average_size}"

    def derive(self):
        """(population, average_size) from the stored forecast; the current values where it has none."""
        from administrative.models import PopulationProjection
        from administrative.calculations.population import DEFAULT_SCENARIO

        projected = PopulationProjection.objects.filter(
            city_id=self.city_id, year=self.year, scenario=DEFAULT_SCENARIO,
        ).values_list('population', flat=True).first()
        population = projected if projected is not None else self.population
        size = chain.average_household_size(population, self.households)
        return population, size if size is not None else self.average_size

    def save(self, *args, **kwargs):
        self.population, self.average_size = self.derive()
        # update_or_create() (the CBS importer) saves with update_fields = the
        # columns it was handed; without this the derived columns are never written.
        if kwargs.get("update_fields"):
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"population", "average_size"}
        super().save(*args, **kwargs)

    @classmethod
    def for_year(cls, city, year):
        """Record of `year`, else the closest earlier one, else the earliest later one (with an average)."""
        records = cls.objects.filter(city=city, average_size__isnull=False)
        return (records.filter(year__lte=year).order_by('-year').first()
                or records.order_by('year').first())

    @classmethod
    def latest(cls, city_id):
        return cls.objects.filter(city_id=city_id, average_size__isnull=False).order_by('-year').first()

    class Meta:
        verbose_name = "Household Size"
        verbose_name_plural = "Household Sizes"
        constraints = [models.UniqueConstraint(fields=['city', 'year'], name='unique_household_size_city_year')]


# Create your models here.
class HousingSupplyDemand(models.Model):
    id = models.AutoField(primary_key=True)
    city = models.ForeignKey("administrative.City", verbose_name="City", on_delete=models.DO_NOTHING, null=True, blank=True)
    neighborhood = models.ForeignKey("administrative.Neighborhood", verbose_name="Neighborhood", on_delete=models.DO_NOTHING, null=True, blank=True)
    year = models.IntegerField(help_text="Year of the housing supply/demand data")
    supply_units = models.IntegerField(help_text="Dwelling stock at the end of the year (CBS 86098NED EindstandVoorraad, Q4)")
    demand_units = models.IntegerField(null=True, blank=True, help_text="Number of housing units demanded = baseline population of the year / average household size (derived for city records; a stored value is kept without both inputs)")
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Housing Supply/Demand {self.year} for {self.neighborhood}"

    def save(self, *args, **kwargs):
        """
        Housing demand follows the population: homes needed = baseline
        population of the year / average persons per home.

        DAG edges: Total_Population, Household_Size -> Housing_Demand
        """
        if self.city_id:
            size = HouseholdSize.for_year(self.city_id, self.year)
            population, _partial = chain.baseline_population(self.city, self.year)
            demand = chain.demand_units(population, size.average_size if size else None)
            if demand is not None:
                self.demand_units = demand
                if kwargs.get("update_fields"):
                    kwargs["update_fields"] = set(kwargs["update_fields"]) | {"demand_units"}
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Housing Supply and Demand"
        verbose_name_plural = "Housing Supply and Demand Records"
          
class ScenarioHousingNeed(models.Model):
    """
    Homes needed for the population of a stored KNMI'23 climate scenario run
    (weather.ClimateScenarioRun: its population year, CBS variant and extra
    growth; 2100 = trend extrapolation), against the current stock and the
    baseline year. Same equation as HousingSupplyDemand (chain.demand_units);
    the household size is HouseholdSize.for_year, i.e. the latest CBS year
    held constant beyond it. HousingSupplyDemand is not changed. Created by
    housing/signals.py when a run is saved. Not a map layer.
    """
    registry_hidden = True

    run = models.OneToOneField("weather.ClimateScenarioRun", on_delete=models.CASCADE, related_name="housing_need")
    city = models.ForeignKey("administrative.City", on_delete=models.DO_NOTHING, null=True, blank=True, related_name="+")
    year = models.IntegerField(null=True, blank=True)
    population = models.IntegerField(null=True, blank=True)
    population_extrapolated = models.BooleanField(default=False)
    household_size = models.FloatField(null=True, blank=True)
    household_size_year = models.IntegerField(null=True, blank=True, help_text="Year of the CBS household size used (held constant after it)")
    dwellings_needed = models.IntegerField(null=True, blank=True)
    stock_units = models.IntegerField(null=True, blank=True, help_text="Latest HousingSupplyDemand.supply_units up to the baseline year")
    stock_year = models.IntegerField(null=True, blank=True)
    gap_units = models.IntegerField(null=True, blank=True, help_text="dwellings_needed - stock_units (negative = surplus)")
    baseline_population = models.IntegerField(null=True, blank=True)
    baseline_dwellings_needed = models.IntegerField(null=True, blank=True)
    last_updated = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Scenario Housing Need"
        verbose_name_plural = "Scenario Housing Needs"

    def save(self, *args, **kwargs):
        """
        DAG edges: Total_Population, Household_Size -> Housing_Demand
        dwellings_needed = chain.demand_units(population of the run's year, household size)
        gap = chain.dwelling_gap(needed, stock)
        """
        from administrative.calculations.population import get_population, is_extrapolated

        run = self.run
        if self.city_id is None:
            self.city = run.city
        self.year = run.population_year
        if self.city is not None:
            self.population = get_population(self.city, self.year, run.population_variant, run.population_growth_pct)
            self.population_extrapolated = is_extrapolated(self.city, self.year)
            self.baseline_population = get_population(self.city, run.baseline_year, run.population_variant, 0)
            size = HouseholdSize.for_year(self.city, self.year)
            if size is not None:
                self.household_size = round(size.average_size, 3)
                self.household_size_year = size.year
                self.dwellings_needed = chain.demand_units(self.population, size.average_size)
                baseline_size = HouseholdSize.for_year(self.city, run.baseline_year)
                self.baseline_dwellings_needed = chain.demand_units(
                    self.baseline_population, baseline_size.average_size if baseline_size else None)
            stock = (HousingSupplyDemand.objects.filter(city=self.city, year__lte=run.baseline_year)
                     .order_by('-year', '-id').first()
                     or HousingSupplyDemand.objects.filter(city=self.city).order_by('year', 'id').first())
            if stock is not None:
                self.stock_units, self.stock_year = stock.supply_units, stock.year
            self.gap_units = chain.dwelling_gap(self.dwellings_needed, self.stock_units)
        self.last_updated = timezone.now()
        super().save(*args, **kwargs)


class HousingProject(models.Model):
    id=models.AutoField(primary_key=True)
    neighborhood = models.ForeignKey("administrative.Neighborhood", verbose_name="Neighborhood", on_delete=models.DO_NOTHING)
    year = models.IntegerField(help_text="Year of the housing project data")
    year_expected_completion = models.IntegerField(help_text="Year of expected completion of the housing project")
    project_name = models.CharField(max_length=100, help_text="Name of the housing project")
    project_description = models.TextField(blank=True, default="", help_text="Description of the housing project")
    project_area = models.FloatField(help_text="Area of the housing project in square meters")
    project_units = models.IntegerField(help_text="Number of housing units in the project")
    STATUS_CHOICES = [("planned", "Planned"), ("completed", "Completed")]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planned", help_text="Completed projects with a generated layout become streets, buildings and dwellings (DAG edge New_Units -> Buildings, housing/signals.py)")
    # Every parameter of the neighbourhood generator (typology, sizes, angle,
    # generator_version), as resolved by builtup/calculations/generative.py::resolve_params,
    # so the stored layout can be regenerated exactly.
    generator_params = models.JSONField(null=True, blank=True, help_text="Neighbourhood generator parameters of the layout (builtup/calculations/generative.py); empty = no generated layout")
    geom = models.MultiPolygonField(srid=COORDINATE_SYSTEM)
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Housing Project {self.year} for {self.neighborhood}"
    
    class Meta:
        verbose_name = "Housing Project"
        verbose_name_plural = "Housing Projects"
        
class CentralBankPolicy(models.Model):
    id = models.AutoField(primary_key=True)
    province = models.ForeignKey("administrative.Province", verbose_name="Province", on_delete=models.DO_NOTHING)
    year = models.IntegerField(help_text="Year of the policy data")
    interest_rate = models.FloatField(help_text="Central bank interest rate in percentage (%)")
    LTV_limit = models.FloatField(help_text="Loan-to-Value limit in percentage (%)")
    LTI_limit = models.FloatField(help_text="Loan-to-Income limit in percentage (%)")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Central Bank Policy {self.year} for {self.province}"
    
    class Meta:
        verbose_name = "Central Bank Policy"
        verbose_name_plural = "Central Bank Policies"


class CreditSupplyConditions(models.Model):
    id = models.AutoField(primary_key=True)
    province = models.ForeignKey("administrative.Province", verbose_name="Province", on_delete=models.DO_NOTHING)
    year = models.IntegerField(help_text="Year of the credit supply conditions data")
    mortgageRate = models.FloatField(help_text="Mortgage rate in percentage (%)")
    mortgage_approval_rate = models.FloatField(help_text="Mortgage approval rate in percentage (%)")
    average_down_payment = models.FloatField(help_text="Average down payment as a percentage of property value (%)")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Credit Supply Conditions {self.year} for {self.province}"
    
    class Meta:
        verbose_name = "Credit Supply Conditions"
        verbose_name_plural = "Credit Supply Conditions Records"

class Mortgage(models.Model):
    id= models.AutoField(primary_key=True)
    property = models.ForeignKey("builtup.Property", verbose_name="Property", on_delete=models.DO_NOTHING)
    totalLoanAmount = models.FloatField(help_text="Total loan amount in EUR")
    interestRate = models.FloatField(help_text="Mortgage interest rate in percentage (%)")
    loanTermYears = models.IntegerField(help_text="Loan term in years")
    downPayment = models.FloatField(help_text="Down payment in EUR")
    monthlyPayment = models.FloatField(help_text="Monthly payment in EUR")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Mortgage for {self.property}"
    
    class Meta:
        verbose_name = "Mortgage"
        verbose_name_plural = "Mortgages"
            
class Rentals(models.Model):
    id = models.AutoField(primary_key=True)
    property = models.ForeignKey("builtup.Property", verbose_name="Property", on_delete=models.DO_NOTHING)
    monthlyRent = models.FloatField(help_text="Monthly rent in EUR")
    annualRent = models.FloatField(help_text="Annual rent in EUR")
    priceToRentRatio = models.FloatField(help_text="Price-to-rent ratio")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Rental for {self.property}"
    
    def save(self, *args, **kwargs):
        self.annualRent = self.monthlyRent * 12
        # Property has no `price`; use the sale price, else the listing price.
        price = self.property.salePrice_EUR or self.property.listingPrice_EUR
        self.priceToRentRatio = price / self.annualRent if price and self.annualRent else 0
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Rental"
        verbose_name_plural = "Rentals"
              
class HousePriceIndex(models.Model):
    """
    House price index of a neighborhood and year, base year = 100.

    Derived in save() from the NVM market reports of the neighborhood's NVM
    region (housing/calculations/prices.py: annual mean of the quarterly median
    price per m2, over the region's base year); without NVM data for the region
    and year the stored `index_value` is kept (a manual or imported value).

    DAG edges: Market_Reports -> House_Price_Index
    """
    id = models.AutoField(primary_key=True)
    neighborhood = models.ForeignKey("administrative.Neighborhood", verbose_name="Neighborhood", on_delete=models.DO_NOTHING)
    year = models.IntegerField(help_text="Year of the house price index data")
    index_value = models.FloatField(help_text="Value of the house price index (base year = 100)")
    baseYear = models.IntegerField(null=True, blank=True, editable=False, help_text="Base year of the index (= 100); derived from the NVM reports")
    pricePerSqm_EUR = models.FloatField(null=True, blank=True, editable=False, help_text="NVM annual mean of the quarterly median price per m2 of the year, EUR/m2; derived")
    nvmRegion = models.CharField(max_length=100, blank=True, editable=False, help_text="NVM region whose reports the index follows; derived")
    indexMethod = models.CharField(max_length=120, blank=True, editable=False, help_text="Method of the derived index (chain.INDEX_METHOD); empty = stored value")
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"House Price Index {self.year} for {self.neighborhood}"

    def save(self, *args, **kwargs):
        """
        index = 100 x NVM price per m2 of the year / that of the region's base year
        (housing/calculations/chain.py::price_index). Without the region's NVM
        prices for the year the stored index is kept.

        DAG edges: Market_Reports -> House_Price_Index
        """
        from .calculations import prices

        derived = prices.index_for(self.neighborhood_id, self.year)
        if derived is not None:
            self.index_value = derived["index"]
            self.baseYear = derived["base_year"]
            self.pricePerSqm_EUR = derived["price"]
            self.nvmRegion = derived["region"]
            self.indexMethod = chain.INDEX_METHOD
            if kwargs.get("update_fields"):
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {
                    "index_value", "baseYear", "pricePerSqm_EUR", "nvmRegion", "indexMethod"}
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "House Price Index"
        verbose_name_plural = "House Price Index Records"


class WOZValue(models.Model):
    """
    Mean WOZ value of the dwellings of a neighborhood (CBS "Kerncijfers wijken
    en buurten", one table per year, catalog entries CBS_WOZ_<year>) and the WOZ
    value per m2 derived from it: the price level the hedonic model of Phase 4
    is fitted on (docs/ACCESSIBILITY_PLAN.md).

    `year` is the CBS table year; its valuation date is 1 January of the year
    before (chain.woz_valuation_year). The floor area is the mean BAG usable area
    of the neighborhood's dwellings at the time of the import
    (housing/calculations/woz.py), stored with its dwelling count. The mean
    walk and bike accessibility of the neighborhood's residential buildings is
    frozen with the row as the baseline the price equation measures a change
    against; it is written once by `woz.freeze_baselines`, not re-derived.

    The map layer is the proxy `WOZValueLatest` (latest year per neighborhood,
    painted by WOZ value per m2); this table holds every year and is not a layer.

    Stored input plus one derived ratio, no DAG edge.
    """
    registry_hidden = True

    id = models.AutoField(primary_key=True)
    neighborhood = models.ForeignKey("administrative.Neighborhood", verbose_name="Neighborhood", on_delete=models.DO_NOTHING, related_name="woz_values")
    year = models.IntegerField(help_text="CBS table year (WOZ valuation date = 1 January of the year before)")
    avgWOZ_EUR = models.FloatField(null=True, blank=True, help_text="Mean WOZ value of the dwellings, EUR (CBS publishes x 1 000 EUR)")
    dwellings = models.IntegerField(null=True, blank=True, help_text="Dwelling stock (CBS Woningvoorraad)")
    meanArea_sqm = models.FloatField(null=True, blank=True, help_text="Mean BAG usable area of the dwellings inside the neighborhood, m2 (housing/calculations/woz.py)")
    areaDwellings = models.IntegerField(null=True, blank=True, help_text="Dwellings the mean area is taken over")
    woz_per_sqm = models.FloatField(null=True, blank=True, editable=False, help_text="Mean WOZ value / mean dwelling area, EUR/m2; derived")
    cbs_table_id = models.CharField(max_length=20, blank=True, help_text="CBS StatLine table the value comes from")
    source = models.CharField(max_length=100, default="CBS Kerncijfers wijken en buurten", help_text="Data provider")
    method = models.CharField(max_length=100, blank=True, editable=False, help_text="Method of the per-m2 value (chain.WOZ_METHOD)")
    baselineAccessWalk = models.FloatField(null=True, blank=True, help_text="Mean walk accessibility score (0-100) of the neighborhood's residential buildings when frozen")
    baselineAccessBike = models.FloatField(null=True, blank=True, help_text="Mean bike accessibility score (0-100) of the neighborhood's residential buildings when frozen")
    baselineMethod = models.CharField(max_length=60, blank=True, help_text="Accessibility method stamp of the frozen baseline (builtup chain.METHOD_STAMP)")
    baselineSnapshot = models.DateField(null=True, blank=True, help_text="Network snapshot date of the frozen baseline")
    geom = models.MultiPolygonField(srid=COORDINATE_SYSTEM, null=True, blank=True, help_text="Copy of the neighborhood's geometry, for the map layer")
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"WOZ {self.year} of {self.neighborhood_id}: {self.avgWOZ_EUR}"

    def save(self, *args, **kwargs):
        self.geom = self.neighborhood.geom
        self.woz_per_sqm = chain.woz_per_sqm(self.avgWOZ_EUR, self.meanArea_sqm)
        self.method = chain.WOZ_METHOD if self.woz_per_sqm is not None else ""
        if kwargs.get("update_fields"):
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"woz_per_sqm", "method", "geom"}
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "WOZ value"
        verbose_name_plural = "WOZ values"
        constraints = [models.UniqueConstraint(fields=["neighborhood", "year"], name="unique_woz_neighborhood_year")]


class _LatestWOZ(models.Manager):
    def get_queryset(self):
        newest = (WOZValue.objects.filter(neighborhood=models.OuterRef("neighborhood"))
                  .order_by("-year").values("year")[:1])
        return super().get_queryset().filter(year=models.Subquery(newest), geom__isnull=False)


class WOZValueLatest(WOZValue):
    """Map layer: the WOZ value per m2 of each neighborhood, latest table year."""
    registry_hidden = False
    objects = _LatestWOZ()

    class Meta:
        proxy = True
        verbose_name = "WOZ value per m2 (latest year)"
        verbose_name_plural = "WOZ value per m2 (latest year)"


class NVMRegionMapping(models.Model):
    """
    The NVM region (COROP area) a municipality belongs to, from NVM's
    "Gebiedsindeling COROP en gemeenten" (importer/nvm_reports.py). NVM reports
    are per region; this maps them to cities, neighborhoods and their index.
    """
    registry_hidden = True

    city = models.OneToOneField("administrative.City", on_delete=models.CASCADE, related_name="nvm_region")
    region = models.CharField(max_length=100, help_text="NVM region name, as in the report titles")
    regionNumber = models.IntegerField(null=True, blank=True, help_text="COROP number in NVM's list")
    source = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.city_id} -> {self.region}"

    class Meta:
        verbose_name = "NVM region mapping"
        verbose_name_plural = "NVM region mappings"


class NVMMarketReport(models.Model):
    """
    One quarterly NVM housing-market figure set: a region, a quarter and a
    dwelling type (Tussenwoning ... Appartement, Totaal), read from NVM's
    "Woningmarkt kwartaalcijfers" PDF by importer/nvm_reports.py. Each PDF gives
    three quarters per figure (same quarter last year, previous quarter, report
    quarter); the figure of the newest report wins.

    The provenance fields make a figure reproducible: the PDF's SHA-256, where it
    came from, when it was read and the parser version. NVM's terms reserve
    reproduction and redistribution (docs/DATA_SOURCES.md): use the figures for
    non-commercial research and ask NVM before redistributing them.

    Feeds House_Price_Index through housing/signals.py (DAG edge
    Market_Reports -> House_Price_Index).
    """
    registry_hidden = True
    TOTAL = "Totaal"

    region = models.CharField(max_length=100, help_text="NVM region; 'Nederland' for the national report")
    year = models.IntegerField()
    quarter = models.IntegerField(help_text="1-4")
    dwellingType = models.CharField(max_length=30, help_text="Tussenwoning, Hoekwoning, 2-onder-1-kap, Vrijstaand, Appartement or Totaal")
    transactions = models.IntegerField(null=True, blank=True, help_text="Number of transactions in the quarter")
    medianPrice_EUR = models.FloatField(null=True, blank=True, help_text="Median transaction price, EUR (NVM prints x 1 000)")
    pricePerSqm_EUR = models.FloatField(null=True, blank=True, help_text="Median transaction price per m2 GBO wonen, EUR/m2")
    daysOnMarket = models.FloatField(null=True, blank=True, help_text="Days from listing to deed (Verkooptijd)")
    askingGap_pct = models.FloatField(null=True, blank=True, help_text="Difference between last asking price and transaction price, % (positive = paid more)")
    aboveAsking_pct = models.FloatField(null=True, blank=True, help_text="Share of the homes sold above the last asking price, %")
    reportYear = models.IntegerField(help_text="Year of the report the figures were read from")
    reportQuarter = models.IntegerField(help_text="Quarter of that report")
    source_url = models.CharField(max_length=500, blank=True, help_text="Where the PDF was published")
    source_file = models.CharField(max_length=200, blank=True)
    pdf_sha256 = models.CharField(max_length=64, help_text="SHA-256 of the PDF the figures were read from")
    retrieved_at = models.DateTimeField(default=timezone.now)
    parser_version = models.CharField(max_length=30, help_text="importer/nvm_reports.py::PARSER_VERSION")

    def __str__(self):
        return f"NVM {self.region} {self.year}-{self.quarter} {self.dwellingType}"

    class Meta:
        verbose_name = "NVM market report figure"
        verbose_name_plural = "NVM market report figures"
        constraints = [models.UniqueConstraint(fields=["region", "year", "quarter", "dwellingType"], name="unique_nvm_region_quarter_type")]



class HousingAffordability(models.Model):
    id = models.AutoField(primary_key=True)
    neighborhood = models.ForeignKey("administrative.Neighborhood", verbose_name="Neighborhood", on_delete=models.DO_NOTHING)
    year = models.IntegerField(help_text="Year of the housing affordability data")
    medianIncome = models.FloatField(help_text="Median annual household income in EUR")
    medianExpenditure = models.FloatField(help_text="Median household expenditure in EUR") #TODO: check how to connect with the expenditure data from the water and electricity models
    medianRent = models.FloatField(help_text="Median monthly rent in EUR")
    medianMortgage = models.FloatField(help_text="Median monthly mortgage payment in EUR")
    medianHousePrice = models.FloatField(help_text="Median house price in EUR")
    medianDisposableIncome = models.FloatField(help_text="Median disposable income in EUR")
    affordabilityIndex = models.FloatField(help_text="Affordability index (median house price divided by median income)")
    affordabilityStressLevel = models.CharField(max_length=50, blank=True, choices=AFFORDABILITY_STRESS_LEVELS, help_text="Affordability stress level: derived in save() from the housing-cost burden and the neighborhood's socio-economic status; a typed value is kept only while the inputs are missing")
    housingCostBurden_pct = models.FloatField(null=True, blank=True, editable=False, help_text="Housing cost (tenure-weighted rent / mortgage x 12) as % of the median annual income; derived")
    sesUsed = models.FloatField(null=True, blank=True, editable=False, help_text="CBS socio-economic status score used for the stress level (None: no social profile); derived")
    sesModifier = models.FloatField(null=True, blank=True, editable=False, help_text="Factor the SES score put on the cost burden; derived")
    stressMethod = models.CharField(max_length=100, blank=True, editable=False, help_text="Method and parameters that produced the stress level (housing/calculations/chain.py::STRESS_METHOD)")
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Housing Affordability {self.year} for {self.neighborhood}"

    def save(self, *args, **kwargs):
        """
        Derives the affordability index, the disposable income and the stress level.

        The stress level is the housing-cost burden (rent / mortgage weighted by
        the neighborhood's share of rental homes, over the median income) scaled
        by the CBS socio-economic status of its NeighborhoodSocialProfile
        (housing/calculations/chain.py). Without a usable income or cost the
        stored level is kept.

        DAG edges: Income_Expenses -> Affordability_Stress
                   Social_Profile  -> Affordability_Stress
        """
        self.affordabilityIndex = self.medianHousePrice / self.medianIncome if self.medianIncome != 0 else 0 #TODO: check if this is the right way to calculate the affordability index, or if we should use median disposable income instead of median income
        self.medianDisposableIncome = self.medianIncome - self.medianExpenditure
        profile = NeighborhoodSocialProfile.objects.filter(neighborhood_id=self.neighborhood_id).first()
        ses = profile.socioEconomicStatus if profile else None
        share = profile.rentalHousing_pct if profile else None
        burden = chain.housing_cost_burden(
            chain.monthly_housing_cost(self.medianRent, self.medianMortgage, share), self.medianIncome)
        level = chain.affordability_stress_level(burden, ses)
        if level is not None:
            self.housingCostBurden_pct = round(burden * 100, 2)
            self.sesUsed = ses
            self.sesModifier = chain.ses_modifier(ses)
            self.stressMethod = chain.STRESS_METHOD
            self.affordabilityStressLevel = level
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Housing Affordability"
        verbose_name_plural = "Housing Affordability Records"
        
    

class NeighborhoodSocialProfile(models.Model):
    """
    Social vulnerability context per neighborhood, from the
    Klimaateffectatlas WFS (RIVM/CBS indicators; importer catalog kea_*,
    docs/KEA_WFS_MAPPING.md). One row per neighborhood; each KEA layer fills
    its own columns. Context for the Income_Expenses / Affordability_Stress
    nodes of core/DAG.dot; stored inputs only, no DAG edge implemented.
    """
    id = models.AutoField(primary_key=True)
    neighborhood = models.OneToOneField("administrative.Neighborhood", verbose_name="Neighborhood", on_delete=models.DO_NOTHING, related_name="social_profile")
    rentalHousing_pct = models.FloatField(null=True, blank=True, help_text="Rental dwellings, % (KEA nl_percentage_huurwoningen_buurt)")
    socioEconomicStatus = models.FloatField(null=True, blank=True, help_text="CBS socio-economic status score (welvaart, opleiding, arbeid), standardised (KEA nl_sociaal_economische_status_buurt.ses_woa)")
    frailHealth_pct = models.FloatField(null=True, blank=True, help_text="Adults with frail health, % (RIVM, KEA nl_broze_gezondheid_buurt)")
    severeLoneliness_pct = models.FloatField(null=True, blank=True, help_text="Adults who are severely lonely, % (RIVM, KEA nl_sterk_eenzaam_buurt)")
    neighborhoodType = models.CharField(max_length=100, null=True, blank=True, help_text="Neighborhood type, e.g. 'Bloemkoolwijk' (KEA wijktypen_buurten.Wijktype1)")
    source = models.CharField(max_length=100, default="Klimaateffectatlas", help_text="Data provider")
    geom = models.MultiPolygonField(srid=COORDINATE_SYSTEM)
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Social profile {self.neighborhood_id}"

    class Meta:
        verbose_name = "Neighborhood Social Profile"
        verbose_name_plural = "Neighborhood Social Profiles"


class ResidentialPropertyManager(models.Manager):
    def get_queryset(self):
        # The property's own BAG function, not its building's: a shop under
        # flats sits in a 'mixed' building but is not a dwelling.
        return super().get_queryset().filter(usageFunction__contains=["Residential function"])


class ResidentialProperty(Property):
    """
    Proxy onto builtup.Property limited to dwellings (BAG woonfunctie), its
    own map layer in the housing catalog. Same table and save() as Property;
    the map's GeoJSON applies this manager's filter (mainMap/views.py::_manager_filter).
    """
    objects = ResidentialPropertyManager()

    class Meta:
        proxy = True
        verbose_name = "Residential Property"
        verbose_name_plural = "Residential Properties"
