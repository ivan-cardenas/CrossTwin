from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse, Http404
from django.core.serializers import serialize
from django.contrib.gis.db import models as gis_models
from django.db import connection
from django.apps import apps

from .models import *
from common.models import Province, City, Neighborhood

# Create your views here.



def _calculate_total_production_day(Watershed, year):
    total_extracted = ExtractionWater.objects.filter(Watershed=Watershed).aggregate(total=models.Sum('pumpflow_m3_s'))['total']
    total_extracted_day = total_extracted*86400 
    total_imported = ImportedWater.objects.filter(Province=Province).aggregate(total=models.Sum('quantity_m3_d'))['total']
    
    return total_extracted_day + total_imported

def _get_consumption_capita(City, year):
    consumption_capita = ConsumptionCapita.objects.get(City=City,year=year)['consumption_capita_L_d']
    
    return consumption_capita

def water_indicators(request, Province_id, year):
    """Single view that calculates all indicators"""
    
    try:
        Province = get_object_or_404(Province, pk=Province_id)
        total_supply = _calculate_total_production_day(Province, year)
        consumption_capita_Province = _get_consumption_capita(Province, year)
        total_demand = consumption_capita_Province * Province.currentPopulation
    except:
        # Mock data for demo
        Province = type('Province', (), {
            'name': 'Demo Province (No Data)',
            'currentPopulation': 1500000,
            'pk': Province_id
        })()
        
        total_supply = 119120  # m³/day (0.8 m³/s extraction + 50k import)
        consumption_capita_Province = 0.120  # m³/person/day
        total_demand = consumption_capita_Province * Province.currentPopulation
    
    difference = total_supply - total_demand
    supply_security = (total_supply / total_demand * 100) if total_demand > 0 else 0
    
    context = {
        'Province': Province,
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
    """Main page with Province/year selector"""
    Provinces = Province.objects.all().order_by('ProvinceName')
    
    if not Provinces.exists():
        Provinces = [
            type('Province', (), {'id': 1, 'ProvinceName': 'Amsterdam Metropolitan Area'})(),
            type('Province', (), {'id': 2, 'ProvinceName': 'Rotterdam Province'})(),
            type('Province', (), {'id': 3, 'ProvinceName': 'Utrecht Province'})(),
        ]
    
    context = {
        'Provinces': Provinces,
    }
    return render(request, 'watersupply/select_filters.html', context)