from .models import *

def calculate_total_production_day():
    total_extracted_res = ExtractionWater.objects.filter(is_active=True, type='residential').aggregate(total=models.Sum('pumpflow_m3_s'))['total']
    total_extracted_res_day = total_extracted_res*86400
    total_imported = ImportedWater.objects.filter(is_active=True).aggregate(total=models.Sum('quantity_m3_d'))['total']
    
    return total_extracted_res_day + total_imported

def demand_supply_diff(cities:dict):
    difference = calculate_total_production_day() - TotalWaterDemand.objects.filter(City=cities).aggregate(total=models.Sum('demand_m3_d'))['total']

    return difference

