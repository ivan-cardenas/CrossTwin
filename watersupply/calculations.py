from .models import *

def _get_consumption_capita(Province, year):
    consumption_capita = ConsumptionCapita.objects.get(province=Province,year=year)['consumption_capita_L_d']
    
    return consumption_capita

def calculate_total_production_day():
    total_extracted_res = ExtractionWater.objects.filter(is_active=True, type='residential').aggregate(total=models.Sum('pumpflow_m3_s'))['total']
    total_extracted_res_day = total_extracted_res*86400
    total_imported = ImportedWater.objects.filter(is_active=True).aggregate(total=models.Sum('quantity_m3_d'))['total']
    
    return total_extracted_res_day + total_imported

def calculate_supply_security(Province):
    cities = City.objects.filter(province=Province)
    demand = TotalWaterDemand.objects.filter(City=cities).aggregate(total=models.Sum('demand_m3_d'))['total']
    production = calculate_total_production_day()
    
    if demand and production:
        supply_security = demand / production
    else:
        supply_security = None

    return supply_security



