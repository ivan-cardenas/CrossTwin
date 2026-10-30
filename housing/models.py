from django.contrib.gis.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings

from builtup.models import Property
from . import chain

COORDINATE_SYSTEM = settings.COORDINATE_SYSTEM
AFFORDABILITY_STRESS_LEVELS = [('low', 'Low'), ('moderate', 'Moderate'), ('high', 'High')] #TODO: check if these are the right thresholds for the affordability stress levels,
                                                                            #  or if we should use different thresholds based on the literature


class HouseholdSize(models.Model):
    """
    Average number of persons per private household (= per occupied home) of a
    City and year, from CBS: households of table 86291NED and the population on
    1 January of table 03759NED (catalog CBS_Households / CBS_PopulationJan,
    each fills its own column; City.pk is the gemeente number). The average is
    derived, so a manually entered `average_size` is kept only without both
    inputs.

    Feeds the dashboard's "persons per home" slider, `HousingSupplyDemand`
    (demand = population / average_size) and `builtup.Property.residents`
    (each dwelling is occupied by this average); see housing/signals.py.

    DAG edges: Total_Population -> Household_Size (CBS ratio)
    """
    id = models.AutoField(primary_key=True)
    city = models.ForeignKey("administrative.City", verbose_name="City", on_delete=models.DO_NOTHING)
    year = models.IntegerField(help_text="Year (1 January) of the household data")
    households = models.IntegerField(null=True, blank=True, help_text="Private households (CBS 86291NED)")
    population = models.IntegerField(null=True, blank=True, help_text="Population on 1 January (CBS 03759NED)")
    average_size = models.FloatField(null=True, blank=True, help_text="Average persons per household = population / households")
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Household size {self.year} for {self.city_id}: {self.average_size}"

    def save(self, *args, **kwargs):
        size = chain.average_household_size(self.population, self.households)
        if size is not None:
            self.average_size = size
        # update_or_create() (the CBS importer) saves with update_fields = the
        # columns it was handed; without this the derived average is never written.
        if kwargs.get("update_fields"):
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"average_size"}
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
    supply_units = models.IntegerField(help_text="Number of housing units supplied")
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
          
class HousingProject(models.Model):
    id=models.AutoField(primary_key=True)
    neighborhood = models.ForeignKey("administrative.Neighborhood", verbose_name="Neighborhood", on_delete=models.DO_NOTHING)
    year = models.IntegerField(help_text="Year of the housing project data")
    year_expected_completion = models.IntegerField(help_text="Year of expected completion of the housing project")
    project_name = models.CharField(max_length=100, help_text="Name of the housing project")
    project_description = models.TextField(help_text="Description of the housing project")
    project_area = models.FloatField(help_text="Area of the housing project in square meters")
    project_units = models.IntegerField(help_text="Number of housing units in the project")
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
    id = models.AutoField(primary_key=True)
    neighborhood = models.ForeignKey("administrative.Neighborhood", verbose_name="Neighborhood", on_delete=models.DO_NOTHING)
    year = models.IntegerField(help_text="Year of the house price index data")
    index_value = models.FloatField(help_text="Value of the house price index (base year = 100)")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"House Price Index {self.year} for {self.neighborhood}"
    
    class Meta:
        verbose_name = "House Price Index"
        verbose_name_plural = "House Price Index Records"
        

class HousingAffordability(models.Model):
    id = models.AutoField(primary_key=True)
    neighborhood = models.ForeignKey("administrative.Neighborhood", verbose_name="Neighborhood", on_delete=models.DO_NOTHING)
    year = models.IntegerField(help_text="Year of the housing affordability data")
    medianIncome = models.FloatField(help_text="Median household income in EUR")
    medianExpenditure = models.FloatField(help_text="Median household expenditure in EUR") #TODO: check how to connect with the expenditure data from the water and electricity models
    medianRent = models.FloatField(help_text="Median rent in EUR")
    medianMortgage = models.FloatField(help_text="Median mortgage in EUR")
    medianHousePrice = models.FloatField(help_text="Median house price in EUR")
    medianDisposableIncome = models.FloatField(help_text="Median disposable income in EUR")
    affordabilityIndex = models.FloatField(help_text="Affordability index (median house price divided by median income)")
    affordabilityStressLevel = models.CharField(max_length=50, choices=AFFORDABILITY_STRESS_LEVELS, help_text="Affordability stress level (e.g., low, moderate, high)")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Housing Affordability {self.year} for {self.neighborhood}"
    
    def save(self, *args, **kwargs):
        self.affordabilityIndex = self.medianHousePrice / self.medianIncome if self.medianIncome != 0 else 0 #TODO: check if this is the right way to calculate the affordability index, or if we should use median disposable income instead of median income
        self.medianDisposableIncome = self.medianIncome - self.medianExpenditure
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
