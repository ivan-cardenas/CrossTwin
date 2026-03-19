from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse, Http404
from django.core.serializers import serialize
from django.contrib.gis.db import models as gis_models
from django.db import connection
from django.apps import apps

from .models import *
from common.models import Province as PM
from .calculations import _get_consumption_capita, calculate_supply_security
# Create your views here.
from django.contrib.gis.db.models.functions import Intersection, Length
from django.contrib.gis.measure import D


MAX_SUPPLY_M3    = 20_000_000   # 20 Mm³/yr = full bar
MAX_CONSUMPTION  = 200          # 200 L/p/day = full bar
MAX_NETWORK      = 5_000        # 5000 km = full bar
MAX_OPEX         = 10_000_000   # €10M = full bar

def water_indicators(request, location, year):
    """Single view that calculates all indicators"""

    try:
        province = get_object_or_404(PM, ProvinceName=location)
        consumption_capita_province = _get_consumption_capita(province, year)
        total_demand = consumption_capita_province * province.currentPopulation

        importedWater = (
            ImportedWater.objects
            .filter(is_active=True)
            .aggregate(total=models.Sum('quantity_m3_d'))['total'] or 0
        )

        total_supply = total_demand + importedWater  # adjust to your actual logic

        supply_security = calculate_supply_security(province)

        service_obj = SupplySecurity.objects.get(province=province, year=year)
        serviceTime = service_obj.serviceTime_h_day  # instance attr, not dict

        network_length = (
            PipeNetwork.objects
            .filter(geom__intersects=province.geom)       # lowercase province
            .annotate(clipped=Intersection('geom', province.geom))
            .annotate(clipped_length=Length('clipped'))
            .aggregate(total=Sum('clipped_length'))['total']
        )
        network_length = network_length.km if network_length else 0

        availableWater = (
            AvailableFreshWater.objects
            .filter(geom__intersects=province.geom)       # lowercase province
            .aggregate(total=Sum('totalQuantity_Mm3'))['total'] or 0
        )

        opex = (
            OPEX.objects
            .filter(year=year)                            # filter, not get → then aggregate
            .aggregate(total=models.Sum('totalOPEX_EUR'))['total'] or 0
        )

    except Exception as e:
        print(f"[water_indicators] falling back to mock data: {e}")

        province = type('Province', (), {
            'ProvinceName': 'Demo Province (No Data)',
            'currentPopulation': 500_000,
        })()

        total_supply = 119_120*365
        consumption_capita_province = 120 # L/p
        total_demand = consumption_capita_province/1000 * province.currentPopulation # 
        importedWater = 50_000
        supply_security = (total_supply / total_demand * 100) if total_demand > 0 else 0
        serviceTime = 8
        network_length = 0
        availableWater = 100 
        opex = 0

    print("total_demand", total_demand)
    context = {
        'Province': province,                            # lowercase — the instance
        'year': year,
        'indicators': {
            'total_supply_Mm3': round(total_supply / 1_000_000, 2),  # pre-divided by 1_000_000,
            'total_supply_percent': round(total_supply/1000000 / availableWater * 100, 2),
            'consumption_capita': consumption_capita_province,
            'imported_water': importedWater,
            'supply_security': supply_security,
            'service_time': serviceTime,
            'network_length': network_length,
            'available_water': availableWater,
            'opex': opex,
        }
    }

    return render(request, 'watersupply/water_indicators.html', context)

def recalculate_indicators(request, location, year):
    """Partial re-render triggered by HTMX slider"""
    
    consumption = float(request.GET.get('consumption', 120))  # L/p/day from slider

    try:
        province = get_object_or_404(PM, ProvinceName=location)
        population = province.currentPopulation
        importedWater = (
            ImportedWater.objects.filter(is_active=True)
            .aggregate(total=models.Sum('quantity_m3_d'))['total'] or 0
        )
        availableWater = (
            AvailableFreshWater.objects
            .filter(geom__intersects=province.geom)
            .aggregate(total=Sum('totalQuantity_Mm3'))['total'] or 0
        )
        opex_total = (
            OPEX.objects.filter(year=year)
            .aggregate(total=models.Sum('totalOPEX_EUR'))['total'] or 0
        )
        service_hours_max = 8760

    except Exception as e:
        print(f"[recalculate] fallback: {e}")
        population = 500_000
        importedWater = 50_000
        availableWater = 100
        opex_total = 2_000_000
        service_hours_max = 8760

    # ── all math in Python ────────────────────────────────
    demand_m3_yr   = (consumption / 1000) * population * 365
    supply_m3_yr   = demand_m3_yr + importedWater
    supply_Mm3     = round(supply_m3_yr / 1_000_000, 2)
    
    supply_security = min(
        round(supply_Mm3 / availableWater * 100, 1), 100
    ) if availableWater > 0 else 0

    service_time = (
        service_hours_max 
        if supply_m3_yr >= demand_m3_yr 
        else round(service_hours_max * (supply_m3_yr / demand_m3_yr), 0)
    )

    opex_per_m3 = opex_total / supply_m3_yr if supply_m3_yr > 0 else 0
    opex = round(supply_m3_yr * opex_per_m3)

    indicators = {
        'consumption_capita': consumption,
        'total_supply_Mm3': supply_Mm3,
        'total_supply_percent': min(supply_Mm3 / availableWater * 100, 100) if availableWater > 0 else 0,
        'supply_security': supply_security,
        'service_time': service_time,
        'service_time_percent': round(service_time / service_hours_max * 100, 1),
        'opex': opex,
        'opex_percent': min(opex / 10_000_000 * 100, 100),
        'consumption_percent': min(consumption / 300 * 100, 100),
    }

    # returns only the partial template, not the full page
    return render(request, 'watersupply/partials/indicators_grid.html', {'indicators': indicators})