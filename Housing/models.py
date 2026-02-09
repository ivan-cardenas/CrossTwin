from django.contrib.gis.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings

COORDINATE_SYSTEM = settings.COORDINATE_SYSTEM
AFFORDABILITY_STRESS_LEVELS = [('low', 'Low'), ('moderate', 'Moderate'), ('high', 'High')] #TODO: check if these are the right thresholds for the affordability stress levels, 
                                                                            #  or if we should use different thresholds based on the literature

# Create your models here.
class HousingSupplyDemand(models.Model):
    id = models.AutoField(primary_key=True)
    neighborhood = models.ForeignKey("common.Neighborhood", verbose_name="Neighborhood", on_delete=models.DO_NOTHING)
    year = models.IntegerField(help_text="Year of the housing supply/demand data")
    supply_units = models.IntegerField(help_text="Number of housing units supplied")
    demand_units = models.IntegerField(help_text="Number of housing units demanded")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Housing Supply/Demand {self.year} for {self.neighborhood}"
    
    class Meta:
        verbose_name = "Housing Supply and Demand"
        verbose_name_plural = "Housing Supply and Demand Records"
        
class CentralBankPolicy(models.Model):
    id = models.AutoField(primary_key=True)
    region = models.ForeignKey("common.Region", verbose_name="Region", on_delete=models.DO_NOTHING)
    year = models.IntegerField(help_text="Year of the policy data")
    interest_rate = models.FloatField(help_text="Central bank interest rate in percentage (%)")
    LTV_limit = models.FloatField(help_text="Loan-to-Value limit in percentage (%)")
    LTI_limit = models.FloatField(help_text="Loan-to-Income limit in percentage (%)")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Central Bank Policy {self.year} for {self.region}"
    
    class Meta:
        verbose_name = "Central Bank Policy"
        verbose_name_plural = "Central Bank Policies"


class CreditSupplyConditions(models.Model):
    id = models.AutoField(primary_key=True)
    region = models.ForeignKey("common.Region", verbose_name="Region", on_delete=models.DO_NOTHING)
    year = models.IntegerField(help_text="Year of the credit supply conditions data")
    mortgageRate = models.FloatField(help_text="Mortgage rate in percentage (%)")
    mortgage_approval_rate = models.FloatField(help_text="Mortgage approval rate in percentage (%)")
    average_down_payment = models.FloatField(help_text="Average down payment as a percentage of property value (%)")
    last_updated = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Credit Supply Conditions {self.year} for {self.region}"
    
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
        self.priceToRentRatio = self.property.price / self.annualRent if self.annualRent != 0 else 0
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Rental"
        verbose_name_plural = "Rentals"
        
    
        
class HousePriceIndex(models.Model):
    id = models.AutoField(primary_key=True)
    neighborhood = models.ForeignKey("common.Neighborhood", verbose_name="Neighborhood", on_delete=models.DO_NOTHING)
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
    neighborhood = models.ForeignKey("common.Neighborhood", verbose_name="Neighborhood", on_delete=models.DO_NOTHING)
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
        
    