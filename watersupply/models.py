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
    
class SupplySecurity(models.Model):
    city = models.ForeignKey(City, on_delete=models.CASCADE, help_text="City code from common.City")
    year = models.IntegerField()
    supply_security_pct = models.FloatField(help_text="in percent")   # %
    security_goal_pct = models.FloatField(help_text="in percent") # %
    service_time_hours = models.FloatField(help_text="in hours per day") # hours/day
    last_updated = models.DateTimeField(default=timezone.now) 
    
    def __str__(self):
        return f"{self.region} - {self.year}: {self.supply_security}"
    
class PipeNetwork(models.Model):
    id = models.AutoField(primary_key=True)
    length_km = models.FloatField(help_text="in kilometers") # km
    geom = models.MultiLineStringField(srid=COORDINATE_SYSTEM)
    maitenanceCost_EUR_km = models.FloatField(null=True, help_text="in EUR per kilometer") # TODO: check if units are EUR or M.U.
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.length_km} km"   
    
class UsersLocation(models.Model):
    id = models.AutoField(primary_key=True)
    neighborhood = models.ForeignKey(Neighborhood, on_delete=models.DO_NOTHING, help_text="Neighborhood code from common.Neighborhood")
    usersTotal = models.IntegerField(help_text="Total number of users in the neighborhood")
    ResidentialUsers = models.IntegerField(null=True, help_text="Number of residential users")
    CommercialUsers = models.IntegerField(null=True, help_text="Number of commercial users")
    IndustrialUsers = models.IntegerField(null=True, help_text="Number of industrial users")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.neighborhood} - {self.usersTotal} users"
    
class MeteredResidential(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(UsersLocation, on_delete=models.DO_NOTHING, help_text="UsersLocation ID from common.UsersLocation")
    installed_meters = models.IntegerField(help_text="Number of installed meters")
    functional_meters = models.IntegerField(help_text="Number of functional meters")
    collected_meters = models.IntegerField(help_text="Number of collected meters")
    userTariff_EUR_m3 = models.FloatField(help_text="in EUR per cubic meter")
    userAffordability_PCT = models.FloatField(help_text="in percent")
    Recovery_EUR = models.FloatField(help_text="in EUR")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.user.neighborhood} - {self.installed_meters} installed meters. {self.Recovery_EUR} EUR recovered"
    
    
class AvailableFreshWater(models.Model):
    id=models.AutoField(primary_key=True)
    SourceName = models.CharField(max_length=100, help_text="Name of the water source")
    geom = models.MultiPolygonField(srid=COORDINATE_SYSTEM)
    infiltrationRate_cm_h = models.FloatField(help_text="Infiltration rate in centimeters per hour")
    infiltrationDepth_cm = models.FloatField(help_text="Infiltration depth in centimeters")
    totalQuantity_Mm3 = models.FloatField(help_text="total quantity in million cubic meters")
    yield_Mm3_year = models.FloatField(help_text="Yield in million cubic meters per year")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.SourceName} - {self.totalQuantity_Mm3} Mm3"
    
class ExtractionWater(models.Model):
    id=models.AutoField(primary_key=True)
    source = models.ForeignKey(AvailableFreshWater,
                               on_delete=models.DO_NOTHING)
    geom = models.MultiPointField(srid=COORDINATE_SYSTEM)
    stationName = models.CharField(max_length=100, help_text="Name of the extraction station")
    pumpflow_m3_s = models.FloatField(help_text="Pump flow in cubic meters per second")
    pumpMaxFlow_m3_s = models.FloatField(help_text="Maximum pump flow in cubic meters per second")
    OperationTime_h_day = models.FloatField(help_text="Operation time in hours per day")
    depth_m = models.FloatField(help_text="Depth in meters")
    pumpEfficiency = models.FloatField(help_text="Pump efficiency in percent")
    pumpEnergyRate_kWh_h = models.FloatField(help_text="Pump energy rate in kilowatt-hours per hour")
    pumpEmissionRate_kg_CO2_h = models.FloatField(help_text="Pump emission rate in kilograms of CO2 per hour") #TODO: This should be calculated from the energy rate and the electricity emission factor
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.source} - {self.stationName}"
    
class ImportedWater(models.Model):
    id=models.AutoField(primary_key=True)
    sourceName = models.CharField(max_length=100, help_text="Name of the imported water source")
    quantity_m3_d = models.FloatField(help_text="Quantity in cubic meters per day")
    price_EUR_m3 = models.FloatField(help_text="Price in EUR per cubic meter") #TODO : Check if it's EUR or M.U.
    
    def __str__(self):
        return f"{self.sourceName} - {self.quantity_m3_d} m3/d"

    
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
    
    
class CoverageWaterSupply(models.Model):
    id = models.AutoField(primary_key=True)
    Neighborhood = models.ForeignKey(Neighborhood, on_delete=models.DO_NOTHING)
    coveredArea_km2 = models.FloatField( help_text="Covered area in square kilometers")
    year = models.IntegerField()
    coveragePCT = models.FloatField(help_text="Coverage of users in percentage")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.Neighborhood} - covered area: {self.coveredArea_km2} km2. Coverage: {self.coveragePCT} %"
    

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

class OPEX(models.Model):
    id = models.AutoField(primary_key=True)
    year = models.IntegerField(help_text="Year of operation")
    UnitaryOPEX_EUR_m3 = models.FloatField(help_text="Unitary OPEX in EUR per cubic meter")
    totalOPEX_EUR = models.FloatField(help_text="Total OPEX in EUR")
    
    
    def __str__(self):
        return f"{self.year}: {self.UnitaryOPEX_EUR_m3} EUR/m3"

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