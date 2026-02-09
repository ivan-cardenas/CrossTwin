from django.contrib.gis.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from common.models import Region, City, Neighborhood
from django.conf import settings

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


# Create your models here.
class ConsumptionCapita(models.Model):
    id=models.AutoField(primary_key=True)
    city = models.ForeignKey(City, on_delete=models.CASCADE, help_text="City code from common.City")
    year = models.IntegerField()
    consumption_capita_L_d = models.FloatField( help_text="in liters per person per day") # L/person/day
    total_consumption_m3_yr = models.FloatField( help_text="in cubic meters per year", null=True, blank=True)  # m3/year
    last_updated = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        if self.consumption_capita_L_d < 0:
            raise ValidationError("Consumption Capita cannot be negative")
        self.total_consumption_m3_yr = (self.consumption_capita_L_d * 365 * 1000 * self.city.currentPopulation)
        super().save(**args, **kwargs)
        

    def __str__(self):
        return f"{self.city} - {self.year}: {self.consumption_capita_L_d} L/person/day"
    
    class Meta:
        verbose_name = "Consumption Capita"
        verbose_name_plural = "Consumption Capita"
    
class TotalWaterDemand(models.Model):
    city = models.ForeignKey(City, on_delete=models.CASCADE , help_text="City code from common.City")
    year = models.IntegerField()
    demandDay = models.FloatField( help_text="in Million cubic meters per day") # Mm3/day
    demandYR = models.FloatField(null=True, help_text="in Million cubic meters per year")  # Mm3/year
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.city} - {self.year}: {self.demandDay} Mm3/day"
    
    def save(self, *args, **kwargs):
        self.demandYR = self.demandDay * 365
        super().save(**args, **kwargs)
        
    class Meta:
        verbose_name = "Total Water Demand"
        verbose_name_plural = "Total Water Demand Records"
    
class SupplySecurity(models.Model):
    city = models.ForeignKey(City, on_delete=models.CASCADE, help_text="City code from common.City")
    year = models.IntegerField()
    supply_security_pct = models.FloatField(help_text="in percent")   # %
    security_goal_pct = models.FloatField(help_text="in percent") # %
    service_time_hours = models.FloatField(help_text="in hours per day") # hours/day
    last_updated = models.DateTimeField(default=timezone.now) 
    
    def __str__(self):
        return f"{self.region} - {self.year}: {self.supply_security}"
    
    class Meta:
        verbose_name = "Supply Security"
        verbose_name_plural = "Supply Security Records"
    
class PipeNetwork(models.Model):
    id = models.AutoField(primary_key=True)
    length_km = models.FloatField(help_text="in kilometers") # km
    geom = models.MultiLineStringField(srid=COORDINATE_SYSTEM)
    maitenanceCost_EUR_km = models.FloatField(null=True, help_text="in EUR per kilometer") # TODO: check if units are EUR or M.U.
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.length_km} km"   
    
    class Meta:
        verbose_name = "Pipe Network"
        verbose_name_plural = "Pipe Networks"
    
class UsersLocation(models.Model):
    id = models.AutoField(primary_key=True)
    neighborhood = models.ForeignKey(Neighborhood, on_delete=models.DO_NOTHING, help_text="Neighborhood code from common.Neighborhood") #TODO: Change to City or make per point?
    usersTotal = models.IntegerField(help_text="Total number of users in the neighborhood")
    ResidentialUsers = models.IntegerField(null=True, help_text="Number of residential users")
    CommercialUsers = models.IntegerField(null=True, help_text="Number of commercial users")
    IndustrialUsers = models.IntegerField(null=True, help_text="Number of industrial users")
    populationServed = models.IntegerField(null=True, help_text="Population served in the neighborhood")
    last_updated = models.DateTimeField(default=timezone.now)
    def __str__(self):
        return f"{self.neighborhood} - {self.usersTotal} users"
    
    class Meta:
        verbose_name = "Users Location"
        verbose_name_plural = "Users Locations"
    
class MeteredResidential(models.Model):
    id = models.AutoField(primary_key=True)
    userLocation = models.ForeignKey(UsersLocation, on_delete=models.DO_NOTHING, help_text="UsersLocation ID from common.UsersLocation")
    installed_meters = models.IntegerField(help_text="Number of installed meters")
    functional_meters = models.IntegerField(help_text="Number of functional meters")
    collected_meters = models.IntegerField(help_text="Number of collected meters")
    userTariff_EUR_m3 = models.FloatField(help_text="in EUR per cubic meter")
    userAffordability_PCT = models.FloatField(help_text="in percent")
    Recovery_EUR = models.FloatField(help_text="in EUR")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.user.neighborhood} - {self.installed_meters} installed meters. {self.Recovery_EUR} EUR recovered"
    
    class Meta:
        verbose_name = "Metered Residential"
        verbose_name_plural = "Metered Residential"
    
    
class AvailableFreshWater(models.Model):
    id=models.AutoField(primary_key=True)
    SourceName = models.CharField(max_length=100, help_text="Name of the water source")
    region = models.ForeignKey(Region, on_delete=models.DO_NOTHING, null=True, help_text="Region code from common.Region. Get automatically assigned on save.")
    geom = models.MultiPolygonField(srid=COORDINATE_SYSTEM)
    infiltrationRate_cm_h = models.FloatField(help_text="Infiltration rate in centimeters per hour") #TODO: this should be calculated from land cover and soil type
    infiltrationDepth_cm = models.FloatField(help_text="Infiltration depth in centimeters")
    totalQuantity_Mm3 = models.FloatField(help_text="total quantity in million cubic meters")
    yield_Mm3_year = models.FloatField(help_text="Yield in million cubic meters per year")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.SourceName} - {self.totalQuantity_Mm3} Mm3"
    
    def save(self, *args, **kwargs):
        region = Region.objects.get(geom__contains=self.geom.centroid)
        self.region = region
        super().save(**args, **kwargs)
        
    class Meta:
        verbose_name = "Available Fresh Water"
        verbose_name_plural = "Available Fresh Water"
    
class ExtractionWater(models.Model):
    id=models.AutoField(primary_key=True)
    source = models.ForeignKey(AvailableFreshWater,
                               on_delete=models.DO_NOTHING, help_text="AvailableFreshWater ID from watersupply.AvailableFreshWater. Get automatically assigned on save.")
    geom = models.MultiPointField(srid=COORDINATE_SYSTEM)
    stationName = models.CharField(max_length=100, help_text="Name of the extraction station")
    pumpflow_m3_s = models.FloatField(help_text="Pump flow in cubic meters per second")
    pumpMaxFlow_m3_s = models.FloatField(help_text="Maximum pump flow in cubic meters per second")
    OperationTime_h_day = models.FloatField(help_text="Operation time in hours per day")
    depth_m = models.FloatField(help_text="Depth in meters")
    pumpEfficiency = models.FloatField(help_text="Pump efficiency in percent")
    pumpEnergyRate_kWh_h = models.FloatField(help_text="Pump energy rate in kilowatt-hours per hour")
    pumpEmissionRate_kg_CO2_h = models.FloatField(null=True, help_text="Pump emission rate in kilograms of CO2 per hour") #TODO: This should be calculated from the energy rate and the electricity emission factor
    pumpEmmissionFactor_kg_CO2_kWh = models.FloatField(null=True, help_text="Pump emission factor in kilograms of CO2 per kilowatt-hour")
    pumpEmission_day_kg_CO2 = models.FloatField(null=True, help_text="Pump emissions in kilograms of CO2 per day")
    pumpEmission_year_kg_CO2 = models.FloatField(null=True, help_text="Pump emissions in kilograms of CO2 per year")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.source} - {self.stationName}"
    
    def save(self, *args, **kwargs):
        # Assign source based on location
        source = AvailableFreshWater.objects.get(geom__contains=self.geom.centroid)
        self.source = source
        
        # Calculate emissions if factors are provided
        if self.pumpEnergyRate_kWh_h is not None and self.pumpEmmissionFactor_kg_CO2_kWh is not None:
            self.pumpEmissionRate_kg_CO2_h = self.pumpEnergyRate_kWh_h * self.pumpEmmissionFactor_kg_CO2_kWh
            self.pumpEmission_day_kg_CO2 = self.pumpEmissionRate_kg_CO2_h * self.OperationTime_h_day
            self.pumpEmission_year_kg_CO2 = self.pumpEmission_day_kg_CO2 * 365
        else:
            self.pumpEmissionRate_kg_CO2_h = None
            self.pumpEmission_day_kg_CO2 = None
            self.pumpEmission_year_kg_CO2 = None
        
        super().save(**args, **kwargs)
    
    class Meta:
        verbose_name = "Extraction Water"
        verbose_name_plural = "Extraction Water"
    
    
    #TODO: Add save method to calculate emissions based on energy rate and emission factor
    
class ImportedWater(models.Model):
    id=models.AutoField(primary_key=True)
    sourceName = models.CharField(max_length=100, help_text="Name of the imported water source")
    quantity_m3_d = models.FloatField(help_text="Quantity in cubic meters per day")
    price_EUR_m3 = models.FloatField(help_text="Price in EUR per cubic meter") #TODO : Check if it's EUR or M.U.
    
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
    
class CoverageWaterSupply(models.Model):
    id = models.AutoField(primary_key=True)
    city = models.ForeignKey(City, on_delete=models.DO_NOTHING, null=True, help_text="City code from common.City")
    coveredArea_km2 = models.FloatField( help_text="Covered area in square kilometers")
    year = models.IntegerField()
    coveragePCT = models.FloatField(help_text="Coverage of users in percentage")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.city} - covered area: {self.coveredArea_km2} km2. Coverage: {self.coveragePCT} %"

    class Meta:
        verbose_name = "Coverage Water Supply"
        verbose_name_plural = "Coverage Water Supply Records"    

class NonRevenueWater(models.Model):
    class LossesTypes(models.TextChoices):
        Apparent = 'A','Apparent'
        Real = 'R', 'Real'
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
    UnavoidableLossses_PCT = models.FloatField(help_text="Unavoidable losses in percentage")
    ILI = models.FloatField(help_text="Infrastructure Leakage Index") #Infrastructure Leakage Index -TODO: this should be calculated from losses
    last_updated = models.DateTimeField(default=timezone.now)
    
    def clean(self):
        valid_types = {
            self.type.Apparent: ['CM', 'UA', 'DE', 'OT'],
            self.type.Real: ['LP', 'LS', 'LM', 'OT']
        }
        
        if self.type in valid_types and self.specificLoss not in valid_types[self.type]:
            raise ValidationError("Invalid loss specification for this loss type.")
        else:
            pass
    
    def __str__(self):
        
        return f"{self.year}: Losses: {self.type} - {self.specificLoss} - {self.loss_Quantity_m3} m3"

    class Meta:
        verbose_name = "Non Revenue Water"
        verbose_name_plural = "Non Revenue Water Records"
    
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
    region = models.ForeignKey(Region, on_delete=models.DO_NOTHING)
    areaName = models.CharField(max_length=100)
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

    def __str__(self):
        return f"{self.source.SourceName} - {self.year}: {self.productionDay} Mm3/day"
    
    def save(self, *args, **kwargs):
        from Energy.models import ElectricityCost
        
        # Get all extraction wells that use THIS specific source
        extraction_wells = ExtractionWater.objects.filter(
        source=self.source
    )
        
        # Calculate total production from all wells using this source
        calculated_production = extraction_wells.aggregate(
            total_production=models.Sum(
                models.F('pumpflow_m3_s') * models.F('OperationTime_h_day') * 86400 / 1e6  # Convert to Mm3/day
            )
        )['total_production'] or 0.0
        
        self.productionDay = calculated_production
        self.productionYR = self.productionDay * 365
        
        # Find wich region this source belongs to
        try:
            source_region = Region.objects.get(
                geom__contains=self.source.geom.centroid
            )
        except Region.DoesNotExist:
            source_region = None
        
        try:
            elec_cost = ElectricityCost.objects.filter(
                region=source_region,
                year=self.year
            ).cost_EUR_kWh
        except ElectricityCost.DoesNotExist:
            elec_cost = 0.15 #TODO : set a default value or handle missing cost appropriately
            
        calculated_cost_day = extraction_wells.aggregate(
            total_cost=models.Sum(
                models.F('pumpEnergyRate_kWh_h') * models.F('OperationTime_h_day') * elec_cost)
        )['total_cost'] or 0.0
        
        self.costDay = calculated_cost_day
        self.costYR = self.costDay * 365
        
        super().save(*args, **kwargs)
        
    class Meta:
        verbose_name = "Total Water Production"
        verbose_name_plural = "Total Water Production Records"