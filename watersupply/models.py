from django.contrib.gis.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from common.models import Region, City, Neighborhood, CoordinateSystem



# Create your models here.
class ConsumptionCapita(models.Model):
    id=models.AutoField(primary_key=True)
    city = models.ForeignKey(City, on_delete=models.CASCADE)
    year = models.IntegerField()
    consumption_capita_L_d = models.FloatField() # L/person/day
    total_consumption_m3_yr = models.FloatField()
    last_updated = models.DateTimeField(default=timezone.now)

    def save(self):
        if self.consumption_capita_L_d < 0:
            raise ValidationError("Consumption Capita cannot be negative")
        self.total_consumption_m3_yr = self.consumption_capita_L_d * 365 * 1000 * City.currentPopulation
        super().save()
        

    def __str__(self):
        return f"{self.region} - {self.year}: {self.consumption_capita_L_d} L/person/day"
    
class TotalWaterDemand(models.Model):
    city = models.ForeignKey(City, on_delete=models.CASCADE)
    year = models.IntegerField()
    demandDay = models.FloatField() # Mm3/day
    demandYR = models.FloatField()  # Mm3/year
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.region} - {self.year}: {self.demandDay} Mm3/day"
    
class SupplySecurity(models.Model):
    city = models.ForeignKey(City, on_delete=models.CASCADE)
    year = models.IntegerField()
    supply_security_pct = models.FloatField()   # %
    security_goal_pct = models.FloatField() # %
    service_time_hours = models.FloatField() # hours/day
    last_updated = models.DateTimeField(default=timezone.now) 
    
    def __str__(self):
        return f"{self.region} - {self.year}: {self.supply_security}"
    
class PipeNetwork(models.Model):
    id = models.AutoField(primary_key=True)
    length_km = models.FloatField() # km
    geom = models.MultiLineStringField(srid=CoordinateSystem)
    maitenanceCost_EUR_km = models.FloatField(null=True) # EUR/km
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.length_km} km"   
    
class UsersLocation(models.Model):
    id = models.AutoField(primary_key=True)
    neighborhood = models.ForeignKey(Neighborhood, on_delete=models.DO_NOTHING)
    usersTotal = models.IntegerField()
    ResidentialUsers = models.IntegerField(null=True)
    CommercialUsers = models.IntegerField(null=True)
    IndustrialUsers = models.IntegerField(null=True)
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.neighborhood} - {self.usersTotal} users"
    
class MeteredResidential(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(UsersLocation, on_delete=models.DO_NOTHING)
    installed_meters = models.IntegerField()
    functional_meters = models.IntegerField()
    collected_meters = models.IntegerField()
    userTariff_EUR_m3 = models.FloatField()
    userAffordability_PCT = models.FloatField()
    Recovery_EUR = models.FloatField()
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.neighborhood} - {self.meters} installed meters. {self.Recovery_EUR} % recoverd"
    
    
class AvailableFreshWater(models.Model):
    id=models.AutoField(primary_key=True)
    SourceName = models.CharField(max_length=100)
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    infiltrationRate_cm_h = models.FloatField()
    infiltrationDepth_cm = models.FloatField()
    totalQuantity_Mm3 = models.FloatField()
    yield_Mm3_year = models.FloatField()
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.SourceName} - {self.totalQuantity_Mm3} Mm3"
    
class ExtractionWater(models.Model):
    id=models.AutoField(primary_key=True)
    source = models.ForeignKey(AvailableFreshWater,
                               on_delete=models.DO_NOTHING)
    geom = models.MultiPointField(srid=CoordinateSystem)
    stationName = models.CharField(max_length=100)
    pumpflow_m3_s = models.FloatField()
    pumpMaxFlow_m3_s = models.FloatField()
    OperationTime_h_day = models.FloatField()
    depth_m = models.FloatField()
    pumpEfficiency = models.FloatField()
    pumpEnergyRate_kWh_h = models.FloatField()
    pumpEmissionRate_kg_CO2_h = models.FloatField()
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.Source} - {self.stationName}"
    
class ImportedWater(models.Model):
    id=models.AutoField(primary_key=True)
    sourceName = models.CharField(max_length=100)
    quantity_m3_d = models.FloatField()
    price_EUR_m3 = models.FloatField()
    
    def __str__(self):
        return f"{self.sourceName} - {self.quantity_m3_d} m3/d"

    
class WaterTreatment(models.Model):
    id = models.AutoField(primary_key=True)
    year = models.IntegerField()
    UnitaryOPEX_EUR_m3 = models.FloatField()
    treatment_efficiency = models.FloatField()
    samplesWaterQuality_OK = models.IntegerField()
    samplesWaterQualityTaken = models.IntegerField()
    EnergyConsumption_MW_day = models.FloatField()
    acceptanceRate = models.FloatField()
    geom = models.MultiPointField(srid=CoordinateSystem)
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Treatement - {self.year}: Accepatance rate: {self.acceptanceRate} %"
    
    
class CoverageWaterSupply(models.Model):
    id = models.AutoField(primary_key=True)
    Neighborhood = models.ForeignKey(Neighborhood, on_delete=models.DO_NOTHING)
    coveredArea_km2 = models.FloatField()
    year = models.IntegerField()
    coveragePCT = models.FloatField()
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
                            default=LossesTypes.Apparent)
    specificLoss = models.CharField(max_length=100, 
                            choices=LossesChoices.choices,
                            default=LossesChoices.ConsumerMeter)
    loss_Quantity_m3 = models.FloatField()
    WaterCost_EUR_day = models.FloatField()
    UnavoidableLossses_PCT = models.FloatField()
    ILI = models.FloatField() # Infrastructure Leakage Index
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
    year = models.IntegerField()
    UnitaryOPEX_EUR_m3 = models.FloatField()
    totalOPEX_EUR = models.FloatField()
    
    
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
    geom = models.MultiPolygonField(srid=CoordinateSystem)
    region = models.ForeignKey(Region, on_delete=models.DO_NOTHING)
    areaName = models.CharField(max_length=100)
    SensibilityLevel = models.IntegerField(
        choices=SensibilityChoices.choices,
        default=SensibilityChoices.NotAffected
                                           )
    year = models.IntegerField()
    areaAffected_km2 = models.FloatField()
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.year}: {self.areaAffected_km2} km2"