from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse, Http404
from django.core.serializers import serialize
from django.contrib.gis.db import models as gis_models
from django.db import connection
from django.apps import apps

from .models import *
from common.models import Region, City, Neighborhood

# Create your views here.
def _calculate_total_production_day(region, year):
    total_extracted = ExtractionWater.objects.filter(region=region).aggregate(total=models.Sum('pumpflow_m3_s'))['total']
    total_extracted_day = total_extracted*86400 
    total_imported = ImportedWater.objects.filter(region=region).aggregate(total=models.Sum('quantity_m3_d'))['total']
    
    return total_extracted_day + total_imported

def _get_consumption_capita(region, year):
    consumption_capita = ConsumptionCapita.objects.get(
        region=region,
        year=year
    )
    return consumption_capita

def water_indicators(request, region_id, year):
    """Single view that calculates all indicators"""
    
    try:
        region = get_object_or_404(Region, pk=region_id)
        total_supply = _calculate_total_production_day(region, year)
        consumption_capita_region = _get_consumption_capita(region, year)
        total_demand = consumption_capita_region * region.currentPopulation
    except:
        # Mock data for demo
        region = type('Region', (), {
            'name': 'Demo Region (No Data)',
            'currentPopulation': 1500000,
            'pk': region_id
        })()
        
        total_supply = 119120  # m³/day (0.8 m³/s extraction + 50k import)
        consumption_capita_region = 0.120  # m³/person/day
        total_demand = consumption_capita_region * region.currentPopulation
    
    difference = total_supply - total_demand
    supply_security = (total_supply / total_demand * 100) if total_demand > 0 else 0
    
    context = {
        'region': region,
        'year': year,
        'indicators': {
            'total_supply': total_supply,
            'total_demand': total_demand,
            'difference': difference,
            'supply_security': supply_security,
        }
    }
    
    return render(request, 'watersupply/water_indicators.html', context)

def water_indicators_main(request):
    """Main page with region/year selector"""
    regions = Region.objects.all().order_by('regionName')
    
    if not regions.exists():
        regions = [
            type('Region', (), {'id': 1, 'regionName': 'Amsterdam Metropolitan Area'})(),
            type('Region', (), {'id': 2, 'regionName': 'Rotterdam Region'})(),
            type('Region', (), {'id': 3, 'regionName': 'Utrecht Province'})(),
        ]
    
    context = {
        'regions': regions,
    }
    return render(request, 'watersupply/select_filters.html', context)