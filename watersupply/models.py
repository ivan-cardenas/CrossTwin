from django.contrib.gis.db import models
from django.db.models import Case, ExpressionWrapper, F, FloatField, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.core.exceptions import ValidationError
from administrative.models import Province, City, Neighborhood
from physicalEnv.models import EnvironmentalCosts
from django.conf import settings

COORDINATE_SYSTEM = settings.COORDINATE_SYSTEM

# EUR/kWh used when no ElectricityCost record exists for a province (or nationally)
# in the year: an assumed Dutch non-household price, not a measured value.
DEFAULT_ELECTRICITY_EUR_KWH = 0.15

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


# Create your models here.
class ConsumptionCapita(models.Model):
    id=models.AutoField(primary_key=True)
    city = models.ForeignKey(City, on_delete=models.CASCADE, help_text="City code from administrative.City")
    year = models.IntegerField()
    consumption_capita_L_d = models.FloatField( help_text="in liters per person per day") # L/person/day
    total_consumption_m3_yr = models.FloatField( help_text="in cubic meters per year", null=True, blank=True)  # m3/year
    last_updated = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        """
        DAG edges: Total_Population, ConsumptionCapita -> Total_Water_Demand
                   (yearly consumption is an intermediate, not a DAG node)
        total_consumption_m3_yr = L/person/day / 1000 * population * 365, with
        the baseline population of `year` (watersupply/calculations/chain.py).
        """
        from .calculations.chain import baseline_population, consumption_m3_yr

        if self.consumption_capita_L_d < 0:
            raise ValidationError("Consumption Capita cannot be negative")
        population = baseline_population(self.city, self.year)
        if population is not None:
            self.total_consumption_m3_yr = consumption_m3_yr(self.consumption_capita_L_d, population)
        self.last_updated = timezone.now()
        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.city} - {self.year}: {self.consumption_capita_L_d} L/person/day"

    @classmethod
    def for_year(cls, city, year):
        """
        The record to use for `city` in `year`: that year's, else the latest
        earlier one (a 2015 survey still describes 2026 until a newer one
        exists), else the earliest later one. None when the city has none.
        """
        records = cls.objects.filter(city=city)
        return (
            records.filter(year__lte=year).order_by('-year', '-id').first()
            or records.filter(year__gt=year).order_by('year', 'id').first()
        )
    
    class Meta:
        verbose_name = "Consumption Capita"
        verbose_name_plural = "Consumption Capita"
    
class TotalWaterDemand(models.Model):
    city = models.ForeignKey(City, on_delete=models.CASCADE , help_text="City code from administrative.City")
    year = models.IntegerField()
    demandDay = models.FloatField( help_text="in Million cubic meters per day") # Mm3/day
    demandYR = models.FloatField(null=True, help_text="in Million cubic meters per year")  # Mm3/year
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.city} - {self.year}: {self.demandDay} Mm3/day"
    
    def save(self, *args, **kwargs):
        """
        DAG edges: Total_Population -> Total_Water_Demand
                   ConsumptionCapita -> Total_Water_Demand
        demandDay [Mm3/day] = population * L/person/day / 1e9   (L -> Mm3), with
        the baseline population of `year` (watersupply/calculations/chain.py) and the
        consumption of `year` or the closest year before it
        (ConsumptionCapita.for_year).
        """
        from .calculations.chain import baseline_population, demand_m3_d

        consumption = ConsumptionCapita.for_year(self.city, self.year)
        if consumption is None:
            raise ValidationError(
                f"No ConsumptionCapita record for {self.city}; "
                "cannot calculate the water demand."
            )
        population = baseline_population(self.city, self.year) or 0
        self.demandDay = demand_m3_d(consumption.consumption_capita_L_d, population) / 1e6  # m3 -> Mm3
        self.demandYR = self.demandDay * 365
        self.last_updated = timezone.now()
        super().save(*args, **kwargs)
        
    class Meta:
        verbose_name = "Total Water Demand"
        verbose_name_plural = "Total Water Demand Records"
    
class SupplySecurity(models.Model):
    city = models.ForeignKey(City, on_delete=models.CASCADE, help_text="City code from administrative.City")
    year = models.IntegerField()
    supply_security_pct = models.FloatField(help_text="in percent")   # %
    security_goal_pct = models.FloatField(help_text="in percent") # %
    service_time_hours = models.FloatField(help_text="in hours per day") # hours/day
    last_updated = models.DateTimeField(default=timezone.now) 
    
    def __str__(self):
        return f"{self.city} - {self.year}: {self.supply_security_pct}%"

    def save(self, *args, **kwargs):
        """
        DAG edges: Total_Water_Demand -> Supply_Security
                   Total_Water_Prod   -> Supply_Security
                   Supply_Security    -> Service_Time
        Same functions as watersupply.views._build_indicators (watersupply/calculations/chain.py):
          supply_security_pct = production / demand * 100
          service_time_hours  = 24 if production >= demand else 24 * production / demand
        Only recalculated when both demand (TotalWaterDemand for this city/year)
        and production are known; otherwise the supplied values are kept.
        """
        from .calculations.indicators import calculate_total_production_day  # avoid circular import
        from .calculations.chain import service_time_hours, supply_security_pct

        demand = TotalWaterDemand.objects.filter(city=self.city, year=self.year).first()
        demand_m3_d = demand.demandDay * 1e6 if demand else 0       # Mm3/day -> m3/day
        production_m3_d = calculate_total_production_day(self.city)  # m3/day
        if demand_m3_d > 0 and production_m3_d > 0:
            self.supply_security_pct = supply_security_pct(production_m3_d, demand_m3_d)
            self.service_time_hours = service_time_hours(production_m3_d, demand_m3_d)
        self.last_updated = timezone.now()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Supply Security"
        verbose_name_plural = "Supply Security Records"
    
class UsersLocation(models.Model):
    id = models.AutoField(primary_key=True)
    neighborhood = models.ForeignKey(Neighborhood, on_delete=models.DO_NOTHING, help_text="Neighborhood code from administrative.Neighborhood") #TODO: Change to City or make per point?
    usersTotal = models.IntegerField(null=True, blank=True, help_text="Water users in the neighborhood: the residents of its properties (derived when it has properties with residents)")
    ResidentialUsers = models.IntegerField(null=True, blank=True, help_text="Number of residential users (= usersTotal when derived)")
    CommercialUsers = models.IntegerField(null=True, blank=True, help_text="Number of commercial users (input, not part of usersTotal)")
    IndustrialUsers = models.IntegerField(null=True, blank=True, help_text="Number of industrial users (input, not part of usersTotal)")
    populationServed = models.IntegerField(null=True, blank=True, help_text="Residents of the neighborhood's properties within buffer_m of the pipe network")
    buffer_m = models.FloatField(null=True, blank=True, editable=False, help_text="Service distance of a pipe used for populationServed (the city's latest CoverageWaterSupply.buffer_m); empty when the counts are stored inputs")
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.neighborhood} - {self.usersTotal} users"

    def save(self, *args, **kwargs):
        """
        A users location is each property (home); its users are its residents.
        Without a property with residents the stored (or supplied) counts are kept.

        DAG edges: Total_Population -> NumberUsers  (Σ residents of the properties)
                   Coverage_WS_Area -> NumberUsers  (Σ residents within buffer_m of a pipe)
        """
        from .calculations.users import neighborhood_users, service_buffer_m

        city_id = (Neighborhood.objects.filter(pk=self.neighborhood_id)
                   .values_list('district__city_id', flat=True).first())
        buffer_m = service_buffer_m(city_id)
        users = neighborhood_users([self.neighborhood_id], buffer_m).get(self.neighborhood_id)
        if users and users.residents > 0:
            self.usersTotal = self.ResidentialUsers = round(users.residents)
            self.populationServed = round(users.residents_served)
            self.buffer_m = buffer_m
        self.last_updated = timezone.now()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Users Location"
        verbose_name_plural = "Users Locations"
    
class MeteredResidential(models.Model):
    id = models.AutoField(primary_key=True)
    userLocation = models.ForeignKey(UsersLocation, on_delete=models.DO_NOTHING, help_text="UsersLocation ID from watersupply.UsersLocation")
    installed_meters = models.IntegerField(help_text="Number of installed meters")
    functional_meters = models.IntegerField(help_text="Number of functional meters")
    collected_meters = models.IntegerField(help_text="Number of collected meters")
    userTariff_EUR_m3 = models.FloatField(help_text="in EUR per cubic meter")
    userAffordability_PCT = models.FloatField(help_text="in percent")
    
    consumption_m3_yr = models.FloatField(
        null=True, blank=True,
        help_text="Annual consumption volume billed (m³/yr)"
    )
    Recovery_EUR = models.FloatField(
        null=True, blank=True,
        help_text="Annual revenue recovered in EUR"
    )
    last_updated = models.DateTimeField(default=timezone.now)
    
    def save(self, *args, **kwargs):
        district = self.userLocation.neighborhood.district
        city = district.city if district else None
        # Get most recent record for this city, not filtered by current year
        consumption_record = ConsumptionCapita.objects.filter(
            city=city
        ).order_by('-year').first() if city else None

        if consumption_record and self.userLocation.populationServed:
            collection_ratio = (
                self.collected_meters / self.installed_meters
                if self.installed_meters else 0  # ← guard against zero division
            )
            # Use per-capita rate × local population served × collection ratio
            # NOT total_consumption_m3_yr which is already the whole city total
            self.consumption_m3_yr = (
                consumption_record.consumption_capita_L_d  # L/person/day
                / 1000                                     # → m³/person/day
                * 365                                      # → m³/person/yr
                * self.userLocation.populationServed       # → m³/yr for this area
                * collection_ratio                         # → billed portion only
            )
            self.Recovery_EUR = self.consumption_m3_yr * self.userTariff_EUR_m3
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.userLocation.neighborhood} - {self.installed_meters} installed meters. {self.Recovery_EUR} EUR recovered"
    
    class Meta:
        verbose_name = "Metered Residential"
        verbose_name_plural = "Metered Residential"

class Watershed(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, help_text="Name of the watershed")
    geom = models.MultiPolygonField(srid=COORDINATE_SYSTEM)
    area_km2 = models.FloatField(help_text="Area of the watershed in square kilometers")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.name}"
    
    def save(self, *args, **kwargs):
        # Calculate area in square kilometers from the geometry
        self.area_km2 = self.geom.area / 1e6  # Convert from m² to km²
        self.last_updated = timezone.now()
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Watershed"
        verbose_name_plural = "Watersheds"

class AvailableFreshWater(models.Model):
    id=models.AutoField(primary_key=True)
    SourceName = models.CharField(max_length=100, help_text="Name of the water source. Corresponds to the Balance Area ")
    watershed = models.ForeignKey(Watershed, on_delete=models.DO_NOTHING, null=True, help_text="Watershed code from watersupply.Watershed. ")
    geom = models.MultiPolygonField(srid=COORDINATE_SYSTEM)
    infiltrationRate_cm_h = models.FloatField(help_text="Area-weighted final infiltration rate in centimeters per hour. Derived in save() from the soil map and land cover (wet-season groundwater) when they cover the source; otherwise a supplied value is kept", null=True, blank=True)
    infiltrationDepth_cm = models.FloatField(help_text="Yearly infiltration (recharge) depth in centimeters per year over the source area. Derived in save() from a year of daily KNMI rain and reference ET at the nearest station, soil map and land cover when all are available; otherwise a supplied value is kept", null=True, blank=True)
    recharge_year = models.IntegerField(null=True, blank=True, help_text="Year of meteorology the recharge depth is derived from; empty = the nearest station's latest complete year")
    totalQuantity_Mm3 = models.FloatField(help_text="total quantity in million cubic meters", null=True, blank=True)
    yield_Mm3_year = models.FloatField(help_text="Yield in million cubic meters per year. Derived in save() from infiltrationDepth_cm and the area when the depth is given", null=True, blank=True)
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.SourceName} - {self.totalQuantity_Mm3} Mm3"

    def save(self, *args, **kwargs):
        """
        DAG edges:  LandCover   -> Infiltration
                    Soil_Type   -> Infiltration
                    Infiltration -> Available_FW
                    Meteorology -> Available_FW

        With soil-map x land-cover pieces over the polygon
        (physicalEnv.calculations.soil.soil_landcover_composition, wet-season groundwater):
          infiltrationRate_cm_h = soil.weighted_infiltration_rate_mm_h / 10
          infiltrationDepth_cm  = chain.recharge_depth_cm_yr(daily rain, ET_ref, pieces),
                                  when a station has a complete year (recharge_year,
                                  else its latest; weather.calculations.water_balance)
        Then yield_Mm3_year = infiltrationDepth_cm / 100 * area_m2 / 1e6
        (chain.recharge_Mm3_yr), whenever the depth is known.
        A missing input keeps the stored (or supplied) value instead of
        writing None. The rate is a capacity during rain, not a yearly amount,
        so it does not enter the yield. Area in the storage CRS's metres.
        """
        from .calculations.chain import recharge_Mm3_yr

        if self.geom is not None:
            self._derive_infiltration()
        if self.infiltrationDepth_cm is not None and self.geom is not None:
            self.yield_Mm3_year = recharge_Mm3_yr(self.infiltrationDepth_cm, self.geom.area)
        # Assign the watershed from location only when none was given explicitly
        if self.watershed_id is None:
            self.watershed = Watershed.objects.filter(geom__contains=self.geom.centroid).first()
        self.last_updated = timezone.now()
        super().save(*args, **kwargs)

    def _derive_infiltration(self):
        """Fill the rate and the yearly depth from soil, land cover and meteorology (see save())."""
        from physicalEnv.calculations.soil import SEASONS, soil_landcover_composition, weighted_infiltration_rate_mm_h
        from weather.calculations.water_balance import yearly_water_balance

        from .calculations.chain import recharge_depth_cm_yr

        composition = soil_landcover_composition(self.geom, SEASONS['wet']['statistic'])[0]
        if not composition:
            return
        rate = weighted_infiltration_rate_mm_h(composition)
        if rate is not None:
            self.infiltrationRate_cm_h = round(rate / 10, 4)
        balance = yearly_water_balance(self.geom.point_on_surface, self.recharge_year)
        if balance is None:
            return
        depth = recharge_depth_cm_yr(balance['daily_rain_mm'], balance['et_ref_mm'], composition)
        if depth is not None:
            self.infiltrationDepth_cm = round(depth, 2)

    class Meta:
        verbose_name = "Available Fresh Water"
        verbose_name_plural = "Available Fresh Water"
    
class ScenarioFreshWater(models.Model):
    """
    Yearly recharge of one AvailableFreshWater source in a stored KNMI'23
    climate scenario run (weather.ClimateScenarioRun): the same water balance
    as AvailableFreshWater.save() (soil x land cover, wet-season groundwater,
    a year of daily KNMI rain and Makkink ET at the nearest station), with the
    scenario's seasonal rain and yearly ET changes. The observed source row
    is not changed; its current-climate values are kept beside the scenario's.
    Created by watersupply/signals.py when a run is saved. Not a map layer.
    """
    registry_hidden = True

    run = models.ForeignKey("weather.ClimateScenarioRun", on_delete=models.CASCADE, related_name="freshwater")
    source = models.ForeignKey(AvailableFreshWater, on_delete=models.CASCADE, related_name="+")
    station = models.ForeignKey("weather.WeatherStation", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
                                help_text="KNMI station of the daily rain and ET (derived)")
    met_year = models.IntegerField(null=True, blank=True, help_text="Year of the station's daily rain and ET (the source's recharge_year, else the latest complete year)")
    rain_mm = models.FloatField(null=True, blank=True)
    runoff_mm = models.FloatField(null=True, blank=True)
    et_mm = models.FloatField(null=True, blank=True)
    recharge_mm = models.FloatField(null=True, blank=True)
    infiltrationDepth_cm = models.FloatField(null=True, blank=True, help_text="Yearly recharge depth in the scenario, cm/yr")
    yield_Mm3_year = models.FloatField(null=True, blank=True, help_text="Yearly recharge volume in the scenario, Mm3/yr")
    baseline_recharge_mm = models.FloatField(null=True, blank=True, help_text="Same balance in the current climate, mm/yr")
    baseline_yield_Mm3_year = models.FloatField(null=True, blank=True, help_text="Same balance in the current climate, Mm3/yr")
    last_updated = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Scenario Fresh Water"
        verbose_name_plural = "Scenario Fresh Water"
        constraints = [models.UniqueConstraint(fields=["run", "source"], name="unique_scenario_freshwater")]

    def save(self, *args, **kwargs):
        """
        DAG edges:  Climate_Change -> Meteorology -> Available_FW
                    LandCover, Soil_Type -> Infiltration -> Available_FW
        balance = chain.scenario_water_balance(station year, composition, scenario)
        depth = recharge / 10; yield = chain.recharge_Mm3_yr(depth, area).
        A missing input (no soil map, land cover or station year) keeps the
        stored values.
        """
        from physicalEnv.calculations.soil import SEASONS, soil_landcover_composition
        from weather.calculations.water_balance import yearly_water_balance

        from .calculations.chain import recharge_Mm3_yr, scenario_water_balance

        geom = self.source.geom
        composition = soil_landcover_composition(geom, SEASONS['wet']['statistic'])[0] if geom else []
        met = yearly_water_balance(geom.point_on_surface, self.source.recharge_year) if composition else None
        scenario = scenario_water_balance(met, composition, self.run.scenario)
        if scenario is not None:
            observed = scenario_water_balance(met, composition, "current")
            self.station, self.met_year = met['station'], met['year']
            self.rain_mm = round(scenario['rain_mm'], 1)
            self.runoff_mm = round(scenario['runoff_mm'], 1)
            self.et_mm = round(scenario['et_mm'], 1)
            self.recharge_mm = round(scenario['recharge_mm'], 1)
            self.infiltrationDepth_cm = round(scenario['recharge_mm'] / 10, 2)
            self.yield_Mm3_year = recharge_Mm3_yr(self.infiltrationDepth_cm, geom.area)
            self.baseline_recharge_mm = round(observed['recharge_mm'], 1)
            self.baseline_yield_Mm3_year = recharge_Mm3_yr(round(observed['recharge_mm'] / 10, 2), geom.area)
        self.last_updated = timezone.now()
        super().save(*args, **kwargs)


class ScenarioWaterSecurity(models.Model):
    """
    Water demand and supply security of a run's city in the scenario's
    population year (weather.ClimateScenarioRun: CBS variant + extra growth,
    2100 = trend extrapolation), against the baseline year, with the same
    equations as TotalWaterDemand / SupplySecurity (calculations/chain.py).
    Production is today's (wells + imports): the scenario changes demand and
    recharge, not the installed capacity. The yearly recharge of the run's
    sources (ScenarioFreshWater) is set beside the extraction. Not a map layer.
    """
    registry_hidden = True

    run = models.OneToOneField("weather.ClimateScenarioRun", on_delete=models.CASCADE, related_name="water_security")
    city = models.ForeignKey("administrative.City", on_delete=models.DO_NOTHING, null=True, blank=True, related_name="+")
    year = models.IntegerField(null=True, blank=True)
    population = models.IntegerField(null=True, blank=True)
    population_extrapolated = models.BooleanField(default=False)
    consumption_L_d = models.FloatField(null=True, blank=True, help_text="L/person/day of ConsumptionCapita.for_year")
    consumption_year = models.IntegerField(null=True, blank=True)
    demand_m3_d = models.FloatField(null=True, blank=True)
    production_m3_d = models.FloatField(null=True, blank=True)
    supply_security_pct = models.FloatField(null=True, blank=True)
    service_time_hours = models.FloatField(null=True, blank=True)
    baseline_population = models.IntegerField(null=True, blank=True)
    baseline_demand_m3_d = models.FloatField(null=True, blank=True)
    baseline_supply_security_pct = models.FloatField(null=True, blank=True)
    yield_Mm3_year = models.FloatField(null=True, blank=True, help_text="Σ scenario recharge of the run's sources, Mm3/yr")
    baseline_yield_Mm3_year = models.FloatField(null=True, blank=True)
    extraction_Mm3_year = models.FloatField(null=True, blank=True, help_text="Active extraction for the city, Mm3/yr")
    last_updated = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Scenario Water Security"
        verbose_name_plural = "Scenario Water Security"

    def save(self, *args, **kwargs):
        """
        DAG edges:  Total_Population -> Total_Water_Demand -> Supply_Security -> Service_Time
                    Available_FW (scenario recharge, set beside the extraction)
        demand = chain.demand_m3_d(consumption, population of the run's year/variant/growth)
        security = chain.supply_security_pct(production, demand); service time likewise.
        """
        from administrative.calculations.population import get_population, is_extrapolated

        from .calculations.chain import demand_m3_d, service_time_hours, supply_security_pct
        from .calculations.indicators import calculate_total_extraction, calculate_total_production_day

        run = self.run
        if self.city_id is None:
            self.city = run.city
        self.year = run.population_year
        if self.city is not None:
            self.population = get_population(self.city, self.year, run.population_variant, run.population_growth_pct)
            self.population_extrapolated = is_extrapolated(self.city, self.year)
            self.baseline_population = get_population(self.city, run.baseline_year, run.population_variant, 0)
            consumption = ConsumptionCapita.for_year(self.city, self.year)
            production = calculate_total_production_day(self.city) or 0
            self.production_m3_d = round(production, 1)
            self.extraction_Mm3_year = round((calculate_total_extraction(self.city) or 0) * 365 / 1e6, 3)
            if consumption is not None:
                self.consumption_L_d = consumption.consumption_capita_L_d
                self.consumption_year = consumption.year
                demand = demand_m3_d(self.consumption_L_d, self.population or 0)
                baseline = demand_m3_d(self.consumption_L_d, self.baseline_population or 0)
                self.demand_m3_d = round(demand, 1)
                self.baseline_demand_m3_d = round(baseline, 1)
                if production > 0 and demand > 0:
                    self.supply_security_pct = round(supply_security_pct(production, demand), 1)
                    self.service_time_hours = service_time_hours(production, demand)
                if production > 0 and baseline > 0:
                    self.baseline_supply_security_pct = round(supply_security_pct(production, baseline), 1)
        sources = list(run.freshwater.values_list("yield_Mm3_year", "baseline_yield_Mm3_year"))
        if sources:
            self.yield_Mm3_year = round(sum(y or 0 for y, _ in sources), 3)
            self.baseline_yield_Mm3_year = round(sum(b or 0 for _, b in sources), 3)
        self.last_updated = timezone.now()
        super().save(*args, **kwargs)


class ExtractionWater(models.Model):
    id=models.AutoField(primary_key=True)
    source = models.ForeignKey(AvailableFreshWater,
                               on_delete=models.DO_NOTHING, help_text="AvailableFreshWater ID from watersupply.AvailableFreshWater. Corresponds to the Balance Area", null=True)
    geom = models.PointField(srid=COORDINATE_SYSTEM)
    stationName = models.CharField(max_length=100, 
                                   help_text="Name of the extraction station or well")
    type = models.CharField(max_length=100,
                            choices=[('residential', 'Residential'), ('commercial', 'Commercial'), ('industrial', 'Industrial')],
                            help_text="Type of extraction (Residential, Commercial, Industrial)", default='residential')
    # --- Permit & Extraction ---
    permit_Mm3_yr = models.FloatField(
        null=True, blank=True,
        help_text="Maximum permitted extraction in Mm³/yr"
    )
    agreement_Mm3_yr = models.FloatField(
        null=True, blank=True,
        help_text="Agreed extraction in Mm³/yr"
    )
    current_extraction_Mm3_yr = models.FloatField(
        null=True, blank=True,
        help_text="Current actual extraction in Mm³/yr"
    )
    num_wells = models.IntegerField(
        null=True, blank=True,
        help_text="Number of individual wells at this station"
    )
    # --- Pump ---
    pumpflow_m3_s = models.FloatField(help_text="Pump flow in cubic meters per second", null=True, blank=True)
    pumpMaxFlow_m3_s = models.FloatField(help_text="Maximum pump flow in cubic meters per second", null=True, blank=True)
    OperationTime_h_day = models.FloatField(help_text="Operation time in hours per day", null=True, blank=True)
    depth_m = models.FloatField(help_text="Depth in meters", null=True, blank=True)
    pumpEfficiency = models.FloatField(help_text="Pump efficiency in percent", null=True, blank=True)
    pumpEnergyRate_kWh_h = models.FloatField(help_text="Pump energy rate in kilowatt-hours per hour", null=True, blank=True) 
    pumpEmissionRate_kg_CO2_h = models.FloatField(null=True, help_text="Pump emission rate in kilograms of CO2 per hour") # calculated in save() from the energy rate and emission factor
    pumpEmmissionFactor_kg_CO2_kWh = models.FloatField(null=True, help_text="Pump emission factor in kilograms of CO2 per kilowatt-hour")
    pumpEmission_day_kg_CO2 = models.FloatField(null=True, help_text="Pump emissions in kilograms of CO2 per day")
    pumpEmission_year_kg_CO2 = models.FloatField(null=True, help_text="Pump emissions in kilograms of CO2 per year")

    # --- Cost fields (per m³) ---
    opex_EUR_m3 = models.FloatField(
        null=True, blank=True,
        help_text="Total OPEX in EUR per m³ (labor+energy+chemicals+tax)"
    )
    labor_EUR_m3 = models.FloatField(null=True, blank=True)
    energy_EUR_m3 = models.FloatField(null=True, blank=True)
    chemicals_EUR_m3 = models.FloatField(null=True, blank=True)
    tax_EUR_m3 = models.FloatField(null=True, blank=True)

    # --- Environmental cost fields (per m³) ---
    co2_cost_EUR_m3 = models.FloatField(
        null=True, blank=True,
        help_text="CO₂ emission cost in EUR per m³"
    )
    drought_damage_EUR_m3 = models.FloatField(
        null=True, blank=True,
        help_text="Drought damage cost in EUR per m³"
    )

    # --- Ownership ---
    inside_property = models.BooleanField(
        default=True,
        help_text="Whether the well is on owned land"
    )

    # --- Active state (for scenarios) ---
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this well is currently active"
    )
    
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.source} - {self.stationName}"

    @staticmethod
    def volume_m3_d():
        """
        Database expression for a well's extracted volume in m3/day, the one
        definition used by the extraction indicator and TotalWaterProduction:
          1. the measured yearly extraction (current_extraction_Mm3_yr * 1e6 / 365),
          2. else pump flow x operation time (m3/s * h/day * 3600 s/h),
          3. else pump flow running all day (m3/s * 86400).
        NULL when none is known, so such a well adds nothing to a Sum.
        """
        return Coalesce(
            ExpressionWrapper(F('current_extraction_Mm3_yr') * 1e6 / 365.0, output_field=FloatField()),
            ExpressionWrapper(F('pumpflow_m3_s') * F('OperationTime_h_day') * 3600.0, output_field=FloatField()),
            ExpressionWrapper(F('pumpflow_m3_s') * 86400.0, output_field=FloatField()),
            output_field=FloatField(),
        )

    def save(self, *args, **kwargs):
        """
        DAG edges: Available_FW -> Total_Extraction
                   Total_Extraction -> Energy_Consumption / CO2_Emission
        Derived here: source (from location, only if not given), pump emissions,
        OPEX per m3, CO2 cost per m3 and drought damage per m3. OPEX and the two
        environmental costs are only calculated when not supplied explicitly.
        """
        # Some vendors report extraction as a negative flow (water leaving the
        # aquifer); store the magnitude so volumes, energy and costs stay positive.
        if self.pumpflow_m3_s is not None:
            self.pumpflow_m3_s = abs(self.pumpflow_m3_s)
        if self.pumpMaxFlow_m3_s is not None:
            self.pumpMaxFlow_m3_s = abs(self.pumpMaxFlow_m3_s)

        # Assign source from location only when none was given explicitly
        if self.source_id is None:
            source = AvailableFreshWater.objects.filter(
                geom__contains=self.geom.centroid
            ).first()
            if source is None:
                raise ValidationError(
                    "No AvailableFreshWater contains this location and no source was given."
                )
            self.source = source

        # Emissions (kg CO2) from pump energy rate x emission factor
        if self.pumpEnergyRate_kWh_h is not None and self.pumpEmmissionFactor_kg_CO2_kWh is not None:
            self.pumpEmissionRate_kg_CO2_h = self.pumpEnergyRate_kWh_h * self.pumpEmmissionFactor_kg_CO2_kWh
            if self.OperationTime_h_day is not None:
                self.pumpEmission_day_kg_CO2 = self.pumpEmissionRate_kg_CO2_h * self.OperationTime_h_day
                self.pumpEmission_year_kg_CO2 = self.pumpEmission_day_kg_CO2 * 365
            else:
                self.pumpEmission_day_kg_CO2 = self.pumpEmission_year_kg_CO2 = None
        else:
            self.pumpEmissionRate_kg_CO2_h = None
            self.pumpEmission_day_kg_CO2 = None
            self.pumpEmission_year_kg_CO2 = None

        # OPEX per m3 = labor + energy + chemicals + tax (missing parts count as 0,
        # but leave it unset if none of them is known)
        if self.opex_EUR_m3 is None:
            parts = [self.labor_EUR_m3, self.energy_EUR_m3, self.chemicals_EUR_m3, self.tax_EUR_m3]
            if any(p is not None for p in parts):
                self.opex_EUR_m3 = sum(p or 0 for p in parts)

        # Environmental costs come from the latest EnvironmentalCosts record
        costs = EnvironmentalCosts.current()
        volume_m3_day = self.pumpflow_m3_s * self.OperationTime_h_day * 3600 if self.pumpflow_m3_s is not None and self.OperationTime_h_day is not None else None

        # CO2 cost per m3 = (kg CO2 per day / m3 per day) * EUR per kg CO2
        if self.co2_cost_EUR_m3 is None and costs and self.pumpEmission_day_kg_CO2 is not None and volume_m3_day:
            self.co2_cost_EUR_m3 = self.pumpEmission_day_kg_CO2 / volume_m3_day * costs.price_EUR_kg_CO2

        # Drought damage is already priced per m3
        if self.drought_damage_EUR_m3 is None and costs:
            self.drought_damage_EUR_m3 = costs.price_EUR_droughtDamage_m3

        self.last_updated = timezone.now()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Extraction Water"
        verbose_name_plural = "Extraction Water"

class ImportedWater(models.Model):
    id=models.AutoField(primary_key=True)
    sourceName = models.CharField(max_length=100, help_text="Name of the imported water source")
    quantity_m3_d = models.FloatField(help_text="Quantity in cubic meters per day")
    price_EUR_m3 = models.FloatField(help_text="Price in EUR per cubic meter")
    is_active = models.BooleanField(default=True)
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.sourceName} - {self.quantity_m3_d} m3/d"

    class Meta:
        verbose_name = "Imported Water"
        verbose_name_plural = "Imported Water"
    
class WaterTreatment(models.Model):
    id = models.AutoField(primary_key=True)
    year = models.IntegerField()
    UnitaryOPEX_EUR_m3 = models.FloatField(help_text="Unitary OPEX in EUR per cubic meter")
    treatment_efficiency = models.FloatField(help_text="Treatment efficiency in percent")
    samplesWaterQuality_OK = models.IntegerField(help_text="Number of samples with OK water quality")
    samplesWaterQualityTaken = models.IntegerField(help_text="Total number of samples taken")
    EnergyConsumption_MW_day = models.FloatField(help_text="Energy consumption in megawatt-hours per day")
    acceptanceRate = models.FloatField(help_text="User Acceptance rate in percent")
    geom = models.MultiPointField(srid=COORDINATE_SYSTEM)
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Treatement - {self.year}: Accepatance rate: {self.acceptanceRate} %"
    
    class Meta:
        verbose_name = "Water Treatment"
        verbose_name_plural = "Water Treatment Records"

class PipeNetwork(models.Model):
    id = models.AutoField(primary_key=True)
    length_km = models.FloatField(help_text="in kilometers")
    diameter_mm = models.FloatField(help_text="Pipe diameter in millimeters", null=True, blank=True)
    diameter_in = models.FloatField(help_text="Pipe diameter in inches", null=True, blank=True)      
    geom = models.MultiLineStringField(srid=COORDINATE_SYSTEM)
    maitenanceCost_EUR_km = models.FloatField(null=True, help_text="in EUR per kilometer")
    origin = models.ForeignKey(ExtractionWater, on_delete=models.DO_NOTHING, help_text="ExtractionWater ID from watersupply.ExtractionWater", null=True) # type: ignore
    destination = models.ForeignKey(UsersLocation, on_delete=models.DO_NOTHING, help_text="UsersLocation ID from watersupply.UsersLocation", null=True) # type: ignore
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Pipe {self.id}: {self.length_km or 0:.2f} km"
    
    def save(self, *args, **kwargs):
        self.length_km = self.geom.length / 1000
        if self.diameter_mm is not None: self.diameter_in = self.diameter_mm / 25.4
        if self.diameter_in is not None: self.diameter_mm = self.diameter_in * 25.4
        super().save(*args, **kwargs)
        
        
    class Meta:
        verbose_name = "Pipe Network"
        verbose_name_plural = "Pipe Networks"
        
        constraints = [
            models.UniqueConstraint(fields=['origin', 'destination'], name='unique_pipe_network')
        ]

class CoverageWaterSupply(models.Model):
    id = models.AutoField(primary_key=True)
    city = models.ForeignKey(City, on_delete=models.DO_NOTHING, null=True, help_text="City code from administrative.City")
    year = models.IntegerField()
    buffer_m = models.FloatField(default=50, help_text="Buffer distance around pipes in meters")
    avg_pressure_m = models.FloatField(
        default=30.0,
        help_text="Average operating pressure of the city's network in m (editable; "
                  "default chain.DEFAULT_PRESSURE_M). Feeds the UARL of LeakageIndex")
    coveredArea_km2 = models.FloatField(help_text="Covered area in square kilometers")
    households_covered = models.IntegerField(default=0, help_text="Number of households within the service area")
    households_total = models.IntegerField(default=0, help_text="Total households in the city")
    population_served = models.IntegerField(null=True, blank=True, help_text="Water users (residents) within buffer_m of the network: Σ UsersLocation.populationServed of the city")
    population_total = models.IntegerField(null=True, blank=True, help_text="Water users (residents) of the city: Σ UsersLocation.usersTotal")
    coveragePCT = models.FloatField(help_text="Coverage of users in percentage")
    urban_area_km2 = models.FloatField(null=True, blank=True, editable=False,
                                       help_text="Urban land cover of the city (classes of the neighborhoods' urban_area) of urban_landcover_year")
    uncovered_urban_km2 = models.FloatField(null=True, blank=True, editable=False,
                                            help_text="Urban land cover outside the service area (geom): where the network has not followed urban growth")
    uncovered_urban_pct = models.FloatField(null=True, blank=True, editable=False,
                                            help_text="uncovered_urban_km2 / urban_area_km2 x 100")
    urban_landcover_year = models.IntegerField(null=True, blank=True, editable=False,
                                               help_text="Land-cover year used: the latest up to the record's year, else the earliest later one")
    geom = models.MultiPolygonField(srid=COORDINATE_SYSTEM, null=True, blank=True,
                                    help_text="Dissolved buffer polygon around pipe network")
    last_updated = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        """
        DAG edges: Network -> Coverage_WS_Area (dissolved buffer of the pipes)
                   NumberUsers -> Coverage_WS  (Σ populationServed / Σ usersTotal
                   of the city's derived UsersLocations; those follow the city's
                   latest record's buffer_m)
                   CityArea -> Network (partial: the city's urban land cover outside
                   the service area is flagged, uncovered_urban_km2; the network
                   itself is not extended)
        """
        from django.contrib.gis.geos import MultiPolygon
        from django.contrib.gis.db.models import Union

        # 1. Buffer all pipes in this city and dissolve overlaps
        pipes = PipeNetwork.objects.filter(
            destination__neighborhood__district__city=self.city
        )
        if not pipes.exists():
            # Fallback: use all pipes whose geometry intersects the city
            pipes = PipeNetwork.objects.filter(geom__intersects=self.city.geom)

        if pipes.exists():
            # Buffer each pipe and union into a single geometry
            dissolved = (
                pipes.aggregate(union=Union('geom'))['union']
            )
            if dissolved:
                dissolved = dissolved.buffer(self.buffer_m)
                # Ensure MultiPolygon
                if dissolved.geom_type == 'Polygon':
                    dissolved = MultiPolygon(dissolved, srid=dissolved.srid)
                self.geom = dissolved
                self.coveredArea_km2 = round(dissolved.area / 1e6, 4)
            else:
                self.geom = None
                self.coveredArea_km2 = 0
        else:
            self.geom = None
            self.coveredArea_km2 = 0

        # 2. Users inside the service area. Derived users locations (buffer_m
        #    set) hold the residents of the city's properties; the households
        #    are its dwellings, counted with this record's buffer.
        city_neighborhoods = Neighborhood.objects.filter(
            district__city=self.city
        )
        derived = UsersLocation.objects.filter(
            neighborhood__in=city_neighborhoods, buffer_m__isnull=False)
        if derived.exists():
            from .calculations.chain import coverage_pct
            from .calculations.users import neighborhood_users

            agg = derived.aggregate(total=Sum('usersTotal'), served=Sum('populationServed'))
            self.population_total = agg['total'] or 0
            self.population_served = agg['served'] or 0
            self.coveragePCT = coverage_pct(self.population_served, self.population_total)
            counts = neighborhood_users(
                list(city_neighborhoods.values_list('pk', flat=True)), self.buffer_m).values()
            self.households_total = sum(c.dwellings for c in counts)
            self.households_covered = sum(c.dwellings_served for c in counts)
            self._set_urban_gap()
            self.last_updated = timezone.now()
            super().save(*args, **kwargs)
            return

        # Legacy: users locations with stored counts only
        self.population_total = self.population_served = None

        # Total households: sum usersTotal from all UsersLocations in city
        self.households_total = (
            UsersLocation.objects.filter(neighborhood__in=city_neighborhoods)
            .aggregate(total=Sum('usersTotal'))['total'] or 0
        )

        # Covered households: only neighborhoods intersecting the buffer
        if self.geom:
            covered_neighborhoods = city_neighborhoods.filter(
                geom__intersects=self.geom
            )
            self.households_covered = (
                UsersLocation.objects.filter(neighborhood__in=covered_neighborhoods)
                .aggregate(total=Sum('usersTotal'))['total'] or 0
            )
        else:
            self.households_covered = 0

        # 3. Coverage percentage
        if self.households_total > 0:
            self.coveragePCT = round(
                self.households_covered / self.households_total * 100, 1
            )
        else:
            self.coveragePCT = 0

        self._set_urban_gap()
        self.last_updated = timezone.now()
        super().save(*args, **kwargs)

    def _set_urban_gap(self):
        """
        DAG edge: CityArea -> Network. Urban land cover outside the service
        area (watersupply/calculations/network_gap.py). Without land cover
        the fields stay empty.
        """
        from .calculations.chain import share_pct
        from .calculations.network_gap import urban_gap

        gap = urban_gap(self.city_id, self.year, self.geom) if self.city_id else None
        if gap is None:
            self.urban_landcover_year = self.urban_area_km2 = None
            self.uncovered_urban_km2 = self.uncovered_urban_pct = None
            return
        self.urban_landcover_year = gap.landcover_year
        self.urban_area_km2 = gap.urban_km2
        self.uncovered_urban_km2 = gap.uncovered_km2
        self.uncovered_urban_pct = share_pct(gap.uncovered_km2, gap.urban_km2)

    def __str__(self):
        return f"{self.city} - covered area: {self.coveredArea_km2} km2. Coverage: {self.coveragePCT} %"

    class Meta:
        verbose_name = "Coverage Water Supply"
        verbose_name_plural = "Coverage Water Supply Records"

class NonRevenueWater(models.Model):
    class LossesTypes(models.TextChoices):
        Apparent = 'A','Apparent'
        Real = 'R', 'Real'

    APPARENT_CHOICES = ['CM', 'UA', 'DE', 'OT']
    REAL_CHOICES     = ['LP', 'LS', 'LM', 'OT']

    class LossesChoices(models.TextChoices):
        ConsumerMeter = 'CM','Meter Innacurracy'
        Unauthorized = 'UA', 'Unathorized consumption'
        DataHandle = 'DE','Data Handling errors'
        Other = 'OT','Other'
        lMains = 'LP','Leakage on Mains'
        lStorage = 'LS','Leakage and overflows at storage'
        lMeters = 'LM','Leakage at meter connection'

    id = models.AutoField(primary_key=True)
    year = models.IntegerField()
    type = models.CharField(max_length=100,
                            choices=LossesTypes.choices,
                            default=LossesTypes.Apparent, help_text="Type of loss (Real or Apparent)")
    specificLoss = models.CharField(max_length=100,
                            choices=LossesChoices.choices,
                            default=LossesChoices.ConsumerMeter , help_text="Specific loss category")
    loss_Quantity_m3 = models.FloatField(help_text="Loss quantity in cubic meters per day")
    WaterCost_EUR_day = models.FloatField(help_text="Water cost in EUR per day")
    UnavoidableLossses_PCT = models.FloatField(help_text="Unavoidable losses in percentage (record data only; the ILI uses the IWA UARL of LeakageIndex)")
    # DAG edge: Network -> Real_Losses. Nullable only for records created before the link.
    pipe = models.ForeignKey(PipeNetwork, on_delete=models.DO_NOTHING, null=True, blank=True,
                             related_name='losses',
                             help_text="Pipe where the real loss (leakage) is presumed to occur")
    last_updated = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        # Auto-assign loss type from specificLoss. The ILI of the year is
        # LeakageIndex (watersupply/signals.py re-saves it after this save).
        if self.specificLoss in self.REAL_CHOICES:
            self.type = self.LossesTypes.Real
        else:
            self.type = self.LossesTypes.Apparent

        self.last_updated = timezone.now()
        super().save(*args, **kwargs)

    def clean(self):
        valid_types = {
            'A': self.APPARENT_CHOICES,
            'R': self.REAL_CHOICES,
        }

        if self.type in valid_types and self.specificLoss not in valid_types[self.type]:
            raise ValidationError("Invalid loss specification for this loss type.")

        # save() derives type from specificLoss, so judge the pipe by specificLoss too
        is_real = self.specificLoss in self.REAL_CHOICES
        if is_real and self.pipe_id is None:
            raise ValidationError({'pipe': "Real losses must be linked to the pipe where the leakage is presumed."})
        if not is_real and self.pipe_id is not None:
            raise ValidationError({'pipe': "Apparent losses are not physical leakage and cannot be linked to a pipe."})

    def __str__(self):
        return f"{self.year}: Losses: {self.type} - {self.specificLoss} - {self.loss_Quantity_m3} m3"

    class Meta:
        verbose_name = "Non Revenue Water"
        verbose_name_plural = "Non Revenue Water Records"

    @staticmethod
    def generate_random_event(year, water_cost_m3=0.50):
        """
        Create a random NonRevenueWater loss event.
        Picks a random LossesChoices, assigns a plausible quantity
        and unavoidable percentage, then saves. Real losses are placed on a
        random pipe (none if the network is empty).
        """
        import random

        # Profiles: (specificLoss, quantity range m3/day, unavoidable %)
        profiles = {
            'CM': (50, 300, 60),     # Meter inaccuracy: moderate volume, high unavoidable
            'UA': (20, 200, 10),     # Unauthorized: moderate, low unavoidable
            'DE': (10, 100, 30),     # Data handling: low volume
            'LP': (100, 2000, 25),   # Leakage mains: high volume
            'LS': (50, 500, 20),     # Leakage storage: medium
            'LM': (30, 400, 15),     # Leakage meters: medium
            'OT': (10, 150, 40),     # Other
        }

        choice = random.choice(list(profiles.keys()))
        q_min, q_max, unavoidable_pct = profiles[choice]
        quantity = round(random.uniform(q_min, q_max), 1)

        event = NonRevenueWater(
            year=year,
            specificLoss=choice,
            loss_Quantity_m3=quantity,
            WaterCost_EUR_day=round(quantity * water_cost_m3, 2),
            UnavoidableLossses_PCT=unavoidable_pct,
            pipe=PipeNetwork.objects.order_by('?').first() if choice in NonRevenueWater.REAL_CHOICES else None,
        )
        event.save()
        return event
    
class LeakageIndex(models.Model):
    """
    Infrastructure Leakage Index of the whole network for one year (IWA):
    ILI = CARL / UARL. CARL = the year's real losses (NonRevenueWater type R);
    UARL = Σ per city (18 Lm + 0.8 Nc + 25 Lp) x P (Lambert et al. 1999), with
    each city's editable pressure (CoverageWaterSupply.avg_pressure_m), mains
    length and connections (calculations/leakage.py). Apparent losses are no
    leakage and do not enter it. The inputs used are stored with the result.
    """
    year = models.IntegerField(unique=True)
    private_pipe_m_per_conn = models.FloatField(
        default=5.0, help_text="Private pipe from property boundary to meter, m per connection "
                               "(editable; default chain.DEFAULT_PRIVATE_PIPE_M)")
    mains_km = models.FloatField(null=True, blank=True, editable=False, help_text="Lm: mains length (km)")
    connections = models.IntegerField(null=True, blank=True, editable=False,
                                      help_text="Nc: service connections (dwellings within the service buffer)")
    pressure_m = models.FloatField(null=True, blank=True, editable=False,
                                   help_text="P: mean of the cities' avg_pressure_m, weighted by Lm + Nc (m)")
    city_inputs = models.JSONField(default=list, blank=True, editable=False,
                                   help_text="Per city: coverage year, Lm, Nc, P and UARL used")
    carl_m3_d = models.FloatField(null=True, blank=True, editable=False,
                                  help_text="CARL: current annual real losses (m³/day)")
    uarl_m3_d = models.FloatField(null=True, blank=True, editable=False,
                                  help_text="UARL: unavoidable annual real losses (m³/day)")
    uarl_reliable = models.BooleanField(default=False, editable=False,
                                        help_text="Nc ≥ 3000, ≥ 20 connections/km and P ≥ 25 m (Lambert & McKenzie 2002)")
    ILI = models.FloatField(null=True, blank=True, editable=False, help_text="Infrastructure Leakage Index")
    last_updated = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        """
        DAG edges: Real_Losses -> ILI (CARL), Network -> ILI (UARL from the mains
                   length, connections and pressure per city)

        Without pipes or connections the stored UARL and ILI are kept (no
        zero is written); without real-loss records CARL and ILI are empty.
        """
        from .calculations import chain, leakage

        carl = (NonRevenueWater.objects.filter(year=self.year, type=NonRevenueWater.LossesTypes.Real)
                .aggregate(total=Sum('loss_Quantity_m3'))['total'])
        self.carl_m3_d = carl
        parts = leakage.network_parts(self.year, self.private_pipe_m_per_conn)
        totals = leakage.combine(parts)
        if totals['mains_km'] > 0 and totals['connections'] > 0:
            self.city_inputs = parts
            self.mains_km = totals['mains_km']
            self.connections = totals['connections']
            self.pressure_m = totals['pressure_m']
            self.uarl_m3_d = round(totals['uarl_m3_d'], 3)
            self.uarl_reliable = totals['reliable']
        self.ILI = chain.ili(carl, self.uarl_m3_d) if carl is not None else None
        self.last_updated = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"ILI {self.year}: {self.ILI}"

    class Meta:
        verbose_name = "Leakage Index (ILI)"
        verbose_name_plural = "Leakage Index (ILI) Records"


class OPEX(models.Model):
    id = models.AutoField(primary_key=True)
    year = models.IntegerField(help_text="Year of operation")
    UnitaryOPEX_EUR_m3 = models.FloatField(help_text="Unitary OPEX in EUR per cubic meter")
    totalOPEX_EUR = models.FloatField(help_text="Total OPEX in EUR")
    OPEX_recovered_EUR = models.FloatField(null=True, help_text="OPEX recovered in EUR")
    OPEX_recovered_PCT = models.FloatField(null=True, help_text="OPEX recovered in percent")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.year}: {self.UnitaryOPEX_EUR_m3} EUR/m3"
    
    def save(self, *args, **kwargs):
        """
        DAG edges: Total_Extraction/Total_Water_Prod -> OPEX
                   Energy_Consumption -> OPEX
                   Imported_Water -> OPEX, WT_Cost -> OPEX, Network -> OPEX
                   Metered_Res_Water -> OPEX_Recovery
        totalOPEX_EUR = extraction (opex/m3 x current extraction; for a well
                        with pump energy data its energy_EUR_m3 share is left out)
                      + pumping energy (pump kWh/day x 365 x the electricity
                        price of the well's province in this record's year,
                        chain.energy_cost_EUR_yr)
                      + imported water (quantity x price)
                      + treatment (mean UnitaryOPEX of that year x volume produced)
                      + network maintenance (EUR/km x length)
        The derived energy cost replaces the stored per-m3 energy share, so a
        supplied opex_EUR_m3 without energy_EUR_m3 is read as excluding energy.
        Treatment energy (WaterTreatment.EnergyConsumption_MW_day) is not priced
        here: it is taken to be inside the treatment UnitaryOPEX.
        The inputs (ExtractionWater, ImportedWater, PipeNetwork, MeteredResidential)
        have no year, so they are read as the current state; treatment and the
        electricity price are filtered by this record's year. If no cost data
        exists at all the supplied totalOPEX_EUR / UnitaryOPEX_EUR_m3 are kept.
        """
        from Energy.models import ElectricityCost
        from watersupply.calculations.chain import energy_cost_EUR_yr

        wells = ExtractionWater.objects.filter(is_active=True)
        pumped = Q(pumpEnergyRate_kWh_h__isnull=False, OperationTime_h_day__isnull=False)
        volume_m3_yr_expr = F('current_extraction_Mm3_yr') * 1e6
        extraction = wells.aggregate(
            cost=Sum(Case(
                When(pumped, then=ExpressionWrapper(
                    (Coalesce(F('opex_EUR_m3'), Value(0.0)) - Coalesce(F('energy_EUR_m3'), Value(0.0)))
                    * volume_m3_yr_expr, output_field=FloatField())),
                default=ExpressionWrapper(F('opex_EUR_m3') * volume_m3_yr_expr, output_field=FloatField()),
                output_field=FloatField(),
            )),
            volume=Sum(ExpressionWrapper(volume_m3_yr_expr, output_field=FloatField())),
        )
        # Pump energy per province (the electricity price is set per province)
        energy_by_province = (
            wells.filter(pumped)
            .annotate(province_id=Subquery(
                Province.objects.filter(geom__contains=OuterRef('geom')).values('pk')[:1]))
            .values('province_id')
            .annotate(kwh_day=Sum(ExpressionWrapper(
                F('pumpEnergyRate_kWh_h') * F('OperationTime_h_day'), output_field=FloatField())))
        )
        energy_cost = sum(
            energy_cost_EUR_yr(row['kwh_day'] or 0, ElectricityCost.price(
                row['province_id'], self.year, DEFAULT_ELECTRICITY_EUR_KWH))
            for row in energy_by_province
        )
        imported = ImportedWater.objects.filter(is_active=True).aggregate(
            cost=Sum(ExpressionWrapper(
                F('quantity_m3_d') * 365.0 * F('price_EUR_m3'), output_field=FloatField())),
            volume=Sum(ExpressionWrapper(
                F('quantity_m3_d') * 365.0, output_field=FloatField())),
        )
        volume_m3_yr = (extraction['volume'] or 0) + (imported['volume'] or 0)

        treatment_unit = WaterTreatment.objects.filter(year=self.year).aggregate(
            avg=models.Avg('UnitaryOPEX_EUR_m3'))['avg'] or 0
        network_maintenance = PipeNetwork.objects.aggregate(
            cost=Sum(ExpressionWrapper(
                F('maitenanceCost_EUR_km') * F('length_km'), output_field=FloatField())),
        )['cost'] or 0

        total = (
            (extraction['cost'] or 0) + energy_cost + (imported['cost'] or 0)
            + treatment_unit * volume_m3_yr + network_maintenance
        )
        if total > 0:
            self.totalOPEX_EUR = total
            self.UnitaryOPEX_EUR_m3 = total / volume_m3_yr if volume_m3_yr else 0

        self.OPEX_recovered_EUR = MeteredResidential.objects.aggregate(
            total=Sum('Recovery_EUR'))['total']
        if self.OPEX_recovered_EUR and self.totalOPEX_EUR:
            self.OPEX_recovered_PCT = self.OPEX_recovered_EUR / self.totalOPEX_EUR * 100
        else:
            self.OPEX_recovered_PCT = None

        self.last_updated = timezone.now()
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "OPEX"
        verbose_name_plural = "OPEX Records"

class AreaAffectedDrought(models.Model):
    class SensibilityChoices(models.IntegerChoices):
        NotAffected = 0, 'Not Affected'
        VeryLow = 1, 'Very Low'
        Low = 2, 'Low'
        Medium = 3, 'Medium'
        High = 4, 'High'
        VeryHigh = 5, 'Very High'
    
    id = models.AutoField(primary_key=True)
    geom = models.MultiPolygonField(srid=COORDINATE_SYSTEM)
    Province = models.ForeignKey(Province, on_delete=models.DO_NOTHING)
    areaName = models.CharField(max_length=100)
    sourceID = models.CharField(max_length=100, unique=True, null=True, blank=True, help_text="Feature id in the source dataset (e.g. the Klimaateffectatlas WFS), the upsert key of re-imports")
    SensibilityLevel = models.IntegerField(
        choices=SensibilityChoices.choices,
        default=SensibilityChoices.NotAffected,
        help_text="Sensibility level to drought"
                                           )
    year = models.IntegerField()
    areaAffected_km2 = models.FloatField(help_text="Area affected in square kilometers")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.year}: {self.areaAffected_km2} km2"

    def save(self, *args, **kwargs):
        """Derived from the geometry: affected area (km2) and, if not given, the Province."""
        self.areaAffected_km2 = self.geom.area / 1e6
        if self.Province_id is None:
            province = Province.objects.filter(geom__contains=self.geom.centroid).first()
            if province is None:
                raise ValidationError("No Province contains this area and none was given.")
            self.Province = province
        self.last_updated = timezone.now()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Area Affected by Drought"
        verbose_name_plural = "Area Affected by Drought Records"
    
class TotalWaterProduction(models.Model):
    id = models.AutoField(primary_key=True)
    source = models.ManyToManyField(AvailableFreshWater,
                               help_text="AvailableFreshWater ID from watersupply.AvailableFreshWater") #TODO: What if the source is imported or multiple sources?
    imported_boolean = models.BooleanField(default=False, help_text="Are there imported sources?")
    source_imported = models.ManyToManyField(ImportedWater, blank=True, help_text="ImportedFreshWater ID from watersupply.ImportedFreshWater")
    year = models.IntegerField()
    productionDay = models.FloatField( help_text="in Million cubic meters per day") # Mm3/day
    productionYR = models.FloatField(null=True, help_text="in Million cubic meters per year")  # Mm3/year
    costDay = models.FloatField(null=True, help_text="in EUR per day")
    costYR = models.FloatField(null=True, help_text="in EUR per year")  # EUR/year
    last_updated = models.DateTimeField(default=timezone.now)

    # Used when no ElectricityCost record exists for the source's province/year.
    DEFAULT_ELECTRICITY_EUR_KWH = DEFAULT_ELECTRICITY_EUR_KWH

    def __str__(self):
        return f"Production {self.year}: {self.productionDay} Mm3/day"

    def calculate(self):
        """
        Set productionDay/YR (Mm3) and costDay/YR (EUR) from the active wells of
        the linked sources plus the linked imported water.

        DAG edges: Total_Extraction -> Total_Water_Prod
                   Imported_Water   -> Total_Water_Prod
                   Energy_Cost      -> Energy_Consumption
        Many-to-many links only exist once the row is saved, so on the very first
        save (no pk yet) production is 0 until the sources are attached; the
        m2m_changed signal in signals.py then calls save() again.
        """
        from Energy.models import ElectricityCost

        if not self.pk:
            self.productionDay = self.productionDay or 0.0
            self.productionYR = self.productionDay * 365
            return

        sources = self.source.all()
        wells = ExtractionWater.objects.filter(is_active=True, source__in=sources)
        extraction = wells.aggregate(
            m3_day=Sum(ExtractionWater.volume_m3_d()),
            kwh_day=Sum(ExpressionWrapper(
                F('pumpEnergyRate_kWh_h') * F('OperationTime_h_day'),
                output_field=FloatField())),
        )

        imported = {'m3_day': 0, 'cost_day': 0}
        if self.imported_boolean:
            agg = self.source_imported.filter(is_active=True).aggregate(
                m3_day=Sum('quantity_m3_d'),
                cost_day=Sum(ExpressionWrapper(
                    F('quantity_m3_d') * F('price_EUR_m3'), output_field=FloatField())),
            )
            imported = {k: v or 0 for k, v in agg.items()}

        # Electricity price: province of the first linked source, for this year
        first_source = sources.first()
        province_id = None
        if first_source is not None:
            province_id = Province.objects.filter(
                geom__contains=first_source.geom.centroid).values_list('pk', flat=True).first()
        elec_cost = ElectricityCost.price(province_id, self.year, self.DEFAULT_ELECTRICITY_EUR_KWH)

        self.productionDay = ((extraction['m3_day'] or 0) + imported['m3_day']) / 1e6  # Mm3/day
        self.productionYR = self.productionDay * 365
        self.costDay = (extraction['kwh_day'] or 0) * elec_cost + imported['cost_day']
        self.costYR = self.costDay * 365

    def save(self, *args, **kwargs):
        self.calculate()
        self.last_updated = timezone.now()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Total Water Production"
        verbose_name_plural = "Total Water Production Records"